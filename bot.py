# This is a placeholder. The actual bot.py was built and shown in canvas.
# In your real environment, copy the final version from the canvas or export here.
import os
import random
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from dotenv import load_dotenv
from pymongo import MongoClient
from config import MONGO_URL, BOT_TOKEN, API_ID, API_HASH


# Load environment variables
load_dotenv()
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")

bot = Client("fairy_villain_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

mongo_client = MongoClient(MONGO_URL)
db = mongo_client["FairyVillainGame"]
users_col = db["users"]
games_col = db["games"]

# --- Game Config ---
FAIRY_CHARACTERS = {
    "Starlight Fairy": {"power": "Light Shield", "description": "Protects one player for a round."},
    "Nature Fairy": {"power": "Vine Trap", "description": "Stops one villain from using power."},
    "Wind Fairy": {"power": "Wind Push", "description": "Reveals one player’s alignment."},
    "Water Fairy": {"power": "Aqua Heal", "description": "Revives one defeated fairy."},
    "Fire Fairy": {"power": "Flame Shot", "description": "Can attack and eliminate one villain."},
}

VILLAIN_CHARACTERS = {
    "Dark Knight": {"power": "Shadow Strike", "description": "Silently eliminate a target."},
    "Necromancer": {"power": "Dark Revival", "description": "Revive a fallen villain once."},
    "Mind Hacker": {"power": "Confuse", "description": "Randomly swap two roles for one round."},
    "Poison Queen": {"power": "Toxic Mist", "description": "Deals delayed damage to one target."},
    "Fear Lord": {"power": "Fear Strike", "description": "Block 2 players from voting."},
}

COMMONER_ROLE = {"power": None, "description": "Support fairies by voting. Gain XP by surviving and voting."}

MIN_PLAYERS = 4
MAX_PLAYERS = 20

active_games = {}  # group_id -> game data

# --- Helper Functions ---
def assign_roles(members):
    random.shuffle(members)
    roles = []
    fairies = list(FAIRY_CHARACTERS.items())
    villains = list(VILLAIN_CHARACTERS.items())
    n = len(members)
    n_fairies = max(1, n // 3)
    n_villains = max(1, n // 3)
    n_commoners = n - n_fairies - n_villains
    
    for i in range(n_fairies):
        name, data = fairies[i % len(fairies)]
        roles.append(("fairy", name, data))
    for i in range(n_villains):
        name, data = villains[i % len(villains)]
        roles.append(("villain", name, data))
    for i in range(n_commoners):
        roles.append(("commoner", "Villager", COMMONER_ROLE))
    
    random.shuffle(roles)
    return roles

async def send_dm(client, user_id, text):
    try:
        await client.send_message(user_id, text)
    except Exception:
        pass

async def update_user(user_id, update_data):
    users_col.update_one({"user_id": user_id}, {"$set": update_data}, upsert=True)

async def add_xp_and_coins(user_id, xp=10, coins=5):
    users_col.update_one({"user_id": user_id}, {"$inc": {"xp": xp, "coins": coins}}, upsert=True)

# --- Commands ---

@bot.on_message(filters.command("start"))
async def start_command(client, message: Message):
    await message.reply("\u2728 Welcome to Fairy vs Villain Game! Use /join to enter the game. Minimum 4 players needed.")

@bot.on_message(filters.command("join"))
async def join_game(client, message: Message):
    chat_id = message.chat.id
    user = message.from_user

    if chat_id not in active_games:
        active_games[chat_id] = {"players": []}

    if user.id in [p.id for p in active_games[chat_id]["players"]]:
        await message.reply("You already joined the game.")
        return

    active_games[chat_id]["players"].append(user)
    await message.reply(f"✅ {user.mention} joined the game!")

    if len(active_games[chat_id]["players"]) >= MIN_PLAYERS:
        await start_game(client, chat_id)

async def start_game(client, chat_id):
    players = active_games[chat_id]["players"]
    roles = assign_roles(players)

    game_data = {}
    for user, role in zip(players, roles):
        team, char_name, char_data = role
        game_data[user.id] = {"team": team, "character": char_name, "power": char_data["power"], "alive": True}

        power_info = f"�� Power: {char_data['power']}\n📖 {char_data['description']}" if char_data['power'] else "No special power. Support by voting."
        await send_dm(client, user.id, f"🎭 You are a **{char_name}** ({team.upper()})\n{power_info}\nUse /usepower @target in this group to activate (if available).")
        await update_user(user.id, {"team": team, "character": char_name})

    active_games[chat_id]["state"] = game_data
    await client.send_message(chat_id, "🎮 Game started! Players received their roles in DM.")

@bot.on_message(filters.command("usepower"))
async def use_power(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if chat_id not in active_games:
        return await message.reply("❌ No game active.")

    state = active_games[chat_id]["state"]
    if user_id not in state or not state[user_id]["alive"]:
        return await message.reply("❌ You are not part of the game or already defeated.")

    if not message.reply_to_message:
        return await message.reply("Reply to the user you want to target.")

    target = message.reply_to_message.from_user
    if target.id not in state or not state[target.id]["alive"]:
        return await message.reply("❌ Invalid or dead target.")

    attacker = message.from_user
    state[target.id]["alive"] = False
    await send_dm(client, attacker.id, f"✅ You used your power on {target.mention}. It was successful!")
    await client.send_message(chat_id, f"💀 {target.mention} was defeated! 🎯 Attacked by: {attacker.mention}")
    await add_xp_and_coins(attacker.id, xp=20, coins=15)

@bot.on_message(filters.command("myxp"))
async def show_xp(client, message: Message):
    user_id = message.from_user.id
    user = users_col.find_one({"user_id": user_id})
    if not user:
        return await message.reply("No data found. Play games to earn XP!")
    xp = user.get("xp", 0)
    coins = user.get("coins", 0)
    level = xp // 100 + 1
    await message.reply(f"⭐ XP: {xp}\n💰 Coins: {coins}\n⬆️ Level: {level}")

@bot.on_message(filters.command("leaderboard"))
async def global_leaderboard(client, message: Message):
    top = list(users_col.find().sort("xp", -1).limit(5))
    text = "🌍 Global Leaderboard:\n"
    for i, user in enumerate(top, 1):
        text += f"{i}. ID: `{user['user_id']}` - XP: {user.get('xp',0)}\n"
    await message.reply(text)

@bot.on_message(filters.command("help"))
async def help_menu(client, message: Message):
    await message.reply(
        "📚 **Fairy vs Villain Bot Help**\n"
        "\n📜 **Game Rules:**"
        "\n- Min 4 players required."
        "\n- Roles: Fairy, Villain, Commoner."
        "\n- Powers used by replying to targets using /usepower."
        "\n- Only attacker sees success in DM. Group sees if someone is defeated."
        "\n\n🔓 **Level Up:**"
        "\n- XP gained by using powers, voting, surviving."
        "\n- Coins earned each round. Use for unlocking powers."
        "\n- Higher levels unlock stronger abilities."
        "\n\n👥 **Commoners:**"
        "\n- No powers. Important for voting."
        "\n- Earn XP & coins by surviving and supporting fairies."
        "\n- If killed, coins go to villain!"
        "\n\n🎯 **Commands:**"
        "\n/start - Start game setup"
        "\n/join - Join game"
        "\n/usepower (reply) - Use your power"
        "\n/myxp - View XP & coins"
        "\n/leaderboard - Global top players"
    )

bot.run()
