"""This module contains tests for the configuration module"""

# General imports
from contextlib import nullcontext
from unittest.mock import MagicMock, patch

# Lib imports
import pytest
from allure import step

# App imports
from core.modules.configuration.main import Configuration, ConfigurationError


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# sys_env driver — load()
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
	"payload",
	[
		# No prefix, no lowercase, default separator → all env vars are returned flat
		{
			"env": {"SOME_KEY": "value"},
			"cfg": {},
			"expected": {"SOME_KEY": "value"},
			"description": "no prefix returns all vars flat",
		},
		# Prefix filtering: only matching vars are kept, prefix+sep is stripped
		{
			"env": {"APP.HOST": "localhost", "OTHER": "ignored"},
			"cfg": {"CFG_PREFIX": "APP", "CFG_SEPARATOR": "."},
			"expected": {"HOST": "localhost"},
			"description": "prefix filters and strips matching vars",
		},
		# Non-matching prefix → empty result
		{
			"env": {"OTHER_KEY": "value"},
			"cfg": {"CFG_PREFIX": "APP", "CFG_SEPARATOR": "_"},
			"expected": {},
			"description": "non-matching prefix returns empty dict",
		},
		# Lowercase flag lowercases the resulting keys
		{
			"env": {"SOME_KEY": "value"},
			"cfg": {"CFG_LOWERCASE": "true"},
			"expected": {"some_key": "value"},
			"description": "lowercase flag lowercases keys",
		},
		# Custom separator builds nested dicts
		{
			"env": {"DB.HOST.PORT": "5432"},
			"cfg": {"CFG_SEPARATOR": "."},
			"expected": {"DB": {"HOST": {"PORT": "5432"}}},
			"description": "custom separator produces nested dict",
		},
		# Prefix + separator + nesting all together
		{
			"env": {"APP.DB.HOST": "localhost", "APP.DB.PORT": "5432", "OTHER": "x"},
			"cfg": {"CFG_PREFIX": "APP", "CFG_SEPARATOR": "."},
			"expected": {"DB": {"HOST": "localhost", "PORT": "5432"}},
			"description": "prefix with nested separator builds nested dict",
		},
		# Lowercase + custom separator
		{
			"env": {"APP.DB.HOST": "localhost"},
			"cfg": {"CFG_PREFIX": "APP", "CFG_SEPARATOR": ".", "CFG_LOWERCASE": "true"},
			"expected": {"db": {"host": "localhost"}},
			"description": "lowercase combined with separator lowercases nested keys",
		},
		# Empty environment → empty result
		{
			"env": {},
			"cfg": {},
			"expected": {},
			"description": "empty environment returns empty dict",
		},
	],
)
def test_sys_env_load(payload):
	"""Test sys_env driver load() under various environment configurations"""

	with step(f"Arrange: {payload['description']}"):
		# load() uses os.environ in two distinct ways:
		#   - .get(key, default)  → reads CFG_* configuration vars
		#   - .items()            → iterates over data vars
		# Merging both into a single dict would cause CFG_* vars to appear in
		# the iteration results, so we mock them separately.
		mock_env = MagicMock()
		mock_env.get.side_effect = lambda key, default=None: payload["cfg"].get(
			key, default
		)
		mock_env.items.return_value = payload["env"].items()

	with step("Act: Import and call sys_env.load()"):
		# pylint: disable=import-outside-toplevel
		from core.modules.configuration.driver import sys_env

		with patch("core.modules.configuration.driver.sys_env.os.environ", mock_env):
			result = sys_env.load()

	with step("Assert: Result matches expected dict"):
		assert result == payload["expected"]


# ---------------------------------------------------------------------------
# sys_env driver — _set_nested()
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
	"payload",
	[
		{
			"keys": ["a"],
			"value": "1",
			"expected": {"a": "1"},
			"description": "single key sets top-level value",
		},
		{
			"keys": ["a", "b"],
			"value": "2",
			"expected": {"a": {"b": "2"}},
			"description": "two keys produce one level of nesting",
		},
		{
			"keys": ["a", "b", "c"],
			"value": "3",
			"expected": {"a": {"b": {"c": "3"}}},
			"description": "three keys produce two levels of nesting",
		},
		{
			"keys": ["a", "b"],
			"value": "overwritten",
			"seed": {"a": {"b": "original"}},
			"expected": {"a": {"b": "overwritten"}},
			"description": "existing nested key is overwritten",
		},
	],
)
def test_set_nested(payload):
	"""Test _set_nested helper builds / overwrites nested dicts correctly"""

	with step(f"Arrange: {payload['description']}"):
		# pylint: disable=import-outside-toplevel
		from core.modules.configuration.driver.sys_env import (
			_set_nested,
		)

		data = payload.get("seed", {})

	with step("Act: Call _set_nested"):
		_set_nested(data, payload["keys"], payload["value"])

	with step("Assert: Data matches expected nested structure"):
		assert data == payload["expected"]


# ---------------------------------------------------------------------------
# Configuration class (main.py)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
	"payload",
	[
		# Valid driver: sys_env, returns the mocked data from load()
		{
			"driver": "sys_env",
			"mock_data": {"key": "value"},
			"valid": True,
			"description": "valid driver initialises and get() returns data",
		},
		# Invalid driver raises ConfigurationError
		{
			"driver": "nonexistent_driver",
			"mock_data": None,
			"valid": False,
			"description": "unknown driver raises ConfigurationError",
		},
	],
)
def test_configuration(monkeypatch, payload):
	"""Test Configuration initialisation and get() with valid and invalid drivers"""

	with step(f"Arrange: {payload['description']}"):
		monkeypatch.setenv("CFG_DRIVER", payload["driver"])
		context = (
			nullcontext() if payload["valid"] else pytest.raises(ConfigurationError)
		)

		if payload["valid"]:
			# Patch the driver's load() so the test is hermetic
			monkeypatch.setattr(
				"core.modules.configuration.driver.sys_env.load",
				lambda: payload["mock_data"],
			)

	with step("Act: Instantiate Configuration"):
		with context as excinfo:
			cfg = Configuration()

	with step("Assert: Outcome is correct"):
		if payload["valid"]:
			assert excinfo is None
			assert cfg.get() == payload["mock_data"]
		else:
			assert isinstance(excinfo, pytest.ExceptionInfo)
			assert payload["driver"] in str(excinfo.value)
