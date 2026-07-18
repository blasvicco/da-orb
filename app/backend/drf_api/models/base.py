"""Base model"""

# General imports
from django.db import models
from django.forms.models import model_to_dict

class MBase(models.Model):
	"""Base model"""

	class Meta:
		abstract = True

	def to_dict(self):
		"""Convert model to dictionary."""
		return model_to_dict(self)
