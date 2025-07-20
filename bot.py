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

@bot.on_message(filters.command("start"))
async def start_message(client, message: Message):
    welcome_text = """
✨ Welcome to Fairy vs Villain — The Ultimate Battle of Magic & Mystery! ✨

Step into a world where enchanting Fairies and cunning Villains clash in a thrilling game of strategy, trust, and deception.

Join the fairy-tale adventure:
- Gather your friends and form alliances.
- Discover your secret role and unique powers.
- Use your wits to survive and outsmart your foes.

Whether you’re a guardian of light or a master of shadows, every decision counts.

Ready to test your skills?  
Type /startgame to create a game lobby and let the battle begin!

Need help? Use /help anytime to learn the rules and master your powers.

May the brightest light shine, and the darkest schemes unravel.  
Good luck, brave player — your destiny awaits! 🌟
"""
    await message.reply(welcome_text)

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
    
    lobbies[chat_id].append({
        "id": user.id,
        "name": user.mention,
        "username": user.username.lower() if user.username else user.first_name.lower(),
        "alive": True
    })

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
                await client.send_message(
                    p["id"],
                    f"🎭 You are a {p['type']} - {p['role']}\n\n🧙 Power: {powers[p['role']]}\n\nUse /usepower in group to activate it."
                )
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
    voter_id = message.from_user.id

    if chat_id not in games:
        return await message.reply("⚠️ No game in progress.")

    players = games[chat_id]["players"]
    votes = games[chat_id].get("votes", {})

    voter = next((p for p in players if p["id"] == voter_id and p["alive"]), None)
    if not voter:
        return await message.reply("❌ You are not in the game or already eliminated.")

    if len(message.command) < 2:
        return await message.reply("❌ Usage: /vote @username")

    target_username = message.command[1].lstrip("@").lower()

    # Find target by username (fall back to name if username missing)
    target = None
    for p in players:
        username = p.get("username") or p["name"].lstrip("@")
        if username.lower() == target_username and p["alive"]:
            target = p
            break

    if not target:
        return await message.reply("❌ Target not found or not alive.")

    # Check if voter already voted
    if voter_id in votes:
        return await message.reply("❌ You already voted this round.")

    # Register vote
    votes[voter_id] = target["id"]
    games[chat_id]["votes"] = votes  # Save votes back

    await message.reply(f"🗳️ Vote registered for {target['name']}!")

    # Count votes per player
    vote_counts = {}
    for t_id in votes.values():
        vote_counts[t_id] = vote_counts.get(t_id, 0) + 1

    # Calculate majority (more than half of alive players)
    alive_count = sum(p["alive"] for p in players)
    majority = alive_count // 2 + 1

    # Check if any player reached majority votes
    for pid, count in vote_counts.items():
        if count >= majority:
            eliminated = next((p for p in players if p["id"] == pid), None)
            if eliminated:
                eliminated["alive"] = False
                await client.send_message(chat_id, f"💀 {eliminated['name']} was eliminated by vote!")
                games[chat_id]["votes"] = {}  # reset votes for next round
            break

            
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
    help_text = r"""
<b>🧚 Welcome to Fairy vs Villain!</b>

<b>🎲 How to Play:</b>
- Players join the game lobby using <code>/join</code>.
- When minimum 4 players have joined, roles are assigned randomly:
  Fairies, Villains, and Commoners.
- Fairies must identify and eliminate Villains.
- Villains try to secretly eliminate Fairies and Commoners.
- Commoners support Fairies by voting wisely.
- Use your unique powers wisely with <code>/usepower</code>.
- Vote to eliminate suspicious players with <code>/vote @username</code>.
- Earn XP and coins by playing, using powers, and winning rounds.
- Upgrade your powers using coins with <code>/upgrade</code> to gain advantage.

<b>📜 Commands:</b>
/startgame — Create a new game lobby in this group  
/join — Join the current game lobby  
/leave — Leave the lobby before game starts  
/end — End the current game  
/usepower — Use your secret special power  
/vote — Vote to eliminate a player (example: /vote @username)  
/upgrade — Upgrade your powers using XP and coins  
/shop — View and buy items with coins  
/myxp — Check your XP and coin balance  
/profile — View your role, stats, and power info  
/stats — See current game status and alive players  
/leaderboard — View global top players  
/myleaderboard — View this group's top players  
/help — Show this help message

<b>📖 Rules:</b>
- Minimum 4 players, maximum 15 per game.  
- Fairies win by eliminating all Villains.  
- Villains win by outnumbering Fairies.  
- Commoners help Fairies by voting carefully.  
- Use powers carefully; some have cooldowns or limits.  
- Voting majority eliminates a player each round.  
- Dead players cannot vote or use powers.

<b>💡 Tips:</b>
- Always communicate and watch for suspicious behavior.  
- Use <code>/usepower</code> privately to turn the tide.  
- Save coins and XP to upgrade powers and items.  
- Stay active and strategize with your team.

Good luck, have fun, and may the best team win! 🧚‍♀️👹
"""
    await message.reply_text(help_text, parse_mode="html")



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
