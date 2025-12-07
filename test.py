import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

EMAIL_ADDRESS = "artem4iknagibator@gmail.com"      # your real Gmail
EMAIL_PASSWORD = "yohv agsn unct rapr"           # Gmail App Password
TO_EMAIL = "artembozadi@gmail.com"            # test receiver

def send_test_email():
    subject = "SMTP test message"
    body = """
    This is a plain SMTP test email.

    If you received this, smtplib works ✅
    """

    message = MIMEMultipart()
    message["From"] = EMAIL_ADDRESS
    message["To"] = TO_EMAIL
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.set_debuglevel(1)   # shows SMTP conversation
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(message)

    print("✅ Email sent successfully")

if __name__ == "__main__":
    send_test_email()