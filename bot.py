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

# /usepower handler
@bot.on_message(filters.command("usepower"))
async def use_power(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if chat_id not in games:
        return await message.reply("⚠️ No game in progress.")

    player = next((p for p in games[chat_id]["players"] if p["id"] == user_id), None)
    if not player or not player["alive"]:
        return await message.reply("❌ You're not in the game or you're defeated.")

    buttons = []
    for target in games[chat_id]["players"]:
        if target["id"] != user_id and target["alive"]:
            buttons.append([InlineKeyboardButton(target["name"], callback_data=f"usepower:{chat_id}:{user_id}:{target['id']}")])

    try:
        await client.send_message(
            user_id,
            f"🎭 You are a {player['type']} - {player['role']}\n\n🧙 Power: {powers.get(player['role'], 'Unknown Power')}\n\nSelect a player to use your power on:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        await message.reply("🤫 Check your DM to use your power!")
    except:
        await message.reply("⚠️ Unable to DM you. Start the bot privately and try again.")


# Handle /usepower callback
@bot.on_callback_query(filters.regex(r"^usepower:(\S+):(\d+):(\d+)$"))
async def handle_usepower_callback(client, callback_query: CallbackQuery):
    chat_id, user_id, target_id = map(int, callback_query.matches[0].groups())

    if chat_id not in games:
        return await callback_query.answer("Game not found.", show_alert=True)

    game = games[chat_id]
    player = next((p for p in game["players"] if p["id"] == user_id), None)
    target = next((p for p in game["players"] if p["id"] == target_id), None)
    if not player or not target:
        return await callback_query.answer("Invalid players.", show_alert=True)

    role = player["role"]
    role_type = player["type"]
    target_type = target["type"]
    result_msg = ""

    try:
        if target.get("burned"):
            return await callback_query.answer("🔥 Target's power is burned this round!", show_alert=True)

        if role == "Light Fairy":
            if target_type == "Villain":
                result_msg = f"🔍 One villain is: {target['name']}"
                await client.send_message(target["id"], "⚠️ A Light Fairy has discovered you are a Villain!")
            else:
                result_msg = f"🔍 {target['name']} is not a villain."

        elif role == "Dream Fairy":
            if target_type == "Villain":
                game.setdefault("blocked_powers", {}).setdefault(chat_id, set()).add(target["id"])
                target["blocked"] = True
                result_msg = f"💤 You blocked {target['name']}'s power for one round!"
                await client.send_message(target["id"], "⚠️ A Fairy's dream magic blocked your power this round!")
            else:
                result_msg = f"😴 {target['name']} is not a Villain. Nothing happened."

        elif role == "Healing Fairy":
            if not target["alive"]:
                target["alive"] = True
                result_msg = f"🌟 You revived {target['name']}!"
                await client.send_message(target["id"], "✨ A Healing Fairy revived you!")
            else:
                result_msg = f"⚠️ {target['name']} is already alive."

        elif role == "Shield Fairy":
            target["shielded"] = True
            result_msg = f"🛡️ You shielded {target['name']} from the next attack or vote."
            await client.send_message(target["id"], "🛡️ You are shielded from the next danger!")

        elif role == "Wind Fairy":
            target["dodged"] = True
            result_msg = f"💨 You blew away any attack on {target['name']} for one round!"
            await client.send_message(target["id"], "💨 A Wind Fairy protected you from attacks this round!")

        elif role == "Dark Lord":
            if target["alive"]:
                if not target.get("shielded"):
                    target["alive"] = False
                    result_msg = f"🔥 You eliminated {target['name']}!"
                    await client.send_message(chat_id, f"💀 {target['name']} was eliminated by a dark force!")
                    await client.send_message(target["id"], "☠️ You were defeated by the Dark Lord.")
                else:
                    result_msg = f"🛡️ {target['name']} was shielded. Attack failed."
            else:
                result_msg = f"{target['name']} is already defeated."

        elif role == "Nightmare":
            if target["alive"]:
                target["feared"] = True
                result_msg = f"🌙 You sent fear into {target['name']}. They will skip the next vote!"
                await client.send_message(target["id"], "😨 You were struck by a Nightmare! You will skip the next vote.")
            else:
                result_msg = f"{target['name']} is already defeated."

        elif role == "Soul Eater":
            if not target["alive"]:
                player["coins"] = player.get("coins", 0) + 2
                result_msg = f"💰 You stole 2 coins from {target['name']}!"
                await client.send_message(target["id"], "🩸 The Soul Eater fed on you even in death.")
            else:
                result_msg = f"{target['name']} is still alive. You can only feed on defeated players."

        elif role == "Shadow Master":
            player["invisible"] = True
            result_msg = f"🕶️ You became invisible from votes for 1 day!"
            await client.send_message(user_id, "👤 No one can vote you for 1 day!")

        elif role == "Fire Demon":
            if target_type == "Fairy":
                target["burned"] = True
                result_msg = f"🔥 You burned {target['name']}'s power for 1 round!"
                await client.send_message(target["id"], "🔥 Your power was burned by the Fire Demon!")
            else:
                result_msg = f"{target['name']} is not a Fairy. Power burn failed."

        elif role == "Village Elder":
            result_msg = "👴 Your votes count double! Use /vote wisely."

        elif role == "Young Mage":
            player["deflect_chance"] = 0.2
            result_msg = "🧙‍♂️ You gained a small chance to deflect one attack."

        elif role == "Wanderer":
            player["xp"] = player.get("xp", 0) + 2
            result_msg = "🚶 You earned extra XP for wandering."

        elif role == "Scout":
            alignment = "Fairy" if target_type == "Fairy" else "Villain" if target_type == "Villain" else "Commoner"
            result_msg = f"🔍 You scouted {target['name']} and found they are a {alignment}."

        elif role == "Blacksmith":
            player["shield_discount"] = True
            result_msg = "🛠️ You now buy shields 1 coin cheaper!"

        else:
            result_msg = f"🪄 You used your power, but nothing happened."

        await callback_query.message.edit_text(result_msg)

    except Exception as e:
        await callback_query.answer("❌ Error occurred. Try again.", show_alert=True)


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

                # ✅ Call the winner check logic
                await check_winner(client, message, games[chat_id])
            break

            
# Winner checking logic
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

    # Fairies + Commoners win
    if not any(p["role"] == "Villain" and p["alive"] for p in players.values()):
        winner_names = [f'<a href="tg://user?id={p["id"]}">{p["name"]}</a>' for p in fairies_commoners_alive]
        await message.reply(
            f"🧚‍♀️ All Villains are defeated!\n\n🏆 <b>Fairy Team Wins!</b>\n🎯 Survivors:\n" + "\n".join(winner_names),
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
