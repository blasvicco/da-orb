"""Abstract Web socket consumer"""

# Libs imports
from channels.generic.websocket import AsyncJsonWebsocketConsumer


class ConsumerActionError(Exception):
	"""Exception class for not valid consumer action"""


class ConsumerGroupError(Exception):
	"""Exception class for not implemented group name"""


class CAbstract(AsyncJsonWebsocketConsumer):
	"""Abstract web socket consumer"""

	group_name = None
	group_name_prefix = None
	user = None
	_auth_ready = False

	async def broadcast(self, event):
		"""Broadcast message"""
		await self.send_json(event["payload"])

	async def connect(self):
		"""Accept the raw connection but hold it in an unauthenticated state."""
		# The consumer is not added to its channel group and resolve_context is
		# not called until auth_init confirms the session credentials.
		self.user = self.scope.get("user")
		if not self.user or not self.user.is_authenticated:
			await self.close()
			return
		await self.accept()

	def _get_auth_ok_extra(self) -> dict:
		"""Return extra fields to merge into the auth.ok payload. Override in subclasses."""
		return {}

	async def auth_init(self, content):
		"""Receive sensitive credentials over the encrypted channel and complete the consumer setup."""
		# Closes the socket on any unexpected error.
		organization = self.scope.get("organization")
		is_b1s = (
			bool(organization) and organization.integration.get("auth_driver") == "b1s"
		)

		# B1S: the WS middleware already resolved the real session server-side via the
		# opaque token, so patching from client-supplied fields would be redundant at
		# best. Open ID has no equivalent proxy yet, so it still relies on this patch.
		if not is_b1s and hasattr(self.user, "session") and self.user.session:
			self.user.session.user["password"] = content.get("password", "")
			self.user.session.database = content.get("database", "")

		await self.resolve_context()

		self.group_name = self.get_group_name()
		await self.channel_layer.group_add(self.group_name, self.channel_name)
		self._auth_ready = True

		await self.send_json({"type": "auth.ok", **self._get_auth_ok_extra()})

	# pylint: disable=unused-argument
	async def disconnect(self, code):
		"""Disconnect"""
		if self.group_name:
			await self.channel_layer.group_discard(
				self.group_name,
				self.channel_name,
			)

	def get_group_name(self):
		"""Override in subclass"""
		raise ConsumerGroupError("GROUP_NOT_IMPLEMENTED")

	async def receive_json(self, content, **kwargs):
		"""Receive msg — only auth_init is processed before the handshake completes."""
		method = content.get("type", "").replace(".", "_")
		if not self._auth_ready and method != "auth_init":
			return
		if hasattr(self, method):
			return await getattr(self, method)(content)
		return

	async def resolve_context(self):
		"""Override in subclasses if DB access is needed"""
		return
