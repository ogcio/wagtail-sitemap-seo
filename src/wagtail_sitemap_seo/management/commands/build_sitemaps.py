# wagtail_sitemap_seo/management/commands/build_sitemaps.py

from __future__ import annotations

import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from wagtail_sitemap_seo.sub_map_builder import MapBuilder


class Command(BaseCommand):
    help = "Build Wagtail sitemap XML files (root_map.xml + per-section map_*.xml)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            default=".",
            help="Directory to write XML files into (default: current working directory).",
        )
        parser.add_argument(
            "--root-file",
            default="root.csv",
            help="Kept for backwards-compat with builder signature; not used if SEO_MAP_URL is set.",
        )

    def handle(self, *args, **options):
        if not getattr(settings, "SEO_MAP_URL", None):
            raise CommandError(
                "SEO_MAP_URL is not set in Django settings. "
                "Your RootBuilder expects settings.SEO_MAP_URL to point to the CSV."
            )

        output_dir = Path(options["output_dir"]).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        old_cwd = Path.cwd()
        os.chdir(output_dir)

        try:
            builder = MapBuilder(options["root_file"])
            builder._load_urls_from_root()
            builder.add_xml_root()

            for page in builder.root_pages:
                builder.build_map(page)

        finally:
            os.chdir(old_cwd)

        self.stdout.write(self.style.SUCCESS(f"Sitemaps generated in: {output_dir}"))
