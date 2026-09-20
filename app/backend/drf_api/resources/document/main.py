"""DRF document viewset"""

# General imports
import os
from datetime import UTC, datetime

# Lib imports
from django.conf import settings
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

# App imports
from core.modules.report import FReport
from core.modules.report.exception import ReportError
from core.modules.storage import FStorage
from core.modules.storage.exception import StorageError
from drf_api.models import MBucketFile, MChatSession, MDocumentTemplate
from drf_api.resources.bucket.serializer import SBucketFile
from drf_api.resources.document.constants import SUPPORTED_DOCUMENT_TYPES
from drf_api.resources.document.permission import PDocumentWrite


def _existing_bucket_file(session, name):
	"""Return the session's workflow_generated bucket file exactly named f'{name}.pdf', or None."""
	return session.bucket_files.filter(
		name=f"{name}.pdf", origin="workflow_generated"
	).first()


def _resolve_template_path(
	session, document_type, business_partner_ref="", language=""
):
	"""Return a local template path: the most specific matching MDocumentTemplate, else the bundled system fallback."""
	# Most specific first, mirroring SAP's own default-plus-override model (see
	# docs/plans/document_generation_and_templates.md §2) extended by one dimension.
	candidates = []
	if business_partner_ref and language:
		candidates.append(
			{"business_partner_ref": business_partner_ref, "language": language}
		)
	if business_partner_ref:
		candidates.append(
			{"business_partner_ref": business_partner_ref, "language": ""}
		)
	if language:
		candidates.append({"business_partner_ref": "", "language": language})
	candidates.append({"is_default": True})

	for filters in candidates:
		template = MDocumentTemplate.objects.filter(
			org=session.org, document_type=document_type, **filters
		).first()
		if template:
			return FStorage.get_instance(driver=settings.STORAGE_DRIVER).download(
				template.storage_path
			)
	return os.path.join(
		settings.REPORT_TEMPLATE_DIR, SUPPORTED_DOCUMENT_TYPES[document_type]
	)


def _resolve_bucket_assets(value):
	"""Recursively replace {"bucket_path": "..."} markers with \\x-hex-encoded file bytes.

	Keeps large static assets (e.g. a report's company logo) out of the process-definition
	schema and every n8n payload/execution record that schema travels through — only a short
	bucket path crosses that pipeline; the actual bytes are fetched here, right before
	rendering, the same way the .rpt template itself is already fetched from bucket storage.

	A bucket_path that fails to resolve (e.g. no logo uploaded yet for this org) degrades to
	"" rather than raising — a document must still generate with or without a logo, the same
	"never simply fails" fallback this plan already applies to a missing DocumentTemplate or a
	missing QR record; _suppress_empty_logo below already treats "" as "hide this object".
	"""
	if isinstance(value, dict):
		if set(value.keys()) == {"bucket_path"}:
			try:
				local_path = FStorage.get_instance(
					driver=settings.STORAGE_DRIVER
				).download(value["bucket_path"])
			except StorageError:
				return ""
			with open(local_path, "rb") as asset_file:
				return "\\x" + asset_file.read().hex()
		return {key: _resolve_bucket_assets(item) for key, item in value.items()}
	if isinstance(value, list):
		return [_resolve_bucket_assets(item) for item in value]
	return value


def _validate_generate_payload(data):
	"""Validate a generate() request payload; returns (document_type, rows, name, params, subreports, section_visibility, object_visibility) or raises ValueError."""
	document_type = data.get("document_type", "")
	if document_type not in SUPPORTED_DOCUMENT_TYPES:
		raise ValueError("UNSUPPORTED_DOCUMENT_TYPE")
	rows = data.get("data")
	if not isinstance(rows, list) or not rows:
		raise ValueError("MISSING_DATA")
	name = data.get("name", "").strip()
	if not name:
		raise ValueError("MISSING_NAME")
	params = data.get("params") or {}
	subreports = data.get("subreports") or {}
	section_visibility = data.get("section_visibility") or {}
	object_visibility = data.get("object_visibility") or {}
	return (
		document_type,
		rows,
		name,
		params,
		subreports,
		section_visibility,
		object_visibility,
	)


def _suppress_empty_logo(subreports, object_visibility):
	"""Force LogoImage2 (the SREncabDocum subreport's external logo field) hidden when its
	resolved bucket asset is empty — a blank/missing value would otherwise render as a broken
	picture rather than nothing. Targets only the subreport's own field by name: the main
	report's separate embedded-logo object is named LogoImageEmbedded (not LogoImage2), a
	deliberate rename so the two can't collide under one object_visibility key."""
	logo = (subreports.get("SREncabDocum") or {}).get("rows", [{}])[0].get("LogoImage")
	if not logo or logo == "\\x":
		object_visibility = {**object_visibility, "LogoImage2": False}
	return object_visibility


class VSDocument(viewsets.ViewSet):
	"""Document view set — workflow-generated document rendering into a session's bucket."""

	permission_classes = [PDocumentWrite]

	@action(detail=False, methods=["post"])
	def generate(self, request, *args, **kwargs):  # pylint: disable=too-many-locals
		"""Render document_type against data for session_id and write the result into its bucket."""
		try:
			(
				document_type,
				rows,
				name,
				params,
				subreports,
				section_visibility,
				object_visibility,
			) = _validate_generate_payload(request.data)
		except ValueError as error:
			return Response({"error": str(error)}, status=400)

		session = get_object_or_404(MChatSession, id=request.data.get("session_id"))

		existing = _existing_bucket_file(session, name)
		if existing and not request.data.get("force_new_version"):
			return Response(SBucketFile(existing).data, status=409)
		if existing:
			name = f"{name}_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"

		template_path = _resolve_template_path(
			session,
			document_type,
			business_partner_ref=request.data.get("business_partner_ref", ""),
			language=request.data.get("language", ""),
		)
		resolved_subreports = _resolve_bucket_assets(subreports)
		object_visibility = _suppress_empty_logo(resolved_subreports, object_visibility)
		try:
			pdf_path = FReport.get_instance(
				driver=settings.REPORT_RENDER_DRIVER
			).render(
				template_path,
				{
					"rows": rows,
					"params": params,
					"subreports": resolved_subreports,
					"section_visibility": section_visibility,
					"object_visibility": object_visibility,
				},
			)
		except ReportError as error:
			return Response({"error": str(error)}, status=400)

		bucket_file = MBucketFile.objects.create(
			mime_type="application/pdf",
			name=f"{name}.pdf",
			origin="workflow_generated",
			session=session,
			size=os.path.getsize(pdf_path),
		)
		bucket_file.storage_path = bucket_file.build_storage_key()
		try:
			FStorage.get_instance(driver=settings.STORAGE_DRIVER).upload(
				pdf_path, bucket_file.storage_path, bucket_file.mime_type
			)
		except StorageError as error:
			bucket_file.delete()
			return Response({"error": str(error)}, status=400)
		bucket_file.save(update_fields=["storage_path"])
		return Response(SBucketFile(bucket_file).data, status=201)
