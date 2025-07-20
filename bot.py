import os
import random
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pymongo import MongoClient

# Load from environment or set your Mongo URI and bot token
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
BOT_TOKEN = os.getenv("BOT_TOKEN", "your-bot-token")
API_ID = int(os.getenv("API_ID", 123456))
API_HASH = os.getenv("API_HASH", "your-api-hash")

bot = Client("fairy-vs-villain", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
client = MongoClient(MONGO_URL)
db = client.fairy_vs_villain
game_data = {}

# ========== Helper Functions ==========
def get_level_up_cost(level):
    return level * 100

def get_required_xp(level):
    return level * 200

async def assign_roles(chat_id):
    players = game_data[chat_id]['players']
    random.shuffle(players)
    roles = ["Fairy", "Villain", "Commoner", "Fairy", "Villain"]
    while len(roles) < len(players):
        roles.append("Commoner")
    random.shuffle(roles)
    for i, user_id in enumerate(players):
        role = roles[i]
        db.users.update_one({"_id": user_id}, {"$set": {"role": role, "alive": True}}, upsert=True)
        user = await bot.get_users(user_id)
        text = f"👤 You are a *{role}*\n"
        if role == "Fairy":
            text += "✨ You can detect and deflect Villains! Use /usepower wisely."
        elif role == "Villain":
            text += "💀 You can attack others! Use /usepower to eliminate."
        else:
            text += "🧑 You are a Commoner. Vote wisely and support Fairies!"
        await bot.send_message(user_id, text)

# ========== Commands ========== 

@bot.on_message(filters.command("start") & filters.group)
async def start_game(client, message: Message):
    chat_id = message.chat.id
    if chat_id not in game_data:
        game_data[chat_id] = {"players": [], "votes": {}, "started": False}
        await message.reply("🎮 Game created! Players use /join to participate.")
    else:
        await message.reply("Game already created. Use /join to join or /reset to reset.")

@bot.on_message(filters.command("join") & filters.group)
async def join_game(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if chat_id in game_data and user_id not in game_data[chat_id]['players']:
        game_data[chat_id]['players'].append(user_id)
        db.users.update_one({"_id": user_id}, {"$setOnInsert": {"xp": 0, "coins": 0, "level": 1}}, upsert=True)
        await message.reply(f"✅ {message.from_user.mention} joined the game!")

        if len(game_data[chat_id]['players']) >= 4 and not game_data[chat_id]['started']:
            game_data[chat_id]['started'] = True
            await message.reply("🚀 Game started! Assigning roles...")
            await assign_roles(chat_id)
    else:
        await message.reply("You're already in the game or game not created yet.")

@bot.on_message(filters.command("leave") & filters.group)
async def leave_game(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if chat_id in game_data and user_id in game_data[chat_id]['players']:
        game_data[chat_id]['players'].remove(user_id)
        await message.reply(f"🚪 {message.from_user.mention} left the game.")

@bot.on_message(filters.command("usepower") & filters.group)
async def use_power(client, message: Message):
    chat_id = message.chat.id
    attacker_id = message.from_user.id
    if len(message.command) < 2:
        return await message.reply("Usage: /usepower @target")
    try:
        target_username = message.command[1].replace("@", "")
        target = await bot.get_users(target_username)
        target_id = target.id
    except:
        return await message.reply("Invalid target username.")

    attacker = db.users.find_one({"_id": attacker_id})
    target_user = db.users.find_one({"_id": target_id})

    if not attacker or not attacker.get("alive", True):
        return await message.reply("You're not alive or in game.")

    if attacker['role'] == "Villain":
        db.users.update_one({"_id": target_id}, {"$set": {"alive": False}})
        db.users.update_one({"_id": attacker_id}, {"$inc": {"xp": 50, "coins": 50}})
        await bot.send_message(attacker_id, f"💥 You attacked @{target_username}!")
        await message.reply(f"💀 @{target_username} was defeated! 🎯 Attacked by: @{message.from_user.username}")

    elif attacker['role'] == "Fairy":
        if target_user and target_user['role'] == "Villain":
            await bot.send_message(attacker_id, f"🛡️ You successfully deflected a Villain: @{target_username}!")
            await message.reply(f"✨ @{message.from_user.username} deflected @{target_username} (Villain)!")
            db.users.update_one({"_id": attacker_id}, {"$inc": {"xp": 40, "coins": 40}})
        else:
            await bot.send_message(attacker_id, "❌ Your detection failed. That wasn't a Villain.")
    else:
        await bot.send_message(attacker_id, "🚫 Commoners don’t have powers!")

@bot.on_message(filters.command("vote") & filters.group)
async def vote_player(client, message: Message):
    chat_id = message.chat.id
    voter_id = message.from_user.id
    if len(message.command) < 2:
        return await message.reply("Usage: /vote @username")
    try:
        voted_username = message.command[1].replace("@", "")
        voted_user = await bot.get_users(voted_username)
        voted_id = voted_user.id
    except:
        return await message.reply("Invalid username.")

    game_data[chat_id]['votes'][voter_id] = voted_id
    db.users.update_one({"_id": voter_id}, {"$inc": {"xp": 10, "coins": 5}})
    await message.reply(f"🗳️ {message.from_user.mention} voted @{voted_username}!")

@bot.on_message(filters.command("myxp"))
async def show_my_xp(client, message: Message):
    user_id = message.from_user.id
    user = db.users.find_one({"_id": user_id})
    if not user:
        return await message.reply("No data found. Join a game first.")
    await message.reply(f"📊 XP: {user['xp']}\n💎 Coins: {user['coins']}\n⭐ Level: {user['level']}")

@bot.on_message(filters.command("upgrade"))
async def upgrade_user(client, message: Message):
    user_id = message.from_user.id
    user = db.users.find_one({"_id": user_id})
    cost = get_level_up_cost(user['level'])
    if user['coins'] >= cost:
        db.users.update_one({"_id": user_id}, {"$inc": {"level": 1, "coins": -cost}})
        await message.reply(f"🎉 You leveled up to Level {user['level'] + 1}!")
    else:
        await message.reply(f"❌ Not enough coins. You need {cost} coins to level up.")

@bot.on_message(filters.command("profile"))
async def show_profile(client, message: Message):
    user_id = message.from_user.id
    user = db.users.find_one({"_id": user_id})
    if not user:
        return await message.reply("Join a game first.")
    await message.reply(f"👤 Role: {user.get('role', 'Unknown')}\n📊 XP: {user['xp']}\n💎 Coins: {user['coins']}\n⭐ Level: {user['level']}")

@bot.on_message(filters.command("reset") & filters.group)
async def reset_game(client, message: Message):
    if message.from_user.id == message.chat.id:
        return await message.reply("Only admins can reset the game.")
    chat_id = message.chat.id
    game_data.pop(chat_id, None)
    await message.reply("🔄 Game reset.")

@bot.on_message(filters.command("leaderboard"))
async def show_global_leaderboard(client, message: Message):
    top = list(db.users.find().sort("xp", -1).limit(5))
    text = "🌍 Global Leaderboard:\n"
    for i, user in enumerate(top, 1):
        text += f"{i}. ID: {user['_id']} - XP: {user['xp']}\n"
    await message.reply(text)

@bot.on_message(filters.command("myleaderboard") & filters.group)
async def show_group_leaderboard(client, message: Message):
    chat_id = message.chat.id
    if chat_id not in game_data:
        return await message.reply("No game data.")
    group_players = game_data[chat_id]['players']
    users = list(db.users.find({"_id": {"$in": group_players}}).sort("xp", -1))
    text = "🏆 Group Leaderboard:\n"
    for i, user in enumerate(users, 1):
        text += f"{i}. ID: {user['_id']} - XP: {user['xp']}\n"
    await message.reply(text)

@bot.on_message(filters.command("help"))
async def show_help(client, message: Message):
    await message.reply(
        """📜 *How to Play Fairy vs Villain*

/start - Start a new game
/join - Join the game
/leave - Leave the game
/usepower - Use your current power (Secret DM, public if success 💥)
/vote - Vote a suspicious player 🗳️
/myxp - Show your XP, level & coins 📊
/upgrade - Level up with coins 💎
/profile - See your full stats
/reset - Reset game manually (Admin only ⚙️)
/leaderboard - View global top players 🌍
/myleaderboard - View this group's top players 🏆

Fairies: Detect and deflect Villains
Villains: Eliminate others secretly
Commoners: Vote and earn XP to help fair team!
        """,
        parse_mode="markdown"
    )

print("✅ Bot is running...")
bot.run()
