from __future__ import annotations

from io import BytesIO
import csv
import urllib.request
import xml.etree.cElementTree as ET

from django.conf import settings
from wagtail.models import Locale, Page, Site

from .base import BaseBuilder
from .s3_helper import save_xml


def email_management_enabled() -> bool:
    return getattr(settings, "WAGTAIL_EMAIL_MANAGEMENT_ENABLED", True)


class RootBuilder(BaseBuilder):
    """
    Builds a sitemap *index* (root_map.xml) from a remote CSV (settings.SEO_MAP_URL).

    The CSV is expected to contain URL paths in the first column, e.g:
      /en/
      /en/about/
      /en/services/
    """

    def __init__(self, root_file: str):
        self.root_file = root_file
        self.root_pages: list[Page] = []
        self.page_url_map: dict[str, Page] = {}

        # Avoid DB access at import time; resolve site here instead.
        self._site_obj = Site.objects.get(is_default_site=True)
        self.site = self._site_obj.site_name

    def site_map_init(self, root: bool = False):
        xml_root = ET.Element("urlset")
        xml_root.attrib["xmlns:xsi"] = "https://www.w3.org/2001/XMLSchema-instance"
        xml_root.attrib["xmlns:xhtml"] = "https://www.w3.org/1999/xhtml"
        xml_root.attrib["xsi:schemaLocation"] = (
            "https://www.sitemaps.org/schemas/sitemap/0.9"
            + " https://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd"
        )
        xml_root.attrib["xmlns"] = "https://www.sitemaps.org/schemas/sitemap/0.9"
        return xml_root

    def add_xml_root(self, xml_root):
        sitemap_index = ET.Element("sitemapindex")
        sitemap_index.attrib["xmlns"] = "http://www.sitemaps.org/schemas/sitemap/0.9"

        for page in self.root_pages:
            # BaseBuilder.build_root_elem should NOT call page.get_url()
            # (it often returns None outside a request). It should use:
            #   page.relative_url(self._site_obj) or page.get_full_url(site=self._site_obj)
            elem = self.build_root_elem(page)
            sitemap_index.append(elem)

        xml_root.append(sitemap_index)
        tree = ET.ElementTree(xml_root)

        if settings.SITEMAP_WRITE_S3:
            buffer = BytesIO()
            tree.write(buffer, encoding="utf-8", xml_declaration=True)
            content = buffer.getvalue()

            key = "root_map.xml"
            if getattr(settings, "SITEMAP_DIR", None):
                key = f"{settings.SITEMAP_DIR}/root_map.xml"
            save_xml(key, content)
        else:
            tree.write("root_map.xml", encoding="utf-8", xml_declaration=True)

    def get_site(self):
        return self.site

    @staticmethod
    def _normalize_path(value: str) -> str:
        value = (value or "").strip()
        if not value:
            return ""
        if not value.startswith("/"):
            value = "/" + value
        if not value.endswith("/"):
            value = value + "/"
        return value

    def _load_urls_from_root(self):
        urls: list[str] = []
        if not getattr(settings, "SEO_MAP_URL", None):
            return

        response = urllib.request.urlopen(settings.SEO_MAP_URL)
        lines = [line.decode("utf-8") for line in response.readlines()]
        cr = csv.reader(lines)

        for row in cr:
            if row and row[0]:
                path = self._normalize_path(row[0])
                if path:
                    urls.append(path)

        locale = Locale.objects.get(language_code="en")

        for path in urls:
            # Match by URL (path), not slug.
            # url_path is internal Wagtail tree path (often like /home/en/...),
            # so __endswith is the simplest reliable matcher.
            page = (
                Page.objects.live()
                .filter(locale=locale, url_path__endswith=path)
                .specific()
                .first()
            )

            if not page:
                print(f"[root-sitemap] Not found: {path}")
                continue

            # Optional: if duplicates exist, prefer the one whose generated path matches exactly
            # for this Site. (This avoids wrong matches when multiple branches end with same suffix.)
            # Only run if we actually have ambiguity.
            duplicates = (
                Page.objects.live()
                .filter(locale=locale, url_path__endswith=path)
                .specific()
            )
            if duplicates.count() > 1:
                for candidate in duplicates:
                    if candidate.relative_url(self._site_obj) == path:
                        page = candidate
                        break

            self.page_url_map[path] = page
            self.root_pages.append(page)
