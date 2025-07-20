from pyrogram import Client, filters
from pyrogram.types import Message
from database.users import get_user_by_id

@Client.on_message(filters.command("myxp"))
async def show_my_xp(client: Client, message: Message):
    user_id = message.from_user.id
    user = await get_user_by_id(user_id)

    if not user:
        await message.reply("❌ You haven't joined the game yet.")
        return

    name = user.get("name", message.from_user.first_name)
    level = user.get("level", 1)
    xp = user.get("xp", 0)
    coins = user.get("coins", 0)
    role = user.get("role", "Unknown").title()
    team = user.get("team", "Hero").title()

    msg = (
        f"📊 **Your Stats, {name}**\n\n"
        f"🎭 Role: {role} ({team})\n"
        f"⭐ XP: {xp}\n"
        f"🔼 Level: {level}\n"
        f"💰 Coins: {coins}\n"
    )

    await message.reply(msg)
    
