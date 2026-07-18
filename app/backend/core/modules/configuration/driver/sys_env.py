"""Driver for environment loads"""

# General imports
import os


def load():
	"""Read environment variables and return a dict."""
	prefix = os.environ.get("CFG_PREFIX", "")
	lowercase = os.environ.get("CFG_LOWERCASE", False)
	separator = os.environ.get("CFG_SEPARATOR", ".")

	result = {}
	for raw_key, value in os.environ.items():
		key = raw_key

		# prefix filtering
		if prefix:
			full_prefix = f"{prefix}{separator}"
			if not raw_key.startswith(full_prefix):
				continue
			key = raw_key[len(full_prefix) :]

		if lowercase:
			key = key.lower()

		# build nested dict from KEY_PART1_PART2
		parts = key.split(separator.lower() if lowercase else separator)
		_set_nested(result, parts, value)

	return result


def _set_nested(data, keys, value):
	"""Recursively set a value inside a nested dict using a list of keys."""
	for key in keys[:-1]:
		data = data.setdefault(key, {})
	data[keys[-1]] = value
