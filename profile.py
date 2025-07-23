from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from config import bot
from bot import games  # Global memory for game state

# ✅ /profile command
@bot.on_message(filters.command("profile") & filters.private)
async def show_profile(client: Client, message: Message):
    user = message.from_user
    name = user.first_name or "Unknown"
    username = f"@{user.username}" if user.username else "No username"
    user_id = user.id

    text = (
        f"👤 <b>Your Profile</b>\n\n"
        f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
        f"👤 <b>Name:</b> {name}\n"
        f"🔗 <b>Username:</b> {username}"
    )

    await message.reply(text, parse_mode="html")
