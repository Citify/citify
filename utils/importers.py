import csv
import io
import requests
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
            'name_en':        name_en,
            'name_fr':        row.get('name_fr', '').strip(),
            'description_en': row.get('description_en', '').strip(),
            'description_fr': row.get('description_fr', '').strip(),
            'price':          price,
            'price_on_request': price_on_request,
        })
    return products


def import_from_website(url):
    """
    Attempt to scrape products from a merchant website.
    Works best with WooCommerce and simple product pages.
    Returns list of dicts with name_en, description_en, price fields.
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

    soup = BeautifulSoup(resp.text, 'html.parser')
    products = []

    # WooCommerce product cards
    woo_items = soup.select('li.product, .woocommerce-loop-product__link')
    if woo_items:
        for item in woo_items[:50]:
            name_tag  = item.select_one('.woocommerce-loop-product__title, h2')
            price_tag = item.select_one('.price .woocommerce-Price-amount, .price')
            name  = name_tag.get_text(strip=True)  if name_tag  else ''
            price_text = price_tag.get_text(strip=True) if price_tag else ''
            if name:
                price = None
                try:
                    price = float(price_text.replace('$', '').replace(',', '').strip())
                except Exception:
                    pass
                products.append({'name_en': name, 'description_en': '', 'price': price,
                                 'price_on_request': price is None,
                                 'name_fr': '', 'description_fr': ''})
        return products, None

    # Shopify product JSON feed
    if 'shopify' in resp.text or 'myshopify' in url:
        try:
            json_url = url.rstrip('/') + '/products.json?limit=50'
            j = requests.get(json_url, timeout=8).json()
            for p in j.get('products', []):
                variant = p['variants'][0] if p.get('variants') else {}
                price = None
                try:
                    price = float(variant.get('price', ''))
                except Exception:
                    pass
                products.append({
                    'name_en': p.get('title', ''),
                    'description_en': BeautifulSoup(p.get('body_html', ''), 'html.parser').get_text()[:300],
                    'price': price,
                    'price_on_request': price is None,
                    'name_fr': '', 'description_fr': '',
                })
            return products, None
        except Exception:
            pass

    # Generic fallback: look for any product-like headings
    for tag in soup.select('h2, h3'):
        text = tag.get_text(strip=True)
        if 5 < len(text) < 150:
            products.append({'name_en': text, 'description_en': '', 'price': None,
                             'price_on_request': True, 'name_fr': '', 'description_fr': ''})
        if len(products) >= 30:
            break

    if not products:
        return [], "No products found. CSV import may work better for this site."

    return products, None
