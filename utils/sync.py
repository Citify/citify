"""
Citify product sync — runs via systemd timer every 30 minutes.
Processes a batch of merchants with auto_sync=True or is_claimed=False
that have a website URL, in round-robin order by last_synced_at.

Priority:
  1. Shopify /products.json
  2. RSS feed
  3. Skip (no supported source)
"""
import hashlib, json, logging, os, sys, time
from datetime import datetime, timedelta

sys.path.insert(0, '/var/www/citify_ynh')
os.environ.setdefault('FLASK_ENV', 'production')
os.environ.setdefault('DATABASE_URL', 'sqlite:////var/www/citify_ynh/citify.db')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [sync] %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler('/var/log/citify_ynh/sync.log'),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger('citify.sync')

BATCH_SIZE      = 10    # merchants per run
MAX_PRODUCTS    = 150   # max products to process per merchant per run
STALE_DAYS      = 3     # days unseen before marking inactive
PURGE_DAYS      = 30    # days inactive before eligible for admin purge
REQUEST_TIMEOUT = 12
REQUEST_HEADERS = {'User-Agent': 'Citify-Sync/1.0 (citify.ca)'}

def get_app():
    from app import create_app
    return create_app()

def fetch_shopify_products(base_url):
    """Fetch up to MAX_PRODUCTS from Shopify /products.json with pagination."""
    import requests
    base = base_url.rstrip('/')
    products = []
    page = 1
    while len(products) < MAX_PRODUCTS:
        url = f"{base}/products.json?limit=250&page={page}"
        try:
            resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers=REQUEST_HEADERS)
            if resp.status_code == 404:
                return None  # not a Shopify store
            resp.raise_for_status()
            data = resp.json().get('products', [])
            if not data:
                break
            products.extend(data)
            if len(data) < 250:
                break
            page += 1
        except Exception as e:
            log.warning(f"Shopify fetch error {base_url}: {e}")
            return None
    return products[:MAX_PRODUCTS]

def is_shopify(url):
    if not url:
        return False
    import requests
    try:
        resp = requests.get(
            url.rstrip('/') + '/products.json?limit=1',
            timeout=8, headers=REQUEST_HEADERS
        )
        return resp.status_code == 200 and 'products' in resp.json()
    except Exception:
        return False

def content_hash(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

def sync_shopify(app, merchant):
    """Sync products from Shopify /products.json."""
    from app import db
    from models import Product, ProductImage
    from utils.sanitise import clean_text, clean_rich

    raw = fetch_shopify_products(merchant.website)
    if raw is None:
        log.info(f"  {merchant.business_name}: not Shopify or unreachable")
        return 0

    new_hash = content_hash(raw)
    if merchant.content_hash == new_hash:
        log.info(f"  {merchant.business_name}: no changes (hash match)")
        merchant.last_synced_at = datetime.utcnow()
        db.session.commit()
        return 0

    now = datetime.utcnow()
    seen_ids = set()
    added = updated = 0

    for p in raw:
        ext_id = str(p.get('id', ''))
        if not ext_id:
            continue
        seen_ids.add(ext_id)

        # Price from first variant
        variants = p.get('variants', [])
        price = None
        try:
            price = float(variants[0]['price']) if variants else None
        except (ValueError, TypeError, KeyError):
            pass

        # Product URL
        handle = p.get('handle', '')
        product_url = f"{merchant.website.rstrip('/')}/products/{handle}" if handle else ''

        # Image
        images = p.get('images', [])
        image_url = images[0].get('src', '') if images else ''
        if 'cdn.shopify.com' in image_url:
            sep = '&' if '?' in image_url else '?'
            image_url = image_url + sep + 'format=jpg&width=800'

        # Find existing or create
        existing = Product.query.filter_by(
            merchant_id=merchant.id, external_id=ext_id
        ).first()

        if existing:
            existing.name_en      = clean_text(p.get('title', existing.name_en))[:200]
            existing.description_en = clean_rich(p.get('body_html', ''))
            existing.price        = price
            existing.product_url  = product_url
            existing.product_type = clean_text(p.get('product_type', '') or '')[:150] or existing.product_type
            existing.last_seen_at = now
            existing.is_active    = True
            updated += 1
        else:
            prod = Product(
                merchant_id     = merchant.id,
                name_en         = clean_text(p.get('title', ''))[:200],
                description_en  = clean_rich(p.get('body_html', '')),
                price           = price,
                price_on_request= price is None,
                product_url     = product_url,
                product_type    = clean_text(p.get('product_type', '') or '')[:150] or None,
                external_id     = ext_id,
                last_seen_at    = now,
                is_active       = True,
            )
            db.session.add(prod)
            db.session.flush()
            if image_url:
                db.session.add(ProductImage(
                    product_id    = prod.id,
                    image_url     = image_url,
                    thumbnail_url = image_url,
                ))
            added += 1

    # Mark products not seen in this sync
    stale_cutoff = now - timedelta(days=STALE_DAYS)
    stale = Product.query.filter(
        Product.merchant_id == merchant.id,
        Product.external_id != None,
        Product.last_seen_at < stale_cutoff,
        Product.is_active == True,
    ).all()
    for s in stale:
        s.is_active = False
        log.info(f"  Marked stale: {s.name_en}")

    merchant.content_hash   = new_hash
    merchant.last_synced_at = now
    db.session.commit()
    try:
        from app import cache
        cache.clear()
    except Exception:
        pass
    log.info(f"  {merchant.business_name}: +{added} new, {updated} updated, {len(stale)} staled")
    return added + updated

def sync_rss(app, merchant):
    """Sync products from RSS feed."""
    from app import db
    from models import Product, ProductImage
    from utils.importers import import_from_rss
    from utils.sanitise import clean_text, clean_rich

    if not merchant.rss_url:
        return 0
    try:
        products_data, error = import_from_rss(merchant.rss_url)
    except Exception as e:
        log.warning(f"  RSS error {merchant.business_name}: {e}")
        return 0
    if error or not products_data:
        return 0

    now = datetime.utcnow()
    new_hash = content_hash(products_data)
    if merchant.content_hash == new_hash:
        log.info(f"  {merchant.business_name}: RSS no changes")
        merchant.last_synced_at = now
        db.session.commit()
        return 0

    added = 0
    for p in products_data[:MAX_PRODUCTS]:
        name = clean_text(p.get('name_en', ''))
        if not name:
            continue
        existing = Product.query.filter_by(
            merchant_id=merchant.id, name_en=name
        ).first()
        if not existing:
            prod = Product(
                merchant_id     = merchant.id,
                name_en         = name,
                description_en  = clean_rich(p.get('description_en', '')),
                price           = p.get('price'),
                price_on_request= p.get('price_on_request', True),
                last_seen_at    = now,
                is_active       = True,
            )
            db.session.add(prod)
            db.session.flush()
            img = p.get('image_url', '')
            if img:
                db.session.add(ProductImage(
                    product_id=prod.id, image_url=img, thumbnail_url=img
                ))
            added += 1
        else:
            existing.last_seen_at = now

    merchant.content_hash   = new_hash
    merchant.last_synced_at = now
    db.session.commit()
    log.info(f"  {merchant.business_name}: RSS +{added} new products")
    return added

def run_batch():
    app = get_app()
    with app.app_context():
        from app import db
        from models import Merchant

        # Pick batch: unclaimed OR auto_sync, ordered by least recently synced
        merchants = Merchant.query.filter(
            Merchant.is_active == True,
            db.or_(
                Merchant.is_claimed == False,
                Merchant.auto_sync  == True,
            ),
            db.or_(
                Merchant.website != '',
                Merchant.rss_url != '',
            )
        ).order_by(
            Merchant.last_synced_at.asc().nullsfirst()
        ).limit(BATCH_SIZE).all()

        if not merchants:
            log.info("No merchants to sync")
            return

        log.info(f"Syncing batch of {len(merchants)} merchants")
        for merchant in merchants:
            log.info(f"Processing: {merchant.business_name}")
            try:
                # Try Shopify first — check URL before making a probe request
                website = merchant.website or ''
                looks_shopify = (
                    'myshopify.com' in website or
                    'shopify' in website or
                    (website and is_shopify(website))
                )
                if website and looks_shopify:
                    sync_shopify(app, merchant)
                elif merchant.rss_url:
                    sync_rss(app, merchant)
                else:
                    log.info(f"  {merchant.business_name}: no sync source")
                    merchant.last_synced_at = datetime.utcnow()
                    db.session.commit()
            except Exception as e:
                log.error(f"  Error syncing {merchant.business_name}: {e}")
                db.session.rollback()
            time.sleep(2)  # be polite between merchants

if __name__ == '__main__':
    run_batch()
