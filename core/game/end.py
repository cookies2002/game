from core.xp import add_xp

for player in winning_players:
    role_type = await get_user_role(player.id)
    await add_xp(user_id=player.id, role_type=role_type, amount=50)
    
for player in winning_team:
    result = await add_xp(player.id, 50)  # 🏆 50 XP for winning

    if result.get("level_up"):
        await bot.send_message(
            player.id,
            f"🏅 Victory Bonus + Level Up!\n"
            f"You're now Level {result['new_level']}!\n"
            f"New Power: {result['new_power']} 💥\n"
            f"Coins Earned: {result['new_coins']}"
        )
      
