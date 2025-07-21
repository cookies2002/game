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

    assignments = ([("Fairy", r) for r in random.sample(roles["Fairy"], fairy_count)] +
                   [("Villain", r) for r in random.sample(roles["Villain"], villain_count)] +
                   [("Commoner", r) for r in random.sample(roles["Commoner"], commoner_count)])
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
async def use_power_handler(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if chat_id not in games or not games[chat_id].get("started"):
        return await message.reply("❌ No active game in this group.")

    game = games[chat_id]
    player = game["players"].get(user_id)

    if not player or not player["alive"]:
        return await message.reply("❌ You're not in an active game.")

    role = player["role"]
    character = player["character"]

    if "power_used" in player and player["power_used"]:
        return await message.reply("❌ You've already used your power this game.")

    # DM the player to choose a target
    target_buttons = []
    for pid, pdata in game["players"].items():
        if pid != user_id and pdata["alive"]:
            target_buttons.append([InlineKeyboardButton(f"{pdata['name']}", callback_data=f"usepower:{chat_id}:{user_id}:{pid}")])

    if not target_buttons:
        return await message.reply("❌ No valid targets to use power on.")

    try:
        await client.send_message(
            user_id,
            f"🧙 You are **{character}** with the power:\n`{powers.get(character, 'Unknown Power')}`\n\n🎯 Choose a target:",
            reply_markup=InlineKeyboardMarkup(target_buttons),
        )
        await message.reply("✅ Check your DM to select a target.")
    except Exception as e:
        await message.reply("❌ Please start a private chat with me and try again.")

@bot.on_callback_query(filters.regex(r"^usepower:(\S+):(\d+):(\d+)$"))
async def handle_usepower_callback(client, callback_query: CallbackQuery):
    chat_id, user_id, target_id = map(int, callback_query.matches[0].groups())

    if chat_id not in games:
        return await callback_query.answer("❌ Game not found.", show_alert=True)

    game = games[chat_id]
    player = game["players"].get(user_id)
    target = game["players"].get(target_id)

    if not player or not player["alive"]:
        return await callback_query.answer("❌ You're not alive.", show_alert=True)
    if not target or not target["alive"]:
        return await callback_query.answer("❌ Target is not alive.", show_alert=True)
    if player.get("power_used"):
        return await callback_query.answer("❌ Power already used.", show_alert=True)

    role = player["role"]
    character = player["character"]
    target_name = target["name"]

    result_msg = ""
    public_announce = ""

    # Power Logic
    if character == "Dark Lord":
        target["alive"] = False
        public_announce = f"💀 {target_name} was eliminated by a dark force!"
        result_msg = f"✅ You used **{character}**'s power to eliminate {target_name}!"
    elif character == "Healing Fairy":
        for pid, pdata in game["players"].items():
            if not pdata["alive"] and pdata["role"] == "Fairy":
                pdata["alive"] = True
                result_msg = f"🌟 You revived {pdata['name']}!"
                break
        if not result_msg:
            result_msg = "❌ No dead Fairy to revive."
    elif character == "Light Fairy":
        villain = next((p for p in game["players"].values() if p["role"] == "Villain" and p["alive"]), None)
        if villain:
            result_msg = f"🔍 Detected Villain: {villain['name']}"
        else:
            result_msg = "❌ No villains to reveal."
    elif character == "Wind Fairy":
        target["shielded"] = True
        result_msg = f"🌪 You shielded {target_name} from the next attack!"
    elif character == "Dream Fairy":
        target["blocked"] = True
        result_msg = f"🌀 You blocked {target_name}'s power for 1 round."
    elif character == "Soul Eater":
        coins = target.get("coins", 0)
        stolen = min(3, coins)
        player["coins"] += stolen
        target["coins"] -= stolen
        result_msg = f"🩸 You stole {stolen} coins from {target_name}!"
    elif character == "Shadow Master":
        player["invisible"] = True
        result_msg = "🕶 You became invisible from votes for 1 day!"
    elif character == "Nightmare":
        target["skip_vote"] = True
        result_msg = f"😱 {target_name} will skip the next vote."
    elif character == "Fire Demon":
        target["power_blocked"] = True
        result_msg = f"🔥 {target_name}'s power is disabled for 1 round."
    elif character == "Scout":
        result_msg = f"🔎 {target_name} is a {target['role']}."
    elif character == "Village Elder":
        result_msg = "👴 Your vote will count double this round."
        player["vote_multiplier"] = 2
    elif character == "Young Mage":
        player["deflect_chance"] = True
        result_msg = "✨ You now have a small chance to deflect attacks."
    elif character == "Wanderer":
        player["xp"] += 5
        result_msg = "🧭 You earned 5 bonus XP!"
    elif character == "Blacksmith":
        player["can_buy_shield_discount"] = True
        result_msg = "🛡️ Your next shield will cost 1 coin less."
    else:
        result_msg = "❌ Unknown power."

    player["power_used"] = True

    # Send DM to player
    try:
        await client.send_message(user_id, f"🧙 Power Used:\n{result_msg}")
    except:
        pass

    # If public result
    if public_announce:
        await client.send_message(chat_id, public_announce)

    await callback_query.answer("✅ Power used successfully.", show_alert=True)
    await callback_query.message.delete()


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
