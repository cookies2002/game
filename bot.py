import asyncio
import random
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message
from pymongo import MongoClient

API_ID = 24977986  # your api id
API_HASH = "abc6095228862c7502397c928bd7999e"
BOT_TOKEN = "8098135944:AAF-zdTqjoYwW3fDdS7BY9zEX5BaiK235iY"
MONGO_URL = "mongodb+srv://xarwin2:xarwin2002@cluster0.qmetx2m.mongodb.net/?retryWrites=true&w=majority"

bot = Client("fairy_vs_villain_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
client = MongoClient(MONGO_URL)
db = client["fairy_vs_villain"]
users_collection = db["users"]

# Game state
players = {}
alive_players = set()
votes = {}
game_started = False
role_data = {}
power_used = set()

fairy_roles = [
    {"name": "Light Fairy", "power": "Reveal a Villain"},
    {"name": "Shield Fairy", "power": "Protect a player from attack"},
    {"name": "Heal Fairy", "power": "Revive a fallen Fairy"},
    {"name": "Stun Fairy", "power": "Stun a Villain for 1 turn"},
    {"name": "Wind Fairy", "power": "Deflect next attack"}
]

villain_roles = [
    {"name": "Dark Lord", "power": "Kill any Fairy instantly"},
    {"name": "Poisoner", "power": "Silence a player"},
    {"name": "Mind Bender", "power": "Confuse voters"},
    {"name": "Shadow", "power": "Hide from vote"},
    {"name": "Thief", "power": "Steal coins from a Fairy"}
]

commoner_role = {"name": "Commoner", "power": "Vote to eliminate Villains"}

# /start - Start a new game or get welcome instructions
@bot.on_message(filters.command("start"))
async def start_game(client, message):
    await message.reply("🌟 Welcome to *Fairy vs Villain*! Use /join to enter the game. Once 4+ join, game starts in 60 seconds! Use /help to learn commands.")

# /join - Join the current game lobby
@bot.on_message(filters.command("join"))
async def join_game(client, message):
    user = message.from_user
    if game_started:
        return await message.reply("❌ Game already started! Wait for the next round.")
    players[user.id] = user
    alive_players.add(user.id)
    await message.reply(f"✅ {user.mention} joined the game!")

    if len(players) == 4:
        await message.reply("⏳ 60 seconds until game starts. Others can still /join.")
        await asyncio.sleep(60)
        if len(players) >= 4:
            await assign_roles(client, message.chat.id)

# /leave - Leave the game lobby
@bot.on_message(filters.command("leave"))
async def leave_game(client, message):
    user_id = message.from_user.id
    if user_id in players:
        players.pop(user_id)
        alive_players.discard(user_id)
        await message.reply("👋 You left the game lobby.")
    else:
        await message.reply("❌ You are not in the game.")

async def assign_roles(client, chat_id):
    global game_started
    game_started = True
    all_players = list(players.keys())
    random.shuffle(all_players)
    roles = (["Fairy"] * 2) + (["Villain"] * 1) + (["Commoner"] * (len(all_players) - 3))
    random.shuffle(roles)

    for user_id, role in zip(all_players, roles):
        if role == "Fairy":
            role_info = random.choice(fairy_roles)
        elif role == "Villain":
            role_info = random.choice(villain_roles)
        else:
            role_info = commoner_role
        role_data[user_id] = {"type": role, "name": role_info["name"], "power": role_info["power"]}
        await client.send_message(user_id, f"🎭 You are *{role_info['name']}* ({role})\n✨ Power: {role_info['power']}\nUse /usepower in group to activate.")

    await client.send_message(chat_id, "🎮 Game started! Roles assigned. Let the battle begin!")

# /usepower - Use your role’s special power (DM & Group alerts)
@bot.on_message(filters.command("usepower"))
async def use_power(client, message):
    user_id = message.from_user.id
    if user_id not in alive_players or user_id in power_used:
        return await message.reply("❌ You can’t use your power now.")
    role = role_data.get(user_id)
    if not role:
        return await message.reply("❌ You don’t have a role yet.")

    power_used.add(user_id)
    if role['type'] == "Villain":
        target = random.choice([uid for uid in alive_players if uid != user_id])
        alive_players.remove(target)
        attacker = players[user_id]
        victim = players[target]
        await client.send_message(message.chat.id, f"💀 {victim.mention} was defeated! 🎯 Attacked by: {attacker.mention}")
        await client.send_message(user_id, "✅ You used your power successfully!")
    else:
        await client.send_message(user_id, f"✨ You used your power: {role['power']} (effect applied secretly)")

# /vote - Vote to eliminate a suspicious player 🗳️
@bot.on_message(filters.command("vote"))
async def vote_player(client, message):
    user = message.from_user
    parts = message.text.split()
    if len(parts) != 2:
        return await message.reply("❌ Usage: /vote @username")

    try:
        target_username = parts[1].lstrip("@")
        target_user = next((u for u in players.values() if u.username == target_username), None)
        if not target_user:
            return await message.reply("❌ Player not found.")
        votes[user.id] = target_user.id
        await message.reply(f"🗳️ {user.mention} voted to eliminate {target_user.mention}!")
        if len(votes) >= len(alive_players):
            result = max(set(votes.values()), key=list(votes.values()).count)
            if result in alive_players:
                alive_players.remove(result)
                await client.send_message(message.chat.id, f"💥 {players[result].mention} was eliminated by vote!")
                votes.clear()
    except:
        await message.reply("❌ Voting failed.")

# /myxp - Show your current XP and coins 📊
@bot.on_message(filters.command("myxp"))
async def my_xp(client, message):
    user = users_collection.find_one({"_id": message.from_user.id}) or {}
    xp = user.get("xp", 0)
    coins = user.get("coins", 0)
    await message.reply(f"📊 XP: {xp} | 💰 Coins: {coins}")

# /profile - View your full game profile and stats
@bot.on_message(filters.command("profile"))
async def profile(client, message):
    user_id = message.from_user.id
    user = users_collection.find_one({"_id": user_id}) or {}
    xp = user.get("xp", 0)
    coins = user.get("coins", 0)
    level = user.get("level", 1)
    await message.reply(f"👤 Profile\nLevel: {level}\nXP: {xp}\nCoins: {coins}")

# /upgrade - Upgrade your powers using XP and coins
@bot.on_message(filters.command("upgrade"))
async def upgrade(client, message):
    user_id = message.from_user.id
    user = users_collection.find_one({"_id": user_id}) or {}
    xp = user.get("xp", 0)
    coins = user.get("coins", 0)
    if xp >= 100 and coins >= 50:
        users_collection.update_one({"_id": user_id}, {"$inc": {"level": 1, "xp": -100, "coins": -50}}, upsert=True)
        await message.reply("🎉 Power upgraded successfully!")
    else:
        await message.reply("❌ Not enough XP or coins to upgrade.")

# /reset - Admin only: Reset the current game ⚙️
@bot.on_message(filters.command("reset"))
async def reset_game(client, message):
    if not message.from_user or not message.from_user.is_self and not message.from_user.id in [admin.id async for admin in bot.get_chat_members(message.chat.id) if admin.status == "creator"]:
        return await message.reply("❌ Only group admin can reset.")
    players.clear()
    alive_players.clear()
    votes.clear()
    role_data.clear()
    power_used.clear()
    global game_started
    game_started = False
    await message.reply("🔄 Game has been reset.")

# /help - Get game instructions, rules, and tips 📜
@bot.on_message(filters.command("help"))
async def help_command(client, message):
    await message.reply("""
🎮 *Fairy vs Villain Commands*:
/start - Start a new game or get welcome instructions
/join - Join the current game lobby
/leave - Leave the game lobby
/usepower - Use your role’s special power (DM & Group alerts)
/vote - Vote to eliminate a suspicious player 🗳️
/myxp - Show your current XP and coins 📊
/profile - View your full game profile and stats
/upgrade - Upgrade your powers using XP and coins
/reset - Admin only: Reset the current game ⚙️
/help - Get game instructions, rules, and tips 📜
/stats - See current game stats (alive/out/power used) 📈
/leaderboard - View global leaderboard 🌍
/myleaderboard - View this group’s leaderboard 🏆
""")

# /stats - See current game stats (alive/out/power used) 📈
@bot.on_message(filters.command("stats"))
async def stats(client, message):
    alive = [players[uid].mention for uid in alive_players]
    out = [players[uid].mention for uid in players if uid not in alive_players]
    used = [players[uid].mention for uid in power_used]
    await message.reply(f"📈 Stats:\nAlive: {', '.join(alive)}\nOut: {', '.join(out)}\nPower Used: {', '.join(used)}")

# /leaderboard - View global leaderboard 🌍
@bot.on_message(filters.command("leaderboard"))
async def leaderboard(client, message):
    top = users_collection.find().sort("xp", -1).limit(5)
    text = "🏆 Global Leaderboard:\n"
    for i, u in enumerate(top, 1):
        text += f"{i}. ID {u['_id']} - XP: {u.get('xp', 0)}\n"
    await message.reply(text)

# /myleaderboard - View this group’s leaderboard 🏆
@bot.on_message(filters.command("myleaderboard"))
async def group_leaderboard(client, message):
    chat_id = str(message.chat.id)
    group_users = users_collection.find({"group_id": chat_id}).sort("xp", -1).limit(5)
    text = f"🏆 Leaderboard for {message.chat.title or 'This Group'}:\n"
    for i, u in enumerate(group_users, 1):
        text += f"{i}. ID {u['_id']} - XP: {u.get('xp', 0)}\n"
    await message.reply(text)

bot.run()
