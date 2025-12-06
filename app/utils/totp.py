import pyotp
import qrcode
import io
import base64


def generate_secret():
    return pyotp.random_base32()


def get_totp_uri(username, secret):
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(
        name=username,
        issuer_name="ChatApp"
    )


def verify_totp(secret, token):
    """Verify a TOTP token"""
    totp = pyotp.TOTP(secret)
    return totp.verify(token, valid_window=1)


def generate_qr_code(uri):
    img = qrcode.make(uri)

    # Save to buffer
    buffered = io.BytesIO()
    img.save(buffered)  # No format needed - PNG is default
    img_str = base64.b64encode(buffered.getvalue()).decode()

    return f'data:image/png;base64,{img_str}'