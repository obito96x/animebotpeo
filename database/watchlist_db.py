from motor.motor_asyncio import AsyncIOMotorClient
from info import DATABASE_URI, DATABASE_NAME
import random

# MongoDB Connection
client = AsyncIOMotorClient(DATABASE_URI)
db = client[DATABASE_NAME]

# Collections
watchlist_col = db['watchlist']
pics_col = db['bot_pictures']
settings_col = db['bot_settings']

# ==========================================
# ⭐ WATCHLIST LOGIC
# ==========================================
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

# ==========================================
# 🖼️ RANDOM PICTURES LOGIC
# ==========================================
async def add_pic(category, pic_url):
    """Adds a picture URL to a specific category (e.g., 'start', 'search', 'monday')."""
    await pics_col.update_one(
        {"category": category}, 
        {"$addToSet": {"urls": pic_url}}, 
        upsert=True
    )

async def remove_pic(category, pic_url):
    """Removes a specific picture URL from a category."""
    await pics_col.update_one(
        {"category": category}, 
        {"$pull": {"urls": pic_url}}
    )

async def get_all_pics(category):
    """Gets all picture URLs for a category."""
    doc = await pics_col.find_one({"category": category})
    return doc.get("urls", []) if doc else []

async def get_random_pic(category, default_pic):
    """Returns a random picture from a category, or a default one if none exist."""
    urls = await get_all_pics(category)
    return random.choice(urls) if urls else default_pic

# ==========================================
# ⏱️ AUTO-DELETE & STICKER SETTINGS
# ==========================================
async def set_autodelete_time(seconds):
    """Sets the global auto-delete timer for files."""
    await settings_col.update_one(
        {"id": "bot_settings"}, 
        {"$set": {"autodelete_time": seconds}}, 
        upsert=True
    )

async def get_autodelete_time():
    """Gets the global auto-delete timer (Returns 0 if disabled)."""
    doc = await settings_col.find_one({"id": "bot_settings"})
    return doc.get("autodelete_time", 0) if doc else 0

async def set_sticker(sticker_id):
    """Sets the custom sticker to send after files."""
    await settings_col.update_one(
        {"id": "bot_settings"}, 
        {"$set": {"sticker_id": sticker_id}}, 
        upsert=True
    )

async def get_sticker():
    """Gets the custom sticker ID (Returns None if not set)."""
    doc = await settings_col.find_one({"id": "bot_settings"})
    return doc.get("sticker_id", None) if doc else None
