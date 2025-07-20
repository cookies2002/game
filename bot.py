import os
import asyncio
import random
from pyrogram import Client, filters
from pyrogram.types import Message
from pymongo import MongoClient
from datetime import datetime, timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
MONGO_URL = os.getenv("MONGO_URL")

bot = Client("fairy_vs_villain", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)
mongo = MongoClient(MONGO_URL)
db = mongo.game_bot
users = db.users

active_games = {}

roles = {
    "Fairy": ["Sparkle Beam", "Moonlight Shield", "Celestial Arrow"],
    "Villain": ["Dark Flame", "Fear Strike", "Shadow Trap"],
    "Commoner": ["Support Vote"]
}

role_list = ["Fairy", "Villain", "Commoner"]

# Assign roles randomly
async def assign_roles(players):
    random.shuffle(players)
    fairies = players[:len(players)//3]
    villains = players[len(players)//3:2*len(players)//3]
    commoners = players[2*len(players)//3:]
    assigned = {}
    for p in fairies:
        assigned[p] = "Fairy"
    for p in villains:
        assigned[p] = "Villain"
    for p in commoners:
        assigned[p] = "Commoner"
    return assigned

# Send instructions to each player
async def send_role_dm(user_id, role):
    level = get_user(user_id).get("level", 1)
    powers = get_power_by_level(role, level)
    try:
        text = f"👤 You are a {role}!\n"
        text += f"🎯 Your power at Level {level}: {powers[0]}\n"
        text += f"🧠 Tip: Use /usepower @target wisely!"
        await bot.send_message(user_id, text)
    except:
        pass

def get_power_by_level(role, level):
    return roles.get(role, [])[max(0, min(level-1, len(roles[role])-1)):] or ["Basic Strike"]

def get_user(user_id):
    user = users.find_one({"_id": user_id})
    if not user:
        user = {"_id": user_id, "xp": 0, "level": 1, "coins": 0}
        users.insert_one(user)
    return user

def update_user(user_id, **kwargs):
    users.update_one({"_id": user_id}, {"$set": kwargs}, upsert=True)

@bot.on_message(filters.command("start"))
async def start_game(client, message):
    chat_id = message.chat.id
    if chat_id not in active_games:
        active_games[chat_id] = {"players": [], "state": "waiting"}
        await message.reply("🎮 Game created! Use /join to participate. Game will auto-start in 1 minute after 4 players join!")

@bot.on_message(filters.command("join"))
async def join_game(client, message):
    chat_id = message.chat.id
    user = message.from_user
    if chat_id not in active_games:
        await message.reply("No active game. Use /start to begin.")
        return
    if user.id not in active_games[chat_id]["players"]:
        active_games[chat_id]["players"].append(user.id)
        await message.reply(f"✅ {user.mention} joined the game!")
        if len(active_games[chat_id]["players"]) == 4:
            await message.reply("⏳ Minimum 4 players joined. Game will auto-start in 60 seconds...")
            await asyncio.sleep(60)
            await begin_game(chat_id)

async def begin_game(chat_id):
    players = active_games[chat_id]["players"]
    if not players or len(players) < 4:
        return
    assigned_roles = await assign_roles(players)
    active_games[chat_id]["assigned"] = assigned_roles
    active_games[chat_id]["state"] = "in_progress"
    for uid, role in assigned_roles.items():
        await send_role_dm(uid, role)
    await bot.send_message(chat_id, "🌀 Roles assigned! Use /usepower @username and /vote to play!")

@bot.on_message(filters.command("usepower"))
async def use_power(client, message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if chat_id not in active_games or active_games[chat_id].get("state") != "in_progress":
        return
    if len(message.command) < 2:
        await message.reply("Please mention a target: /usepower @username")
        return
    target = message.command[1]
    user_role = active_games[chat_id]["assigned"].get(user_id)
    if user_role == "Commoner":
        await message.reply("🚫 Commoners cannot use powers!")
        return
    await bot.send_message(user_id, f"💥 You used your power on {target}!")
    if user_role in ["Fairy", "Villain"]:
        await message.reply(f"💀 {target} was defeated! 🎯 Attacked by: {message.from_user.mention}")
    update_user(user_id, coins=get_user(user_id)["coins"] + 10)

@bot.on_message(filters.command("vote"))
async def vote_player(client, message):
    await message.reply("🗳️ Voting coming soon...")

@bot.on_message(filters.command("myxp"))
async def show_my_xp(client, message):
    u = get_user(message.from_user.id)
    await message.reply(f"📊 XP: {u['xp']} | Level: {u['level']} | Coins: {u['coins']}")

@bot.on_message(filters.command("upgrade"))
async def upgrade(client, message):
    u = get_user(message.from_user.id)
    if u['coins'] >= 50:
        users.update_one({"_id": u['_id']}, {"$inc": {"level": 1, "coins": -50}})
        await message.reply(f"⬆️ Upgraded to level {u['level']+1}! Remaining coins: {u['coins'] - 50}")
    else:
        await message.reply("❌ Not enough coins to upgrade (50 needed).")

@bot.on_message(filters.command("profile"))
async def profile(client, message):
    u = get_user(message.from_user.id)
    await message.reply(f"👤 Profile\nLevel: {u['level']}\nXP: {u['xp']}\nCoins: {u['coins']}")

@bot.on_message(filters.command("instructions"))
async def show_help(client, message):
    await message.reply(
        "📜 Game Instructions:\n"
        "- Fairies, Villains, and Commoners are assigned.\n"
        "- Use /usepower @username (only Fairies/Villains).\n"
        "- Commoners vote to help Fairies.\n"
        "- Earn XP/Coins by using power, surviving, voting.\n"
        "- Use /upgrade to unlock stronger powers!\n"
        "- Game auto-starts at 4+ players after 60 sec."
    )

@bot.on_message(filters.command("powers"))
async def powers(client, message):
    u = get_user(message.from_user.id)
    role = None
    for game in active_games.values():
        if u['_id'] in game.get("assigned", {}):
            role = game["assigned"][u['_id']]
            break
    if not role:
        await message.reply("You're not in an active game.")
        return
    powers = roles[role]
    await message.reply(f"🔮 Future Powers for {role}:\n" + "\n".join([f"Level {i+1}: {p}" for i, p in enumerate(powers)]))

print("✅ Bot is running...")
bot.run()
