"""DRF seat viewset"""

# Lib imports
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

# App imports
from drf_api.models import MSeat
from drf_api.resources.auth.helpers import (
	reinstate_seat,
	resolve_request_identity,
	set_org_admin,
)
from drf_api.resources.seat.permission import PSeat
from drf_api.resources.seat.serializer import SSeat


class VSSeat(viewsets.ViewSet):
	"""Seat/role management view set — org-admin only (see PSeat)."""

	permission_classes = [PSeat]

	@action(detail=False, methods=["post"])
	def reinstate(self, request, *args, **kwargs):
		"""Reinstate a previously revoked seat, subject to the org's current seat_limit."""
		org, _, _ = resolve_request_identity(request)
		username = request.data.get("username", "").strip()
		if not username:
			return Response({"error": "MISSING_USERNAME"}, status=400)

		try:
			seat = reinstate_seat(org, username)
		except ValidationError as error:
			error_msg = error.detail if hasattr(error, "detail") else str(error)
			if isinstance(error_msg, list) and len(error_msg) > 0:
				error_msg = error_msg[0]
			status = 400 if error_msg == "SEAT_NOT_FOUND" else 403
			return Response({"error": error_msg}, status=status)
		return Response(SSeat(seat).data)

	@action(detail=False, methods=["post"])
	def revoke(self, request, *args, **kwargs):
		"""Revoke a seat, freeing capacity for someone else."""
		org, acting_username, _ = resolve_request_identity(request)
		username = request.data.get("username", "").strip()
		if not username:
			return Response({"error": "MISSING_USERNAME"}, status=400)
		if username == acting_username:
			return Response({"error": "CANNOT_REVOKE_SELF"}, status=403)

		seat = get_object_or_404(MSeat, org=org, username=username)
		seat.revoked_by = acting_username
		seat.revoked_on = timezone.now()
		seat.status = "revoked"
		seat.save()
		return Response(SSeat(seat).data)

	@action(detail=False, methods=["get"])
	def seats(self, request, *args, **kwargs):
		"""Return every seat for the caller's org, each annotated with its current role."""
		org, _, _ = resolve_request_identity(request)
		qs = MSeat.objects.filter(org=org)
		return Response(SSeat(qs, many=True).data)

	@action(detail=False, methods=["post"])
	def set_role(self, request, *args, **kwargs):
		"""Grant or revoke the org-admin role for a username."""
		org, acting_username, _ = resolve_request_identity(request)
		username = request.data.get("username", "").strip()
		role = request.data.get("role", "")
		if not username or role not in ("admin", "standard"):
			return Response({"error": "INVALID_REQUEST"}, status=400)
		if username == acting_username and role == "standard":
			return Response({"error": "CANNOT_REMOVE_OWN_ADMIN"}, status=403)

		set_org_admin(org, username, role == "admin")
		return Response({"role": role, "username": username})
