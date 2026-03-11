import asyncio, re, logging, math
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from pyrogram.errors import FloodWait

from database.users_chats_db import db
from database.ia_filterdb import get_search_results
from utils import temp, get_settings
from info import *

# Anilist fetcher
try:
    from plugins.anilist import fetch_anime_details as get_anime_info
except ImportError:
    get_anime_info = None

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

# In-Memory Cache
if not hasattr(temp, 'SEARCHES'): temp.SEARCHES = {}
OWNER_USERNAME = environ.get('OWNER_USERNAME', 'i_killed_my_clan')
# Default 16:9 Search Banner (Change URL if you want your own custom banner)
SEARCH_BANNER = "https://graph.org/file/99eebf5dbe8a134f548e0.jpg"

# ==========================================
# 🧹 AI FILE CLEANER
# ==========================================
def get_clean_name(filename):
    clean = re.sub(r'\[.*?\]|\(.*?\)', '', filename)
    clean = re.sub(r'\.(mkv|mp4|avi|mpe?g)$', '', clean, flags=re.IGNORECASE)
    clean = re.split(r'\s-\s|\sEp\s|\sE\d', clean)[0]
    return clean.replace(".", " ").replace("_", " ").strip()

def extract_ep_num(filename, index):
    match = re.search(r'(?i)(?:ep|e|episode)\s*0*(\d+)', filename)
    if match: return match.group(1)
    match = re.search(r'-\s*0*(\d+)', filename)
    if match: return match.group(1)
    return str(index)

# ==========================================
# 💬 MAIN SEARCH HANDLERS
# ==========================================
@Client.on_message(filters.group & filters.text & filters.incoming)
async def group_search(client, message):
    if message.text.startswith("/") or message.text.startswith("#"): return
    settings = await get_settings(message.chat.id)
    if settings.get('auto_ffilter', True):
        await auto_filter(client, message)

@Client.on_message(filters.private & filters.text & filters.incoming)
async def pm_search_handler(bot, message):
    if message.text.startswith("/") or message.text.startswith("#"): return  
    await message.reply_text(
        f"<b>🙋 ʜᴇʏ {message.from_user.first_name}, \n\nPlease use the `/search` command to find Anime/Manga!\n\nExample: `/search Naruto`</b>"
    )

# ==========================================
# 🔍 STEP 1: SEARCH RESULTS UI
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
    
    # Group files by Clean Name
    grouped_titles = {}
    for f in files:
        c_name = get_clean_name(f.file_name)
        if not c_name: c_name = "Unknown"
        if c_name not in grouped_titles: grouped_titles[c_name] = []
        grouped_titles[c_name].append(f)
        
    temp.SEARCHES[key] = grouped_titles
    titles = list(grouped_titles.keys())
    
    btn = []
    for i, title in enumerate(titles[:5]): # Show top 5 distinct titles
        ep_count = len(grouped_titles[title])
        btn.append([InlineKeyboardButton(f"📺 {title} ({ep_count} EP)", callback_data=f"stitle#{key}#{i}")])
        
    btn.append([InlineKeyboardButton("📄 1/1", callback_data="pages")])
    btn.append([InlineKeyboardButton("🏠 HOME", callback_data="start"), InlineKeyboardButton("CLOSE", callback_data="close_data")])
    
    cap = f"🎯 <b>ꜱᴇᴀʀᴄʜ ʀᴇsᴜʟᴛꜱ</b>\n\n"
    cap += f"▸ <b>Qᴜᴇʀʏ:</b> /search {search_clean}\n"
    cap += f"▸ <b>Rᴇsᴜʟᴛꜱ:</b> {len(titles)} ᴀɴɪᴍᴇ\n"
    cap += f"▸ <b>Pᴀɢᴇ:</b> 1 of 1\n\n"
    cap += "<i>ꜱᴇʟᴇᴄᴛ ᴀɴ ᴀɴɪᴍᴇ ᴛᴏ ᴠɪᴇᴡ ᴅᴇᴛᴀɪʟꜱ ↓</i>"

    await m.delete()
    await msg.reply_photo(photo=SEARCH_BANNER, caption=cap, reply_markup=InlineKeyboardMarkup(btn))

# ==========================================
# 📺 STEP 2: ANIME DETAILS UI
# ==========================================
@Client.on_callback_query(filters.regex(r"^stitle#"))
async def select_title_cb(client, query):
    _, key, index = query.data.split("#")
    
    grouped_titles = temp.SEARCHES.get(key)
    if not grouped_titles: return await query.answer("Session Expired!", show_alert=True)
    
    titles = list(grouped_titles.keys())
    selected_title = titles[int(index)]
    files = grouped_titles[selected_title]
    
    # Fetch Anilist Details
    anime_info = await get_anime_info(selected_title) if get_anime_info else {}
    
    cover = anime_info.get("cover_image", SEARCH_BANNER)
    rating = anime_info.get('score', 'N/A')
    atype = anime_info.get('format', 'TV Series')
    status = anime_info.get('status', 'FINISHED')
    eps = anime_info.get('episodes', len(files))
    genres = ", ".join(anime_info.get('genres', ['Action', 'Adventure']))
    synopsis = anime_info.get('description', 'No synopsis available.')[:250]
    
    cap = f"<b>{selected_title}</b>\n"
    cap += f"┌──────────────────────\n"
    cap += f"» <b>Type:</b> {atype}\n"
    cap += f"» <b>Average Rating:</b> {rating}%\n"
    cap += f"» <b>Status:</b> {status}\n"
    cap += f"» <b>Episodes/Chapters:</b> {eps}\n"
    cap += f"» <b>Genres:</b> {genres}\n\n"
    cap += f"‣ <b>𝗦𝗬𝗡𝗢𝗣𝗦𝗜𝗦</b>\n"
    cap += f"➟ <i>{synopsis}...</i>"

    btn = [
        [InlineKeyboardButton("👀 WATCH NOW", callback_data=f"swatch#{key}#{index}#0")],
        [InlineKeyboardButton("⭐ ADD TO WATCHLIST", callback_data=f"addwatch#{selected_title}")],
        [InlineKeyboardButton("🔙 BACK", callback_data=f"sback#{key}"), InlineKeyboardButton("❌ CLOSE", callback_data="close_data")]
    ]
    
    await query.message.edit_media(InputMediaPhoto(media=cover, caption=cap))
    await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(btn))

# ==========================================
# 🔢 STEP 3: EPISODE GRID UI (1-30)
# ==========================================
@Client.on_callback_query(filters.regex(r"^swatch#"))
async def swatch_cb(client, query):
    _, key, index, offset = query.data.split("#")
    offset = int(offset)
    
    grouped_titles = temp.SEARCHES.get(key)
    if not grouped_titles: return await query.answer("Session Expired!", show_alert=True)
    
    titles = list(grouped_titles.keys())
    selected_title = titles[int(index)]
    files = grouped_titles[selected_title]
    total_eps = len(files)
    
    # Sort files alphabetically to ensure correct episode order
    files = sorted(files, key=lambda x: x.file_name)
    current_chunk = files[offset:offset+30]
    
    cap = f"📺 <b>{selected_title}</b>\n\n"
    end_offset = min(offset + 30, total_eps)
    cap += f"<b>Select episode ({offset+1}-{end_offset} of {total_eps}):</b>"

    btn = []
    row = []
    for i, f in enumerate(current_chunk, start=offset+1):
        ep_label = extract_ep_num(f.file_name, i)
        row.append(InlineKeyboardButton(ep_label, callback_data=f"file#{f.file_id}"))
        if len(row) == 5:
            btn.append(row)
            row = []
    if row: btn.append(row)
    
    btn.append([InlineKeyboardButton("📥 DOWNLOAD ALL EPISODES", callback_data=f"downall#{key}#{index}")])
    
    # Pagination for episodes > 30
    page_row = []
    if offset > 0:
        page_row.append(InlineKeyboardButton("⬅️", callback_data=f"swatch#{key}#{index}#{offset-30}"))
    if total_eps > offset + 30:
        page_row.append(InlineKeyboardButton("➡️", callback_data=f"swatch#{key}#{index}#{offset+30}"))
    if page_row: btn.append(page_row)
        
    btn.append([InlineKeyboardButton("🔙 BACK", callback_data=f"stitle#{key}#{index}"), InlineKeyboardButton("❌ CLOSE", callback_data="close_data")])
    
    # Send Grid View
    await query.message.edit_caption(caption=cap, reply_markup=InlineKeyboardMarkup(btn))

# ==========================================
# 🔙 BACK BUTTON & OTHER CALLBACKS
# ==========================================
@Client.on_callback_query(filters.regex(r"^sback#"))
async def back_to_search(client, query):
    _, key = query.data.split("#")
    grouped_titles = temp.SEARCHES.get(key)
    if not grouped_titles: return await query.answer("Session Expired!", show_alert=True)
    
    titles = list(grouped_titles.keys())
    btn = []
    for i, title in enumerate(titles[:5]):
        ep_count = len(grouped_titles[title])
        btn.append([InlineKeyboardButton(f"📺 {title} ({ep_count} EP)", callback_data=f"stitle#{key}#{i}")])
        
    btn.append([InlineKeyboardButton("📄 1/1", callback_data="pages")])
    btn.append([InlineKeyboardButton("🏠 HOME", callback_data="start"), InlineKeyboardButton("CLOSE", callback_data="close_data")])
    
    cap = f"🎯 <b>ꜱᴇᴀʀᴄʜ ʀᴇsᴜʟᴛꜱ</b>\n\n"
    cap += f"▸ <b>Rᴇsᴜʟᴛꜱ:</b> {len(titles)} ᴀɴɪᴍᴇ\n▸ <b>Pᴀɢᴇ:</b> 1 of 1\n\n<i>ꜱᴇʟᴇᴄᴛ ᴀɴ ᴀɴɪᴍᴇ ᴛᴏ ᴠɪᴇᴡ ᴅᴇᴛᴀɪʟꜱ ↓</i>"

    await query.message.edit_media(InputMediaPhoto(media=SEARCH_BANNER, caption=cap))
    await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(btn))

@Client.on_callback_query(filters.regex(r"^file#"))
async def single_file_cb(bot, query):
    _, file_id = query.data.split("#")
    await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start=file_{file_id}")

@Client.on_callback_query(filters.regex(r"^downall#"))
async def downall_cb(bot, query):
    _, key, index = query.data.split("#")
    grouped_titles = temp.SEARCHES.get(key)
    if not grouped_titles: return await query.answer("Session Expired!", show_alert=True)
    
    titles = list(grouped_titles.keys())
    selected_title = titles[int(index)]
    files = grouped_titles[selected_title]
    
    await query.answer("Sending all episodes... ⏳", show_alert=False)
    for f in files:
        try:
            await bot.send_cached_media(chat_id=query.message.chat.id, file_id=f.file_id)
            await asyncio.sleep(0.5)
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
            await bot.send_cached_media(chat_id=query.message.chat.id, file_id=f.file_id)

@Client.on_callback_query(filters.regex(r"^close_data$"))
async def close_cb(bot, query):
    await query.message.delete()
    
@Client.on_callback_query(filters.regex(r"^addwatch#"))
async def addwatch_cb(bot, query):
    _, title = query.data.split("#")
    # Database watchlist connection setup here later
    await query.answer(f"⭐ {title} Added to Watchlist!", show_alert=True)
    
