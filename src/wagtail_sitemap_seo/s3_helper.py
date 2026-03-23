from django.core.files.base import ContentFile


def save_xml(name: str, content: bytes) -> str:
    """
    Save an XML file to S3 using SitemapS3Storage.

    Requires the [s3] extra: pip install wagtail-sitemap-seo[s3]

    Returns the final storage path.
    """
    from .storage import SitemapS3Storage  # lazy: only imported when S3 is actually used

    storage = SitemapS3Storage()
    if storage.exists(name):
        storage.delete(name)
    return storage.save(name, ContentFile(content))