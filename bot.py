# bot.py - Fairy vs Villain Game Bot

from pyrogram import Client, filters
from pyrogram.types import Message
from config import BOT_TOKEN, API_ID, API_HASH, MONGO_URL
from pymongo import MongoClient
import asyncio
import random

bot = Client("fairy_villain_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
db = MongoClient(MONGO_URL).fairyvillain

# In-memory game state
games = {}

# Roles and Powers
fairy_roles = [
    ("Light Fairy", "Protects an ally from attacks for one night."),
    ("Wind Fairy", "Can redirect an attack to another player."),
    ("Time Fairy", "Skip one vote phase once per game."),
    ("Healing Fairy", "Revives a fallen ally once."),
    ("Truth Fairy", "Reveals if a player is Villain (1-time use).")
]

villain_roles = [
    ("Dark Lord", "Kills one player every night."),
    ("Mind Stealer", "Silences one player during vote."),
    ("Fear Mage", "Block 2 player votes for a round."),
    ("Soul Eater", "Absorbs XP of defeated player."),
    ("Shadow Walker", "Avoid detection by Truth Fairy.")
]

commoner_msg = "🧑‍🌾 You're a Commoner!\nYou don’t have any powers.\nUse /vote to help eliminate the Villains."

# Start command
@bot.on_message(filters.command("start"))
async def start_game(client, message: Message):
    await message.reply("👾 Welcome to *Fairy vs Villain*!\nUse /join to enter the game.\nMinimum 4 players required.\nGame starts 60 seconds after 4 players join.")

# Join command
@bot.on_message(filters.command("join"))
async def join_game(client, message: Message):
    chat_id = message.chat.id
    user = message.from_user
    games.setdefault(chat_id, {"players": {}, "started": False, "roles": {}, "alive": set(), "votes": {}, "used_power": set()})
    game = games[chat_id]

    if game["started"]:
        return await message.reply("🚫 Game already started!")

    if user.id in game["players"]:
        return await message.reply("✅ You already joined.")

    game["players"][user.id] = user
    await message.reply(f"🎮 {user.mention} joined the game!")

    if len(game["players"]) == 4:
        await message.reply("⏳ 60 seconds left! More can join...")
        await asyncio.sleep(60)
        if not game["started"]:
            await assign_roles(client, chat_id)

# Assign roles randomly
async def assign_roles(client, chat_id):
    game = games[chat_id]
    players = list(game["players"].keys())
    random.shuffle(players)

    roles = ["Fairy", "Fairy", "Villain", "Commoner"] + ["Commoner"] * (len(players) - 4)
    random.shuffle(roles)

    for user_id, role in zip(players, roles):
        user = game["players"][user_id]
        game["roles"][user_id] = role
        game["alive"].add(user_id)

        if role == "Fairy":
            name, power = random.choice(fairy_roles)
            db.users.update_one({"_id": user_id}, {"$set": {"role": name}}, upsert=True)
            await client.send_message(user_id, f"🌟 You're a **Fairy**!\nRole: {name}\nPower: {power}\nUse /usepower during the game.")
        elif role == "Villain":
            name, power = random.choice(villain_roles)
            db.users.update_one({"_id": user_id}, {"$set": {"role": name}}, upsert=True)
            await client.send_message(user_id, f"😈 You're a **Villain**!\nRole: {name}\nPower: {power}\nUse /usepower to eliminate others.")
        else:
            await client.send_message(user_id, commoner_msg)

    game["started"] = True
    await client.send_message(chat_id, "✅ Game Started! Use /vote or /usepower. Check /help for rules.")

# Use Power
@bot.on_message(filters.command("usepower"))
async def use_power(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    game = games.get(chat_id)

    if not game or not game["started"]:
        return await message.reply("🚫 Game not active!")

    if user_id not in game["alive"]:
        return await message.reply("💀 You are eliminated!")

    if user_id in game["used_power"]:
        return await message.reply("🕒 You already used your power.")

    if game["roles"][user_id] == "Commoner":
        return await message.reply("❌ Commoners have no power!")

    game["used_power"].add(user_id)
    target = random.choice([uid for uid in game["alive"] if uid != user_id])
    game["alive"].discard(target)
    target_name = game["players"][target].mention
    attacker = message.from_user.mention
    await client.send_message(target, "💀 You were defeated by a special power!")
    await client.send_message(chat_id, f"💥 {target_name} was defeated! 🎯 Attacked by: {attacker}")

# Vote Command
@bot.on_message(filters.command("vote"))
async def vote_player(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    game = games.get(chat_id)

    if not game or not game["started"]:
        return await message.reply("🚫 No game running!")

    if user_id not in game["alive"]:
        return await message.reply("❌ You’re not alive!")

    reply = message.reply_to_message
    if not reply:
        return await message.reply("👆 Reply to the player you want to vote!")

    voted = reply.from_user.id
    if voted not in game["alive"]:
        return await message.reply("🙅 Player already out!")

    game["votes"].setdefault(voted, []).append(user_id)
    await message.reply(f"🗳️ Vote casted on {reply.from_user.mention}!")

    # Eliminate if majority
    if len(game["votes"][voted]) >= len(game["alive"]) // 2:
        game["alive"].discard(voted)
        await client.send_message(chat_id, f"❌ {reply.from_user.mention} has been eliminated by vote!")

# Help command
@bot.on_message(filters.command("help"))
async def help_cmd(client, message: Message):
    await message.reply("""
🎮 *Fairy vs Villain Game Bot*

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

bot.run()
    
