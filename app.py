from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_caching import Cache
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
import os

db = SQLAlchemy()
login_manager = LoginManager()
cache = Cache()
csrf = CSRFProtect()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=os.environ.get("RATELIMIT_STORAGE_URI", "memory://"),
)
talisman = Talisman()


def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-this-in-production')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///citify.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['CACHE_TYPE'] = 'SimpleCache'
    app.config['CACHE_DEFAULT_TIMEOUT'] = 300

    # Backblaze B2 config (set via environment variables on server)
    app.config['B2_KEY_ID']       = os.environ.get('B2_KEY_ID', '')
    app.config['B2_APP_KEY']      = os.environ.get('B2_APP_KEY', '')
    app.config['B2_BUCKET_NAME']  = os.environ.get('B2_BUCKET_NAME', 'citify-images')
    app.config['B2_ENDPOINT_URL'] = os.environ.get('B2_ENDPOINT_URL', '')

    # Max image upload size: 8MB
    app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024

    # Secure session cookies
    app.config['SESSION_COOKIE_SECURE']      = True
    app.config['SESSION_COOKIE_HTTPONLY']    = True
    app.config['SESSION_COOKIE_SAMESITE']    = 'Lax'
    app.config['PERMANENT_SESSION_LIFETIME'] = 86400 * 14  # 14 days

    # Content Security Policy
    csp = {
        'default-src': ["'self'"],
        'script-src':  ["'self'", 'cdn.jsdelivr.net', 'unpkg.com'],
        'style-src':   ["'self'", "'unsafe-inline'", 'cdn.jsdelivr.net',
                        'fonts.googleapis.com', 'unpkg.com'],
        'font-src':    ["'self'", 'fonts.gstatic.com', 'fonts.googleapis.com'],
        'img-src':     ["'self'", 'data:', '*.backblazeb2.com',
                        '*.tile.openstreetmap.org', 'unpkg.com'],
        'connect-src': ["'self'"],
        'frame-src':   ["'none'"],
        'object-src':  ["'none'"],
    }

    db.init_app(app)
    login_manager.init_app(app)
    cache.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    talisman.init_app(
        app,
        content_security_policy=csp,
        force_https=False,
        strict_transport_security=True,
        strict_transport_security_max_age=31536000,
        frame_options='DENY',
        referrer_policy='strict-origin-when-cross-origin',
    )

    login_manager.login_view = 'auth.login'
    login_manager.login_message_fr = 'Veuillez vous connecter pour acceder a cette page.'
    login_manager.login_message_en = 'Please log in to access this page.'

    from routes.public   import public_bp
    from routes.auth     import auth_bp
    from routes.merchant import merchant_bp
    from routes.admin    import admin_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp,     url_prefix='/auth')
    app.register_blueprint(merchant_bp, url_prefix='/merchant')
    app.register_blueprint(admin_bp,    url_prefix='/admin')


    # Inject categories into every template globally
    @app.context_processor
    def inject_globals():
        from models import Category
        from utils.lang import get_lang
        from flask_login import current_user
        try:
            cats = Category.query.all()
        except Exception:
            cats = []
        return dict(categories=cats, lang=get_lang(), current_user=current_user)

    # Custom error pages
    @app.errorhandler(400)
    def bad_request(e):
        return render_template('errors/400.html'), 400

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(429)
    def too_many_requests(e):
        return render_template('errors/429.html'), 429

    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html'), 500

    with app.app_context():
        db.create_all()
        seed_categories()

    return app



def invalidate_public_cache():
    """Call this after any merchant/product change to clear cached pages."""
    try:
        cache.clear()
    except Exception:
        pass

def seed_categories():
    from models import Category, Subcategory
    if Category.query.first():
        return

    categories = [
        ("Food & Drink", "Alimentation & Boissons", [
            ("Restaurants & Cafes", "Restaurants & Cafes"),
            ("Bakeries & Pastry", "Boulangeries & Patisseries"),
            ("Grocery & Specialty Food", "Epiceries & Alimentation specialisee"),
            ("Catering", "Traiteurs"),
            ("Food Trucks", "Camions-repas"),
        ]),
        ("Retail & Shopping", "Commerce & Magasins", [
            ("Clothing & Accessories", "Vetements & Accessoires"),
            ("Books & Stationery", "Livres & Papeterie"),
            ("Electronics & Tech", "Electronique & Tech"),
            ("Home & Garden", "Maison & Jardin"),
            ("Gifts & Crafts", "Cadeaux & Artisanat"),
            ("Vintage & Secondhand", "Vintage & Seconde main"),
            ("Jewellery", "Bijouterie"),
        ]),
        ("Health & Beauty", "Sante & Beaute", [
            ("Hair & Beauty Salons", "Salons de coiffure & beaute"),
            ("Spas & Wellness", "Spas & Bien-etre"),
            ("Pharmacies & Health", "Pharmacies & Sante"),
            ("Fitness & Sports", "Fitness & Sports"),
        ]),
        ("Home & Professional Services", "Services a domicile & Professionnels", [
            ("Contractors & Renovation", "Entrepreneurs & Renovation"),
            ("Cleaning Services", "Services de nettoyage"),
            ("Plumbing & Electrical", "Plomberie & Electricite"),
            ("Tutoring & Education", "Tutorat & Education"),
            ("Legal & Financial", "Services juridiques & Financiers"),
            ("Accounting", "Comptabilite"),
        ]),
        ("Arts & Culture", "Arts & Culture", [
            ("Art Galleries", "Galeries d-art"),
            ("Music & Entertainment", "Musique & Divertissement"),
            ("Photography", "Photographie"),
            ("Printing & Design", "Impression & Design"),
        ]),
        ("Automotive", "Automobile", [
            ("Repair & Maintenance", "Reparation & Entretien"),
            ("Parts & Accessories", "Pieces & Accessoires"),
        ]),
        ("Children & Family", "Enfants & Famille", [
            ("Childcare & Daycare", "Garde d-enfants & Garderies"),
            ("Toys & Games", "Jouets & Jeux"),
            ("Childrens Clothing", "Vetements enfants"),
        ]),
        ("Pets", "Animaux", [
            ("Veterinary", "Veterinaire"),
            ("Grooming", "Toilettage"),
            ("Pet Supplies", "Accessoires animaux"),
        ]),
        ("Technology", "Technologie", [
            ("IT Services", "Services informatiques"),
            ("Phone Repair", "Reparation de telephones"),
            ("Web & Design Services", "Services web & Design"),
        ]),
        ("Other", "Autre", [
            ("Other", "Autre"),
        ]),
    ]

    for cat_en, cat_fr, subs in categories:
        cat = Category(
            name_en=cat_en, name_fr=cat_fr,
            slug=cat_en.lower().replace(' & ', '-').replace(' ', '-').replace("'", '')
        )
        db.session.add(cat)
        db.session.flush()
        for sub_en, sub_fr in subs:
            sub = Subcategory(
                name_en=sub_en, name_fr=sub_fr,
                slug=sub_en.lower().replace(' & ', '-').replace(' ', '-').replace("'", ''),
                category_id=cat.id
            )
            db.session.add(sub)

    db.session.commit()


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
