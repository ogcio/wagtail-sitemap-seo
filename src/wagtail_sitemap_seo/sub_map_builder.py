import logging
import re
import unicodedata
from io import BytesIO

import xml.etree.cElementTree as ET
from django.conf import settings

from .root_builder import RootBuilder
from .s3_helper import save_xml

logger = logging.getLogger(__name__)


def _page_slug(title: str) -> str:
    """
    Convert a page title to a safe, ASCII-only, URL/filename slug.

    Steps:
      1. NFKD-normalise: decompose accented chars (é -> e + combining acute)
      2. Encode to ASCII ignoring combining marks (drops the accent bytes)
      3. Lowercase
      4. Replace any run of non-alphanumeric characters with a single hyphen
      5. Strip leading/trailing hyphens

    Examples:
      "Overseas Travel | Travel Wise"  -> "overseas-travel-travel-wise"
      "Éire ag Comhthionól Ginearálta" -> "eire-ag-comhthionol-ginearlta"
      "Irish Aid"                      -> "irish-aid"
      "EU50"                           -> "eu50"
    """
    normalised = unicodedata.normalize("NFKD", title)
    ascii_bytes = normalised.encode("ascii", "ignore")
    ascii_str = ascii_bytes.decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_str)
    return slug.strip("-")


class MapBuilder(RootBuilder):

    def __init__(self, root_file):
        super().__init__(root_file)

    def build_map(self, page):
        # Use the locale of the page being mapped rather than hardcoding 'en'.
        # This ensures Irish (/ga/), English (/en/), and any other locale
        # sections each get their own correct descendant pages.
        locale = page.locale
        pages = page.get_descendants(inclusive=True).live().filter(locale=locale)

        new_map = self.site_map_init()
        for p in pages:
            elem = self.build_url_elem(p)
            new_map.append(elem)

        slug = _page_slug(page.title)
        tree = ET.ElementTree(new_map)

        if getattr(settings, "SITEMAP_WRITE_S3", False):
            buffer = BytesIO()
            tree.write(buffer, encoding='utf-8', xml_declaration=True)
            content = buffer.getvalue()
            if getattr(settings, "SITEMAP_DIR", None):
                save_xml('{}/map_{}.xml'.format(settings.SITEMAP_DIR, slug), content)
            else:
                save_xml('map_{}.xml'.format(slug), content)
        else:
            tree.write('map_{}.xml'.format(slug), encoding='utf-8', xml_declaration=True)
            logger.info("[sitemap] Wrote map_%s.xml locally", slug)

    def _latest_lastmod(self, page):
        """
        Return the most recent last_published_at across all live descendants
        of `page` (inclusive). Falls back to None if no page has been published.
        """
        result = (
            page.get_descendants(inclusive=True)
            .live()
            .order_by("-last_published_at")
            .values_list("last_published_at", flat=True)
            .first()
        )
        return result

    def build_root_elem(self, url):
        sitemap_elem = ET.Element('sitemap')
        loc_elem = ET.Element('loc')
        published_elem = ET.Element('lastmod')

        loc_elem.text = '{}/sitemap/map_{}.xml'.format(
            self.get_site(),
            _page_slug(url.title)
        )

        lastmod = self._latest_lastmod(url)
        published_elem.text = self._format_date(lastmod)

        sitemap_elem.append(loc_elem)
        sitemap_elem.append(published_elem)
        return sitemap_elem
