import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

# MongoDB connection
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")

# Telegram bot credentials
BOT_TOKEN = os.getenv("BOT_TOKEN", "your-bot-token")
API_ID = int(os.getenv("API_ID", 123456))
API_HASH = os.getenv("API_HASH", "your-api-hash")

# Optional game settings (defaults)
MIN_PLAYERS = int(os.getenv("MIN_PLAYERS", 4))
MAX_PLAYERS = int(os.getenv("MAX_PLAYERS", 10))
