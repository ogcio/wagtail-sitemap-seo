"""
Tests for the build_sitemaps management command.
DB-dependent tests are marked with @pytest.mark.django_db.
"""

from unittest.mock import patch

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

    def test_output_dir_is_created_if_missing(self, settings, tmp_path):
        settings.SEO_MAP_URL = "https://example.com/map.csv"
        new_dir = tmp_path / "new" / "nested" / "dir"

        # build_sitemaps will fail when trying to fetch the CSV, but the
        # directory should be created before that point.
        with patch("wagtail_sitemap_seo.sub_map_builder.MapBuilder._load_urls_from_root"):
            with patch("wagtail_sitemap_seo.sub_map_builder.MapBuilder.add_xml_root"):
                call_command("build_sitemaps", output_dir=str(new_dir))

        assert new_dir.exists(), "Command should create --output-dir even if it does not exist"

    def test_locale_argument_no_longer_exists(self):
        """--locale was removed; locale is now derived from each page."""
        from django.core.management import load_command_class
        from django.core.management.base import CommandError
        cmd = load_command_class("wagtail_sitemap_seo", "build_sitemaps")
        parser = cmd.create_parser("manage.py", "build_sitemaps")
        with pytest.raises((SystemExit, CommandError)):
            parser.parse_args(["--locale", "en"])
