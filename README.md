# MyNet Server

[![Project Status: WIP](https://img.shields.io/badge/Status-Work%20In%20Progress-orange)](https://github.com/your-org/mynet-server)

## Overview

Backend service for MyNet technical communication platform. Built with Flask and WebSockets, providing real-time messaging, code execution, and LaTeX rendering for technical collaboration.

## 🚀 Quick Start

Run the complete platform using the infrastructure repository:

```bash
git clone https://github.com/M1XaM/my-net-infra.git
cd my-net-infra
docker-compose up
```

## 🏗️ Architecture

- **Flask Application** - REST API and WebSocket handlers
- **WebSocket Server** - Real-time messaging
- **PostgreSQL** - Primary data storage

## 🛠️ Technology Stack

- Flask
- PostgreSQL
- Docker

## ✨ Features

- **User Authentication** - Secure registration and login with JWT tokens
- **Email Verification** - Token-based email verification for new users
- **Google OAuth** - Sign in with Google integration
- **Real-time Messaging** - WebSocket-based chat functionality
- **End-to-End Encryption** - Encrypted storage for sensitive data

## 📖 Documentation

- [Email Verification Setup](docs/EMAIL_VERIFICATION.md) - Configuration and usage guide


## 📋 Status

🚧 **Work in Progress** - Core functionality implemented and being tested.

## 🔗 Related Repos

- [MyNet Client](https://github.com/M1XaM/my-net-client)
- [MyNet Infrastructure](https://github.com/M1XaM/my-net-infra)
