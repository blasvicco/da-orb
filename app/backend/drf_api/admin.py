"""Django admin register"""

# General imports
import json

# Lib imports
from django import forms
from django.contrib import admin

# App imports
from drf_api.models import MOrganization

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
			"b1s also requires: base_url. "
			"Optional for b1s: b1s_default_database."
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
	list_display = ["id", "name", "slug", "get_auth_driver", "created_on"]
	list_filter = ["created_on"]
	search_fields = ["id", "name", "slug"]

	@admin.display(description="Auth Driver")
	def get_auth_driver(self, obj):
		"""Display the configured auth driver in the list view."""
		return obj.integration.get("auth_driver", "open_id")
