# bot.py
import os
import random
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")

bot = Client("treasure_war_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
client = MongoClient(MONGO_URL)
db = client["treasure_war"]
players = {}
games = {}

MIN_PLAYERS = 4

roles = {
    "pirates": ["Captain Kraken", "Gunpowder Gale", "Rum Raider"],
    "ninjas": ["Shadow Fang", "Mist Blade", "Gold Ghost"],
    "commoners": ["Treasure Seeker", "Village Guard", "Fisher"]
}

@bot.on_message(filters.command("startgame"))
async def start_game(client, message):
    chat_id = message.chat.id
    if chat_id in games and games[chat_id].get("started"):
        await message.reply("❌ Game already started.")
        return
    games[chat_id] = {"players": [], "started": False}
    await message.reply("🎮 Game created! Players use /join to enter the lobby.")

@bot.on_message(filters.command("join"))
async def join_game(client, message):
    user = message.from_user
    chat_id = message.chat.id
    if chat_id not in games:
        await message.reply("❗ No active game. Ask admin to use /startgame")
        return

    if user.id in games[chat_id]["players"]:
        await message.reply("✅ You already joined the game.")
        return

    games[chat_id]["players"].append(user.id)
    players[user.id] = {"name": user.first_name, "role": None, "xp": 0, "coins": 0, "alive": True}
    await message.reply(f"👤 {user.first_name} joined the game!")

    if len(games[chat_id]["players"]) >= MIN_PLAYERS and not games[chat_id]["started"]:
        await start_roles_assignment(chat_id, client)

async def start_roles_assignment(chat_id, client):
    user_ids = games[chat_id]["players"]
    random.shuffle(user_ids)
    count = len(user_ids)

    pirate_count = max(1, count // 4)
    ninja_count = max(1, count // 4)
    commoner_count = count - pirate_count - ninja_count

    pirates = user_ids[:pirate_count]
    ninjas = user_ids[pirate_count:pirate_count + ninja_count]
    commoners = user_ids[pirate_count + ninja_count:]

    for uid in pirates:
        role = random.choice(roles["pirates"])
        players[uid]["role"] = role
        await client.send_message(uid, f"🏴‍☠️ You are a Pirate: {role}\nUse /usepower during night phase.")

    for uid in ninjas:
        role = random.choice(roles["ninjas"])
        players[uid]["role"] = role
        await client.send_message(uid, f"🥷 You are a Ninja: {role}\nUse /usepower during night phase.")

    for uid in commoners:
        role = random.choice(roles["commoners"])
        players[uid]["role"] = role
        await client.send_message(uid, f"👨‍🌾 You are a Commoner: {role}\nVote during day and help your side win!")

    games[chat_id]["started"] = True
    await bot.send_message(chat_id, "✅ Roles assigned! The battle begins soon!")
    await asyncio.sleep(10)
    await bot.send_message(chat_id, "🌅 Day Phase has begun! Use /vote to vote out enemies.")

@bot.on_message(filters.command("profile"))
async def show_profile(client, message: Message):
    user_id = message.from_user.id
    user = players.get(user_id)
    if not user:
        await message.reply("You are not part of the game.")
        return

    await message.reply(f"📜 Profile for {user['name']}\n"
                        f"🔰 Role: {user['role']}\n"
                        f"⚔️ XP: {user['xp']}\n"
                        f"💰 Coins: {user['coins']}\n"
                        f"❤️ Alive: {'Yes' if user['alive'] else 'No'}")

@bot.on_message(filters.command("usepower"))
async def use_power(client, message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user = players.get(user_id)

    if not user or not user["alive"]:
        await message.reply("❌ You cannot use powers right now.")
        return

    # For simplicity, simulate power success
    user["xp"] += 20
    user["coins"] += 10
    await client.send_message(user_id, f"🎯 Power used successfully! +20 XP, +10 Coins")

@bot.on_message(filters.command("vote"))
async def vote_player(client, message: Message):
    await message.reply("🗳️ Voting system coming soon!")

@bot.on_message(filters.command("loot"))
async def loot_command(client, message: Message):
    user_id = message.from_user.id
    if user_id not in players or not players[user_id]["alive"]:
        await message.reply("❌ You cannot loot now.")
        return

    coins = random.randint(5, 15)
    players[user_id]["coins"] += coins
    players[user_id]["xp"] += 10
    await message.reply(f"🪙 You found {coins} coins! (+10 XP)")

bot.run()
