from core.xp import add_xp
# Example usage
await add_xp(user_id=message.from_user.id, role_type="hero", amount=20)


# After successful power usage:
result = await add_xp(user_id, 20)  # 🎯 20 XP for using power

if result.get("level_up"):
    await bot.send_message(
        user_id,
        f"🔼 You've leveled up to Level {result['new_level']}!\n"
        f"New Power: {result['new_power']} 🌀\n"
        f"Bonus Coins: 💰 {result['new_coins']}"
    )
  
