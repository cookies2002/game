import os
import asyncio
import random
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient
from dotenv import load_dotenv
from pyrogram.enums import ParseMode

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
blocked_powers = {}  # {group_id: set of user_ids who are blocked}
active_powers = {}  # Stores per game player power usage
cooldowns = {}  # Cooldown to prevent spamming power


# Roles and Powers
roles = {
    "Fairy": ["Moonlight Fairy", "Dream Healer", "Flame Fairy", "Fairy Queen", "Star Whisperer"],
    "Villain": ["Soul Eater", "Dark Witch", "Nightmare", "Shadow", "Fear Master"],
    "Commoner": ["Village Elder", "Ghost", "Cursed One", "Fairy Spy"]
}

powers = {
    "Moonlight Fairy": "Shields one player for the night. Prevents any attack.",
    "Dream Healer": "Heals one Fairy or Commoner if attacked.",
    "Flame Fairy": "Burns a Villain. If not shielded, target is eliminated.",
    "Fairy Queen": "Blocks a Villain's power for one round.",
    "Star Whisperer": "Reveals if target is Villain (doesn’t say name).",

    "Soul Eater": "Absorbs XP from a defeated player.",
    "Dark Witch": "Silences a player for one round. They can’t vote or use power.",
    "Nightmare": "Creates a fake illusion. Redirects one player’s action to another.",
    "Shadow": "Blinds one player. Their vote won’t count.",
    "Fear Master": "Blocks two players from voting for one round.",

    "Village Elder": "Votes have double weight.",
    "Ghost": "Can vote even after death (once).",
    "Cursed One": "Curses a player — they lose XP next round.",
    "Fairy Spy": "Learns if someone is Fairy or Villain."
}




def get_alive_players(chat_id):
    return [p for p in games[chat_id]["players"] if p["alive"]]

@bot.on_message(filters.command("start"))
async def start_message(client, message: Message):
    await message.reply("Welcome to Fairy vs Villain! Use /startgame to begin.")

@bot.on_message(filters.command("startgame"))
async def start_game(client, message: Message):
    chat_id = message.chat.id
    if chat_id in games:
        return await message.reply("⚠️ Game already in progress here.")
    lobbies[chat_id] = []
    await message.reply("🎮 Game lobby created! Players use /join to enter. Minimum 4 players required.")

@bot.on_message(filters.command("join"))
async def join_game(client: Client, message: Message):
    chat_id = message.chat.id
    user = message.from_user

    if message.chat.type == "private":
        return await message.reply("❌ This command only works in groups.")

    if chat_id not in games:
        games[chat_id] = {
            "players": [],
            "started": False,
            "roles_assigned": False,
        }

    if games[chat_id]["started"]:
        return await message.reply("🚫 Game already started! Wait for the next round.")

    # Prevent duplicate join
    if any(p["id"] == user.id for p in games[chat_id]["players"]):
        return await message.reply("✅ You already joined the game.")

    # Add player
    games[chat_id]["players"].append({
        "id": user.id,
        "name": user.first_name,
        "username": user.username or f"id{user.id}",
        "alive": True,
        "role": None,
        "type": None,
        "xp": 0,
        "coins": 0,
        "level": 1,
    })

    current_count = len(games[chat_id]["players"])
    mention = f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"
    await message.reply(f"🙋 {mention} joined! ({current_count}/15)", parse_mode=ParseMode.HTML)

    # Start countdown if 4+ players
    if current_count >= 4 and not games[chat_id]["started"]:
        countdown_msg = await message.reply("⏳ 60 seconds until game auto-starts. Others can still /join!")

        async def countdown_start():
            await asyncio.sleep(60)
            await countdown_msg.delete()
            if not games[chat_id]["started"] and len(games[chat_id]["players"]) >= 4:
                games[chat_id]["started"] = True
                await assign_roles_and_start(client, chat_id)
                await client.send_message(
                    chat_id,
                    "🎲 <b>Roles assigned! Check your DM for your role and power.</b>",
                    parse_mode=ParseMode.HTML

                )

        asyncio.create_task(countdown_start())


async def assign_roles_and_start(client, chat_id):
    players = games[chat_id]["players"]
    random.shuffle(players)
    total = len(players)
    fairy_count = total // 3
    villain_count = total // 3
    commoner_count = total - fairy_count - villain_count

    assignments = (
        [("Fairy", r) for r in random.choices(roles["Fairy"], k=fairy_count)] +
        [("Villain", r) for r in random.choices(roles["Villain"], k=villain_count)] +
        [("Commoner", r) for r in random.choices(roles["Commoner"], k=commoner_count)]
    )
    random.shuffle(assignments)

    for player, (rtype, rname) in zip(players, assignments):
        player["type"] = rtype
        player["role"] = rname
        try:
            await client.send_message(
                player["id"],
                f"🎭 You are a {rtype} - {rname}\n\n🧙 Power: {powers.get(rname, 'None')}"
            )
        except:
            pass
            games[chat_id]["roles_assigned"] = True


# Continuing from your existing code, we now add the `/usepower` command
# and its callback button interaction logic

@bot.on_message(filters.command("usepower"))
async def use_power_handler(client: Client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if chat_id not in games or not games[chat_id].get("started"):
        return await message.reply("⚠️ You are not part of an active game.")

    player = next((p for p in games[chat_id]["players"] if p["id"] == user_id), None)
    if not player:
        return await message.reply("⚠️ You're not in this game.")

    if not player["alive"]:
        return await message.reply("💀 Dead players can't use power.")

    try:
        peer = InputPeerUser(user_id, 0)
        alive_players = [p for p in games[chat_id]["players"] if p["id"] != user_id and p["alive"]]
        
        if not alive_players:
            return await client.send_message(user_id, "❌ No valid targets to use your power on.")

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(p["name"], callback_data=f"usepower:{p['id']}:{chat_id}")]
            for p in alive_players
        ])

        await client.send_message(
            user_id,
            f"🎭 You are a {player['type']} - {player['role']}\n\n🧙 Power: {powers.get(player['role'], 'None')}\n\nSelect a player to use your power on:",
            reply_markup=keyboard
        )

        await message.reply("🤫 Check your DM to use your power!")
    except Exception as e:
        await message.reply("❌ Could not DM you. Start a chat with me first.")


@bot.on_callback_query(filters.regex("^usepower:(\\d+):(\\-?\\d+)$"))
async def power_button_handler(client: Client, callback: CallbackQuery):
    target_id, chat_id = map(int, callback.data.split(":")[1:])
    user_id = callback.from_user.id
    player = next((p for p in games[chat_id]["players"] if p["id"] == user_id), None)
    target = next((p for p in games[chat_id]["players"] if p["id"] == target_id), None)

    if not player or not target or not player["alive"] or not target["alive"]:
        return await callback.answer("Invalid target or you're not alive.", show_alert=True)

    role = player["role"]
    role_type = player["type"]
    power_text = ""
    public_announce = ""

    if role == "Flame Fairy":
        if target["type"] == "Villain":
            target["alive"] = False
            power_text = f"✅ Power used successfully on @{target['username']}!\n🎯 Your Flame Fairy burned them to ashes!"
            public_announce = f"🔥 @{target['username']} was defeated by a Flame Fairy!"
        else:
            power_text = f"⚠️ @{target['username']} is not a Villain. Your Flame Fairy power failed."
    elif role == "Fairy Queen":
        blocked_powers.setdefault(chat_id, set()).add(target_id)
        power_text = f"✅ You blocked @{target['username']}'s power this round."
    elif role == "Dark Witch":
        blocked_powers.setdefault(chat_id, set()).add(target_id)
        power_text = f"🪄 You silenced @{target['username']}. They can't vote or use powers this round."
    elif role == "Fairy Spy":
        power_text = f"🕵️ Target @{target['username']} is a {target['type']}!"
    else:
        power_text = f"✅ You used your power on @{target['username']}."

    await callback.message.edit_text(power_text)

    if public_announce:
        await client.send_message(chat_id, public_announce)

    if target["id"] != user_id:
        try:
            await client.send_message(
                target["id"], f"⚡ A {role} just used their power on you!"
            )
        except:
            pass


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

    if voter.get("feared"):
        return await message.reply("😨 You are feared and cannot vote this round!")

    if len(message.command) < 2:
        return await message.reply("❌ Usage: /vote @username")

    target_username = message.command[1].lstrip("@").lower()

    # Find the target player by username
    target = None
    for p in players:
        username = p.get("username") or p["name"].lstrip("@")
        if (
            username.lower() == target_username
            and p["alive"]
            and not p.get("invisible")
        ):
            target = p
            break

    if not target:
        return await message.reply("❌ Target not found, not alive, or is invisible.")

    if voter_id in votes:
        return await message.reply("❌ You already voted this round.")

    # Register the vote
    votes[voter_id] = target["id"]
    games[chat_id]["votes"] = votes

    await message.reply(f"🗳️ Your vote for {target['name']} has been registered!")

    # Tally the votes
    vote_counts = {}
    for t_id in votes.values():
        vote_counts[t_id] = vote_counts.get(t_id, 0) + 1

    # Majority calculation
    alive_count = sum(p["alive"] and not p.get("invisible") for p in players)
    majority = alive_count // 2 + 1

    # Check if someone has majority votes
    for pid, count in vote_counts.items():
        if count >= majority:
            eliminated = next((p for p in players if p["id"] == pid), None)
            if eliminated:
                eliminated["alive"] = False
                await client.send_message(chat_id, f"💀 {eliminated['name']} was eliminated by vote!")

                games[chat_id]["votes"] = {}  # Reset votes

                # ✅ FIXED: Correct winner check logic
                await check_game_end(client, message, games[chat_id])
            break
            
async def check_game_end(client, message, game):
    chat_id = message.chat.id
    players = game["players"]

    alive_players = [p for p in players.values() if p["alive"]]

    villains_alive = [p for p in alive_players if p["role"] == "Villain"]
    fairies_commoners_alive = [p for p in alive_players if p["role"] in ["Fairy", "Commoner"]]

    # Villains win
    if len(villains_alive) >= len(fairies_commoners_alive):
        winner_names = [f'<a href="tg://user?id={p["id"]}">{p["name"]}</a>' for p in villains_alive]
        await message.reply(
            f"💀 Villains have taken over!\n\n🏆 <b>Villain Team Wins!</b>\n🎯 Survivors:\n" + "\n".join(winner_names),
            parse_mode=ParseMode.HTML
        )
        games.pop(chat_id, None)
        return

    # Fairies/Commoners win
    if len(villains_alive) == 0:
        winner_names = [f'<a href="tg://user?id={p["id"]}">{p["name"]}</a>' for p in fairies_commoners_alive]
        await message.reply(
            f"🧚‍♀️ Villains have been defeated!\n\n🏆 <b>Fairy Team Wins!</b>\n🎉 Survivors:\n" + "\n".join(winner_names),
            parse_mode=ParseMode.HTML
        )
        games.pop(chat_id, None)
        return


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
    
#/stats
@bot.on_message(filters.command("stats"))
async def show_stats(client, message: Message):
    chat_id = message.chat.id
    if chat_id not in games:
        return await message.reply("⚠️ No game running.")
    alive = get_alive_players(chat_id)
    phase = games[chat_id].get('phase', '❓ Unknown')
    await message.reply(f"📊 Game Stats:\n- Alive: {len(alive)}\n- Phase: {phase}")

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
    help_text = """
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
    await message.reply_text(help_text, parse_mode=ParseMode.HTML)
    
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
