import asyncio, re, logging, math, aiohttp, uuid, os, random
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from pyrogram.errors import FloodWait

from database.users_chats_db import db
from database.ia_filterdb import Media, Media2 
from database.watchlist_db import add_to_watchlist, remove_from_watchlist, get_autodelete_time, get_sticker
from database.database import ProObito
from utils import temp, get_settings
from info import *

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

if not hasattr(temp, 'SEARCHES'): temp.SEARCHES = {}
OWNER_USERNAME = environ.get('OWNER_USERNAME', 'i_killed_my_clan')
PICS = (os.environ.get("PICS", "https://envs.sh/ZUb.png?2ftEB=1 https://envs.sh/ZUi.png?KNgjn=1 https://envs.sh/oD5.jpg https://envs.sh/7nm.jpg https://envs.sh/Chb.jpg")).split()

# =========================================
# ⏱️ VIP AUTO DELETE LOGIC
# =========================================
def convert_time(duration_seconds: int) -> str:
    periods = [('Yᴇᴀʀ', 31536000), ('Mᴏɴᴛʜ', 2592000), ('Dᴀʏ', 86400), ('Hᴏᴜʀ', 3600), ('Mɪɴᴜᴛᴇ', 60), ('Sᴇᴄᴏɴᴅ', 1)]
    parts = []
    for period_name, period_seconds in periods:
        if duration_seconds >= period_seconds:
            num_periods = duration_seconds // period_seconds
            duration_seconds %= period_seconds
            parts.append(f"{num_periods} {period_name}{'s' if num_periods > 1 else ''}")
    if len(parts) == 0: return "0 Sᴇᴄᴏɴᴅ"
    elif len(parts) == 1: return parts[0]
    else: return ', '.join(parts[:-1]) +' ᴀɴᴅ '+ parts[-1]

DEL_MSG = "<b>⚠️ Dᴜᴇ ᴛᴏ Cᴏᴘʏʀɪɢʜᴛ ɪssᴜᴇs....\n<blockquote>Yᴏᴜʀ ғɪʟᴇs ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇᴅ ᴡɪᴛʜɪɴ <a href='https://t.me/{username}'>{time}</a>. Sᴏ ᴘʟᴇᴀsᴇ ғᴏʀᴡᴀʀᴅ ᴛʜᴇᴍ ᴛᴏ ᴀɴʏ ᴏᴛʜᴇʀ ᴘʟᴀᴄᴇ ғᴏʀ ғᴜᴛᴜʀᴇ ᴀᴠᴀɪʟᴀʙɪʟɪᴛʏ.</blockquote></b>"

async def auto_del_notification(client, msg_chat_id, messages, delay_time, transfer=None):
    bot_me = await client.get_me()
    bot_username = bot_me.username
    temp_msg = await client.send_message(msg_chat_id, DEL_MSG.format(username=bot_username, time=convert_time(delay_time)), disable_web_page_preview=True)
    await asyncio.sleep(delay_time)
    for m in messages:
        try:
            if m: await m.delete()
        except: pass
    try:
        if transfer:
            name = "♻️ Cʟɪᴄᴋ Hᴇʀᴇ"
            link = f"https://t.me/{bot_username}?start={transfer}"
            button = [[InlineKeyboardButton(text=name, url=link), InlineKeyboardButton(text="Cʟᴏsᴇ ✖️", callback_data="close_data")]]
            await temp_msg.edit_text(text=f"<b>Pʀᴇᴠɪᴏᴜs Mᴇssᴀɢᴇ ᴡᴀs Dᴇʟᴇᴛᴇᴅ 🗑\n<blockquote>Iғ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ɢᴇᴛ ᴛʜᴇ ғɪʟᴇs ᴀɢᴀɪɴ, ᴛʜᴇɴ ᴄʟɪᴄᴋ: [<a href='{link}'>{name}</a>] ʙᴜᴛᴛᴏɴ ʙᴇʟᴏᴡ ᴇʟsᴇ ᴄʟᴏsᴇ ᴛʜɪs ᴍᴇssᴀɢᴇ.</blockquote></b>", reply_markup=InlineKeyboardMarkup(button), disable_web_page_preview=True)
        else:
            await temp_msg.edit_text("<b><blockquote>Pʀᴇᴠɪᴏᴜs Mᴇssᴀɢᴇ ᴡᴀs Dᴇʟᴇᴛᴇᴅ 🗑</blockquote></b>")
    except Exception: pass

# ==========================================
# 🧠 EXTRACTOR (AUDIO, SEASON & 70% MATCH)
# ==========================================
def extract_file_info(filename):
    season = 1
    ep_num = 0.0
    audio_tags = []

    lower_name = filename.lower()
    if 'multi' in lower_name: audio_tags.append("Multi")
    elif 'dual' in lower_name: audio_tags.append("Dual")
    elif 'dub' in lower_name: audio_tags.append("Dub")
    elif 'sub' in lower_name: audio_tags.append("Sub")
    audio = " ".join(audio_tags)

    s_e_match = re.search(r'(?i)(?:\[?s|season)\s*0*(\d+).*?(?:e|ep|episode)\s*0*(\d+(?:\.\d+)?)]?', filename)
    if s_e_match:
        season = int(s_e_match.group(1))
        ep_num = float(s_e_match.group(2))
    else:
        s_match = re.search(r'(?i)(?:s|season)\s*0*(\d+)', filename)
        if s_match: season = int(s_match.group(1))
        ep_match = re.search(r'(?i)(?:\[C|\[S|ch[\-\s]*|ep[\-\s]*|vol[\-\s]*|v|e)(?!s\d)0*(\d+(?:\.\d+)?)', filename)
        if ep_match:
            ep_num = float(ep_match.group(1))
        else:
            ep_match = re.search(r'(?i)[- ]\s*0*(\d+(?:\.\d+)?)\s*(?:1080p|720p|480p|mkv|mp4|pdf|cbz|cbr)', filename)
            if ep_match: ep_num = float(ep_match.group(1))

    name = filename
    # Remove S02 E12 formats completely from title before cleaning
    name = re.sub(r'(?i)(?:\[?s|season)\s*0*\d+.*?(?:e|ep|episode)\s*0*\d+(?:\.\d+)?]?', '', name)
    name = re.sub(r'(?i)(?:\[?s|season)\s*0*\d+]?', '', name)
    name = re.sub(r'(?i)(?:\[C|\[S|ch[\-\s]*|ep[\-\s]*|vol[\-\s]*|v|e)(?!s\d)0*\d+(?:\.\d+)?]?', '', name)
    
    name = re.sub(r'\[.*?\]|\(.*?\)', '', name) 
    name = re.sub(r'\.(mkv|mp4|avi|mpe?g|pdf|cbz|cbr|jpg|png)$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'(?i)\b(1080p|720p|480p|amzn|web-?dl|rip|dual|multi|audio|hindi|english|subbed|dubbed|dub|sub|x264|x265|hevc|ddp2?\.?\d?|aac)\b', '', name)
    name = re.sub(r'[^a-zA-Z0-9\s]', ' ', name).strip() 
    name = re.sub(r'\s+', ' ', name)
    name = name.strip('- ').title()

    return name if name else "Unknown", season, ep_num, audio

def is_similar(t1, t2):
    stop_words = {'the', 'a', 'an', 'of', 'and', 'in', 'to', 'with', 'for', 'is', 'at', 'on', 'part', 'season'}
    w1 = [x for x in re.sub(r'[^a-z0-9\s]', '', t1.lower()).split() if x not in stop_words]
    w2 = [x for x in re.sub(r'[^a-z0-9\s]', '', t2.lower()).split() if x not in stop_words]
    if not w1 or not w2: return False
    s1, s2 = set(w1), set(w2)
    intersection = s1.intersection(s2)
    if min(len(s1), len(s2)) == 0: return False
    return (len(intersection) / min(len(s1), len(s2))) >= 0.70

def get_emoji(filename):
    ext = filename.split('.')[-1].lower() if '.' in filename else ''
    if ext == 'pdf': return '📕'
    if ext in ['cbz', 'cbr']: return '📗'
    if ext in ['mkv', 'mp4', 'avi']: return '🎬'
    return '📙'

# ==========================================
# 🌐 ANILIST 16:9 COVER (RANDOM PICKER)
# ==========================================
async def fetch_anilist_16x9(query, category="anime"):
    url = "https://graphql.anilist.co"
    media_type = "MANGA" if category == "manga" else "ANIME"
    graphql_query = "query ($search: String, $type: MediaType) { Media (search: $search, type: $type) { title { english romaji } bannerImage coverImage { extraLarge } averageScore format status episodes chapters genres description startDate { year } } }"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={'query': graphql_query, 'variables': {"search": query, "type": media_type}}) as resp:
                data = await resp.json()
                if 'data' in data and data['data']['Media']: return data['data']['Media']
    except Exception: pass
    return None

# ==========================================
# 🔍 AUTO FILTER (GROUP SUPPORT + 70% MATCH + SEASONS)
# ==========================================
async def auto_filter(client, msg, req_cat=None):
    if msg.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        if hasattr(ProObito, 'is_group_approved') and not await ProObito.is_group_approved(msg.chat.id): 
            return
            
    search = msg.text.lower()
    if len(search) < 2 or len(search) > 100: return
    
    m = await msg.reply_text(f'**🔎 Searching Database...** `{search}`')
    search_clean = re.sub(r"[:-]", "", search.replace("-", " ")).strip()
    
    stop_words = {'the', 'a', 'an', 'of', 'and', 'in', 'to', 'with', 'for', 'is', 'at', 'on', 'part'}
    search_words = [w for w in search_clean.split() if w.lower() not in stop_words and len(w) > 2]
    if not search_words: search_words = [search_clean]
        
    regex_queries = [{"file_name": {"$regex": w, "$options": "i"}} for w in search_words]
    query = {"$or": regex_queries}
    
    cursor1 = Media.find(query)
    cursor2 = Media2.find(query)
    files = await cursor1.to_list(length=3000) + await cursor2.to_list(length=3000)
    
    if not files: return await m.edit("<b>❌ No Anime/Manga found!</b>")

    key = f"{msg.chat.id}-{msg.id}"
    grouped_titles = {}
    
    for f in files:
        title, season, ep, aud = extract_file_info(f.file_name)
        is_manga = any(x in f.file_name.lower() for x in ['.pdf', '.cbz', '.cbr', 'manga', 'ch '])
        cat = "manga" if is_manga else "anime"
        
        if req_cat and cat != req_cat: continue
            
        found_key = None
        for existing_title in grouped_titles.keys():
            if is_similar(existing_title, title):
                found_key = existing_title
                break
                
        if not found_key:
            found_key = title
            grouped_titles[found_key] = {"category": cat, "seasons": {}}
            
        if season not in grouped_titles[found_key]["seasons"]:
            grouped_titles[found_key]["seasons"][season] = {"files": [], "seen_eps": set()}
            
        if ep not in grouped_titles[found_key]["seasons"][season]["seen_eps"]:
            grouped_titles[found_key]["seasons"][season]["files"].append((f, ep, aud))
            grouped_titles[found_key]["seasons"][season]["seen_eps"].add(ep)
            
    if not grouped_titles: return await m.edit(f"<b>❌ No {req_cat if req_cat else 'files'} found matching keywords!</b>")
        
    temp.SEARCHES[key] = grouped_titles
    titles = list(grouped_titles.keys())
    
    btn = []
    for i, title in enumerate(titles[:30]): 
        cat = grouped_titles[title]["category"]
        label = f"📚 {title}" if cat == "manga" else f"📺 {title}"
        btn.append([InlineKeyboardButton(label, callback_data=f"stitle#{key}#{i}")])
        
    btn.append([InlineKeyboardButton("❌ CLOSE", callback_data="close_data")])
    
    search_pic = None
    if titles:
        top_ani = await fetch_anilist_16x9(titles[0], grouped_titles[titles[0]]["category"])
        if top_ani:
            imgs = []
            if top_ani.get("bannerImage"): imgs.append(top_ani.get("bannerImage"))
            if top_ani.get("coverImage", {}).get("extraLarge"): imgs.append(top_ani.get("coverImage", {}).get("extraLarge"))
            if imgs: search_pic = random.choice(imgs)
            
    if not search_pic: search_pic = random.choice(PICS)

    cap = f"🎯 <b>SEARCH RESULTS</b> ❞\n\n▸ <b>QUERY:</b> {search_clean}\n▸ <b>RESULTS:</b> {len(titles)} MATCHES\n\n<i>SELECT AN ITEM TO VIEW SEASONS ↓</i>"
    await m.delete()
    await msg.reply_photo(photo=search_pic, caption=cap, reply_markup=InlineKeyboardMarkup(btn))

# ==========================================
# 📺 DETAILS (SEASON MENU)
# ==========================================
def safe_float(val):
    try: return float(val)
    except: return 0.0

@Client.on_callback_query(filters.regex(r"^stitle#"))
async def select_title_cb(client, query):
    try:
        _, key, index = query.data.split("#")
        grouped_titles = temp.SEARCHES.get(key)
        if not grouped_titles: return await query.answer("❌ Session Expired!", show_alert=True)
        
        titles = list(grouped_titles.keys())
        selected_title = titles[int(index)]
        title_data = grouped_titles[selected_title]
        cat = title_data["category"]
        
        anime_info = await fetch_anilist_16x9(selected_title, cat)
        if not anime_info: anime_info = {}
        
        anilist_title = anime_info.get('title', {})
        display_title = anilist_title.get('english') or anilist_title.get('romaji') or selected_title
        
        cover = None
        if anime_info:
            imgs = []
            if anime_info.get("bannerImage"): imgs.append(anime_info.get("bannerImage"))
            if anime_info.get("coverImage", {}).get("extraLarge"): imgs.append(anime_info.get("coverImage", {}).get("extraLarge"))
            if imgs: cover = random.choice(imgs)
        if not cover: cover = random.choice(PICS)
            
        atype = "Manhwa/Manga" if cat == "manga" else str(anime_info.get('format', 'TV Series')).replace('_',' ')
        status = anime_info.get('status', 'RELEASING').title()
        genres = ", ".join(anime_info.get('genres', ['Action', 'Fantasy'])[:3])
        synopsis = re.sub(r'<[^>]+>', '', str(anime_info.get('description', 'Synopsis not available.')))[:250] 
        
        cap = f"📚 <b>{display_title}</b> ❞\n┌──────────────────────\n✧ <b>Type:</b> {atype} | ✧ <b>Status:</b> {status}\n✶ <b>Genres:</b> {genres}\n⚟ <b>Synopsis:</b> {synopsis}...\n\n👇 **SELECT SEASON/VOLUME:**"
        
        btn = []
        seasons = sorted(list(title_data["seasons"].keys()))
        for s in seasons:
            eps_count = len(title_data["seasons"][s]["files"])
            s_text = "Chapters" if cat == "manga" else f"Season {s}"
            btn.append([InlineKeyboardButton(f"🎬 {s_text} ({eps_count} Eps/Ch)", callback_data=f"sseason#{key}#{index}#{s}#0")])
            
        safe_title = selected_title[:35]
        btn.append([InlineKeyboardButton("📁 ADD TO LIBRARY" if cat == "manga" else "⭐ ADD TO WATCHLIST", callback_data=f"addwatch#{safe_title}#{cat}")])
        btn.append([InlineKeyboardButton("🔙 BACK", callback_data=f"sback#{key}"), InlineKeyboardButton("❌ CLOSE", callback_data="close_data")])
        
        await query.message.edit_media(InputMediaPhoto(media=cover, caption=cap))
        await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
    except Exception:
        await query.answer("❌ Error processing details.", show_alert=True)

# ==========================================
# 🔢 GRID (EPISODES & AUDIO TAGS)
# ==========================================
@Client.on_callback_query(filters.regex(r"^sseason#"))
async def swatch_cb(client, query):
    try:
        _, key, index, season, offset = query.data.split("#")
        season = int(season)
        offset = int(offset)
        
        grouped_titles = temp.SEARCHES.get(key)
        if not grouped_titles: return await query.answer("❌ Session Expired!", show_alert=True)
        
        titles = list(grouped_titles.keys())
        selected_title = titles[int(index)]
        cat = grouped_titles[selected_title]["category"]
        files_data = grouped_titles[selected_title]["seasons"][season]["files"]
        total_eps = len(files_data)
        
        files_data.sort(key=lambda x: safe_float(x[1]))
        current_chunk = files_data[offset:offset+30]
        
        s_lbl = "" if cat == "manga" else f"[Season {season}]"
        cap = f"📚 <b>{selected_title} {s_lbl}</b> ❞\n\n<b>Select {'chapter' if cat == 'manga' else 'episode'}:</b>\n📕 <i>PDF</i> 📗 <i>CBZ</i> 🎬 <i>Video</i>"

        btn = []
        row = []
        bot_username = client.me.username if client.me else temp.U_NAME
        
        for f, ep_num, aud in current_chunk:
            fmt_ep = str(int(ep_num)) if ep_num == int(ep_num) else str(ep_num)
            icon = get_emoji(f.file_name)
            
            short_id = str(uuid.uuid4())[:10]
            if not hasattr(temp, 'FILES_CACHE'): temp.FILES_CACHE = {}
            temp.FILES_CACHE[short_id] = f.file_id
            
            # Add AUDIO Tag to Button
            lbl = f"{fmt_ep} {icon}"
            if aud: lbl = f"[{aud}] {lbl}"
            
            row.append(InlineKeyboardButton(lbl, url=f"https://t.me/{bot_username}?start=file_{short_id}"))
            if len(row) == 3:
                btn.append(row)
                row = []
        if row: btn.append(row)
        
        current_page, total_pages = (offset // 30) + 1, math.ceil(total_eps / 30) if total_eps > 0 else 1
        page_row = []
        if offset > 0: page_row.append(InlineKeyboardButton("⬅️ PREV", callback_data=f"sseason#{key}#{index}#{season}#{offset-30}"))
        page_row.append(InlineKeyboardButton(f"{current_page}/{total_pages}", callback_data="pages"))
        if total_eps > offset + 30: page_row.append(InlineKeyboardButton("NEXT ➡️", callback_data=f"sseason#{key}#{index}#{season}#{offset+30}"))
        if page_row: btn.append(page_row)
        
        btn.append([InlineKeyboardButton("📥 DOWNLOAD ALL", callback_data=f"downall#{key}#{index}#{season}#{offset}")])
        btn.append([InlineKeyboardButton("🔙 BACK", callback_data=f"stitle#{key}#{index}"), InlineKeyboardButton("❌ CLOSE", callback_data="close_data")])
        await query.message.edit_caption(caption=cap, reply_markup=InlineKeyboardMarkup(btn))
    except Exception:
        await query.answer("❌ Error processing grid.", show_alert=True)

# ==========================================
# 🔙 BACK & DOWNLOAD ALL (ACTUAL FILES)
# ==========================================
@Client.on_callback_query(filters.regex(r"^sback#"))
async def back_to_search(client, query):
    _, key = query.data.split("#")
    grouped_titles = temp.SEARCHES.get(key)
    if not grouped_titles: return await query.answer("❌ Session Expired!", show_alert=True)
    
    titles = list(grouped_titles.keys())
    btn = []
    for i, title in enumerate(titles[:30]):
        cat = grouped_titles[title]["category"]
        btn.append([InlineKeyboardButton(f"📚 {title}" if cat == "manga" else f"📺 {title}", callback_data=f"stitle#{key}#{i}")])
        
    btn.append([InlineKeyboardButton("❌ CLOSE", callback_data="close_data")])
    cap = f"🎯 <b>SEARCH RESULTS</b> ❞\n\n▸ <b>RESULTS:</b> {len(titles)} MATCHES\n\n<i>SELECT AN ITEM TO VIEW SEASONS ↓</i>"
    
    search_pic = None
    if titles:
        top_ani = await fetch_anilist_16x9(titles[0], grouped_titles[titles[0]]["category"])
        if top_ani:
            imgs = []
            if top_ani.get("bannerImage"): imgs.append(top_ani.get("bannerImage"))
            if top_ani.get("coverImage", {}).get("extraLarge"): imgs.append(top_ani.get("coverImage", {}).get("extraLarge"))
            if imgs: search_pic = random.choice(imgs)
    if not search_pic: search_pic = random.choice(PICS)

    await query.message.edit_media(InputMediaPhoto(media=search_pic, caption=cap))
    await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(btn))

@Client.on_callback_query(filters.regex(r"^downall#"))
async def downall_cb(bot, query):
    _, key, index, season, offset = query.data.split("#")
    season, offset = int(season), int(offset)
    grouped_titles = temp.SEARCHES.get(key)
    if not grouped_titles: return await query.answer("❌ Session Expired!", show_alert=True)
    
    titles = list(grouped_titles.keys())
    selected_title = titles[int(index)]
    files_data = grouped_titles[selected_title]["seasons"][season]["files"]
    files_data.sort(key=lambda x: safe_float(x[1]))
    current_chunk = files_data[offset:offset+30]
    
    await query.answer("Sending actual files to your PM... ⏳", show_alert=False)
    
    sent_msgs = []
    for f, ep, aud in current_chunk:
        try:
            m = await bot.send_cached_media(chat_id=query.from_user.id, file_id=f.file_id)
            sent_msgs.append(m)
            await asyncio.sleep(0.5)
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
            m = await bot.send_cached_media(chat_id=query.from_user.id, file_id=f.file_id)
            sent_msgs.append(m)
        except Exception: pass
        
    timer = await get_autodelete_time()
    stk_id = await get_sticker()
    
    if stk_id and sent_msgs:
        s_msg = await bot.send_sticker(query.from_user.id, stk_id)
        sent_msgs.append(s_msg)
        
    if timer > 0 and sent_msgs:
        search_link = f"getfile-{selected_title.replace(' ', '-')}"
        asyncio.create_task(auto_del_notification(bot, query.from_user.id, sent_msgs, timer, transfer=search_link))

@Client.on_callback_query(filters.regex(r"^close_data$"))
async def close_cb(bot, query):
    await query.message.delete()
    
