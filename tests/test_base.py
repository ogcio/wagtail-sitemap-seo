"""
Tests for BaseBuilder: _format_date and build_url_elem.
These are pure-logic tests requiring no database.
"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from wagtail_sitemap_seo.base import BaseBuilder


# ---------------------------------------------------------------------------
# _format_date
# ---------------------------------------------------------------------------

class TestFormatDate:
    def setup_method(self):
        self.builder = BaseBuilder()

    def test_returns_none_for_none(self):
        assert self.builder._format_date(None) is None

    def test_returns_none_for_empty_string(self):
        assert self.builder._format_date("") is None

    def test_returns_none_for_false(self):
        assert self.builder._format_date(False) is None

    def test_formats_datetime_to_iso_string(self):
        dt = datetime(2024, 6, 15)
        assert self.builder._format_date(dt) == "2024-06-15"

    def test_formats_datetime_zero_padded(self):
        dt = datetime(2024, 1, 5)
        assert self.builder._format_date(dt) == "2024-01-05"

    def test_parses_valid_date_string_to_datetime(self):
        result = self.builder._format_date("2024-06-15")
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 6
        assert result.day == 15

    def test_invalid_date_string_raises_value_error(self):
        with pytest.raises(ValueError):
            self.builder._format_date("not-a-date")

    def test_invalid_date_format_raises_value_error(self):
        with pytest.raises(ValueError):
            self.builder._format_date("15/06/2024")


# ---------------------------------------------------------------------------
# build_url_elem
# ---------------------------------------------------------------------------

def _make_url(full_url="https://example.com/en/page/", last_published=None, translations=None):
    url = MagicMock()
    url.full_url = full_url
    url.last_published_at = last_published
    url.get_translations.return_value = translations or []
    return url


class TestBuildUrlElem:
    def setup_method(self):
        self.builder = BaseBuilder()

    def test_returns_element_tagged_url(self):
        elem = self.builder.build_url_elem(_make_url())
        assert elem.tag == "url"

    def test_contains_loc_with_correct_text(self):
        url = _make_url(full_url="https://example.com/en/about/")
        elem = self.builder.build_url_elem(url)
        loc = elem.find("loc")
        assert loc is not None
        assert loc.text == "https://example.com/en/about/"

    def test_contains_lastmod_when_published_at_is_set(self):
        url = _make_url(last_published=datetime(2024, 3, 10))
        elem = self.builder.build_url_elem(url)
        lastmod = elem.find("lastmod")
        assert lastmod is not None
        assert lastmod.text == "2024-03-10"

    def test_lastmod_text_is_none_when_not_published(self):
        url = _make_url(last_published=None)
        elem = self.builder.build_url_elem(url)
        lastmod = elem.find("lastmod")
        assert lastmod is not None
        assert lastmod.text is None

    def test_always_contains_x_default_hreflang(self):
        elem = self.builder.build_url_elem(_make_url())
        hreflang_values = [c.attrib.get("hreflang") for c in elem if c.tag == "xhtml:link"]
        assert "x-default" in hreflang_values

    def test_always_contains_en_hreflang(self):
        elem = self.builder.build_url_elem(_make_url())
        hreflang_values = [c.attrib.get("hreflang") for c in elem if c.tag == "xhtml:link"]
        assert "en" in hreflang_values

    def test_translation_locale_is_included(self):
        trans = MagicMock()
        trans.locale.language_code = "ga"
        trans.full_url = "https://example.com/ga/about/"
        url = _make_url(translations=[trans])
        elem = self.builder.build_url_elem(url)
        hreflang_values = [c.attrib.get("hreflang") for c in elem if c.tag == "xhtml:link"]
        assert "ga" in hreflang_values

    def test_multiple_translations_all_included(self):
        translations = []
        for code in ("ga", "fr", "de"):
            t = MagicMock()
            t.locale.language_code = code
            t.full_url = f"https://example.com/{code}/page/"
            translations.append(t)

        url = _make_url(translations=translations)
        elem = self.builder.build_url_elem(url)
        hreflang_values = [c.attrib.get("hreflang") for c in elem if c.tag == "xhtml:link"]
        for code in ("ga", "fr", "de"):
            assert code in hreflang_values

    def test_hreflang_links_have_rel_alternate(self):
        elem = self.builder.build_url_elem(_make_url())
        for child in elem:
            if child.tag == "xhtml:link":
                assert child.attrib.get("rel") == "alternate"

    def test_hreflang_links_have_href_attribute(self):
        elem = self.builder.build_url_elem(_make_url(full_url="https://example.com/en/"))
        for child in elem:
            if child.tag == "xhtml:link":
                assert "href" in child.attrib
