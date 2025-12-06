import random
import string
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app


def generate_verification_code():
    """Generate a 6-digit random verification code"""
    return ''.join(random.choices(string.digits, k=6))


def send_verification_email(email, verification_code, username="User"):
    """Send verification email with 6-digit code"""
    try:
        # Get email config
        mail_server = current_app.config.get('MAIL_SERVER')
        mail_port = current_app.config.get('MAIL_PORT')
        mail_username = current_app.config.get('MAIL_USERNAME')
        mail_password = current_app.config.get('MAIL_PASSWORD')
        mail_from = current_app.config.get('MAIL_FROM_EMAIL')

        if not mail_username or not mail_password:
            print(f"⚠️  Email not configured.  Code: {verification_code}")
            return False

        # Create HTML email
        subject = "MyNet - Email Verification Code"
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; background-color: #f5f5f5; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px;">
                    <h2 style="color: #333; text-align: center;">Welcome to MyNet</h2>
                    <p style="color: #666; font-size: 16px;">Hello {username},</p>
                    <p style="color: #666; font-size: 16px;">You want to register a new account on MyNet.  Here is your verification code:</p>

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

        # Create message
        message = MIMEMultipart('alternative')
        message['Subject'] = subject
        message['From'] = mail_from
        message['To'] = email
        message.attach(MIMEText(html_body, 'html'))

        # Send email
        with smtplib.SMTP(mail_server, mail_port) as server:
            server.starttls()
            server.login(mail_username, mail_password)
            server.send_message(message)

        print(f"✅ Verification email sent to {email}")
        return True

    except Exception as e:
        print(f"❌ Error sending email: {str(e)}")
        return False