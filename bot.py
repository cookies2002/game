# ✅ Complete Working Code with Welcome Message Support
# -----------------------------------------------

import os
import random
import asyncio
from collections import defaultdict, Counter
from pyrogram import Client, filters
from pyrogram.types import Message
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")

bot = Client("fairy_power_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
db = MongoClient(MONGO_URL).fairy_power_game
users_col = db.users

active_games = {}
all_roles = {
    "Fairy": ["Sparkle Beam", "Moonlight Shield", "Celestial Arrow"],
    "Villain": ["Dark Flame", "Shadow Strike", "Fear Curse"],
    "Commoner": ["Vote"]
}

MAX_PLAYERS = 15
level_thresholds = {1: 0, 2: 100, 3: 250, 4: 500, 5: 1000}
cooldown_tracker = defaultdict(dict)

# Utility Functions

def get_user(user_id):
    user = users_col.find_one({"_id": user_id})
    if not user:
        user = {"_id": user_id, "xp": 0, "level": 1, "coins": 0, "role": None}
        users_col.insert_one(user)
    return user

def update_user(user_id, **kwargs):
    users_col.update_one({"_id": user_id}, {"$set": kwargs})

def get_level(xp):
    level = 1
    for lvl, threshold in sorted(level_thresholds.items()):
        if xp >= threshold:
            level = lvl
    return level

def get_power(role, level):
    if role not in all_roles:
        return "None"
    powers = all_roles[role]
    index = min(level - 1, len(powers) - 1)
    return powers[index]

def assign_roles(players):
    total_players = len(players)
    num_villains = max(1, total_players // 4)
    num_fairies = max(1, total_players // 3)
    num_commoners = total_players - (num_villains + num_fairies)
    role_list = ["Villain"] * num_villains + ["Fairy"] * num_fairies + ["Commoner"] * num_commoners
    random.shuffle(role_list)
    random.shuffle(players)
    return {player: role_list[i] for i, player in enumerate(players)}

# Private Welcome Message
@bot.on_message(filters.private & filters.command("start"))
async def welcome_user(client, message: Message):
    await message.reply(
        """
👋 **Welcome to Fairy Power Game Bot!**

✨ Team-based mystery game with Fairies, Villains, and Commoners.
🧠 Use powers, vote wisely, and level up!

🎮 Group Admins: Use /start in a group to create a new game.
👥 Players: Use /join to enter and wait for game to begin.

🔍 Use /instructions for rules.
💡 Use /help to see all commands.
        """
    )

# Game Commands (Group)
@bot.on_message(filters.command("start") & filters.group)
async def start_game(client, message: Message):
    chat_id = message.chat.id
    if chat_id in active_games:
        await message.reply("🎮 Game already active! Use /join to enter.")
        return
    active_games[chat_id] = {"players": [], "state": "waiting", "roles": {}, "votes": {}, "cooldowns": {}, "alive": set()}
    await message.reply("🕒 4 players joined. Waiting 60 seconds for more players before starting game...")
    await asyncio.sleep(60)
    if len(active_games[chat_id]["players"]) >= 4:
        await begin_game(chat_id)
    else:
        await client.send_message(chat_id, "❌ Not enough players. Game cancelled.")
        active_games.pop(chat_id)

@bot.on_message(filters.command("join"))
async def join_game(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    mention = message.from_user.mention
    if chat_id not in active_games:
        await message.reply("❌ No game active. Use /start to begin one.")
        return
    game = active_games[chat_id]
    if user_id in game["players"]:
        await message.reply("✅ You're already in!")
        return
    if len(game["players"]) >= MAX_PLAYERS:
        await message.reply("⚠️ Max players reached.")
        return
    game["players"].append(user_id)
    await message.reply(f"✅ {mention} joined the game! ({len(game['players'])}/{MAX_PLAYERS})")

@bot.on_message(filters.command("leave"))
async def leave_game(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if chat_id in active_games and user_id in active_games[chat_id]["players"]:
        active_games[chat_id]["players"].remove(user_id)
        await message.reply("👋 You left the game.")

async def begin_game(chat_id):
    game = active_games[chat_id]
    players = game["players"]
    roles = assign_roles(players)
    game["roles"] = roles
    game["state"] = "playing"
    game["alive"] = set(players)
    for user_id, role in roles.items():
        user = get_user(user_id)
        level = user.get("level", 1)
        power = get_power(role, level)
        update_user(user_id, role=role)
        msg = f"🎭 Your role is: {role}\n⭐ Level: {level}\n✨ Power: {power}\nUse /usepower @username to use it. Use /powers to view future powers."
        await bot.send_message(user_id, msg)
    await bot.send_message(chat_id, "🎮 Game started! Players received their roles in DM.")

# XP & Leaderboard
@bot.on_message(filters.command("myxp"))
async def myxp(client, message: Message):
    user = get_user(message.from_user.id)
    await message.reply(f"📊 XP: {user['xp']} | ⭐ Level: {user['level']} | 💎 Coins: {user['coins']}")

@bot.on_message(filters.command("leaderboard"))
async def leaderboard(client, message: Message):
    top = list(users_col.find().sort("xp", -1).limit(10))
    msg = "🌍 Global Leaderboard:\n"
    for i, u in enumerate(top, 1):
        msg += f"{i}. ID {u['_id']} - {u['xp']} XP\n"
    await message.reply(msg)

@bot.on_message(filters.command("myleaderboard"))
async def my_leaderboard(client, message: Message):
    chat_id = message.chat.id
    players = active_games.get(chat_id, {}).get("players", [])
    if not players:
        await message.reply("No game or players found in this group.")
        return
    records = [get_user(uid) for uid in players]
    top = sorted(records, key=lambda x: x['xp'], reverse=True)
    msg = "🏆 Group Leaderboard:\n"
    for i, u in enumerate(top, 1):
        msg += f"{i}. ID {u['_id']} - {u['xp']} XP\n"
    await message.reply(msg)

@bot.on_message(filters.command("instructions"))
async def instructions(client, message: Message):
    await message.reply("""
📖 **Game Instructions**

- Use /start to create a game.
- /join to enter, /leave to exit.
- Once 4+ players join, game starts in 60 sec.
- Roles: Fairy 🧚, Villain 😈, Commoner 👤
- Each role has powers based on level.
- Use /usepower @username to attack (Fairy/Villain only)
- /vote @username to eliminate suspicious Villains
- Earn XP & Coins by attacking and surviving
- /upgrade to level up and unlock stronger powers
    """)

# Start the bot
bot.run()
