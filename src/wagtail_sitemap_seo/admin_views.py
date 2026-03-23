from __future__ import annotations

import logging

from django.conf import settings
from django.contrib import messages
from django.core.management import call_command
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from wagtail.admin.auth import permission_required

logger = logging.getLogger(__name__)


def _resolve_output_dir() -> str:
    """
    Determine the output directory for sitemap files.

    Priority:
      1. settings.SITEMAP_DIR  (explicit operator configuration)
      2. settings.MEDIA_ROOT / "sitemaps"  (safe absolute fallback)
    """
    sitemap_dir = getattr(settings, "SITEMAP_DIR", None)
    if sitemap_dir:
        return str(sitemap_dir)

    media_root = getattr(settings, "MEDIA_ROOT", None)
    if media_root:
        return str(media_root).rstrip("/") + "/sitemaps"

    raise RuntimeError(
        "Cannot determine sitemap output directory. "
        "Set SITEMAP_DIR or MEDIA_ROOT in your Django settings."
    )


@permission_required("wagtailadmin.access_admin")
@require_http_methods(["GET", "POST"])
def build_sitemaps_admin_view(request):
    if request.method == "POST":
        try:
            output_dir = _resolve_output_dir()
            call_command("build_sitemaps", output_dir=output_dir)
            messages.success(request, "Sitemaps generated successfully.")
        except Exception as e:
            logger.exception("Failed to generate sitemaps via admin")
            messages.error(request, f"Failed to generate sitemaps: {e!s}")

        return redirect(reverse("wagtailadmin_home"))

    return render(request, "wagtail_sitemap_seo/build_sitemaps_confirm.html")
