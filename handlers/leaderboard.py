# handlers/leaderboard.py
from pyrogram import Client, filters
from database.users import get_top_players

@Client.on_message(filters.command("leaderboard") & filters.group)
async def show_leaderboard(client, message):
    top_players = await get_top_players(limit=10)

    if not top_players:
        await message.reply("🏆 No leaderboard data available yet.")
        return

    leaderboard_text = "🏆 **Global Leaderboard**\n\n"
    for i, player in enumerate(top_players, start=1):
        name = player.get("name", "Unknown")
        coins = player.get("coins", 0)
        xp = player.get("xp", 0)
        level = player.get("level", 1)
        leaderboard_text += f"{i}. {name} - 💰 {coins} coins | ⭐ {xp} XP | 🔼 Level {level}\n"

    await message.reply(leaderboard_text)
  
