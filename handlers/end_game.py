# handlers/end_game.py
from pyrogram import Client, filters
from core.game import end_game_session

@Client.on_message(filters.command("endgame") & filters.group)
async def handle_end_game(client, message):
    if not message.from_user:
        return

    chat_id = message.chat.id
    ended = await end_game_session(chat_id)

    if ended:
        await message.reply("🛑 Game session ended. Leaderboard and stats saved.")
    else:
        await message.reply("❌ No active game session found to end.")
      
