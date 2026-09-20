"""DRF document template viewset"""

# Lib imports
from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

# App imports
from core.modules.report import FReport
from core.modules.report.exception import ReportError
from core.modules.storage import FStorage
from core.modules.storage.exception import StorageError
from drf_api.models import MDocumentTemplate
from drf_api.resources.auth.helpers import resolve_request_identity
from drf_api.resources.document.constants import SUPPORTED_DOCUMENT_TYPES
from drf_api.resources.document_template.permission import PDocumentTemplate
from drf_api.resources.document_template.serializer import SDocumentTemplate

_BYTES_PER_MB = 1024 * 1024


def _validate_upload(request):
	"""Validate an upload() request; returns (name, document_type, upload) or raises ValueError."""
	name = request.data.get("name", "").strip()
	if not name:
		raise ValueError("MISSING_NAME")
	document_type = request.data.get("document_type", "")
	if document_type not in SUPPORTED_DOCUMENT_TYPES:
		raise ValueError("UNSUPPORTED_DOCUMENT_TYPE")
	upload = request.FILES.get("file")
	if not upload:
		raise ValueError("MISSING_FILE")
	if not upload.name.lower().endswith(".rpt"):
		raise ValueError("INVALID_FILE_TYPE")
	if upload.size > settings.TEMPLATE_MAX_FILE_SIZE_MB * _BYTES_PER_MB:
		raise ValueError("FILE_TOO_LARGE")
	return name, document_type, upload


class VSDocumentTemplate(viewsets.ViewSet):
	"""Document template view set — org-admin CRUD, set-default, and preview."""

	parser_classes = [FormParser, JSONParser, MultiPartParser]
	permission_classes = [PDocumentTemplate]

	@action(detail=False, methods=["post"])
	def preview(self, request, *args, **kwargs):
		"""Render an existing template against supplied sample data and return the PDF bytes directly."""
		template = self._get_owned_template(request, request.data.get("template_id"))
		rows = request.data.get("data")
		if not isinstance(rows, list) or not rows:
			return Response({"error": "MISSING_DATA"}, status=400)
		try:
			template_path = FStorage.get_instance(
				driver=settings.STORAGE_DRIVER
			).download(template.storage_path)
			pdf_path = FReport.get_instance(
				driver=settings.REPORT_RENDER_DRIVER
			).render(template_path, {"rows": rows})
		except (StorageError, ReportError) as error:
			return Response({"error": str(error)}, status=400)
		with open(pdf_path, "rb") as pdf_file:
			return HttpResponse(pdf_file.read(), content_type="application/pdf")

	@action(detail=False, methods=["delete"])
	def remove(self, request, *args, **kwargs):
		"""Delete a template owned by the requester's org, removing it from storage and the DB."""
		template = self._get_owned_template(
			request, request.query_params.get("template_id")
		)
		if template.storage_path:
			try:
				FStorage.get_instance(driver=settings.STORAGE_DRIVER).delete(
					template.storage_path
				)
			except StorageError as error:
				return Response({"error": str(error)}, status=400)
		template.delete()
		return Response(status=204)

	@action(detail=False, methods=["post"])
	def set_default(self, request, *args, **kwargs):
		"""Mark a template as its org's default for its document_type, unsetting any other default."""
		template = self._get_owned_template(request, request.data.get("template_id"))
		with transaction.atomic():
			MDocumentTemplate.objects.filter(
				org=template.org, document_type=template.document_type
			).update(is_default=False)
			template.is_default = True
			template.save(update_fields=["is_default"])
		return Response(SDocumentTemplate(template).data)

	@action(detail=False, methods=["get"])
	def templates(self, request, *args, **kwargs):
		"""Return every template owned by the requester's org, optionally filtered by document_type."""
		org = self._get_org(request)
		queryset = MDocumentTemplate.objects.filter(org=org)
		document_type = request.query_params.get("document_type")
		if document_type:
			queryset = queryset.filter(document_type=document_type)
		return Response(SDocumentTemplate(queryset, many=True).data)

	@action(detail=False, methods=["patch"])
	def update_template(self, request, *args, **kwargs):
		"""Rename, retype, and/or replace the file of a template owned by the requester's org."""
		template = self._get_owned_template(request, request.data.get("template_id"))
		name = request.data.get("name", "").strip()
		if name:
			template.name = name
		document_type = request.data.get("document_type", "")
		if document_type:
			if document_type not in SUPPORTED_DOCUMENT_TYPES:
				return Response({"error": "UNSUPPORTED_DOCUMENT_TYPE"}, status=400)
			template.document_type = document_type
		# Presence (not truthiness) decides whether these are touched, unlike name/document_type
		# above — an admin clearing an override back to "no override" submits an empty string,
		# which is a real, meaningful value here, not "field omitted".
		if "business_partner_ref" in request.data:
			template.business_partner_ref = request.data.get("business_partner_ref", "")
		if "language" in request.data:
			template.language = request.data.get("language", "")
		upload = request.FILES.get("file")
		if upload:
			error = self._replace_file(template, upload)
			if error:
				return Response({"error": error}, status=400)
		template.save()
		return Response(SDocumentTemplate(template).data)

	@action(detail=False, methods=["post"])
	def upload(self, request, *args, **kwargs):
		"""Create a new template for the requester's org and write its bytes to storage."""
		org = self._get_org(request)
		try:
			name, document_type, upload_file = _validate_upload(request)
		except ValueError as error:
			return Response({"error": str(error)}, status=400)

		template = MDocumentTemplate.objects.create(
			business_partner_ref=request.data.get("business_partner_ref", ""),
			document_type=document_type,
			language=request.data.get("language", ""),
			name=name,
			org=org,
			original_filename=upload_file.name,
		)
		template.storage_path = template.build_storage_key()
		try:
			FStorage.get_instance(driver=settings.STORAGE_DRIVER).upload(
				upload_file.temporary_file_path(),
				template.storage_path,
				"application/octet-stream",
			)
		except StorageError as error:
			template.delete()
			return Response({"error": str(error)}, status=400)
		template.save(update_fields=["storage_path"])
		return Response(SDocumentTemplate(template).data, status=201)

	def _get_org(self, request):
		"""Return the requester's org."""
		org, _, _ = resolve_request_identity(request)
		return org

	def _get_owned_template(self, request, template_id):
		"""Return the requester's MDocumentTemplate for template_id, 404ing on any ownership mismatch."""
		return get_object_or_404(
			MDocumentTemplate, id=template_id, org=self._get_org(request)
		)

	def _replace_file(self, template, upload):
		"""Validate and write a replacement file for template; returns an error code, or None on success."""
		if not upload.name.lower().endswith(".rpt"):
			return "INVALID_FILE_TYPE"
		if upload.size > settings.TEMPLATE_MAX_FILE_SIZE_MB * _BYTES_PER_MB:
			return "FILE_TOO_LARGE"
		template.original_filename = upload.name
		try:
			FStorage.get_instance(driver=settings.STORAGE_DRIVER).upload(
				upload.temporary_file_path(),
				template.storage_path,
				"application/octet-stream",
			)
		except StorageError as error:
			return str(error)
		return None
