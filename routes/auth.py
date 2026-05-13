from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import Merchant
from app import db, limiter
from utils.lang import get_lang
from utils.geocode import geocode
from utils.sanitise import clean_text
import re

auth_bp = Blueprint('auth', __name__)


def make_slug(name):
    slug = name.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_-]+', '-', slug)
    slug = slug.strip('-')
    base = slug
    i = 1
    while Merchant.query.filter_by(slug=slug).first():
        slug = f"{base}-{i}"
        i += 1
    return slug


@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per hour")
def register():
    lang = get_lang()
    if current_user.is_authenticated:
        return redirect(url_for('merchant.dashboard'))

    if request.method == 'POST':
        email         = clean_text(request.form.get('email', '')).lower()
        password      = request.form.get('password', '')
        business_name = clean_text(request.form.get('business_name', ''))
        address       = clean_text(request.form.get('address', ''))
        neighbourhood = clean_text(request.form.get('neighbourhood', ''))
        neq           = clean_text(request.form.get('neq', ''))

        errors = []
        if not email or '@' not in email:
            errors.append('Valid email required.' if lang == 'en' else 'Courriel valide requis.')
        if len(password) < 8:
            errors.append('Password must be at least 8 characters.' if lang == 'en'
                          else 'Le mot de passe doit comporter au moins 8 caracteres.')
        if not business_name:
            errors.append('Business name required.' if lang == 'en'
                          else 'Nom de commerce requis.')
        if Merchant.query.filter_by(email=email).first():
            errors.append('Email already registered.' if lang == 'en'
                          else 'Courriel deja enregistre.')

        if errors:
            return render_template('auth/register.html', errors=errors,
                                   lang=lang, form=request.form)

        slug = make_slug(business_name)
        lat, lon = geocode(address) if address else (None, None)

        merchant = Merchant(
            email=email,
            business_name=business_name,
            slug=slug,
            address=address,
            neighbourhood=neighbourhood,
            neq=neq,
            latitude=lat,
            longitude=lon,
            is_verified=bool(neq),
        )
        merchant.set_password(password)
        db.session.add(merchant)
        db.session.commit()

        login_user(merchant)
        flash('Welcome to Citify! / Bienvenue sur Citify!', 'success')
        return redirect(url_for('merchant.dashboard'))

    return render_template('auth/register.html', lang=lang, errors=[], form={})


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    lang = get_lang()
    if current_user.is_authenticated:
        return redirect(url_for('merchant.dashboard'))

    if request.method == 'POST':
        email    = clean_text(request.form.get('email', '')).lower()
        password = request.form.get('password', '')
        merchant = Merchant.query.filter_by(email=email).first()

        if merchant and merchant.check_password(password) and merchant.is_active:
            login_user(merchant, remember=True)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('merchant.dashboard'))

        error = ('Invalid email or password.' if lang == 'en'
                 else 'Courriel ou mot de passe invalide.')
        return render_template('auth/login.html', error=error, lang=lang)

    return render_template('auth/login.html', error=None, lang=lang)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('public.index'))
