"""This module contains tests for the endpoints management command"""

# Lib imports
import pytest
from allure import step
from django.core.management import call_command
from django.urls import include, path

# App imports
from core.management.commands.endpoints import list_patterns

pytestmark = pytest.mark.django_db


def test_list_patterns_yields_named_routes_and_recurses_into_includes():
	"""Test list_patterns yields (name, route) for named patterns, skips unnamed, and recurses into includes"""

	with step(
		"Arrange: A pattern list with a named leaf, an unnamed leaf, and a nested include."
	):
		patterns = [
			path("leaf/", lambda request: None, name="leaf"),
			path("unnamed/", lambda request: None),
			path(
				"nested/",
				include([path("inner/", lambda request: None, name="inner")]),
			),
		]

	with step("Act: Call list_patterns."):
		result = list(list_patterns(patterns))

	with step("Assert: Only named routes are yielded, with correctly built prefixes."):
		assert result == [("leaf", "leaf/"), ("inner", "nested/inner/")]


def test_handle_prints_registered_routes(capsys):
	"""Test the endpoints command imports the given app's urls and prints its routes"""

	with step("Arrange: Nothing extra needed."):
		pass

	with step("Act: Call the endpoints management command for drf_api."):
		call_command("endpoints", app="drf_api")

	with step("Assert: A known drf_api route is printed."):
		output = capsys.readouterr().out
		assert "chat" in output
