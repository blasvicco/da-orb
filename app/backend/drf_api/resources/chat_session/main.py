"""DRF chat session list viewset"""

# Lib imports
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

# App imports
from drf_api.models import MChatSession, MProject
from drf_api.resources.auth.helpers import resolve_request_identity
from drf_api.resources.chat_session.filter import DFChatSession
from drf_api.resources.chat_session.permission import PChatSession
from drf_api.resources.chat_session.serializer import SChatSessionItem

# The detail strings double as i18n keys on the frontend: the shared table component upper-cases
# them and swaps spaces for underscores (see api.error.response.* in the locale files).
_ERR_INVALID_SESSION_IDS = "Chat ids must be a list of integers."
_ERR_NO_SESSIONS = "Select at least one chat."
_ERR_PROJECT_NOT_FOUND = "The destination project no longer exists."
_ERR_SESSIONS_NOT_FOUND = "Some of the selected chats no longer exist."
_ERR_TOO_MANY_SESSIONS = "Too many chats selected."

# Upper bound on one bulk move, so a request can't carry an unbounded IN (...) list.
_MAX_MOVE_SESSIONS = 500


class VSChatSession(
	mixins.ListModelMixin, viewsets.GenericViewSet
):  # pylint: disable=too-many-ancestors
	"""Chat session list view set — the requester's chats with pagination/filter/sort, plus a bulk move between projects."""

	# Sibling of VSChat (which serves the sidebar's fixed-size lists and the WebSocket flow):
	# this is the table view of "all my chats", so it gets the same globally configured
	# DjangoFilterBackend + LimitOffsetPagination the project list uses.
	#
	# No session authentication: identity comes from the Bearer token (see PChatSession), and
	# DRF's SessionAuthentication would otherwise enforce CSRF on unsafe methods for any
	# browser that happens to hold a Django session cookie.
	authentication_classes = []
	filter_backends = [DjangoFilterBackend, OrderingFilter]
	filterset_class = DFChatSession
	ordering = ["-updated_on"]
	ordering_fields = ["created_on", "title", "tokens_used", "updated_on"]
	permission_classes = [PChatSession]
	serializer_class = SChatSessionItem

	def get_queryset(self):
		"""Return the requester's live chats, each annotated with its token total so a page is one query."""
		org, username, connection_key = self._get_org_and_user(self.request)
		if org is None or not username:
			return MChatSession.objects.none()
		return (
			MChatSession.objects.filter(
				connection_key=connection_key,
				deleted_on__isnull=True,
				org=org,
				username=username,
			)
			.select_related("project")
			.annotate(
				tokens_used=Coalesce(
					Sum(
						"usage_events__total_tokens",
						filter=Q(usage_events__event_type="token_usage"),
					),
					0,
				)
			)
		)

	@action(detail=False, methods=["post"])
	def move(self, request, *args, **kwargs):
		"""Move several of the requester's chats into one of the requester's projects — all of them or none."""
		# Every lookup filters by identity directly instead of leaning on object permissions:
		# this is a POST, so PChat-style ownership checks would never fire, and any user of the
		# same tenant could otherwise move someone else's chats.
		org, username, connection_key = self._get_org_and_user(request)
		session_ids = self._parse_session_ids(request.data.get("session_ids"))
		project_id = request.data.get("project_id")
		project = (
			MProject.objects.filter(
				connection_key=connection_key,
				deleted_on__isnull=True,
				id=project_id,
				org=org,
				username=username,
			).first()
			if isinstance(project_id, int) and not isinstance(project_id, bool)
			else None
		)
		if project is None:
			raise NotFound(_ERR_PROJECT_NOT_FOUND)
		sessions = MChatSession.objects.filter(
			connection_key=connection_key,
			deleted_on__isnull=True,
			id__in=session_ids,
			org=org,
			username=username,
		)
		# A missing id means the list the user is looking at is stale (or the id isn't theirs):
		# refuse the whole move rather than silently moving a subset.
		if sessions.count() != len(session_ids):
			raise NotFound(_ERR_SESSIONS_NOT_FOUND)
		moved = sessions.update(project_id=project.pk)
		return Response({"moved": moved, "project_id": project.pk})

	def _get_org_and_user(self, request):
		"""Return (org, username, connection_key) from the request context."""
		return resolve_request_identity(request)

	@staticmethod
	def _parse_session_ids(raw):
		"""Return the de-duplicated chat ids from a request value, or raise a validation error naming session_ids."""
		if not isinstance(raw, list) or any(
			not isinstance(value, int) or isinstance(value, bool) for value in raw
		):
			raise ValidationError({"session_ids": _ERR_INVALID_SESSION_IDS})
		unique_ids = list(dict.fromkeys(raw))
		if not unique_ids:
			raise ValidationError({"session_ids": _ERR_NO_SESSIONS})
		if len(unique_ids) > _MAX_MOVE_SESSIONS:
			raise ValidationError({"session_ids": _ERR_TOO_MANY_SESSIONS})
		return unique_ids
