import os
import random
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")

bot = Client("fairy_vs_villain", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
client = MongoClient(MONGO_URL)
db = client.fairyvillain

lobby = {}
games = {}
powers = {
    "Fairy": ["✨ Heal", "🛡️ Shield", "🔮 Vision"],
    "Villain": ["💀 Kill", "🤐 Silence", "🕸️ Trap"],
    "Commoner": []
}

@bot.on_message(filters.command("startgame") & filters.group)
async def start_game(_, message: Message):
    chat_id = message.chat.id
    if chat_id in games:
        await message.reply("❗ Game already running. Use /end to reset.")
        return
    lobby[chat_id] = []
    await message.reply("🌟 Fairy vs Villain has begun! Type /join to enter the mystical game!")

@bot.on_message(filters.command("join") & filters.group)
async def join_game(_, message: Message):
    chat_id = message.chat.id
    user = message.from_user
    if chat_id not in lobby:
        await message.reply("❗ Use /startgame to begin first!")
        return
    if user.id in [p['id'] for p in lobby[chat_id]]:
        await message.reply("✅ You’ve already joined the battle!")
        return
    lobby[chat_id].append({"id": user.id, "username": user.username, "role": None, "alive": True})
    await message.reply(f"✨ @{user.username} joined the enchanted realm!")
    if len(lobby[chat_id]) >= 4:
        await begin_game(chat_id)

async def begin_game(chat_id):
    players = lobby[chat_id]
    random.shuffle(players)
    roles = ["Fairy", "Villain", "Commoner"] * 5
    roles = roles[:len(players)]
    random.shuffle(roles)
    for i, player in enumerate(players):
        player["role"] = roles[i]
        player["xp"] = 0
        player["coins"] = 0
        await bot.send_message(player["id"], f"🌈 Welcome, @{player['username']}!\nYour role is: {player['role']}\nPower: {powers[player['role']][0] if powers[player['role']] else 'None'}")
    games[chat_id] = players
    del lobby[chat_id]
    await bot.send_message(chat_id, "🎮 Game has started! Use /vote or /usepower wisely!")

@bot.on_message(filters.command("leave") & filters.group)
async def leave_game(_, message: Message):
    chat_id = message.chat.id
    user = message.from_user
    if chat_id in lobby:
        lobby[chat_id] = [p for p in lobby[chat_id] if p['id'] != user.id]
        await message.reply("👋 You left the lobby.")
    else:
        await message.reply("❌ You're not in the lobby.")

@bot.on_message(filters.command("end") & filters.group)
async def end_game(_, message: Message):
    chat_id = message.chat.id
    user = message.from_user
    if chat_id in games:
        del games[chat_id]
        await message.reply("🛑 Game ended. Use /startgame to begin again.")
    else:
        await message.reply("❌ No active game to end.")

@bot.on_message(filters.command("usepower") & filters.group)
async def use_power(_, message: Message):
    chat_id = message.chat.id
    user = message.from_user
    if chat_id not in games:
        return
    player = next((p for p in games[chat_id] if p['id'] == user.id), None)
    if not player or not player['alive']:
        return
    role = player['role']
    if role in powers and powers[role]:
        power = powers[role][0]
        await bot.send_message(user.id, f"🔮 You used your power: {power}! Magic is unfolding...")
        await bot.send_message(chat_id, f"✨ A mysterious power was felt in the air... 🌀")
        player['xp'] += 10
        player['coins'] += 5

@bot.on_message(filters.command("vote") & filters.group)
async def vote_player(_, message: Message):
    chat_id = message.chat.id
    if chat_id not in games:
        return
    buttons = [InlineKeyboardButton(f"@{p['username']}", callback_data=f"vote:{p['id']}") for p in games[chat_id] if p['alive']]
    keyboard = InlineKeyboardMarkup([buttons[i:i + 2] for i in range(0, len(buttons), 2)])
    await message.reply("🗳️ Vote to eliminate a player:", reply_markup=keyboard)

@bot.on_callback_query()
async def handle_vote(client, callback_query):
    data = callback_query.data
    if data.startswith("vote:"):
        target_id = int(data.split(":")[1])
        chat_id = callback_query.message.chat.id
        for player in games[chat_id]:
            if player['id'] == target_id:
                player['alive'] = False
                await bot.send_message(chat_id, f"💀 @{player['username']} was eliminated by vote!")
                break
        await callback_query.message.delete()

@bot.on_message(filters.command("myxp") & filters.group)
async def my_xp(_, message: Message):
    chat_id = message.chat.id
    user = message.from_user
    if chat_id not in games:
        return
    player = next((p for p in games[chat_id] if p['id'] == user.id), None)
    if player:
        await message.reply(f"🌟 XP: {player['xp']} | 🪙 Coins: {player['coins']}")

@bot.on_message(filters.command("profile") & filters.group)
async def my_profile(_, message: Message):
    chat_id = message.chat.id
    user = message.from_user
    if chat_id not in games:
        return
    player = next((p for p in games[chat_id] if p['id'] == user.id), None)
    if player:
        await message.reply(f"🔍 @{player['username']}\nRole: {player['role']}\nXP: {player['xp']}\nCoins: {player['coins']}\nAlive: {'✅' if player['alive'] else '❌'}")

@bot.on_message(filters.command("upgrade") & filters.group)
async def upgrade_power(_, message: Message):
    chat_id = message.chat.id
    user = message.from_user
    player = next((p for p in games.get(chat_id, []) if p['id'] == user.id), None)
    if not player:
        return
    if player['coins'] >= 10:
        player['coins'] -= 10
        player['xp'] += 20
        await message.reply("🔺 Power upgraded! +20 XP, -10 coins")
    else:
        await message.reply("❌ Not enough coins to upgrade.")

@bot.on_message(filters.command("shop") & filters.group)
async def open_shop(_, message: Message):
    await message.reply("🛒 Shop Items:\n- Scroll (10 coins)\n- Shield (15 coins)\n- XP Boost (20 coins)")

@bot.on_message(filters.command("stats") & filters.group)
async def game_stats(_, message: Message):
    chat_id = message.chat.id
    if chat_id not in games:
        return
    stats = [f"@{p['username']} - {p['role']} - {'✅ Alive' if p['alive'] else '❌ Out'}" for p in games[chat_id]]
    await message.reply("📊 Game Stats:\n" + "\n".join(stats))

@bot.on_message(filters.command("leaderboard") & filters.group)
async def leaderboard(_, message: Message):
    all_players = []
    for game in games.values():
        all_players.extend(game)
    top = sorted(all_players, key=lambda x: x['xp'], reverse=True)[:5]
    board = [f"{i+1}. @{p['username']} - XP: {p['xp']}" for i, p in enumerate(top)]
    await message.reply("🌐 Global Leaderboard:\n" + "\n".join(board))

@bot.on_message(filters.command("myleaderboard") & filters.group)
async def my_leaderboard(_, message: Message):
    chat_id = message.chat.id
    if chat_id not in games:
        return
    top = sorted(games[chat_id], key=lambda x: x['xp'], reverse=True)
    board = [f"{i+1}. @{p['username']} - XP: {p['xp']}" for i, p in enumerate(top)]
    await message.reply("🏆 Group Leaderboard:\n" + "\n".join(board))

@bot.on_message(filters.command("help") & filters.group)
async def show_help(_, message: Message):
    await message.reply(
        "🧚‍♀️ *Fairy vs Villain Bot Help*\n"
        "\n/startgame - Start a new game in the group"
        "\n/join - Join the game lobby"
        "\n/leave - Leave the lobby before game starts"
        "\n/end - End or reset the current game"
        "\n/usepower - Use your secret special power"
        "\n/vote - Vote to eliminate a player"
        "\n/upgrade - Upgrade your powers using XP and coins"
        "\n/shop - Buy scrolls, shields, or power-ups"
        "\n/myxp - Check your XP and coins"
        "\n/profile - View your stats and role info"
        "\n/stats - View game status, alive players, and actions"
        "\n/leaderboard - View global leaderboard"
        "\n/myleaderboard - View this group's top players"
        "\n/help - Show how to play, rules, roles and power info",
        parse_mode="markdown"
    )

print("🤖 Fairy vs Villain Bot is running...")
bot.run()
