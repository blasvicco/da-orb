"""This module contains tests for the document viewset"""

# General imports
import tempfile

# Lib imports
import pytest
from allure import step
from rest_framework.test import APIRequestFactory

# App imports
from core.modules.report.exception import ReportError
from core.modules.storage.exception import StorageError
from drf_api.models import (
	MBucketFile,
	MChatSession,
	MDocumentTemplate,
	MOrganization,
	MProject,
)
from drf_api.resources.document.main import VSDocument

pytestmark = pytest.mark.django_db

_factory = APIRequestFactory()
_ROWS = [{"InvoiceNumber": "12345", "LineItem": "Widget", "Qty": 1}]


def _make_org(slug="acme"):
	"""Create a persisted MOrganization instance"""
	return MOrganization.objects.create(name=slug, slug=slug)


def _make_request(data, secret="test-secret"):
	"""Build a DRF-compatible generate() POST request with a valid shared-secret header"""
	return _factory.post("/", data, format="json", HTTP_X_N8N_SECRET=secret)


def _make_rendered_pdf():
	"""Create a real temporary file standing in for a rendered PDF, so os.path.getsize succeeds"""
	with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as pdf_file:
		pdf_file.write(b"%PDF-1.4 fake")
		return pdf_file.name


def test_generate_creates_bucket_file_and_writes_to_storage(mocker, settings):
	"""Test generate renders the template, creates the MBucketFile row, and writes it to storage"""

	with step(
		"Arrange: A session, a mocked renderer and storage driver, and a valid payload."
	):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		mock_freport = mocker.patch("drf_api.resources.document.main.FReport")
		mock_freport.get_instance.return_value.render.return_value = (
			_make_rendered_pdf()
		)
		mock_fstorage = mocker.patch("drf_api.resources.document.main.FStorage")
		request = _make_request(
			{
				"data": _ROWS,
				"document_type": "invoice",
				"name": "factura_12345",
				"session_id": session.id,
			}
		)

	with step("Act: Call generate."):
		response = VSDocument.as_view({"post": "generate"})(request)

	with step("Assert: The record is created, rendered, and uploaded to storage."):
		assert response.status_code == 201
		bucket_file = MBucketFile.objects.get(id=response.data["id"])
		assert bucket_file.name == "factura_12345.pdf"
		assert bucket_file.mime_type == "application/pdf"
		assert bucket_file.origin == "workflow_generated"
		assert bucket_file.storage_path == bucket_file.build_storage_key()
		mock_freport.get_instance.return_value.render.assert_called_once()
		assert mock_freport.get_instance.return_value.render.call_args[0][1] == {
			"rows": _ROWS,
			"params": {},
			"subreports": {},
			"section_visibility": {},
			"object_visibility": {"LogoImage2": False},
		}
		mock_fstorage.get_instance.return_value.upload.assert_called_once()


def test_generate_passes_params_and_subreports_to_the_renderer(mocker, settings):
	"""Test generate forwards optional params/subreports through to the render call unchanged"""

	with step(
		"Arrange: A session, a mocked renderer, and a payload carrying params/subreports."
	):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		mock_freport = mocker.patch("drf_api.resources.document.main.FReport")
		mock_freport.get_instance.return_value.render.return_value = (
			_make_rendered_pdf()
		)
		mocker.patch("drf_api.resources.document.main.FStorage")
		params = {"dockey@": 45501, "objectid@": 13}
		subreports = {"TaxDetails.rpt": {"rows": [{"RATE": 21}]}}
		request = _make_request(
			{
				"data": _ROWS,
				"document_type": "invoice",
				"name": "factura_12345",
				"params": params,
				"session_id": session.id,
				"subreports": subreports,
			}
		)

	with step("Act: Call generate."):
		response = VSDocument.as_view({"post": "generate"})(request)

	with step("Assert: params/subreports reached the render call unchanged."):
		assert response.status_code == 201
		assert mock_freport.get_instance.return_value.render.call_args[0][1] == {
			"rows": _ROWS,
			"params": params,
			"subreports": subreports,
			"section_visibility": {},
			"object_visibility": {"LogoImage2": False},
		}


def test_generate_passes_section_visibility_to_the_renderer(mocker, settings):
	"""Test generate forwards an optional section_visibility override through to the render call unchanged"""

	with step(
		"Arrange: A session, a mocked renderer, and a payload carrying section_visibility."
	):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		mock_freport = mocker.patch("drf_api.resources.document.main.FReport")
		mock_freport.get_instance.return_value.render.return_value = (
			_make_rendered_pdf()
		)
		mocker.patch("drf_api.resources.document.main.FStorage")
		section_visibility = {
			"ReportHeaderSection3": True,
			"ReportFooterSection17": True,
		}
		request = _make_request(
			{
				"data": _ROWS,
				"document_type": "invoice",
				"name": "factura_12345",
				"section_visibility": section_visibility,
				"session_id": session.id,
			}
		)

	with step("Act: Call generate."):
		response = VSDocument.as_view({"post": "generate"})(request)

	with step("Assert: section_visibility reached the render call unchanged."):
		assert response.status_code == 201
		assert mock_freport.get_instance.return_value.render.call_args[0][1] == {
			"rows": _ROWS,
			"params": {},
			"subreports": {},
			"section_visibility": section_visibility,
			"object_visibility": {"LogoImage2": False},
		}


def test_generate_defaults_params_and_subreports_when_absent(mocker, settings):
	"""Test generate tolerates a payload with no params/subreports, defaulting both to {}"""

	with step(
		"Arrange: A session, a mocked renderer, and a payload without params/subreports."
	):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		mock_freport = mocker.patch("drf_api.resources.document.main.FReport")
		mock_freport.get_instance.return_value.render.return_value = (
			_make_rendered_pdf()
		)
		mocker.patch("drf_api.resources.document.main.FStorage")
		request = _make_request(
			{
				"data": _ROWS,
				"document_type": "invoice",
				"name": "factura_12345",
				"session_id": session.id,
			}
		)

	with step("Act: Call generate."):
		response = VSDocument.as_view({"post": "generate"})(request)

	with step("Assert: params/subreports default to empty dicts."):
		assert response.status_code == 201
		assert mock_freport.get_instance.return_value.render.call_args[0][1] == {
			"rows": _ROWS,
			"params": {},
			"subreports": {},
			"section_visibility": {},
			"object_visibility": {"LogoImage2": False},
		}


def test_generate_resolves_bucket_path_markers_in_subreports(mocker, settings):
	"""Test generate replaces a {"bucket_path": ...} marker with \\x-hex-encoded file bytes"""

	with step(
		"Arrange: A session and subreports carrying a bucket_path marker alongside a plain value."
	):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		with tempfile.NamedTemporaryFile(delete=False) as asset_file:
			asset_file.write(b"\x89PNG\r\n")
			asset_path = asset_file.name
		mock_fstorage = mocker.patch("drf_api.resources.document.main.FStorage")
		mock_fstorage.get_instance.return_value.download.return_value = asset_path
		mock_freport = mocker.patch("drf_api.resources.document.main.FReport")
		mock_freport.get_instance.return_value.render.return_value = (
			_make_rendered_pdf()
		)
		subreports = {
			"SREncabDocum": {
				"rows": [
					{
						"LogoImage": {"bucket_path": "bvs/assets/logo.png"},
						"CompnyName": "BVS SA",
					}
				]
			}
		}
		request = _make_request(
			{
				"data": _ROWS,
				"document_type": "invoice",
				"name": "factura_12345",
				"session_id": session.id,
				"subreports": subreports,
			}
		)

	with step("Act: Call generate."):
		response = VSDocument.as_view({"post": "generate"})(request)

	with step(
		"Assert: the marker was resolved via the bucket path, the plain value untouched."
	):
		assert response.status_code == 201
		mock_fstorage.get_instance.return_value.download.assert_called_once_with(
			"bvs/assets/logo.png"
		)
		resolved_row = mock_freport.get_instance.return_value.render.call_args[0][1][
			"subreports"
		]["SREncabDocum"]["rows"][0]
		assert resolved_row["LogoImage"] == "\\x89504e470d0a"
		assert resolved_row["CompnyName"] == "BVS SA"


def test_generate_degrades_to_empty_when_bucket_path_asset_is_missing(mocker, settings):
	"""Test generate resolves an unresolvable bucket_path marker to "" and still renders, instead of raising"""

	with step(
		"Arrange: A session and subreports carrying a bucket_path marker FStorage cannot download."
	):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		mock_fstorage = mocker.patch("drf_api.resources.document.main.FStorage")
		mock_fstorage.get_instance.return_value.download.side_effect = StorageError(
			"Download failed for key 'bvs/document_templates/invoice/logo.png': not found"
		)
		mock_freport = mocker.patch("drf_api.resources.document.main.FReport")
		mock_freport.get_instance.return_value.render.return_value = (
			_make_rendered_pdf()
		)
		subreports = {
			"SREncabDocum": {
				"rows": [
					{
						"LogoImage": {
							"bucket_path": "bvs/document_templates/invoice/logo.png"
						},
						"CompnyName": "BVS SA",
					}
				]
			}
		}
		request = _make_request(
			{
				"data": _ROWS,
				"document_type": "invoice",
				"name": "factura_12345",
				"session_id": session.id,
				"subreports": subreports,
			}
		)

	with step("Act: Call generate."):
		response = VSDocument.as_view({"post": "generate"})(request)

	with step(
		'Assert: generation still succeeds, LogoImage degrades to "", and LogoImage2 is hidden.'
	):
		assert response.status_code == 201
		rendered_args = mock_freport.get_instance.return_value.render.call_args[0][1]
		resolved_row = rendered_args["subreports"]["SREncabDocum"]["rows"][0]
		assert resolved_row["LogoImage"] == ""
		assert resolved_row["CompnyName"] == "BVS SA"
		assert rendered_args["object_visibility"]["LogoImage2"] is False


def test_generate_uses_the_orgs_default_template_when_set(mocker, settings):
	"""Test generate downloads and renders the org's default MDocumentTemplate instead of the system fallback"""

	with step("Arrange: A session whose org has a default invoice template set."):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		MDocumentTemplate.objects.create(
			document_type="invoice",
			is_default=True,
			name="acme_invoice",
			org=org,
			storage_path="acme/document_templates/invoice/1_acme_invoice.rpt",
		)
		mock_fstorage = mocker.patch("drf_api.resources.document.main.FStorage")
		mock_fstorage.get_instance.return_value.download.return_value = (
			"/tmp/downloaded.rpt"
		)
		mock_freport = mocker.patch("drf_api.resources.document.main.FReport")
		mock_freport.get_instance.return_value.render.return_value = (
			_make_rendered_pdf()
		)
		request = _make_request(
			{
				"data": _ROWS,
				"document_type": "invoice",
				"name": "factura_12345",
				"session_id": session.id,
			}
		)

	with step("Act: Call generate."):
		response = VSDocument.as_view({"post": "generate"})(request)

	with step(
		"Assert: the org's template was downloaded and rendered, not the system fallback."
	):
		assert response.status_code == 201
		mock_fstorage.get_instance.return_value.download.assert_called_once_with(
			"acme/document_templates/invoice/1_acme_invoice.rpt"
		)
		assert (
			mock_freport.get_instance.return_value.render.call_args[0][0]
			== "/tmp/downloaded.rpt"
		)


def test_generate_prefers_exact_bp_and_language_match_over_everything(mocker, settings):
	"""Test generate picks the (business_partner_ref, language) exact match over any less specific template"""

	with step("Arrange: A default, a BP-only match, and an exact BP+language match."):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		MDocumentTemplate.objects.create(
			document_type="invoice",
			is_default=True,
			name="default",
			org=org,
			storage_path="path/default.rpt",
		)
		MDocumentTemplate.objects.create(
			business_partner_ref="C001",
			document_type="invoice",
			name="bp_only",
			org=org,
			storage_path="path/bp_only.rpt",
		)
		exact = MDocumentTemplate.objects.create(
			business_partner_ref="C001",
			document_type="invoice",
			language="es",
			name="exact",
			org=org,
			storage_path="path/exact.rpt",
		)
		mock_fstorage = mocker.patch("drf_api.resources.document.main.FStorage")
		mock_fstorage.get_instance.return_value.download.return_value = (
			"/tmp/downloaded.rpt"
		)
		mocker.patch(
			"drf_api.resources.document.main.FReport"
		).get_instance.return_value.render.return_value = _make_rendered_pdf()
		request = _make_request(
			{
				"business_partner_ref": "C001",
				"data": _ROWS,
				"document_type": "invoice",
				"language": "es",
				"name": "factura_12345",
				"session_id": session.id,
			}
		)

	with step("Act: Call generate."):
		VSDocument.as_view({"post": "generate"})(request)

	with step("Assert: the exact BP+language match was downloaded."):
		mock_fstorage.get_instance.return_value.download.assert_called_once_with(
			exact.storage_path
		)


def test_generate_prefers_bp_only_match_over_the_org_default(mocker, settings):
	"""Test generate picks a business_partner_ref-only match over the org default when no language is given"""

	with step("Arrange: A default and a BP-only match, request naming only the BP."):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		MDocumentTemplate.objects.create(
			document_type="invoice",
			is_default=True,
			name="default",
			org=org,
			storage_path="path/default.rpt",
		)
		bp_only = MDocumentTemplate.objects.create(
			business_partner_ref="C001",
			document_type="invoice",
			name="bp_only",
			org=org,
			storage_path="path/bp_only.rpt",
		)
		mock_fstorage = mocker.patch("drf_api.resources.document.main.FStorage")
		mock_fstorage.get_instance.return_value.download.return_value = (
			"/tmp/downloaded.rpt"
		)
		mocker.patch(
			"drf_api.resources.document.main.FReport"
		).get_instance.return_value.render.return_value = _make_rendered_pdf()
		request = _make_request(
			{
				"business_partner_ref": "C001",
				"data": _ROWS,
				"document_type": "invoice",
				"name": "factura_12345",
				"session_id": session.id,
			}
		)

	with step("Act: Call generate."):
		VSDocument.as_view({"post": "generate"})(request)

	with step("Assert: the BP-only match was downloaded, not the org default."):
		mock_fstorage.get_instance.return_value.download.assert_called_once_with(
			bp_only.storage_path
		)


def test_generate_prefers_language_only_match_over_the_org_default(mocker, settings):
	"""Test generate picks a language-only match over the org default when no business_partner_ref is given"""

	with step(
		"Arrange: A default and a language-only match, request naming only the language."
	):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		MDocumentTemplate.objects.create(
			document_type="invoice",
			is_default=True,
			name="default",
			org=org,
			storage_path="path/default.rpt",
		)
		language_only = MDocumentTemplate.objects.create(
			document_type="invoice",
			language="es",
			name="language_only",
			org=org,
			storage_path="path/language_only.rpt",
		)
		mock_fstorage = mocker.patch("drf_api.resources.document.main.FStorage")
		mock_fstorage.get_instance.return_value.download.return_value = (
			"/tmp/downloaded.rpt"
		)
		mocker.patch(
			"drf_api.resources.document.main.FReport"
		).get_instance.return_value.render.return_value = _make_rendered_pdf()
		request = _make_request(
			{
				"data": _ROWS,
				"document_type": "invoice",
				"language": "es",
				"name": "factura_12345",
				"session_id": session.id,
			}
		)

	with step("Act: Call generate."):
		VSDocument.as_view({"post": "generate"})(request)

	with step("Assert: the language-only match was downloaded, not the org default."):
		mock_fstorage.get_instance.return_value.download.assert_called_once_with(
			language_only.storage_path
		)


def test_generate_rejects_unsupported_document_type(settings):
	"""Test generate rejects a document_type outside the Phase 1 fixed set"""

	with step("Arrange: A session and a payload naming an unsupported document type."):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		request = _make_request(
			{
				"data": _ROWS,
				"document_type": "purchase_order",
				"name": "po_1",
				"session_id": session.id,
			}
		)

	with step("Act: Call generate."):
		response = VSDocument.as_view({"post": "generate"})(request)

	with step("Assert: 400 is returned with UNSUPPORTED_DOCUMENT_TYPE."):
		assert response.status_code == 400
		assert response.data["error"] == "UNSUPPORTED_DOCUMENT_TYPE"


@pytest.mark.parametrize(
	"payload",
	[
		{"data": [], "description": "empty rows list is rejected"},
		{"data": "not-a-list", "description": "non-list data is rejected"},
	],
)
def test_generate_rejects_missing_data(settings, payload):
	"""Test generate rejects a payload with no usable row data"""

	with step(f"Arrange: {payload['description']}."):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		request = _make_request(
			{
				"data": payload["data"],
				"document_type": "invoice",
				"name": "factura_12345",
				"session_id": session.id,
			}
		)

	with step("Act: Call generate."):
		response = VSDocument.as_view({"post": "generate"})(request)

	with step("Assert: 400 is returned with MISSING_DATA."):
		assert response.status_code == 400
		assert response.data["error"] == "MISSING_DATA"


def test_generate_rejects_missing_name(settings):
	"""Test generate rejects a payload with a blank name"""

	with step("Arrange: A session and a payload with no name."):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		request = _make_request(
			{
				"data": _ROWS,
				"document_type": "invoice",
				"name": "",
				"session_id": session.id,
			}
		)

	with step("Act: Call generate."):
		response = VSDocument.as_view({"post": "generate"})(request)

	with step("Assert: 400 is returned with MISSING_NAME."):
		assert response.status_code == 400
		assert response.data["error"] == "MISSING_NAME"


def test_generate_returns_409_with_existing_file_when_not_forced(mocker, settings):
	"""Test generate returns the already-existing file (409) instead of re-rendering, without force_new_version"""

	with step(
		"Arrange: A session already carrying a workflow_generated file with the same name."
	):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		existing = MBucketFile.objects.create(
			name="factura_12345.pdf",
			origin="workflow_generated",
			session=session,
			size=1,
		)
		mock_freport = mocker.patch("drf_api.resources.document.main.FReport")
		request = _make_request(
			{
				"data": _ROWS,
				"document_type": "invoice",
				"name": "factura_12345",
				"session_id": session.id,
			}
		)

	with step("Act: Call generate."):
		response = VSDocument.as_view({"post": "generate"})(request)

	with step(
		"Assert: 409 is returned with the existing file, and nothing was rendered."
	):
		assert response.status_code == 409
		assert response.data["id"] == existing.id
		mock_freport.get_instance.return_value.render.assert_not_called()


def test_generate_creates_a_versioned_file_when_forced(mocker, settings):
	"""Test generate appends a datetime suffix and creates a new row when force_new_version is set"""

	with step(
		"Arrange: A session already carrying a workflow_generated file with the same name."
	):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		existing = MBucketFile.objects.create(
			name="factura_12345.pdf",
			origin="workflow_generated",
			session=session,
			size=1,
		)
		mock_freport = mocker.patch("drf_api.resources.document.main.FReport")
		mock_freport.get_instance.return_value.render.return_value = (
			_make_rendered_pdf()
		)
		mocker.patch("drf_api.resources.document.main.FStorage")
		request = _make_request(
			{
				"data": _ROWS,
				"document_type": "invoice",
				"force_new_version": True,
				"name": "factura_12345",
				"session_id": session.id,
			}
		)

	with step("Act: Call generate."):
		response = VSDocument.as_view({"post": "generate"})(request)

	with step(
		"Assert: A new, differently-named row is created, and the original is untouched."
	):
		assert response.status_code == 201
		assert response.data["id"] != existing.id
		assert response.data["name"] != existing.name
		assert response.data["name"].startswith("factura_12345_")
		assert MBucketFile.objects.filter(id=existing.id).exists()


def test_generate_returns_400_when_render_fails(mocker, settings):
	"""Test generate returns 400 when the renderer driver raises ReportError"""

	with step("Arrange: A session and a renderer that fails."):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		mock_freport = mocker.patch("drf_api.resources.document.main.FReport")
		mock_freport.get_instance.return_value.render.side_effect = ReportError("boom")
		request = _make_request(
			{
				"data": _ROWS,
				"document_type": "invoice",
				"name": "factura_12345",
				"session_id": session.id,
			}
		)

	with step("Act: Call generate."):
		response = VSDocument.as_view({"post": "generate"})(request)

	with step("Assert: 400 is returned and no row is created."):
		assert response.status_code == 400
		assert response.data["error"] == "boom"
		assert not MBucketFile.objects.exists()


def test_generate_returns_400_and_discards_the_row_when_storage_upload_fails(
	mocker, settings
):
	"""Test generate deletes the just-created MBucketFile row when the storage driver's upload raises StorageError"""

	with step(
		"Arrange: A session, a working renderer, and a storage driver that fails to upload."
	):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		mock_freport = mocker.patch("drf_api.resources.document.main.FReport")
		mock_freport.get_instance.return_value.render.return_value = (
			_make_rendered_pdf()
		)
		mock_fstorage = mocker.patch("drf_api.resources.document.main.FStorage")
		mock_fstorage.get_instance.return_value.upload.side_effect = StorageError(
			"boom"
		)
		request = _make_request(
			{
				"data": _ROWS,
				"document_type": "invoice",
				"name": "factura_12345",
				"session_id": session.id,
			}
		)

	with step("Act: Call generate."):
		response = VSDocument.as_view({"post": "generate"})(request)

	with step("Assert: 400 is returned and the row is not left behind."):
		assert response.status_code == 400
		assert response.data["error"] == "boom"
		assert not MBucketFile.objects.exists()


def test_generate_rejects_requests_without_the_shared_secret(settings):
	"""Test generate 403s when the request carries no (or the wrong) X-N8n-Secret header"""

	with step("Arrange: A session and a request with the wrong shared secret."):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		request = _make_request(
			{
				"data": _ROWS,
				"document_type": "invoice",
				"name": "factura_12345",
				"session_id": session.id,
			},
			secret="wrong-secret",
		)

	with step("Act: Call generate."):
		response = VSDocument.as_view({"post": "generate"})(request)

	with step("Assert: 403 is returned."):
		assert response.status_code == 403
