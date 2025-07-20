import os
import asyncio
import random
from pyrogram import Client, filters
from pyrogram.types import Message
from pymongo import MongoClient
from datetime import datetime, timedelta

# Environment variables
API_ID = int(os.getenv("API_ID", "24977986"))
API_HASH = os.getenv("API_HASH", "abc6095228862c7502397c928bd7999e")
BOT_TOKEN = os.getenv("BOT_TOKEN", "8098135944:AAF-zdTqjoYwW3fDdS7BY9zEX5BaiK235iY")
MONGO_URL = os.getenv("MONGO_URL", "mongodb+srv://xarwin2:xarwin2002@cluster0.qmetx2m.mongodb.net/?retryWrites=true&w=majority")

bot = Client("fairy_vs_villain", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
mongo = MongoClient(MONGO_URL)
db = mongo.fairy_vs_villain

active_games = {}

# Roles and Powers
roles_data = {
    "Fairy": ["Sparkle Beam", "Moonlight Shield", "Celestial Arrow"],
    "Villain": ["Dark Pulse", "Shadow Bind", "Terror Wave"],
    "Commoner": []
}

max_players = 15
min_players = 4

# XP & coins for actions
action_rewards = {
    "vote": 10,
    "power_use": 20,
    "survive": 15,
    "eliminate": 30
}

# Helper: Get or create user profile
def get_profile(user_id):
    user = db.users.find_one({"_id": user_id})
    if not user:
        user = {"_id": user_id, "xp": 0, "level": 1, "coins": 0}
        db.users.insert_one(user)
    return user

# Helper: Save user profile
def save_profile(user_id, xp=0, coins=0):
    user = get_profile(user_id)
    new_xp = user["xp"] + xp
    new_coins = user["coins"] + coins
    new_level = new_xp // 100 + 1
    db.users.update_one({"_id": user_id}, {"$set": {"xp": new_xp, "coins": new_coins, "level": new_level}})

# Command: /start
@bot.on_message(filters.command("start"))
async def start_game(client, message: Message):
    chat_id = message.chat.id
    if chat_id not in active_games:
        active_games[chat_id] = {"players": [], "state": "waiting", "cooldowns": {}, "votes": {}, "timer_task": None}
        await message.reply("🎮 Game started! Players, type /join to enter the game. Minimum 4 players required. Auto-start in 1 minute!")
        task = asyncio.create_task(timer_autostart(chat_id))
        active_games[chat_id]["timer_task"] = task
    else:
        await message.reply("⚠️ Game already active. Type /join to join.")

# Timer for autostart after 1 min
async def timer_autostart(chat_id):
    await asyncio.sleep(60)
    if chat_id in active_games and active_games[chat_id]["state"] == "waiting":
        await begin_game(chat_id)

# Command: /join
@bot.on_message(filters.command("join"))
async def join_game(client, message: Message):
    chat_id = message.chat.id
    user = message.from_user
    if chat_id not in active_games:
        await message.reply("❌ No game active. Type /start to begin.")
        return
    if user.id not in active_games[chat_id]["players"]:
        active_games[chat_id]["players"].append(user.id)
        await message.reply(f"✅ {user.mention} joined the game!")
        if len(active_games[chat_id]["players"]) >= max_players:
            await begin_game(chat_id)
    else:
        await message.reply("⚠️ You already joined.")

# Begin Game
async def begin_game(chat_id):
    game = active_games[chat_id]
    players = game["players"]
    if len(players) < min_players:
        return

    game["state"] = "active"
    roles = assign_roles(players)
    game["roles"] = roles
    game["cooldowns"] = {uid: datetime.min for uid in players}
    game["votes"] = {}

    for uid in players:
        role = roles[uid]
        power = get_power(role, get_profile(uid)["level"])
        text = f"👤 You are a {role}!\nPower: {power if power else 'None'}\n\nUse your power with /usepower @username\nVote a player with /vote @username\nUpgrade with /upgrade when you get enough XP."
        await bot.send_message(uid, text)

    await bot.send_message(chat_id, "🚀 Game has begun! Use /usepower and /vote to play.")

# Assign roles randomly
def assign_roles(players):
    roles = {}
    random.shuffle(players)
    count = len(players)
    fairies = players[:count//3]
    villains = players[count//3:2*count//3]
    commoners = players[2*count//3:]
    for uid in fairies:
        roles[uid] = "Fairy"
    for uid in villains:
        roles[uid] = "Villain"
    for uid in commoners:
        roles[uid] = "Commoner"
    return roles

# Get power based on role and level
def get_power(role, level):
    if role in roles_data and roles_data[role]:
        index = min(len(roles_data[role])-1, level // 3)
        return roles_data[role][index]
    return None

# Command: /usepower @username
@bot.on_message(filters.command("usepower"))
async def use_power(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    game = active_games.get(chat_id)

    if not game or game["state"] != "active":
        await message.reply("❌ Game not active.")
        return

    if user_id not in game["players"]:
        await message.reply("❌ You're not in the game.")
        return

    role = game["roles"].get(user_id)
    if role == "Commoner":
        await message.reply("🛡️ Commoners have no active power.")
        return

    if datetime.now() - game["cooldowns"][user_id] < timedelta(seconds=60):
        await message.reply("⏳ Your power is on cooldown. Try later.")
        return

    if len(message.command) < 2:
        await message.reply("⚠️ Usage: /usepower @username")
        return

    target_username = message.command[1].lstrip("@").lower()
    target_user_id = None

    for uid in game["players"]:
        try:
            user = await bot.get_users(uid)
            if user.username and user.username.lower() == target_username:
                target_user_id = uid
                break
        except:
            continue

    if not target_user_id:
        await message.reply("❌ Target user not found or not in game.")
        return

    game["cooldowns"][user_id] = datetime.now()

    # Success
    await bot.send_message(user_id, f"🎯 You used your power on @{target_username} successfully!")
    if role == "Villain" and game["roles"][target_user_id] == "Commoner":
        save_profile(user_id, xp=action_rewards["power_use"] + action_rewards["eliminate"], coins=10)
        save_profile(target_user_id, xp=0)
        await bot.send_message(chat_id, f"💀 @{target_username} was defeated! 🎯 Attacked by: @{message.from_user.username}")
    else:
        save_profile(user_id, xp=action_rewards["power_use"], coins=5)

# Command: /vote @username
@bot.on_message(filters.command("vote"))
async def vote_command(client, message: Message):
    chat_id = message.chat.id
    voter_id = message.from_user.id
    game = active_games.get(chat_id)

    if not game or game["state"] != "active":
        await message.reply("❌ Game not active.")
        return

    if voter_id not in game["players"]:
        await message.reply("❌ You're not in the game.")
        return

    if len(message.command) < 2:
        await message.reply("⚠️ Usage: /vote @username")
        return

    target_username = message.command[1].lstrip("@").lower()
    target_user_id = None

    for uid in game["players"]:
        try:
            user = await bot.get_users(uid)
            if user.username and user.username.lower() == target_username:
                target_user_id = uid
                break
        except:
            continue

    if not target_user_id:
        await message.reply("❌ Target user not found.")
        return

    game["votes"][voter_id] = target_user_id
    save_profile(voter_id, xp=action_rewards["vote"], coins=2)
    await message.reply(f"🗳️ Vote recorded for @{target_username}!")

# Command: /upgrade
@bot.on_message(filters.command("upgrade"))
async def upgrade_cmd(client, message: Message):
    user_id = message.from_user.id
    user = get_profile(user_id)
    cost = user["level"] * 50
    if user["coins"] >= cost:
        user["coins"] -= cost
        user["xp"] += 100
        db.users.update_one({"_id": user_id}, {"$set": {"coins": user["coins"], "xp": user["xp"]}})
        await message.reply(f"⬆️ You upgraded to Level {user['xp']//100 + 1}! 🎉")
    else:
        await message.reply("💰 Not enough coins to upgrade.")

# Command: /profile
@bot.on_message(filters.command("profile"))
async def profile_cmd(client, message: Message):
    user = get_profile(message.from_user.id)
    await message.reply(f"📊 Profile:\nLevel: {user['level']}\nXP: {user['xp']}\nCoins: {user['coins']}")

# Command: /myxp
@bot.on_message(filters.command("myxp"))
async def myxp_cmd(client, message: Message):
    user = get_profile(message.from_user.id)
    await message.reply(f"📈 XP: {user['xp']} | Level: {user['level']}")

# Command: /leaderboard
@bot.on_message(filters.command("leaderboard"))
async def leaderboard(client, message: Message):
    top = db.users.find().sort("xp", -1).limit(10)
    text = "🌍 Global Leaderboard:\n"
    for i, u in enumerate(top, start=1):
        try:
            user = await bot.get_users(u["_id"])
            text += f"{i}. {user.first_name} - {u['xp']} XP\n"
        except:
            continue
    await message.reply(text)

# Command: /myleaderboard
@bot.on_message(filters.command("myleaderboard"))
async def group_leaderboard(client, message: Message):
    chat_id = message.chat.id
    if chat_id > 0:
        await message.reply("❌ This command only works in groups.")
        return

    game = active_games.get(chat_id)
    if not game:
        await message.reply("❌ No game data.")
        return

    players = game["players"]
    text = "🏆 Group Leaderboard:\n"
    for i, uid in enumerate(sorted(players, key=lambda u: get_profile(u)["xp"], reverse=True), start=1):
        try:
            user = await bot.get_users(uid)
            text += f"{i}. {user.first_name} - {get_profile(uid)['xp']} XP\n"
        except:
            continue
    await message.reply(text)

# Command: /instructions
@bot.on_message(filters.command("instructions"))
async def instructions_cmd(client, message: Message):
    await message.reply("📜 How to Play:\n- Join game with /join\n- Fairies/Villains have powers\n- Use power: /usepower @username\n- Commoners support with votes\n- Level up to unlock better powers!\n- XP via votes, survival, attacks\n- View stats: /myxp /profile\n- Upgrade: /upgrade\n- Win as a team! 🧚‍♀️👿")

bot.run()
