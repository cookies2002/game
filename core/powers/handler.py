from pyrogram.types import Message
from core.xp import add_xp
from database.users import get_user_role

async def handle_power_use(bot, message: Message):
    user_id = message.from_user.id

    # 🛡️ You may add your power execution logic here...
    # For example: applying damage, silencing, etc.

    # 🔍 Get the player's role (hero or villain)
    role_type = await get_user_role(user_id)

    # 🎯 Add XP for using a power
    result = await add_xp(user_id=user_id, role_type=role_type, amount=20)

    # 🆙 If player leveled up, DM them the new power and rewards
    if result.get("level_up"):
        await bot.send_message(
            user_id,
            f"🔼 You've leveled up to Level {result['new_level']}!\n"
            f"🌀 New Power: {result['new_power']}\n"
            f"💰 Bonus Coins: {result['new_coins']}"
        )
        
