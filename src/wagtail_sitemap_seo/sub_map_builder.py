from io import BytesIO
from .root_builder import RootBuilder
from wagtail.models import Locale
from datetime import datetime

import xml.etree.cElementTree as ET

from django.conf import settings

from .s3_helper import save_xml


class MapBuilder(RootBuilder):

    def __init__(self, root_file):
        super().__init__(root_file)

    def build_map(self, page):
        locale = Locale.objects.get(language_code='en')
        pages = page.get_descendants(inclusive=True).live().filter(locale=locale)

        new_map = self.site_map_init()
        for p in pages:
            elem = self.build_url_elem(p)
            new_map.append(elem)
        title = page.title.replace(' ', '').lower()
        tree = ET.ElementTree(new_map)

        if settings.SITEMAP_WRITE_S3:

            buffer = BytesIO()
            tree.write(buffer, encoding='utf-8', xml_declaration=True)
            content = buffer.getvalue()
            if settings.SITEMAP_DIR:
                save_xml('{}/map_{}.xml'.format(settings.SITEMAP_DIR, title), content)
            else:
                save_xml('map_{}.xml'.format(title), content)
        else:
            tree.write('map_{}.xml'.format(title), encoding='utf-8', xml_declaration=True)


    def build_root_elem(self, url):
        sitemap_elem = ET.Element('sitemap')
        loc_elem = ET.Element('loc')
        published_elem = ET.Element('lastmod')
        print(url)

        # TODO: perhaps load path from settings?

        loc_elem.text = '{}/sitemap/map_{}.xml'.format(
            self.get_site(),
            url.title.replace(' ', '').lower()
        )
        published_elem.text = self._format_date(datetime.today())

        sitemap_elem.append(loc_elem)
        sitemap_elem.append(published_elem)
        return sitemap_elem
