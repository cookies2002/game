import os

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
BOT_TOKEN = os.getenv("BOT_TOKEN", "your-bot-token")
API_ID = int(os.getenv("API_ID", 123456))
API_HASH = os.getenv("API_HASH", "your-api-hash")