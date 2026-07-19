"""This module contains tests for the B1S authentication driver"""

# General imports
from datetime import timedelta
from unittest.mock import MagicMock, patch

# Lib imports
import pytest
from allure import step
from django.utils import timezone

# App imports
from drf_api.models import MOrganization, MSessionProxy
from drf_api.resources.auth.driver.abstract import AuthDriverError
from drf_api.resources.auth.driver.b1s import Instance

pytestmark = pytest.mark.django_db


def _make_driver(base_url="https://fake.example.com/b1s/v1"):
	"""Build a B1S driver instance with a fake integration config"""
	return Instance({"auth_driver": "b1s", "base_url": base_url})


def _make_org(slug="acme"):
	"""Create a persisted MOrganization instance"""
	return MOrganization.objects.create(name=slug, slug=slug)


@pytest.mark.parametrize(
	"payload",
	[
		{
			"credentials": {"password": "secret", "username": "bob"},
			"description": "missing database raises MISSING_DATABASE",
		},
		{
			"credentials": {"database": "", "password": "secret", "username": "bob"},
			"description": "blank database raises MISSING_DATABASE",
		},
	],
)
def test_authenticate_missing_database(payload):
	"""Test authenticate raises AuthDriverError when database is absent for password auth"""

	with step(f"Arrange: {payload['description']}"):
		driver = _make_driver()

	with step("Act/Assert: authenticate raises MISSING_DATABASE."):
		with pytest.raises(AuthDriverError, match="MISSING_DATABASE"):
			driver.authenticate(**payload["credentials"])


def test_authenticate_token_trust_ignores_missing_database():
	"""Test authenticate does not require database when trusting a pre-issued token"""

	with step("Arrange: credentials carry a token and no password/database."):
		driver = _make_driver()

	with step("Act: Call authenticate with only a token."):
		session_data = driver.authenticate(token="existing-session-id", username="bob")

	with step("Assert: Session is built from the trusted token, database left blank."):
		assert session_data["access_token"] == "existing-session-id"
		assert session_data["database"] == ""


def test_authenticate_success_with_database():
	"""Test authenticate posts to SAP Login and returns a session dict when database is present"""

	with step("Arrange: Mock a successful SAP Login response."):
		driver = _make_driver()
		mock_response = MagicMock(status_code=200)
		mock_response.json.return_value = {"SessionId": "new-session-id"}

	with step("Act: Call authenticate with full credentials."):
		with patch(
			"drf_api.resources.auth.driver.b1s.requests.post",
			return_value=mock_response,
		) as mock_post:
			session_data = driver.authenticate(
				database="TESTDB", password="secret", username="bob"
			)

	with step("Assert: SAP was called with CompanyDB and the session was returned."):
		assert mock_post.call_args.kwargs["json"]["CompanyDB"] == "TESTDB"
		assert session_data["access_token"] == "new-session-id"
		assert session_data["database"] == "TESTDB"


@pytest.mark.parametrize(
	"payload",
	[
		{
			"data": {"password": "secret", "username": "bob"},
			"description": "missing database",
		},
		{
			"data": {"database": "", "password": "secret", "username": "bob"},
			"description": "blank database",
		},
		{
			"data": {"database": "TESTDB", "username": "bob"},
			"description": "missing password",
		},
		{
			"data": {"database": "TESTDB", "password": "secret"},
			"description": "missing username",
		},
	],
)
def test_login_missing_credentials(payload):
	"""Test login raises MISSING_CREDENTIALS when any required field is absent"""

	with step(f"Arrange: request data with {payload['description']}."):
		driver = _make_driver()
		request = MagicMock(data=payload["data"])

	with step("Act/Assert: login raises MISSING_CREDENTIALS."):
		with pytest.raises(AuthDriverError, match="MISSING_CREDENTIALS"):
			driver.login(request, org="acme")


def test_login_success():
	"""Test login authenticates against SAP and returns the session dict when all fields are present"""

	with step("Arrange: Mock a successful SAP Login response."):
		driver = _make_driver()
		request = MagicMock(
			data={"database": " TESTDB ", "password": "secret", "username": " bob "}
		)
		mock_response = MagicMock(status_code=200)
		mock_response.json.return_value = {"SessionId": "new-session-id"}

	with step("Act: Call login."):
		with patch(
			"drf_api.resources.auth.driver.b1s.requests.post",
			return_value=mock_response,
		) as mock_post:
			session_data = driver.login(request, org="acme")

	with step("Assert: Credentials were trimmed and the session dict was returned."):
		assert mock_post.call_args.kwargs["json"]["CompanyDB"] == "TESTDB"
		assert mock_post.call_args.kwargs["json"]["UserName"] == "bob"
		assert session_data["database"] == "TESTDB"
		assert session_data["user"]["password"] == "secret"


def test_resolve_session_missing_token():
	"""Test resolve_session returns None for an empty token"""

	with step("Act: Call resolve_session with an empty token."):
		result = _make_driver().resolve_session("")

	with step("Assert: None is returned."):
		assert result is None


def test_resolve_session_unknown_token():
	"""Test resolve_session returns None when no row matches the token"""

	with step("Act: Call resolve_session with a token that was never issued."):
		result = _make_driver().resolve_session("does-not-exist")

	with step("Assert: None is returned."):
		assert result is None


def test_resolve_session_expired_token():
	"""Test resolve_session returns None once the proxy session has expired"""

	with step("Arrange: A proxy session that already expired."):
		org = _make_org()
		session = MSessionProxy.objects.create(
			auth_driver="b1s",
			connection_key="TESTDB",
			credentials={"password": "secret", "username": "bob"},
			expires_at=timezone.now() - timedelta(seconds=1),
			org=org,
			token="expired-token",
			username="bob",
		)

	with step("Act: Call resolve_session."):
		result = _make_driver().resolve_session(session.token)

	with step("Assert: None is returned."):
		assert result is None


def test_resolve_session_valid_token_bumps_last_active_on():
	"""Test resolve_session returns the row and refreshes last_active_on for a valid token"""

	with step("Arrange: A live proxy session with a stale last_active_on."):
		org = _make_org()
		session = MSessionProxy.objects.create(
			auth_driver="b1s",
			connection_key="TESTDB",
			credentials={"password": "secret", "username": "bob"},
			expires_at=timezone.now() + timedelta(hours=1),
			org=org,
			token="live-token",
			username="bob",
		)
		MSessionProxy.objects.filter(pk=session.pk).update(
			last_active_on=timezone.now() - timedelta(days=1)
		)
		stale_last_active_on = MSessionProxy.objects.get(pk=session.pk).last_active_on

	with step("Act: Call resolve_session."):
		result = _make_driver().resolve_session(session.token)

	with step("Assert: The row is returned and last_active_on was bumped."):
		assert result.id == session.id
		assert result.username == "bob"
		refreshed = MSessionProxy.objects.get(pk=session.pk)
		assert refreshed.last_active_on > stale_last_active_on


def test_resolve_session_payload_valid_token_swaps_credentials():
	"""Test resolve_session_payload swaps in the real credentials for a valid proxy token"""

	with step(
		"Arrange: A live proxy session and a session_dict carrying its opaque token."
	):
		org = _make_org()
		session = MSessionProxy.objects.create(
			auth_driver="b1s",
			connection_key="TESTDB",
			credentials={"password": "real-secret", "username": "bob"},
			expires_at=timezone.now() + timedelta(hours=1),
			org=org,
			token="live-token",
			username="bob",
		)
		session_dict = {
			"access_token": session.token,
			"database": "",
			"user": {"password": "", "username": "bob"},
		}

	with step("Act: Call resolve_session_payload."):
		result = _make_driver().resolve_session_payload(session_dict)

	with step("Assert: The real credentials and connection key are swapped in."):
		assert result["database"] == "TESTDB"
		assert result["user"] == {"password": "real-secret", "username": "bob"}


def test_resolve_session_payload_invalid_token_passes_through():
	"""Test resolve_session_payload returns the session_dict unchanged for an unresolvable token"""

	with step(
		"Arrange: A session_dict carrying a token with no matching proxy session."
	):
		session_dict = {
			"access_token": "does-not-exist",
			"database": "",
			"user": {"password": "", "username": "bob"},
		}

	with step("Act: Call resolve_session_payload."):
		result = _make_driver().resolve_session_payload(session_dict)

	with step("Assert: The session_dict is returned unchanged."):
		assert result == session_dict


def test_resolve_identity_valid_token_ignores_spoofed_headers():
	"""Test Instance.resolve_identity trusts the verified opaque token, not client headers"""

	with step(
		"Arrange: A live proxy session and a request with spoofed identity headers."
	):
		org = _make_org()
		session = MSessionProxy.objects.create(
			auth_driver="b1s",
			connection_key="TESTDB",
			credentials={"password": "secret", "username": "bob"},
			expires_at=timezone.now() + timedelta(hours=1),
			org=org,
			token="live-token",
			username="bob",
		)
		driver = _make_driver()
		request = MagicMock(
			headers={
				"Authorization": f"Bearer {session.token}",
				"X-SAP-Connection-Key": "SPOOFEDDB",
				"X-SAP-Username": "spoofed-user",
			}
		)

	with step("Act: Call resolve_identity."):
		username, connection_key = driver.resolve_identity(request)

	with step(
		"Assert: Identity comes from the verified token, ignoring the spoofed headers."
	):
		assert username == "bob"
		assert connection_key == "TESTDB"


def test_resolve_identity_invalid_token_returns_blank():
	"""Test Instance.resolve_identity returns ('', '') for a missing or unresolvable token"""

	with step("Arrange: A request with no matching proxy session."):
		driver = _make_driver()
		request = MagicMock(headers={"Authorization": "Bearer does-not-exist"})

	with step("Act: Call resolve_identity."):
		username, connection_key = driver.resolve_identity(request)

	with step("Assert: Both values are blank."):
		assert username == ""
		assert connection_key == ""


@pytest.mark.parametrize(
	"payload",
	[
		{
			"description": "empty bearer token",
			"headers": {"Authorization": "Bearer "},
		},
		{
			"description": "missing Authorization header",
			"headers": {},
		},
		{
			"description": "non-bearer scheme",
			"headers": {"Authorization": "Basic abc123"},
		},
	],
)
def test_resolve_identity_malformed_authorization_header(payload):
	"""Test Instance.resolve_identity returns ('', '') when the Authorization header carries no bearer token"""

	with step(f"Arrange: A request with {payload['description']}."):
		driver = _make_driver()
		request = MagicMock(headers=payload["headers"])

	with step("Act: Call resolve_identity."):
		username, connection_key = driver.resolve_identity(request)

	with step("Assert: Both values are blank."):
		assert username == ""
		assert connection_key == ""


def test_resolve_ws_session_valid_token_returns_session_dict():
	"""Test resolve_ws_session builds a session dict from the verified proxy token, ignoring client-supplied fields"""

	with step("Arrange: A live proxy session."):
		org = _make_org()
		session = MSessionProxy.objects.create(
			auth_driver="b1s",
			connection_key="TESTDB",
			credentials={"password": "secret", "username": "bob"},
			expires_at=timezone.now() + timedelta(hours=1),
			org=org,
			token="live-token",
			username="bob",
		)

	with step(
		"Act: Call resolve_ws_session with mismatched client-supplied fields."
	):
		result = _make_driver().resolve_ws_session(
			{"database": "SPOOFEDDB", "expires_at": 999, "password": "spoofed"},
			org="someone-elses-org",
			token=session.token,
			username="spoofed-user",
		)

	with step(
		"Assert: The session dict reflects the verified proxy session, not the spoofed inputs."
	):
		assert result["access_token"] == session.token
		assert result["database"] == "TESTDB"
		assert result["expires_at"] == 999
		assert result["user"] == {"password": "", "username": "bob"}


def test_resolve_ws_session_invalid_token_returns_none():
	"""Test resolve_ws_session returns None when the token doesn't resolve to a live proxy session"""

	with step("Act: Call resolve_ws_session with a token that was never issued."):
		result = _make_driver().resolve_ws_session(
			{"database": "", "expires_at": 0, "password": ""},
			org="acme",
			token="does-not-exist",
			username="bob",
		)

	with step("Assert: None is returned."):
		assert result is None
