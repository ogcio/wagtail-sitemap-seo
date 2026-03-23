"""
Tests for SitemapProxyView.
All tests mock default_storage so no real filesystem or S3 is needed.
"""

import io
from unittest.mock import MagicMock, patch

import pytest
from django.http import Http404
from django.test import RequestFactory

from wagtail_sitemap_seo.views import SitemapProxyView

SAMPLE_XML = b'<?xml version="1.0" encoding="utf-8"?><sitemapindex/>'


@pytest.fixture()
def factory():
    return RequestFactory()


@pytest.fixture()
def view():
    return SitemapProxyView.as_view()


class TestSitemapProxyView:

    def test_raises_404_when_file_does_not_exist(self, factory, view, settings):
        settings.SITEMAP_DIR = "sitemap"

        with patch("wagtail_sitemap_seo.views.default_storage") as mock_storage:
            mock_storage.exists.return_value = False
            request = factory.get("/sitemap/root_map.xml")
            with pytest.raises(Http404):
                view(request, file_name="root_map")

    def test_returns_200_when_file_exists(self, factory, view, settings):
        settings.SITEMAP_DIR = "sitemap"

        with patch("wagtail_sitemap_seo.views.default_storage") as mock_storage:
            mock_storage.exists.return_value = True
            mock_storage.open.return_value = io.BytesIO(SAMPLE_XML)
            request = factory.get("/sitemap/root_map.xml")
            response = view(request, file_name="root_map")
            assert response.status_code == 200

    def test_content_type_is_application_xml(self, factory, view, settings):
        settings.SITEMAP_DIR = "sitemap"

        with patch("wagtail_sitemap_seo.views.default_storage") as mock_storage:
            mock_storage.exists.return_value = True
            mock_storage.open.return_value = io.BytesIO(SAMPLE_XML)
            request = factory.get("/sitemap/root_map.xml")
            response = view(request, file_name="root_map")
            assert response["Content-Type"] == "application/xml"

    def test_cache_control_header_is_set(self, factory, view, settings):
        settings.SITEMAP_DIR = "sitemap"

        with patch("wagtail_sitemap_seo.views.default_storage") as mock_storage:
            mock_storage.exists.return_value = True
            mock_storage.open.return_value = io.BytesIO(SAMPLE_XML)
            request = factory.get("/sitemap/root_map.xml")
            response = view(request, file_name="root_map")
            assert "public" in response["Cache-Control"]
            assert "max-age=300" in response["Cache-Control"]

    def test_storage_key_uses_sitemap_dir(self, factory, view, settings):
        settings.SITEMAP_DIR = "custom_sitemaps"

        with patch("wagtail_sitemap_seo.views.default_storage") as mock_storage:
            mock_storage.exists.return_value = False
            request = factory.get("/sitemap/root_map.xml")
            try:
                view(request, file_name="root_map")
            except Http404:
                pass
            mock_storage.exists.assert_called_once_with("custom_sitemaps/root_map.xml")

    def test_storage_key_strips_slashes_from_sitemap_dir(self, factory, view, settings):
        settings.SITEMAP_DIR = "/sitemap/"

        with patch("wagtail_sitemap_seo.views.default_storage") as mock_storage:
            mock_storage.exists.return_value = False
            request = factory.get("/sitemap/root_map.xml")
            try:
                view(request, file_name="root_map")
            except Http404:
                pass
            mock_storage.exists.assert_called_once_with("sitemap/root_map.xml")

    def test_defaults_to_sitemap_dir_when_setting_absent(self, factory, view, settings):
        if hasattr(settings, "SITEMAP_DIR"):
            delattr(settings, "SITEMAP_DIR")

        with patch("wagtail_sitemap_seo.views.default_storage") as mock_storage:
            mock_storage.exists.return_value = False
            request = factory.get("/sitemap/root_map.xml")
            try:
                view(request, file_name="root_map")
            except Http404:
                pass
            # Default fallback is "sitemap"
            mock_storage.exists.assert_called_once_with("sitemap/root_map.xml")
