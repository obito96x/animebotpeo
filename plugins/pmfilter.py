import asyncio, re, logging, math, aiohttp
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from pyrogram.errors import FloodWait

from database.users_chats_db import db
from database.ia_filterdb import Media, Media2 # Direct import for unlimited search
from utils import temp, get_settings
from info import *

try:
    from database.watchlist_db import add_to_watchlist, remove_from_watchlist
except ImportError:
    async def add_to_watchlist(u, t, c): pass
    async def remove_from_watchlist(u, t, c): pass

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

if not hasattr(temp, 'SEARCHES'): temp.SEARCHES = {}
OWNER_USERNAME = environ.get('OWNER_USERNAME', 'i_killed_my_clan')
SEARCH_BANNER = "https://graph.org/file/99eebf5dbe8a134f548e0.jpg"

# ==========================================
# 🧠 GOD-LEVEL CLEANER & EXTRACTOR
# ==========================================
def extract_and_clean(filename):
    ep_num = "0"
    
    # 1. Extract Chapter/Episode Number (Handles [C225.5], [S226], Ch-225.5, etc.)
    match = re.search(r'(?i)(?:\[C|\[S|ch[\-\s]*|ep[\-\s]*|vol[\-\s]*|v|e|season[\-\s]*)0*(\d+(?:\.\d+)?)', filename)
    if match:
        ep_num = match.group(1)
    else:
        match = re.search(r'(?i)[- ]\s*0*(\d+(?:\.\d+)?)\s*(?:1080p|720p|480p|mkv|mp4|pdf|cbz|cbr)', filename)
        if match: ep_num = match.group(1)

    # 2. Clean Name completely
    name = filename
    name = re.sub(r'\[.*?\]|\(.*?\)', '', name) # Remove ALL Brackets like [AC], [1080p]
    name = re.sub(r'\.(mkv|mp4|avi|mpe?g|pdf|cbz|cbr|jpg|png)$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'[^\w\s\.\-]', ' ', name) # Remove weird symbols like ⇉, ⌯
    name = re.split(r'(?i)(?:\s-\s)?\b(?:ch|chapter|ep|episode|vol|volume|season)\b', name)[0] # Chop at Ep/Ch
    name = re.split(r'(?i)\bs\d{1,2}\b', name)[0] # Chop at S01
    name = re.sub(r'(?i)@\w+', '', name) # Remove Telegram Usernames
    name = re.sub(r'(?i)\b(1080p|720p|480p|amzn|web|dl|rip|dual|audio|hindi|english|subbed|dubbed)\b', '', name)
    name = re.sub(r'[^a-zA-Z0-9\s]', ' ', name).strip() # Final symbol strip
    name = " ".join(name.split()).title()

    return name if name else "Unknown", ep_num

def get_emoji(filename):
    ext = filename.split('.')[-1].lower() if '.' in filename else ''
    if ext == 'pdf': return '📕'
    if ext in ['cbz', 'cbr']: return '📗'
    if ext in ['mkv', 'mp4', 'avi']: return '🎬'
    return '📙'

# ==========================================
# 🌐 ANILIST 16:9 COVER (ENGLISH NAMES)
# ==========================================
async def fetch_anilist_16x9(query, category="anime"):
    url = "https://graphql.anilist.co"
    media_type = "MANGA" if category == "manga" else "ANIME"
    graphql_query = '''
    query ($search: String, $type: MediaType) {
      Media (search: $search, type: $type) {
        title { english romaji }
        bannerImage
        coverImage { extraLarge }
        averageScore
        format
        status
        episodes
        chapters
        genres
        description
        startDate { year }
      }
    }
    '''
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={'query': graphql_query, 'variables': {"search": query, "type": media_type}}) as resp:
                data = await resp.json()
                if 'data' in data and data['data']['Media']:
                    return data['data']['Media']
    except Exception: pass
    return None

# ==========================================
# 🔍 AUTO FILTER (UNLIMITED SEARCH FIX)
# ==========================================
async def auto_filter(client, msg, req_cat=None):
    search = msg.text.lower()
    if len(search) < 2 or len(search) > 100: return
    
    m = await msg.reply_text(f'**🔎 Searching Database...** `{search}`')
    search_clean = re.sub(r"[:-]", "", search.replace("-", " ")).strip()
    
    # 🔥 UNLIMITED SEARCH QUERY (Bypasses the 10-50 limit)
    regex_pattern = {"$regex": search_clean.replace(" ", ".*"), "$options": "i"}
    cursor1 = Media.find({"file_name": regex_pattern})
    cursor2 = Media2.find({"file_name": regex_pattern})
    
    files = await cursor1.to_list(length=2000) + await cursor2.to_list(length=2000)
    
    if not files: 
        return await m.edit("<b>❌ No Anime/Manga found with this name. Check spelling!</b>")

    key = f"{msg.chat.id}-{msg.id}"
    grouped_titles = {}
    
    search_words = search_clean.split()
    prefix = " ".join(search_words[:2]).lower() if len(search_words) >= 2 else search_clean.lower()
    
    for f in files:
        title, ep = extract_and_clean(f.file_name)
        is_manga = any(x in f.file_name.lower() for x in ['.pdf', '.cbz', '.cbr', 'manga', 'ch '])
        cat = "manga" if is_manga else "anime"
        
        if req_cat and cat != req_cat: continue
            
        if prefix in title.lower() or search_clean.lower() in f.file_name.lower().replace('.',' '):
            title = search_clean.title()
            
        if title not in grouped_titles: 
            grouped_titles[title] = {"files": [], "category": cat, "seen_eps": set()}
            
        try: ep_val = float(ep) if '.' in ep else int(ep)
        except: ep_val = 0
            
        # 🔥 DUPLICATE CHAPTER REMOVER (10 Channels issue fixed)
        if ep_val not in grouped_titles[title]["seen_eps"]:
            grouped_titles[title]["files"].append((f, ep_val))
            grouped_titles[title]["seen_eps"].add(ep_val)
            
    if not grouped_titles:
        return await m.edit(f"<b>❌ No {req_cat if req_cat else 'files'} found for this query!</b>")
        
    temp.SEARCHES[key] = grouped_titles
    titles = list(grouped_titles.keys())
    
    btn = []
    for i, title in enumerate(titles[:30]): 
        cat = grouped_titles[title]["category"]
        total_eps = len(grouped_titles[title]["files"])
        label = f"📚 {title}" if cat == "manga" else f"📺 {title} ({total_eps} EP)"
        btn.append([InlineKeyboardButton(label, callback_data=f"stitle#{key}#{i}")])
        
    btn.append([InlineKeyboardButton("🏠 HOME", callback_data="start"), InlineKeyboardButton("❌ CLOSE", callback_data="close_data")])
    
    cap = f"🎯 <b>SEARCH RESULTS</b> ❞\n\n"
    cap += f"▸ <b>QUERY:</b> {search_clean}\n"
    cap += f"▸ <b>RESULTS:</b> {len(titles)} GROUPS FOUND\n\n"
    cap += "<i>SELECT AN ITEM TO VIEW DETAILS ↓</i>"

    await m.delete()
    await msg.reply_photo(photo=SEARCH_BANNER, caption=cap, reply_markup=InlineKeyboardMarkup(btn))

# ==========================================
# 📺 STEP 2: DETAILS UI
# ==========================================
@Client.on_callback_query(filters.regex(r"^stitle#"))
async def select_title_cb(client, query):
    try:
        _, key, index = query.data.split("#")
        grouped_titles = temp.SEARCHES.get(key)
        if not grouped_titles: return await query.answer("❌ Session Expired!", show_alert=True)
        
        titles = list(grouped_titles.keys())
        selected_title = titles[int(index)]
        title_data = grouped_titles[selected_title]
        total_eps = len(title_data["files"])
        cat = title_data["category"]
        
        anime_info = await fetch_anilist_16x9(selected_title, cat)
        if not anime_info: anime_info = {}
        
        anilist_title = anime_info.get('title', {})
        display_title = anilist_title.get('english') or anilist_title.get('romaji') or selected_title
        
        cover = anime_info.get("bannerImage") or anime_info.get("coverImage", {}).get("extraLarge", SEARCH_BANNER)
        atype = "Manhwa/Manga" if cat == "manga" else str(anime_info.get('format', 'TV Series')).replace('_',' ')
        status = anime_info.get('status', 'RELEASING').title()
        year = anime_info.get('startDate', {}).get('year', 'Unknown')
        genres = ", ".join(anime_info.get('genres', ['Action', 'Fantasy'])[:3])
        
        synopsis_raw = str(anime_info.get('description', 'Synopsis not available.'))
        synopsis = re.sub(r'<[^>]+>', '', synopsis_raw)[:250] 
        
        cap = f"📚 <b>{display_title}</b> ❞\n"
        cap += f"┌──────────────────────\n"
        cap += f"✧ <b>Type:</b> {atype} | ✧ <b>Status:</b> {status}\n"
        cap += f"✦ <b>{'Chapters' if cat == 'manga' else 'Episodes'}:</b> {total_eps}\n"
        cap += f"✶ <b>Genres:</b> {genres}\n"
        cap += f"✦ <b>Since:</b> {year}\n"
        cap += f"⚟ <b>Synopsis:</b> {synopsis}...\n"

        read_btn_txt = "📖 READ CHAPTERS" if cat == "manga" else "👀 WATCH EPISODES"
        down_btn_txt = "📥 DOWNLOAD CHAPTERS" if cat == "manga" else "📥 DOWNLOAD ALL"
        lib_btn_txt = "📁 ADD TO LIBRARY" if cat == "manga" else "⭐ ADD TO WATCHLIST"
        
        safe_title = selected_title[:35]
        
        btn = [
            [InlineKeyboardButton(read_btn_txt, callback_data=f"swatch#{key}#{index}#0")],
            [InlineKeyboardButton(lib_btn_txt, callback_data=f"addwatch#{safe_title}#{cat}")],
            [InlineKeyboardButton(down_btn_txt, callback_data=f"downall#{key}#{index}#0")],
            [InlineKeyboardButton("🔙 BACK", callback_data=f"sback#{key}"), InlineKeyboardButton("❌ CLOSE", callback_data="close_data")]
        ]
        
        await query.message.edit_media(InputMediaPhoto(media=cover, caption=cap))
        await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
    except Exception as e:
        logger.error(f"Error in select_title_cb: {e}")
        await query.answer("❌ Error processing details.", show_alert=True)

# ==========================================
# 🔢 STEP 3: 3-COLUMN GRID
# ==========================================
def safe_float(val):
    try: return float(val)
    except: return 0.0

@Client.on_callback_query(filters.regex(r"^swatch#"))
async def swatch_cb(client, query):
    try:
        _, key, index, offset = query.data.split("#")
        offset = int(offset)
        
        grouped_titles = temp.SEARCHES.get(key)
        if not grouped_titles: return await query.answer("❌ Session Expired!", show_alert=True)
        
        titles = list(grouped_titles.keys())
        selected_title = titles[int(index)]
        cat = grouped_titles[selected_title]["category"]
        files_data = grouped_titles[selected_title]["files"]
        total_eps = len(files_data)
        
        # 🔥 FLOAT SORTING: Ch 225.5 comes exactly after 225
        files_data.sort(key=lambda x: safe_float(x[1]))
        current_chunk = files_data[offset:offset+30]
        
        cap = f"📚 <b>{selected_title}</b> ❞\n\n"
        cap += f"<b>Select {'chapter' if cat == 'manga' else 'episode'} to {'read' if cat == 'manga' else 'watch'} (oldest first):</b>\n"
        cap += f"📕 <i>PDF</i> 📗 <i>CBZ</i> 📘 <i>CBR</i> 🎬 <i>Video</i>"

        btn = []
        row = []
        for f, ep_num in current_chunk:
            fmt_ep = str(int(ep_num)) if ep_num == int(ep_num) else str(ep_num)
            icon = get_emoji(f.file_name)
            label = f"Ch {fmt_ep} {icon}" if cat == "manga" else f"Ep {fmt_ep} {icon}"
            row.append(InlineKeyboardButton(label, callback_data=f"file#{f.file_id}"))
            if len(row) == 3:
                btn.append(row)
                row = []
        if row: btn.append(row)
        
        current_page = (offset // 30) + 1
        total_pages = math.ceil(total_eps / 30) if total_eps > 0 else 1
        page_row = []
        if offset > 0: page_row.append(InlineKeyboardButton("⬅️ PREV", callback_data=f"swatch#{key}#{index}#{offset-30}"))
        page_row.append(InlineKeyboardButton(f"{current_page}/{total_pages}", callback_data="pages"))
        if total_eps > offset + 30: page_row.append(InlineKeyboardButton("NEXT ➡️", callback_data=f"swatch#{key}#{index}#{offset+30}"))
        if page_row: btn.append(page_row)
            
        btn.append([InlineKeyboardButton("🔙 BACK", callback_data=f"stitle#{key}#{index}"), InlineKeyboardButton("❌ CLOSE", callback_data="close_data")])
        await query.message.edit_caption(caption=cap, reply_markup=InlineKeyboardMarkup(btn))
    except Exception as e:
        logger.error(f"Error in swatch_cb: {e}")
        await query.answer("❌ Error processing grid.", show_alert=True)

@Client.on_callback_query(filters.regex(r"^sback#"))
async def back_to_search(client, query):
    _, key = query.data.split("#")
    grouped_titles = temp.SEARCHES.get(key)
    if not grouped_titles: return await query.answer("❌ Session Expired!", show_alert=True)
    
    titles = list(grouped_titles.keys())
    btn = []
    for i, title in enumerate(titles[:30]):
        cat = grouped_titles[title]["category"]
        total_eps = len(grouped_titles[title]["files"])
        label = f"📚 {title}" if cat == "manga" else f"📺 {title} ({total_eps} EP)"
        btn.append([InlineKeyboardButton(label, callback_data=f"stitle#{key}#{i}")])
        
    btn.append([InlineKeyboardButton("🏠 HOME", callback_data="start"), InlineKeyboardButton("CLOSE", callback_data="close_data")])
    cap = f"🎯 <b>SEARCH RESULTS</b> ❞\n\n▸ <b>RESULTS:</b> {len(titles)} GROUPS\n\n<i>SELECT AN ITEM TO VIEW DETAILS ↓</i>"

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
    if not grouped_titles: return await query.answer("❌ Session Expired!", show_alert=True)
    
    titles = list(grouped_titles.keys())
    selected_title = titles[int(index)]
    files_data = grouped_titles[selected_title]["files"]
    files_data.sort(key=lambda x: safe_float(x[1]))
    current_chunk = files_data[offset:offset+30]
    
    await query.answer("Sending files to your PM... ⏳", show_alert=False)
    for f, ep in current_chunk:
        try:
            await bot.send_cached_media(chat_id=query.from_user.id, file_id=f.file_id)
            await asyncio.sleep(0.5)
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
            await bot.send_cached_media(chat_id=query.from_user.id, file_id=f.file_id)
        except Exception: pass

@Client.on_callback_query(filters.regex(r"^close_data$"))
async def close_cb(bot, query):
    await query.message.delete()
    
@Client.on_callback_query(filters.regex(r"^addwatch#"))
async def addwatch_cb(bot, query):
    _, title, cat = query.data.split("#")
    user_id = query.from_user.id
    await add_to_watchlist(user_id, title, cat)
    msg_txt = "Library" if cat == "manga" else "Watchlist"
    await query.answer(f"⭐ {title} Added to {msg_txt}!", show_alert=True)
    btn_txt = "➖ REMOVE FROM LIBRARY" if cat == "manga" else "➖ REMOVE FROM WATCHLIST"
    new_btn = list(query.message.reply_markup.inline_keyboard)
    new_btn[1] = [InlineKeyboardButton(btn_txt, callback_data=f"remwatch#{title}#{cat}")]
    await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(new_btn))

@Client.on_callback_query(filters.regex(r"^remwatch#"))
async def remwatch_cb(bot, query):
    _, title, cat = query.data.split("#")
    user_id = query.from_user.id
    await remove_from_watchlist(user_id, title, cat)
    msg_txt = "Library" if cat == "manga" else "Watchlist"
    await query.answer(f"➖ {title} Removed from {msg_txt}!", show_alert=True)
    btn_txt = "📁 ADD TO LIBRARY" if cat == "manga" else "⭐ ADD TO WATCHLIST"
    new_btn = list(query.message.reply_markup.inline_keyboard)
    new_btn[1] = [InlineKeyboardButton(btn_txt, callback_data=f"addwatch#{title}#{cat}")]
    await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(new_btn))
            
