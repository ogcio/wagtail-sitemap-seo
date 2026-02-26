from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.core.management import call_command
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from wagtail.admin.auth import permission_required


@permission_required("wagtailadmin.access_admin")
@require_http_methods(["GET", "POST"])
def build_sitemaps_admin_view(request):
    if request.method == "POST":
        try:
            call_command("build_sitemaps")
            messages.success(request, f"Sitemaps generated successfully.")
        except Exception as e:
            print(e)
            print(e)
            print(e)
            messages.error(request, f"Failed to generate sitemaps: {e!s}")

        return redirect(reverse("wagtailadmin_home"))

    return render(request, "wagtail_sitemap_seo/build_sitemaps_confirm.html")
