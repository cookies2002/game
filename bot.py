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

bot = Client("fairy_vs_villain_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, parse_mode=ParseMode.HTML)
mongo = MongoClient(MONGO_URL)
db = mongo.fairy_game

ADMIN_ID = 7813285237
user_data = {}  # Store powers per user
lobbies = {}
games = {}
blocked_powers = {}  # {group_id: set of user_ids who are blocked}
active_powers = {}  # Stores per game player power usage
cooldowns = {}  # Cooldown to prevent spamming power
used_powers = {}

power_prices = {
    "shield": "₹29 - Blocks 1 vote",
    "scroll": "₹49 - Double vote power"
}

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
async def start(client: Client, message: Message):
    await message.reply(
        "🌟 Welcome to Fairy vs Villain!\n"
        "Join a group and type /join to start playing!\n\n"
        "You’ll get secret powers and XP via DM during the game.\n"
        "Make sure you're ready!",
    )

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
        msg = await message.reply("🚫 Game already started! Wait for the next round.")
        await asyncio.sleep(10)
        return await msg.delete()

    if any(p["id"] == user.id for p in games[chat_id]["players"]):
        msg = await message.reply("✅ You already joined the game.")
        await asyncio.sleep(10)
        return await msg.delete()

    # Add player quickly first
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
        "votes": 0,
        "shield_active": False,
        "scroll_active": False,
    })

    # ✅ Quick join confirmation
    current_count = len(games[chat_id]["players"])
    mention = f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"
    join_msg = await message.reply(
        f"🙋 {mention} joined! ({current_count}/15)",
        parse_mode=ParseMode.HTML
    )
    await asyncio.sleep(10)
    await join_msg.delete()

    # 📩 DM Prompt with clickable link
    dm_msg = await message.reply(
        "📩 To fully participate, please <a href='https://t.me/fairy_game_bot'>START the bot in private chat</a>. "
        "Otherwise you won't receive power instructions!",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )
    await asyncio.sleep(10)
    await dm_msg.delete()

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
    players = games[chat_id]["players"]  # ✅ Already a list
    random.shuffle(players)

    total = len(players)
    fairy_count = total // 3
    villain_count = total // 3
    commoner_count = total - fairy_count - villain_count

    assignments = (
        [("Fairy", r) for r in random.sample(roles["Fairy"], k=fairy_count)] +
        [("Villain", r) for r in random.sample(roles["Villain"], k=villain_count)] +
        [("Commoner", r) for r in random.sample(roles["Commoner"], k=commoner_count)]
    )
    random.shuffle(assignments)

    for player, (rtype, rname) in zip(players, assignments):
        player["type"] = rtype
        player["role"] = rname
        player["team"] = rtype if rtype in ["Fairy", "Villain"] else None
        player["alive"] = True
        player["power_used"] = False
        player["power_target"] = None
        player["vote"] = None
        player["joined_team"] = None

        # DM Message
        role_msg = f"🎭 You are a {rtype} - {rname}\n\n🧙 Power: {powers.get(rname, 'None')}"

        if rtype == "Fairy":
            role_msg += (
                "\n\n✨ As a Fairy, your goal is to defeat all Villains.\n"
                "Use /usepower to protect, expose, or strike Villains.\n"
                "Work with Commoners during voting."
            )
        elif rtype == "Villain":
            role_msg += (
                "\n\n😈 As a Villain, your goal is to eliminate all Fairies and Commoners.\n"
                "Use /usepower secretly to destroy or block others.\n"
                "Avoid detection during voting!"
            )
        else:
            role_msg += (
                "\n\n👤 You are a Commoner.\n"
                "You have no powers but your vote is powerful.\n"
                "Work with Fairies to eliminate Villains."
            )

        try:
            await client.send_message(player["id"], role_msg)
        except:
            pass  # Bot can't DM if user didn't start it

    games[chat_id]["roles_assigned"] = True


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
        return await message.reply("💀 Dead players can't use powers.")

    try:
        alive_players = [p for p in games[chat_id]["players"] if p["id"] != user_id and p["alive"]]
        if not alive_players:
            return await client.send_message(user_id, "❌ No valid targets to use your power on.")

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(p["name"], callback_data=f"usepower:{p['id']}:{chat_id}")]
            for p in alive_players
        ])

        await client.send_message(
            user_id,
            f"🎭 You are a {player.get('type')} - {player.get('role')}\n\n🧙 Power: {powers.get(player.get('role'), 'Unknown Power')}\n\nSelect a player to use your power on:",
            reply_markup=keyboard
        )

        await message.reply("🤫 Check your DM to use your power!")
    except Exception:
        await message.reply("❌ Could not DM you. Start a chat with me first.")


@bot.on_callback_query(filters.regex(r"^usepower:(\d+):(-?\d+)$"))
# Updated handle_usepower_callback with proper logic enforcement and DM alerts
# --- Power Usage Handler ---
async def handle_usepower_callback(client, callback_query: CallbackQuery):
    from_user = callback_query.from_user
    target_id, chat_id = map(int, callback_query.matches[0].groups())
    user_id = from_user.id

    if chat_id not in games or not games[chat_id].get("started"):
        return await callback_query.answer("⚠️ Game not found or not started.", show_alert=True)

    game = games[chat_id]
    player = next((p for p in game["players"] if p["id"] == user_id), None)
    target = next((p for p in game["players"] if p["id"] == target_id), None)

    if not player or not target:
        return await callback_query.answer("❌ Invalid player or target.", show_alert=True)
    if not player["alive"]:
        return await callback_query.answer("💀 You are dead!", show_alert=True)

    role = player.get("role", "")
    power_text = ""
    group_announce = ""
    blocked_alert = ""
    chat_key = (chat_id, user_id)

    # --- Power Usage Limitation ---
    if "power_used_count" not in player:
        player["power_used_count"] = 0

    # Allow 2 times for Flame Fairy and Soul Eater only
    allowed_uses = 2 if role in ["Flame Fairy", "Soul Eater"] else 1

    if player["power_used_count"] >= allowed_uses:
        if player.get("scroll_active"):
            player["scroll_active"] = False  # Use scroll
            await client.send_message(user_id, "📜 Scroll used to activate your power again!")
        else:
            return await callback_query.answer(
                "❌ You already used your power.\nBuy a 📜 Scroll to reuse it.",
                show_alert=True
            )

    # ✅ Use power now
    player["power_used_count"] += 1

    # --- Fairy Powers ---
    if role == "Moonlight Fairy":
        target["shielded"] = True
        power_text = f"🛡️ You shielded {target['name']} from attacks this round."
        blocked_alert = "You were shielded by Moonlight Fairy."

    elif role == "Dream Healer":
        target["healed"] = True
        power_text = f"💊 If {target['name']} is attacked, they will be healed."
        blocked_alert = "Dream Healer is protecting you tonight."

    elif role == "Flame Fairy":
        if target.get("shielded"):
            power_text = f"🛡️ {target['name']} was shielded. Your flame failed."
            blocked_alert = "You were attacked but shielded!"
        else:
            target["alive"] = False
            group_announce = f"💀 {target['name']} was burned by a Flame Fairy!"
            power_text = f"🔥 You successfully burned {target['name']}!"
            blocked_alert = f"🔥 You were attacked by a Flame Fairy and eliminated."

    elif role == "Fairy Queen":
        target["power_blocked"] = True
        power_text = f"🚫 {target['name']}'s power is blocked this round."
        blocked_alert = f"🚫 Your power was blocked by the Fairy Queen!"

    elif role == "Star Whisperer":
        identity = "Villain" if target.get("team") == "Villain" else "Not a Villain"
        power_text = f"🔍 Your target {target['name']} is {identity}."

    # --- Villain Powers ---
    elif role == "Soul Eater":
        target["xp_drained"] = True
        power_text = f"☠️ You will absorb XP from {target['name']} if they die."
        blocked_alert = f"☠️ Soul Eater marked you."

    elif role == "Dark Witch":
        target["silenced"] = True
        power_text = f"🔇 {target['name']} is silenced this round."
        blocked_alert = f"🔇 You are silenced by a Dark Witch."

    elif role == "Nightmare":
        alive_targets = [p for p in game["players"] if p["alive"] and p["id"] != target_id]
        if alive_targets:
            random_target = random.choice(alive_targets)
            target["redirect_to"] = random_target["id"]
            power_text = f"🌫️ {target['name']}'s actions are redirected to {random_target['name']}."
            blocked_alert = f"🌫️ Nightmare twisted your power tonight."

    elif role == "Shadow":
        target["blinded"] = True
        power_text = f"🌑 {target['name']}'s vote will not count."
        blocked_alert = f"🌑 You were blinded. Your vote won’t count."

    elif role == "Fear Master":
        alive_others = [p for p in game["players"] if p["id"] != user_id and p["alive"]]
        if len(alive_others) < 2:
            return await callback_query.answer("❌ Not enough players to block.", show_alert=True)
        blocked = random.sample(alive_others, 2)
        for b in blocked:
            b["vote_blocked"] = True
            try:
                await client.send_message(b["id"], "😱 You were blocked from voting by the Fear Master!")
            except: pass
        power_text = f"😱 You blocked {blocked[0]['name']} and {blocked[1]['name']} from voting."
        group_announce = "😨 Fear Master has blocked 2 players from voting this round!"

    # --- Commoner Powers ---
    elif role == "Village Elder":
        player["double_vote"] = True
        power_text = "⚖️ Your vote will have double power."

    elif role == "Ghost":
        if not player.get("used_afterlife_vote"):
            player["afterlife_vote"] = True
            player["used_afterlife_vote"] = True
            power_text = "👻 You may vote once from the afterlife."
        else:
            power_text = "❌ You already used your ghost vote."

    elif role == "Cursed One":
        target["cursed"] = True
        power_text = f"🧿 {target['name']} is cursed and will lose XP next round."
        blocked_alert = f"🧿 You were cursed by the Cursed One."

    elif role == "Fairy Spy":
        info = "Villain" if target.get("team") == "Villain" else "Fairy or Commoner"
        power_text = f"🕵️ {target['name']} is {info}."

    elif role == "Demon Lord":
        target["vote_blocked"] = True
        target["silenced"] = True
        power_text = f"😈 You silenced and blocked {target['name']} from voting."
        blocked_alert = f"😈 Demon Lord has silenced and blocked you!"

    else:
        return await callback_query.answer("❌ No power available for your role.", show_alert=True)

    await callback_query.answer("✅ Power used!", show_alert=False)
    await client.send_message(user_id, f"🎯 Power Result:\n{power_text}")

    if blocked_alert:
        try:
            await client.send_message(target["id"], blocked_alert)
        except:
            pass

    if group_announce:
        await client.send_message(chat_id, group_announce)


#vote
@bot.on_message(filters.command("vote"))
async def vote_player(client, message: Message):
    chat_id = message.chat.id
    voter_id = message.from_user.id

    if chat_id not in games:
        return await message.reply("⚠️ No game in progress.")

    game = games[chat_id]
    players = game["players"]
    votes = game.get("votes", {})

    voter = next((p for p in players if p["id"] == voter_id), None)
    if not voter or (not voter["alive"] and not (voter.get("role") == "Ghost" and not voter.get("ghost_voted"))):
        return await message.reply("❌ You are not in the game or already eliminated.")

    # Restriction checks
    if voter.get("silenced"):
        return await message.reply("🔇 You are silenced and cannot vote this round!")

    if voter.get("vote_blocked"):
        return await message.reply("😨 You are blocked and cannot vote this round!")

    if len(message.command) < 2:
        return await message.reply("❌ Usage: /vote @username")

    target_username = message.command[1].lstrip("@").lower()

    # Find target player
    target = None
    for p in players:
        username = p.get("username") or p["name"].lstrip("@")
        if username.lower() == target_username and p["alive"] and not p.get("invisible"):
            target = p
            break

    if not target:
        return await message.reply("❌ Target not found, not alive, or is invisible.")

    if voter_id in votes:
        return await message.reply("❌ You already voted this round.")

    # 🛡 Check if target has shield
    if target.get("shield_active"):
        target["shield_active"] = False  # Consume shield
        return await message.reply("🛡 The player blocked your vote with a shield!")

    # 🧮 Calculate vote weight
    vote_weight = 1

    # 👻 Ghost logic (one-time vote after death)
    if voter.get("role") == "Ghost" and not voter["alive"]:
        if voter.get("ghost_voted"):
            return await message.reply("👻 You already used your Ghost vote!")
        voter["ghost_voted"] = True

    # 😵‍💫 Shadow blinded (vote = 0)
    if voter.get("blinded"):
        vote_weight = 0
        voter["blinded"] = False  # Consume effect

    # 📜 Scroll power (double vote)
    if voter_player.get("scroll_active"):
        vote_weight = 2
        voter_player["scroll_active"] = False  # Consume scroll

    # 🧓 Village Elder power
    if (
        voter.get("role") == "Village Elder"
        and voter.get("type") == "Commoner"
        and voter.get("double_vote")
    ):
        vote_weight *= 2

    # ✅ Register vote
    votes[voter_id] = {"target_id": target["id"], "weight": vote_weight}
    game["votes"] = votes

    await message.reply(
        f"🗳️ You voted against {target['name']}.\n"
        f"Vote Power: {vote_weight}"
    )

    # 🔢 Count votes
    vote_counts = {}
    for vote in votes.values():
        tid = vote["target_id"]
        weight = vote["weight"]
        vote_counts[tid] = vote_counts.get(tid, 0) + weight

    # 🧮 Calculate total possible voting power (for majority)
    total_votes = 0
    for p in players:
        if p.get("alive") and not p.get("vote_blocked") and not p.get("silenced") and not p.get("invisible"):
            if p.get("blinded"):
                continue
            if p.get("role") == "Village Elder" and p.get("double_vote"):
                total_votes += 2
            else:
                total_votes += 1
        elif p.get("role") == "Ghost" and not p.get("alive") and not p.get("ghost_voted"):
            total_votes += 1

    majority = total_votes // 2 + 1

    # 💀 Check for elimination
    for target_id, count in vote_counts.items():
        if count >= majority:
            eliminated = next((p for p in players if p["id"] == target_id), None)
            if eliminated:
                eliminated["alive"] = False
                await client.send_message(chat_id, f"💀 {eliminated['name']} was eliminated by vote!")

                # Reset votes
                game["votes"] = {}
                for p in players:
                    p["votes"] = 0

                await check_game_end(client, chat_id)
            break


async def check_game_end(client, chat_id):
    game = games.get(chat_id)
    if not game or "players" not in game:
        return

    # Remove dead players from teams
    alive_fairies = [p for p in game["players"] if p.get("alive") and p.get("joined_team") == "Fairy"]
    alive_villains = [p for p in game["players"] if p.get("alive") and p.get("joined_team") == "Villain"]

    if not alive_fairies and alive_villains:
        winner_text = "😈 <b>Villain Team Wins!</b>"
    elif not alive_villains and alive_fairies:
        winner_text = "🧚 <b>Fairy Team Wins!</b>"
    elif not alive_fairies and not alive_villains:
        winner_text = "☠️ <b>All players are dead. No team wins.</b>"
    else:
        return  # Game still going

    # Game ended, announce and reset
    await client.send_message(chat_id, winner_text, parse_mode="HTML")
    del games[chat_id]

    # Game continues


@bot.on_message(filters.command("join_fairy") & filters.group)
async def join_fairy_team(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    username = message.from_user.username
    name = message.from_user.first_name

    game = games.get(chat_id)

    if not game or not game.get("players"):
        await message.reply("❌ No game is currently running.")
        return

    for player in game["players"]:
        if player["id"] == user_id:
            player["joined_team"] = "Fairy"
            await message.reply(
                "🧚 You have joined the <b>Fairy Team</b>!",
                parse_mode=ParseMode.HTML  # ✅ Use correct enum here
            )
            return

    await message.reply("❌ You haven't joined the game yet. Use /join to enter first.")


@bot.on_message(filters.command("join_villain") & filters.group)
async def join_villain_team(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    username = message.from_user.username
    name = message.from_user.first_name

    game = games.get(chat_id)

    if not game or not game.get("players"):
        await message.reply("❌ No game is currently running.")
        return

    for player in game["players"]:
        if player["id"] == user_id:
            player["joined_team"] = "Villain"
            await message.reply(
                "😈 You have joined the <b>Villain Team</b>!",
                parse_mode=ParseMode.HTML  # ✅ Correct Enum
            )
            return

    await message.reply("❌ You haven't joined the game yet. Use /join to enter first.")

    


#team_status
@bot.on_message(filters.command("team_status") & filters.group)
async def team_status(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    game = games.get(chat_id)

    if not game:
        await message.reply("❌ No game is currently running.")
        return

    # Check if user is in the game
    player = next((p for p in game["players"] if p["id"] == user_id), None)
    if not player:
        await message.reply("❌ You haven't joined the game.")
        return

    fairy_team = []
    villain_team = []

    for player in game["players"]:
        uid = player.get("id")
        username = player.get("username")
        name = player.get("name", "Unknown")
        alive = player.get("alive", True)
        team = player.get("joined_team")

        # Create mention
        if username:
            mention = f"@{username}"
        else:
            mention = f"<a href='tg://user?id={uid}'>{name}</a>"

        status = "✅ Alive" if alive else "☠️ Dead"

        if team == "Fairy":
            fairy_team.append(f"• {mention} - {status}")
        elif team == "Villain":
            villain_team.append(f"• {mention} - {status}")

    fairy_text = "\n".join(fairy_team) if fairy_team else "No one joined yet."
    villain_text = "\n".join(villain_team) if villain_team else "No one joined yet."

    msg = (
        "<b>🧚 Fairy Team Members:</b>\n" + fairy_text + "\n\n" +
        "<b>😈 Villain Team Members:</b>\n" + villain_text
    )

    await message.reply(msg, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)


# ✅ Show profile
@bot.on_message(filters.command("profile") & filters.private)
async def show_profile(client: Client, message: Message):
    user_id = message.from_user.id

    for game_chat_id, game in games.items():
        for player in game["players"]:
            if player.get("id") == user_id:
                coins = player.get("coins", 0)
                xp = player.get("xp", 0)
                level = player.get("level", 1)
                role = player.get("role", "🧍 Player")
                shield = player.get("shield", 0)
                scroll = player.get("scroll", 0)
                shield_active = player.get("shield_active", False)
                scroll_active = player.get("scroll_active", False)
                power = level * 10 + xp

                next_level_xp = (level + 1) * 10
                progress = int((xp / next_level_xp) * 10)
                progress_bar = "🟩" * progress + "⬜" * (10 - progress)

                text = (
                    f"👤 <b>Your Profile</b>\n"
                    f"🪪 Name: <b>{message.from_user.first_name}</b>\n"
                    f"🪙 Coins: <b>{coins}</b>\n"
                    f"⭐ XP: <b>{xp}</b>\n"
                    f"⬆️ Level: <b>{level}</b>\n"
                    f"⚡ Power Level: <b>{power}</b>\n"
                    f"📈 XP Progress: <code>[{progress_bar}]</code>\n"
                    f"🎭 Role: <b>{role}</b>\n"
                    f"🛡 Shield: <b>{shield}</b> {'🟢 Active' if shield_active else ''}\n"
                    f"📜 Scroll: <b>{scroll}</b> {'🟢 Active' if scroll_active else ''}"
                )

                buttons = [
                    [InlineKeyboardButton("🎒 View Inventory", callback_data=f"inventory:{game_chat_id}:{user_id}")],
                    [InlineKeyboardButton("🛡 Use Shield", callback_data=f"use_shield:{game_chat_id}:{user_id}")],
                    [InlineKeyboardButton("📜 Use Scroll", callback_data=f"use_scroll:{game_chat_id}:{user_id}")]
                ]

                return await message.reply(
                    text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

    await message.reply("❌ You are not part of an active game.")


# ✅ View inventory
@bot.on_callback_query(filters.regex(r"^inventory:(-?\d+):(\d+)$"))
async def inventory_callback(client: Client, callback_query: CallbackQuery):
    chat_id, user_id = map(int, callback_query.data.split(":")[1:])
    game = games.get(chat_id)
    if not game:
        return await callback_query.answer("❌ Game not found", show_alert=True)

    for player in game["players"]:
        if player.get("id") == user_id:
            shield = player.get("shield", 0)
            scroll = player.get("scroll", 0)

            inventory_text = (
                f"🎒 <b>Your Inventory</b>\n"
                f"🛡 Shield: <b>{shield}</b> {'🟢 Active' if player.get('shield_active') else ''}\n"
                f"📜 Scroll: <b>{scroll}</b> {'🟢 Active' if player.get('scroll_active') else ''}"
            )

            return await callback_query.message.edit_text(
                inventory_text,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data=f"profile_back:{chat_id}:{user_id}")]
                ])
            )

    await callback_query.answer("❌ Player not found", show_alert=True)


# # ✅ Show user profile (with fallback if not in game)
@bot.on_callback_query(filters.regex(r"^show_profile$"))
async def show_profile_callback(client: Client, callback_query: CallbackQuery):
    await show_profile(client, callback_query.message)
    
async def show_profile(client, message):
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else None

    game = games.get(chat_id)
    if not game:
        # 🔁 Fallback: No active game
        text = "👤 Profile:\n(No active game)"
        buttons = [[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]]
        return await message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    # 🔍 Search for player in the game
    player = next((p for p in game.get("players", []) if p.get("id") == user_id), None)
    if player:
        text = f"👤 Profile of {player['name']}"
        buttons = [
            [InlineKeyboardButton("🎒 Inventory", callback_data=f"inventory:{chat_id}:{user_id}")],
            [InlineKeyboardButton("🔙 Back", callback_data=f"profile_back:{chat_id}:{user_id}")]
        ]
        return await message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    # ❌ Player not found in game
    text = "❌ Player not found in the current game."
    buttons = [[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]]
    return await message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))


# 🔁 Callback to go back to profile from inventory
@bot.on_callback_query(filters.regex(r"^profile_back:(-?\d+):(\d+)$"))
async def back_to_profile(client: Client, callback_query: CallbackQuery):
    chat_id, user_id = map(int, callback_query.data.split(":")[1:])
    game = games.get(chat_id)

    if game:
        player = next((p for p in game.get("players", []) if p.get("id") == user_id), None)
        if player:
            # 👤 Go back to profile
            return await show_profile(client, callback_query.message)

    # ⛔ Fallback: game or player not found
    text = "👤 Profile:\n(No active game or user not found)"
    buttons = [[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]]
    return await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@bot.on_callback_query(filters.regex(r"^main_menu$"))
async def main_menu_callback(client, callback_query):
    await callback_query.message.edit_text(
        "🏠 Main Menu",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("▶️ Start Game", callback_data="startgame")],
            [InlineKeyboardButton("👤 Profile", callback_data="show_profile")],  # <-- fixed here
        ])
    )

    

# ✅ Use shield (1-time defense)
@bot.on_callback_query(filters.regex(r"^use_shield:(-?\d+):(\d+)$"))
async def use_shield(client: Client, callback_query: CallbackQuery):
    chat_id, user_id = map(int, callback_query.data.split(":")[1:])
    if callback_query.from_user.id != user_id:
        return await callback_query.answer("🚫 Not your profile", show_alert=True)

    game = games.get(chat_id)
    if not game:
        return await callback_query.answer("❌ Game not found", show_alert=True)

    for player in game["players"]:
        if player["id"] == user_id:
            if player.get("shield", 0) > 0:
                if player.get("shield_active", False):
                    return await callback_query.answer("🛡 Already active!", show_alert=True)
                player["shield"] -= 1
                player["shield_active"] = True
                return await callback_query.answer("🛡 Shield activated! You'll block the next vote.", show_alert=True)
            else:
                return await callback_query.answer("⚠️ No shields left!", show_alert=True)


# ✅ Use scroll (1-time double vote)
@bot.on_callback_query(filters.regex(r"^use_scroll:(-?\d+):(\d+)$"))
async def use_scroll(client: Client, callback_query: CallbackQuery):
    chat_id, user_id = map(int, callback_query.data.split(":")[1:])
    if callback_query.from_user.id != user_id:
        return await callback_query.answer("🚫 Not your profile", show_alert=True)

    game = games.get(chat_id)
    if not game:
        return await callback_query.answer("❌ Game not found", show_alert=True)

    for player in game["players"]:
        if player["id"] == user_id:
            if player.get("scroll", 0) > 0:
                if player.get("scroll_active", False):
                    return await callback_query.answer("📜 Already active!", show_alert=True)
                player["scroll"] -= 1
                player["scroll_active"] = True
                return await callback_query.answer("📜 Scroll activated! Your next vote is doubled.", show_alert=True)
            else:
                return await callback_query.answer("⚠️ No scrolls left!", show_alert=True)

# /buy command
@bot.on_message(filters.command("buy") & filters.private)
async def buy_menu(client, message: Message):
    powers_text = "\n".join([f"🔹 <b>{name.capitalize()}</b>: {desc}" for name, desc in power_prices.items()])
    text = (
        "<b>🛍 Buy Powers</b>\n\n"
        f"{powers_text}\n\n"
        "📸 Send your payment screenshot *here*.\n"
        "🧾 Admin will verify and activate your power.\n\n"
        "⚠️ <i>Send screenshot only after payment!</i>"
    )
    await message.reply(text, parse_mode=ParseMode.HTML)

@bot.on_message(filters.private & filters.photo)
async def handle_payment_screenshot(client, message: Message):
    user = message.from_user
    caption = (
        f"💳 <b>New Purchase Request</b>\n\n"
        f"👤 User: <a href='tg://user?id={user.id}'>{user.first_name}</a>\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"📷 Screenshot below."
    )
    try:
        await client.copy_message(
            chat_id=ADMIN_ID,
            from_chat_id=message.chat.id,
            message_id=message.id,
            caption=caption,
            parse_mode=ParseMode.HTML
        )
        await message.reply("✅ Screenshot sent to admin. Please wait for approval.")
    except Exception as e:
        await message.reply("❌ Failed to send screenshot to admin.")
        print(e)


# /allow command for admin
@bot.on_message(filters.command("allow") & filters.user(ADMIN_ID))
async def allow_power(client, message: Message):
    try:
        _, uid_str, power_name = message.text.split(maxsplit=2)
        user_id = int(uid_str)
        power_name = power_name.lower()

        if power_name not in ["shield", "scroll"]:
            await message.reply("❌ Invalid power name. Use shield, scroll.")
            return

        # Create user entry if not exists
        if user_id not in user_data:
            user_data[user_id] = {}

        if power_name == "vip":
            user_data[user_id]["shield"] = 999  # Unlimited shields for 1 day
        else:
            user_data[user_id][power_name] = True

        await message.reply(f"✅ Power '{power_name}' granted to user {user_id}.")

        # Notify user
        try:
            await client.send_message(user_id, f"🎉 Admin approved your purchase!\nPower '{power_name}' activated.")
        except:
            await message.reply("⚠️ User could not be notified in DM (maybe privacy settings).")
    except ValueError:
        await message.reply("⚠️ Usage: /allow user_id power_name")


    
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

print("🚀 Bot started!")
bot.run()
