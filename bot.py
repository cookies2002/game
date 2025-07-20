import os
import asyncio
import random
from pyrogram import Client, filters
from pyrogram.types import Message
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")

bot = Client("fairy_vs_villain_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
mongo = MongoClient(MONGO_URL)
db = mongo["fairy_game"]
users = db["users"]
games = db["games"]

ROLES = {
    "Fairy": [
        {"name": "Light Fairy", "power": "Reveal a player's role"},
        {"name": "Healing Fairy", "power": "Revive a defeated player"},
        {"name": "Wind Fairy", "power": "Deflect one attack"},
        {"name": "Shield Fairy", "power": "Protect someone for one round"},
        {"name": "Mirror Fairy", "power": "Reflect an attack back"}
    ],
    "Villain": [
        {"name": "Dark Lord", "power": "Eliminate a player instantly"},
        {"name": "Shadow Mage", "power": "Block a power for 1 round"},
        {"name": "Fear Bringer", "power": "Silence 2 players"},
        {"name": "Mind Twister", "power": "Swap 2 roles"},
        {"name": "Death Caller", "power": "Convert a commoner to villain"}
    ],
    "Commoner": [
        {"name": "Citizen", "power": "Can vote. Earn coins by surviving"},
        {"name": "Hunter", "power": "If killed, can take one with them"},
        {"name": "Guardian", "power": "Protect 1 person once"},
        {"name": "Priest", "power": "Can pray to reduce damage"},
        {"name": "Spy", "power": "Once check someone secretly"}
    ]
}

group_sessions = {}

# /startgame - Start a game
@bot.on_message(filters.command("startgame"))
async def start_game(client, message: Message):
    chat_id = message.chat.id
    if chat_id in group_sessions:
        await message.reply("⚠️ Game already started in this group.")
        return
    group_sessions[chat_id] = {"players": [], "status": "waiting"}
    await message.reply("🎮 Game lobby started! Type /join to enter. Minimum 4 players required.")

# /join - Join lobby
@bot.on_message(filters.command("join"))
async def join_game(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    username = message.from_user.mention

    session = group_sessions.get(chat_id)
    if not session:
        await message.reply("❌ No game lobby. Start one using /startgame.")
        return

    if session["status"] != "waiting":
        await message.reply("🚫 Game already in progress.")
        return

    if user_id in session["players"]:
        await message.reply("✅ You already joined.")
        return

    if len(session["players"]) >= 15:
        await message.reply("🚫 Max 15 players allowed.")
        return

    session["players"].append(user_id)
    await message.reply(f"🧙 {username} joined the game!")

    if len(session["players"]) >= 4:
        await message.reply("⏳ Enough players! Game will start in 60 seconds. Others can still /join.")
        await asyncio.sleep(60)
        await start_roles(client, message)

async def start_roles(client, message):
    chat_id = message.chat.id
    session = group_sessions.get(chat_id)
    if not session or session["status"] != "waiting":
        return

    players = session["players"]
    random.shuffle(players)
    total = len(players)

    role_counts = {
        "Fairy": max(1, total // 3),
        "Villain": max(1, total // 4),
        "Commoner": total - (max(1, total // 3) + max(1, total // 4))
    }

    assigned_roles = []

    for role, count in role_counts.items():
        for _ in range(count):
            uid = players.pop()
            role_info = random.choice(ROLES[role])
            assigned_roles.append((uid, role, role_info))
            users.update_one({"_id": uid}, {"$set": {
                "role": role_info["name"],
                "power": role_info["power"],
                "team": role,
                "xp": 0,
                "coins": 0,
                "alive": True
            }}, upsert=True)
            await client.send_message(uid,
                f"🎭 Your role: <b>{role_info['name']}</b>\n💥 Power: <i>{role_info['power']}</i>\nUse /usepower in group (secretly)\nTeam: <b>{role}</b>",
                parse_mode="html"
            )

    group_sessions[chat_id]["status"] = "started"
    await message.reply("🚀 Game started! Check your DM for your role. Let the battle begin!")

# /leave - Exit before game starts
@bot.on_message(filters.command("leave"))
async def leave_game(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    session = group_sessions.get(chat_id)
    if session and session["status"] == "waiting":
        if user_id in session["players"]:
            session["players"].remove(user_id)
            await message.reply("❎ You left the game lobby.")
        else:
            await message.reply("❌ You weren't in the lobby.")
    else:
        await message.reply("❌ Can't leave now.")

# /end - Reset game
@bot.on_message(filters.command("end"))
async def end_game(client, message: Message):
    if message.from_user.id not in [admin.user.id async for admin in client.get_chat_members(message.chat.id, filter="administrators")]:
        await message.reply("❌ Only admins can end the game.")
        return
    chat_id = message.chat.id
    if chat_id in group_sessions:
        del group_sessions[chat_id]
        await message.reply("🛑 Game ended and reset.")
    else:
        await message.reply("ℹ️ No active game.")

# /usepower - Secretly use power
@bot.on_message(filters.command("usepower"))
async def use_power(client, message: Message):
    user_id = message.from_user.id
    user = users.find_one({"_id": user_id})
    if not user or not user.get("alive", True):
        await message.reply("❌ You are not alive or in the game.")
        return

    await message.reply("🧙 Your power usage was received. You'll get a DM.")
    await client.send_message(user_id, f"🌀 You used your power: <b>{user['power']}</b>", parse_mode="html")

# /vote - Vote someone
@bot.on_message(filters.command("vote"))
async def vote_player(client, message: Message):
    await message.reply("🗳️ Vote received. Voting feature WIP.")

# /upgrade - Upgrade
@bot.on_message(filters.command("upgrade"))
async def upgrade_power(client, message: Message):
    await message.reply("✨ Upgrade system WIP. You need XP and coins.")

# /shop - Buy items
@bot.on_message(filters.command("shop"))
async def shop(client, message: Message):
    await message.reply("🛒 Shop coming soon. Items: Shield, Scrolls, Boosts.")

# /myxp - Show XP
@bot.on_message(filters.command("myxp"))
async def show_xp(client, message: Message):
    user_id = message.from_user.id
    user = users.find_one({"_id": user_id})
    if not user:
        await message.reply("🙁 You're not in the game yet.")
    else:
        await message.reply(f"💠 XP: {user['xp']} | 💰 Coins: {user['coins']}")

# /profile - Show stats
@bot.on_message(filters.command("profile"))
async def profile(client, message: Message):
    user_id = message.from_user.id
    user = users.find_one({"_id": user_id})
    if not user:
        await message.reply("❌ No profile found.")
    else:
        await message.reply(
            f"👤 <b>Your Profile</b>\n🎭 Role: {user['role']}\n💥 Power: {user['power']}\n🏅 XP: {user['xp']}\n💰 Coins: {user['coins']}\n🧬 Team: {user['team']}",
            parse_mode="html"
        )

# /stats - Show alive etc
@bot.on_message(filters.command("stats"))
async def stats(client, message: Message):
    chat_id = message.chat.id
    session = group_sessions.get(chat_id)
    if not session:
        await message.reply("❌ No game in progress.")
        return
    alive = [uid for uid in session["players"] if users.find_one({"_id": uid, "alive": True})]
    await message.reply(f"🔢 Alive players: {len(alive)}")

# /leaderboard - Global
@bot.on_message(filters.command("leaderboard"))
async def leaderboard(client, message: Message):
    top = users.find().sort("xp", -1).limit(5)
    msg = "🏆 Global Leaderboard:\n"
    for i, u in enumerate(top, 1):
        msg += f"{i}. {u.get('role', '❔')} - {u.get('xp', 0)} XP\n"
    await message.reply(msg)

# /myleaderboard - Group only
@bot.on_message(filters.command("myleaderboard"))
async def my_leaderboard(client, message: Message):
    chat_id = message.chat.id
    session = group_sessions.get(chat_id)
    if not session:
        await message.reply("❌ No game in progress.")
        return
    msg = "📍 Group Leaderboard:\n"
    for i, uid in enumerate(session["players"], 1):
        u = users.find_one({"_id": uid})
        if u:
            msg += f"{i}. {u.get('role', '❔')} - {u.get('xp', 0)} XP\n"
    await message.reply(msg)

# /help - Instructions
@bot.on_message(filters.command("help"))
async def show_help(client, message: Message):
    await message.reply(
        "<b>🧚 Fairy vs Villain - How to Play:</b>\n"
        "• /startgame - Start a new game\n"
        "• /join - Join the game lobby\n"
        "• /leave - Exit before game starts\n"
        "• /end - End/reset the game\n"
        "• /usepower - Use secret powers\n"
        "• /vote - Vote a player (WIP)\n"
        "• /upgrade - Upgrade your powers\n"
        "• /shop - Buy scrolls, shield (soon)\n"
        "• /myxp - Check your XP and coins\n"
        "• /profile - See your stats\n"
        "• /stats - Check game state\n"
        "• /leaderboard - Top global players\n"
        "• /myleaderboard - Top in this group\n",
        parse_mode="html"
    )

print("🤖 Fairy vs Villain Bot is running...")
bot.run()
