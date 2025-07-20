from pyrogram import Client, filters
from pyrogram.types import Message
import random
import asyncio
import datetime

# Bot and user data
players = {}
game_data = {}
user_data = {}
cooldowns = {}

# --- Configuration ---
COIN_REWARD = 5
XP_REWARD = 10
LEVEL_UP_COST = 10
MIN_PLAYERS = 4

# --- Helper Functions ---
def get_power(role, level):
    if role == "Fairy":
        if level >= 5:
            return "🌈 Celestial Storm"
        elif level >= 3:
            return "🌪️ Tornado Blast"
        else:
            return "✨ Fairy Spark"
    elif role == "Villain":
        if level >= 5:
            return "🧨 Chaos Rage"
        elif level >= 3:
            return "🔥 Hellfire"
        else:
            return "💀 Dark Strike"
    else:  # Commoner
        return "👥 Vote Boost" if level >= 3 else "🤝 Support"

def get_role_tip(role):
    if role == "Fairy":
        return "Use /usepower to defeat Villains and protect Commoners."
    elif role == "Villain":
        return "Use /usepower to secretly eliminate others."
    else:
        return "Vote wisely. At Level 3, your vote counts double!"

def check_cooldown(user_id):
    now = datetime.datetime.now()
    if user_id in cooldowns:
        if now < cooldowns[user_id]:
            return (True, (cooldowns[user_id] - now).seconds)
    return (False, 0)

# --- Bot Commands ---

@Client.on_message(filters.command("start"))
async def start_game(client, message: Message):
    chat_id = message.chat.id
    game_data[chat_id] = {"started": False, "players": []}
    await message.reply("🎮 Game created! Use /join to participate.")

@Client.on_message(filters.command("join"))
async def join_game(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    username = message.from_user.mention

    if chat_id not in game_data:
        await message.reply("❗ Use /start to begin a game first.")
        return

    if user_id in game_data[chat_id]["players"]:
        await message.reply("👀 You're already in the game!")
        return

    game_data[chat_id]["players"].append(user_id)
    players[user_id] = {"username": username, "alive": True}

    # Assign role and initialize user
    role = random.choice(["Fairy", "Villain", "Commoner"])
    user_data[user_id] = {"xp": 0, "coins": 0, "level": 1, "role": role}

    power = get_power(role, 1)
    await client.send_message(
        user_id,
        f"🌟 Your Role: {role}\n✨ Power: {power}\n📈 Tip: {get_role_tip(role)}\n💡 Level up to unlock stronger powers!"
    )

    await message.reply(f"✅ {username} joined the game!")

@Client.on_message(filters.command("usepower"))
async def use_power(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user = user_data.get(user_id)
    username = message.from_user.mention

    if not user or not players.get(user_id, {}).get("alive"):
        await message.reply("❌ You are not in the game or not alive.")
        return

    # Cooldown check
    on_cooldown, seconds_left = check_cooldown(user_id)
    if on_cooldown:
        await message.reply(f"⏳ Your power is cooling down. Wait {seconds_left} seconds.")
        return

    # Choose target randomly for now
    alive_targets = [uid for uid in players if players[uid]["alive"] and uid != user_id]
    if not alive_targets:
        await message.reply("🤷 No valid targets.")
        return

    target_id = random.choice(alive_targets)
    target = user_data.get(target_id)
    target_name = players[target_id]["username"]

    role = user["role"]
    level = user["level"]
    power = get_power(role, level)

    result_msg = f"🎯 You used {power} on {target_name}!\n"

    if role == "Villain" or role == "Fairy":
        players[target_id]["alive"] = False
        result_msg += f"💀 {target_name} was defeated!"
        await message.reply(f"💀 {target_name} was defeated! 🎯 Attacked by: {username}")

    # DM to attacker
    await client.send_message(user_id, result_msg)

    # Add rewards
    user["xp"] += XP_REWARD
    user["coins"] += COIN_REWARD

    # Set cooldown (30s)
    cooldowns[user_id] = datetime.datetime.now() + datetime.timedelta(seconds=30)

@Client.on_message(filters.command("myxp"))
async def my_xp(client, message: Message):
    user_id = message.from_user.id
    user = user_data.get(user_id)
    if not user:
        await message.reply("❗ You're not registered yet. Use /join in a game.")
        return
    await message.reply(f"📊 XP: {user['xp']}\n🏅 Level: {user['level']}\n💰 Coins: {user['coins']}")

@Client.on_message(filters.command("upgrade"))
async def upgrade(client, message: Message):
    user_id = message.from_user.id
    user = user_data.get(user_id)
    if not user:
        await message.reply("❗ Join the game first.")
        return

    if user["coins"] < LEVEL_UP_COST:
        await message.reply("😢 Not enough coins to level up.")
        return

    user["coins"] -= LEVEL_UP_COST
    user["level"] += 1
    new_power = get_power(user["role"], user["level"])

    upgrade_msg = f"✅ You upgraded to Level {user['level']}!\n🔓 New Power: {new_power}\n💰 Coins left: {user['coins']}"

    if user["role"] == "Commoner" and user["level"] == 3:
        upgrade_msg += "\n🛡️ You unlocked Shield Vote! Your vote counts double."

    await message.reply(upgrade_msg)

@Client.on_message(filters.command("powers"))
async def powers(client, message: Message):
    power_info = (
        "✨ *Fairy Powers:*\n"
        "- L1–2: Fairy Spark\n"
        "- L3–4: Tornado Blast\n"
        "- L5+: Celestial Storm\n\n"
        "💀 *Villain Powers:*\n"
        "- L1–2: Dark Strike\n"
        "- L3–4: Hellfire\n"
        "- L5+: Chaos Rage\n\n"
        "👥 *Commoner Powers:*\n"
        "- L1–2: Support (vote only)\n"
        "- L3+: Shield Vote (vote counts x2)"
    )
    await message.reply(power_info, quote=True)

@Client.on_message(filters.command("instructions"))
async def instructions(client, message: Message):
    help_msg = (
        "🧚‍♀️ *Fairy vs Villain Game Guide* 🦹‍♂️\n\n"
        "🔹 Use /join to enter an ongoing game.\n"
        "🔹 Roles: Fairy, Villain, Commoner — each with unique powers.\n"
        "🔹 Earn XP & coins by using powers and surviving.\n"
        "🔹 Use /upgrade to level up and unlock stronger powers.\n"
        "🔹 Commoners help vote — their vote counts double after Level 3.\n"
        "🔹 Use /usepower with strategy. Each power has a cooldown.\n"
        "🔹 Track progress with /myxp and /profile.\n\n"
        "🎯 Goal: Fairies eliminate Villains, Villains eliminate all."
    )
    await message.reply(help_msg, quote=True)

print("✅ Fairy vs Villain Bot is now running...")
