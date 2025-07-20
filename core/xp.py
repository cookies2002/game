from pyrogram.enums import ParseMode
from pyrogram.errors import PeerIdInvalid
from utils.levels import get_upgrade_info

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
        print(f"Can't DM user {user_id} — they might not have started the bot.")
        
