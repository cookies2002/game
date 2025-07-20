# handlers/profile.py
from pyrogram import Client, filters
from database.users import get_user_stats

@Client.on_message(filters.command("profile"))
async def show_profile(client, message):
    user = message.from_user
    stats = await get_user_stats(user.id)

    if not stats:
        await message.reply("❌ You haven't joined the game yet.")
        return

    text = (
        f"👤 **{user.first_name}'s Profile**\n"
        f"🏅 Role: {stats.get('role', 'Unknown')}\n"
        f"🔥 Power: {stats.get('power', 'None')}\n"
        f"📈 Level: {stats.get('level', 1)}\n"
        f"💰 Coins: {stats.get('coins', 0)}\n"
        f"⭐ XP: {stats.get('xp', 0)}"
    )
    await message.reply(text)
