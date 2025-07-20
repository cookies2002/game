import asyncio
import random
import os
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatType
from pymongo import MongoClient
from datetime import datetime

# === Config === #
API_ID = int(os.getenv("API_ID", 24977986))
API_HASH = os.getenv("API_HASH", "abc6095228862c7502397c928bd7999e")
BOT_TOKEN = os.getenv("BOT_TOKEN", "8098135944:AAF-zdTqjoYwW3fDdS7BY9zEX5BaiK235iY")
MONGO_URL = os.getenv("MONGO_URL", "mongodb+srv://xarwin2:xarwin2002@cluster0.qmetx2m.mongodb.net/?retryWrites=true&w=majority")

bot = Client("fairy_vs_villain", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
mongo = MongoClient(MONGO_URL)
db = mongo.fairy_game

# === In-Memory Game Data === #
current_games = {}
player_roles = {}
player_votes = {}
power_used = {}

# === Role Definitions === #
fairy_roles = ["Light Fairy", "Healing Fairy", "Shield Fairy", "Speed Fairy", "Illusion Fairy"]
villain_roles = ["Dark Lord", "Shadow Witch", "Venom Beast", "Curse Master", "Night Hunter"]
commoner_roles = ["Village Guardian", "Helper", "Watcher", "Spy", "Supporter"]

role_powers = {
    "Light Fairy": "Eliminate one Villain in light beam.",
    "Healing Fairy": "Revive one eliminated Fairy.",
    "Shield Fairy": "Protect one Fairy for 1 round.",
    "Speed Fairy": "Use double power for 1 round.",
    "Illusion Fairy": "Confuse one Villain vote.",
    "Dark Lord": "Kill any Fairy in darkness.",
    "Shadow Witch": "Block Fairy powers for 1 round.",
    "Venom Beast": "Poison and slowly kill a Fairy.",
    "Curse Master": "Curse a Fairy to silence.",
    "Night Hunter": "Detect and attack hidden players.",
    "Village Guardian": "Can vote to eliminate villains only.",
    "Helper": "Supports voting process.",
    "Watcher": "Keeps track of player status.",
    "Spy": "Receives DM alerts if Villain votes.",
    "Supporter": "Boosts Fairy XP passively."
}

# === Helper Functions === #
def get_mention(user):
    return f"@{user.username}" if user.username else f"{user.first_name}"

async def assign_roles(chat_id):
    players = current_games[chat_id]['players']
    random.shuffle(players)
    n = len(players)

    fairies = players[:n//3]
    villains = players[n//3:2*n//3]
    commoners = players[2*n//3:]

    for user_id in fairies:
        role = random.choice(fairy_roles)
        player_roles[user_id] = role
        await bot.send_message(user_id, f"🌟 You're a **Fairy**!
Role: {role}
Power: {role_powers[role]}
Use /usepower to activate your power secretly.")

    for user_id in villains:
        role = random.choice(villain_roles)
        player_roles[user_id] = role
        await bot.send_message(user_id, f"😈 You're a **Villain**!
Role: {role}
Power: {role_powers[role]}
Use /usepower to attack or block others.")

    for user_id in commoners:
        role = random.choice(commoner_roles)
        player_roles[user_id] = role
        await bot.send_message(user_id, f"🧑 You're a **Commoner**!
Role: {role}
Power: {role_powers[role]}
Vote with /vote to help eliminate villains.")

@bot.on_message(filters.command("start") & filters.group)
async def start_game(client, message: Message):
    chat_id = message.chat.id
    if chat_id not in current_games:
        current_games[chat_id] = {"players": [], "started": False}
        await message.reply("🎮 Welcome to *Fairy vs Villain*! Use /join to enter the lobby. Game will auto-start when 4 players join.")

@bot.on_message(filters.command("join") & filters.group)
async def join_game(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if chat_id not in current_games:
        current_games[chat_id] = {"players": [], "started": False}

    if user_id in current_games[chat_id]['players']:
        await message.reply("🔔 You already joined the game.")
        return

    current_games[chat_id]['players'].append(user_id)
    await message.reply(f"✅ {get_mention(message.from_user)} joined the game!")

    if len(current_games[chat_id]['players']) == 4:
        await message.reply("⏳ Minimum players reached! Game will start in 60 seconds... Others can still join.")
        await asyncio.sleep(60)
        if not current_games[chat_id]['started']:
            current_games[chat_id]['started'] = True
            await assign_roles(chat_id)
            await message.reply("🚀 Game started! Roles have been secretly assigned via DM.")

@bot.on_message(filters.command("usepower") & filters.group)
async def use_power(client, message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    if user_id not in player_roles:
        await message.reply("❌ You have no power to use.")
        return

    role = player_roles[user_id]
    action = f"{get_mention(message.from_user)} used **{role}** power!"
    await bot.send_message(user_id, f"✅ You used your power: {role_powers[role]}")

    if "kill" in role_powers[role].lower() or "eliminate" in role_powers[role].lower():
        target = random.choice([uid for uid in current_games[chat_id]['players'] if uid != user_id])
        current_games[chat_id]['players'].remove(target)
        power_used[chat_id] = power_used.get(chat_id, 0) + 1
        mention_target = await client.get_users(target)
        await message.reply(f"💀 {get_mention(mention_target)} was eliminated!
🎯 Attacked by: {get_mention(message.from_user)}")

@bot.on_message(filters.command("vote") & filters.group)
async def vote_player(client, message: Message):
    voter_id = message.from_user.id
    chat_id = message.chat.id
    if voter_id not in player_roles:
        await message.reply("❌ You cannot vote right now.")
        return

    if len(message.command) < 2:
        await message.reply("Usage: /vote user_id")
        return

    try:
        target_id = int(message.command[1])
        if target_id not in current_games[chat_id]['players']:
            await message.reply("❌ Invalid target.")
            return
        player_votes[voter_id] = target_id
        await message.reply(f"🗳️ You voted to eliminate {get_mention(await client.get_users(target_id))}!")
    except Exception:
        await message.reply("⚠️ Error in voting. Provide a valid user ID.")

@bot.on_message(filters.command("stats") & filters.group)
async def show_stats(client, message: Message):
    chat_id = message.chat.id
    alive = len(current_games.get(chat_id, {}).get("players", []))
    eliminated = len(player_roles) - alive
    used = power_used.get(chat_id, 0)
    await message.reply(f"📈 Stats:\nAlive: {alive}\nEliminated: {eliminated}\nPower used: {used}")

@bot.on_message(filters.command("profile"))
async def profile(client, message):
    user_id = message.from_user.id
    user_data = db.users.find_one({"user_id": user_id}) or {"xp": 0, "coins": 0, "level": 1}
    await message.reply(f"👤 Profile:\nXP: {user_data['xp']}\nCoins: {user_data['coins']}\nLevel: {user_data['level']}")

@bot.on_message(filters.command("myxp"))
async def my_xp(client, message):
    user_id = message.from_user.id
    user_data = db.users.find_one({"user_id": user_id}) or {"xp": 0, "coins": 0}
    await message.reply(f"📊 Your XP: {user_data['xp']} | Coins: {user_data['coins']}")

@bot.on_message(filters.command("upgrade"))
async def upgrade(client, message):
    user_id = message.from_user.id
    user = db.users.find_one({"user_id": user_id}) or {"xp": 0, "coins": 0, "level": 1}
    if user['xp'] >= 100 and user['coins'] >= 50:
        db.users.update_one({"user_id": user_id}, {"$inc": {"level": 1, "xp": -100, "coins": -50}}, upsert=True)
        await message.reply("⬆️ You upgraded your power! Level increased by 1.")
    else:
        await message.reply("❌ Not enough XP or coins. Need 100 XP & 50 Coins.")

@bot.on_message(filters.command("help"))
async def help_command(client, message):
    await message.reply("""
📜 *Fairy vs Villain Game Commands:*

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

@bot.on_message(filters.command("reset") & filters.user([123456789]))  # Replace with admin ID
async def reset_game(client, message: Message):
    chat_id = message.chat.id
    current_games.pop(chat_id, None)
    player_roles.clear()
    player_votes.clear()
    power_used.pop(chat_id, None)
    await message.reply("🔁 Game reset.")

bot.run()
