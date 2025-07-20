# handlers/madras_levelup.py
from pyrogram import Client, filters
from database.users import get_user_stats
from utils.levels import get_upgrade_info

@Client.on_message(filters.command("mylevelup"))
async def show_levelup_path(client, message):
    user_id = message.from_user.id

    stats = await get_user_stats(user_id)
    if not stats:
        await message.reply("❌ You don't have any game data yet.")
        return

    current_level = stats.get("level", 1)
    coins = stats.get("coins", 0)
    xp = stats.get("xp", 0)
    role = stats.get("role", "Unknown")

    upgrade_info = get_upgrade_info(role, current_level)
    if not upgrade_info:
        await message.reply("🎉 You are at the maximum level!")
        return

    next_level = current_level + 1
    coin_cost = upgrade_info["coin_cost"]
    new_power = upgrade_info["power"]

    msg = f"🚀 **Level Up Path for **\n\n"
    msg += f"🔼 Current Level: {current_level}\n"
    msg += f"💰 Coins: {coins}\n"
    msg += f"⭐ XP: {xp}\n\n"
    msg += f"➡️ Next Level: {next_level}\n"
    msg += f"🔓 Unlocks: {new_power}\n"
    msg += f"💸 Cost: {coin_cost} coins\n\n"
    msg += "Use your coins to level up and unlock stronger abilities!"

    await message.reply(msg)
  
