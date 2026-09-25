"""This module contains tests for the 0019 data migration that gives existing chat sessions their identity's Default project"""

# Lib imports
import pytest
from allure import step
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

_BEFORE_BACKFILL = [("drf_api", "0018_mchatsession_project")]
_AFTER_BACKFILL = [("drf_api", "0019_backfill_default_projects")]


def _migrate(targets):
	"""Migrate the test database to the given targets and return that state's historical apps registry"""
	executor = MigrationExecutor(connection)
	executor.migrate(targets)
	return MigrationExecutor(connection).loader.project_state(targets).apps


@pytest.fixture(name="historical_apps")
def fixture_historical_apps():
	"""Step the schema back to just before the backfill (project still nullable), restoring the latest schema afterwards"""
	try:
		yield _migrate(_BEFORE_BACKFILL)
	finally:
		# Always leave the shared test database on its final schema for every other test.
		executor = MigrationExecutor(connection)
		executor.migrate(executor.loader.graph.leaf_nodes())


@pytest.mark.django_db(transaction=True)
def test_backfill_gives_every_existing_session_its_identitys_default_project(
	historical_apps,
):
	"""Test each (org, username, connection_key) identity gets one Default project, live and soft-deleted sessions alike"""

	with step(
		"Arrange: Sessions for three identities (one soft-deleted), across two orgs."
	):
		org_model = historical_apps.get_model("drf_api", "MOrganization")
		session_model = historical_apps.get_model("drf_api", "MChatSession")
		acme = org_model.objects.create(name="acme", slug="acme")
		globex = org_model.objects.create(name="globex", slug="globex")
		identities = {
			"bob_testdb": (acme, "bob", "TESTDB"),
			"bob_otherdb": (acme, "bob", "OTHERDB"),
			"bob_globex": (globex, "bob", "TESTDB"),
		}
		created = {
			name: session_model.objects.create(
				connection_key=connection_key, org=org, username=username
			)
			for name, (org, username, connection_key) in identities.items()
		}
		# A second and a soft-deleted session for the same identity must share its project.
		created["bob_testdb_second"] = session_model.objects.create(
			connection_key="TESTDB", org=acme, username="bob"
		)
		created["bob_testdb_deleted"] = session_model.objects.create(
			connection_key="TESTDB",
			deleted_on="2026-01-01T00:00:00Z",
			org=acme,
			username="bob",
		)

	with step("Act: Apply the backfill migration."):
		after = _migrate(_AFTER_BACKFILL)

	with step(
		"Assert: No session is left without a project, and each identity has exactly one Default."
	):
		session_model = after.get_model("drf_api", "MChatSession")
		project_model = after.get_model("drf_api", "MProject")
		assert not session_model.objects.filter(project__isnull=True).exists()
		assert project_model.objects.count() == 3
		assert all(
			project.is_default and project.name == "Default"
			for project in project_model.objects.all()
		)
		by_pk = {row.pk: row for row in session_model.objects.select_related("project")}
		for name, session in created.items():
			project = by_pk[session.pk].project
			assert (project.org_id, project.username, project.connection_key) == (
				by_pk[session.pk].org_id,
				by_pk[session.pk].username,
				by_pk[session.pk].connection_key,
			), name
		assert (
			by_pk[created["bob_testdb"].pk].project_id
			== by_pk[created["bob_testdb_second"].pk].project_id
			== by_pk[created["bob_testdb_deleted"].pk].project_id
		)


@pytest.mark.django_db(transaction=True)
def test_backfill_reuses_an_existing_default_project_and_leaves_assigned_sessions_alone(
	historical_apps,
):
	"""Test the backfill never duplicates a Default project and never reassigns a session that already has a project"""

	with step(
		"Arrange: bob already has a Default and a Work project, plus a session in Work and one without a project."
	):
		org_model = historical_apps.get_model("drf_api", "MOrganization")
		project_model = historical_apps.get_model("drf_api", "MProject")
		session_model = historical_apps.get_model("drf_api", "MChatSession")
		org = org_model.objects.create(name="acme", slug="acme")
		default = project_model.objects.create(
			connection_key="TESTDB",
			is_default=True,
			name="Default",
			org=org,
			username="bob",
		)
		work = project_model.objects.create(
			connection_key="TESTDB", name="Work", org=org, username="bob"
		)
		assigned = session_model.objects.create(
			connection_key="TESTDB", org=org, project=work, username="bob"
		)
		orphan = session_model.objects.create(
			connection_key="TESTDB", org=org, username="bob"
		)

	with step("Act: Apply the backfill migration."):
		after = _migrate(_AFTER_BACKFILL)

	with step(
		"Assert: The orphan joined the existing Default, the assigned session stayed in Work, and no Default was duplicated."
	):
		session_model = after.get_model("drf_api", "MChatSession")
		project_model = after.get_model("drf_api", "MProject")
		assert session_model.objects.get(pk=orphan.pk).project_id == default.pk
		assert session_model.objects.get(pk=assigned.pk).project_id == work.pk
		assert project_model.objects.filter(is_default=True).count() == 1


@pytest.mark.django_db(transaction=True)
def test_backfill_is_a_noop_without_any_sessions_and_the_schema_then_tightens(
	historical_apps,
):
	"""Test the backfill tolerates an empty table, and that 0020 (NOT NULL) then applies cleanly"""

	with step("Arrange: A schema at 0018 with no chat sessions."):
		assert historical_apps.get_model("drf_api", "MChatSession").objects.count() == 0

	with step("Act: Apply the backfill, then the NOT NULL tightening."):
		_migrate(_AFTER_BACKFILL)
		after = _migrate([("drf_api", "0020_alter_mchatsession_project")])

	with step("Assert: No projects were invented, and project is now required."):
		assert after.get_model("drf_api", "MProject").objects.count() == 0
		assert (
			after.get_model("drf_api", "MChatSession")._meta.get_field("project").null
			is False
		)
