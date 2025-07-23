from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from config import bot
from bot import games  # Global memory for game state

@bot.on_message(filters.command("profile") & (filters.group | filters.private))
async def show_profile(client: Client, message: Message):
    print(f"📥 Received /profile from {message.from_user.id}")  # ✅ Inside function
    await message.reply("✅ Profile command working!")
    
