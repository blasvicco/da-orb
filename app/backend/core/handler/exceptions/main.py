"""Exception handler"""

# General imports
import logging
import traceback

# Libs imports
from drf_standardized_errors.handler import exception_handler as base_handler

logger = logging.getLogger(__name__)

IGNORE_EXCEPTIONS = {
	"AuthenticationFailed",
	"NotAuthenticated",
	"PermissionDenied",
	"ValidationError",
}


def exception_handler(exc, context):
	"""Log the full traceback for any unhandled exception."""
	if type(exc).__name__ not in IGNORE_EXCEPTIONS:
		logger.error(
			"Unhandled exception in view: %s\n%s",
			str(exc),
			traceback.format_exc(),
			extra={"context": str(context)},
		)
	return base_handler(exc, context)
