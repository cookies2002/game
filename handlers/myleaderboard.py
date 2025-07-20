from pyrogram import Client, filters
from pyrogram.types import Message
from database.users import get_group_top_players

@Client.on_message(filters.command("myleaderboard") & filters.group)
async def show_group_leaderboard(client: Client, message: Message):
    chat_id = message.chat.id
    top_players = await get_group_top_players(chat_id, limit=10)

    if not top_players:
        await message.reply("📊 No data for this group yet.")
        return

    text = f"📍 **Leaderboard for {message.chat.title}**\n\n"
    for i, player in enumerate(top_players, start=1):
        name = player.get("name") or f"Player {i}"
        xp = player.get("xp", 0)
        coins = player.get("coins", 0)
        level = player.get("level", 1)
        text += f"{i}. {name} — 💰 {coins} | ⭐ {xp} XP | 🔼 Level {level}\n"

    await message.reply(text)
  
