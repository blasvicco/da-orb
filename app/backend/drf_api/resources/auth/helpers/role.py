"""Org-admin role helpers, backed by Django's own Group/User tables."""

# Each SAP identity gets a namespaced, never-login-capable "peg" User (Django's
# User.username is globally unique, but SAP usernames aren't unique across orgs)
# that exists purely as an M2M anchor into that org's "org-admin:<slug>" Group.
# Ops can bootstrap the first admin for an org entirely through Django Admin's
# native Users/Groups screens — no in-app bootstrap flow is needed.

# Lib imports
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group


def get_org_admin_group(org):
	"""Get or create the Django Group representing this org's admins."""
	return Group.objects.get_or_create(name=f"org-admin:{org.slug}")[0]


def is_org_admin(org, username) -> bool:
	"""Return True if the given username belongs to this org's admin group."""
	return (
		get_user_model()
		.objects.filter(
			username=_peg_username(org, username),
			groups__name=f"org-admin:{org.slug}",
		)
		.exists()
	)


def set_org_admin(org, username, is_admin: bool):
	"""Add or remove the given username from this org's admin group."""
	user, created = get_user_model().objects.get_or_create(
		username=_peg_username(org, username),
		defaults={"is_active": True, "is_staff": False},
	)
	if created:
		user.set_unusable_password()
		user.save()
	group = get_org_admin_group(org)
	(user.groups.add if is_admin else user.groups.remove)(group)


def _peg_username(org, username) -> str:
	"""Return the namespaced, never-login-capable peg username for this SAP identity."""
	return f"{org.slug}.{username}"
