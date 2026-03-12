import asyncio, re, logging, math
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from pyrogram.errors import FloodWait

from database.users_chats_db import db
from database.ia_filterdb import get_search_results
from utils import temp, get_settings
from info import *

# Anilist fetcher (Safe Import)
try:
    from plugins.anilist import fetch_anime_details as get_anime_info
except ImportError:
    get_anime_info = None

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

if not hasattr(temp, 'SEARCHES'): temp.SEARCHES = {}
OWNER_USERNAME = environ.get('OWNER_USERNAME', 'i_killed_my_clan')
SEARCH_BANNER = "https://graph.org/file/99eebf5dbe8a134f548e0.jpg"

# ==========================================
# 🧠 ULTRA-AGGRESSIVE CLEANER & GROUPER
# ==========================================
def extract_and_clean(filename):
    ep_num = "0"
    
    # 1. Extract Chapter/Episode safely
    match = re.search(r'(?i)(?:ch|chapter|ep|episode|vol|v|e)[\s\-]*0*(\d+(?:\.\d+)?)', filename)
    if match:
        ep_num = match.group(1)
    else:
        match = re.search(r'(?i)s\d{1,2}e0*(\d+)', filename)
        if match: 
            ep_num = match.group(1)
        else:
            match = re.search(r'(?i)[- ]\s*0*(\d+(?:\.\d+)?)\s*(?:1080p|720p|mkv|mp4|pdf|cbz|cbr)', filename)
            if match: ep_num = match.group(1)

    # 2. Clean Name completely
    name = re.sub(r'\.\w{3,4}$', '', filename) # Remove Extension
    name = re.sub(r'\[.*?\]|\(.*?\)', '', name) # Remove ALL Brackets
    name = re.split(r'(?i)(\bs\d{1,2}e\d{1,4}\b|\b(?:chapter|ch|ep|episode|vol|volume)\b\s*\d+)', name)[0] # Chop at Ep/Ch
    name = re.split(r'(?i)\bs\d{1,2}\b', name)[0] # Chop at S01
    name = re.sub(r'(?i)@\w+', '', name) # Remove Telegram Usernames
    name = name.replace('.', ' ').replace('_', ' ').replace('-', ' ') # Replace dots/underscores
    tags = r'(?i)\b(1080p|720p|480p|amzn|web|dl|rip|dual|audio|hindi|english|subbed|dubbed)\b'
    name = re.sub(tags, '', name) # Remove qualities
    name = re.sub(r'[^a-zA-Z0-9]+$', '', name.strip()).strip() # Remove trailing symbols
    name = " ".join(name.split()).title() # Title case and clean extra spaces

    return name if name else "Unknown", ep_num

def get_emoji(filename):
    ext = filename.split('.')[-1].lower() if '.' in filename else ''
    if ext == 'pdf': return '📕'
    if ext == 'cbz': return '📗'
    if ext == 'cbr': return '📘'
    if ext in ['mkv', 'mp4', 'avi']: return '🎬'
    return '📙'

# ==========================================
# 💬 MESSAGE HANDLERS
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
        f"<b>🙋 ʜᴇʏ {message.from_user.first_name}, \n\nPlease use the `/search` command to find Anime/Manga!\n\nExample: `/search Naruto`</b>",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📝 ʀᴇǫᴜᴇsᴛ ʜᴇʀᴇ ", url=GRP_LNK)]])
    )

# ==========================================
# 🔍 STEP 1: EXACT VIOLET SEARCH UI
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
    
    # 🔥 GROUPING MAGIC HAPPENS HERE
    grouped_titles = {}
    for f in files:
        title, ep = extract_and_clean(f.file_name)
        # Determine if Manga or Anime based on extension
        is_manga = any(x in f.file_name.lower() for x in ['.pdf', '.cbz', '.cbr'])
        cat = "manga" if is_manga else "anime"
        
        if title not in grouped_titles: 
            grouped_titles[title] = {"files": [], "category": cat}
            
        try: ep_val = float(ep) if '.' in ep else int(ep)
        except: ep_val = 0
            
        grouped_titles[title]["files"].append((f, ep_val))
        
    temp.SEARCHES[key] = grouped_titles
    titles = list(grouped_titles.keys())
    
    btn = []
    for i, title in enumerate(titles[:10]): 
        total_eps = len(grouped_titles[title]["files"])
        label = "CH" if grouped_titles[title]["category"] == "manga" else "EP"
        btn.append([InlineKeyboardButton(f"📺 {title} ({total_eps} {label})", callback_data=f"stitle#{key}#{i}")])
        
    btn.append([InlineKeyboardButton("📄 1/1", callback_data="pages")])
    btn.append([InlineKeyboardButton("🏠 HOME", callback_data="start"), InlineKeyboardButton("CLOSE", callback_data="close_data")])
    
    cap = f"🎯 <b>SEARCH RESULTS</b> ❞\n\n"
    cap += f"▸ <b>QUERY:</b> /search {search_clean}\n"
    cap += f"▸ <b>RESULTS:</b> {len(titles)} ITEMS\n"
    cap += f"▸ <b>PAGE:</b> 1 of 1\n\n"
    cap += "<i>SELECT AN ITEM TO VIEW DETAILS ↓</i>"

    await m.delete()
    await msg.reply_photo(photo=SEARCH_BANNER, caption=cap, reply_markup=InlineKeyboardMarkup(btn))

# ==========================================
# 📺 STEP 2: DETAILS UI (EXACT SCREENSHOT MATCH)
# ==========================================
@Client.on_callback_query(filters.regex(r"^stitle#"))
async def select_title_cb(client, query):
    try:
        _, key, index = query.data.split("#")
        grouped_titles = temp.SEARCHES.get(key)
        if not grouped_titles: return await query.answer("❌ Session Expired! Search again.", show_alert=True)
        
        titles = list(grouped_titles.keys())
        selected_title = titles[int(index)]
        title_data = grouped_titles[selected_title]
        total_eps = len(title_data["files"])
        cat = title_data["category"]
        
        # Fallback Anilist integration
        anime_info = await get_anime_info(selected_title) if get_anime_info else {}
        if not anime_info: anime_info = {}
        
        cover = anime_info.get("cover_image", SEARCH_BANNER) 
        rating = anime_info.get('score', 'N/A')
        atype = "Manhwa/Manga" if cat == "manga" else "TV Series"
        status = anime_info.get('status', 'Releasing')
        year = anime_info.get('startDate', {}).get('year', 'Unknown')
        genres = ", ".join(anime_info.get('genres', ['Action', 'Fantasy']))
        synopsis = anime_info.get('description', 'Synopsis not available.')[:250]
        
        cap = f"📚 <b>{selected_title}</b> ❞\n"
        cap += f"┌──────────────────────\n"
        cap += f"✧ <b>Type:</b> {atype} | ✧ <b>Status:</b> {status}\n"
        cap += f"✦ <b>{'Chapters' if cat == 'manga' else 'Episodes'}:</b> {total_eps}\n"
        cap += f"✶ <b>Genres:</b> {genres}\n"
        cap += f"✦ <b>Since:</b> {year}\n"
        cap += f"⚟ <b>Synopsis:</b> {synopsis}...\n"

        read_btn_txt = "📖 READ CHAPTERS" if cat == "manga" else "👀 WATCH EPISODES"
        down_btn_txt = "📥 DOWNLOAD CHAPTERS" if cat == "manga" else "📥 DOWNLOAD ALL"
        
        btn = [
            [InlineKeyboardButton(read_btn_txt, callback_data=f"swatch#{key}#{index}#0")],
            [InlineKeyboardButton("📁 ADD TO LIBRARY", callback_data=f"addwatch#{selected_title}")],
            [InlineKeyboardButton(down_btn_txt, callback_data=f"downall#{key}#{index}#0")],
            [InlineKeyboardButton("🔙 BACK", callback_data=f"sback#{key}"), InlineKeyboardButton("❌ CLOSE", callback_data="close_data")]
        ]
        
        await query.message.edit_media(InputMediaPhoto(media=cover, caption=cap))
        await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
    except Exception as e:
        logger.error(f"Error in select_title_cb: {e}")
        await query.answer("❌ Error processing details. Please try again.", show_alert=True)

# ==========================================
# 🔢 STEP 3: 3-COLUMN GRID UI
# ==========================================
@Client.on_callback_query(filters.regex(r"^swatch#"))
async def swatch_cb(client, query):
    try:
        _, key, index, offset = query.data.split("#")
        offset = int(offset)
        
        grouped_titles = temp.SEARCHES.get(key)
        if not grouped_titles: return await query.answer("❌ Session Expired! Search again.", show_alert=True)
        
        titles = list(grouped_titles.keys())
        selected_title = titles[int(index)]
        cat = grouped_titles[selected_title]["category"]
        
        files_data = grouped_titles[selected_title]["files"]
        total_eps = len(files_data)
        
        # Sort nicely (Ch 1, Ch 2...)
        files_data.sort(key=lambda x: x[1])
        
        # Chunk of 30 per page
        current_chunk = files_data[offset:offset+30]
        
        cap = f"📚 <b>{selected_title}</b> ❞\n\n"
        cap += f"<b>Select {'chapter' if cat == 'manga' else 'episode'} to {'read' if cat == 'manga' else 'watch'} (oldest first):</b>\n"
        cap += f"📕 <i>PDF</i> 📗 <i>CBZ</i> 📘 <i>CBR</i> 📙 <i>Other</i>"

        btn = []
        row = []
        for f, ep_num in current_chunk:
            fmt_ep = str(int(ep_num)) if ep_num == int(ep_num) else str(ep_num)
            icon = get_emoji(f.file_name)
            label = f"Ch {fmt_ep} {icon}" if cat == "manga" else f"Ep {fmt_ep} {icon}"
            
            row.append(InlineKeyboardButton(label, callback_data=f"file#{f.file_id}"))
            
            # 🔥 EXACTLY 3 BUTTONS PER ROW
            if len(row) == 3:
                btn.append(row)
                row = []
        if row: btn.append(row)
        
        # Pagination Math
        current_page = (offset // 30) + 1
        total_pages = math.ceil(total_eps / 30) if total_eps > 0 else 1
        
        page_row = []
        if offset > 0:
            page_row.append(InlineKeyboardButton("⬅️ PREV", callback_data=f"swatch#{key}#{index}#{offset-30}"))
            
        page_row.append(InlineKeyboardButton(f"{current_page}/{total_pages}", callback_data="pages"))
        
        if total_eps > offset + 30:
            page_row.append(InlineKeyboardButton("NEXT ➡️", callback_data=f"swatch#{key}#{index}#{offset+30}"))
            
        if page_row: btn.append(page_row)
            
        btn.append([InlineKeyboardButton("🔙 BACK", callback_data=f"stitle#{key}#{index}"), InlineKeyboardButton("❌ CLOSE", callback_data="close_data")])
        
        await query.message.edit_caption(caption=cap, reply_markup=InlineKeyboardMarkup(btn))
    except Exception as e:
        logger.error(f"Error in swatch_cb: {e}")
        await query.answer("❌ Error processing grid. Please try again.", show_alert=True)

# ==========================================
# 🔙 BACK & DOWNLOAD CALLBACKS
# ==========================================
@Client.on_callback_query(filters.regex(r"^sback#"))
async def back_to_search(client, query):
    _, key = query.data.split("#")
    grouped_titles = temp.SEARCHES.get(key)
    if not grouped_titles: return await query.answer("❌ Session Expired! Search again.", show_alert=True)
    
    titles = list(grouped_titles.keys())
    btn = []
    for i, title in enumerate(titles[:10]):
        total_eps = len(grouped_titles[title]["files"])
        label = "CH" if grouped_titles[title]["category"] == "manga" else "EP"
        btn.append([InlineKeyboardButton(f"📺 {title} ({total_eps} {label})", callback_data=f"stitle#{key}#{i}")])
        
    btn.append([InlineKeyboardButton("📄 1/1", callback_data="pages")])
    btn.append([InlineKeyboardButton("🏠 HOME", callback_data="start"), InlineKeyboardButton("CLOSE", callback_data="close_data")])
    
    cap = f"🎯 <b>SEARCH RESULTS</b> ❞\n\n▸ <b>RESULTS:</b> {len(titles)} ITEMS\n▸ <b>PAGE:</b> 1 of 1\n\n<i>SELECT AN ITEM TO VIEW DETAILS ↓</i>"

    await query.message.edit_media(InputMediaPhoto(media=SEARCH_BANNER, caption=cap))
    await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(btn))

@Client.on_callback_query(filters.regex(r"^file#"))
async def single_file_cb(bot, query):
    _, file_id = query.data.split("#")
    await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start=file_{file_id}")

@Client.on_callback_query(filters.regex(r"^downall#"))
async def downall_cb(bot, query):
    _, key, index, offset = query.data.split("#")
    offset = int(offset)
    grouped_titles = temp.SEARCHES.get(key)
    if not grouped_titles: return await query.answer("❌ Session Expired! Search again.", show_alert=True)
    
    titles = list(grouped_titles.keys())
    selected_title = titles[int(index)]
    files_data = grouped_titles[selected_title]["files"]
    
    files_data.sort(key=lambda x: x[1])
    current_chunk = files_data[offset:offset+30]
    
    await query.answer("Sending files to your PM... ⏳", show_alert=False)
    for f, ep in current_chunk:
        try:
            await bot.send_cached_media(chat_id=query.from_user.id, file_id=f.file_id)
            await asyncio.sleep(0.5)
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
            await bot.send_cached_media(chat_id=query.from_user.id, file_id=f.file_id)
        except Exception:
            pass

@Client.on_callback_query(filters.regex(r"^close_data$"))
async def close_cb(bot, query):
    await query.message.delete()
    
@Client.on_callback_query(filters.regex(r"^addwatch#"))
async def addwatch_cb(bot, query):
    _, title = query.data.split("#")
    await query.answer(f"⭐ {title} Added to Library!", show_alert=True)
