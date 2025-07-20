# handlers/levelup.py
from pyrogram import Client, filters
from database.users import get_user_level, get_user_xp, get_user_coins, upgrade_user_level, get_user_role_data

LEVEL_COST = {
    1: 20,
    2: 40,
    3: 70,
    4: 100,
    5: 150
}

@Client.on_message(filters.private & filters.command("levelup"))
async def levelup_handler(client, message):
    user_id = message.from_user.id
    level = await get_user_level(user_id)
    xp = await get_user_xp(user_id)
    coins = await get_user_coins(user_id)
    role_data = await get_user_role_data(user_id)

    next_level = level + 1
    cost = LEVEL_COST.get(level, None)

    if not role_data:
        await message.reply("❌ You don't have a role assigned yet. Wait for the game to begin.")
        return

    if cost is None:
        await message.reply("🏆 You have reached the max level!")
        return

    msg = f"🎮 Your Role: {role_data['name']}\n💠 Power: {role_data['power']}\n⭐ Level: {level}\n💰 Coins: {coins}\n🧪 XP: {xp}"
    msg += f"\n\n➡️ To upgrade to Level {next_level}, you need {cost} coins.\nUse `/upgrade` to level up if you have enough."
    await message.reply(msg)

@Client.on_message(filters.private & filters.command("upgrade"))
async def upgrade_command(client, message):
    user_id = message.from_user.id
    level = await get_user_level(user_id)
    coins = await get_user_coins(user_id)

    cost = LEVEL_COST.get(level, None)
    if cost is None:
        await message.reply("🏆 You're already at the max level!")
        return

    if coins < cost:
        await message.reply(f"❌ You need {cost} coins to upgrade. You only have {coins}.")
        return

    await upgrade_user_level(user_id)
    await message.reply(f"✅ Level up successful! You're now Level {level + 1}. New powers may be unlocked!")
  
