"""
Tests for the admin view: build_sitemaps_admin_view and _resolve_output_dir.
"""

from unittest.mock import patch

import pytest
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore

from wagtail_sitemap_seo.admin_views import _resolve_output_dir


# ---------------------------------------------------------------------------
# _resolve_output_dir
# ---------------------------------------------------------------------------

class TestResolveOutputDir:

    def test_returns_sitemap_dir_when_set(self, settings):
        settings.SITEMAP_DIR = "/var/www/sitemaps"
        assert _resolve_output_dir() == "/var/www/sitemaps"

    def test_sitemap_dir_takes_priority_over_media_root(self, settings):
        settings.SITEMAP_DIR = "/explicit/sitemap"
        settings.MEDIA_ROOT = "/media"
        assert _resolve_output_dir() == "/explicit/sitemap"

    def test_falls_back_to_media_root_sitemaps_subdir(self, settings):
        settings.SITEMAP_DIR = None
        settings.MEDIA_ROOT = "/var/www/media"
        assert _resolve_output_dir() == "/var/www/media/sitemaps"

    def test_media_root_trailing_slash_is_stripped(self, settings):
        settings.SITEMAP_DIR = None
        settings.MEDIA_ROOT = "/var/www/media/"
        assert _resolve_output_dir() == "/var/www/media/sitemaps"

    def test_raises_when_neither_setting_is_configured(self, settings):
        settings.SITEMAP_DIR = None
        settings.MEDIA_ROOT = None
        with pytest.raises(RuntimeError, match="SITEMAP_DIR or MEDIA_ROOT"):
            _resolve_output_dir()

    def test_raises_when_both_settings_absent(self, settings):
        if hasattr(settings, "SITEMAP_DIR"):
            delattr(settings, "SITEMAP_DIR")
        if hasattr(settings, "MEDIA_ROOT"):
            delattr(settings, "MEDIA_ROOT")
        with pytest.raises(RuntimeError):
            _resolve_output_dir()


# ---------------------------------------------------------------------------
# build_sitemaps_admin_view — output_dir is always passed to call_command
# ---------------------------------------------------------------------------

def _make_post_request(path="/admin/sitemaps/build/"):
    from django.contrib.auth.models import User

    factory = RequestFactory()
    request = factory.post(path)
    # Attach a superuser so Wagtail's permission_required passes
    user = User(username="admin", is_staff=True, is_superuser=True)
    user.pk = 1
    request.user = user
    # Attach message storage required by messages.success/error
    request.session = SessionStore()
    messages_storage = FallbackStorage(request)
    request._messages = messages_storage
    return request


@pytest.mark.django_db
class TestBuildSitemapsAdminViewOutputDir:

    def test_call_command_receives_explicit_output_dir(self, settings):
        settings.SITEMAP_DIR = "/explicit/sitemaps"

        from wagtail_sitemap_seo.admin_views import build_sitemaps_admin_view
        with patch("wagtail_sitemap_seo.admin_views.call_command") as mock_cmd, \
             patch("wagtail_sitemap_seo.admin_views.redirect"), \
             patch("wagtail_sitemap_seo.admin_views.reverse", return_value="/admin/"):
            mock_cmd.return_value = None
            request = _make_post_request()
            build_sitemaps_admin_view(request)

        mock_cmd.assert_called_once_with("build_sitemaps", output_dir="/explicit/sitemaps")

    def test_call_command_never_called_without_output_dir(self, settings):
        """Regression guard: output_dir must always be passed, never rely on cwd."""
        settings.SITEMAP_DIR = "/some/dir"

        from wagtail_sitemap_seo.admin_views import build_sitemaps_admin_view
        with patch("wagtail_sitemap_seo.admin_views.call_command") as mock_cmd, \
             patch("wagtail_sitemap_seo.admin_views.redirect"), \
             patch("wagtail_sitemap_seo.admin_views.reverse", return_value="/admin/"):
            mock_cmd.return_value = None
            request = _make_post_request()
            build_sitemaps_admin_view(request)

        call_kwargs = mock_cmd.call_args
        assert "output_dir" in call_kwargs.kwargs, (
            "call_command must always receive output_dir — never rely on process cwd"
        )

    def test_error_is_logged_not_printed_on_failure(self, settings):
        settings.SITEMAP_DIR = "/some/dir"

        from wagtail_sitemap_seo.admin_views import build_sitemaps_admin_view
        with patch("wagtail_sitemap_seo.admin_views.call_command", side_effect=Exception("boom")), \
             patch("wagtail_sitemap_seo.admin_views.redirect"), \
             patch("wagtail_sitemap_seo.admin_views.reverse", return_value="/admin/"), \
             patch("wagtail_sitemap_seo.admin_views.logger") as mock_logger:
            request = _make_post_request()
            build_sitemaps_admin_view(request)

        mock_logger.exception.assert_called_once()
