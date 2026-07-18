"""Driver for aws secret manager loads"""

# General imports
import json
import os

# Lib imports
try:
	import boto3
	from botocore.exceptions import ClientError
except ImportError:
	boto3 = None
	ClientError = None


def load():
	"""Fetch the secret from AWS Secrets Manager and return it as a dict."""
	secret_name = os.environ.get("CFG_SECRET_NAME")
	region = os.environ.get("CFG_REGION")

	session = boto3.session.Session()
	client = session.client(service_name="secretsmanager", region_name=region)

	kwargs = {"SecretId": secret_name}
	try:
		response = client.get_secret_value(**kwargs)
	except ClientError as error:
		error_code = error.response["Error"]["Code"]
		raise RuntimeError(
			f"Could not retrieve secret '{secret_name}': [{error_code}] {error}"
		) from error

	secret_string = response.get("SecretString")
	if secret_string is None:
		raise ValueError(
			f"Secret '{secret_name}' contains binary data, which is not supported by this driver."
		)

	try:
		return json.loads(secret_string)
	except json.JSONDecodeError as error:
		raise ValueError(f"Secret '{secret_name}' is not valid JSON.") from error
