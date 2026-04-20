import logging
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_verification_email(email: str, first_name: str, verification_url: str) -> bool:
    """Send email verification email via Resend API.

    Returns True on success, False on failure. Silently fails if API key not configured.
    """
    if not settings.resend_api_key:
        logger.warning("Resend API key not configured - skipping verification email")
        return False

    name = first_name or "there"
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #0a0a0a; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #0a0a0a; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 480px; background-color: #111111; border: 1px solid #222222;">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 32px 32px 24px; border-bottom: 1px solid #222222;">
                            <span style="font-size: 20px; font-weight: 600; color: #ffffff; letter-spacing: -0.5px;">Perigee</span>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 32px;">
                            <h1 style="margin: 0 0 16px; font-size: 24px; font-weight: 600; color: #ffffff;">
                                Verify your email
                            </h1>
                            <p style="margin: 0 0 24px; font-size: 15px; line-height: 1.6; color: #888888;">
                                Hi {name}, welcome to Perigee! Click the button below to verify your email address and get started.
                            </p>
                            <a href="{verification_url}" style="display: inline-block; padding: 14px 28px; background-color: #4F46E5; color: #ffffff; text-decoration: none; font-size: 14px; font-weight: 600; border-radius: 6px;">
                                Verify Email
                            </a>
                            <p style="margin: 24px 0 0; font-size: 13px; color: #666666;">
                                This link expires in 24 hours. If you didn't create an account, you can safely ignore this email.
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 24px 32px; border-top: 1px solid #222222;">
                            <p style="margin: 0; font-size: 12px; color: #666666;">
                                &copy; Perigee. All rights reserved.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {settings.resend_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": f"{settings.resend_from_name} <{settings.resend_from_email}>",
                    "to": [email],
                    "subject": "Verify your Perigee email",
                    "html": html_content,
                },
            )
            if response.status_code >= 400:
                logger.error(f"Resend API error: {response.status_code} - {response.text}")
                return False
            return True
    except Exception as e:
        logger.error(f"Failed to send verification email: {e}")
        return False


async def send_password_reset_email(email: str, first_name: str, reset_url: str) -> bool:
    """Send password reset email via Resend API.

    Returns True on success, False on failure. Silently fails if API key not configured.
    """
    if not settings.resend_api_key:
        logger.warning("Resend API key not configured - skipping password reset email")
        return False

    name = first_name or "there"
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #0a0a0a; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #0a0a0a; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 480px; background-color: #111111; border: 1px solid #222222;">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 32px 32px 24px; border-bottom: 1px solid #222222;">
                            <span style="font-size: 20px; font-weight: 600; color: #ffffff; letter-spacing: -0.5px;">Perigee</span>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 32px;">
                            <h1 style="margin: 0 0 16px; font-size: 24px; font-weight: 600; color: #ffffff;">
                                Reset your password
                            </h1>
                            <p style="margin: 0 0 24px; font-size: 15px; line-height: 1.6; color: #888888;">
                                Hi {name}, we received a request to reset your password. Click the button below to choose a new password.
                            </p>
                            <a href="{reset_url}" style="display: inline-block; padding: 14px 28px; background-color: #4F46E5; color: #ffffff; text-decoration: none; font-size: 14px; font-weight: 600; border-radius: 6px;">
                                Reset Password
                            </a>
                            <p style="margin: 24px 0 0; font-size: 13px; color: #666666;">
                                This link expires in 1 hour. If you didn't request a password reset, you can safely ignore this email.
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 24px 32px; border-top: 1px solid #222222;">
                            <p style="margin: 0; font-size: 12px; color: #666666;">
                                &copy; Perigee. All rights reserved.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {settings.resend_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": f"{settings.resend_from_name} <{settings.resend_from_email}>",
                    "to": [email],
                    "subject": "Reset your Perigee password",
                    "html": html_content,
                },
            )
            if response.status_code >= 400:
                logger.error(f"Resend API error: {response.status_code} - {response.text}")
                return False
            return True
    except Exception as e:
        logger.error(f"Failed to send password reset email: {e}")
        return False
