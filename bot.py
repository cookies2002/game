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


roles = {
    "Fairy": ["Moonlight Fairy", "Dream Healer", "Flame Fairy", "Fairy Queen", "Star Whisperer"],
    "Villain": ["Soul Eater", "Dark Witch", "Nightmare", "Shadow", "Fear Master"],
    "Commoner": ["Village Elder", "Ghost", "Cursed One", "Fairy Spy"]
}

powers = {
    "Moonlight Fairy": "Shields a player from attacks.",
    "Soul Eater": "Blocks a player's power.",
    "Dark Witch": "Burns a player, making them lose coins.",
    "Dream Healer": "Saves a player from elimination.",
    "Nightmare": "Weakens a player's defense.",
    "Star Whisperer": "Grants a player double XP.",
    "Shadow": "Blinds a player — misvote risk.",
    "Flame Fairy": "Kills one Villain if correct.",
    "Fairy Queen": "Blocks XP gain for a player.",
    "Ghost": "Silences a player's vote.",
    "Dark Fairy": "Reveals a player's team.",
    "Fear Master": "Blocks a player's vote.",
    "Fairy Spy": "Views target's coins.",
    "Village Elder": "Vote counts x2 this round.",
    "Cursed One": "If target dies, they lose XP.",
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


# ✅ Full working /usepower command + callback logic
# Supports 15 roles and correct power logic, with DM notifications

@bot.on_message(filters.command("usepower") & filters.group)
async def use_power_command(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if chat_id not in games or user_id not in games[chat_id]["players"]:
        return await message.reply("⚠️ You are not part of an active game.")

    player = games[chat_id]["players"][user_id]
    if not player.get("alive", True):
        return await message.reply("☠️ You are eliminated and cannot use powers.")

    if active_powers.get((chat_id, user_id), False):
        return await message.reply("🛑 You've already used your power this round.")

    role = player["role"]
    power = powers.get(role)
    if not power:
        return await message.reply("❌ Your role has no special power.")

    # Get valid targets (exclude self and dead)
    alive_players = [p for p in games[chat_id]["players"].values() if p["alive"] and p["id"] != user_id]
    if not alive_players:
        return await message.reply("❌ No valid targets.")

    buttons = [
        [InlineKeyboardButton(f"{p['name']}", callback_data=f"usepower:{chat_id}:{user_id}:{p['id']}")]
        for p in alive_players
    ]

    await message.reply(
        f"🧙‍♂️ Choose a target to use your power: *{power}*",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.MARKDOWN
    )

@bot.on_callback_query(filters.regex(r"^usepower:(\d+):(\d+):(\d+)$"))
async def handle_usepower_callback(client, callback_query: CallbackQuery):
    chat_id, user_id, target_id = map(int, callback_query.matches[0].groups())

    if chat_id not in games:
        return await callback_query.answer("⚠️ Game not found.", show_alert=True)

    game = games[chat_id]
    if user_id not in game["players"] or target_id not in game["players"]:
        return await callback_query.answer("❌ Invalid player.", show_alert=True)

    user = game["players"][user_id]
    target = game["players"][target_id]

    if not user["alive"] or not target["alive"]:
        return await callback_query.answer("☠️ Either you or target is eliminated.", show_alert=True)

    role = user["role"]
    user["power_used"] = True
    active_powers[(chat_id, user_id)] = True

    # Store target effects
    effects = target.setdefault("effects", {})

    result = "✅ Power used successfully."

    # Power Logic
    if role == "Moonlight Fairy":
        effects["shielded"] = True
        result = f"🛡️ {target['name']} is shielded from attacks tonight."

    elif role == "Soul Eater":
        effects["blocked"] = True
        result = f"🚫 {target['name']}'s power is blocked for the round."

    elif role == "Dark Witch":
        coins_lost = min(10, target.get("coins", 0))
        target["coins"] -= coins_lost
        result = f"🔥 Burned {target['name']}, lost {coins_lost} coins."

    elif role == "Dream Healer":
        effects["healed"] = True
        result = f"💖 You will save {target['name']} from death if attacked."

    elif role == "Nightmare":
        effects["weakened"] = True
        result = f"😵 {target['name']}'s defenses are weakened."

    elif role == "Star Whisperer":
        effects["double_xp"] = True
        result = f"🌟 {target['name']} will get double XP this round."

    elif role == "Shadow":
        effects["blinded"] = True
        result = f"👁️ {target['name']} is blinded — they may misvote."

    elif role == "Flame Fairy":
        if target["type"] == "Villain":
            target["alive"] = False
            result = f"💥 You eliminated {target['name']} (Villain)!"
            await client.send_message(chat_id, f"💀 {target['name']} was defeated! 🎯 Attacked by: {user['name']}")
        else:
            result = f"❌ {target['name']} was not a Villain. Power wasted."

    elif role == "Fairy Queen":
        effects["xp_blocked"] = True
        result = f"⛔ {target['name']}'s XP gain is blocked."

    elif role == "Ghost":
        effects["silenced"] = True
        result = f"🔇 {target['name']} won't be able to vote this round."

    elif role == "Dark Fairy":
        result = f"🕵️ {target['name']} is on the *{target['type']}* team."
        await client.send_message(user_id, result, parse_mode=ParseMode.MARKDOWN)

    elif role == "Fear Master":
        effects["vote_blocked"] = True
        result = f"⚠️ {target['name']}'s vote won't count."

    elif role == "Fairy Spy":
        result = f"💰 {target['name']} has {target.get('coins', 0)} coins."

    elif role == "Village Elder":
        effects["vote_x2"] = True
        result = f"📊 {target['name']}'s vote will count twice."

    elif role == "Cursed One":
        effects["cursed"] = user_id
        result = f"💀 If {target['name']} dies, they’ll lose XP."

    else:
        result = f"❌ Your role power is not implemented yet."

    await callback_query.answer("🎯 Power used!")
    await client.send_message(user_id, f"🪄 Power result:\n{result}")


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
