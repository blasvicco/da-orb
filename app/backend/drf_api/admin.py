"""Django admin register"""

# General imports
import json

# Lib imports
from django import forms
from django.contrib import admin, messages
from django.http import HttpResponseRedirect

# App imports
from drf_api.models import MOrganization, MSeat, MSessionProxy
from drf_api.resources.auth.helpers import is_org_admin, set_org_admin

# Required keys per auth driver
_DRIVER_REQUIRED_KEYS = {
	"open_id": {"base_url", "client_id", "client_secret", "auth_driver"},
	"b1s": {"base_url", "auth_driver"},
}


class MOrganizationForm(forms.ModelForm):
	"""Form for MOrganization in Django Admin to handle encrypted JSON field as plain JSON."""

	integration = forms.CharField(
		help_text=(
			"Plain JSON dictionary. Will be automatically encrypted when saved. "
			"Must include 'auth_driver' (open_id or b1s). "
			"open_id also requires: base_url, client_id, client_secret. "
			"b1s also requires: base_url."
		),
		required=False,
		widget=forms.Textarea(attrs={"cols": 80, "rows": 10}),
	)

	class Meta:
		model = MOrganization
		fields = "__all__"

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		if self.instance and hasattr(self.instance, "integration"):
			value = self.instance.integration
			if isinstance(value, dict):
				self.initial["integration"] = json.dumps(value, indent=4)
			elif isinstance(value, str):
				try:
					parsed = json.loads(value)
					self.initial["integration"] = json.dumps(parsed, indent=4)
				except json.JSONDecodeError:
					self.initial["integration"] = value

	def clean_integration(self):
		"""Validate that the submitted integration field is a valid JSON dictionary."""
		data = self.cleaned_data.get("integration")
		if not data:
			return {}
		try:
			parsed = json.loads(data)
			if not isinstance(parsed, dict):
				raise forms.ValidationError(
					"The integration field must be a JSON object/dictionary."
				)

			driver = parsed.get("auth_driver", "")
			if not driver:
				raise forms.ValidationError(
					"Missing required key: 'auth_driver'. Valid values: open_id, b1s."
				)

			required_keys = _DRIVER_REQUIRED_KEYS.get(driver)
			if required_keys is None:
				raise forms.ValidationError(
					f"Unknown auth_driver '{driver}'. Valid values: {', '.join(_DRIVER_REQUIRED_KEYS)}."
				)

			missing = required_keys - parsed.keys()
			if missing:
				raise forms.ValidationError(
					f"Missing required integration keys for driver '{driver}': {', '.join(sorted(missing))}"
				)

			return parsed
		except json.JSONDecodeError as error:
			raise forms.ValidationError("Invalid JSON format.") from error


@admin.register(MOrganization)
class MOrganizationAdmin(admin.ModelAdmin):
	"""Custom Admin for MOrganization"""

	form = MOrganizationForm
	list_display = ["id", "name", "slug", "get_auth_driver", "seat_limit", "created_on"]
	list_filter = ["created_on"]
	search_fields = ["id", "name", "slug"]

	@admin.display(description="Auth Driver")
	def get_auth_driver(self, obj):
		"""Display the configured auth driver in the list view."""
		return obj.integration.get("auth_driver", "open_id")


@admin.register(MSessionProxy)
class MSessionProxyAdmin(admin.ModelAdmin):
	"""Read-only admin for MSessionProxy."""

	# Ops visibility into active proxy sessions only; the encrypted credentials
	# are excluded from every view, including the detail page.

	exclude = ["credentials"]
	list_display = [
		"id",
		"org",
		"auth_driver",
		"username",
		"connection_key",
		"issued_on",
		"expires_at",
	]
	list_filter = ["org", "auth_driver"]
	search_fields = ["username", "connection_key"]

	def has_add_permission(self, request):
		"""Disallow creating rows via admin — sessions are only created by the login flow."""
		return False

	def has_change_permission(self, request, obj=None):
		"""Disallow editing rows via admin — sessions are immutable once issued."""
		return False


@admin.register(MSeat)
class MSeatAdmin(admin.ModelAdmin):
	"""Admin for MSeat."""

	# Lets ops manually revoke/reinstate a seat and toggle a seat's org-admin
	# role until the in-app seat-management view covers every case.

	change_form_template = "admin/drf_api/mseat/change_form.html"
	list_display = [
		"id",
		"org",
		"username",
		"status",
		"get_role",
		"granted_on",
		"revoked_on",
	]
	list_filter = ["org", "status"]
	search_fields = ["username"]

	@admin.display(description="Role")
	def get_role(self, obj):
		"""Display the seat's current org-admin role in the list view."""
		return "Admin" if is_org_admin(obj.org, obj.username) else "Standard"

	def change_view(self, request, object_id, form_url="", extra_context=None):
		"""Inject the seat's current role so the change form can label the toggle button."""
		seat = self.get_object(request, object_id)
		extra_context = extra_context or {}
		if seat is not None:
			extra_context["seat_is_admin"] = is_org_admin(seat.org, seat.username)
		return super().change_view(request, object_id, form_url, extra_context)

	def response_change(self, request, obj):
		"""Handle the custom Promote/Demote button submitted from the change form."""
		if "_toggle_role" in request.POST:
			new_is_admin = not is_org_admin(obj.org, obj.username)
			set_org_admin(obj.org, obj.username, new_is_admin)
			role_label = "an admin" if new_is_admin else "a standard user"
			self.message_user(
				request, f"'{obj.username}' is now {role_label}.", messages.SUCCESS
			)
			return HttpResponseRedirect(request.path)
		return super().response_change(request, obj)
