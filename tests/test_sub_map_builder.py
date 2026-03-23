"""
Tests for MapBuilder (sub_map_builder).

Includes a regression test for Issue 2:
  settings.SITEMAP_WRITE_S3 must not raise AttributeError when the setting
  is absent from Django settings.
"""

import os
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bare_map_builder():
    """Instantiate MapBuilder without hitting the DB."""
    from wagtail_sitemap_seo.sub_map_builder import MapBuilder

    builder = MapBuilder.__new__(MapBuilder)
    builder.root_pages = []
    builder.page_url_map = {}
    builder.root_file = "test.csv"
    builder._locale_cache = {}
    builder._root_url_path_cache = {}
    mock_site = MagicMock()
    mock_site.root_url = "https://example.com"
    builder._site_obj = mock_site
    builder.site = "https://example.com"
    return builder


def _mock_page(title="Home"):
    page = MagicMock()
    page.title = title
    page.full_url = f"https://example.com/en/{title.lower()}/"
    page.last_published_at = None
    page.get_translations.return_value = []
    page.get_descendants.return_value.live.return_value.filter.return_value = []
    return page


# ---------------------------------------------------------------------------
# Issue 2 regression: SITEMAP_WRITE_S3 missing must not raise AttributeError
# ---------------------------------------------------------------------------

class TestSitemapWriteS3Setting:

    def test_build_map_does_not_raise_when_setting_absent(self, tmp_path, settings):
        """
        Regression test for Issue 2.
        If SITEMAP_WRITE_S3 is not defined in settings, build_map() must not
        raise AttributeError. It should fall back to local file writing.
        """
        # Remove the setting to simulate it being absent
        if hasattr(settings, "SITEMAP_WRITE_S3"):
            delattr(settings, "SITEMAP_WRITE_S3")

        builder = _bare_map_builder()
        page = _mock_page("Home")

        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            with patch("wagtail_sitemap_seo.sub_map_builder.Locale") as MockLocale:
                MockLocale.objects.get.return_value = MagicMock()
                # Must not raise AttributeError
                try:
                    builder.build_map(page)
                except AttributeError as exc:
                    pytest.fail(
                        f"build_map() raised AttributeError when SITEMAP_WRITE_S3 "
                        f"was absent from settings: {exc}"
                    )
        finally:
            os.chdir(old)

    def test_build_map_writes_local_file_when_s3_disabled(self, tmp_path, settings):
        settings.SITEMAP_WRITE_S3 = False
        settings.SITEMAP_DIR = None

        builder = _bare_map_builder()
        page = _mock_page("About")

        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            with patch("wagtail_sitemap_seo.sub_map_builder.Locale") as MockLocale:
                MockLocale.objects.get.return_value = MagicMock()
                builder.build_map(page)
        finally:
            os.chdir(old)

        assert (tmp_path / "map_about.xml").exists(), (
            "build_map() should write map_<title>.xml locally when SITEMAP_WRITE_S3=False"
        )

    def test_local_map_file_contains_urlset_root(self, tmp_path, settings):
        settings.SITEMAP_WRITE_S3 = False
        settings.SITEMAP_DIR = None

        builder = _bare_map_builder()
        page = _mock_page("Section")

        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            with patch("wagtail_sitemap_seo.sub_map_builder.Locale") as MockLocale:
                MockLocale.objects.get.return_value = MagicMock()
                builder.build_map(page)
        finally:
            os.chdir(old)

        root = ET.parse(str(tmp_path / "map_section.xml")).getroot()
        assert "urlset" in root.tag, (
            "Per-section map files must have <urlset> as their root element."
        )


# ---------------------------------------------------------------------------
# build_root_elem structure
# ---------------------------------------------------------------------------

class TestBuildRootElem:

    def test_returns_sitemap_element(self):
        builder = _bare_map_builder()
        page = _mock_page("Home")

        elem = builder.build_root_elem(page)

        assert elem.tag == "sitemap"

    def test_sitemap_elem_contains_loc(self):
        builder = _bare_map_builder()
        page = _mock_page("Home")

        elem = builder.build_root_elem(page)

        loc = elem.find("loc")
        assert loc is not None
        assert loc.text is not None
        assert loc.text.endswith("map_home.xml")

    def test_sitemap_elem_contains_lastmod(self):
        builder = _bare_map_builder()
        page = _mock_page("Home")

        elem = builder.build_root_elem(page)

        lastmod = elem.find("lastmod")
        assert lastmod is not None

    def test_loc_uses_page_title_slug(self):
        builder = _bare_map_builder()
        page = _mock_page("My Section")

        elem = builder.build_root_elem(page)

        loc = elem.find("loc")
        assert "map_mysection.xml" in loc.text
