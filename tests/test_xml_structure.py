"""
Regression tests for Issue 1 fix: root_map.xml must have <sitemapindex> as
its document root, NOT <urlset> wrapping <sitemapindex>.

These tests are intentionally strict about XML structure because an invalid
sitemap index silently breaks search-engine crawling.
"""

import os
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock

import pytest

SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
SITEMAPINDEX_TAG = f"{{{SITEMAP_NS}}}sitemapindex"
URLSET_TAG = f"{{{SITEMAP_NS}}}urlset"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bare_root_builder(pages=None):
    """
    Instantiate RootBuilder bypassing __init__ (which hits the DB) so we can
    test XML logic in isolation.
    """
    from wagtail_sitemap_seo.root_builder import RootBuilder

    builder = RootBuilder.__new__(RootBuilder)
    builder.root_pages = pages or []
    builder.root_file = "test.csv"
    builder.page_url_map = {}
    builder._locale_cache = {}
    builder._root_url_path_cache = {}
    mock_site = MagicMock()
    mock_site.root_url = "https://example.com"
    builder._site_obj = mock_site
    builder.site = "https://example.com"
    return builder


def _sitemap_elem(name="home"):
    """Return a minimal <sitemap> element for test stubs."""
    elem = ET.Element("sitemap")
    loc = ET.SubElement(elem, "loc")
    loc.text = f"https://example.com/sitemap/map_{name}.xml"
    return elem


@pytest.fixture()
def local_output(tmp_path, settings):
    """
    Switch cwd to tmp_path and configure settings for local (non-S3) output.
    Restores cwd on teardown.
    """
    settings.SITEMAP_WRITE_S3 = False
    settings.SITEMAP_DIR = None
    old = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(old)


# ---------------------------------------------------------------------------
# Tests: add_xml_root produces a valid sitemapindex document
# ---------------------------------------------------------------------------

class TestAddXmlRootStructure:

    def test_root_element_tag_is_sitemapindex(self, local_output):
        builder = _bare_root_builder()
        builder.build_root_elem = MagicMock(return_value=_sitemap_elem())

        builder.add_xml_root()

        root = ET.parse(str(local_output / "root_map.xml")).getroot()
        assert root.tag == SITEMAPINDEX_TAG, (
            f"Expected root tag '{SITEMAPINDEX_TAG}', got '{root.tag}'. "
            "The sitemap index spec requires <sitemapindex> as the document root."
        )

    def test_root_element_is_not_urlset(self, local_output):
        builder = _bare_root_builder()
        builder.build_root_elem = MagicMock(return_value=_sitemap_elem())

        builder.add_xml_root()

        root = ET.parse(str(local_output / "root_map.xml")).getroot()
        assert "urlset" not in root.tag, (
            "root_map.xml must NOT wrap <sitemapindex> inside <urlset>."
        )

    def test_sitemapindex_is_not_a_child_of_urlset(self, local_output):
        """Regression guard: old code nested <sitemapindex> under <urlset>."""
        builder = _bare_root_builder()
        builder.build_root_elem = MagicMock(return_value=_sitemap_elem())

        builder.add_xml_root()

        root = ET.parse(str(local_output / "root_map.xml")).getroot()
        for child in root:
            assert "urlset" not in child.tag, (
                "Found <urlset> as a child of root. "
                "<sitemapindex> must be the document root, not nested."
            )

    def test_sitemap_entries_are_direct_children_of_root(self, local_output):
        pages = [MagicMock(title=f"Section {i}") for i in range(3)]
        builder = _bare_root_builder(pages)
        builder.build_root_elem = MagicMock(
            side_effect=lambda p: _sitemap_elem(p.title.replace(" ", "").lower())
        )

        builder.add_xml_root()

        root = ET.parse(str(local_output / "root_map.xml")).getroot()
        assert len(list(root)) == 3, (
            "All <sitemap> entries must be direct children of <sitemapindex>."
        )

    def test_sitemapindex_namespace_is_correct(self, local_output):
        builder = _bare_root_builder()
        builder.build_root_elem = MagicMock(return_value=_sitemap_elem())

        builder.add_xml_root()

        root = ET.parse(str(local_output / "root_map.xml")).getroot()
        assert SITEMAP_NS in root.tag, (
            f"sitemapindex must carry the sitemap namespace {SITEMAP_NS}."
        )

    def test_root_map_file_is_created(self, local_output):
        builder = _bare_root_builder()
        builder.build_root_elem = MagicMock()

        builder.add_xml_root()

        assert (local_output / "root_map.xml").exists()

    def test_build_root_elem_called_once_per_page(self, local_output):
        pages = [MagicMock(title="A"), MagicMock(title="B"), MagicMock(title="C")]
        builder = _bare_root_builder(pages)
        builder.build_root_elem = MagicMock(
            side_effect=lambda p: _sitemap_elem(p.title.lower())
        )

        builder.add_xml_root()

        assert builder.build_root_elem.call_count == 3

    def test_empty_root_pages_produces_empty_sitemapindex(self, local_output):
        builder = _bare_root_builder(pages=[])
        builder.build_root_elem = MagicMock()

        builder.add_xml_root()

        root = ET.parse(str(local_output / "root_map.xml")).getroot()
        assert root.tag == SITEMAPINDEX_TAG
        assert len(list(root)) == 0

    def test_output_goes_to_sitemap_dir_when_configured(self, tmp_path, settings):
        settings.SITEMAP_WRITE_S3 = False
        settings.SITEMAP_DIR = "maps"
        (tmp_path / "maps").mkdir()

        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            builder = _bare_root_builder()
            builder.build_root_elem = MagicMock()
            builder.add_xml_root()
        finally:
            os.chdir(old)

        out_file = tmp_path / "maps" / "root_map.xml"
        assert out_file.exists(), "root_map.xml should be written inside SITEMAP_DIR"
        root = ET.parse(str(out_file)).getroot()
        assert "sitemapindex" in root.tag


# ---------------------------------------------------------------------------
# Tests: site_map_init still returns <urlset> (used for per-section maps)
# ---------------------------------------------------------------------------

class TestSiteMapInit:

    def test_returns_urlset_element(self):
        from wagtail_sitemap_seo.root_builder import RootBuilder
        builder = RootBuilder.__new__(RootBuilder)
        urlset = builder.site_map_init()
        assert urlset.tag == "urlset"

    def test_urlset_has_sitemap_namespace(self):
        from wagtail_sitemap_seo.root_builder import RootBuilder
        builder = RootBuilder.__new__(RootBuilder)
        urlset = builder.site_map_init()
        assert urlset.attrib.get("xmlns") == SITEMAP_NS

    def test_urlset_has_xhtml_namespace(self):
        from wagtail_sitemap_seo.root_builder import RootBuilder
        builder = RootBuilder.__new__(RootBuilder)
        urlset = builder.site_map_init()
        assert "xmlns:xhtml" in urlset.attrib

    def test_urlset_has_schema_location(self):
        from wagtail_sitemap_seo.root_builder import RootBuilder
        builder = RootBuilder.__new__(RootBuilder)
        urlset = builder.site_map_init()
        assert "xsi:schemaLocation" in urlset.attrib
