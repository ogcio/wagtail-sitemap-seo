from __future__ import annotations

from django.urls import path, reverse

from wagtail import hooks
from wagtail.admin.menu import MenuItem

from .admin_views import build_sitemaps_admin_view


@hooks.register("register_admin_urls")
def register_admin_urls():
    return [
        path("sitemaps/build/", build_sitemaps_admin_view, name="wagtail_sitemap_seo_build"),
    ]


@hooks.register("register_settings_menu_item")
def register_admin_menu_item():
    return MenuItem(
        "Build sitemaps",
        reverse("wagtail_sitemap_seo_build"),
        icon_name="doc-full-inverse",
        order=9000,
    )
