import subprocess, textwrap, logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

FROM_ADDRESS = "Citify <welcome@citify.ca>"
LOGO_URL     = "https://citify.ca/static/img/icon-192.png"
BRAND_RED    = "#e94560"
BRAND_DARK   = "#1a1a2e"


def _send(to, subject, body_text, body_html=None):
    """Send email via sendmail. Multipart if HTML provided, plain text otherwise."""
    if body_html:
        msg = MIMEMultipart('alternative')
        msg['From']    = FROM_ADDRESS
        msg['To']      = to
        msg['Subject'] = subject
        msg.attach(MIMEText(body_text, 'plain', 'utf-8'))
        msg.attach(MIMEText(body_html, 'html', 'utf-8'))
        raw = msg.as_bytes()
    else:
        raw = (
            f"From: {FROM_ADDRESS}\nTo: {to}\nSubject: {subject}\n"
            f"Content-Type: text/plain; charset=utf-8\nMIME-Version: 1.0\n\n{body_text}"
        ).encode('utf-8')

    try:
        proc = subprocess.run(
            ["/usr/sbin/sendmail", "-t"],
            input=raw,
            capture_output=True,
        )
        if proc.returncode != 0:
            logger.error("sendmail error: %s", proc.stderr.decode())
            return False
        return True
    except Exception as e:
        logger.error("mail send exception: %s", e)
        return False


def _html_wrapper(content_html, preview_text=""):
    """Wrap content in a clean branded HTML email shell."""
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Citify</title>
</head>
<body style="margin:0;padding:0;background:#f4f4f7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <div style="display:none;max-height:0;overflow:hidden;color:#f4f4f7;">{preview_text}</div>
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f7;padding:32px 16px;">
    <tr>
      <td align="center">
        <table width="100%" cellpadding="0" cellspacing="0" style="max-width:580px;">

          <!-- Logo header -->
          <tr>
            <td align="center" style="padding-bottom:24px;">
              <a href="https://citify.ca" style="text-decoration:none;">
                <img src="{LOGO_URL}" alt="Citify" width="52" height="52"
                     style="display:block;margin:0 auto 10px;border-radius:12px;">
                <span style="font-size:22px;font-weight:700;color:{BRAND_DARK};
                             letter-spacing:-0.5px;display:block;">Citify</span>
                <span style="font-size:12px;color:#9ca3af;display:block;margin-top:2px;">
                  Montreal's Bilingual Merchant Directory
                </span>
              </a>
            </td>
          </tr>

          <!-- Card -->
          <tr>
            <td style="background:#ffffff;border-radius:12px;overflow:hidden;
                       box-shadow:0 2px 8px rgba(0,0,0,0.08);">
              {content_html}
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td align="center" style="padding:24px 0 8px;color:#9ca3af;
                                      font-size:12px;line-height:1.7;">
              <p style="margin:0;">
                <a href="https://citify.ca" style="color:{BRAND_RED};text-decoration:none;">citify.ca</a>
                &nbsp;&middot;&nbsp;
                Montr&eacute;al, Qu&eacute;bec, Canada
              </p>
              <p style="margin:6px 0 0;">
                Vous recevez ce courriel car votre commerce figure dans des r&eacute;pertoires publics.<br>
                You received this because your business appears in public directories.<br>
                Pour retirer votre fiche / To remove your listing:
                <a href="mailto:hello@citify.ca"
                   style="color:{BRAND_RED};text-decoration:none;">hello@citify.ca</a>
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def send_seed_welcome_email(merchant, claim_link, to_email=None):
    name  = merchant.business_name
    email = to_email or merchant.email

    subject      = f"{name} est sur Citify ! / Your {name} listing is live!"
    preview_text = (f"Réclamez votre fiche gratuite pour {name} · "
                    f"Claim your free listing for {name} on Citify.")

    features = [
        (
            "Modifiez votre description, adresse et horaires",
            "Edit your description, address &amp; hours"
        ),
        (
            "Ajoutez vos photos et produits",
            "Upload photos and showcase your products"
        ),
        (
            "Synchronisez automatiquement vos produits Shopify ou RSS",
            "Auto-sync your products from Shopify or RSS"
        ),
        (
            "Affichez une promotion ou un coupon sur votre profil public",
            "Show a promotion or coupon on your public profile"
        ),
        (
            "Recueillez des avis et &eacute;valuations de vos clients",
            "Collect customer ratings &amp; reviews"
        ),
        (
            "G&eacute;rez plusieurs adresses et succursales",
            "Manage multiple locations &amp; branches"
        ),
        (
            "Indiquez vos options de livraison",
            "Add your delivery options &amp; order links"
        ),
        (
            "Consultez vos statistiques de visites",
            "See who's viewing your profile (analytics)"
        ),
        (
            "Kit marketing gratuit : codes QR, bannières sociales, carte d'affaires",
            "Free marketing kit: QR codes, social banners, business card"
        ),
        (
            "<strong>Mettez votre commerce en vedette</strong> pour plus de visibilit&eacute;",
            "<strong>Boost your visibility</strong> with a Featured Listing"
        ),
    ]

    features_html = ''.join(f"""
        <tr>
          <td width="22" style="vertical-align:top;padding-bottom:12px;">
            <span style="color:{BRAND_RED};font-size:15px;font-weight:bold;">&#10003;</span>
          </td>
          <td style="padding-bottom:12px;">
            <span style="font-size:14px;color:{BRAND_DARK};line-height:1.4;">{fr}</span><br>
            <span style="font-size:13px;color:#6b7280;line-height:1.4;font-style:italic;">{en}</span>
          </td>
        </tr>""" for fr, en in features)

    content_html = f"""
      <!-- Red accent bar -->
      <div style="height:5px;background:linear-gradient(90deg,{BRAND_RED},{BRAND_RED}cc);"></div>

      <div style="padding:36px 40px;">

        <!-- Bilingual headline -->
        <h1 style="margin:0 0 4px;font-size:22px;font-weight:700;color:{BRAND_DARK};line-height:1.3;">
          Votre fiche est en ligne&nbsp;! &#127881;
        </h1>
        <h2 style="margin:0 0 24px;font-size:16px;font-weight:400;color:#6b7280;line-height:1.3;">
          Your listing is live on Citify!
        </h2>

        <!-- FR intro -->
        <p style="margin:0 0 12px;font-size:15px;color:#374151;line-height:1.7;
                  padding-left:12px;border-left:3px solid {BRAND_RED};">
          Nous avons cr&eacute;&eacute; une <strong>fiche gratuite</strong> pour
          <strong style="color:{BRAND_DARK};">{name}</strong> sur
          <a href="https://citify.ca" style="color:{BRAND_RED};text-decoration:none;">citify.ca</a>,
          l'annuaire bilingue des commer&ccedil;ants montr&eacute;alais.
          Votre fiche est d&eacute;j&agrave; visible par les clients qui cherchent
          en fran&ccedil;ais et en anglais.
        </p>

        <!-- EN intro -->
        <p style="margin:0 0 28px;font-size:15px;color:#374151;line-height:1.7;
                  padding-left:12px;border-left:3px solid #e2e8f0;">
          We've created a <strong>free listing</strong> for
          <strong style="color:{BRAND_DARK};">{name}</strong> on
          <a href="https://citify.ca" style="color:{BRAND_RED};text-decoration:none;">citify.ca</a>
          &mdash; Montreal's bilingual local merchant directory.
          Your listing is already visible to shoppers searching in both languages.
        </p>

        <!-- CTA button -->
        <table cellpadding="0" cellspacing="0" width="100%" style="margin-bottom:12px;">
          <tr>
            <td align="center" style="background:{BRAND_RED};border-radius:8px;">
              <a href="{claim_link}"
                 style="display:block;padding:16px 36px;font-size:16px;font-weight:700;
                        color:#ffffff;text-decoration:none;text-align:center;">
                R&eacute;clamer ma fiche gratuite &nbsp;/&nbsp; Claim my free listing &rarr;
              </a>
            </td>
          </tr>
        </table>

        <p style="margin:0 0 6px;font-size:12px;color:#9ca3af;text-align:center;">
          Ce lien expire dans 48&nbsp;heures &nbsp;&middot;&nbsp; This link expires in 48 hours
        </p>
        <p style="margin:0 0 28px;font-size:11px;word-break:break-all;text-align:center;">
          <a href="{claim_link}" style="color:{BRAND_RED};">{claim_link}</a>
        </p>

        <!-- Features -->
        <div style="background:#f9fafb;border-radius:8px;padding:22px 26px;margin-bottom:8px;">
          <p style="margin:0 0 16px;font-size:12px;font-weight:700;color:{BRAND_DARK};
                    text-transform:uppercase;letter-spacing:0.7px;">
            Une fois votre fiche r&eacute;clam&eacute;e&nbsp;/ Once you claim your listing:
          </p>
          <table cellpadding="0" cellspacing="0" width="100%">
            {features_html}
          </table>
        </div>

      </div>
    """

    html = _html_wrapper(content_html, preview_text)

    text = textwrap.dedent(f"""\
        Votre fiche {name} est en ligne sur Citify !
        Your {name} listing is live on Citify!

        FR: Nous avons cree une fiche gratuite pour {name} sur citify.ca,
        l'annuaire bilingue des commercants montrealais.

        EN: We've created a free listing for {name} on citify.ca,
        Montreal's bilingual merchant directory.

        RECLAMEZ VOTRE FICHE / CLAIM YOUR LISTING (48h):
        {claim_link}

        Une fois reclamee, vous pouvez / Once claimed, you can:
          - Modifier description, adresse et horaires
            / Edit description, address & hours
          - Ajouter photos et produits / Upload photos and products
          - Indiquer vos options de livraison / Add delivery options
          - Consulter vos statistiques / View analytics
          - Repondre aux messages clients / Respond to messages
          - Mettre en vedette votre commerce / Feature your listing

        Questions: hello@citify.ca
        — Citify · citify.ca · Montreal, Quebec
    """)

    return _send(email, subject, text, body_html=html)


def send_claim_verification_email(merchant, verify_link):
    name    = merchant.business_name
    subject = f"Verifiez votre fiche {name} sur Citify / Verify your {name} listing"

    content_html = f"""
      <div style="height:5px;background:linear-gradient(90deg,{BRAND_RED},{BRAND_RED}cc);"></div>
      <div style="padding:36px 40px;">

        <h1 style="margin:0 0 20px;font-size:20px;font-weight:700;color:{BRAND_DARK};">
          V&eacute;rifiez votre demande&nbsp;/<br>
          <span style="font-weight:400;font-size:16px;color:#6b7280;">
            Verify your listing claim
          </span>
        </h1>

        <p style="margin:0 0 12px;font-size:15px;color:#374151;line-height:1.7;
                  padding-left:12px;border-left:3px solid {BRAND_RED};">
          Une demande de r&eacute;clamation a &eacute;t&eacute; soumise pour la fiche
          <strong>{name}</strong> sur Citify.
          Si c'est vous, cliquez sur le bouton ci-dessous pour v&eacute;rifier.
        </p>

        <p style="margin:0 0 24px;font-size:15px;color:#374151;line-height:1.7;
                  padding-left:12px;border-left:3px solid #e2e8f0;">
          Someone requested to claim the Citify listing for <strong>{name}</strong>.
          If that was you, click below to verify your ownership.
        </p>

        <table cellpadding="0" cellspacing="0" width="100%" style="margin-bottom:20px;">
          <tr>
            <td align="center" style="background:{BRAND_RED};border-radius:8px;">
              <a href="{verify_link}"
                 style="display:block;padding:15px 32px;font-size:15px;font-weight:700;
                        color:#ffffff;text-decoration:none;text-align:center;">
                V&eacute;rifier ma fiche&nbsp;/&nbsp;Verify my listing &rarr;
              </a>
            </td>
          </tr>
        </table>

        <p style="margin:0 0 6px;font-size:12px;color:#9ca3af;text-align:center;">
          Lien valide 48h &middot; Link valid for 48 hours
        </p>
        <p style="margin:0 0 24px;font-size:11px;word-break:break-all;text-align:center;">
          <a href="{verify_link}" style="color:{BRAND_RED};">{verify_link}</a>
        </p>

        <div style="border-top:1px solid #f3f4f6;padding-top:16px;">
          <p style="margin:0;font-size:13px;color:#9ca3af;line-height:1.6;">
            Si vous n'avez pas fait cette demande, ignorez ce courriel.<br>
            If you did not request this, you can safely ignore this email.
          </p>
        </div>
      </div>
    """

    html = _html_wrapper(content_html, f"Verifiez votre fiche {name} sur Citify")

    text = textwrap.dedent(f"""\
        Verifiez votre demande pour {name} sur Citify.
        Verify your claim for {name} on Citify.

        FR: Cliquez sur le lien ci-dessous pour verifier votre fiche.
        EN: Click the link below to verify your listing ownership.

        {verify_link}

        Valide 48h / Valid for 48 hours.
        Si vous n'avez pas fait cette demande, ignorez ce courriel.
        If you did not request this, ignore this email.

        — Citify · citify.ca
    """)

    return _send(merchant.email, subject, text, body_html=html)
