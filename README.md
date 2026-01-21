# MyNet Server

[![Project Status: WIP](https://img.shields.io/badge/Status-Work%20In%20Progress-orange)](https://github.com/your-org/mynet-server)

## Overview

Backend service for MyNet technical communication platform. Built with FastAPI and WebSockets, providing real-time messaging, code execution, and LaTeX rendering for technical collaboration.

## 🚀 Quick Start

Check [infrastructure repository](https://github.com/M1XaM/my-net-infra).

## 🏗️ Architecture

- **FastAPI Application** - async REST API and WebSocket handlers
- **WebSocket Server** - Real-time messaging
- **PostgreSQL** - Primary data storage

## 🛠️ Technology Stack

- FastAPI
- PostgreSQL
- Docker

## ✨ Features

- **User Authentication** - Secure registration and login with JWT tokens
- **Email Verification** - Token-based email verification for new users
- **Google OAuth** - Sign in with Google integration
- **Real-time Messaging** - WebSocket-based chat functionality

## 📋 Status

🚧 **Work in Progress** - Core functionality implemented and being tested.

## 🔗 Related Repos

- [MyNet Client](https://github.com/M1XaM/my-net-client)
- [MyNet Infrastructure](https://github.com/M1XaM/my-net-infra)
