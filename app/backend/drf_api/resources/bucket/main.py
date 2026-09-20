"""DRF bucket viewset"""

# Lib imports
from django.conf import settings
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

# App imports
from core.modules.storage import FStorage
from core.modules.storage.exception import StorageError
from drf_api.models import MBucketFile, MChatSession
from drf_api.resources.auth.helpers import resolve_request_identity
from drf_api.resources.bucket.permission import PBucket
from drf_api.resources.bucket.serializer import SBucketFile

_BYTES_PER_MB = 1024 * 1024
_PRESIGNED_URL_EXPIRES_IN = 300


class VSBucket(viewsets.ViewSet):
	"""Bucket view set — session-scoped file listing, upload, and presigned download."""

	# Class-level (not per-action): most actions are GET-with-query-params or
	# multipart (upload); extraction's PATCH branch reads a JSON body, so
	# JSONParser has to be included here too — a per-action
	# @action(parser_classes=...) kwarg is only merged in by the router's
	# get_urls(), so it's silently ignored when a view is bound directly via
	# as_view({...}) the way this project's own resource tests do.
	parser_classes = [FormParser, JSONParser, MultiPartParser]
	permission_classes = [PBucket]

	def _get_org_and_user(self, request):
		"""Return (org, username, connection_key) from the request context."""
		return resolve_request_identity(request)

	def _get_owned_file(self, request, file_id):
		"""Return the requester's MBucketFile for file_id, 404ing on any ownership mismatch."""
		org, username, connection_key = self._get_org_and_user(request)
		return get_object_or_404(
			MBucketFile,
			id=file_id,
			session__connection_key=connection_key,
			session__org=org,
			session__username=username,
		)

	def _get_owned_session(self, request, session_id):
		"""Return the requester's MChatSession for session_id, 404ing on any ownership mismatch."""
		org, username, connection_key = self._get_org_and_user(request)
		return get_object_or_404(
			MChatSession,
			connection_key=connection_key,
			id=session_id,
			org=org,
			username=username,
		)

	@action(detail=False, methods=["delete"])
	def delete_file(self, request, *args, **kwargs):
		"""Delete a bucket file owned by the requester, removing it from storage and the DB."""
		bucket_file = self._get_owned_file(request, request.query_params.get("file_id"))
		if bucket_file.storage_path:
			try:
				FStorage.get_instance(driver=settings.STORAGE_DRIVER).delete(
					bucket_file.storage_path
				)
			except StorageError as error:
				return Response({"error": str(error)}, status=400)
		bucket_file.delete()
		return Response(status=204)

	@action(detail=False, methods=["get"])
	def download(self, request, *args, **kwargs):
		"""Return a presigned download URL for a bucket file owned by the requester."""
		bucket_file = self._get_owned_file(request, request.query_params.get("file_id"))
		try:
			url = FStorage.get_instance(driver=settings.STORAGE_DRIVER).presigned_url(
				bucket_file.storage_path, expires_in=_PRESIGNED_URL_EXPIRES_IN
			)
		except StorageError as error:
			return Response({"error": str(error)}, status=400)
		return Response({"url": url})

	@action(detail=False, methods=["get", "patch"])
	def extraction(self, request, *args, **kwargs):
		"""Get or persist the cached extraction result for a bucket file owned by the requester."""
		bucket_file = self._get_owned_file(request, request.query_params.get("file_id"))
		if request.method == "PATCH":
			bucket_file.extracted_content = request.data.get("extracted_content") or ""
			bucket_file.save(update_fields=["extracted_content"])
		return Response({"extracted_content": bucket_file.extracted_content})

	@action(detail=False, methods=["get"])
	def files(self, request, *args, **kwargs):
		"""Return every bucket file for a session owned by the requester."""
		session = self._get_owned_session(
			request, request.query_params.get("session_id")
		)
		return Response(SBucketFile(session.bucket_files.all(), many=True).data)

	@action(detail=False, methods=["post"])
	def upload(self, request, *args, **kwargs):
		"""Upload a file into a session's bucket and return the created record."""
		session = self._get_owned_session(request, request.data.get("session_id"))

		upload = request.FILES.get("file")
		if not upload:
			return Response({"error": "MISSING_FILE"}, status=400)
		max_size = settings.BUCKET_MAX_FILE_SIZE_MB * _BYTES_PER_MB
		if upload.size > max_size:
			return Response({"error": "FILE_TOO_LARGE"}, status=400)

		bucket_file = MBucketFile.objects.create(
			mime_type=upload.content_type or "",
			name=upload.name,
			session=session,
			size=upload.size,
		)
		bucket_file.storage_path = bucket_file.build_storage_key()
		try:
			FStorage.get_instance(driver=settings.STORAGE_DRIVER).upload(
				upload.temporary_file_path(),
				bucket_file.storage_path,
				bucket_file.mime_type,
			)
		except StorageError as error:
			bucket_file.delete()
			return Response({"error": str(error)}, status=400)
		bucket_file.save(update_fields=["storage_path"])
		return Response(SBucketFile(bucket_file).data, status=201)
