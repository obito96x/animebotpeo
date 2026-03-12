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

if not hasattr(temp, 'SEARCHES'): temp.SEARCHES = {}
if not hasattr(temp, 'SEASONS_CACHE'): temp.SEASONS_CACHE = {} # Naya Cache For Seasons
OWNER_USERNAME = environ.get('OWNER_USERNAME', 'i_killed_my_clan')
SEARCH_BANNER = "https://graph.org/file/99eebf5dbe8a134f548e0.jpg"

# ==========================================
# 🧠 ADVANCED REGEX FILE PARSER
# ==========================================
SEP = r'[\s\.\-_]*'
SEASON_EPISODE_PATTERNS = [
    (re.compile(rf'\bS{SEP}(\d{{1,2}}){SEP}E{SEP}(\d{{1,4}})\b', re.IGNORECASE), (1, 2)),
    (re.compile(rf'\[S{SEP}(\d{{1,2}}){SEP}E{SEP}(\d{{1,4}})\]', re.IGNORECASE), (1, 2)),
    (re.compile(rf'\b(\d{{1,2}}){SEP}[xX]{SEP}(\d{{1,4}})\b', re.IGNORECASE), (1, 2)),
    (re.compile(rf'\[(\d{{1,2}}){SEP}[xX]{SEP}(\d{{1,4}})\]', re.IGNORECASE), (1, 2)),
    (re.compile(rf'\bSeason{SEP}(\d{{1,2}}){SEP}Episode{SEP}(\d{{1,4}})\b', re.IGNORECASE), (1, 2)),
    (re.compile(rf'\bSeason{SEP}(\d{{1,2}}){SEP}Ep{SEP}(\d{{1,4}})\b', re.IGNORECASE), (1, 2)),
    (re.compile(rf'\[S{SEP}(\d{{1,2}})\]{SEP}\[E{SEP}(\d{{1,4}})\]', re.IGNORECASE), (1, 2)),
    (re.compile(rf'\bE{SEP}(\d{{1,4}}){SEP}S{SEP}(\d{{1,2}})\b', re.IGNORECASE), (2, 1)),
    (re.compile(rf'\bE{SEP}(\d{{1,4}})(?=[\s\.\-_)\'\]]+|$)(?![\dp])', re.IGNORECASE), (None, 1)),
    (re.compile(rf'\[E{SEP}(\d{{1,4}})\]', re.IGNORECASE), (None, 1)),
    (re.compile(rf'\bEpisode{SEP}(\d{{1,4}})(?=[\s\.\-_)\]]+|$)', re.IGNORECASE), (None, 1)),
    (re.compile(rf'\bEp{SEP}(\d{{1,4}})(?=[\s\.\-_)\]]+|$)', re.IGNORECASE), (None, 1)),
    (re.compile(r'\[(\d{2,3})\](?!p|fps|i)', re.IGNORECASE), (None, 1)),
    (re.compile(r'\bS(\d{1,2})[\.\-_]?E(\d{1,4})\b', re.IGNORECASE), (1, 2)), 
    (re.compile(r'\bS(\d{1,2})\s+E(\d{1,4})\b', re.IGNORECASE), (1, 2)),
    (re.compile(r'\bSeason[\s\-_.]*(\d{1,2})[\s\-_.]*E[\s\-_.]*(\d{1,4})\b', re.IGNORECASE), (1, 2)),
    (re.compile(r'\bS(\d{1,2})\.(\d{1,4})\b', re.IGNORECASE), (1, 2)),
    (re.compile(r'\bS(\d{1,2})\-(\d{1,4})\b', re.IGNORECASE), (1, 2)),
    (re.compile(r'\b(\d{1,2})\.(\d{1,4})\b(?!p|fps)', re.IGNORECASE), (1, 2)),
    (re.compile(r'\b(\d{1,2})\-(\d{1,4})\b(?!p|fps)', re.IGNORECASE), (1, 2)),
    (re.compile(r'(?:^|[\s\-_.(\[])E(\d{2,5})(?=[\s\-_.)\]]|$)(?!p|fps)', re.IGNORECASE), (None, 1)),
    (re.compile(r'(?:^|[\s\-_.(\[])Episode[\s\-_.]*(\d{1,4})(?=[\s\-_.)\]]|$)', re.IGNORECASE), (None, 1)),
    (re.compile(r'(?:^|[\s\-_.(\[])Ep[\s\-_.]*(\d{1,4})(?=[\s\-_.)\]]|$)', re.IGNORECASE), (None, 1)),
    (re.compile(r'(?:^|[\s\-_.])(\d{2,4})(?=[\s\-_.]|$)(?!p|fps|\d)', re.IGNORECASE), (None, 1)),
    (re.compile(r'\[(\d{2,4})\](?!p|fps)', re.IGNORECASE), (None, 1)),
    (re.compile(r'^S(\d{2})E(\d{2,4})$', re.IGNORECASE), (1, 2)),
    (re.compile(r'^S(\d{2})\s*-\s*E(\d{2,4})$', re.IGNORECASE), (1, 2)),
    (re.compile(r'\[[\s]*(\d{2,4})[\s]*\](?!p|i|fps)', re.IGNORECASE), (None, 1)),
    (re.compile(r'(?:^|[\s\-_.(\[])\s*(\d{2,4})\s*(?=[\s\-_.)\]])', re.IGNORECASE), (None, 1))
]

def extract_file_info(filename, fallback_index=0):
    season = "1"
    episode = str(fallback_index)
    
    for pattern, (s_idx, e_idx) in SEASON_EPISODE_PATTERNS:
        match = pattern.search(filename)
        if match:
            if s_idx is not None:
                try: season = str(int(match.group(s_idx)))
                except: pass
            if e_idx is not None:
                try: episode = str(int(match.group(e_idx)))
                except: pass
            break

    lower_name = filename.lower()
    qual = "Normal"
    if re.search(r'\b(2160p|4k)\b', lower_name): qual = "4K"
    elif re.search(r'\b1080p\b', lower_name): qual = "1080p"
    elif re.search(r'\b720p\b', lower_name): qual = "720p"
    elif re.search(r'\b480p\b', lower_name): qual = "480p"
    
    clean_title = re.sub(r'\.(mkv|mp4|avi|mpe?g)$', '', filename, flags=re.IGNORECASE)
    clean_title = re.sub(r'\[.*?\]|\(.*?\)', '', clean_title)
    
    for pattern, _ in SEASON_EPISODE_PATTERNS:
        m = pattern.search(clean_title)
        if m:
            clean_title = clean_title[:m.start()]
            break
            
    clean_title = clean_title.replace(".", " ").replace("_", " ")
    tags = r'\b(mkv|mp4|avi|hd|1080p|720p|480p|4k|webrip|web-dl|amzn|x265|x264|hevc|hindi|english|dual|audio|dubbed|subbed)\b'
    clean_title = re.sub(tags, '', clean_title, flags=re.IGNORECASE)
    clean_title = re.sub(r'[-–—~]\s*$', '', clean_title.strip()).strip()
    clean_title = " ".join(clean_title.split())
    if not clean_title: clean_title = "Unknown Anime"
    
    return clean_title.title(), season, episode, qual

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
    await message.reply_text(f"<b>🙋 ʜᴇʏ {message.from_user.first_name}, \n\nPlease use the `/search` command to find Anime/Manga!\n\nExample: `/search Naruto`</b>")

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
    
    # 🧠 GROUP FILES BY CLEAN NAME AND SEASON
    grouped_titles = {}
    for i, f in enumerate(files):
        title, season, ep, qual = extract_file_info(f.file_name, i)
        
        if title not in grouped_titles: 
            grouped_titles[title] = {"seasons": {}}
            
        if season not in grouped_titles[title]["seasons"]:
            grouped_titles[title]["seasons"][season] = []
            
        ep_int = int(ep) if ep.isdigit() else 0
        grouped_titles[title]["seasons"][season].append((f, ep_int, qual))
        
    temp.SEARCHES[key] = grouped_titles
    titles = list(grouped_titles.keys())
    
    btn = []
    for i, title in enumerate(titles[:10]): 
        total_ep_count = sum([len(s) for s in grouped_titles[title]["seasons"].values()])
        btn.append([InlineKeyboardButton(f"📺 {title} ({total_ep_count} EP)", callback_data=f"stitle#{key}#{i}")])
        
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
# 📺 STEP 2: ANIME DETAILS UI (INFO BOX)
# ==========================================
@Client.on_callback_query(filters.regex(r"^stitle#"))
async def select_title_cb(client, query):
    _, key, index = query.data.split("#")
    
    grouped_titles = temp.SEARCHES.get(key)
    if not grouped_titles: return await query.answer("Session Expired!", show_alert=True)
    
    titles = list(grouped_titles.keys())
    selected_title = titles[int(index)]
    title_data = grouped_titles[selected_title]
    total_eps = sum([len(s) for s in title_data["seasons"].values()])
    
    anime_info = await get_anime_info(selected_title) if get_anime_info else {}
    
    # Optional cover handling, fallback to Search Banner (Ensure Anilist returns 16:9 images if configured)
    cover = anime_info.get("cover_image", SEARCH_BANNER) 
    rating = anime_info.get('score', 'N/A')
    atype = anime_info.get('format', 'TV Series')
    status = anime_info.get('status', 'FINISHED')
    eps = anime_info.get('episodes', total_eps)
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

    # 🔥 Check if multiple seasons exist
    available_seasons = list(title_data["seasons"].keys())
    available_seasons.sort(key=lambda x: int(x) if x.isdigit() else 0)
    
    btn = []
    
    # If Anime has multiple seasons, show Season Buttons first!
    if len(available_seasons) > 1:
        for s in available_seasons:
            s_ep_count = len(title_data["seasons"][s])
            btn.append([InlineKeyboardButton(f"✨ Season {s} ({s_ep_count} EP)", callback_data=f"sselect#{key}#{index}#{s}")])
    else:
        # Direct Watch Now if only 1 season exists
        only_s = available_seasons[0]
        btn.append([InlineKeyboardButton("👀 WATCH NOW", callback_data=f"swatch#{key}#{index}#{only_s}#0")])
        
    btn.append([InlineKeyboardButton("⭐ ADD TO WATCHLIST", callback_data=f"addwatch#{selected_title}")])
    btn.append([InlineKeyboardButton("🔙 BACK", callback_data=f"sback#{key}"), InlineKeyboardButton("❌ CLOSE", callback_data="close_data")])
    
    await query.message.edit_media(InputMediaPhoto(media=cover, caption=cap))
    await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(btn))


# ==========================================
# 🌟 STEP 2.5: SEASON TO EPISODE REDIRECT
# ==========================================
@Client.on_callback_query(filters.regex(r"^sselect#"))
async def season_select_cb(client, query):
    _, key, index, season_num = query.data.split("#")
    # Redirect to swatch (Episode Grid) but for the specific season!
    query.data = f"swatch#{key}#{index}#{season_num}#0"
    await swatch_cb(client, query)

# ==========================================
# 🔢 STEP 3: EPISODE GRID UI (30 EPs per page)
# ==========================================
@Client.on_callback_query(filters.regex(r"^swatch#"))
async def swatch_cb(client, query):
    _, key, index, season_num, offset = query.data.split("#")
    offset = int(offset)
    
    grouped_titles = temp.SEARCHES.get(key)
    if not grouped_titles: return await query.answer("Session Expired!", show_alert=True)
    
    titles = list(grouped_titles.keys())
    selected_title = titles[int(index)]
    
    # Fetch episodes for ONLY the selected Season
    season_files = grouped_titles[selected_title]["seasons"].get(season_num, [])
    total_eps = len(season_files)
    
    season_files.sort(key=lambda x: x[1])
    current_chunk = season_files[offset:offset+30]
    
    end_offset = min(offset + 30, total_eps)
    cap = f"📺 <b>{selected_title} (Season {season_num})</b>\n\n"
    cap += f"<b>Select episode ({offset+1}-{end_offset} of {total_eps}):</b>"

    btn = []
    row = []
    for f, ep_num, qual in current_chunk:
        row.append(InlineKeyboardButton(str(ep_num), callback_data=f"file#{f.file_id}"))
        if len(row) == 5:
            btn.append(row)
            row = []
    if row: btn.append(row)
    
    btn.append([InlineKeyboardButton("📥 DOWNLOAD ALL EPISODES", callback_data=f"downall#{key}#{index}#{season_num}#{offset}")])
    
    page_row = []
    if offset > 0:
        page_row.append(InlineKeyboardButton("⬅️ PREV", callback_data=f"swatch#{key}#{index}#{season_num}#{offset-30}"))
    if total_eps > offset + 30:
        page_row.append(InlineKeyboardButton("NEXT ➡️", callback_data=f"swatch#{key}#{index}#{season_num}#{offset+30}"))
    if page_row: btn.append(page_row)
        
    btn.append([InlineKeyboardButton("🔙 BACK", callback_data=f"stitle#{key}#{index}"), InlineKeyboardButton("❌ CLOSE", callback_data="close_data")])
    
    await query.message.edit_caption(caption=cap, reply_markup=InlineKeyboardMarkup(btn))

# ==========================================
# 🔙 EXTRA CALLBACKS
# ==========================================
@Client.on_callback_query(filters.regex(r"^sback#"))
async def back_to_search(client, query):
    _, key = query.data.split("#")
    grouped_titles = temp.SEARCHES.get(key)
    if not grouped_titles: return await query.answer("Session Expired!", show_alert=True)
    
    titles = list(grouped_titles.keys())
    btn = []
    for i, title in enumerate(titles[:10]):
        total_ep_count = sum([len(s) for s in grouped_titles[title]["seasons"].values()])
        btn.append([InlineKeyboardButton(f"📺 {title}", callback_data=f"stitle#{key}#{i}")])
        
    btn.append([InlineKeyboardButton("📄 1/1", callback_data="pages")])
    btn.append([InlineKeyboardButton("🏠 HOME", callback_data="start"), InlineKeyboardButton("CLOSE", callback_data="close_data")])
    
    cap = f"🎯 <b>ꜱᴇᴀʀᴄʜ ʀᴇsᴜʟᴛꜱ</b>\n\n▸ <b>Rᴇsᴜʟᴛꜱ:</b> {len(titles)} ᴀɴɪᴍᴇ\n▸ <b>Pᴀɢᴇ:</b> 1 of 1\n\n<i>ꜱᴇʟᴇᴄᴛ ᴀɴ ᴀɴɪᴍᴇ ᴛᴏ ᴠɪᴇᴡ ᴅᴇᴛᴀɪʟꜱ ↓</i>"

    await query.message.edit_media(InputMediaPhoto(media=SEARCH_BANNER, caption=cap))
    await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(btn))

@Client.on_callback_query(filters.regex(r"^file#"))
async def single_file_cb(bot, query):
    _, file_id = query.data.split("#")
    await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start=file_{file_id}")

@Client.on_callback_query(filters.regex(r"^downall#"))
async def downall_cb(bot, query):
    _, key, index, season_num, offset = query.data.split("#")
    offset = int(offset)
    grouped_titles = temp.SEARCHES.get(key)
    if not grouped_titles: return await query.answer("Session Expired!", show_alert=True)
    
    titles = list(grouped_titles.keys())
    selected_title = titles[int(index)]
    season_files = grouped_titles[selected_title]["seasons"].get(season_num, [])
    
    season_files.sort(key=lambda x: x[1])
    current_chunk = season_files[offset:offset+30]
    
    await query.answer("Sending episodes to your PM... ⏳", show_alert=False)
    for f, ep, qual in current_chunk:
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
    await query.answer(f"⭐ {title} Added to Watchlist!", show_alert=True)
    
    new_btn = [
        [InlineKeyboardButton(query.message.reply_markup.inline_keyboard[0][0].text, callback_data=query.message.reply_markup.inline_keyboard[0][0].callback_data)],
        [InlineKeyboardButton("➖ REMOVE FROM WATCHLIST", callback_data=f"remwatch#{title}")],
        [InlineKeyboardButton("🔙 BACK", callback_data=query.message.reply_markup.inline_keyboard[2][0].callback_data), 
         InlineKeyboardButton("❌ CLOSE", callback_data="close_data")]
    ]
    await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(new_btn))

@Client.on_callback_query(filters.regex(r"^remwatch#"))
async def remwatch_cb(bot, query):
    _, title = query.data.split("#")
    await query.answer(f"➖ {title} Removed from Watchlist!", show_alert=True)
    
    new_btn = [
        [InlineKeyboardButton(query.message.reply_markup.inline_keyboard[0][0].text, callback_data=query.message.reply_markup.inline_keyboard[0][0].callback_data)],
        [InlineKeyboardButton("⭐ ADD TO WATCHLIST", callback_data=f"addwatch#{title}")],
        [InlineKeyboardButton("🔙 BACK", callback_data=query.message.reply_markup.inline_keyboard[2][0].callback_data), 
         InlineKeyboardButton("❌ CLOSE", callback_data="close_data")]
    ]
    await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(new_btn))
                          
