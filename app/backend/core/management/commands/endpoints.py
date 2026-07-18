"""Django command to list all the registered endpoints"""

# General imports
from importlib import import_module

# Libs imports
from django.core.management.base import BaseCommand
from django.urls import URLPattern, URLResolver, get_resolver


def list_patterns(patterns, prefix=""):
	"""To list all patterns"""
	for pattern in patterns:
		if isinstance(pattern, URLPattern):  # single route
			name = pattern.name
			route = prefix + getattr(pattern.pattern, "_route", str(pattern.pattern))
			if name:
				yield name, route
		elif isinstance(pattern, URLResolver):  # included urls
			nested_prefix = prefix + getattr(
				pattern.pattern, "_route", str(pattern.pattern)
			)
			yield from list_patterns(pattern.url_patterns, prefix=nested_prefix)


class Command(BaseCommand):
	"""Command class"""

	help = "List all available endpoints"

	def add_arguments(self, parser):
		"""Add arguments"""
		parser.add_argument(
			"-a",
			"--app",
			help="Specify an app to import (e.g., 'drf_api'). ",
			type=str,
		)

	def handle(self, *args, **options):
		"""Force import your dynamic DRF router module"""
		app = options.get("app")
		import_module("core.urls")  # ensure project URLconf loads
		import_module(f"{app}.urls")  # adjust if needed

		resolver = get_resolver()
		for name, route in list_patterns(resolver.url_patterns):
			print(f"{name:45s} -> {route}")
