import os
from pyrogram import Client, filters
from pyrogram.types import Message
from pymongo import MongoClient
from dotenv import load_dotenv
import asyncio
import random
from datetime import datetime, timedelta

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
MONGO_URL = os.getenv("MONGO_URL")

bot = Client("fairy_vs_villain_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
mongo = MongoClient(MONGO_URL)
db = mongo.fairy_vs_villain
users = db.users

active_games = {}
power_cooldowns = {}

roles_data = {
    "Fairy": [
        {"power": "Sparkle Beam", "desc": "Attack a villain. (LVL 1)"},
        {"power": "Moonlight Shield", "desc": "Protect one ally. (LVL 2)"},
        {"power": "Celestial Arrow", "desc": "Guaranteed attack hit. (LVL 3+)"},
    ],
    "Villain": [
        {"power": "Shadow Strike", "desc": "Attack a player. (LVL 1)"},
        {"power": "Dark Cloak", "desc": "Avoid voting once. (LVL 2)"},
        {"power": "Chaos Rage", "desc": "Kill and silence. (LVL 3+)"},
    ],
    "Commoner": [
        {"power": "Vote", "desc": "Vote during elimination. (LVL 1+)"},
        {"power": "Wisdom Glance", "desc": "Detect one role. (LVL 3+)"}
    ]
}

async def get_or_create_user(user_id):
    user = users.find_one({"_id": user_id})
    if not user:
        user = {"_id": user_id, "xp": 0, "coins": 0, "level": 1, "wins": 0, "losses": 0, "role": None, "group": None}
        users.insert_one(user)
    return user

def assign_roles(player_ids):
    num_players = len(player_ids)
    num_villains = max(1, num_players // 4)
    num_fairies = max(1, num_players // 3)
    num_commoners = num_players - num_villains - num_fairies
    roles_pool = ["Villain"] * num_villains + ["Fairy"] * num_fairies + ["Commoner"] * num_commoners
    random.shuffle(roles_pool)
    return dict(zip(player_ids, roles_pool))

async def begin_game(chat_id):
    game = active_games[chat_id]
    players = game["players"]
    roles = assign_roles(players)
    game["roles"] = roles
    game["state"] = "started"

    for player_id, role in roles.items():
        user = await get_or_create_user(player_id)
        users.update_one({"_id": player_id}, {"$set": {"role": role, "group": chat_id}})
        level = user.get("level", 1)
        power_info = roles_data[role][min(level-1, len(roles_data[role])-1)]
        text = f"👤 You are a {role}!
💥 Power: {power_info['power']}
📘 Description: {power_info['desc']}

Use /usepower @username to activate your power.")
        try:
            await bot.send_message(player_id, text)
        except:
            pass
    await bot.send_message(chat_id, "🎮 Game started! Roles have been sent via DM.")

@bot.on_message(filters.command("start"))
async def start_game(client, message):
    chat_id = message.chat.id
    if chat_id in active_games:
        return await message.reply("🚫 Game already active in this group.")
    active_games[chat_id] = {"players": [], "state": "waiting"}
    await message.reply("🎉 Game created! Players, type /join to participate.")

    await asyncio.sleep(60)
    if len(active_games[chat_id]["players"]) >= 4:
        await begin_game(chat_id)
    else:
        await message.reply("⏳ Not enough players joined. Game cancelled.")
        del active_games[chat_id]

@bot.on_message(filters.command("join"))
async def join_game(client, message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if chat_id not in active_games or active_games[chat_id]["state"] != "waiting":
        return await message.reply("❌ No active game to join. Use /start first.")
    if user_id in active_games[chat_id]["players"]:
        return await message.reply("✅ You already joined!")
    active_games[chat_id]["players"].append(user_id)
    await message.reply(f"👤 {message.from_user.first_name} joined the game!")

@bot.on_message(filters.command("usepower"))
async def use_power(client, message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if chat_id not in active_games or active_games[chat_id]["state"] != "started":
        return await message.reply("❌ No active game.")
    target_username = message.text.split(" ")[-1].replace("@", "")
    target_id = None

    for user in await bot.get_chat_members(chat_id):
        if user.user.username == target_username:
            target_id = user.user.id
            break

    if not target_id:
        return await message.reply("❌ User not found or not in group.")

    user_data = await get_or_create_user(user_id)
    role = user_data.get("role")
    level = user_data.get("level", 1)
    if role == "Commoner":
        return await message.reply("🚫 Commoners cannot attack!")

    cooldown_key = f"{user_id}_{chat_id}"
    now = datetime.now()
    last_used = power_cooldowns.get(cooldown_key)
    if last_used and now - last_used < timedelta(seconds=60):
        return await message.reply("⏳ Power on cooldown. Wait a bit!")
    power_cooldowns[cooldown_key] = now

    # Simplified effect (actual logic like kill, silence can be added)
    if random.random() < 0.6:
        await message.reply(f"💀 @{target_username} was defeated! 🎯 Attacked by: @{message.from_user.username}")
    try:
        await client.send_message(user_id, f"✅ Your power was used on @{target_username}")
    except:
        pass

@bot.on_message(filters.command("myxp"))
async def my_xp(client, message):
    user_id = message.from_user.id
    user = await get_or_create_user(user_id)
    xp = user.get("xp", 0)
    level = user.get("level", 1)
    coins = user.get("coins", 0)
    await message.reply(f"📊 XP: {xp}\n🏅 Level: {level}\n💰 Coins: {coins}")

@bot.on_message(filters.command("upgrade"))
async def upgrade(client, message):
    user_id = message.from_user.id
    user = await get_or_create_user(user_id)
    level = user.get("level", 1)
    coins = user.get("coins", 0)
    cost = level * 10
    if coins < cost:
        return await message.reply(f"💸 Not enough coins! Need {cost} to upgrade.")
    users.update_one({"_id": user_id}, {"$inc": {"level": 1, "coins": -cost}})
    await message.reply(f"🎉 Level Up! You are now level {level+1}. 💰 Coins left: {coins - cost}")

@bot.on_message(filters.command("profile"))
async def profile(client, message):
    user_id = message.from_user.id
    user = await get_or_create_user(user_id)
    await message.reply(f"📄 Profile\nLevel: {user.get('level')}\nXP: {user.get('xp')}\nCoins: {user.get('coins')}\nWins: {user.get('wins')}\nLosses: {user.get('losses')}")

@bot.on_message(filters.command("leaderboard"))
async def leaderboard(client, message):
    top = users.find().sort("xp", -1).limit(5)
    text = "🌍 Global Leaderboard\n"
    for i, user in enumerate(top, 1):
        text += f"{i}. ID: {user['_id']} - XP: {user['xp']}\n"
    await message.reply(text)

@bot.on_message(filters.command("myleaderboard"))
async def my_leaderboard(client, message):
    group_id = message.chat.id
    top = users.find({"group": group_id}).sort("xp", -1).limit(5)
    text = "🏆 Group Leaderboard\n"
    for i, user in enumerate(top, 1):
        text += f"{i}. ID: {user['_id']} - XP: {user['xp']}\n"
    await message.reply(text)

@bot.on_message(filters.command("instructions"))
async def instructions(client, message):
    text = (
        "📜 *Game Instructions*\n\n"
        "- /start: Begin game\n"
        "- /join: Join game\n"
        "- /usepower @username: Use power\n"
        "- /vote @username: Vote\n"
        "- /myxp, /upgrade, /profile\n"
        "- XP for winning, voting, surviving\n"
        "- Coins used for leveling up\n"
        "- Fairies & Villains gain new powers at Level 2, 3\n"
        "- Commoners help vote and can earn roles later"
    )
    await message.reply(text)

bot.run()
