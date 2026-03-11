import asyncio, re, logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait

from database.users_chats_db import db
from database.ia_filterdb import get_search_results
from utils import temp, get_size, get_settings
from info import *

# Anilist fetcher
try:
    from plugins.anilist import fetch_anime_details as get_anime_info
except ImportError:
    get_anime_info = None

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

# In-Memory Cache for holding search states
if not hasattr(temp, 'SEARCHES'): temp.SEARCHES = {}
if not hasattr(temp, 'QUAL_FILES'): temp.QUAL_FILES = {}

OWNER_USERNAME = environ.get('OWNER_USERNAME', 'i_killed_my_clan')

# ==========================================
# 🧹 AI FILE CLEANER & QUALITY EXTRACTOR
# ==========================================
def get_clean_name(filename):
    clean = re.sub(r'\[.*?\]|\(.*?\)', '', filename)
    clean = re.sub(r'\.(mkv|mp4|avi|mpe?g)$', '', clean, flags=re.IGNORECASE)
    clean = re.split(r'\s-\s|\sEp\s|\sE\d', clean)[0]
    return clean.replace(".", " ").replace("_", " ").strip()

def get_quality(filename):
    lower_name = filename.lower()
    if "1080" in lower_name: return "1080p"
    if "720" in lower_name: return "720p"
    if "480" in lower_name: return "480p"
    if "2160" in lower_name or "4k" in lower_name: return "4K"
    return "Normal"

async def auto_delete_msg(message, delay):
    await asyncio.sleep(delay)
    try: await message.delete()
    except: pass

# ==========================================
# 💬 MESSAGE HANDLERS
# ==========================================
@Client.on_message(filters.group & filters.text & filters.incoming)
async def group_search(client, message):
    if message.text.startswith("/") or message.text.startswith("#"): return
    settings = await get_settings(message.chat.id)
    # Group mein auto-filter on hai toh chalega
    if settings.get('auto_ffilter', True):
        await auto_filter(client, message)

@Client.on_message(filters.private & filters.text & filters.incoming)
async def pm_search_handler(bot, message):
    # 🔴 FIX: Agar direct text (bina /) daala toh search nahi hoga!
    if message.text.startswith("/") or message.text.startswith("#"): return  
    
    await message.reply_text(
        f"<b>🙋 ʜᴇʏ {message.from_user.first_name}, \n\nPlease use the `/search` command to find Anime/Manga!\n\nExample: `/search Naruto`</b>",   
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📝 ʀᴇǫᴜᴇsᴛ ʜᴇʀᴇ ", url=GRP_LNK)]])
    )

# ==========================================
# 🔍 STEP 1: SEARCH & TITLE GROUPING (VIP UI)
# ==========================================
async def auto_filter(client, msg):
    search = msg.text.lower()
    if len(search) < 2 or len(search) > 100: return
    
    m = await msg.reply_text(f'**🔎 Searching...** `{search}`')
    search_clean = re.sub(r"[:-]", "", search.replace("-", " ")).strip()
    
    files, _, _ = await get_search_results(msg.chat.id, search_clean, offset=0, filter=True)
    if not files: 
        return await m.edit("<b>❌ No Anime/Manga found with this name. Check spelling!</b>")

    key = f"{msg.chat.id}-{msg.id}"
    
    # Group files by Clean Anime Name
    grouped_titles = {}
    for f in files:
        c_name = get_clean_name(f.file_name)
        if not c_name: c_name = "Unknown"
        if c_name not in grouped_titles: grouped_titles[c_name] = []
        grouped_titles[c_name].append(f)
        
    temp.SEARCHES[key] = grouped_titles
    titles = list(grouped_titles.keys())
    
    # STEP 2A: Multiple Titles Found -> Show List
    if len(titles) > 1:
        btn = []
        for i, title in enumerate(titles[:15]): 
            btn.append([InlineKeyboardButton(f"📁 {title}", callback_data=f"stitle#{key}#{i}")])
        btn.append([InlineKeyboardButton("❌ Close", callback_data="close_data")])
        
        await m.edit(
            f"<b>📚 Found Multiple Results for:</b> `{search}`\n\n👇 Please select the exact Anime/Manga you want:",
            reply_markup=InlineKeyboardMarkup(btn)
        )
    # STEP 2B: Only 1 Title Found -> Skip directly to Quality Selection
    else:
        await m.delete()
        await show_qualities(client, msg.chat.id, key, 0)

# ==========================================
# 📺 STEP 3: SHOW ANIME INFO & QUALITIES
# ==========================================
@Client.on_callback_query(filters.regex(r"^stitle#"))
async def select_title_cb(client, query):
    _, key, index = query.data.split("#")
    await show_qualities(client, query.message.chat.id, key, int(index), query.message.id)

async def show_qualities(client, chat_id, key, title_index, delete_msg_id=None):
    grouped_titles = temp.SEARCHES.get(key)
    if not grouped_titles: return
    
    titles = list(grouped_titles.keys())
    if title_index >= len(titles): return
    
    selected_title = titles[title_index]
    title_files = grouped_titles[selected_title]
    
    # Group the files by Quality
    quality_groups = {"4K": [], "1080p": [], "720p": [], "480p": [], "Normal": []}
    for f in title_files:
        q = get_quality(f.file_name)
        quality_groups[q].append(f)
        
    # Generate Vertical Quality Buttons
    btn = []
    for q in ["4K", "1080p", "720p", "480p", "Normal"]:
        if quality_groups[q]:
            q_key = f"{key}_{title_index}_{q}"
            temp.QUAL_FILES[q_key] = quality_groups[q]
            btn.append([InlineKeyboardButton(f"🖥️ {q} ({len(quality_groups[q])} Files)", callback_data=f"squal#{q_key}")])
            
    if len(titles) > 1:
        btn.append([InlineKeyboardButton("🔙 Go Back", callback_data=f"sback#{key}")])
    btn.append([InlineKeyboardButton("❌ Close", callback_data="close_data")])
    
    # Fetch Anilist Image & Details
    anime_info = await get_anime_info(selected_title) if get_anime_info else None
    
    if anime_info:
        cap = f"🎬 **Name:** `{anime_info.get('title', selected_title)}`\n"
        cap += f"✨ **Episodes:** `{anime_info.get('episodes', 'Unknown')}`\n"
        cap += f"⚡ **Status:** `{anime_info.get('status', 'Completed')}`\n\n"
        cap += "<b>👇 Select Quality To Download 👇</b>"
        cover = anime_info.get("cover_image")
    else:
        cap = f"🎬 **Name:** `{selected_title}`\n\n<b>👇 Select Quality To Download 👇</b>"
        cover = "https://graph.org/file/99eebf5dbe8a134f548e0.jpg" # Default image
        
    if delete_msg_id:
        try: await client.delete_messages(chat_id, delete_msg_id)
        except: pass
        
    msg = await client.send_photo(chat_id=chat_id, photo=cover, caption=cap, reply_markup=InlineKeyboardMarkup(btn))
    
    # Auto Delete Setup if enabled
    settings = await get_settings(chat_id)
    if settings.get('auto_delete', True):
        asyncio.create_task(auto_delete_msg(msg, DELETE_TIME))

# ==========================================
# 📥 STEP 4: SEND FILES & NAVIGATION
# ==========================================
@Client.on_callback_query(filters.regex(r"^squal#"))
async def select_quality_cb(client, query):
    _, q_key = query.data.split("#")
    files = temp.QUAL_FILES.get(q_key)
    if not files: return await query.answer("Session expired! Please search again.", show_alert=True)
        
    await query.answer("Sending requested files to you... ⏳", show_alert=False)
    bot_username = client.me.username if client.me else temp.U_NAME
    
    for f in files:
        try:
            await client.send_cached_media(
                chat_id=query.message.chat.id, 
                file_id=f.file_id, 
                caption=f"**{f.file_name}**\n\n<i>Downloaded via @{bot_username}</i>"
            )
            await asyncio.sleep(1) # Protect against FloodWait
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
            await client.send_cached_media(chat_id=query.message.chat.id, file_id=f.file_id, caption=f"**{f.file_name}**")

@Client.on_callback_query(filters.regex(r"^sback#"))
async def back_to_titles_cb(client, query):
    _, key = query.data.split("#")
    grouped_titles = temp.SEARCHES.get(key)
    if not grouped_titles: return await query.answer("Session expired! Please search again.", show_alert=True)
        
    titles = list(grouped_titles.keys())
    btn = []
    for i, title in enumerate(titles[:15]):
        btn.append([InlineKeyboardButton(f"📁 {title}", callback_data=f"stitle#{key}#{i}")])
    btn.append([InlineKeyboardButton("❌ Close", callback_data="close_data")])
    
    await query.message.delete()
    msg = await client.send_message(
        chat_id=query.message.chat.id,
        text=f"<b>📚 Found Multiple Results!</b>\n\n👇 Please select the exact Anime/Manga:",
        reply_markup=InlineKeyboardMarkup(btn)
    )

@Client.on_callback_query(filters.regex(r"^close_data$"))
async def close_cb(bot, query):
    await query.message.delete()
    
