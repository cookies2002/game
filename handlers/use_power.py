# handlers/use_power.py
from pyrogram import Client, filters
from database.users import get_user_role_data, is_alive, get_target_user
from core.power_engine import execute_power

@Client.on_message(filters.private & filters.command("use"))
async def use_power(client, message):
    user_id = message.from_user.id
    args = message.text.split()

    if len(args) < 2:
        await message.reply("⚠️ Usage: /use <username or ID>")
        return

    if not await is_alive(user_id):
        await message.reply("💀 You are dead and cannot use powers.")
        return

    role_data = await get_user_role_data(user_id)
    if not role_data:
        await message.reply("❌ Role data not found. Please wait for game to start.")
        return

    target_input = args[1]
    target_user = await get_target_user(target_input)
    if not target_user:
        await message.reply("❌ Target not found. Make sure they are in the game.")
        return

    result = await execute_power(user_id, target_user.id)
    await message.reply(result)
  
