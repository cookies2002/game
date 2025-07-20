from pyrogram import Client, filters
from pyrogram.types import Message
from database.users import get_user_by_id

@Client.on_message(filters.command("myxp"))
async def show_my_xp(client: Client, message: Message):
    user_id = message.from_user.id
    user = await get_user_by_id(user_id)

    if not user:
        await message.reply("❌ You're not registered yet.")
        return

    level = user.get("level", 1)
    xp = user.get("xp", 0)
    coins = user.get("coins", 0)
    role = user.get("role", "Unknown").capitalize()

    await message.reply(
        f"📊 **Your Stats**\n"
        f"🧙 Role: {role}\n"
        f"🔼 Level: {level}\n"
        f"⭐ XP: {xp}\n"
        f"💰 Coins: {coins}"
    )
  
