import boto3
import uuid
import io
import re
import requests
from PIL import Image
from flask import current_app

THUMBNAIL_SIZE = (400, 400)
FULL_SIZE      = (1200, 1200)
QUALITY        = 82


def get_b2_client():
    return boto3.client(
        's3',
        endpoint_url=current_app.config['B2_ENDPOINT_URL'],
        aws_access_key_id=current_app.config['B2_KEY_ID'],
        aws_secret_access_key=current_app.config['B2_APP_KEY'],
    )


def _resize_and_upload(img, uid):
    """
    Internal: takes a PIL Image and a uid string, resizes to full + thumb,
    uploads both to B2, returns (full_url, thumb_url).
    """
    bucket   = current_app.config['B2_BUCKET_NAME']
    endpoint = current_app.config['B2_ENDPOINT_URL'].rstrip('/')

    if img.mode in ('RGBA', 'P', 'LA'):
        img = img.convert('RGB')

    # --- Full size ---
    full_img = img.copy()
    full_img.thumbnail(FULL_SIZE, Image.LANCZOS)
    full_buf = io.BytesIO()
    full_img.save(full_buf, format='JPEG', quality=QUALITY, optimize=True)
    full_buf.seek(0)
    full_key = f"products/full/{uid}.jpg"

    # --- Thumbnail (centre-cropped square) ---
    thumb_img = img.copy()
    thumb_img.thumbnail(THUMBNAIL_SIZE, Image.LANCZOS)
    w, h  = thumb_img.size
    side  = min(w, h)
    left  = (w - side) // 2
    top   = (h - side) // 2
    thumb_img = thumb_img.crop((left, top, left + side, top + side))
    thumb_buf = io.BytesIO()
    thumb_img.save(thumb_buf, format='JPEG', quality=QUALITY, optimize=True)
    thumb_buf.seek(0)
    thumb_key = f"products/thumb/{uid}.jpg"

    client = get_b2_client()
    client.upload_fileobj(full_buf,  bucket, full_key,  ExtraArgs={'ContentType': 'image/jpeg'})
    client.upload_fileobj(thumb_buf, bucket, thumb_key, ExtraArgs={'ContentType': 'image/jpeg'})

    # Use virtual-hosted-style URL (subdomain) — path-style is deprecated
    base = re.sub(r'https://s3\.'  , f'https://{bucket}.s3.', endpoint)
    full_url  = f"{base}/{full_key}"
    thumb_url = f"{base}/{thumb_key}"
    return full_url, thumb_url


def _coerce_to_pil_image_url(image_url):
    """
    Some CDNs serve HEIC or other PIL-incompatible formats.
    Shopify CDN supports format conversion via URL params — request JPEG instead.
    Returns a URL that is more likely to be a PIL-readable format.
    """
    low = image_url.lower()

    # Shopify CDN: append format=jpg to get JPEG regardless of source format
    if 'cdn.shopify.com' in low:
        sep = '&' if '?' in image_url else '?'
        return image_url + sep + 'format=jpg&width=1200'

    # Generic HEIC/HEIF — nothing we can do without libheif, skip
    base = low.split('?')[0]
    if base.endswith('.heic') or base.endswith('.heif'):
        return None

    return image_url


def process_and_upload(file_storage):
    """
    Takes a Flask file upload, compresses it into two sizes,
    uploads both to Backblaze B2, and returns (full_url, thumb_url).
    """
    img = Image.open(file_storage)
    uid = uuid.uuid4().hex
    return _resize_and_upload(img, uid)


def upload_image_from_url(image_url):
    """
    Downloads a remote image URL, resizes it, uploads to Backblaze B2,
    and returns (full_url, thumb_url).
    Returns (None, None) if the URL is empty, unreachable, or not a
    PIL-readable image format.
    """
    if not image_url or not image_url.startswith('http'):
        return None, None

    if not current_app.config.get('B2_KEY_ID'):
        return None, None

    # Coerce CDN URL to a PIL-friendly format where possible
    fetch_url = _coerce_to_pil_image_url(image_url)
    if fetch_url is None:
        current_app.logger.warning(f"[B2 image] Skipping unsupported format: {image_url}")
        return None, None

    try:
        resp = requests.get(
            fetch_url,
            timeout=15,
            headers={'User-Agent': 'Mozilla/5.0 (Citify importer)'},
        )
        resp.raise_for_status()
        raw = io.BytesIO(resp.content)
        img = Image.open(raw)
        # Convert to RGB immediately — avoids verify/reopen dance and handles HEIC
        # that somehow made it through as a JPEG (Shopify format conversion)
        img = img.convert('RGB')

    except Exception as e:
        current_app.logger.error(f"[B2 image fetch] {fetch_url} → {e}")
        return None, None

    uid = uuid.uuid4().hex
    try:
        return _resize_and_upload(img, uid)
    except Exception as e:
        current_app.logger.error(f"[B2 image upload] {fetch_url} → {e}")
        return None, None


def upload_logo(file_storage, merchant_slug):
    """Save merchant logo to local static folder."""
    import time, os
    img = Image.open(file_storage)
    if img.mode in ('RGBA', 'P', 'LA'):
        img = img.convert('RGB')
    img.thumbnail((600, 600), Image.LANCZOS)
    logos_dir = os.path.join(current_app.root_path, 'static', 'logos')
    os.makedirs(logos_dir, exist_ok=True)
    filename = f"{merchant_slug}-{int(time.time())}.jpg"
    filepath = os.path.join(logos_dir, filename)
    img.save(filepath, format='JPEG', quality=85, optimize=True)
    return f"/static/logos/{filename}"
