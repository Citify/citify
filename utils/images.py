import boto3
import uuid
import io
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


def process_and_upload(file_storage):
    """
    Takes a Flask file upload, compresses it into two sizes,
    uploads both to Backblaze B2, and returns (full_url, thumb_url).
    """
    bucket   = current_app.config['B2_BUCKET_NAME']
    endpoint = current_app.config['B2_ENDPOINT_URL'].rstrip('/')

    img = Image.open(file_storage)

    # Convert RGBA / palette to RGB for JPEG
    if img.mode in ('RGBA', 'P', 'LA'):
        img = img.convert('RGB')

    uid = uuid.uuid4().hex

    # --- Full size ---
    full_img = img.copy()
    full_img.thumbnail(FULL_SIZE, Image.LANCZOS)
    full_buf = io.BytesIO()
    full_img.save(full_buf, format='JPEG', quality=QUALITY, optimize=True)
    full_buf.seek(0)
    full_key = f"products/full/{uid}.jpg"

    # --- Thumbnail ---
    thumb_img = img.copy()
    thumb_img.thumbnail(THUMBNAIL_SIZE, Image.LANCZOS)
    # Centre-crop to square
    w, h = thumb_img.size
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

    # Correct Backblaze B2 public URL: endpoint/bucket/key
    full_url  = f"{endpoint}/{bucket}/{full_key}"
    thumb_url = f"{endpoint}/{bucket}/{thumb_key}"

    return full_url, thumb_url


def upload_logo(file_storage, merchant_slug):
    """Upload merchant logo image."""
    bucket   = current_app.config['B2_BUCKET_NAME']
    endpoint = current_app.config['B2_ENDPOINT_URL'].rstrip('/')

    img = Image.open(file_storage)
    if img.mode in ('RGBA', 'P', 'LA'):
        img = img.convert('RGB')
    img.thumbnail((600, 600), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=85, optimize=True)
    buf.seek(0)

    key = f"logos/{merchant_slug}.jpg"
    client = get_b2_client()
    client.upload_fileobj(buf, bucket, key, ExtraArgs={'ContentType': 'image/jpeg'})

    # Correct Backblaze B2 public URL: endpoint/bucket/key
    return f"{endpoint}/{bucket}/{key}"
