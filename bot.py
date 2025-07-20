import os
import asyncio
import random
from pyrogram import Client, filters
from pyrogram.types import Message
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")

bot = Client("fairy_vs_villain_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
mongo = MongoClient(MONGO_URL)
db = mongo.fairy_game

lobbies = {}
games = {}

roles = {
    "Fairy": ["Wind Fairy", "Healing Fairy", "Light Fairy", "Shield Fairy", "Dream Fairy"],
    "Villain": ["Dark Lord", "Shadow Master", "Nightmare", "Soul Eater", "Fire Demon"],
    "Commoner": ["Village Elder", "Young Mage", "Wanderer", "Scout", "Blacksmith"]
}

powers = {
    "Wind Fairy": "Blows away one attack on any player.",
    "Healing Fairy": "Revives a recently defeated Fairy once per game.",
    "Light Fairy": "Reveals one Villain to a Fairy.",
    "Shield Fairy": "Shields any player from vote or attack.",
    "Dream Fairy": "Blocks a Villain's power for one round.",
    "Dark Lord": "Instantly eliminate one player (cooldown 2 rounds).",
    "Shadow Master": "Become invisible from votes for 1 day.",
    "Nightmare": "Send fear—target skips next vote.",
    "Soul Eater": "Steal coins from defeated players.",
    "Fire Demon": "Burn a Fairy’s power for one round.",
    "Village Elder": "Votes count x2.",
    "Young Mage": "Small chance to deflect attack.",
    "Wanderer": "Earn extra XP every round.",
    "Scout": "Can detect if someone is Fairy or Villain.",
    "Blacksmith": "Can buy shield at 1 coin less."
}

# Helper to get alive players in game
def get_alive_players(chat_id):
    return [p for p in games[chat_id]["players"] if p["alive"]]

# /startgame
@bot.on_message(filters.command("startgame"))
async def start_game(client, message: Message):
    chat_id = message.chat.id
    if chat_id in games:
        return await message.reply("⚠️ Game already in progress here.")
    lobbies[chat_id] = []
    await message.reply("🎮 Game lobby created! Players use /join to enter. Minimum 4 players required.")

# /join
@bot.on_message(filters.command("join"))
async def join_game(client, message: Message):
    chat_id = message.chat.id
    user = message.from_user
    if chat_id not in lobbies:
        return await message.reply("❌ No game lobby! Use /startgame to begin.")
    if any(p["id"] == user.id for p in lobbies[chat_id]):
        return await message.reply("✅ You already joined.")
    lobbies[chat_id].append({"id": user.id, "name": user.mention, "alive": True})
    await message.reply(f"🙋 {user.mention} joined! ({len(lobbies[chat_id])}/15)")
    if 4 <= len(lobbies[chat_id]) <= 15:
        await asyncio.sleep(5)
        players = lobbies.pop(chat_id)
        random.shuffle(players)
        roles_assigned = []
        f_count, v_count = 2, 1
        for p in players:
            if f_count > 0:
                role_type = "Fairy"
                f_count -= 1
            elif v_count > 0:
                role_type = "Villain"
                v_count -= 1
            else:
                role_type = "Commoner"
            role_name = random.choice(roles[role_type])
            roles_assigned.append({**p, "role": role_name, "type": role_type})
        games[chat_id] = {"players": roles_assigned, "votes": {}, "phase": "day"}
        await message.reply("🎲 Roles assigned! Check your DM for your role and power.")
        for p in roles_assigned:
            try:
                await client.send_message(p["id"], f"🎭 You are a {p['type']} - {p['role']}\n\n🧙 Power: {powers[p['role']]}\n\nUse /usepower in group to activate it.")
            except:
                pass

# /usepower
@bot.on_message(filters.command("usepower"))
async def use_power(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if chat_id not in games:
        return await message.reply("⚠️ No game in progress.")

    player = next((p for p in games[chat_id]["players"] if p["id"] == user_id), None)
    if not player:
        return await message.reply("❌ You're not in the game.")
    if not player["alive"]:
        return await message.reply("💀 You are defeated and cannot use powers.")

    role = player["role"]
    role_type = player["type"]
    target = None

    if role == "Dark Lord":
        targets = [p for p in games[chat_id]["players"] if p["id"] != user_id and p["alive"]]
        if not targets:
            return await message.reply("🎯 No valid target to attack.")
        target = random.choice(targets)
        target["alive"] = False
        await message.reply(f"🔥 A mysterious force has eliminated {target['name']}!")
        try:
            await client.send_message(target["id"], "☠️ You were eliminated by a dark power.")
        except:
            pass

    elif role == "Light Fairy":
        villains = [p for p in games[chat_id]["players"] if p["type"] == "Villain" and p["id"] != user_id]
        if villains:
            revealed = random.choice(villains)
            await client.send_message(user_id, f"🔍 One villain is: {revealed['name']}")
        else:
            await client.send_message(user_id, "✨ No villains found to reveal.")

    else:
        await client.send_message(user_id, f"🪄 You used your power: {powers[role]}\n(Effect not implemented yet.)")

    await message.reply("🤫 You secretly used your power!")

# /vote
@bot.on_message(filters.command("vote"))
async def vote_player(client, message: Message):
    chat_id = message.chat.id
    user = message.from_user

    if chat_id not in games:
        return await message.reply("⚠️ No game in progress.")

    if len(message.command) < 2:
        return await message.reply("❌ Usage: /vote @username")

    target_username = message.command[1].lstrip("@").lower()
    players = games[chat_id]["players"]

    # Ensure each player has a usable 'username' field
    for p in players:
        if "username" not in p:
            p["username"] = p.get("name", "").replace("@", "").lower()

    # Find voter and target
    @bot.on_message(filters.command("vote") & filters.group)
async def vote_handler(client, message):
    voter_id = message.from_user.id
    voter = next((p for p in players if p["id"] == voter_id and p["alive"]), None)

    if not voter:
        await message.reply("❌ You are not in the game or already eliminated.")
        return

    if len(message.command) < 2:
        await message.reply("⚠️ Please specify a target. Example: /vote @username")
        return

    target_username = message.command[1].lstrip("@").lower()

    target = next(
        (p for p in players if p["username"].lower() == target_username and p["alive"]),
        None
    )

    if not target:
        await message.reply("❌ Target not found or not alive.")
        return

    # Register vote
    game_data.setdefault("votes", {}).setdefault(target["id"], []).append(voter_id)
    await message.reply("🗳️ Vote registered!")

    # Check if majority reached
    alive_players = [p for p in players if p["alive"]]
    total_votes = sum(len(v) for v in game_data["votes"].values())

    if total_votes >= len(alive_players):
        # Count votes
        vote_counts = {}
        for target_id, voter_list in game_data["votes"].items():
            vote_counts[target_id] = vote_counts.get(target_id, 0) + len(voter_list)

        # Get most voted player
        most_voted = max(vote_counts.items(), key=lambda x: x[1])[0]
        eliminated_player = next((p for p in players if p["id"] == most_voted), None)

        if eliminated_player:
            eliminated_player["alive"] = False
            await client.send_message(
                message.chat.id,
                f"💀 {eliminated_player['name']} was eliminated by voting!"
            )

        # Clear votes for next round
        game_data["votes"] = {}


            
# /upgrade
@bot.on_message(filters.command("upgrade"))
async def upgrade_power(client, message: Message):
    await message.reply("⚙️ Upgrade coming soon. Use coins to boost powers!")

# /shop
@bot.on_message(filters.command("shop"))
async def open_shop(client, message: Message):
    await message.reply("🛒 Shop Items:\n- Shield: 3 coins\n- Scroll: 5 coins\n- Extra Vote: 4 coins")

# /myxp
@bot.on_message(filters.command("myxp"))
async def show_xp(client, message: Message):
    await message.reply("⭐ XP: 20 | 💰 Coins: 5 (Sample stats)")

# /profile
@bot.on_message(filters.command("profile"))
async def view_profile(client, message: Message):
    await message.reply("🧝 Profile:\n- Role: Unknown\n- Type: Unknown\n- XP: 20\n- Coins: 5")

# /stats
@bot.on_message(filters.command("stats"))
async def show_stats(client, message: Message):
    chat_id = message.chat.id
    if chat_id not in games:
        return await message.reply("⚠️ No game running.")
    alive = get_alive_players(chat_id)
    await message.reply(f"📊 Game Stats:\n- Alive: {len(alive)}\n- Phase: {games[chat_id]['phase']}")

# /leaderboard
@bot.on_message(filters.command("leaderboard"))
async def global_leaderboard(client, message: Message):
    await message.reply("🌍 Global Leaderboard\n1. PlayerA - 100 XP\n2. PlayerB - 88 XP")

# /myleaderboard
@bot.on_message(filters.command("myleaderboard"))
async def local_leaderboard(client, message: Message):
    await message.reply("🏆 Group Leaderboard\n1. You - 42 XP\n2. Friend - 39 XP")

# /help
@bot.on_message(filters.command("help"))
async def help_menu(client, message: Message):
    await message.reply(
        "<b>🧚 How to Play Fairy vs Villain</b>\n\n"
        "<b>📜 Commands:</b>\n"
        "/startgame - Start a new game in the group\n"
        "/join - Join the game lobby\n"
        "/leave - Leave the lobby before game starts\n"
        "/end - End or reset the current game\n"
        "/usepower - Use your secret special power\n"
        "/vote - Vote to eliminate a player\n"
        "/upgrade - Upgrade your powers using XP and coins\n"
        "/shop - Buy scrolls, shields, or power-ups\n"
        "/myxp - Check your XP and coins\n"
        "/profile - View your stats and role info\n"
        "/stats - View game status, alive players, and actions\n"
        "/leaderboard - View global leaderboard\n"
        "/myleaderboard - View this group's top players\n"
        "/help - Show how to play, rules, roles and power info\n\n"
        "<b>📖 Rules:</b> Minimum 4 players, max 15. Fairies defeat Villains. Commoners help via votes.\n"
        "Use powers strategically. XP and coins help you upgrade!",
        parse_mode="html")

# /end
@bot.on_message(filters.command("end"))
async def end_game(client, message: Message):
    chat_id = message.chat.id
    if chat_id in games:
        del games[chat_id]
        await message.reply("🛑 Game ended. Use /startgame to play again.")
    else:
        await message.reply("⚠️ No game running to end.")

# /leave
@bot.on_message(filters.command("leave"))
async def leave_lobby(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if chat_id in lobbies:
        lobbies[chat_id] = [p for p in lobbies[chat_id] if p["id"] != user_id]
        await message.reply("👋 You left the lobby.")
    else:
        await message.reply("❌ No lobby to leave.")

bot.run()
