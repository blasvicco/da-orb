"""URL configuration for core project."""
# The `urlpatterns` list routes URLs to views:
# https://docs.djangoproject.com/en/5.1/topics/http/urls/

# Lib imports
from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

# App imports
from core.views import healthcheck
from drf_api.urls import router as drf_api_urls

v1_router = DefaultRouter()
v1_router.registry.extend(drf_api_urls.registry)

urlpatterns = [
	path("orb/", admin.site.urls),
	path("api/v1/", include((v1_router.urls, "v1"), namespace="v1")),
	path("api/hc-ping/", healthcheck, name="healthcheck"),
]
