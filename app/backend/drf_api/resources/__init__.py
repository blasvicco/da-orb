"""DRF resource modules"""

# Import order here is intentional, not alphabetical: auth.permission needs
# BasePermission already bound on this module, and seat.permission needs
# PIsOrgAdmin already bound — reordering these three re-introduces a circular
# import. base_serializer/base_viewset have no such constraint.
from drf_api.resources.base_permission import BasePermission
from drf_api.resources.auth.permission import PIsOrgAdmin
from drf_api.resources.seat.permission import PHasActiveSeat
from drf_api.resources.base_serializer import BaseSerializer
from drf_api.resources.base_viewset import BaseViewSet
