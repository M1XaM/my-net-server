# Email Verification System

This document describes the email verification system implemented for user registration.

## Overview

The email verification system ensures that users have access to the email address they register with. Users must verify their email before they can log in to the application.

## Features

- Secure token-based email verification
- 24-hour token expiration
- Resend verification email functionality
- Automatic verification for Google OAuth users
- Comprehensive error handling

## Environment Variables

Configure the following environment variables in your `.env` file:

```bash
# SMTP Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=noreply@mynet.com
SMTP_FROM_NAME=MyNet
APP_URL=http://localhost:3000
```

**Note:** For Gmail, you need to use an [App Password](https://support.google.com/accounts/answer/185833) instead of your regular password.

## API Endpoints

### 1. Register User
**POST** `/api/register`

Creates a new user account and sends a verification email.

**Request Body:**
```json
{
  "username": "john_doe",
  "email": "john@example.com",
  "password": "securePassword123"
}
```

**Response (201):**
```json
{
  "message": "Registration successful. Please check your email to verify your account.",
  "email": "john@example.com"
}
```

**Errors:**
- `400`: Username required / Password required / Email required
- `400`: Username already exists / Email already exists

### 2. Verify Email
**GET** `/api/auth/verify-email?token=<verification_token>`

Verifies the user's email address using the token sent to their email.

**Query Parameters:**
- `token`: The verification token from the email

**Response (200):**
```json
{
  "message": "Email verified successfully. You can now log in."
}
```

**Errors:**
- `400`: Verification token required
- `400`: Invalid verification token
- `400`: This verification link has already been used
- `400`: This verification link has expired
- `404`: User not found

### 3. Resend Verification Email
**POST** `/api/auth/resend-verification`

Sends a new verification email to the user.

**Request Body:**
```json
{
  "email": "john@example.com"
}
```

**Response (200):**
```json
{
  "message": "Verification email sent. Please check your inbox."
}
```

**Errors:**
- `400`: Email required
- `400`: Email already verified
- `404`: User not found

### 4. Login
**POST** `/api/login`

Updated to check email verification status before allowing login.

**Request Body:**
```json
{
  "username": "john_doe",
  "password": "securePassword123"
}
```

**Response (200):**
```json
{
  "id": 1,
  "username": "john_doe",
  "access_token": "eyJ0eXAiOiJKV1QiLCJh...",
  "csrf_token": "abc123..."
}
```

**Errors:**
- `401`: Invalid username or password
- `403`: Please verify your email before logging in

## Database Schema

### User Model Extensions
- `is_email_verified`: Boolean field indicating if email is verified (default: `false`)
- `email_verified_at`: Timestamp of when email was verified (nullable)

### EmailVerification Model
- `id`: Primary key
- `user_id`: Foreign key to User
- `token`: Unique verification token (64 characters)
- `expires_at`: Token expiration timestamp
- `is_used`: Boolean indicating if token has been used
- `created_at`: Timestamp of token creation

## Security Features

1. **Secure Token Generation**: Uses Python's `secrets` module for cryptographically secure tokens
2. **Token Expiration**: Tokens expire after 24 hours
3. **One-Time Use**: Tokens can only be used once
4. **Transaction Safety**: User and verification token created in single database transaction
5. **SMTP Validation**: All SMTP configuration validated before attempting to send emails
6. **Timezone-Aware**: Uses UTC timestamps throughout

## Development Mode

If SMTP credentials are not configured, the system will log verification emails instead of sending them:

```
SMTP not fully configured. Email will not be sent.
Would send email to john@example.com with subject: Verify Your Email - MyNet
```

This allows development and testing without requiring a real SMTP server.

## Google OAuth Integration

Users who sign in with Google OAuth are automatically verified since Google has already verified their email address. These users:
- Have `is_email_verified` set to `true`
- Have `email_verified_at` set to the time of first login
- Can log in immediately without email verification

## Email Template

The verification email includes:
- Welcoming message with username
- Clear call-to-action button
- Plain text link as fallback
- Expiration notice (24 hours)
- HTML and plain text versions

## Error Handling

The system handles various error scenarios:

- **Invalid tokens**: Returns clear error messages
- **Expired tokens**: Allows resending new verification email
- **Used tokens**: Prevents token reuse
- **Missing users**: Handles deleted users gracefully
- **Duplicate emails**: Prevents registration with existing emails
- **SMTP failures**: Logs errors without breaking registration flow

## Testing

To test the email verification flow:

1. Register a new user
2. Check application logs for verification link (if SMTP not configured)
3. Visit the verification URL
4. Attempt to login before verification (should fail with 403)
5. Complete verification
6. Login successfully

## Migration Notes

When deploying this feature to an existing database:

1. The database migration will add new fields to the `users` table and create the `email_verifications` table
2. Existing users will have `is_email_verified` set to `false` by default
3. Consider running a script to set `is_email_verified` to `true` for existing users if you want to grandfather them in
4. Alternatively, require existing users to verify their email on next login
