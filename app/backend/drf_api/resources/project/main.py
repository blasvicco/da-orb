"""DRF project viewset"""

# Lib imports
from django.db.models import Count, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

# App imports
from drf_api.models import MProject
from drf_api.resources.auth.helpers import resolve_request_identity
from drf_api.resources.project.filter import DFProject
from drf_api.resources.project.permission import PProject
from drf_api.resources.project.serializer import SProject

# The detail strings double as i18n keys on the frontend: shared table component upper-cases
# them and swaps spaces for underscores (see api.error.response.* in the locale files).
_ERR_DEFAULT_CANNOT_BE_DELETED = "Default project cannot be deleted."
_ERR_DEFAULT_CANNOT_BE_RENAMED = "Default project cannot be renamed."
_ERR_STILL_HAS_ACTIVE_CHAT_SESSIONS = "Project still has active chat sessions."


class VSProject(viewsets.ModelViewSet):  # pylint: disable=too-many-ancestors
	"""Project view set — identity-scoped CRUD with pagination/filter/sort, plus default, select and empty."""

	# Deliberately a ModelViewSet rather than this app's usual hand-rolled ViewSet: it is the
	# first resource needing real pagination/filtering/sorting, which DRF's globally
	# configured DjangoFilterBackend + LimitOffsetPagination already provide.
	#
	# No session authentication: identity comes from the Bearer token (see PProject), and
	# DRF's SessionAuthentication would otherwise enforce CSRF on unsafe methods for any
	# browser that happens to hold a Django session cookie.
	authentication_classes = []
	filter_backends = [DjangoFilterBackend, OrderingFilter]
	filterset_class = DFProject
	ordering = ["-accessed_on"]
	ordering_fields = [
		"accessed_on",
		"chat_sessions_count",
		"created_on",
		"name",
		"summary",
		"updated_on",
	]
	permission_classes = [PProject]
	serializer_class = SProject

	@action(detail=False, methods=["get"])
	def default(self, request, *args, **kwargs):
		"""Return the requester's Default project, creating it on first use, and mark it as just accessed."""
		org, username, connection_key = self._get_org_and_user(request)
		project = MProject.resolve_for_chat(org, username, connection_key, None)
		return Response(self._serialize_project(project.pk))

	@action(detail=True, methods=["post"])
	def empty(self, request, *args, **kwargs):
		"""Soft-delete every active chat session in a project, so the project itself can then be deleted."""
		project = self.get_object()
		project.chat_sessions.filter(deleted_on__isnull=True).update(
			deleted_on=timezone.now()
		)
		return Response(self._serialize_project(project.pk))

	def get_queryset(self):
		"""Return the requester's non-deleted projects, annotated with their active chat session count."""
		org, username, connection_key = self._get_org_and_user(self.request)
		if org is None or not username:
			return MProject.objects.none()
		return MProject.objects.filter(
			connection_key=connection_key,
			deleted_on__isnull=True,
			org=org,
			username=username,
		).annotate(
			chat_sessions_count=Count(
				"chat_sessions", filter=Q(chat_sessions__deleted_on__isnull=True)
			)
		)

	def perform_create(self, serializer):
		"""Stamp the requester's identity onto the new project — never taken from the request body."""
		org, username, connection_key = self._get_org_and_user(self.request)
		serializer.save(
			connection_key=connection_key,
			is_default=False,
			org=org,
			username=username,
		)

	def perform_destroy(self, instance):
		"""Soft-delete a project, refusing the Default project and any project with active chat sessions."""
		if instance.is_default:
			raise ValidationError({"id": _ERR_DEFAULT_CANNOT_BE_DELETED})
		if instance.chat_sessions.filter(deleted_on__isnull=True).exists():
			raise ValidationError({"id": _ERR_STILL_HAS_ACTIVE_CHAT_SESSIONS})
		instance.delete()

	def perform_update(self, serializer):
		"""Save a project edit, refusing to rename the Default project (a direct API call could otherwise bypass the UI)."""
		instance = serializer.instance
		new_name = serializer.validated_data.get("name", instance.name)
		if instance.is_default and new_name != instance.name:
			raise ValidationError({"name": _ERR_DEFAULT_CANNOT_BE_RENAMED})
		serializer.save()

	@action(detail=True, methods=["post"])
	def select(self, request, *args, **kwargs):
		"""Mark a project as just accessed, so it sorts first in the selector, and return it."""
		project = self.get_object()
		MProject.objects.filter(pk=project.pk).update(accessed_on=timezone.now())
		return Response(self._serialize_project(project.pk))

	def _get_org_and_user(self, request):
		"""Return (org, username, connection_key) from the request context."""
		return resolve_request_identity(request)

	def _serialize_project(self, project_id):
		"""Re-fetch a project through get_queryset() so its chat_sessions_count annotation is fresh, and serialize it."""
		return SProject(self.get_queryset().get(pk=project_id)).data
