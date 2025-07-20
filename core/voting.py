from core.xp import add_xp
from database.users import get_user_role

async def process_vote(bot, voter_id: int, target_id: int):
    # ✅ Save vote in your database or memory here...
    # Example: save_vote(voter_id, target_id)

    # 🔍 Get the player's role (hero or villain)
    role_type = await get_user_role(voter_id)

    # 🎯 Add XP for casting a vote
    result = await add_xp(user_id=voter_id, role_type=role_type, amount=10)

    # 🆙 If the player leveled up, DM them the new details
    if result.get("level_up"):
        await bot.send_message(
            voter_id,
            f"🔼 You've leveled up to Level {result['new_level']}!\n"
            f"🌀 New Power: {result['new_power']}\n"
            f"💰 Bonus Coins: {result['new_coins']}"
        )
        
