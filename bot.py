import os
import asyncio
import random
from pyrogram import Client, filters
from pyrogram.types import Message
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta

# ========== CONFIG ==========
API_ID = int(os.getenv("API_ID", 123456))
API_HASH = os.getenv("API_HASH", "your-api-hash")
BOT_TOKEN = os.getenv("BOT_TOKEN", "your-bot-token")
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")

bot = Client("fairy_vs_villain", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
mongo = AsyncIOMotorClient(MONGO_URL)
db = mongo.fairy_game

# ========== GAME VARIABLES ==========
active_games = {}
players = {}
game_state = {}
player_roles = {}
player_powers = {}
power_cooldowns = {}

# ========== ROLE DEFINITIONS ==========
ROLES = ["Fairy", "Villain", "Commoner"]
MAX_PLAYERS = 15
MIN_PLAYERS = 4

FAIRY_POWERS = ["Sparkle Beam", "Moonlight Shield", "Celestial Arrow"]
VILLAIN_POWERS = ["Shadow Slash", "Dark Curse", "Fear Blast"]

LEVELS = {
    1: {"xp": 0, "coins": 0},
    2: {"xp": 100, "coins": 50},
    3: {"xp": 250, "coins": 100},
    4: {"xp": 500, "coins": 150},
    5: {"xp": 1000, "coins": 300}
}

# ========== UTILITY FUNCTIONS ==========
async def update_user(user_id, update):
    await db.users.update_one({"_id": user_id}, {"$set": update}, upsert=True)

def assign_roles(player_ids):
    roles = ["Fairy"] + ["Villain"] + ["Commoner"] * (len(player_ids) - 2)
    random.shuffle(roles)
    return dict(zip(player_ids, roles))

def get_power(role):
    if role == "Fairy":
        return random.choice(FAIRY_POWERS)
    elif role == "Villain":
        return random.choice(VILLAIN_POWERS)
    else:
        return None

async def send_role_dm(client, user_id, role, power):
    text = f"👤 You are a {role}!\n"
    if role == "Fairy":
        text += f"✨ Power: {power}\nUse /usepower to help your team in secret."
    elif role == "Villain":
        text += f"😈 Power: {power}\nUse /usepower wisely to eliminate enemies."
    else:
        text += "🙋 You are a Commoner!\nYou can vote to help Fairies."
    await client.send_message(user_id, text)

async def award_xp_and_coins(user_id, xp=20, coins=10):
    user = await db.users.find_one({"_id": user_id})
    if not user:
        user = {"_id": user_id, "xp": 0, "coins": 0, "level": 1}
    user["xp"] += xp
    user["coins"] += coins

    # Level up
    for lvl in sorted(LEVELS.keys()):
        if user["xp"] >= LEVELS[lvl]["xp"]:
            user["level"] = lvl

    await db.users.update_one({"_id": user_id}, {"$set": user}, upsert=True)

# ========== COMMAND HANDLERS ==========

@bot.on_message(filters.command("start"))
async def start_game(client, message: Message):
    chat_id = message.chat.id
    if chat_id in active_games:
        await message.reply("🕹️ Game already running!")
        return
    active_games[chat_id] = []
    await message.reply("🎮 Game starting! Type /join to participate. Waiting 1 minute or minimum 4 players...")
    await asyncio.sleep(60)
    if len(active_games[chat_id]) >= MIN_PLAYERS:
        await begin_game(chat_id)
    else:
        del active_games[chat_id]
        await message.reply("❌ Not enough players. Game cancelled.")

@bot.on_message(filters.command("join"))
async def join_game(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if chat_id not in active_games:
        await message.reply("⚠️ No active game. Use /start to begin.")
        return
    if user_id in active_games[chat_id]:
        await message.reply("✅ You already joined!")
        return
    if len(active_games[chat_id]) >= MAX_PLAYERS:
        await message.reply("🚫 Game is full (15 players).")
        return
    active_games[chat_id].append(user_id)
    await message.reply(f"✅ {message.from_user.first_name} joined the game!")

@bot.on_message(filters.command("leave"))
async def leave_game(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if chat_id in active_games and user_id in active_games[chat_id]:
        active_games[chat_id].remove(user_id)
        await message.reply("👋 You left the game.")

async def begin_game(chat_id):
    player_ids = active_games[chat_id]
    roles = assign_roles(player_ids)
    player_roles.update(roles)

    for uid in player_ids:
        role = roles[uid]
        power = get_power(role)
        player_powers[uid] = power
        await send_role_dm(bot, uid, role, power)

    await bot.send_message(chat_id, "🎲 Game started! Use /vote @user to vote, /usepower @user to use your power in secret.")

@bot.on_message(filters.command("usepower"))
async def use_power(client, message: Message):
    user_id = message.from_user.id
    if user_id not in player_roles:
        await message.reply("❌ You are not in a game.")
        return

    args = message.text.split()
    if len(args) < 2:
        await message.reply("Usage: /usepower @username")
        return

    if player_roles[user_id] == "Commoner":
        await message.reply("❌ Commoners cannot use powers!")
        return

    target_username = args[1].lstrip("@")
    try:
        target = await client.get_users(target_username)
    except:
        await message.reply("❌ Invalid username.")
        return

    target_id = target.id
    if target_id not in player_roles:
        await message.reply("❌ Target is not in game.")
        return

    # Simple logic: if Villain hits anyone, message shown. If Fairy protects, show nothing.
    attacker_role = player_roles[user_id]
    power = player_powers[user_id]

    await award_xp_and_coins(user_id)
    await client.send_message(user_id, f"✅ You secretly used your power '{power}' on {target_username}.")

    if attacker_role == "Villain":
        await message.chat.send_message(f"💀 @{target_username} was defeated! 🎯 Attacked by: @{message.from_user.username}")

@bot.on_message(filters.command("vote"))
async def vote_command(client, message: Message):
    await message.reply("🗳️ Voting logic coming soon!")

@bot.on_message(filters.command("myxp"))
async def show_xp(client, message: Message):
    user_id = message.from_user.id
    user = await db.users.find_one({"_id": user_id})
    if not user:
        await message.reply("❌ No XP data.")
        return
    await message.reply(f"📊 Level: {user['level']}\nXP: {user['xp']}\n💰 Coins: {user['coins']}")

@bot.on_message(filters.command("profile"))
async def profile_command(client, message: Message):
    await show_xp(client, message)

@bot.on_message(filters.command("upgrade"))
async def upgrade_command(client, message: Message):
    user_id = message.from_user.id
    user = await db.users.find_one({"_id": user_id})
    if not user:
        await message.reply("❌ No user data.")
        return
    current_level = user.get("level", 1)
    next_level = current_level + 1
    if next_level not in LEVELS:
        await message.reply("🏆 You are at max level!")
        return
    need_coins = LEVELS[next_level]["coins"]
    if user["coins"] >= need_coins:
        await db.users.update_one({"_id": user_id}, {"$inc": {"coins": -need_coins}, "$set": {"level": next_level}})
        await message.reply(f"💎 Upgraded to level {next_level}!")
    else:
        await message.reply(f"❌ Need {need_coins} coins to upgrade.")

@bot.on_message(filters.command("leaderboard"))
async def global_leaderboard(client, message: Message):
    top = db.users.find().sort("xp", -1).limit(10)
    text = "🌍 Global Leaderboard:\n"
    async for user in top:
        text += f"👤 {user['_id']}: Level {user['level']} - XP {user['xp']}\n"
    await message.reply(text)

@bot.on_message(filters.command("myleaderboard"))
async def group_leaderboard(client, message: Message):
    chat_id = str(message.chat.id)
    top = db.users.find({"group": chat_id}).sort("xp", -1).limit(10)
    text = "🏆 Group Leaderboard:\n"
    async for user in top:
        text += f"👤 {user['_id']}: Level {user['level']} - XP {user['xp']}\n"
    await message.reply(text)

@bot.on_message(filters.command("reset"))
async def reset_game(client, message: Message):
    if not message.from_user or not message.from_user.is_bot:
        chat_id = message.chat.id
        active_games.pop(chat_id, None)
        await message.reply("🔄 Game reset.")

@bot.on_message(filters.command("help"))
async def help_command(client, message: Message):
    await message.reply(
        "📜 *How to Play Fairy vs Villain Game*\n\n"
        "- /start – Start a new game\n"
        "- /join – Join the current game\n"
        "- /leave – Leave the game\n"
        "- /usepower – Use your character's power in secret\n"
        "- /vote – Vote for a suspicious player\n"
        "- /myxp – Check your XP and level\n"
        "- /upgrade – Level up with coins\n"
        "- /profile – Show your full profile\n"
        "- /leaderboard – Global top players\n"
        "- /myleaderboard – Group top players\n"
        "- /reset – Reset game (admin only)\n\n"
        "🧚 *Fairy Powers*: Support your team secretly.\n"
        "😈 *Villain Powers*: Eliminate enemies silently.\n"
        "🙋 *Commoners*: Vote smartly to win.\n\n"
        "💎 Earn XP/Coins by using powers and voting. Level up for stronger effects!"
    )

print("✅ Fairy vs Villain Bot Running...")
bot.run()
