from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime


@login_manager.user_loader
def load_user(user_id):
    return Merchant.query.get(int(user_id))


class Category(db.Model):
    __tablename__ = 'categories'
    id       = db.Column(db.Integer, primary_key=True)
    name_en  = db.Column(db.String(100), nullable=False)
    name_fr  = db.Column(db.String(100), nullable=False)
    slug     = db.Column(db.String(100), unique=True, nullable=False)
    subcategories = db.relationship('Subcategory', backref='category', lazy=True)
    merchants     = db.relationship('Merchant', backref='category', lazy=True)

    def name(self, lang='en'):
        return self.name_fr if lang == 'fr' else self.name_en


class Subcategory(db.Model):
    __tablename__ = 'subcategories'
    id          = db.Column(db.Integer, primary_key=True)
    name_en     = db.Column(db.String(100), nullable=False)
    name_fr     = db.Column(db.String(100), nullable=False)
    slug        = db.Column(db.String(100), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    merchants   = db.relationship('Merchant', backref='subcategory', lazy=True)

    def name(self, lang='en'):
        return self.name_fr if lang == 'fr' else self.name_en


class Merchant(db.Model, UserMixin):
    __tablename__ = 'merchants'

    id               = db.Column(db.Integer, primary_key=True)
    # Auth
    email            = db.Column(db.String(150), unique=True, nullable=False)
    password_hash    = db.Column(db.String(256), nullable=False)
    # Business info
    business_name    = db.Column(db.String(200), nullable=False)
    slug             = db.Column(db.String(200), unique=True, nullable=False)
    description_en   = db.Column(db.Text, default='')
    description_fr   = db.Column(db.Text, default='')
    neq              = db.Column(db.String(20), default='')      # Quebec business number
    # Location
    address          = db.Column(db.String(300), default='')
    city             = db.Column(db.String(100), default='Montréal')
    neighbourhood    = db.Column(db.String(100), default='')
    latitude         = db.Column(db.Float, nullable=True)
    longitude        = db.Column(db.Float, nullable=True)
    # Category
    category_id      = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
    subcategory_id   = db.Column(db.Integer, db.ForeignKey('subcategories.id'), nullable=True)
    # Social links
    website          = db.Column(db.String(300), default='')
    phone            = db.Column(db.String(50), default='')
    whatsapp         = db.Column(db.String(50), default='')
    instagram        = db.Column(db.String(150), default='')
    facebook         = db.Column(db.String(300), default='')
    # RSS feed for product import
    rss_url          = db.Column(db.String(500), default='')
    video_url        = db.Column(db.String(500), default='')
    # --- Delivery ---
    offers_delivery          = db.Column(db.Boolean, default=False)
    delivery_url             = db.Column(db.String(500))
    third_party_delivery_url = db.Column(db.String(500))
    # --- Newsletter ---
    newsletter_url   = db.Column(db.String(500))
    # Auto-sync
    auto_sync        = db.Column(db.Boolean, default=False)
    last_synced_at   = db.Column(db.DateTime, nullable=True)
    content_hash     = db.Column(db.String(64))
    # Rating cache — updated on each new rating
    rating_avg       = db.Column(db.Float, default=0.0)
    rating_count     = db.Column(db.Integer, default=0)
    # --- Promotion banner ---
    promo_title      = db.Column(db.String(200))
    promo_body       = db.Column(db.String(500))
    promo_url        = db.Column(db.String(500))
    promo_expires    = db.Column(db.Date, nullable=True)
    affiliate_suffix = db.Column(db.String(200))
    affiliate_url    = db.Column(db.String(500))
    # Opening hours — JSON string: {"mon":{"open":"09:00","close":"17:00","closed":false}, ...}
    hours_json       = db.Column(db.Text, default='')
    # Claimed status (for seeded/scraped listings)
    is_claimed       = db.Column(db.Boolean, default=True)  # True for self-registered
    claim_token      = db.Column(db.String(100), nullable=True)
    claim_token_expires = db.Column(db.DateTime, nullable=True)
    # Featured
    is_featured      = db.Column(db.Boolean, default=False)
    featured_until   = db.Column(db.DateTime, nullable=True)
    # Status
    is_active        = db.Column(db.Boolean, default=True)
    is_admin         = db.Column(db.Boolean, default=False)
    is_verified      = db.Column(db.Boolean, default=False)   # NEQ verified badge
    flag_count       = db.Column(db.Integer, default=0)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    # Logo/banner
    logo_url         = db.Column(db.String(500), default='')
    banner_url       = db.Column(db.String(500), default='')

    products   = db.relationship('Product',  backref='merchant', lazy=True,
                               cascade='all, delete-orphan')
    flags      = db.relationship('Flag',     backref='merchant', lazy=True,
                               cascade='all, delete-orphan')
    locations  = db.relationship('Location', backref='merchant', lazy=True,
                               cascade='all, delete-orphan', order_by='Location.id')
    ratings    = db.relationship('Rating',   backref='merchant', lazy=True,
                               cascade='all, delete-orphan')
    messages   = db.relationship('Message',  backref='merchant', lazy=True,
                               cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def has_neq(self):
        return bool(self.neq and self.neq.strip())

    @property
    def active_promo(self):
        """Return promo data if currently active, else None."""
        from datetime import date
        if not self.promo_title:
            return None
        if self.promo_expires and self.promo_expires < date.today():
            return None
        return self

    def description(self, lang='en'):
        return self.description_fr if lang == 'fr' else self.description_en

    def product_count(self):
        return Product.query.filter_by(merchant_id=self.id, is_active=True).count()

    def get_hours(self):
        import json
        if not self.hours_json:
            return {}
        try:
            return json.loads(self.hours_json)
        except Exception:
            return {}

    def is_open_now(self):
        from datetime import datetime
        import pytz
        hours = self.get_hours()
        if not hours:
            return None  # No hours set
        try:
            tz = pytz.timezone('America/Montreal')
            now = datetime.now(tz)
            day_keys = ['mon','tue','wed','thu','fri','sat','sun']
            day_key = day_keys[now.weekday()]
            day = hours.get(day_key, {})
            if not day or day.get('closed'):
                return False
            open_t  = datetime.strptime(day['open'],  '%H:%M').replace(
                year=now.year, month=now.month, day=now.day, tzinfo=now.tzinfo)
            close_t = datetime.strptime(day['close'], '%H:%M').replace(
                year=now.year, month=now.month, day=now.day, tzinfo=now.tzinfo)
            return open_t <= now <= close_t
        except Exception:
            return None




class Location(db.Model):
    """Additional physical locations for a merchant (multi-branch support)."""
    __tablename__ = 'locations'

    id          = db.Column(db.Integer, primary_key=True)
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchants.id'), nullable=False)
    label_en    = db.Column(db.String(200), default='')   # e.g. "Main Store"
    label_fr    = db.Column(db.String(200), default='')   # e.g. "Magasin principal"
    address     = db.Column(db.String(300), default='')
    latitude    = db.Column(db.Float, nullable=True)
    longitude   = db.Column(db.Float, nullable=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    def label(self, lang='en'):
        if lang == 'fr' and self.label_fr:
            return self.label_fr
        return self.label_en or self.address or 'Location'

class Product(db.Model):
    __tablename__ = 'products'

    id             = db.Column(db.Integer, primary_key=True)
    merchant_id    = db.Column(db.Integer, db.ForeignKey('merchants.id'), nullable=False)
    name_en        = db.Column(db.String(200), nullable=False)
    name_fr        = db.Column(db.String(200), default='')
    description_en = db.Column(db.Text, default='')
    description_fr = db.Column(db.Text, default='')
    price            = db.Column(db.Float, nullable=True)        # None = price on request
    price_on_request = db.Column(db.Boolean, default=False)
    is_on_sale       = db.Column(db.Boolean, default=False)
    sale_price       = db.Column(db.Float, nullable=True)
     # --- Affiliate ---
    affiliate_url = db.Column(db.String(500))
    product_url   = db.Column(db.String(500))  # original source URL
    external_id   = db.Column(db.String(200))  # Shopify product ID or RSS guid
    last_seen_at  = db.Column(db.DateTime, nullable=True)  # last confirmed by sync
    category_id    = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
    product_type   = db.Column(db.String(150), nullable=True)  # raw Shopify product_type, used for grouping
    is_active      = db.Column(db.Boolean, default=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    images = db.relationship('ProductImage', backref='product', lazy=True,
                             cascade='all, delete-orphan')

    def name(self, lang='en'):
        if lang == 'fr' and self.name_fr:
            return self.name_fr
        return self.name_en

    def description(self, lang='en'):
        if lang == 'fr' and self.description_fr:
            return self.description_fr
        return self.description_en

    def display_price(self):
        if self.price_on_request or self.price is None:
            return None
        return f"${self.price:.2f}"

    @property
    def thumbnail(self):
        img = self.images[0] if self.images else None
        return img.thumbnail_url if img else ''

    @property
    def primary_image(self):
        img = self.images[0] if self.images else None
        return img.image_url if img else ''


class ProductImage(db.Model):
    __tablename__ = 'product_images'
    id            = db.Column(db.Integer, primary_key=True)
    product_id    = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    image_url     = db.Column(db.String(500), nullable=False)     # Full size on B2
    thumbnail_url = db.Column(db.String(500), nullable=False)     # Thumbnail on B2
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)




class Rating(db.Model):
    __tablename__ = 'ratings'
    id          = db.Column(db.Integer, primary_key=True)
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchants.id'), nullable=False)
    score       = db.Column(db.Integer, nullable=False)  # 1-5
    comment     = db.Column(db.String(300), default='')
    reviewer_ip = db.Column(db.String(50), default='')
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

class Message(db.Model):
    __tablename__ = 'messages'
    id          = db.Column(db.Integer, primary_key=True)
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchants.id'), nullable=False)
    sender_name = db.Column(db.String(200), nullable=False)
    sender_email= db.Column(db.String(200), nullable=False)
    body        = db.Column(db.Text, nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)


class PageView(db.Model):
    __tablename__ = 'page_views'
    id          = db.Column(db.Integer, primary_key=True)
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchants.id'), nullable=False)
    event_type  = db.Column(db.String(50), nullable=False)  # 'profile_view', 'product_view'
    product_id  = db.Column(db.Integer, nullable=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)


class Flag(db.Model):
    __tablename__ = 'flags'
    id          = db.Column(db.Integer, primary_key=True)
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchants.id'), nullable=False)
    reason      = db.Column(db.String(300), default='')
    reporter_ip = db.Column(db.String(50), default='')
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed    = db.Column(db.Boolean, default=False)
