# bot.py
import asyncio
import random
import time
from pyrogram import Client, filters
from pyrogram.types import Message

api_id = 12345678  # Replace with your API_ID
api_hash = "your_api_hash"
bot_token = "your_bot_token"

bot = Client("FairyVsVillainBot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

# Game state
players = []
player_roles = {}
game_started = False
group_id = None
joined_time = None
eliminated_players = []
votes = {}
power_used = {}
max_players = 15

FAIRIES = {
    "Fairy Sparkle": "✨ Can deflect a villain's attack once.",
    "Crystal Fairy": "🔮 Can reveal one random villain to self.",
    "Light Fairy": "💡 Can protect one player from being attacked.",
    "Dream Fairy": "💭 Can silence a player for one round.",
    "Wind Fairy": "🍃 Can move a vote to another player secretly."
}

VILLAINS = {
    "Dark Phantom": "💀 Can eliminate a player during night.",
    "Shadow Queen": "🕷️ Can block a fairy's power.",
    "Chaos Bringer": "🔥 Can disable voting for one round.",
    "Fearmonger": "😱 Can scare two players into skipping votes.",
    "Night Crawler": "🌑 Can stay hidden from investigations."
}

COMMONERS = ["Villager", "Elf", "Sprite", "Gnome", "Peasant"]

@bot.on_message(filters.command("start"))
async def start(client, message: Message):
    await message.reply("🌟 Welcome to Fairy vs Villain Game!
Use /join to enter the magical battle!")

@bot.on_message(filters.command("join"))
async def join_game(client, message: Message):
    global players, game_started, group_id, joined_time
    if game_started:
        await message.reply("🚫 Game already started! Wait for next round.")
        return

    if message.from_user.id in players:
        await message.reply("⚠️ You already joined!")
        return

    if len(players) >= max_players:
        await message.reply("🔒 Max 15 players reached!")
        return

    players.append(message.from_user.id)
    group_id = message.chat.id
    await message.reply(f"✅ {message.from_user.mention} joined the game! ({len(players)}/15)")

    if len(players) == 4:
        joined_time = time.time()
        await message.reply("⏳ 4 players joined! 1 minute to allow more players...")
        await asyncio.sleep(60)
        if len(players) >= 4:
            await start_game(client)

async def start_game(client):
    global game_started
    game_started = True
    await assign_roles(client)
    await client.send_message(group_id, "🎮 Game started! Use /vote or /usepower and survive!")

async def assign_roles(client):
    roles_pool = (list(FAIRIES.items()) + list(VILLAINS.items()) + [(c, None) for c in COMMONERS])
    random.shuffle(roles_pool)
    assigned = {}
    for player_id in players:
        role, power = roles_pool.pop()
        assigned[player_id] = {"role": role, "power": power, "alive": True}
        text = f"🎭 Your role: {role}\n"
        if power:
            text += f"🔋 Power: {power}"
        else:
            text += "🧍 No special power. Vote wisely."
        await client.send_message(player_id, text)
    global player_roles
    player_roles = assigned

@bot.on_message(filters.command("profile"))
async def profile(client, message: Message):
    user = message.from_user.id
    if user not in player_roles:
        await message.reply("🚫 You're not in the game.")
        return
    data = player_roles[user]
    await message.reply(f"🎭 Role: {data['role']}\n🔋 Power: {data['power'] or 'None'}\n❤️ Status: {'Alive' if data['alive'] else 'Out'}")

@bot.on_message(filters.command("vote"))
async def vote(client, message: Message):
    if not game_started or player_roles.get(message.from_user.id, {}).get("alive") is not True:
        return await message.reply("🚫 You're not allowed to vote now.")

    if len(message.command) < 2:
        return await message.reply("Usage: /vote @username")

    username = message.command[1].lstrip("@")
    for pid, info in player_roles.items():
        if info.get("alive") and (await client.get_users(pid)).username == username:
            votes[pid] = votes.get(pid, 0) + 1
            await message.reply(f"🗳️ Vote cast against @{username}!")
            return
    await message.reply("⚠️ Invalid player or player already out.")

@bot.on_message(filters.command("usepower"))
async def use_power(client, message: Message):
    uid = message.from_user.id
    if uid not in player_roles or not player_roles[uid]["alive"]:
        return await message.reply("❌ You can't use power now.")

    role = player_roles[uid]["role"]
    power = player_roles[uid]["power"]
    if not power:
        return await message.reply("🧍 You don’t have a power to use.")

    power_used[uid] = True
    if "eliminate" in power or "attack" in power:
        if len(message.command) < 2:
            return await message.reply("Usage: /usepower @username")
        target_user = message.command[1].lstrip("@")
        for pid, pdata in player_roles.items():
            if pdata["alive"] and (await client.get_users(pid)).username == target_user:
                player_roles[pid]["alive"] = False
                eliminated_players.append(pid)
                await client.send_message(pid, f"☠️ You were attacked by a villain: {role}!")
                await client.send_message(group_id, f"💀 @{target_user} was defeated! 🎯 Attacked by: {message.from_user.mention}")
                return
        return await message.reply("Invalid target or already out.")
    else:
        await message.reply("🔋 Your power is now used. [Effect not visible to group]")
        await client.send_message(uid, f"✅ You used your power: {power}")

@bot.on_message(filters.command("stats"))
async def stats(client, message: Message):
    alive = [uid for uid, r in player_roles.items() if r["alive"]]
    out = [uid for uid in players if uid not in alive]
    text = f"📊 Alive: {len(alive)} | ☠️ Out: {len(out)}\n"
    text += "\n👥 Players Alive:\n"
    for uid in alive:
        user = await client.get_users(uid)
        text += f"✅ {user.mention}\n"
    text += "\n☠️ Players Out:\n"
    for uid in out:
        user = await client.get_users(uid)
        text += f"❌ {user.mention}\n"
    await message.reply(text)

@bot.on_message(filters.command("reset"))
async def reset_game(client, message: Message):
    if not message.from_user or not message.from_user.is_self and not message.from_user.id == (await client.get_chat_member(message.chat.id, message.from_user.id)).user.id:
        return await message.reply("Only group admins can reset.")

    global players, player_roles, game_started, joined_time, eliminated_players, votes, power_used
    players.clear()
    player_roles.clear()
    game_started = False
    joined_time = None
    eliminated_players.clear()
    votes.clear()
    power_used.clear()
    await message.reply("🔄 Game reset successful. Use /join to start again!")

bot.run()
