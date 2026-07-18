"""Core views"""

# Lib imports
from django.http import HttpResponse


def healthcheck(request):
	"""Healtcheck view"""
	return HttpResponse("pong", content_type="text/plain")
