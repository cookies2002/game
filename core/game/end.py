from core.xp import add_xp
from database.users import get_user_role

async def reward_winners(bot, winning_players: list):
    for player in winning_players:
        role_type = await get_user_role(player.id)

        result = await add_xp(user_id=player.id, role_type=role_type, amount=50)  # 🏆 50 XP

        if result.get("level_up"):
            await bot.send_message(
                player.id,
                f"🏆 Game Victory Bonus!\n"
                f"🔼 You've leveled up to Level {result['new_level']}!\n"
                f"🌀 New Power: {result['new_power']}\n"
                f"💰 Bonus Coins: {result['new_coins']}"
            )
            
