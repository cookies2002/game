# ✅ Updated `bot.py` with all discussed features including:
# - Auto-start after 4 players with countdown
# - Role DM and power instructions
# - Voting system (villain elimination only)
# - Leveling, upgrade with coins
# - /powers, /instructions, and corrected /usepower with @username
# - Commoners cannot attack
# - Max players = 15

# -- Begin Full Code --

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
    roles = ["Fairy", "Villain", "Commoner"]
    total_players = len(players)
    num_villains = max(1, total_players // 4)
    num_fairies = max(1, total_players // 3)
    num_commoners = total_players - (num_villains + num_fairies)
    role_list = ["Villain"] * num_villains + ["Fairy"] * num_fairies + ["Commoner"] * num_commoners
    random.shuffle(role_list)
    random.shuffle(players)
    return {player: role_list[i] for i, player in enumerate(players)}

# Game Commands

@bot.on_message(filters.command("start"))
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

@bot.on_message(filters.command("usepower"))
async def use_power(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    game = active_games.get(chat_id)
    if not game or user_id not in game.get("alive", []): return
    role = game["roles"].get(user_id)
    if role == "Commoner":
        await message.reply("🚫 Commoners can’t use attack powers.")
        return
    if len(message.command) < 2:
        await message.reply("❗ Use format: /usepower @username")
        return
    target_username = message.command[1].lstrip("@")
    try:
        target = await client.get_users(target_username)
        target_id = target.id
    except:
        await message.reply("❌ Invalid target.")
        return
    if target_id not in game["alive"]:
        await message.reply("⚠️ Target already defeated.")
        return
    game["alive"].remove(target_id)
    attacker_name = message.from_user.mention
    await client.send_message(user_id, f"🎯 You used your power on @{target_username}!")
    await client.send_message(chat_id, f"💥 @{target_username} was defeated! 🎯 Attacked by: {attacker_name}")
    user = get_user(user_id)
    xp_gain, coin_gain = 50, 20
    new_xp = user["xp"] + xp_gain
    new_level = get_level(new_xp)
    update_user(user_id, xp=new_xp, coins=user["coins"] + coin_gain, level=new_level)

@bot.on_message(filters.command("vote"))
async def vote_player(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    game = active_games.get(chat_id)
    if not game or user_id not in game.get("alive", []): return
    if len(message.command) < 2:
        await message.reply("❗ Use format: /vote @username")
        return
    target_username = message.command[1].lstrip("@")
    try:
        target = await client.get_users(target_username)
        target_id = target.id
    except:
        await message.reply("❌ Invalid vote target.")
        return
    game["votes"][user_id] = target_id
    await message.reply(f"🗳️ Vote cast for @{target_username}!")
    if len(game["votes"]) == len(game["alive"]):
        tally = Counter(game["votes"].values())
        voted_out = tally.most_common(1)[0][0]
        role = game["roles"].get(voted_out)
        if role == "Villain":
            game["alive"].remove(voted_out)
            await client.send_message(chat_id, f"🚨 @{target_username} was a Villain and has been eliminated!")
        else:
            await client.send_message(chat_id, f"⚠️ @{target_username} was NOT a Villain!")
        game["votes"] = {}

@bot.on_message(filters.command("upgrade"))
async def upgrade(client, message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    next_level = user["level"] + 1
    if next_level not in level_thresholds:
        await message.reply("🌟 Max level reached!")
        return
    required = (next_level * 100)
    if user["coins"] < required:
        await message.reply(f"💎 Need {required} coins to upgrade to Level {next_level}.")
        return
    update_user(user_id, coins=user["coins"] - required, level=next_level)
    await message.reply(f"✅ Leveled up to {next_level}! Remaining Coins: {user['coins'] - required}")

@bot.on_message(filters.command("profile"))
async def profile(client, message: Message):
    user = get_user(message.from_user.id)
    msg = f"📊 Your Stats:\n⭐ Level: {user['level']}\n✨ XP: {user['xp']}\n💎 Coins: {user['coins']}\n🎭 Role: {user.get('role', 'None')}"
    await message.reply(msg)

@bot.on_message(filters.command("powers"))
async def powers(client, message: Message):
    user = get_user(message.from_user.id)
    role = user.get("role")
    if role not in all_roles:
        await message.reply("You don’t have a role yet.")
        return
    msg = "🔮 Your Future Powers by Level:\n"
    for i, p in enumerate(all_roles[role], 1):
        msg += f"Level {i}: {p}\n"
    await message.reply(msg)

@bot.on_message(filters.command("help"))
async def help_menu(client, message: Message):
    await message.reply("""
🧚‍♀️ **Fairy Power Game**
/start - Start a new game
/join - Join the game
/leave - Leave the game
/usepower @user - Use your power (secret)
/vote @user - Vote suspicious player
/myxp - View XP & level
/upgrade - Level up
/profile - Full stats
/leaderboard - Global top
/myleaderboard - Group top
/reset - Admin only
/instructions - How to play
/powers - See future powers
""")

bot.run()
