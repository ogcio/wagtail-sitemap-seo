# wagtail-sitemap-seo

Sitemap XML generation helpers for Wagtail. Generates a standards-compliant
sitemap index (`root_map.xml`) and per-section sitemap files (`map_*.xml`)
with multilingual `hreflang` support, from a remote CSV of page paths.

---

## Requirements

- Python >= 3.10
- Django >= 4.2
- Wagtail >= 5.2
- S3 support (optional): `pip install wagtail-sitemap-seo[s3]`

---

## Install

```bash
pip install wagtail-sitemap-seo

# If you want S3 upload support:
pip install "wagtail-sitemap-seo[s3]"
```

---

## Configure

### 1. Add to `INSTALLED_APPS`

```python
INSTALLED_APPS = [
    ...
    "wagtail_sitemap_seo",
]
```

### 2. Add to your root `urls.py`

The proxy view serves sitemap XML files under your own domain:

```python
from django.urls import path, include

urlpatterns = [
    ...
    path("sitemap/", include("wagtail_sitemap_seo.urls")),
]
```

Sitemaps will be available at `/sitemap/root_map.xml`, `/sitemap/map_home.xml`, etc.

### 3. Set Django settings

| Setting | Required | Description |
|---|---|---|
| `SEO_MAP_URL` | Yes | URL to a CSV file listing the root section paths to include in the sitemap index. Single column, one path per row (e.g. `/en/`, `/en/visit/`, `/ga/`). |
| `SITEMAP_DIR` | Recommended | Directory (local path or S3 prefix) where XML files are written and served from. Defaults to `"sitemap"`. |
| `SITEMAP_WRITE_S3` | No | Set to `True` to upload XML files to S3 instead of writing locally. Requires the `[s3]` extra and standard `django-storages` AWS settings. Defaults to `False`. |

**Example:**

```python
SEO_MAP_URL = "https://your-site.com/static/sitemap-roots.csv"
SITEMAP_DIR = "sitemap"
SITEMAP_WRITE_S3 = False  # set True in production with S3
```

**CSV format** — one path per line, first column only:

```
/en/
/en/visit/
/en/about/
/ga/
/ga/comhthionol/
```

Each path is matched to a live Wagtail `Page` using the locale prefix and
Wagtail's page tree. Per-section maps are generated in the locale of each
matched page automatically.

---

## Run

### Management command

```bash
python manage.py build_sitemaps --output-dir ./sitemaps
```

This writes `root_map.xml` and `map_<section>.xml` files into `--output-dir`.
If `SITEMAP_WRITE_S3=True`, files are uploaded to S3 instead and
`--output-dir` is used only as a temporary working directory.

### Wagtail admin

A **"Build sitemaps"** item appears in the Wagtail **Settings** menu.
Clicking it triggers the same build process as the management command.
Requires the `wagtailadmin.access_admin` permission.

The output directory is resolved automatically:

1. `SITEMAP_DIR` setting (if set)
2. `MEDIA_ROOT/sitemaps` (fallback)

---

## How it works

1. Fetches `SEO_MAP_URL` (a CSV) and resolves each path to a live Wagtail page.
2. Writes `root_map.xml` — a `<sitemapindex>` listing all section maps.
3. For each section page, writes `map_<title>.xml` — a `<urlset>` of all live
   descendants in that page's locale, with `<lastmod>` and `hreflang` alternates.
4. The proxy view (`SitemapProxyView`) serves the XML files from Django's
   configured storage backend under your domain.

---

## S3 setup

Ensure `django-storages` is configured with your AWS credentials:

```python
AWS_STORAGE_BUCKET_NAME = "your-bucket"
AWS_S3_REGION_NAME = "eu-west-1"
# ... other django-storages AWS settings
SITEMAP_WRITE_S3 = True
SITEMAP_DIR = "sitemap"  # S3 key prefix
```

---

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,s3]"
pytest
```
