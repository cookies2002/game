# database/users.py
async def get_top_players(limit=10):
    players = await users_collection.find().sort([
        ("level", -1),
        ("xp", -1),
        ("coins", -1)
    ]).limit(limit).to_list(length=limit)
    return players

async def get_group_top_players(chat_id: int, limit=10):
    return await users_collection.find({
        "group_id": chat_id
    }).sort([
        ("level", -1),
        ("xp", -1)
    ]).limit(limit).to_list(length=limit)

async def update_user(user_id: int, update_data: dict):
    await users_collection.update_one(
        {"_id": user_id},
        {"$set": update_data}
    )
    
    
  
