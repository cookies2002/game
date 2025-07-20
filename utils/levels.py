# utils/levels.py

hero_levels = {
    1: {"xp_required": 0, "power": "Rasengan", "coin_reward": 0},
    2: {"xp_required": 50, "power": "Giant Rasengan", "coin_reward": 10},
    3: {"xp_required": 120, "power": "Shadow Clone Strike", "coin_reward": 20},
    4: {"xp_required": 220, "power": "Sage Mode", "coin_reward": 30},
    5: {"xp_required": 350, "power": "Baryon Mode", "coin_reward": 50},
}

villain_levels = {
    1: {"xp_required": 0, "power": "Fireball Jutsu", "coin_reward": 0},
    2: {"xp_required": 60, "power": "Susano'o", "coin_reward": 15},
    3: {"xp_required": 130, "power": "Rinnegan Absorption", "coin_reward": 25},
    4: {"xp_required": 230, "power": "Limbo Clone Strike", "coin_reward": 35},
    5: {"xp_required": 360, "power": "Infinite Tsukuyomi", "coin_reward": 60},
}


def get_upgrade_info(role_type: str, current_level: int):
    """
    Returns the next level info: XP needed, new power, coins.
    """
    role_type = role_type.lower()
    if current_level >= 5:
        return None  # Max level reached

    if role_type in ["hero", "hokage", "shinobi"]:
        return hero_levels.get(current_level + 1)
    else:
        return villain_levels.get(current_level + 1)


def get_xp_requirement(role_type: str, level: int) -> int:
    """
    Returns the XP required to reach a given level.
    """
    role_type = role_type.lower()
    if role_type in ["hero", "hokage", "shinobi"]:
        return hero_levels.get(level, {}).get("xp_required", 9999)
    else:
        return villain_levels.get(level, {}).get("xp_required", 9999)
      
