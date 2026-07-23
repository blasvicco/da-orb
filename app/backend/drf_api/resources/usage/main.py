"""DRF usage viewset"""

# Lib imports
from django.db.models import Count, DurationField, ExpressionWrapper, F, Sum
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

# App imports
from drf_api.models import MChatMessage, MChatSession, MSeat, MUsageEvent
from drf_api.resources.auth.helpers import resolve_request_identity
from drf_api.resources.usage.permission import PUsage

_TOP_N = 5


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
		now = timezone.now()
		tokens_this_month = (
			token_events.filter(
				occurred_on__year=now.year, occurred_on__month=now.month
			).aggregate(total=Sum("total_tokens"))["total"]
			or 0
		)

		return Response(
			{
				"plan": {
					"seats": {
						"total": org.plan.get("seats", org.seat_limit),
						"used": MSeat.objects.filter(org=org, status="active").count(),
					},
					"tokens": {
						"total": org.plan.get("tokens", 0),
						"used": tokens_this_month,
					},
				},
				"processes": {
					"by_process": list(
						process_events.values("process_name")
						.annotate(count=Count("id"))
						.order_by("-count")[:_TOP_N]
					),
					"total": process_events.count(),
				},
				"session_time": self._session_time_by_user(org),
				"tokens": {
					"by_process": list(
						token_events.values("process_name")
						.annotate(total_tokens=Sum("total_tokens"))
						.order_by("-total_tokens")[:_TOP_N]
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
