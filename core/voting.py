# After a user casts a valid vote:
from core.xp import add_xp

result = await add_xp(voter.id, 10)  # 🗳️ 10 XP for participating in vote

if result.get("level_up"):
    await bot.send_message(
        voter.id,
        f"🔼 Level Up! You're now Level {result['new_level']}\n"
        f"New Power Unlocked: {result['new_power']}\n"
        f"💰 Bonus Coins: {result['new_coins']}"
    )
  
