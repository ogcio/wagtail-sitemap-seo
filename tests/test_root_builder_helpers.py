"""
Tests for RootBuilder static helper methods.
These are pure-logic / no-DB tests.
"""

import pytest

from wagtail_sitemap_seo.root_builder import RootBuilder


# ---------------------------------------------------------------------------
# _normalize_path
# ---------------------------------------------------------------------------

class TestNormalizePath:

    def test_adds_leading_slash_when_missing(self):
        assert RootBuilder._normalize_path("en/") == "/en/"

    def test_adds_trailing_slash_when_missing(self):
        assert RootBuilder._normalize_path("/en") == "/en/"

    def test_keeps_both_slashes_when_present(self):
        assert RootBuilder._normalize_path("/en/visit/") == "/en/visit/"

    def test_empty_string_returns_empty(self):
        assert RootBuilder._normalize_path("") == ""

    def test_whitespace_only_returns_empty(self):
        assert RootBuilder._normalize_path("   ") == ""

    def test_deep_path_gets_both_slashes(self):
        assert RootBuilder._normalize_path("en/visit/heritage") == "/en/visit/heritage/"

    def test_already_normalised_path_unchanged(self):
        assert RootBuilder._normalize_path("/ga/comhthionol/") == "/ga/comhthionol/"

    def test_strips_surrounding_whitespace(self):
        assert RootBuilder._normalize_path("  /en/  ") == "/en/"


# ---------------------------------------------------------------------------
# _extract_language_and_suffix
# ---------------------------------------------------------------------------

class TestExtractLanguageAndSuffix:

    def test_simple_language_and_one_segment(self):
        lang, suffix = RootBuilder._extract_language_and_suffix("/en/visit/")
        assert lang == "en"
        assert suffix == "visit/"

    def test_language_only_path_gives_empty_suffix(self):
        lang, suffix = RootBuilder._extract_language_and_suffix("/en/")
        assert lang == "en"
        assert suffix == ""

    def test_multi_segment_path(self):
        lang, suffix = RootBuilder._extract_language_and_suffix("/en/visit/heritage/")
        assert lang == "en"
        assert suffix == "visit/heritage/"

    def test_hyphenated_locale_code(self):
        lang, suffix = RootBuilder._extract_language_and_suffix("/zh-hans/about/")
        assert lang == "zh-hans"
        assert suffix == "about/"

    def test_root_slash_returns_none_lang_and_empty_suffix(self):
        lang, suffix = RootBuilder._extract_language_and_suffix("/")
        assert lang is None
        assert suffix == ""

    def test_irish_locale(self):
        lang, suffix = RootBuilder._extract_language_and_suffix("/ga/comhthionol/")
        assert lang == "ga"
        assert suffix == "comhthionol/"

    def test_three_level_path(self):
        lang, suffix = RootBuilder._extract_language_and_suffix("/en/a/b/c/")
        assert lang == "en"
        assert suffix == "a/b/c/"
