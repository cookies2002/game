import asyncio
import random
from pyrogram import Client, filters
from pyrogram.types import Message
from config import MONGO_URL, BOT_TOKEN, API_ID, API_HASH
from motor.motor_asyncio import AsyncIOMotorClient

bot = Client("fairy_vs_villain_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
db = AsyncIOMotorClient(MONGO_URL).fairy_game

players = []
game_started = False
group_id = None

roles = {}
used_powers = set()
votes = {}
xp_data = {}

role_powers = {
    "Fairy Sparkle": "✨ Can deflect a villain's attack once.",
    "Fairy Healer": "💖 Can heal and revive one fallen player.",
    "Fairy Shield": "🛡️ Can protect a player from being attacked.",
    "Fairy Vision": "🔮 Can reveal the role of another player.",
    "Fairy Wind": "🍃 Can confuse a villain's action.",
    
    "Dark Slayer": "💀 Can instantly eliminate a player.",
    "Shadow Mage": "🧿 Can block a player's power for 1 round.",
    "Mind Thief": "🧠 Can steal another player’s power.",
    "Fear Bringer": "😱 Can make 2 players unable to vote.",
    "Chaos Master": "🔥 Can cause random chaos among powers.",
    
    "Commoner": "🙂 Can vote and help Fairies win. Earn XP by voting."
}

@bot.on_message(filters.command("start") & filters.group)
async def start_game(client, message: Message):
    global game_started, players, group_id
    if game_started:
        return await message.reply("🚫 A game is already in progress!")
    players = []
    group_id = message.chat.id
    game_started = False
    await message.reply("🎮 New game starting! Type /join to participate.")
    await asyncio.sleep(60)  # Allow 1 minute to join
    if len(players) >= 4:
        await assign_roles_and_start(client)
    else:
        await message.reply("❌ Not enough players to start the game.")

@bot.on_message(filters.command("join") & filters.group)
async def join_game(client, message: Message):
    user = message.from_user
    if user.id in [p["id"] for p in players]:
        return await message.reply("✅ You're already in the game!")
    players.append({"id": user.id, "name": user.mention, "username": user.username})
    await message.reply(f"🙋‍♂️ {user.mention} joined the game!")

@bot.on_message(filters.command("usepower") & filters.group)
async def use_power(client, message: Message):
    user_id = message.from_user.id
    if user_id not in roles:
        return await message.reply("❌ You're not in this game.")
    role = roles[user_id]["role"]
    power = roles[user_id]["power"]
    if user_id in used_powers:
        return await message.reply("⛔ You've already used your power.")
    used_powers.add(user_id)
    # Simulate random result
    await client.send_message(user_id, f"🎯 You used your power: {power}")
    await message.reply(f"💥 {message.from_user.mention} used their power!")

@bot.on_message(filters.command("vote") & filters.group)
async def vote_command(client, message: Message):
    if not game_started:
        return await message.reply("❌ Game hasn't started.")
    if len(message.command) < 2:
        return await message.reply("🗳️ Usage: /vote @username")
    target_username = message.command[1].lstrip("@")
    voter_id = message.from_user.id
    for p in players:
        if p["username"] == target_username:
            votes[voter_id] = p["id"]
            return await message.reply(f"🗳️ Vote registered for {p['name']}")
    await message.reply("❌ Player not found.")

@bot.on_message(filters.command("myxp"))
async def my_xp(client, message: Message):
    user_id = str(message.from_user.id)
    data = await db.users.find_one({"_id": user_id}) or {"xp": 0, "coins": 0}
    await message.reply(f"📊 XP: {data.get('xp', 0)} | 💰 Coins: {data.get('coins', 0)}")

@bot.on_message(filters.command("profile"))
async def profile(client, message: Message):
    user_id = str(message.from_user.id)
    data = await db.users.find_one({"_id": user_id}) or {}
    role_info = roles.get(message.from_user.id, {})
    role_display = f"{role_info.get('role')} - {role_info.get('power')}" if role_info else "Not playing"
    await message.reply(f"👤 Profile:\n🔹 XP: {data.get('xp', 0)}\n💰 Coins: {data.get('coins', 0)}\n🎭 Role: {role_display}")

@bot.on_message(filters.command("stats") & filters.group)
async def game_stats(client, message: Message):
    alive = [p for p in players if p["id"] not in used_powers]
    out = [p for p in players if p["id"] in used_powers]
    await message.reply(f"📊 Game Stats:\n🟢 Alive: {len(alive)}\n🔴 Out: {len(out)}\n💥 Attacks used: {len(used_powers)}")

@bot.on_message(filters.command("reset") & filters.group)
async def reset_game(client, message: Message):
    global players, roles, votes, used_powers, game_started
    players = []
    roles = {}
    votes = {}
    used_powers = set()
    game_started = False
    await message.reply("🔄 Game has been reset.")

@bot.on_message(filters.command("help"))
async def help_menu(client, message: Message):
    await message.reply("""
📜 Game Commands:
/start - Start a new game
/join - Join the game
/leave - Leave the game
/usepower - Use your current power (Secret DM, public if success 💥)
/vote - Vote a suspicious player 🗳️
/myxp - Show your XP & coins 📊
/profile - See your full stats
/reset - Reset game manually (Admin only ⚙️)
/help - Show the help menu 📜
/leaderboard - View global top players 🌍
/myleaderboard - View this group's top players 🏆
/stats - Show current game stats 👥
    """)

async def assign_roles_and_start(client):
    global game_started
    game_started = True
    total = len(players)
    fairy_count = total // 2
    villain_count = (total - fairy_count) // 2
    commoner_count = total - fairy_count - villain_count
    random.shuffle(players)
    roles.clear()
    for i, p in enumerate(players):
        uid = p["id"]
        if i < fairy_count:
            role, power = random.choice(list(FAIRIES.items()))
        elif i < fairy_count + villain_count:
            role, power = random.choice(list(VILLAINS.items()))
        else:
            role, power = random.choice(list(COMMONERS.items()))
        roles[uid] = {"role": role, "power": power}
        await client.send_message(uid, f"🎭 Your Role: {role}\n🔮 Power: {power}\n💡 Use /usepower in group or DM")
    await client.send_message(group_id, "🚀 Game Started! Roles assigned secretly. Use /vote and /usepower wisely!")

bot.run()
