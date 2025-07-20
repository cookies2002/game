import asyncio
import random
from pyrogram import Client, filters
from pyrogram.types import Message
from config import API_ID, API_HASH, BOT_TOKEN
from motor.motor_asyncio import AsyncIOMotorClient

bot = Client("fairy_vs_villain", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# MongoDB Setup
mongo_client = AsyncIOMotorClient("mongodb+srv://xarwin2:xarwin2002@cluster0.qmetx2m.mongodb.net/?retryWrites=true&w=majority")
db = mongo_client.fairy_vs_villain

# Game Variables
game_started = False
players = []
group_id = None
roles = {}
alive_players = []
out_players = []
powers_used = {}
votes = {}

# Character Definitions
FAIRIES = {
    "Fairy Sparkle": "✨ Can deflect a villain's attack once.",
    "Fairy Glow": "🌟 Reveals if a player is a villain.",
    "Fairy Shield": "🛡️ Protects a player from being attacked.",
    "Fairy Whisper": "🧚 Silences a villain for one round.",
    "Fairy Light": "🔦 Revives one fallen fairy once."
}

VILLAINS = {
    "Dark Phantom": "💀 Can instantly eliminate one player.",
    "Shadow Mage": "🕶️ Blocks a fairy power for one turn.",
    "Black Widow": "🕷️ Spreads confusion — changes a vote.",
    "Night Terror": "🌒 Silences one player.",
    "Dread Lord": "🔥 Can burn a fairy’s shield."
}

COMMONERS = ["Villager", "Peasant", "Helper", "Watcher", "Common Soul"]

# Commands
@bot.on_message(filters.command("start"))
async def start_game(client, message):
    global game_started, players, group_id
    if game_started:
        await message.reply("🎮 Game already started!")
        return
    group_id = message.chat.id
    players.clear()
    roles.clear()
    alive_players.clear()
    out_players.clear()
    powers_used.clear()
    votes.clear()
    game_started = True
    await message.reply("🌟 Welcome to Fairy vs Villain Game!\nUse /join to enter the magical battlefield! Minimum 4 players to start.")

@bot.on_message(filters.command("join"))
async def join_game(client, message):
    global players
    user = message.from_user
    if user.id in [p['id'] for p in players]:
        await message.reply("🧙 You already joined the game!")
        return
    players.append({"id": user.id, "username": user.username or user.first_name})
    await message.reply(f"✅ @{user.username or user.first_name} joined the battle! Total: {len(players)} players")
    if len(players) >= 4:
        await message.reply("⏳ 1 minute left before game starts. Others can /join quickly!")
        await asyncio.sleep(60)
        if len(players) >= 4:
            await assign_roles_and_start(client)
        else:
            await message.reply("❌ Not enough players. Game cancelled.")

async def assign_roles_and_start(client):
    global roles, alive_players
    random.shuffle(players)
    total = len(players)
    fairy_count = max(1, total // 3)
    villain_count = max(1, total // 4)
    assigned = set()

    for _ in range(fairy_count):
        player = get_unassigned_player(assigned)
        role, power = random.choice(list(FAIRIES.items()))
        roles[player['id']] = {"role": role, "power": power, "team": "Fairy"}
        assigned.add(player['id'])

    for _ in range(villain_count):
        player = get_unassigned_player(assigned)
        role, power = random.choice(list(VILLAINS.items()))
        roles[player['id']] = {"role": role, "power": power, "team": "Villain"}
        assigned.add(player['id'])

    for player in players:
        if player['id'] not in assigned:
            role = random.choice(COMMONERS)
            roles[player['id']] = {"role": role, "power": None, "team": "Commoner"}

    for player in players:
        uid = player['id']
        info = roles[uid]
        text = f"🌟 Your role: {info['role']}\n🏷️ Team: {info['team']}\n💫 Power: {info['power'] or 'None'}\nUse /usepower carefully."
        try:
            await client.send_message(uid, text)
        except:
            await client.send_message(group_id, f"❌ Couldn't DM @{player['username']}. Make sure you started the bot in DM!")

    alive_players.extend([p['id'] for p in players])
    await client.send_message(group_id, "🔥 Game has begun! Use /vote or /usepower to play!")

# Helpers
def get_unassigned_player(assigned):
    for p in players:
        if p['id'] not in assigned:
            return p

@bot.on_message(filters.command("stats"))
async def show_stats(client, message):
    alive = [f"@{p['username']}" for p in players if p['id'] in alive_players]
    out = [f"@{p['username']}" for p in players if p['id'] in out_players]
    used = [f"@{p['username']}" for p in players if p['id'] in powers_used]
    text = f"📊 Game Stats:\n👥 Alive: {len(alive)} → {', '.join(alive)}\n💀 Out: {len(out)} → {', '.join(out)}\n⚡ Powers used: {', '.join(used) if used else 'None'}"
    await message.reply(text)

# TODO: Implement usepower, vote, profile, upgrade, myxp, leaderboard etc.

print("🤖 Fairy vs Villain bot started!")
bot.run()
