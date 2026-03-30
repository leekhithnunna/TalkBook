import smtplib, sys, os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config.config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, EMAIL_FROM, APP_NAME


def _get_smtp_config() -> dict:
    """Get SMTP config — DB settings override env vars."""
    try:
        from db.database import get_smtp_settings
        db = get_smtp_settings()
        return {
            "host":     db.get("smtp_host",     SMTP_HOST),
            "port":     int(db.get("smtp_port", SMTP_PORT)),
            "user":     db.get("smtp_user",     SMTP_USER),
            "password": db.get("smtp_password", SMTP_PASSWORD),
        }
    except Exception:
        return {"host": SMTP_HOST, "port": SMTP_PORT, "user": SMTP_USER, "password": SMTP_PASSWORD}


def send_confirmation_email(to_email: str, name: str, booking_ref: str,
                             booking_type: str, booking_date: str, booking_time: str) -> tuple[bool, str]:
    """Send booking confirmation. Returns (success, error_message)."""
    cfg = _get_smtp_config()
    if not cfg["user"] or not cfg["password"]:
        return False, "SMTP not configured. Go to Settings → Email to set up."

    subject = f"[{APP_NAME}] Booking Confirmed – {booking_ref}"
    body = (
        f"Hi {name},\n\n"
        f"Your booking has been confirmed on {APP_NAME}.\n\n"
        f"  Booking ID : {booking_ref}\n"
        f"  Type       : {booking_type}\n"
        f"  Date       : {booking_date}\n"
        f"  Time       : {booking_time}\n\n"
        f"Thank you for using {APP_NAME}!\n"
        f"Talk. Book. Done.\n"
    )
    msg = MIMEMultipart()
    msg["From"]    = cfg["user"]
    msg["To"]      = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=10) as server:
            server.starttls()
            server.login(cfg["user"], cfg["password"])
            server.sendmail(cfg["user"], to_email, msg.as_string())
        return True, ""
    except smtplib.SMTPAuthenticationError:
        return False, "SMTP authentication failed. Check your email/password in Settings."
    except smtplib.SMTPException as e:
        return False, f"SMTP error: {str(e)}"
    except Exception as e:
        return False, f"Email failed: {str(e)}"
