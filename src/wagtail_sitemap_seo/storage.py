try:
    from storages.backends.s3boto3 import S3Boto3Storage as _S3Base
except ImportError as _exc:
    raise ImportError(
        "S3 support requires django-storages. "
        "Install it with: pip install wagtail-sitemap-seo[s3]"
    ) from _exc


class SitemapS3Storage(_S3Base):
    """
    S3 storage for sitemaps that overwrites existing keys.
    Keeps the project's global AWS_S3_FILE_OVERWRITE=False untouched.
    """
    file_overwrite = True
