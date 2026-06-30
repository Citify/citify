import csv
import io
import re
import requests
import feedparser
from bs4 import BeautifulSoup


def parse_csv(file_storage):
    """
    Parse a merchant product CSV upload.
    Expected columns: name_en, name_fr, description_en, description_fr, price
    Returns list of dicts.
    """
    stream = io.StringIO(file_storage.stream.read().decode('utf-8-sig'))
    reader = csv.DictReader(stream)
    products = []
    for row in reader:
        name_en = row.get('name_en', '').strip()
        if not name_en:
            continue
        price = None
        price_on_request = False
        raw_price = row.get('price', '').strip().replace('$', '').replace(',', '')
        if raw_price.lower() in ('', 'sur demande', 'on request', 'n/a'):
            price_on_request = True
        else:
            try:
                price = float(raw_price)
            except ValueError:
                price_on_request = True

        products.append({
            'name_en':          name_en,
            'name_fr':          row.get('name_fr', '').strip(),
            'description_en':   row.get('description_en', '').strip(),
            'description_fr':   row.get('description_fr', '').strip(),
            'price':            price,
            'price_on_request': price_on_request,
        })
    return products


def _parse_price(text):
    """
    Extract a float price from a string like '$12.99', '12,99 $', 'CAD 45.00'.
    Returns (float, False) on success, (None, True) if no price found.
    """
    if not text:
        return None, True
    cleaned = re.sub(r'[^\d.,]', '', str(text)).replace(',', '.')
    match = re.search(r'\d+\.?\d*', cleaned)
    if match:
        try:
            return float(match.group()), False
        except ValueError:
            pass
    return None, True


def _is_valid_image_url(url):
    """Basic check that a URL looks like an image."""
    if not url or not url.startswith('http'):
        return False
    low = url.lower().split('?')[0]
    return any(low.endswith(ext) for ext in ('.jpg', '.jpeg', '.png', '.webp', '.gif'))


def import_from_rss(url):
    """
    Import products from an RSS/Atom feed URL.
    Returns (list_of_product_dicts, error_string_or_None).
    """
    if not url.startswith('http'):
        url = 'https://' + url

    try:
        feed = feedparser.parse(url)
    except Exception as e:
        return [], f"Could not parse feed: {e}"

    if feed.bozo and not feed.entries:
        return [], "Feed could not be read. Please check the URL and try again."

    if not feed.entries:
        return [], "Feed is empty or contains no products."

    products = []
    for entry in feed.entries[:50]:
        name = entry.get('title', '').strip()
        if not name:
            continue

        # Strip HTML from summary/description
        raw_summary = entry.get('summary', '') or entry.get('description', '')
        if raw_summary:
            description = BeautifulSoup(raw_summary, 'html.parser').get_text(separator=' ', strip=True)[:500]
        else:
            description = ''

        # Try to find a price
        price = None
        price_on_request = False

        price_candidates = [
            entry.get('price_value'),
            entry.get('g_price'),
            entry.get('price'),
        ]
        for tag in entry.get('tags', []):
            term = tag.get('term', '')
            if re.match(r'^\$?\d+[\d.,]*$', term.strip()):
                price_candidates.append(term)

        for candidate in price_candidates:
            if candidate:
                price, price_on_request = _parse_price(str(candidate))
                if price is not None:
                    break

        if price is None:
            match = re.search(r'\$\s*(\d+[\d.,]*)', name)
            if match:
                price, price_on_request = _parse_price(match.group(1))

        if price is None:
            price_on_request = True

        # Extract image URL — try multiple sources in priority order
        image_url = None

        # 1. media:content
        media_content = entry.get('media_content', [])
        if media_content:
            image_url = media_content[0].get('url')

        # 2. media:thumbnail
        if not image_url:
            media_thumbnail = entry.get('media_thumbnail', [])
            if media_thumbnail:
                image_url = media_thumbnail[0].get('url')

        # 3. enclosures
        if not image_url:
            for enc in entry.get('enclosures', []):
                if enc.get('type', '').startswith('image/'):
                    image_url = enc.get('href') or enc.get('url')
                    break

        # 4. img tag inside summary HTML
        if not image_url and raw_summary:
            img_tag = BeautifulSoup(raw_summary, 'html.parser').find('img')
            if img_tag:
                src = img_tag.get('src') or img_tag.get('data-src')
                if src and src.startswith('http'):
                    image_url = src

        # 5. entry link page — only if we still have nothing and link exists
        # (skipped to keep import fast; RSS media fields should be sufficient)

        # Validate
        if image_url and not image_url.startswith('http'):
            image_url = None

        products.append({
            'name_en':          name,
            'name_fr':          '',
            'description_en':   description,
            'description_fr':   '',
            'price':            price,
            'price_on_request': price_on_request,
            'image_url':        image_url or '',
        })

    if not products:
        return [], "No products could be extracted from this feed."

    return products, None


def import_from_website(url):
    """
    Attempt to scrape products from a merchant website.
    Works best with WooCommerce and Shopify.
    Returns list of dicts with name_en, description_en, price, image_url fields.
    """
    if not url.startswith('http'):
        url = 'https://' + url

    try:
        resp = requests.get(url, timeout=8, headers={
            'User-Agent': 'Mozilla/5.0 (Citify product importer)'
        })
        resp.raise_for_status()
    except Exception as e:
        return [], f"Could not reach website: {e}"

    # Suppress XML-parsed-as-HTML warning for Atom feeds
    import warnings
    from bs4 import XMLParsedAsHTMLWarning
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

    soup = BeautifulSoup(resp.text, 'html.parser')
    products = []

    # ------------------------------------------------------------------ #
    # Shopify — use /products.json which has full image data
    # ------------------------------------------------------------------ #
    if 'shopify' in resp.text or 'myshopify' in url:
        try:
            base = url.split('/collections')[0].split('/products')[0].split('?')[0].rstrip('/')
            json_url = base + '/products.json?limit=50'
            j = requests.get(json_url, timeout=8).json()
            for p in j.get('products', []):
                variant = p['variants'][0] if p.get('variants') else {}
                price = None
                try:
                    price = float(variant.get('price', ''))
                except Exception:
                    pass

                # Shopify products.json gives images array with src
                image_url = ''
                images = p.get('images', [])
                if images:
                    image_url = images[0].get('src', '')

                products.append({
                    'name_en':          p.get('title', ''),
                    'name_fr':          '',
                    'description_en':   BeautifulSoup(
                        p.get('body_html', ''), 'html.parser'
                    ).get_text()[:300],
                    'description_fr':   '',
                    'price':            price,
                    'price_on_request': price is None,
                    'image_url':        image_url,
                })
            if products:
                return products, None
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # WooCommerce product cards
    # ------------------------------------------------------------------ #
    woo_items = soup.select('li.product, .product-type-simple, .product-type-variable')
    if woo_items:
        for item in woo_items[:50]:
            name_tag  = item.select_one('.woocommerce-loop-product__title, h2')
            price_tag = item.select_one('.price .woocommerce-Price-amount, .price')
            img_tag   = item.select_one('img.wp-post-image, .attachment-woocommerce_thumbnail, img')

            name       = name_tag.get_text(strip=True)  if name_tag  else ''
            price_text = price_tag.get_text(strip=True) if price_tag else ''
            if not name:
                continue

            # WooCommerce lazy-loads with data-src
            image_url = ''
            if img_tag:
                image_url = (
                    img_tag.get('data-src') or
                    img_tag.get('data-lazy-src') or
                    img_tag.get('src') or ''
                )
                # Skip tiny placeholder base64 images
                if image_url.startswith('data:'):
                    image_url = ''

            price = None
            try:
                price = float(price_text.replace('$', '').replace(',', '').strip())
            except Exception:
                pass

            products.append({
                'name_en':          name,
                'name_fr':          '',
                'description_en':   '',
                'description_fr':   '',
                'price':            price,
                'price_on_request': price is None,
                'image_url':        image_url,
            })
        if products:
            return products, None

    # ------------------------------------------------------------------ #
    # Generic fallback — any product-like headings with nearby images
    # ------------------------------------------------------------------ #
    for tag in soup.select('h2, h3'):
        text = tag.get_text(strip=True)
        if not (5 < len(text) < 150):
            continue

        # Look for an image near this heading (sibling or parent container)
        image_url = ''
        container = tag.parent
        if container:
            img = container.find('img')
            if img:
                image_url = (
                    img.get('data-src') or
                    img.get('data-lazy-src') or
                    img.get('src') or ''
                )
                if image_url.startswith('data:'):
                    image_url = ''

        products.append({
            'name_en':          text,
            'name_fr':          '',
            'description_en':   '',
            'description_fr':   '',
            'price':            None,
            'price_on_request': True,
            'image_url':        image_url,
        })
        if len(products) >= 30:
            break

    if not products:
        return [], "No products found. CSV import may work better for this site."

    return products, None
