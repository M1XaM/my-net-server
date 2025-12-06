import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_email(to_email, subject, html_content, text_content=None):
    """
    Send an email using SMTP configuration from app config
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        html_content: HTML content of the email
        text_content: Plain text content (optional, defaults to stripped HTML)
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        smtp_host = current_app.config.get('SMTP_HOST')
        smtp_port = current_app.config.get('SMTP_PORT')
        smtp_username = current_app.config.get('SMTP_USERNAME')
        smtp_password = current_app.config.get('SMTP_PASSWORD')
        from_email = current_app.config.get('SMTP_FROM_EMAIL')
        from_name = current_app.config.get('SMTP_FROM_NAME', 'MyNet')
        
        # Check if SMTP is configured
        if not all([smtp_host, smtp_port, smtp_username, smtp_password, from_email]):
            logger.warning("SMTP not fully configured. Email will not be sent.")
            logger.info(f"Would send email to {to_email} with subject: {subject}")
            return True  # Return True in development mode
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{from_name} <{from_email}>" if from_name else from_email
        msg['To'] = to_email
        
        # Add text and HTML parts
        if text_content:
            part1 = MIMEText(text_content, 'plain')
            msg.attach(part1)
        
        part2 = MIMEText(html_content, 'html')
        msg.attach(part2)
        
        # Send email
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.sendmail(from_email, to_email, msg.as_string())
        
        logger.info(f"Email sent successfully to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        return False

def send_verification_email(to_email, username, verification_token):
    """
    Send email verification link to user
    
    Args:
        to_email: User's email address
        username: User's username
        verification_token: Verification token
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    app_url = current_app.config.get('APP_URL', 'http://localhost:3000')
    verification_url = f"{app_url}/verify-email?token={verification_token}"
    
    subject = "Verify Your Email - MyNet"
    
    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #4CAF50;">Welcome to MyNet, {username}!</h2>
                <p>Thank you for registering. Please verify your email address to activate your account.</p>
                <p>Click the button below to verify your email:</p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{verification_url}" 
                       style="background-color: #4CAF50; 
                              color: white; 
                              padding: 12px 30px; 
                              text-decoration: none; 
                              border-radius: 5px;
                              display: inline-block;">
                        Verify Email
                    </a>
                </div>
                <p>Or copy and paste this link into your browser:</p>
                <p style="word-break: break-all; color: #666;">{verification_url}</p>
                <p style="margin-top: 30px; font-size: 12px; color: #999;">
                    This link will expire in 24 hours. If you didn't create an account, please ignore this email.
                </p>
            </div>
        </body>
    </html>
    """
    
    text_content = f"""
    Welcome to MyNet, {username}!
    
    Thank you for registering. Please verify your email address to activate your account.
    
    Click the link below to verify your email:
    {verification_url}
    
    This link will expire in 24 hours. If you didn't create an account, please ignore this email.
    """
    
    return send_email(to_email, subject, html_content, text_content)
