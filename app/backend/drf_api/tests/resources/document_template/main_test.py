"""This module contains tests for the document template viewset"""

# General imports
import tempfile
from urllib.parse import urlencode

# Lib imports
import pytest
from allure import step
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIRequestFactory

# App imports
from core.modules.report.exception import ReportError
from core.modules.storage.exception import StorageError
from drf_api.models import MDocumentTemplate, MOrganization
from drf_api.resources.auth.helpers import set_org_admin
from drf_api.resources.document_template.main import VSDocumentTemplate

pytestmark = pytest.mark.django_db

_factory = APIRequestFactory()


def _make_org(slug="acme"):
	"""Create a persisted MOrganization instance with an admin user ('admin') already granted"""
	org = MOrganization.objects.create(name=slug, slug=slug)
	set_org_admin(org, "admin", True)
	return org


def _make_request(method, org, data=None, query=None, username="admin"):
	"""Build a DRF-compatible request acting as the given (by default, admin) username"""
	build = getattr(_factory, method)
	path = f"/?{urlencode(query)}" if query else "/"
	has_file = isinstance(data, dict) and any(
		isinstance(value, SimpleUploadedFile) for value in data.values()
	)
	kwargs = {"format": "multipart" if has_file else "json"} if data is not None else {}
	request = build(path, data=data, HTTP_X_SAP_USERNAME=username, **kwargs)
	request.get_org_slug = lambda: org.slug
	return request


def _make_rendered_pdf():
	"""Create a real temporary file standing in for a rendered PDF, so its bytes can be read back"""
	with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as pdf_file:
		pdf_file.write(b"%PDF-1.4 fake")
		return pdf_file.name


def test_templates_requires_admin():
	"""Test templates denies a non-admin requester"""

	with step("Arrange: A non-admin username."):
		org = _make_org()
		request = _make_request("get", org, username="not-an-admin")

	with step("Act: Call templates."):
		response = VSDocumentTemplate.as_view({"get": "templates"})(request)

	with step("Assert: 403 is returned."):
		assert response.status_code == 403


def test_templates_lists_only_the_owning_orgs_templates():
	"""Test templates only returns rows belonging to the requesting org"""

	with step("Arrange: Two orgs, each with their own template."):
		org = _make_org()
		other_org = _make_org(slug="other")
		matching = MDocumentTemplate.objects.create(
			document_type="invoice", name="acme_invoice", org=org
		)
		MDocumentTemplate.objects.create(
			document_type="invoice", name="other_invoice", org=other_org
		)
		request = _make_request("get", org)

	with step("Act: Call templates."):
		response = VSDocumentTemplate.as_view({"get": "templates"})(request)

	with step("Assert: Only the owning org's template is returned."):
		assert response.status_code == 200
		assert [row["id"] for row in response.data] == [matching.id]


def test_templates_filters_by_document_type():
	"""Test templates filters by the document_type query param when given"""

	with step("Arrange: An org with templates of two different document types."):
		org = _make_org()
		invoice = MDocumentTemplate.objects.create(
			document_type="invoice", name="inv", org=org
		)
		MDocumentTemplate.objects.create(document_type="quote", name="qte", org=org)
		request = _make_request("get", org, query={"document_type": "invoice"})

	with step("Act: Call templates."):
		response = VSDocumentTemplate.as_view({"get": "templates"})(request)

	with step("Assert: Only the invoice template is returned."):
		assert response.status_code == 200
		assert [row["id"] for row in response.data] == [invoice.id]


def test_upload_creates_template_and_writes_to_storage(mocker):
	"""Test upload creates the MDocumentTemplate row and writes its bytes to storage under the right key"""

	with step("Arrange: An org and a mocked storage driver."):
		org = _make_org()
		mock_fstorage = mocker.patch(
			"drf_api.resources.document_template.main.FStorage"
		)
		upload_file = SimpleUploadedFile("acme_invoice.rpt", b"fake rpt bytes")
		request = _make_request(
			"post",
			org,
			data={
				"document_type": "invoice",
				"name": "Acme Invoice",
				"file": upload_file,
			},
		)

	with step("Act: Call upload."):
		response = VSDocumentTemplate.as_view({"post": "upload"})(request)

	with step(
		"Assert: The record is created and the driver's upload received the built key."
	):
		assert response.status_code == 201
		template = MDocumentTemplate.objects.get(id=response.data["id"])
		assert template.name == "Acme Invoice"
		assert template.document_type == "invoice"
		assert template.original_filename == "acme_invoice.rpt"
		assert template.storage_path == template.build_storage_key()
		call_args = mock_fstorage.get_instance.return_value.upload.call_args
		assert call_args[0][1] == template.storage_path


def test_upload_persists_business_partner_ref_and_language(mocker):
	"""Test upload stores the optional business_partner_ref and language override fields"""

	with step("Arrange: An org and an upload naming a BP and a language."):
		org = _make_org()
		mocker.patch("drf_api.resources.document_template.main.FStorage")
		request = _make_request(
			"post",
			org,
			data={
				"business_partner_ref": "C001",
				"document_type": "invoice",
				"file": SimpleUploadedFile("acme_invoice.rpt", b"bytes"),
				"language": "es",
				"name": "Acme Invoice ES",
			},
		)

	with step("Act: Call upload."):
		response = VSDocumentTemplate.as_view({"post": "upload"})(request)

	with step("Assert: Both override fields are persisted and serialized back."):
		assert response.status_code == 201
		assert response.data["business_partner_ref"] == "C001"
		assert response.data["language"] == "es"
		template = MDocumentTemplate.objects.get(id=response.data["id"])
		assert template.business_partner_ref == "C001"
		assert template.language == "es"


@pytest.mark.parametrize(
	"payload",
	[
		{
			"data": {"document_type": "invoice", "name": ""},
			"description": "missing name is rejected",
			"error": "MISSING_NAME",
			"with_file": False,
		},
		{
			"data": {"document_type": "invoice", "name": "x"},
			"description": "missing file is rejected",
			"error": "MISSING_FILE",
			"with_file": False,
		},
		{
			"data": {"document_type": "purchase_order", "name": "x"},
			"description": "unsupported document_type is rejected",
			"error": "UNSUPPORTED_DOCUMENT_TYPE",
			"with_file": True,
		},
	],
)
def test_upload_rejects_invalid_payloads(mocker, payload):
	"""Test upload rejects a payload missing required fields or naming an unsupported document type"""

	with step(f"Arrange: {payload['description']}."):
		org = _make_org()
		mocker.patch("drf_api.resources.document_template.main.FStorage")
		data = dict(payload["data"])
		if payload["with_file"]:
			data["file"] = SimpleUploadedFile("x.rpt", b"bytes")
		request = _make_request("post", org, data=data)

	with step("Act: Call upload."):
		response = VSDocumentTemplate.as_view({"post": "upload"})(request)

	with step("Assert: 400 is returned with the expected error, nothing persisted."):
		assert response.status_code == 400
		assert response.data["error"] == payload["error"]
		assert not MDocumentTemplate.objects.exists()


def test_upload_rejects_a_non_rpt_extension(mocker):
	"""Test upload rejects a file whose name doesn't end in .rpt"""

	with step("Arrange: A file named with the wrong extension."):
		org = _make_org()
		mocker.patch("drf_api.resources.document_template.main.FStorage")
		request = _make_request(
			"post",
			org,
			data={
				"document_type": "invoice",
				"file": SimpleUploadedFile("invoice.txt", b"bytes"),
				"name": "x",
			},
		)

	with step("Act: Call upload."):
		response = VSDocumentTemplate.as_view({"post": "upload"})(request)

	with step("Assert: 400 is returned with INVALID_FILE_TYPE."):
		assert response.status_code == 400
		assert response.data["error"] == "INVALID_FILE_TYPE"


def test_upload_rejects_file_over_the_configured_size_limit(mocker, settings):
	"""Test upload rejects a file larger than settings.TEMPLATE_MAX_FILE_SIZE_MB"""

	with step("Arrange: A max size of 0MB and a non-empty file."):
		settings.TEMPLATE_MAX_FILE_SIZE_MB = 0
		org = _make_org()
		mocker.patch("drf_api.resources.document_template.main.FStorage")
		request = _make_request(
			"post",
			org,
			data={
				"document_type": "invoice",
				"file": SimpleUploadedFile("invoice.rpt", b"bytes"),
				"name": "x",
			},
		)

	with step("Act: Call upload."):
		response = VSDocumentTemplate.as_view({"post": "upload"})(request)

	with step("Assert: 400 is returned with FILE_TOO_LARGE."):
		assert response.status_code == 400
		assert response.data["error"] == "FILE_TOO_LARGE"


def test_upload_returns_400_and_discards_the_row_when_storage_upload_fails(mocker):
	"""Test upload deletes the just-created MDocumentTemplate row when the driver's upload raises StorageError"""

	with step("Arrange: An org and a storage driver that fails to upload."):
		org = _make_org()
		mock_fstorage = mocker.patch(
			"drf_api.resources.document_template.main.FStorage"
		)
		mock_fstorage.get_instance.return_value.upload.side_effect = StorageError(
			"boom"
		)
		request = _make_request(
			"post",
			org,
			data={
				"document_type": "invoice",
				"file": SimpleUploadedFile("invoice.rpt", b"bytes"),
				"name": "x",
			},
		)

	with step("Act: Call upload."):
		response = VSDocumentTemplate.as_view({"post": "upload"})(request)

	with step("Assert: 400 is returned and the row is not left behind."):
		assert response.status_code == 400
		assert response.data["error"] == "boom"
		assert not MDocumentTemplate.objects.exists()


def test_update_template_renames():
	"""Test update_template applies a new name without touching document_type or the file"""

	with step("Arrange: An existing template."):
		org = _make_org()
		template = MDocumentTemplate.objects.create(
			document_type="invoice", name="old name", org=org
		)
		request = _make_request(
			"patch", org, data={"name": "new name", "template_id": template.id}
		)

	with step("Act: Call update_template."):
		response = VSDocumentTemplate.as_view({"patch": "update_template"})(request)

	with step("Assert: The row reflects the new name; document_type is unchanged."):
		assert response.status_code == 200
		template.refresh_from_db()
		assert template.name == "new name"
		assert template.document_type == "invoice"


def test_update_template_sets_the_override_fields():
	"""Test update_template sets business_partner_ref and language when present in the payload"""

	with step("Arrange: An existing template with no overrides set."):
		org = _make_org()
		template = MDocumentTemplate.objects.create(
			document_type="invoice", name="inv", org=org
		)
		request = _make_request(
			"patch",
			org,
			data={
				"business_partner_ref": "C001",
				"language": "es",
				"template_id": template.id,
			},
		)

	with step("Act: Call update_template."):
		response = VSDocumentTemplate.as_view({"patch": "update_template"})(request)

	with step("Assert: Both override fields are set."):
		assert response.status_code == 200
		template.refresh_from_db()
		assert template.business_partner_ref == "C001"
		assert template.language == "es"


def test_update_template_clears_the_override_fields_when_submitted_empty():
	"""Test update_template clears an existing override when the field is submitted as an empty string"""

	with step("Arrange: An existing template with an override already set."):
		org = _make_org()
		template = MDocumentTemplate.objects.create(
			business_partner_ref="C001",
			document_type="invoice",
			language="es",
			name="inv",
			org=org,
		)
		request = _make_request(
			"patch",
			org,
			data={"business_partner_ref": "", "template_id": template.id},
		)

	with step("Act: Call update_template."):
		response = VSDocumentTemplate.as_view({"patch": "update_template"})(request)

	with step(
		"Assert: business_partner_ref is cleared; language, left out of the payload, is untouched."
	):
		assert response.status_code == 200
		template.refresh_from_db()
		assert template.business_partner_ref == ""
		assert template.language == "es"


def test_update_template_rejects_unsupported_document_type():
	"""Test update_template rejects retyping to an unsupported document_type"""

	with step("Arrange: An existing template."):
		org = _make_org()
		template = MDocumentTemplate.objects.create(
			document_type="invoice", name="inv", org=org
		)
		request = _make_request(
			"patch",
			org,
			data={"document_type": "purchase_order", "template_id": template.id},
		)

	with step("Act: Call update_template."):
		response = VSDocumentTemplate.as_view({"patch": "update_template"})(request)

	with step("Assert: 400 is returned and the row is unchanged."):
		assert response.status_code == 400
		assert response.data["error"] == "UNSUPPORTED_DOCUMENT_TYPE"
		template.refresh_from_db()
		assert template.document_type == "invoice"


def test_update_template_retypes_to_another_supported_document_type(mocker):
	"""Test update_template moves a template to another supported document_type"""

	with step("Arrange: An invoice template and a second supported document type."):
		org = _make_org()
		mocker.patch.dict(
			"drf_api.resources.document_template.main.SUPPORTED_DOCUMENT_TYPES",
			{"credit_note": "credit_note_default.rpt"},
		)
		template = MDocumentTemplate.objects.create(
			document_type="invoice", name="inv", org=org
		)
		request = _make_request(
			"patch",
			org,
			data={"document_type": "credit_note", "template_id": template.id},
		)

	with step("Act: Call update_template."):
		response = VSDocumentTemplate.as_view({"patch": "update_template"})(request)

	with step("Assert: 200 is returned and the row now has the new document type."):
		assert response.status_code == 200
		template.refresh_from_db()
		assert template.document_type == "credit_note"


@pytest.mark.parametrize(
	"payload",
	[
		{
			"description": "a file that is not an .rpt",
			"expected_error": "INVALID_FILE_TYPE",
			"filename": "new.txt",
			"max_size_mb": None,
			"storage_error": None,
		},
		{
			"description": "a file over the configured size limit",
			"expected_error": "FILE_TOO_LARGE",
			"filename": "new.rpt",
			"max_size_mb": 0,
			"storage_error": None,
		},
		{
			"description": "a storage driver that fails to upload",
			"expected_error": "boom",
			"filename": "new.rpt",
			"max_size_mb": None,
			"storage_error": StorageError("boom"),
		},
	],
)
def test_update_template_rejects_a_replacement_file_that_cannot_be_stored(
	mocker, payload, settings
):
	"""Test update_template returns 400 and leaves the row unchanged when the replacement file is refused"""

	with step(f"Arrange: An existing template and {payload['description']}."):
		if payload["max_size_mb"] is not None:
			settings.TEMPLATE_MAX_FILE_SIZE_MB = payload["max_size_mb"]
		org = _make_org()
		template = MDocumentTemplate.objects.create(
			document_type="invoice",
			name="inv",
			org=org,
			original_filename="old.rpt",
			storage_path="acme/document_templates/invoice/1_inv.rpt",
		)
		mock_fstorage = mocker.patch(
			"drf_api.resources.document_template.main.FStorage"
		)
		mock_fstorage.get_instance.return_value.upload.side_effect = payload[
			"storage_error"
		]
		request = _make_request(
			"patch",
			org,
			data={
				"file": SimpleUploadedFile(payload["filename"], b"bytes"),
				"template_id": template.id,
			},
		)

	with step("Act: Call update_template."):
		response = VSDocumentTemplate.as_view({"patch": "update_template"})(request)

	with step("Assert: 400 is returned with the reason and the row is unchanged."):
		assert response.status_code == 400
		assert response.data["error"] == payload["expected_error"]
		template.refresh_from_db()
		assert template.original_filename == "old.rpt"


def test_update_template_replaces_the_file(mocker):
	"""Test update_template writes a replacement file to the same storage key"""

	with step("Arrange: An existing template and a mocked storage driver."):
		org = _make_org()
		template = MDocumentTemplate.objects.create(
			document_type="invoice",
			name="inv",
			org=org,
			storage_path="acme/document_templates/invoice/1_inv.rpt",
		)
		mock_fstorage = mocker.patch(
			"drf_api.resources.document_template.main.FStorage"
		)
		request = _make_request(
			"patch",
			org,
			data={
				"file": SimpleUploadedFile("new.rpt", b"bytes"),
				"template_id": template.id,
			},
		)

	with step("Act: Call update_template."):
		response = VSDocumentTemplate.as_view({"patch": "update_template"})(request)

	with step(
		"Assert: The driver's upload received the template's existing storage key."
	):
		assert response.status_code == 200
		mock_fstorage.get_instance.return_value.upload.assert_called_once()
		call_args = mock_fstorage.get_instance.return_value.upload.call_args
		assert call_args[0][1] == template.storage_path
		template.refresh_from_db()
		assert template.original_filename == "new.rpt"


def test_remove_deletes_the_storage_object_and_the_row(mocker):
	"""Test remove deletes both the storage object and the MDocumentTemplate row"""

	with step("Arrange: An existing template and a mocked storage driver."):
		org = _make_org()
		template = MDocumentTemplate.objects.create(
			document_type="invoice",
			name="inv",
			org=org,
			storage_path="acme/document_templates/invoice/1_inv.rpt",
		)
		mock_fstorage = mocker.patch(
			"drf_api.resources.document_template.main.FStorage"
		)
		request = _make_request("delete", org, query={"template_id": template.id})

	with step("Act: Call remove."):
		response = VSDocumentTemplate.as_view({"delete": "remove"})(request)

	with step("Assert: 204 is returned, storage deleted, row gone."):
		assert response.status_code == 204
		mock_fstorage.get_instance.return_value.delete.assert_called_once_with(
			template.storage_path
		)
		assert not MDocumentTemplate.objects.filter(id=template.id).exists()


def test_remove_returns_400_and_keeps_the_row_when_storage_delete_fails(mocker):
	"""Test remove keeps the MDocumentTemplate row when the driver's delete raises StorageError"""

	with step(
		"Arrange: An existing template and a storage driver that fails to delete."
	):
		org = _make_org()
		template = MDocumentTemplate.objects.create(
			document_type="invoice",
			name="inv",
			org=org,
			storage_path="acme/document_templates/invoice/1_inv.rpt",
		)
		mock_fstorage = mocker.patch(
			"drf_api.resources.document_template.main.FStorage"
		)
		mock_fstorage.get_instance.return_value.delete.side_effect = StorageError(
			"boom"
		)
		request = _make_request("delete", org, query={"template_id": template.id})

	with step("Act: Call remove."):
		response = VSDocumentTemplate.as_view({"delete": "remove"})(request)

	with step("Assert: 400 is returned with the reason and the row still exists."):
		assert response.status_code == 400
		assert response.data["error"] == "boom"
		assert MDocumentTemplate.objects.filter(id=template.id).exists()


def test_set_default_unsets_any_other_default_for_the_same_document_type():
	"""Test set_default unsets the previous default for the same (org, document_type) pair"""

	with step("Arrange: Two invoice templates, one already default."):
		org = _make_org()
		old_default = MDocumentTemplate.objects.create(
			document_type="invoice", is_default=True, name="old", org=org
		)
		new_default = MDocumentTemplate.objects.create(
			document_type="invoice", name="new", org=org
		)
		request = _make_request("post", org, data={"template_id": new_default.id})

	with step("Act: Call set_default."):
		response = VSDocumentTemplate.as_view({"post": "set_default"})(request)

	with step("Assert: The new template is default, the old one no longer is."):
		assert response.status_code == 200
		old_default.refresh_from_db()
		new_default.refresh_from_db()
		assert new_default.is_default is True
		assert old_default.is_default is False


def test_set_default_does_not_affect_other_document_types():
	"""Test set_default only touches templates of the same document_type"""

	with step("Arrange: An invoice default and a quote default."):
		org = _make_org()
		quote_default = MDocumentTemplate.objects.create(
			document_type="quote", is_default=True, name="qte", org=org
		)
		invoice_template = MDocumentTemplate.objects.create(
			document_type="invoice", name="inv", org=org
		)
		request = _make_request("post", org, data={"template_id": invoice_template.id})

	with step("Act: Call set_default."):
		VSDocumentTemplate.as_view({"post": "set_default"})(request)

	with step("Assert: The quote template's default flag is untouched."):
		quote_default.refresh_from_db()
		assert quote_default.is_default is True


def test_preview_returns_pdf_bytes(mocker):
	"""Test preview downloads and renders the template, returning the PDF bytes directly"""

	with step("Arrange: An existing template, a mocked storage driver and renderer."):
		org = _make_org()
		template = MDocumentTemplate.objects.create(
			document_type="invoice",
			name="inv",
			org=org,
			storage_path="acme/document_templates/invoice/1_inv.rpt",
		)
		mock_fstorage = mocker.patch(
			"drf_api.resources.document_template.main.FStorage"
		)
		mock_fstorage.get_instance.return_value.download.return_value = (
			"/tmp/downloaded.rpt"
		)
		mock_freport = mocker.patch("drf_api.resources.document_template.main.FReport")
		mock_freport.get_instance.return_value.render.return_value = (
			_make_rendered_pdf()
		)
		request = _make_request(
			"post",
			org,
			data={"data": [{"Product Name": "x"}], "template_id": template.id},
		)

	with step("Act: Call preview."):
		response = VSDocumentTemplate.as_view({"post": "preview"})(request)

	with step("Assert: The PDF bytes are returned directly, nothing persisted."):
		assert response.status_code == 200
		assert response["Content-Type"] == "application/pdf"
		assert response.content.startswith(b"%PDF")
		mock_fstorage.get_instance.return_value.download.assert_called_once_with(
			template.storage_path
		)


def test_preview_rejects_missing_data():
	"""Test preview rejects a request with no sample data"""

	with step("Arrange: An existing template, no data in the payload."):
		org = _make_org()
		template = MDocumentTemplate.objects.create(
			document_type="invoice", name="inv", org=org
		)
		request = _make_request("post", org, data={"template_id": template.id})

	with step("Act: Call preview."):
		response = VSDocumentTemplate.as_view({"post": "preview"})(request)

	with step("Assert: 400 is returned with MISSING_DATA."):
		assert response.status_code == 400
		assert response.data["error"] == "MISSING_DATA"


def test_preview_returns_400_when_render_fails(mocker):
	"""Test preview returns 400 when the renderer driver raises ReportError"""

	with step("Arrange: An existing template and a renderer that fails."):
		org = _make_org()
		template = MDocumentTemplate.objects.create(
			document_type="invoice",
			name="inv",
			org=org,
			storage_path="acme/document_templates/invoice/1_inv.rpt",
		)
		mocker.patch(
			"drf_api.resources.document_template.main.FStorage"
		).get_instance.return_value.download.return_value = "/tmp/downloaded.rpt"
		mocker.patch(
			"drf_api.resources.document_template.main.FReport"
		).get_instance.return_value.render.side_effect = ReportError("boom")
		request = _make_request(
			"post",
			org,
			data={"data": [{"Product Name": "x"}], "template_id": template.id},
		)

	with step("Act: Call preview."):
		response = VSDocumentTemplate.as_view({"post": "preview"})(request)

	with step("Assert: 400 is returned."):
		assert response.status_code == 400
		assert response.data["error"] == "boom"
