# bot.py

from pyrogram import Client, filters
from pyrogram.types import Message
import random
from config import API_ID, API_HASH, BOT_TOKEN
from database import assign_user, get_user, get_power, get_team, get_character, add_xp, get_xp, get_leaderboard

app = Client("fairy_game_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

fairy_characters = {
    "Flora": "🌷 Flower Trap - Block next villain's power",
    "Mira": "🫥 Shimmer Shield - Immune to powers for 2 hrs",
    "Twinkle": "✨ XP Boost - Grant +15 XP to a fairy",
    "Elsa": "❄ Freeze Spell - Freeze villain for 1 hr",
    "Luna": "💖 Heal Glow - Give 10 XP to a fairy"
}

villain_characters = {
    "Malva": "🔥 Burn XP - Remove 10 XP from a fairy",
    "Hexa": "🤯 Confusion Curse - Change fairy's power",
    "Darko": "🔁 XP Swap - Swap XP with a fairy",
    "Vira": "🧲 Power Drain - Steal someone's power",
    "Nox": "🦂 Poison Touch - -5 XP/hr for 3 hrs"
}

@app.on_message(filters.command("join"))
async def join(client, message: Message):
    await message.reply("🌟 You've joined the magical world! Type /getpower to receive your role and magical power.")

@app.on_message(filters.command("getpower"))
async def get_power_command(client, message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    if user_id in get_user:
        await message.reply("🔄 You already received your role today!")
        return

    team = random.choice(["fairy", "villain"])
    if team == "fairy":
        character = random.choice(list(fairy_characters.keys()))
        power = fairy_characters[character]
    else:
        character = random.choice(list(villain_characters.keys()))
        power = villain_characters[character]

    assign_user(user_id, username, team, character, power)

    try:
        await client.send_message(user_id,
            f"🎭 Hello @{username}!
"
            f"You are on Team: {'🧚 Fairy' if team == 'fairy' else '😈 Villain'}
"
            f"Character: {character}
"
            f"Power: {power}

"
            f"Use your power with /usepower @target_username in the group.
"
            f"1️⃣ Use power once a day.
"
            f"🏆 Earn XP and level up your magic!
"
        )
        await message.reply("✅ Role & Power sent via DM!")
    except:
        await message.reply("❗ Please start a private chat with me first, then try again.")

@app.on_message(filters.command("mystats"))
async def mystats(client, message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    if not user:
        await message.reply("❗ You haven't joined yet. Type /join.")
        return
    await message.reply(
        f"🎭 @{user['username']}
"
        f"Team: {user['team'].capitalize()}
"
        f"Character: {user['character']}
"
        f"Power: {user['power']}
"
        f"XP: {get_xp(user_id)}"
    )

@app.on_message(filters.command("leaderboard"))
async def leaderboard(client, message: Message):
    board = get_leaderboard()
    if not board:
        await message.reply("🏆 No players yet.")
        return
    text = "🏆 Leaderboard:
"
    for i, (uid, xp_val) in enumerate(board[:10], start=1):
        user = get_user(uid)
        if user:
            text += f"{i}. @{user['username']} - {xp_val} XP
"
    await message.reply(text)

app.run()
