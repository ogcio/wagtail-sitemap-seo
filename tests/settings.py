"""
Minimal Django settings used exclusively by the test suite.
"""

SECRET_KEY = "test-secret-key-not-for-production"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "taggit",
    "wagtail",
    "wagtail.admin",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.sites",
    "wagtail.snippets",
    "wagtail.embeds",
    "wagtail.locales",
    "wagtail.users",
    "wagtail_sitemap_seo",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "/static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = "/tmp/wagtail_sitemap_seo_test_media/"

WAGTAIL_SITE_NAME = "Test Site"

# Default sitemap settings — individual tests override via pytest-django's `settings` fixture
SEO_MAP_URL = "https://example.com/map.csv"
SITEMAP_DIR = "sitemap"
SITEMAP_WRITE_S3 = False
