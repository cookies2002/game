from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from bot import games  # Global memory for game state


# ✅ Show profile
@Client.on_message(filters.command("profile"))
async def show_profile(client: Client, message: Message):
    user_id = message.from_user.id

    for game_chat_id, game in games.items():
        for player in game["players"]:
            if player.get("id") == user_id:
                coins = player.get("coins", 0)
                xp = player.get("xp", 0)
                level = player.get("level", 1)
                role = player.get("role", "🧍 Player")
                shield = player.get("shield", 0)
                scroll = player.get("scroll", 0)
                shield_active = player.get("shield_active", False)
                scroll_active = player.get("scroll_active", False)
                power = level * 10 + xp

                next_level_xp = (level + 1) * 10
                progress = int((xp / next_level_xp) * 10)
                progress_bar = "🟩" * progress + "⬜" * (10 - progress)

                text = (
                    f"👤 <b>Your Profile</b>\n"
                    f"🪪 Name: <b>{message.from_user.first_name}</b>\n"
                    f"🪙 Coins: <b>{coins}</b>\n"
                    f"⭐ XP: <b>{xp}</b>\n"
                    f"⬆️ Level: <b>{level}</b>\n"
                    f"⚡ Power Level: <b>{power}</b>\n"
                    f"📈 XP Progress: <code>[{progress_bar}]</code>\n"
                    f"🎭 Role: <b>{role}</b>\n"
                    f"🛡 Shield: <b>{shield}</b> {'🟢 Active' if shield_active else ''}\n"
                    f"📜 Scroll: <b>{scroll}</b> {'🟢 Active' if scroll_active else ''}"
                )

                buttons = [
                    [InlineKeyboardButton("🎒 View Inventory", callback_data=f"inventory:{game_chat_id}:{user_id}")],
                    [InlineKeyboardButton("🛡 Use Shield", callback_data=f"use_shield:{game_chat_id}:{user_id}")],
                    [InlineKeyboardButton("📜 Use Scroll", callback_data=f"use_scroll:{game_chat_id}:{user_id}")]
                ]

                return await message.reply(
                    text,
                    parse_mode="html",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

    await message.reply("❌ You are not part of an active game.")


# ✅ View inventory
@Client.on_callback_query(filters.regex(r"^inventory:(-?\d+):(\d+)$"))
async def inventory_callback(client: Client, callback_query: CallbackQuery):
    chat_id, user_id = map(int, callback_query.data.split(":")[1:])
    game = games.get(chat_id)
    if not game:
        return await callback_query.answer("❌ Game not found", show_alert=True)

    for player in game["players"]:
        if player.get("id") == user_id:
            shield = player.get("shield", 0)
            scroll = player.get("scroll", 0)
            inventory_text = (
                f"🎒 <b>Your Inventory</b>\n"
                f"🛡 Shield: <b>{shield}</b>\n"
                f"📜 Scroll: <b>{scroll}</b>"
            )
            return await callback_query.message.edit_text(
                inventory_text,
                parse_mode="html",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data=f"profile_back:{chat_id}:{user_id}")]
                ])
            )
    await callback_query.answer("❌ Player not found", show_alert=True)


# ✅ Back to profile from inventory
@Client.on_callback_query(filters.regex(r"^profile_back:(-?\d+):(\d+)$"))
async def back_to_profile(client: Client, callback_query: CallbackQuery):
    chat_id, user_id = map(int, callback_query.data.split(":")[1:])
    for player in games.get(chat_id, {}).get("players", []):
        if player.get("id") == user_id:
            message = callback_query.message
            return await show_profile(client, message)
    await callback_query.answer("❌ Player not found", show_alert=True)


# ✅ Use shield (1-time defense)
@Client.on_callback_query(filters.regex(r"use_shield:(-?\d+):(\d+)"))
async def use_shield(client: Client, callback_query: CallbackQuery):
    chat_id, user_id = map(int, callback_query.data.split(":")[1:])
    if callback_query.from_user.id != user_id:
        return await callback_query.answer("🚫 Not your profile", show_alert=True)

    game = games.get(chat_id)
    if not game:
        return await callback_query.answer("❌ Game not found", show_alert=True)

    for player in game["players"]:
        if player["id"] == user_id:
            if player.get("shield", 0) > 0:
                if player.get("shield_active", False):
                    return await callback_query.answer("🛡 Already active!", show_alert=True)
                player["shield"] -= 1
                player["shield_active"] = True
                return await callback_query.answer("🛡 Shield activated! You'll block the next vote.", show_alert=True)
            else:
                return await callback_query.answer("⚠️ No shields left!", show_alert=True)


# ✅ Use scroll (1-time double vote)
@Client.on_callback_query(filters.regex(r"use_scroll:(-?\d+):(\d+)"))
async def use_scroll(client: Client, callback_query: CallbackQuery):
    chat_id, user_id = map(int, callback_query.data.split(":")[1:])
    if callback_query.from_user.id != user_id:
        return await callback_query.answer("🚫 Not your profile", show_alert=True)

    game = games.get(chat_id)
    if not game:
        return await callback_query.answer("❌ Game not found", show_alert=True)

    for player in game["players"]:
        if player["id"] == user_id:
            if player.get("scroll", 0) > 0:
                if player.get("scroll_active", False):
                    return await callback_query.answer("📜 Already active!", show_alert=True)
                player["scroll"] -= 1
                player["scroll_active"] = True
                return await callback_query.answer("📜 Scroll activated! Your next vote is doubled.", show_alert=True)
            else:
                return await callback_query.answer("⚠️ No scrolls left!", show_alert=True)
