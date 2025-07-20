from pyrogram import Client, filters
from pyrogram.types import Message
from database.users import get_user_by_id, update_user
from datetime import datetime, timedelta

DAILY_COINS = 50

@Client.on_message(filters.command("dailyreward"))
async def claim_daily_reward(client: Client, message: Message):
    user_id = message.from_user.id
    user = await get_user_by_id(user_id)

    if not user:
        await message.reply("❌ You are not registered yet.")
        return

    last_claim = user.get("last_daily")
    now = datetime.utcnow()

    if last_claim:
        last_time = datetime.fromisoformat(last_claim)
        if now - last_time < timedelta(hours=24):
            remaining = timedelta(hours=24) - (now - last_time)
            hours, remainder = divmod(remaining.seconds, 3600)
            minutes = remainder // 60
            await message.reply(f"⏳ You’ve already claimed your daily reward.\nTry again in **{hours}h {minutes}m**.")
            return

    # Update coins and timestamp
    new_coins = user.get("coins", 0) + DAILY_COINS
    await update_user(user_id, {
        "coins": new_coins,
        "last_daily": now.isoformat()
    })

    await message.reply(
        f"🎉 You claimed your daily reward of 💰 {DAILY_COINS} coins!\n"
        f"Your new balance: **{new_coins} coins**."
    )
  
