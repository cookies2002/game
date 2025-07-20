# bot.py — Fairy vs Villain Game Bot

import random
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from config import BOT_TOKEN, API_ID, API_HASH
from pymongo import MongoClient

# MongoDB Setup
client = MongoClient("mongodb+srv://xarwin2:xarwin2002@cluster0.qmetx2m.mongodb.net/?retryWrites=true&w=majority")
db = client["fairy_vs_villain"]
users_col = db["users"]

bot = Client("fairy_villain_bot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

players = []
game_started = False
group_id = None
roles = {}
player_status = {}
used_power = set()
votes = {}

fairy_characters = [
    ("🌟 Fairy of Light", "Reveal a Villain"),
    ("🧚 Nature Fairy", "Revive one eliminated Fairy"),
    ("💫 Dream Fairy", "Silence one Villain for 1 round"),
    ("🔥 Flame Fairy", "Burn one Villain - instant defeat"),
    ("🌈 Rainbow Fairy", "Shield a teammate for 1 round"),
]

villain_characters = [
    ("💀 Shadow Reaper", "Kill a Fairy at night"),
    ("🕷️ Web of Lies", "Confuse Fairy role once"),
    ("🩸 Blood Mage", "Drain XP from another player"),
    ("⚡ Dark Blaster", "Stun a player (skip vote)"),
    ("🧠 Mind Hacker", "View another player’s role"),
]

commoners = ["🧍 Commoner"] * 10  # Up to 15 players

# Utility Functions

def get_user(user_id):
    return users_col.find_one({"_id": user_id})

def create_or_update_user(user_id, username):
    user = get_user(user_id)
    if not user:
        users_col.insert_one({"_id": user_id, "username": username, "xp": 0, "coins": 0, "level": 1})
    else:
        users_col.update_one({"_id": user_id}, {"$set": {"username": username}})

def add_xp(user_id, amount):
    users_col.update_one({"_id": user_id}, {"$inc": {"xp": amount, "coins": amount}})

# Start Command
@bot.on_message(filters.command("start"))
async def start_game(client, message: Message):
    await message.reply(
        "🌟 Welcome to *Fairy vs Villain*!\n\nUse /join to enter the game lobby. When 4+ players join, game will auto-start in 1 minute. Max 15 players allowed.\n\nUse /help for rules and guidance."
    )

# Help Command
@bot.on_message(filters.command("help"))
async def help_cmd(client, message: Message):
    await message.reply(
        "📜 *Game Instructions*\n\n- Players will be randomly assigned as 🌟 Fairies, 💀 Villains, or 🧍 Commoners.\n- Use /usepower to activate your role’s ability (Fairies/Villains only).\n- Use /vote to eliminate someone suspicious.\n- Earn XP & Coins via actions and wins.\n- Upgrade powers using /upgrade.\n\nCommands: /join /leave /profile /myxp /vote /usepower /upgrade /reset /stats /leaderboard /myleaderboard"
    )

# Join Command
@bot.on_message(filters.command("join"))
async def join_game(client, message: Message):
    global players, group_id, game_started
    if game_started:
        await message.reply("🚫 Game already started!")
        return

    user = message.from_user
    if user.id in players:
        await message.reply("✅ You already joined!")
        return

    players.append(user.id)
    create_or_update_user(user.id, user.username)
    group_id = message.chat.id

    await message.reply(f"🙋 {user.mention} joined the game! ({len(players)}/15)")

    if len(players) == 4:
        await message.reply("⏳ 4 players joined! Game starting in 60 seconds... Others can still /join!")
        await asyncio.sleep(60)
        if len(players) >= 4:
            await start_roles(client)

# Leave Command
@bot.on_message(filters.command("leave"))
async def leave_game(client, message: Message):
    user = message.from_user
    if user.id in players:
        players.remove(user.id)
        await message.reply("👋 You left the game lobby.")

# Role Assignment
async def start_roles(client):
    global game_started, roles, player_status
    game_started = True
    random.shuffle(players)

    total = len(players)
    num_fairies = max(1, total // 3)
    num_villains = max(1, total // 4)

    fairy_ids = players[:num_fairies]
    villain_ids = players[num_fairies:num_fairies + num_villains]
    commoner_ids = players[num_fairies + num_villains:]

    for uid in fairy_ids:
        character, power = random.choice(fairy_characters)
        roles[uid] = ("Fairy", character, power)
        player_status[uid] = "alive"
        await client.send_message(uid, f"🌟 You are a *Fairy*!\nRole: {character}\nPower: {power}\nUse /usepower in group to activate it!")

    for uid in villain_ids:
        character, power = random.choice(villain_characters)
        roles[uid] = ("Villain", character, power)
        player_status[uid] = "alive"
        await client.send_message(uid, f"💀 You are a *Villain*!\nRole: {character}\nPower: {power}\nUse /usepower in group to activate it!")

    for uid in commoner_ids:
        roles[uid] = ("Commoner", "🧍 Commoner", "No special power")
        player_status[uid] = "alive"
        await client.send_message(uid, f"🧍 You are a *Commoner*. Help Fairies by voting Villains!")

    await client.send_message(group_id, "🎮 Game Started! Roles assigned. Use /vote or /usepower to begin the battle!")

# Use Power
@bot.on_message(filters.command("usepower"))
async def use_power(client, message: Message):
    user_id = message.from_user.id
    if user_id in used_power:
        await client.send_message(user_id, "⚠️ You already used your power.")
        return

    if roles[user_id][0] not in ["Fairy", "Villain"]:
        await client.send_message(user_id, "❌ Only Fairies and Villains have powers!")
        return

    used_power.add(user_id)
    add_xp(user_id, 10)
    await client.send_message(user_id, f"✅ You used your power: {roles[user_id][2]}!")
    await client.send_message(group_id, f"🎯 Power used by {message.from_user.mention}!")

# Vote
@bot.on_message(filters.command("vote"))
async def vote_cmd(client, message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("Usage: /vote @username")
        return

    username = parts[1].lstrip("@")
    user_id = None
    for uid in players:
        if users_col.find_one({"_id": uid, "username": username}):
            user_id = uid
            break

    if not user_id:
        await message.reply("❌ User not found in game.")
        return

    if player_status.get(user_id) != "alive":
        await message.reply("⚰️ Player already defeated.")
        return

    votes[user_id] = votes.get(user_id, 0) + 1
    await message.reply(f"🗳️ You voted to eliminate @{username}!")

# Profile
@bot.on_message(filters.command("profile"))
async def profile_cmd(client, message: Message):
    user = get_user(message.from_user.id)
    role_info = roles.get(message.from_user.id, ("None", "-", "-"))
    await message.reply(
        f"👤 *Your Profile*\nRole: {role_info[0]}\nXP: {user['xp']}\nCoins: {user['coins']}\nLevel: {user['level']}"
    )

# My XP
@bot.on_message(filters.command("myxp"))
async def myxp(client, message: Message):
    user = get_user(message.from_user.id)
    await message.reply(f"📊 XP: {user['xp']} | Coins: {user['coins']}")

# Upgrade
@bot.on_message(filters.command("upgrade"))
async def upgrade_cmd(client, message: Message):
    user = get_user(message.from_user.id)
    if user['xp'] >= 100:
        users_col.update_one({"_id": user['_id']}, {"$inc": {"level": 1, "xp": -100, "coins": -50}})
        await message.reply("⬆️ Power upgraded! Level increased!")
    else:
        await message.reply("❌ Not enough XP. Need 100 XP to upgrade.")

# Reset
@bot.on_message(filters.command("reset"))
async def reset_game(client, message: Message):
    if not message.from_user.is_chat_admin():
        await message.reply("❌ Only admins can reset the game.")
        return
    global players, roles, used_power, votes, player_status, game_started
    players = []
    roles = {}
    used_power = set()
    votes = {}
    player_status = {}
    game_started = False
    await message.reply("🔁 Game reset.")

# Stats
@bot.on_message(filters.command("stats"))
async def stats_cmd(client, message: Message):
    alive = [uid for uid in players if player_status.get(uid) == "alive"]
    out = [uid for uid in players if player_status.get(uid) != "alive"]
    await message.reply(f"📈 Stats:\nAlive: {len(alive)}\nEliminated: {len(out)}\nPower used: {len(used_power)}")

# Leaderboard
@bot.on_message(filters.command("leaderboard"))
async def leaderboard_cmd(client, message: Message):
    top_users = users_col.find().sort("xp", -1).limit(5)
    board = "🌍 *Global Leaderboard*\n"
    for idx, user in enumerate(top_users, 1):
        board += f"{idx}. @{user['username']} - {user['xp']} XP\n"
    await message.reply(board)

# Group Leaderboard
@bot.on_message(filters.command("myleaderboard"))
async def my_leaderboard(client, message: Message):
    chat_users = [uid for uid in players]
    user_data = users_col.find({"_id": {"$in": chat_users}}).sort("xp", -1)
    board = "🏆 *Group Leaderboard*\n"
    for idx, user in enumerate(user_data, 1):
        board += f"{idx}. @{user['username']} - {user['xp']} XP\n"
    await message.reply(board)

bot.run()
