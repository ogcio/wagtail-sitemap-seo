import logging
from io import BytesIO

import xml.etree.cElementTree as ET
from django.conf import settings

from .root_builder import RootBuilder
from .s3_helper import save_xml

logger = logging.getLogger(__name__)


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
        title = page.title.replace(' ', '').lower()
        tree = ET.ElementTree(new_map)

        if getattr(settings, "SITEMAP_WRITE_S3", False):
            buffer = BytesIO()
            tree.write(buffer, encoding='utf-8', xml_declaration=True)
            content = buffer.getvalue()
            if getattr(settings, "SITEMAP_DIR", None):
                save_xml('{}/map_{}.xml'.format(settings.SITEMAP_DIR, title), content)
            else:
                save_xml('map_{}.xml'.format(title), content)
        else:
            tree.write('map_{}.xml'.format(title), encoding='utf-8', xml_declaration=True)
            logger.info("[sitemap] Wrote map_%s.xml locally", title)

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
            url.title.replace(' ', '').lower()
        )

        lastmod = self._latest_lastmod(url)
        published_elem.text = self._format_date(lastmod)

        sitemap_elem.append(loc_elem)
        sitemap_elem.append(published_elem)
        return sitemap_elem
