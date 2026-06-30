from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
import secrets
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


@auth_bp.route('/claim/<slug>', methods=['GET', 'POST'])
@limiter.limit("5 per hour")
def claim_request(slug):
    lang     = get_lang()
    merchant = Merchant.query.filter_by(slug=slug, is_active=True, is_claimed=False).first_or_404()

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        if not email or '@' not in email:
            flash('Valid email required.' if lang == 'en' else 'Courriel valide requis.', 'error')
            return redirect(url_for('auth.claim_request', slug=slug))

        # Generate token
        token = secrets.token_urlsafe(32)
        merchant.claim_token         = token
        merchant.claim_token_expires = datetime.utcnow() + timedelta(hours=24)
        db.session.commit()

        # Send verification email via smtp2go
        from utils.mail import _send
        verify_url = url_for('auth.claim_verify', slug=slug, token=token, _external=True)
        subject    = f"Claim your Citify listing — {merchant.business_name}"
        body_text  = (
            f"Hello,\n\n"
            f"You requested to claim the following business listing on Citify:\n\n"
            f"  {merchant.business_name}\n"
            f"  {merchant.address or ''}\n\n"
            f"Click the link below to verify your ownership and set your password:\n\n"
            f"  {verify_url}\n\n"
            f"This link expires in 24 hours.\n\n"
            f"If you did not request this, please ignore this email.\n\n"
            f"— Citify Montreal\n"
            f"https://citify.ca"
        )
        body_html = f"""
        <div style="font-family:sans-serif;max-width:600px;margin:0 auto;">
          <h2 style="color:#e94560;">Claim Your Citify Listing</h2>
          <p>You requested to claim the following business listing:</p>
          <p><strong>{merchant.business_name}</strong><br>
          {merchant.address or ''}</p>
          <p>Click the button below to verify your ownership and set your password:</p>
          <p style="margin:24px 0;">
            <a href="{verify_url}"
               style="background:#e94560;color:#fff;padding:12px 24px;border-radius:6px;
                      text-decoration:none;font-weight:600;">
              Claim My Listing
            </a>
          </p>
          <p style="font-size:13px;color:#9ca3af;">
            This link expires in 24 hours. If you did not request this, ignore this email.
          </p>
        </div>"""
        try:
            _send(to=email, subject=subject, body_text=body_text, body_html=body_html)
        except Exception:
            pass

        flash('Verification email sent! Check your inbox. / Courriel envoyé! Vérifiez votre boîte.', 'success')
        return redirect(url_for('public.merchant_profile', slug=slug))

    return render_template('auth/claim_request.html', merchant=merchant, lang=lang)


@auth_bp.route('/claim/<slug>/verify/<token>', methods=['GET', 'POST'])
def claim_verify(slug, token):
    lang     = get_lang()
    merchant = Merchant.query.filter_by(slug=slug, is_active=True, is_claimed=False).first_or_404()

    if (not merchant.claim_token or
        merchant.claim_token != token or
        not merchant.claim_token_expires or
        datetime.utcnow() > merchant.claim_token_expires):
        flash('This link has expired or is invalid. / Ce lien a expiré.', 'error')
        return redirect(url_for('public.merchant_profile', slug=slug))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')

        errors = []
        if not email or '@' not in email:
            errors.append('Valid email required.')
        if Merchant.query.filter(Merchant.email == email, Merchant.id != merchant.id).first():
            errors.append('Email already in use.')
        if len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if password != confirm:
            errors.append('Passwords do not match.')

        if errors:
            return render_template('auth/claim_verify.html',
                                   merchant=merchant, token=token, errors=errors, lang=lang)

        merchant.email               = email
        merchant.is_claimed          = True
        merchant.claim_token         = None
        merchant.claim_token_expires = None
        merchant.auto_sync           = False
        merchant.set_password(password)
        db.session.commit()

        login_user(merchant)
        flash('Listing claimed! Welcome to Citify. / Fiche revendiquée! Bienvenue sur Citify.', 'success')
        return redirect(url_for('merchant.dashboard'))

    return render_template('auth/claim_verify.html',
                           merchant=merchant, token=token, errors=[], lang=lang)

