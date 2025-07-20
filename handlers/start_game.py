# handlers/start_game.py
from pyrogram import Client, filters
from core.game import start_game
from handlers.dm_role import dm_role_details
from database.users import get_all_players

@Client.on_message(filters.command("startgame") & filters.group)
async def handle_start_game(client, message):
    if not message.from_user:
        return

    chat_id = message.chat.id
    started = await start_game(chat_id)

    if not started:
        await message.reply("❌ Failed to start game. Make sure enough players joined.")
        return

    players = await get_all_players(chat_id)
    for user_id in players:
        await dm_role_details(client, user_id)

    await message.reply("🎮 Game started! Roles have been assigned and DMed to players.")
  
