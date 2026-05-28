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
    # Status
    is_active        = db.Column(db.Boolean, default=True)
    is_admin         = db.Column(db.Boolean, default=False)
    is_verified      = db.Column(db.Boolean, default=False)   # NEQ verified badge
    flag_count       = db.Column(db.Integer, default=0)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    # Logo/banner
    logo_url         = db.Column(db.String(500), default='')
    banner_url       = db.Column(db.String(500), default='')

    products = db.relationship('Product', backref='merchant', lazy=True,
                               cascade='all, delete-orphan')
    flags    = db.relationship('Flag', backref='merchant', lazy=True,
                               cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def has_neq(self):
        return bool(self.neq and self.neq.strip())

    def description(self, lang='en'):
        return self.description_fr if lang == 'fr' else self.description_en

    def product_count(self):
        return Product.query.filter_by(merchant_id=self.id, is_active=True).count()


class Product(db.Model):
    __tablename__ = 'products'

    id             = db.Column(db.Integer, primary_key=True)
    merchant_id    = db.Column(db.Integer, db.ForeignKey('merchants.id'), nullable=False)
    name_en        = db.Column(db.String(200), nullable=False)
    name_fr        = db.Column(db.String(200), default='')
    description_en = db.Column(db.Text, default='')
    description_fr = db.Column(db.Text, default='')
    price          = db.Column(db.Float, nullable=True)          # None = price on request
    price_on_request = db.Column(db.Boolean, default=False)
    category_id    = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
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
        img = ProductImage.query.filter_by(product_id=self.id).first()
        return img.thumbnail_url if img else ''

    @property
    def primary_image(self):
        img = ProductImage.query.filter_by(product_id=self.id).first()
        return img.image_url if img else ''


class ProductImage(db.Model):
    __tablename__ = 'product_images'
    id            = db.Column(db.Integer, primary_key=True)
    product_id    = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    image_url     = db.Column(db.String(500), nullable=False)     # Full size on B2
    thumbnail_url = db.Column(db.String(500), nullable=False)     # Thumbnail on B2
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)


class Flag(db.Model):
    __tablename__ = 'flags'
    id          = db.Column(db.Integer, primary_key=True)
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchants.id'), nullable=False)
    reason      = db.Column(db.String(300), default='')
    reporter_ip = db.Column(db.String(50), default='')
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed    = db.Column(db.Boolean, default=False)
