import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import user_repository

from app.utils.security import (
    generate_totp_secret,
    get_totp_uri,
    verify_totp,
    generate_qr_code,
)
from app.utils.config import settings


async def setup_totp(db: AsyncSession, user_id: UUID) -> tuple[str | None, str | None, str | None]:
    """
    Generates a new TOTP secret, saves it, and creates a QR code.
    Returns (secret, qr_code, error_message).
    """
    user = await user_repository.get_by_id(db, user_id)
    if not user:
        return None, None, 'User not found. The account may have been deleted'

    secret = generate_totp_secret()
    
    await user_repository.save_user_totp_setup(db, user, secret)

    uri = get_totp_uri(user.username, secret)
    qr_code = generate_qr_code(uri)

    return secret, qr_code, None


async def enable_totp(db: AsyncSession, user_id: UUID, token: str) -> str | None:
    """
    Verifies the token and enables 2FA for the user.
    Returns error_message or None on success.
    """
    user = await user_repository.get_by_id(db, user_id)

    if not user:
        return 'User not found. The account may have been deleted'
    
    if not user.totp_secret:
        return 'Please complete the 2FA setup first by scanning the QR code'

    if verify_totp(user.totp_secret, token):
        await user_repository.enable_user_totp(db, user)
        return None
    else:
        return 'The verification code is invalid or has expired. Please try a new code from your authenticator app'


async def disable_totp(db: AsyncSession, user_id: UUID, token: str) -> str | None:
    """
    Verifies the token and disables 2FA for the user.
    Returns error_message or None on success.
    """
    user = await user_repository.get_by_id(db, user_id)

    if not user:
        return 'User not found. The account may have been deleted'
    
    if not user.totp_enabled:
        return '2FA is not currently enabled on your account'
    
    if not user.totp_secret:
        return '2FA configuration is missing. Please contact support'
            
    if verify_totp(user.totp_secret, token):
        await user_repository.disable_user_totp(db, user)
        return None
    else:
        return 'The verification code is invalid or has expired. Please try a new code from your authenticator app'


async def send_verification_email_async(
    email: str,
    verification_code: str,
    username: str = "User"
) -> bool:
    """Send verification email with 6-digit code asynchronously"""
    try:
        mail_server = settings.MAIL_SERVER
        mail_port = settings.MAIL_PORT
        mail_username = settings.MAIL_USERNAME
        mail_password = settings.MAIL_PASSWORD
        mail_from = settings.MAIL_FROM_EMAIL

        if not mail_username or not mail_password:
            print(f"⚠️ Email not configured. Code: {verification_code}")
            return False

        subject = "MyNet - Email Verification Code"
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; background-color: #f5f5f5; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px;">
                    <h2 style="color: #333; text-align: center;">Welcome to MyNet</h2>
                    <p style="color: #666; font-size: 16px;">Hello {username},</p>
                    <p style="color: #666; font-size: 16px;">You want to register a new account on MyNet. Here is your verification code:</p>
                    <div style="background-color: #f0f0f0; padding: 20px; border-radius: 5px; text-align: center; margin: 20px 0;">
                        <p style="font-size: 32px; font-weight: bold; color: #0066cc; letter-spacing: 5px; margin: 0;">
                            {verification_code}
                        </p>
                    </div>
                    <p style="color: #666; font-size: 16px;">Write it inside the verification field to activate your new account.</p>
                    <p style="color: #999; font-size: 14px;">This code expires in 15 minutes.</p>
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                    <p style="color: #999; font-size: 12px; text-align: center;">
                        If you didn't request this, please ignore this email.
                    </p>
                </div>
            </body>
        </html>
        """

        message = MIMEMultipart('alternative')
        message['Subject'] = subject
        message['From'] = mail_from
        message['To'] = email
        message.attach(MIMEText(html_body, 'html'))

        await aiosmtplib.send(
            message,
            hostname=mail_server,
            port=mail_port,
            username=mail_username,
            password=mail_password,
            start_tls=True,
        )

        print(f"✅ Verification email sent to {email}")
        return True

    except Exception as e:
        print(f"❌ Error sending email: {str(e)}")
        return False
