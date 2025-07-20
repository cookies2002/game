# handlers/dm_role.py
from pyrogram import Client
from database.users import get_user_role_data, get_user_level

async def dm_role_details(bot: Client, user_id: int):
    role_data = await get_user_role_data(user_id)
    level = await get_user_level(user_id)

    if not role_data:
        return

    power_desc = role_data.get("description", "No description available.")
    power_name = role_data.get("power", "Unknown Power")
    role_name = role_data.get("name", "Unknown Role")

    message = f"🎭 **Your Role:** {role_name}\n💠 **Power:** {power_name} (Lvl {level})\n\n"\
              f"🔍 **How to use:** Use `/use <target>` in private chat to activate.\n\n"\
              f"📈 Check `/levelup` to upgrade and unlock stronger abilities.\n💰 Earn coins by surviving, winning, or using powers smartly.\n\n🧠 Power Info:\n{power_desc}"

    try:
        await bot.send_message(user_id, message)
    except Exception as e:
        print(f"❌ Failed to DM user {user_id}: {e}")
      
