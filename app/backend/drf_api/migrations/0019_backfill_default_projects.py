from django.db import migrations


def backfill_default_projects(apps, _schema_editor):
	"""Give every project-less chat session its (org, username, connection_key) identity's Default project."""
	chat_session = apps.get_model("drf_api", "MChatSession")
	project = apps.get_model("drf_api", "MProject")
	# order_by() clears MChatSession's default ordering, which would otherwise be added to
	# the SELECT and defeat distinct().
	identities = (
		chat_session.objects.filter(project__isnull=True)
		.order_by()
		.values_list("connection_key", "org_id", "username")
		.distinct()
	)
	for connection_key, org_id, username in identities:
		default, _ = project.objects.get_or_create(
			connection_key=connection_key,
			defaults={"name": "Default"},
			is_default=True,
			org_id=org_id,
			username=username,
		)
		chat_session.objects.filter(
			connection_key=connection_key,
			org_id=org_id,
			project__isnull=True,
			username=username,
		).update(project_id=default.pk)


class Migration(migrations.Migration):

	dependencies = [
		("drf_api", "0018_mchatsession_project"),
	]

	operations = [
		migrations.RunPython(backfill_default_projects, migrations.RunPython.noop),
	]
