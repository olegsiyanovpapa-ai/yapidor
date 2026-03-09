# TON Crypto Villa Bot

Telegram bot for buying/selling TON with Tonkeeper integration and Lava business payments.

## Features

- **TON Connect 2.0 Integration**: Connect Tonkeeper and other TON wallets seamlessly.
- **Lava Payments**: Fast and secure fiat-to-crypto payments (Cards RF, SBP).
- **User Management**: Maintains user sessions and wallet addresses.
- **Modern UI**: Clean and intuitive Telegram interface.

## Quick Start

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd bot.ton
   ```

2. **Setup environment**:
   Copy `.env.example` to `.env` and fill in your credentials.
   ```bash
   copy .env.example .env
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the bot**:
   ```bash
   run.bat
   ```

## Requirements

- Python 3.9+
- Aiogram 3.x
- TON Connect 2.0

## License

This project is licensed under the MIT License.
