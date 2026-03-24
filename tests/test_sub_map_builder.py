"""
Tests for MapBuilder (sub_map_builder) and the _page_slug helper.

Includes regression tests for:
  Issue 2: SITEMAP_WRITE_S3 must not raise AttributeError when absent
  Issue 7: locale derived from page, not hardcoded 'en'
  Issue 8: filenames are ASCII-safe slugs (pipe, accents, spaces all handled)
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
# Issue 8: _page_slug — safe ASCII slug generation
# ---------------------------------------------------------------------------

class TestPageSlug:

    def _slug(self, title):
        from wagtail_sitemap_seo.sub_map_builder import _page_slug
        return _page_slug(title)

    def test_simple_title_lowercased(self):
        assert self._slug("Irish Aid") == "irish-aid"

    def test_spaces_become_hyphens(self):
        assert self._slug("Visit Ireland") == "visit-ireland"

    def test_pipe_character_becomes_hyphen(self):
        # Regression: "Overseas Travel | Travel Wise" used to produce
        # "overseastravel|travelwise" which broke the proxy URL regex.
        assert self._slug("Overseas Travel | Travel Wise") == "overseas-travel-travel-wise"

    def test_accented_characters_are_ascii_normalised(self):
        # Regression: Irish titles with é, ó, á used to produce filenames
        # with non-ASCII bytes that break some S3 / CDN configurations.
        result = self._slug("Éire ag Comhthionól Ginearálta na nA")
        assert result.isascii(), f"Expected ASCII-only slug, got: {result!r}"

    def test_accented_e_dropped_correctly(self):
        assert self._slug("Éire") == "eire"

    def test_multiple_special_chars_collapsed_to_single_hyphen(self):
        assert self._slug("EU 50 & Beyond!") == "eu-50-beyond"

    def test_leading_trailing_hyphens_stripped(self):
        assert not self._slug("---Home---").startswith("-")
        assert not self._slug("---Home---").endswith("-")

    def test_alphanumeric_only_title_unchanged(self):
        assert self._slug("EU50") == "eu50"

    def test_empty_title_returns_empty_string(self):
        assert self._slug("") == ""

    def test_only_special_chars_returns_empty(self):
        assert self._slug("| & !") == ""

    def test_real_world_pipe_title(self):
        slug = self._slug("Overseas Travel | Travel Wise")
        assert "|" not in slug
        assert slug.isascii()

    def test_real_world_irish_title(self):
        slug = self._slug("Éire ag Comhthionól Ginearálta na nA")
        assert slug.isascii()
        assert "|" not in slug
        assert " " not in slug

    def test_slug_matches_proxy_url_regex(self):
        """Slugs must match the proxy view URL pattern [-\\w]+."""
        import re
        pattern = re.compile(r"^[-\w]+$")
        titles = [
            "Overseas Travel | Travel Wise",
            "Éire ag Comhthionól Ginearálta",
            "Irish Aid",
            "Department of Foreign Affairs and Trade",
            "EU50",
            "Ireland at the UN",
        ]
        for title in titles:
            slug = self._slug(title)
            if slug:  # empty slug has no filename to match
                assert pattern.match(slug), (
                    f"Slug {slug!r} (from {title!r}) does not match proxy URL regex [-\\w]+"
                )


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
        if hasattr(settings, "SITEMAP_WRITE_S3"):
            delattr(settings, "SITEMAP_WRITE_S3")

        builder = _bare_map_builder()
        page = _mock_page("Home")

        old = os.getcwd()
        os.chdir(tmp_path)
        try:
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
            builder.build_map(page)
        finally:
            os.chdir(old)

        assert (tmp_path / "map_about.xml").exists(), (
            "build_map() should write map_<title>.xml locally when SITEMAP_WRITE_S3=False"
        )

    def test_build_map_uses_page_locale_not_hardcoded_en(self, tmp_path, settings):
        """
        Regression test for Issue 7.
        build_map() must filter descendants by page.locale, not by a hardcoded 'en' locale.
        """
        settings.SITEMAP_WRITE_S3 = False
        settings.SITEMAP_DIR = None

        builder = _bare_map_builder()
        page = _mock_page("Gaeilge")

        ga_locale = MagicMock()
        ga_locale.language_code = "ga"
        page.locale = ga_locale

        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            builder.build_map(page)
        finally:
            os.chdir(old)

        page.get_descendants.return_value.live.return_value.filter.assert_called_once_with(
            locale=ga_locale
        )

    def test_local_map_file_contains_urlset_root(self, tmp_path, settings):
        settings.SITEMAP_WRITE_S3 = False
        settings.SITEMAP_DIR = None

        builder = _bare_map_builder()
        page = _mock_page("Section")

        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            builder.build_map(page)
        finally:
            os.chdir(old)

        path = tmp_path / "map_section.xml"
        raw = path.read_bytes()
        assert raw.startswith(b"<?xml"), (
            "Sitemap files must start with an XML declaration, not plain text."
        )
        assert b"<urlset" in raw, "Sitemap must have a root <urlset> element."
        # Non-empty maps use </urlset>; an empty tree may serialize as <urlset ... />.
        if b"<url>" in raw:
            assert b"</urlset>" in raw
        else:
            assert b"</urlset>" in raw or b"/>" in raw

        root = ET.parse(str(path)).getroot()
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

    def test_loc_uses_hyphenated_slug(self):
        builder = _bare_map_builder()
        page = _mock_page("My Section")

        elem = builder.build_root_elem(page)

        loc = elem.find("loc")
        assert "map_my-section.xml" in loc.text

    def test_loc_slug_sanitises_pipe_character(self):
        """Regression: pipe in title must not appear in the <loc> URL."""
        builder = _bare_map_builder()
        page = _mock_page("Overseas Travel | Travel Wise")

        elem = builder.build_root_elem(page)

        loc = elem.find("loc")
        assert "|" not in loc.text
        assert "overseas-travel-travel-wise" in loc.text

    def test_loc_slug_sanitises_accented_characters(self):
        """Regression: accented Irish characters must be ASCII-normalised."""
        builder = _bare_map_builder()
        page = _mock_page("Éire ag Comhthionól")

        elem = builder.build_root_elem(page)

        loc = elem.find("loc")
        assert loc.text.isascii(), f"<loc> contains non-ASCII: {loc.text!r}"


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
