"""
Tests for the build_sitemaps management command.
DB-dependent tests are marked with @pytest.mark.django_db.
"""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError


@pytest.mark.django_db
class TestBuildSitemapsCommand:

    def test_raises_command_error_when_seo_map_url_is_none(self, settings):
        settings.SEO_MAP_URL = None

        with pytest.raises(CommandError, match="SEO_MAP_URL"):
            call_command("build_sitemaps")

    def test_raises_command_error_when_seo_map_url_is_empty_string(self, settings):
        settings.SEO_MAP_URL = ""

        with pytest.raises(CommandError, match="SEO_MAP_URL"):
            call_command("build_sitemaps")

    def test_raises_command_error_for_nonexistent_locale(self, settings, tmp_path):
        settings.SEO_MAP_URL = "https://example.com/map.csv"

        with pytest.raises(CommandError, match="Locale"):
            call_command("build_sitemaps", locale="xx-nonexistent", output_dir=str(tmp_path))

    def test_output_dir_is_created_if_missing(self, settings, tmp_path):
        settings.SEO_MAP_URL = "https://example.com/map.csv"
        new_dir = tmp_path / "new" / "nested" / "dir"

        # Will fail at locale lookup, but the directory should exist by then
        with pytest.raises(CommandError):
            call_command("build_sitemaps", locale="xx-nonexistent", output_dir=str(new_dir))

        assert new_dir.exists(), "Command should create --output-dir even if it does not exist"
