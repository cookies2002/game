# database/users.py
async def get_top_players(limit=10):
    players = await users_collection.find().sort([
        ("level", -1),
        ("xp", -1),
        ("coins", -1)
    ]).limit(limit).to_list(length=limit)
    return players
  
