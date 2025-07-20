from pyrogram import Client, filters
from pyrogram.types import Message
from database.users import get_user_by_id, update_user

UPGRADE_COST = 100  # Customize this
XP_BOOST = 50       # Bonus XP for coin use

@Client.on_message(filters.command("usecoin"))
async def use_coin_to_upgrade(client: Client, message: Message):
    user_id = message.from_user.id
    user = await get_user_by_id(user_id)

    if not user:
        await message.reply("❌ You are not registered yet.")
        return

    coins = user.get("coins", 0)
    xp = user.get("xp", 0)

    if coins < UPGRADE_COST:
        await message.reply(f"💰 You need at least {UPGRADE_COST} coins to upgrade!\nYour balance: {coins} coins.")
        return

    # Deduct coins and add XP
    new_coins = coins - UPGRADE_COST
    new_xp = xp + XP_BOOST

    await update_user(user_id, {
        "coins": new_coins,
        "xp": new_xp
    })

    await message.reply(
        f"✅ You spent {UPGRADE_COST} coins!\n"
        f"⭐ Gained {XP_BOOST} XP\n"
        f"💰 New balance: {new_coins} coins"
    )
  
