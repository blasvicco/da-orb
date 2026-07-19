"""DRF usage viewset"""

# Lib imports
from django.db.models import Count, DurationField, ExpressionWrapper, F, Sum
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

# App imports
from drf_api.models import MChatMessage, MChatSession, MUsageEvent
from drf_api.resources.auth.helpers import resolve_request_identity
from drf_api.resources.usage.permission import PUsage

_TOP_N = 10


class VSUsage(viewsets.ViewSet):
	"""Org usage dashboard view set — org-admin only (see PUsage)."""

	permission_classes = [PUsage]

	@action(detail=False, methods=["get"])
	def summary(self, request, *args, **kwargs):
		"""Return aggregate token/process/activity metrics for the caller's org."""
		org, _, _ = resolve_request_identity(request)

		token_events = MUsageEvent.objects.filter(org=org, event_type="token_usage")
		process_events = MUsageEvent.objects.filter(
			org=org, event_type="process_execution"
		)

		return Response(
			{
				"processes": {
					"by_process": list(
						process_events.values("process_name")
						.annotate(count=Count("id"))
						.order_by("-count")
					),
					"total": process_events.count(),
				},
				"session_time": self._session_time_by_user(org),
				"tokens": {
					"by_model": list(
						token_events.values("model_name")
						.annotate(total_tokens=Sum("total_tokens"))
						.order_by("-total_tokens")
					),
					"total": token_events.aggregate(total=Sum("total_tokens"))["total"]
					or 0,
				},
				"top_users": {
					"by_messages": list(
						MChatMessage.objects.filter(session__org=org)
						.values(username=F("session__username"))
						.annotate(count=Count("id"))
						.order_by("-count")[:_TOP_N]
					),
					"by_processes": list(
						process_events.values("username")
						.annotate(count=Count("id"))
						.order_by("-count")[:_TOP_N]
					),
					"by_tokens": list(
						token_events.values("username")
						.annotate(total_tokens=Sum("total_tokens"))
						.order_by("-total_tokens")[:_TOP_N]
					),
				},
			}
		)

	def _session_time_by_user(self, org, limit=_TOP_N):
		"""Approximate per-user active time as the sum of (updated_on - created_on) across their chat sessions."""
		# Not true login duration, but needs no new tracking mechanism.
		rows = (
			MChatSession.objects.filter(org=org)
			.values("username")
			.annotate(
				duration=Sum(
					ExpressionWrapper(
						F("updated_on") - F("created_on"), output_field=DurationField()
					)
				)
			)
			.order_by("-duration")[:limit]
		)
		return [
			{
				"seconds": row["duration"].total_seconds() if row["duration"] else 0,
				"username": row["username"],
			}
			for row in rows
		]
