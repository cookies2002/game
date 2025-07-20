# Fairy vs Villain Telegram Game Bot
# bot.py

import os
import random
import asyncio
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import Message
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

# Bot credentials
API_ID = int(os.getenv("24977986"))
API_HASH = os.getenv("abc6095228862c7502397c928bd7999e")
BOT_TOKEN = os.getenv("8098135944:AAF-zdTqjoYwW3fDdS7BY9zEX5BaiK235iY")
MONGO_URL = os.getenv("mongodb+srv://xarwin2:xarwin2002@cluster0.qmetx2m.mongodb.net/?retryWrites=true&w=majority")

bot = Client("fairy_vs_villain_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
client = MongoClient(MONGO_URL)
db = client.fairy_game

# In-memory storage
games = {}
power_cooldowns = {}

# Characters
fairy_powers = ["🌟 Light Heal", "🛡️ Magic Shield", "✨ Fairy Glow", "🌀 Energy Bubble", "🧚‍♀️ Soul Bind"]
villain_powers = ["💀 Shadow Strike", "🧨 Curse", "🔇 Silence", "🔥 Fire Blast", "🧠 Mind Control"]
commoner_power = "🤝 Vote Power"

# XP and Level thresholds
LEVELS = {
    1: 0,
    2: 50,
    3: 150,
    4: 300,
    5: 500,
}

# Command Handlers
@bot.on_message(filters.command("start"))
async def start(client, message):
    await message.reply("Welcome to 🧚‍♀️ *Fairy vs Villain*!\nUse /join to enter the game.", quote=True)

@bot.on_message(filters.command("join"))
async def join(client, message):
    chat_id = str(message.chat.id)
    user = message.from_user
    if chat_id not in games:
        games[chat_id] = {"players": {}, "state": "waiting", "votes": {}, "alive": set(), "powers": {}, "joined_at": datetime.utcnow()}
    if user.id in games[chat_id]["players"]:
        await message.reply("You already joined!")
        return
    games[chat_id]["players"][user.id] = user.first_name
    games[chat_id]["alive"].add(user.id)
    await message.reply(f"✅ {user.mention} joined the game!")

    if len(games[chat_id]["players"]) >= 4:
        await start_game(chat_id)

async def start_game(chat_id):
    group = games[chat_id]
    group["state"] = "started"
    player_ids = list(group["players"].keys())
    random.shuffle(player_ids)

    num = len(player_ids)
    num_fairy = num // 3
    num_villain = num // 3
    num_common = num - num_fairy - num_villain

    roles = (["Fairy"] * num_fairy) + (["Villain"] * num_villain) + (["Commoner"] * num_common)
    random.shuffle(roles)

    for uid, role in zip(player_ids, roles):
        user_data = {
            "user_id": uid,
            "coins": 0,
            "xp": 0,
            "level": 1,
            "role": role,
            "alive": True
        }
        db.users.update_one({"user_id": uid}, {"$set": user_data}, upsert=True)
        power = random.choice(fairy_powers if role == "Fairy" else villain_powers if role == "Villain" else [commoner_power])
        group["powers"][uid] = power
        await bot.send_message(uid, f"🌟 Your role: *{role}*\nYour power: {power}\nUse /usepower @target in group to act!")

    await bot.send_message(int(chat_id), "🎮 Game started! Use /vote or /usepower")

@bot.on_message(filters.command("leave"))
async def leave(client, message):
    chat_id = str(message.chat.id)
    user = message.from_user
    if chat_id not in games:
        await message.reply("No active game here.")
        return
    if user.id in games[chat_id]["players"]:
        games[chat_id]["players"].pop(user.id)
        games[chat_id]["alive"].discard(user.id)
        await message.reply(f"👋 {user.mention} left the game.")
    else:
        await message.reply("You are not in the game!")

@bot.on_message(filters.command("end"))
async def end(client, message):
    chat_id = str(message.chat.id)
    if message.from_user.id != (await client.get_chat_member(chat_id, message.from_user.id)).user.id:
        await message.reply("Only group admin can end the game.")
        return
    if chat_id in games:
        games.pop(chat_id)
        await message.reply("🛑 Game has been ended manually by admin.")
    else:
        await message.reply("No game is active.")

# Add other command handlers (/vote, /usepower, /upgrade, /profile, etc.) below...

bot.run()
