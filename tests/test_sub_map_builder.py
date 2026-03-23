"""
Tests for MapBuilder (sub_map_builder).

Includes a regression test for Issue 2:
  settings.SITEMAP_WRITE_S3 must not raise AttributeError when the setting
  is absent from Django settings.
"""

import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
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


# ---------------------------------------------------------------------------
# Issue 6 regression: lastmod must use real page dates, not datetime.today()
# ---------------------------------------------------------------------------

class TestLatestLastmod:

    def test_returns_most_recent_last_published_at(self):
        builder = _bare_map_builder()
        page = MagicMock()

        d1 = datetime(2024, 1, 10, tzinfo=timezone.utc)
        d2 = datetime(2024, 6, 15, tzinfo=timezone.utc)
        d3 = datetime(2023, 11, 1, tzinfo=timezone.utc)

        (page.get_descendants.return_value
             .live.return_value
             .order_by.return_value
             .values_list.return_value
             .first.return_value) = d2

        result = builder._latest_lastmod(page)
        assert result == d2

    def test_returns_none_when_no_pages_published(self):
        builder = _bare_map_builder()
        page = MagicMock()

        (page.get_descendants.return_value
             .live.return_value
             .order_by.return_value
             .values_list.return_value
             .first.return_value) = None

        result = builder._latest_lastmod(page)
        assert result is None

    def test_orders_by_last_published_at_descending(self):
        builder = _bare_map_builder()
        page = MagicMock()

        qs = (page.get_descendants.return_value
                  .live.return_value
                  .order_by.return_value)
        qs.values_list.return_value.first.return_value = None

        builder._latest_lastmod(page)

        page.get_descendants.return_value.live.return_value.order_by.assert_called_once_with(
            "-last_published_at"
        )


class TestBuildRootElemLastmod:

    def test_lastmod_uses_actual_page_date_not_today(self):
        """
        Regression test for Issue 6.
        build_root_elem must not use datetime.today() — it must use the most
        recent last_published_at from the page's descendants.
        """
        builder = _bare_map_builder()
        page = _mock_page("Home")

        real_date = datetime(2024, 3, 20, tzinfo=timezone.utc)
        builder._latest_lastmod = MagicMock(return_value=real_date)

        elem = builder.build_root_elem(page)

        lastmod = elem.find("lastmod")
        assert lastmod.text == "2024-03-20", (
            "lastmod must reflect the page's actual last_published_at, not today's date"
        )

    def test_lastmod_is_none_when_no_published_date(self):
        builder = _bare_map_builder()
        page = _mock_page("Home")

        builder._latest_lastmod = MagicMock(return_value=None)
        elem = builder.build_root_elem(page)

        lastmod = elem.find("lastmod")
        assert lastmod.text is None

    def test_build_root_elem_calls_latest_lastmod(self):
        builder = _bare_map_builder()
        page = _mock_page("Home")

        builder._latest_lastmod = MagicMock(return_value=None)
        builder.build_root_elem(page)

        builder._latest_lastmod.assert_called_once_with(page)

    def test_lastmod_does_not_equal_todays_date_by_default(self):
        """
        Ensure the old datetime.today() fallback is gone.
        If _latest_lastmod returns None, lastmod text must be None — not today.
        """
        from datetime import date

        builder = _bare_map_builder()
        page = _mock_page("Home")
        builder._latest_lastmod = MagicMock(return_value=None)

        elem = builder.build_root_elem(page)
        lastmod = elem.find("lastmod")

        today_str = date.today().strftime("%Y-%m-%d")
        assert lastmod.text != today_str, (
            "lastmod must not fall back to today's date — use actual page publish date"
        )
