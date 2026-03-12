from motor.motor_asyncio import AsyncIOMotorClient
from info import DATABASE_URI, DATABASE_NAME

# MongoDB Connection
client = AsyncIOMotorClient(DATABASE_URI)
db = client[DATABASE_NAME]
watchlist_col = db['watchlist']

async def add_to_watchlist(user_id, title, category):
    """Saves Anime or Manga to the respective list, prevents duplicates."""
    await watchlist_col.update_one(
        {"user_id": user_id, "title": title, "category": category},
        {"$set": {"user_id": user_id, "title": title, "category": category}},
        upsert=True
    )

async def remove_from_watchlist(user_id, title, category):
    """Removes Anime or Manga from the list."""
    await watchlist_col.delete_one({"user_id": user_id, "title": title, "category": category})

async def get_watchlist(user_id, category):
    """Fetches the list based on category ('anime' or 'manga')."""
    cursor = watchlist_col.find({"user_id": user_id, "category": category})
    return await cursor.to_list(length=100) # Max 100 items per user to prevent lag
