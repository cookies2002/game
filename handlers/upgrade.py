# handlers/upgrade.py
from pyrogram import Client, filters
from database.users import get_user_stats, update_user_stats
from utils.levels import get_upgrade_info

@Client.on_message(filters.command("upgrade"))
async def upgrade_level(client, message):
    user_id = message.from_user.id

    stats = await get_user_stats(user_id)
    if not stats:
        await message.reply("❌ You haven't started the game yet.")
        return

    current_level = stats.get("level", 1)
    coins = stats.get("coins", 0)
    role = stats.get("role", "Unknown")

    upgrade_info = get_upgrade_info(role, current_level)
    if not upgrade_info:
        await message.reply("🎉 You are already at the max level!")
        return

    coin_cost = upgrade_info["coin_cost"]
    new_power = upgrade_info["power"]

    if coins < coin_cost:
        await message.reply(f"💸 You need {coin_cost} coins to upgrade, but you only have {coins}.")
        return

    # Upgrade user
    new_level = current_level + 1
    new_coins = coins - coin_cost
    await update_user_stats(user_id, {
        "level": new_level,
        "coins": new_coins,
        "power": new_power
    })

    await message.reply(
        f"✅ Level upgraded to {new_level}!\n"
        f"🎯 New Power Unlocked: {new_power}\n"
        f"💰 Remaining Coins: {new_coins}"
    )
  
