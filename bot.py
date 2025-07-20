from pyrogram import Client, filters
from pyrogram.types import Message
from pymongo import MongoClient
import random
import asyncio
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# Environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

bot = Client("fairy_vs_villain_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
client = MongoClient(MONGO_URL)
db = client.game
users_collection = db.users

# Game state and config
active_games = {}
role_powers = {
    "Fairy": ["Sparkle Beam", "Moonlight Shield", "Celestial Arrow"],
    "Villain": ["Shadow Strike", "Fear Trap", "Doom Blast"],
    "Commoner": ["Vote"]
}

power_cooldown = timedelta(minutes=1)
max_players = 15
min_players = 4

def get_user(user_id):
    user = users_collection.find_one({"_id": user_id})
    if not user:
        user = {"_id": user_id, "xp": 0, "coins": 0, "level": 1, "wins": 0, "games": 0, "group_stats": {}}
        users_collection.insert_one(user)
    return user

def update_user(user_id, update):
    users_collection.update_one({"_id": user_id}, {"$set": update})

def add_xp(user_id, xp):
    user = get_user(user_id)
    level = user["level"]
    coins = user.get("coins", 0)
    new_xp = user["xp"] + xp
    level_up_cost = level * 10
    if new_xp >= level * 100:
        level += 1
        new_xp = 0
        coins += 5
    update_user(user_id, {"xp": new_xp, "level": level, "coins": coins})

def assign_roles(players):
    roles = ["Fairy", "Villain"] * (len(players) // 2)
    while len(roles) < len(players):
        roles.append("Commoner")
    random.shuffle(roles)
    return dict(zip(players, roles))

async def send_power_guide(user_id, role, level):
    powers = role_powers.get(role, [])
    power = powers[min(level - 1, len(powers) - 1)]
    text = f"👤 You are a {role}!
🎯 Power: {power}
💡 Use /usepower @username in group to activate (secret DM feedback)
📈 XP helps you level up to unlock more powers!"
    await bot.send_message(user_id, text)

async def begin_game(chat_id):
    game = active_games[chat_id]
    players = game["players"]
    roles = assign_roles(players)
    game["state"] = "running"
    game["roles"] = roles
    game["cooldowns"] = {}
    for user_id, role in roles.items():
        user = get_user(user_id)
        await send_power_guide(user_id, role, user.get("level", 1))
    await bot.send_message(chat_id, "🎮 Game started! Use /usepower, /vote, and strategize wisely!")

@bot.on_message(filters.command("start") & filters.group)
async def start_game(client, message):
    chat_id = message.chat.id
    if chat_id in active_games:
        await message.reply("⚠️ Game already active!")
        return
    active_games[chat_id] = {"players": [], "state": "waiting"}
    await message.reply("🕹 Game starting! Type /join to participate (1 min to auto-start)")
    await asyncio.sleep(60)
    game = active_games.get(chat_id)
    if game and len(game["players"]) >= min_players:
        await begin_game(chat_id)
    else:
        await message.reply("❌ Not enough players. Game cancelled.")
        active_games.pop(chat_id, None)

@bot.on_message(filters.command("join") & filters.group)
async def join_game(client, message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    username = message.from_user.mention
    if chat_id not in active_games:
        await message.reply("No game active. Type /start to begin one.")
        return
    game = active_games[chat_id]
    if user_id in game["players"]:
        await message.reply("You're already in the game!")
        return
    if len(game["players"]) >= max_players:
        await message.reply("Max players reached.")
        return
    game["players"].append(user_id)
    await message.reply(f"✅ {username} joined the game!")

@bot.on_message(filters.command("usepower") & filters.group)
async def use_power(client, message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if chat_id not in active_games:
        return
    game = active_games[chat_id]
    if game["state"] != "running":
        return
    args = message.text.split()
    if len(args) != 2 or not message.reply_to_message:
        await message.reply("Usage: /usepower @username")
        return
    target_user = message.reply_to_message.from_user
    if target_user.id == user_id:
        await message.reply("You cannot target yourself.")
        return
    role = game["roles"].get(user_id)
    target_role = game["roles"].get(target_user.id)
    user = get_user(user_id)
    last_used = game["cooldowns"].get(user_id)
    if last_used and datetime.utcnow() - last_used < power_cooldown:
        await message.reply("⏳ Power is cooling down.")
        return
    level = user.get("level", 1)
    power_list = role_powers.get(role, [])
    if not power_list:
        await bot.send_message(user_id, "🛑 You have no active power.")
        return
    power = power_list[min(level - 1, len(power_list) - 1)]
    game["cooldowns"][user_id] = datetime.utcnow()
    result = f"🔮 You used {power} on @{target_user.username or target_user.first_name}"
    if role == "Villain" and target_role == "Fairy":
        await bot.send_message(chat_id, f"💀 @{target_user.username or target_user.first_name} was defeated! 🎯 Attacked by: @{message.from_user.username or message.from_user.first_name}")
    elif role == "Fairy" and target_role == "Villain":
        await bot.send_message(chat_id, f"💀 @{target_user.username or target_user.first_name} was defeated! 🎯 Attacked by: @{message.from_user.username or message.from_user.first_name}")
    await bot.send_message(user_id, result)
    add_xp(user_id, 20)

@bot.on_message(filters.command("myxp"))
async def my_xp(client, message):
    user = get_user(message.from_user.id)
    await message.reply(f"📊 XP: {user['xp']} | Level: {user['level']} | Coins: {user.get('coins', 0)}")

@bot.on_message(filters.command("leaderboard"))
async def leaderboard(client, message):
    top = users_collection.find().sort("xp", -1).limit(5)
    text = "🌍 Global Leaderboard:\n"
    for i, user in enumerate(top, 1):
        text += f"{i}. {user['_id']} - Level {user.get('level',1)} XP: {user['xp']}\n"
    await message.reply(text)

@bot.on_message(filters.command("myleaderboard") & filters.group)
async def group_leaderboard(client, message):
    chat_id = str(message.chat.id)
    all_users = users_collection.find({f"group_stats.{chat_id}": {"$exists": True}})
    sorted_users = sorted(all_users, key=lambda u: u["group_stats"][chat_id]["xp"])
    text = "🏆 Group Leaderboard:\n"
    for i, user in enumerate(sorted_users[:5], 1):
        text += f"{i}. {user['_id']} - XP: {user['group_stats'][chat_id]['xp']}\n"
    await message.reply(text)

@bot.on_message(filters.command("instructions"))
async def instructions(client, message):
    await message.reply("""📜 **How to Play:**
1. Type /start in group
2. Everyone joins with /join
3. Game auto-starts with 4+ players in 1 minute
4. Roles: Fairy (defeat Villains), Villain (eliminate others), Commoner (vote only)
5. Use /usepower @username to act (DM only)
6. Gain XP to level up and unlock powers
7. Vote wisely using /vote to eliminate threats!
8. Earn coins, XP and level up with /upgrade
""")

print("🤖 Bot is running...")
bot.run()
