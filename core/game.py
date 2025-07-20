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

# core/power_engine.py

power_effects = {
    "rasengan": lambda user, target: f"🔵 Rasengan used by {user} on {target}! Stunned.",
    "amaterasu": lambda user, target: f"🔥 Amaterasu unleashed by {user} on {target}! Burning over time.",
    "sharingan": lambda user, target: f"👁️ Sharingan reveals {target}'s role!",
    "drunken_fist": lambda user, _: f"🍶 Rock Lee uses Drunken Fist! Votes x2 this round.",
    "flying_raijin": lambda user, target: f"⚡ Minato swaps places with {target}, avoiding danger!",
    "regeneration": lambda user, _: f"💊 Tsunade revives one hero from the dead!",
    "infinite_tsukuyomi": lambda user, _: f"🌕 Madara blinds everyone! No voting next round.",
    "tsukuyomi": lambda user, target: f"🧠 Itachi traps {target} in Tsukuyomi! Vote disabled.",
    "curse_mark": lambda user, target: f"🐍 Orochimaru curses {target}, draining XP.",
    "almighty_push": lambda user, _: f"🌀 Pain cancels all powers tonight!",
    "chakra_drain": lambda user, target: f"💧 Kisame drains chakra from {target}, steals coins!",
    "silent_kill": lambda user, target: f"🗡️ Zabuza silently kills {target}. No trace left."
}

async def apply_phase_effects(group_id: int, phase: str):
    # Placeholder: Apply background sounds, memes, power triggers, etc.
    print(f"[GAME] Applying {phase} effects in group {group_id}...")
    # Logic will go here later to apply auto powers

async def use_power(user_id: int, power: str, target_id: int = None):
    effect = power_effects.get(power)
    if effect:
        return effect(user_id, target_id)
    return "❌ Unknown power."
    
