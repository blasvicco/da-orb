"""This module contains tests for the usage dashboard viewset"""

# Lib imports
import pytest
from allure import step
from django.utils import timezone
from rest_framework.test import APIRequestFactory

# App imports
from drf_api.models import MChatMessage, MChatSession, MOrganization, MSeat, MUsageEvent
from drf_api.resources.auth.helpers import set_org_admin
from drf_api.resources.usage.main import VSUsage

pytestmark = pytest.mark.django_db

_factory = APIRequestFactory()


def _make_org(slug="acme"):
	"""Create a persisted MOrganization instance with an admin user ('admin') already granted"""
	org = MOrganization.objects.create(name=slug, slug=slug)
	set_org_admin(org, "admin", True)
	return org


def _make_request(org, username="admin"):
	"""Build a DRF-compatible GET request acting as the given (by default, admin) username"""
	request = _factory.get("/", HTTP_X_SAP_USERNAME=username)
	request.get_org_slug = lambda: org.slug
	return request


def test_summary_requires_admin():
	"""Test summary denies a non-admin requester"""

	with step("Arrange: A non-admin username."):
		org = _make_org()
		request = _make_request(org, username="not-an-admin")

	with step("Act: Call summary."):
		response = VSUsage.as_view({"get": "summary"})(request)

	with step("Assert: 403 is returned."):
		assert response.status_code == 403


def test_summary_aggregates_token_usage_by_process():
	"""Test summary sums total_tokens overall and grouped by process_name"""

	with step("Arrange: Three token_usage events across two processes and two users."):
		org = _make_org()
		MUsageEvent.objects.create(
			event_type="token_usage",
			occurred_on=timezone.now(),
			org=org,
			process_name="create_purchase_order",
			total_tokens=100,
			username="bob",
		)
		MUsageEvent.objects.create(
			event_type="token_usage",
			occurred_on=timezone.now(),
			org=org,
			process_name="create_purchase_order",
			total_tokens=50,
			username="alice",
		)
		MUsageEvent.objects.create(
			event_type="token_usage",
			occurred_on=timezone.now(),
			org=org,
			process_name="goods_receipt",
			total_tokens=25,
			username="bob",
		)
		request = _make_request(org)

	with step("Act: Call summary."):
		response = VSUsage.as_view({"get": "summary"})(request)

	with step("Assert: Token totals are correct, overall and by process."):
		assert response.status_code == 200
		assert response.data["tokens"]["total"] == 175
		by_process = {
			row["process_name"]: row["total_tokens"]
			for row in response.data["tokens"]["by_process"]
		}
		assert by_process == {"create_purchase_order": 150, "goods_receipt": 25}


def test_summary_plan_reports_seat_and_token_usage_against_plan_limits():
	"""Test summary reports active seat count and this-month token usage against org.plan limits"""

	with step(
		"Arrange: An org with a plan, an active and a revoked seat, and tokens "
		"spread across this month and last month."
	):
		org = _make_org()
		org.plan = {"seats": 10, "tokens": 1000}
		org.save()
		MSeat.objects.create(org=org, status="active", username="bob")
		MSeat.objects.create(org=org, status="revoked", username="carol")
		MUsageEvent.objects.create(
			event_type="token_usage",
			occurred_on=timezone.now(),
			org=org,
			total_tokens=40,
			username="bob",
		)
		MUsageEvent.objects.create(
			event_type="token_usage",
			occurred_on=timezone.now() - timezone.timedelta(days=32),
			org=org,
			total_tokens=999,
			username="bob",
		)
		request = _make_request(org)

	with step("Act: Call summary."):
		response = VSUsage.as_view({"get": "summary"})(request)

	with step(
		"Assert: plan.seats counts only active seats; plan.tokens counts only this month."
	):
		assert response.status_code == 200
		assert response.data["plan"]["seats"] == {"total": 10, "used": 1}
		assert response.data["plan"]["tokens"] == {"total": 1000, "used": 40}


def test_summary_aggregates_process_execution_by_process():
	"""Test summary counts process_execution events overall and grouped by process_name"""

	with step("Arrange: Three process_execution events across two process names."):
		org = _make_org()
		MUsageEvent.objects.create(
			event_type="process_execution",
			occurred_on=timezone.now(),
			org=org,
			process_name="create_purchase_order",
			username="bob",
		)
		MUsageEvent.objects.create(
			event_type="process_execution",
			occurred_on=timezone.now(),
			org=org,
			process_name="create_purchase_order",
			username="alice",
		)
		MUsageEvent.objects.create(
			event_type="process_execution",
			occurred_on=timezone.now(),
			org=org,
			process_name="goods_receipt",
			username="bob",
		)
		request = _make_request(org)

	with step("Act: Call summary."):
		response = VSUsage.as_view({"get": "summary"})(request)

	with step("Assert: Process totals are correct, overall and by process."):
		assert response.status_code == 200
		assert response.data["processes"]["total"] == 3
		by_process = {
			row["process_name"]: row["count"]
			for row in response.data["processes"]["by_process"]
		}
		assert by_process == {"create_purchase_order": 2, "goods_receipt": 1}


def test_summary_top_users_rankings():
	"""Test summary ranks users by message count, token total, and process count independently"""

	with step("Arrange: Messages and usage events split across two users."):
		org = _make_org()
		session_bob = MChatSession.objects.create(org=org, username="bob")
		session_alice = MChatSession.objects.create(org=org, username="alice")
		MChatMessage.objects.create(
			session=session_bob, text="a", timestamp=timezone.now(), type="user"
		)
		MChatMessage.objects.create(
			session=session_bob, text="b", timestamp=timezone.now(), type="agent"
		)
		MChatMessage.objects.create(
			session=session_alice, text="c", timestamp=timezone.now(), type="user"
		)
		MUsageEvent.objects.create(
			event_type="token_usage",
			occurred_on=timezone.now(),
			org=org,
			total_tokens=100,
			username="bob",
		)
		MUsageEvent.objects.create(
			event_type="process_execution",
			occurred_on=timezone.now(),
			org=org,
			process_name="create_purchase_order",
			username="alice",
		)
		request = _make_request(org)

	with step("Act: Call summary."):
		response = VSUsage.as_view({"get": "summary"})(request)

	with step("Assert: bob leads by messages/tokens, alice leads by processes."):
		assert response.status_code == 200
		assert response.data["top_users"]["by_messages"][0]["username"] == "bob"
		assert response.data["top_users"]["by_messages"][0]["count"] == 2
		assert response.data["top_users"]["by_tokens"][0]["username"] == "bob"
		assert response.data["top_users"]["by_processes"][0]["username"] == "alice"


def test_summary_session_time_approximation():
	"""Test summary sums (updated_on - created_on) per user across their chat sessions"""

	with step("Arrange: A chat session with a forced, known duration."):
		org = _make_org()
		session = MChatSession.objects.create(org=org, username="bob")
		start = timezone.now()
		MChatSession.objects.filter(pk=session.pk).update(
			created_on=start, updated_on=start + timezone.timedelta(minutes=10)
		)
		request = _make_request(org)

	with step("Act: Call summary."):
		response = VSUsage.as_view({"get": "summary"})(request)

	with step("Assert: bob's approximated session time is ~600 seconds."):
		assert response.status_code == 200
		row = next(r for r in response.data["session_time"] if r["username"] == "bob")
		assert 599 <= row["seconds"] <= 601
