# core/game.py
from database.games import create_game, end_game, get_game, update_phase
from database.users import assign_role, get_alive_players, reset_players
from core.power_engine import apply_phase_effects
import random

async def start_game(group_id: int, players: list):
    """Initialize game, assign roles, DM each player."""
    roles = randomize_roles(players)
    for player_id, role in roles.items():
        await assign_role(player_id, role)
    await create_game(group_id, players)
    return roles

async def end_game_session(group_id: int):
    await end_game(group_id)
    await reset_players()

async def next_phase(group_id: int):
    game = await get_game(group_id)
    if not game:
        return None

    new_phase = "night" if game['phase'] == "day" else "day"
    await update_phase(group_id, new_phase)
    await apply_phase_effects(group_id, new_phase)
    return new_phase

def randomize_roles(players):
    """Assign half heroes, half villains (or +1 heroes if odd)."""
    total = len(players)
    random.shuffle(players)
    mid = (total + 1) // 2
    roles = {}
    for i, user_id in enumerate(players):
        roles[user_id] = "hero" if i < mid else "villain"
    return roles
