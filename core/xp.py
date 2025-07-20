# core/xp.py
from database.users import get_user_stats, update_user_stats
from utils.levels import get_upgrade_info

async def add_xp(user_id: int, amount: int):
    stats = await get_user_stats(user_id)
    if not stats:
        return

    current_xp = stats.get("xp", 0)
    level = stats.get("level", 1)
    coins = stats.get("coins", 0)
    role = stats.get("role", "Unknown")

    new_xp = current_xp + amount

    upgrade = get_upgrade_info(role, level)
    required_xp = upgrade.get("xp_required") if upgrade else 9999

    # Level-up if enough XP
    if new_xp >= required_xp and upgrade:
        new_level = level + 1
        new_power = upgrade["power"]
        new_coins = coins + upgrade.get("coin_reward", 10)
        carry_xp = new_xp - required_xp

        await update_user_stats(user_id, {
            "level": new_level,
            "xp": carry_xp,
            "coins": new_coins,
            "power": new_power
        })

        return {
            "level_up": True,
            "new_level": new_level,
            "new_power": new_power,
            "new_coins": new_coins
        }

    else:
        await update_user_stats(user_id, {"xp": new_xp})
        return {
            "level_up": False,
            "xp": new_xp
        }
