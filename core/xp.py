from pyrogram.enums import ParseMode
from pyrogram.errors import PeerIdInvalid
from pyrogram import Client
from database.users import get_user_data, update_user_xp_level_coins
from utils.levels import get_upgrade_info

# Pyrogram Client (import the existing bot client if shared elsewhere)
app = Client("game_bot")

async def add_xp(user_id: int, role_type: str, amount: int):
    user = await get_user_data(user_id)
    if not user:
        return

    current_xp = user.get("xp", 0)
    current_level = user.get("level", 1)
    new_xp = current_xp + amount

    # Fetch next level info
    next_level_info = get_upgrade_info(role_type, current_level)

    if not next_level_info or new_xp < next_level_info["xp_required"]:
        await update_user_xp_level_coins(user_id, xp=new_xp)
        return

    # Level up!
    new_level = current_level + 1
    coin_reward = next_level_info["coin_reward"]

    await update_user_xp_level_coins(
        user_id,
        xp=new_xp,
        level=new_level,
        coins=user.get("coins", 0) + coin_reward,
    )

    await notify_level_up(user_id, new_level, role_type)

async def notify_level_up(user_id: int, new_level: int, role_type: str):
    upgrade = get_upgrade_info(role_type, new_level - 1)
    if not upgrade:
        return

    try:
        text = (
            f"🆙 <b>You've reached Level {new_level}!</b>\n\n"
            f"🔓 New Power: <b>{upgrade['power']}</b>\n"
            f"💰 Coins Earned: <b>{upgrade['coin_reward']}</b>\n"
            f"⚔️ Role: <b>{role_type.title()}</b>\n"
        )

        next_info = get_upgrade_info(role_type, new_level)
        if next_info:
            text += (
                f"\n📈 Next Level: <b>{new_level + 1}</b>\n"
                f"🔼 XP Needed: <code>{next_info['xp_required']}</code>\n"
                f"🎁 Next Power: <b>{next_info['power']}</b>"
            )
        else:
            text += "\n🌟 You have reached the final level. Max power unlocked!"

        text += "\n\n💡 Use /mylevelup to check progress anytime."

        await app.send_message(user_id, text, parse_mode=ParseMode.HTML)

    except PeerIdInvalid:
        print(f"❌ Can't DM user {user_id} — they might not have started the bot.")
        
