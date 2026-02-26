## Install

pip install wagtail-sitemap-seo

## Configure

Add to INSTALLED_APPS:
- wagtail_sitemap_seo

Set:
- SEO_MAP_URL=<url to your root csv>, single column with each root url in a new row. 
- SITEMAP_WRITE_S3=<boolean for s3 support>
- SITEMAP_DIR=points to a dir for S3
## Run

python manage.py build_sitemaps --output-dir ./sitemaps
