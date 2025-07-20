from pyrogram import Client, filters
from pyrogram.types import Message
from config import BOT_TOKEN, API_ID, API_HASH, MONGO_URL
from pymongo import MongoClient
from random import choice, shuffle
import asyncio

bot = Client("fairy_vs_villain_bot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)
db = MongoClient(MONGO_URL).fairy_vs_villain

# Game data in memory
games = {}

# Roles and powers
FAIRIES = {
    "Fairy Sparkle": "✨ Can deflect a villain's attack once.",
    "Healing Fairy": "💖 Can secretly heal a player (once per game).",
    "Vision Fairy": "🔮 Can discover a player’s role once.",
    "Guardian Fairy": "🛡️ Can protect a player from being voted out.",
    "Whispering Fairy": "📢 Can secretly send hint to a player."
}

VILLAINS = {
    "Dark Lord": "💀 Can eliminate a player at night.",
    "Shadow Queen": "🌘 Can block a Fairy’s power.",
    "Nightmare": "😈 Can spread fear - players skip their turn.",
    "Curse Bringer": "🕷️ Curses a Fairy, disabling their powers.",
    "Soul Stealer": "🪦 Gains coins if Commoner is eliminated."
}

COMMONERS = {
    "Villager": "🗳️ Can vote to eliminate villains and earn XP.",
    "Helper": "🤝 Gets bonus XP when helping Fairies vote right.",
    "Scout": "🧐 Can peek roles with 50% chance (1/game).",
    "Believer": "🙏 Gains coins if Fairies win.",
    "Trader": "💰 Trades coins for clues (not implemented)."
}

ALL_ROLES = list(FAIRIES.items()) + list(VILLAINS.items()) + list(COMMONERS.items())

# XP/Coins system
def get_level(xp):
    if xp < 100: return 1
    if xp < 250: return 2
    if xp < 500: return 3
    if xp < 1000: return 4
    return 5

def get_upgrade_cost(level):
    return level * 100

# Game Functions
async def assign_roles(group_id):
    players = games[group_id]['players']
    shuffle(players)
    assigned = {}
    roles_pool = list(FAIRIES.items()) + list(VILLAINS.items()) + list(COMMONERS.items())
    shuffle(roles_pool)
    
    for i, user_id in enumerate(players):
        if i < len(roles_pool):
            role_name, power = roles_pool[i]
            assigned[user_id] = {
                'role': role_name,
                'power': power,
                'alive': True,
                'used_power': False
            }
            try:
                await bot.send_message(user_id, f"🧙‍♀️ Your Role: {role_name}\n\n✨ Power: {power}\nUse /usepower in the group to activate if applicable.")
            except:
                pass

    games[group_id]['roles'] = assigned

async def announce_winner(group_id):
    roles = games[group_id]['roles']
    fairies_alive = [uid for uid, r in roles.items() if r['alive'] and r['role'] in FAIRIES]
    villains_alive = [uid for uid, r in roles.items() if r['alive'] and r['role'] in VILLAINS]

    if not fairies_alive:
        await bot.send_message(group_id, "😈 Villains have won the game!")
    elif not villains_alive:
        await bot.send_message(group_id, "🧚‍♀️ Fairies and Commoners have defeated the villains!")

# Commands

@bot.on_message(filters.command("start") & filters.group)
async def start_game(client, message):
    chat_id = message.chat.id
    if chat_id in games:
        await message.reply("⚠️ Game already running. Use /reset to restart.")
        return
    games[chat_id] = {'players': [], 'roles': {}, 'votes': {}}
    await message.reply("🎮 Game started! Players, type /join to participate.")

@bot.on_message(filters.command("join") & filters.group)
async def join_game(client, message):
    chat_id = message.chat.id
    user = message.from_user
    if chat_id not in games:
        await message.reply("Start a game first using /start")
        return
    if user.id in games[chat_id]['players']:
        await message.reply("✅ You're already in the game.")
        return
    games[chat_id]['players'].append(user.id)
    await message.reply(f"🙋 {user.mention} joined the game!")
    if len(games[chat_id]['players']) >= 4:
        await assign_roles(chat_id)
        await message.reply("🎲 Roles have been assigned via DM!")

@bot.on_message(filters.command("leave") & filters.group)
async def leave_game(client, message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if chat_id in games and user_id in games[chat_id]['players']:
        games[chat_id]['players'].remove(user_id)
        await message.reply("🚪 You left the game.")

@bot.on_message(filters.command("usepower") & filters.group)
async def use_power(client, message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if chat_id not in games or user_id not in games[chat_id]['roles']:
        return
    role_info = games[chat_id]['roles'][user_id]
    if role_info['used_power']:
        await message.reply("⚠️ You've already used your power.")
        return

    role_info['used_power'] = True
    power_result = f"✅ {message.from_user.mention} used their power: {role_info['power']}"
    await bot.send_message(user_id, f"🎯 You used your power: {role_info['power']}")
    await message.reply(power_result)

@bot.on_message(filters.command("vote") & filters.group)
async def vote_player(client, message):
    chat_id = message.chat.id
    user = message.from_user
    if len(message.command) < 2:
        await message.reply("Usage: /vote @username")
        return
    target_username = message.command[1].lstrip("@")
    games[chat_id]['votes'][user.id] = target_username
    await message.reply(f"🗳️ {user.mention} voted to eliminate @{target_username}")

@bot.on_message(filters.command("reset") & filters.group)
async def reset_game(client, message):
    if not message.from_user or not message.from_user.id:
        return
    if message.from_user.id != message.chat.id:
        games.pop(message.chat.id, None)
        await message.reply("🔄 Game reset.")

@bot.on_message(filters.command("help"))
async def help_menu(client, message):
    await message.reply("""
📜 *Fairy vs Villain Bot Commands:*
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

🎮 _Min 4 players required. Roles sent via DM. Commoners help Fairies. Fairies defeat Villains!_
    """, quote=True)

@bot.on_message(filters.command("myxp"))
async def show_xp(client, message):
    user = db.users.find_one({"_id": message.from_user.id}) or {"xp": 0, "coins": 0}
    level = get_level(user['xp'])
    await message.reply(f"📊 XP: {user['xp']}\n💎 Coins: {user['coins']}\n🎖️ Level: {level}")

@bot.on_message(filters.command("upgrade"))
async def upgrade_user(client, message):
    user = db.users.find_one({"_id": message.from_user.id}) or {"xp": 0, "coins": 0}
    level = get_level(user['xp'])
    cost = get_upgrade_cost(level)
    if user['coins'] >= cost:
        db.users.update_one({"_id": message.from_user.id}, {"$inc": {"xp": 50, "coins": -cost}}, upsert=True)
        await message.reply(f"🔼 You upgraded to Level {get_level(user['xp']+50)}!")
    else:
        await message.reply("💰 Not enough coins to upgrade.")

@bot.on_message(filters.command("profile"))
async def profile(client, message):
    user = db.users.find_one({"_id": message.from_user.id}) or {"xp": 0, "coins": 0}
    await message.reply(f"👤 *{message.from_user.first_name}*\nXP: {user['xp']}\nCoins: {user['coins']}\nLevel: {get_level(user['xp'])}")

@bot.on_message(filters.command("leaderboard"))
async def leaderboard(client, message):
    top = db.users.find().sort("xp", -1).limit(5)
    text = "🌍 *Global Leaderboard:*\n"
    for i, u in enumerate(top, 1):
        text += f"{i}. [User](tg://user?id={u['_id']}) - XP: {u['xp']}\n"
    await message.reply(text)

@bot.on_message(filters.command("myleaderboard") & filters.group)
async def my_leaderboard(client, message):
    group_id = str(message.chat.id)
    top = db.group_stats.find({"group": group_id}).sort("xp", -1).limit(5)
    text = "🏆 *Group Leaderboard:*\n"
    for i, u in enumerate(top, 1):
        text += f"{i}. [User](tg://user?id={u['user']}) - XP: {u['xp']}\n"
    await message.reply(text)

bot.run()
