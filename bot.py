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
used_powers = {}


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
        return await message.reply("🚫 Game already started! Wait for the next round.")

    # Prevent duplicate join
    if any(p["id"] == user.id for p in games[chat_id]["players"]):
        return await message.reply("✅ You already joined the game.")

    await message.reply(
    "📩 To fully participate, please [START the bot in private chat](https://t.me/fairy_game_bot). "
    "Otherwise you won't receive power instructions!",
    disable_web_page_preview=True
    )
    
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
        [("Fairy", r) for r in random.sample(roles["Fairy"], k=fairy_count)] +
        [("Villain", r) for r in random.sample(roles["Villain"], k=villain_count)] +
        [("Commoner", r) for r in random.sample(roles["Commoner"], k=commoner_count)]
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
# Maintain state for used powers

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

    role = player.get("role")
    power_text = ""
    group_announce = ""
    blocked_alert = ""

    # Only allow 1-time power usage unless special
    if used_powers.get((chat_id, user_id)) and role != "Demon Lord":
        return await callback_query.answer("❌ You have already used your power.", show_alert=True)
    used_powers[(chat_id, user_id)] = True

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
        identity = "Villain" if target["type"] == "Villain" else "Not a Villain"
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
        random_target = random.choice([p for p in game["players"] if p["alive"] and p["id"] != target_id])
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
                await client.send_message(b["id"], f"😱 You were blocked from voting by the Fear Master!")
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
        info = "Villain" if target["type"] == "Villain" else "Fairy or Commoner"
        power_text = f"🕵️ {target['name']} is {info}."

    elif role == "Demon Lord":
        # Special: use power twice (track manually or allow again later)
        if used_powers.get((chat_id, user_id), 0) >= 2:
            return await callback_query.answer("❌ Demon Lord can only use power 2 times.", show_alert=True)
        used_powers[(chat_id, user_id)] = used_powers.get((chat_id, user_id), 0) + 1
        target["vote_blocked"] = True
        target["silenced"] = True
        power_text = f"😈 You silenced and blocked {target['name']} from voting."
        blocked_alert = f"😈 Demon Lord has silenced and blocked you!"

    # --- Final Messaging ---
    await callback_query.answer("✅ Power used!", show_alert=False)
    await client.send_message(user_id, f"🎯 Power Result:\n{power_text}")

    if blocked_alert:
        try:
            await client.send_message(target["id"], blocked_alert)
        except: pass

    if group_announce:
        await client.send_message(chat_id, group_announce)




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
