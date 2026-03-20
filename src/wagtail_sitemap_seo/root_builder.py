from __future__ import annotations

import csv
import logging
import urllib.request
import xml.etree.cElementTree as ET
from io import BytesIO
from typing import Optional

from django.conf import settings
from wagtail.models import Locale, Page, Site

from .base import BaseBuilder
from .s3_helper import save_xml

logger = logging.getLogger(__name__)


def email_management_enabled() -> bool:
    return getattr(settings, "WAGTAIL_EMAIL_MANAGEMENT_ENABLED", True)


class RootBuilder(BaseBuilder):
    """
    Builds a sitemap *index* (root_map.xml) from a remote CSV (settings.SEO_MAP_URL).

    CSV first column is expected to contain URL paths, e.g:
      /en/
      /en/visit/
      /ga/comhthionol-ginearalta-na-na/
    """

    def __init__(self, root_file: str):
        self.root_file = root_file
        self.root_pages: list[Page] = []
        self.page_url_map: dict[str, Page] = {}

        # Avoid DB access at import time; resolve Site here instead.
        self._site_obj = Site.objects.get(is_default_site=True)
        self.site = self._site_obj.root_url.rstrip("/")

        # small caches to avoid repetitive DB hits
        self._locale_cache: dict[str, Locale] = {}
        self._root_url_path_cache: dict[int, str] = {}  # locale.id -> root_page.url_path

    # -----------------------------
    # XML generation
    # -----------------------------
    def site_map_init(self, root: bool = False):
        xml_root = ET.Element("urlset")
        xml_root.attrib["xmlns:xsi"] = "http://www.w3.org/2001/XMLSchema-instance"
        xml_root.attrib["xmlns:xhtml"] = "http://www.w3.org/1999/xhtml"
        xml_root.attrib["xsi:schemaLocation"] = (
            "http://www.sitemaps.org/schemas/sitemap/0.9"
            + " http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd"
        )
        xml_root.attrib["xmlns"] = "http://www.sitemaps.org/schemas/sitemap/0.9"
        return xml_root

    def add_xml_root(self, xml_root):
        sitemap_index = ET.Element("sitemapindex")
        sitemap_index.attrib["xmlns"] = "http://www.sitemaps.org/schemas/sitemap/0.9"

        for page in self.root_pages:
            # IMPORTANT: BaseBuilder.build_root_elem should not rely on page.get_url()
            # outside a request. Prefer:
            #   page.relative_url(self._site_obj)  OR  page.get_full_url(site=self._site_obj)
            elem = self.build_root_elem(page)
            sitemap_index.append(elem)

        xml_root.append(sitemap_index)
        tree = ET.ElementTree(xml_root)

        out_name = "root_map.xml"
        if getattr(settings, "SITEMAP_DIR", None):
            out_name = f"{str(settings.SITEMAP_DIR).strip('/')}/root_map.xml"

        if getattr(settings, "SITEMAP_WRITE_S3", False):
            buffer = BytesIO()
            tree.write(buffer, encoding="utf-8", xml_declaration=True)
            content = buffer.getvalue()
            save_xml(out_name, content)
            logger.info("[root-sitemap] Wrote sitemap index to storage: %s", out_name)
        else:
            tree.write(out_name, encoding="utf-8", xml_declaration=True)
            logger.info("[root-sitemap] Wrote sitemap index locally: %s", out_name)

    def get_site(self):
        return self.site

    # -----------------------------
    # Helpers
    # -----------------------------
    @staticmethod
    def _normalize_path(value: str) -> str:
        """Ensure leading and trailing slash."""
        value = (value or "").strip()
        if not value:
            return ""
        if not value.startswith("/"):
            value = "/" + value
        if not value.endswith("/"):
            value = value + "/"
        return value

    @staticmethod
    def _extract_language_and_suffix(path: str) -> tuple[Optional[str], str]:
        """
        Given a normalized public path like "/en/visit/" return:
          ("en", "visit/")
        For "/en/" return:
          ("en", "")
        If no language segment is present, returns:
          (None, "visit/")  or (None, "")
        """
        parts = path.strip("/").split("/")
        if not parts or parts == [""]:
            return None, ""

        first = parts[0]
        # Treat "en", "ga", "zh-hans" etc as potential locale codes.
        # We'll validate against Locale table later.
        remainder = parts[1:]
        suffix = "/".join(remainder) + ("/" if remainder else "")
        return first, suffix

    def _get_locale(self, language_code: str) -> Optional[Locale]:
        if language_code in self._locale_cache:
            return self._locale_cache[language_code]

        try:
            locale = Locale.objects.get(language_code=language_code)
        except Locale.DoesNotExist:
            return None

        self._locale_cache[language_code] = locale
        return locale

    def _get_root_url_path_for_locale(self, locale: Locale) -> str:
        """
        Returns the internal Wagtail url_path for the site's root page *in that locale*,
        e.g. "/home/" or "/ireland/" etc.
        """
        if locale.id in self._root_url_path_cache:
            return self._root_url_path_cache[locale.id]

        root = self._site_obj.root_page
        if root.locale_id != locale.id:
            try:
                root = root.get_translation(locale)
            except Exception:
                # If the root page isn't translated for this locale, fall back to site root
                # (better than crashing; you'll just get fewer matches)
                logger.warning(
                    "[root-sitemap] Site root page has no translation for locale=%s; using default root",
                    locale.language_code,
                )

        root_url_path = root.url_path  # internal tree path, always ends with "/"
        self._root_url_path_cache[locale.id] = root_url_path
        return root_url_path

    # -----------------------------
    # CSV load + page matching
    # -----------------------------
    def _load_urls_from_root(self):
        seo_map_url = getattr(settings, "SEO_MAP_URL", None)
        if not seo_map_url:
            logger.warning("[root-sitemap] settings.SEO_MAP_URL not set; skipping root sitemap build")
            return

        logger.info("[root-sitemap] Loading CSV: %s", seo_map_url)

        try:
            response = urllib.request.urlopen(seo_map_url)
        except Exception:
            logger.exception("[root-sitemap] Failed to fetch CSV from %s", seo_map_url)
            return

        lines = [line.decode("utf-8") for line in response.readlines()]
        cr = csv.reader(lines)

        raw_paths: list[str] = []
        for row in cr:
            if row and row[0]:
                p = self._normalize_path(row[0])
                if p:
                    raw_paths.append(p)

        logger.info("[root-sitemap] Loaded %d path(s) from CSV", len(raw_paths))

        found = 0
        missing = 0
        invalid_locale = 0

        for public_path in raw_paths:
            lang_guess, suffix = self._extract_language_and_suffix(public_path)

            # Determine locale:
            # 1) if CSV path starts with a valid locale code -> use that locale
            # 2) else fall back to default site's locale (root_page.locale)
            locale = None
            if lang_guess:
                locale = self._get_locale(lang_guess)
                if locale is None:
                    invalid_locale += 1
                    logger.warning("[root-sitemap] Unknown locale prefix '%s' in path: %s", lang_guess, public_path)

            if locale is None:
                locale = self._site_obj.root_page.locale  # type: ignore[assignment]

            root_url_path = self._get_root_url_path_for_locale(locale)

            # Homepage case: "/en/" or "/ga/" -> suffix == "" -> match root page translation
            full_url_path = root_url_path + suffix  # root_url_path already endswith "/"

            page = (
                Page.objects.live()
                .filter(locale=locale, url_path=full_url_path)
                .specific()
                .first()
            )

            if not page:
                # Fallback: endswith matcher (less strict) in case tree structure differs.
                # This also helps if the CSV is missing intermediate segments that exist in url_path.
                fallback_suffix = "/" + suffix if suffix and not suffix.startswith("/") else (suffix or "/")
                page = (
                    Page.objects.live()
                    .filter(locale=locale, url_path__endswith=fallback_suffix)
                    .specific()
                    .first()
                )

            if not page:
                missing += 1
                logger.warning("[root-sitemap] Not found: %s (locale=%s)", public_path, locale.language_code)
                continue

            found += 1
            self.page_url_map[public_path] = page
            self.root_pages.append(page)

        logger.info(
            "[root-sitemap] Done. found=%d missing=%d invalid-locale=%d",
            found, missing, invalid_locale
        )
