import os, json, logging, asyncio, string, aiohttp, datetime
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database.watchlist_db import get_watchlist
from database.ia_filterdb import Media, Media2
from database.users_chats_db import db
from plugins.pmfilter import auto_filter 
from info import *
from utils import temp

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)
BATCH_FILES = {}

# 🖼️ Yahan apni pasand ki image laga lena
HELP_BANNER = "https://graph.org/file/99eebf5dbe8a134f548e0.jpg"
ONGOING_ANIME_BANNER = "https://graph.org/file/99eebf5dbe8a134f548e0.jpg"
ONGOING_MANGA_BANNER = "https://graph.org/file/99eebf5dbe8a134f548e0.jpg"
OWNER_USERNAME = environ.get('OWNER_USERNAME', 'i_killed_my_clan')

# =========================================
# 🚀 SEARCH CATEGORY ROUTERS
# =========================================
@Client.on_message(filters.command(["search", "s"]))
async def search_all(client, message):
    if len(message.command) < 2:
        return await message.reply_text("<b>❌ Provide a name!\nExample:</b> `/search Naruto`")
    message.text = " ".join(message.command[1:])
    try: await auto_filter(client, message, req_cat=None) # Searches both
    except Exception as e: await message.reply_text(f"<b>❌ Error:</b> {e}")

@Client.on_message(filters.command(["anime"]))
async def search_anime(client, message):
    if len(message.command) < 2:
        return await message.reply_text("<b>❌ Provide an Anime name!\nExample:</b> `/anime Naruto`")
    message.text = " ".join(message.command[1:])
    try: await auto_filter(client, message, req_cat="anime") # ONLY Anime
    except Exception as e: await message.reply_text(f"<b>❌ Error:</b> {e}")

@Client.on_message(filters.command(["manga"]))
async def search_manga(client, message):
    if len(message.command) < 2:
        return await message.reply_text("<b>❌ Provide a Manga name!\nExample:</b> `/manga Solo Leveling`")
    message.text = " ".join(message.command[1:])
    try: await auto_filter(client, message, req_cat="manga") # ONLY Manga
    except Exception as e: await message.reply_text(f"<b>❌ Error:</b> {e}")


# =========================================
# 🚀 START & BASIC COMMANDS
# =========================================
@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        btn = [[InlineKeyboardButton('➕ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ᴄʜᴀᴛ ➕', url=f'http://t.me/{temp.U_NAME}?startgroup=true')]]
        await message.reply("<b>Bot is Active! Send any Anime name to search.</b>", reply_markup=InlineKeyboardMarkup(btn))
        return 
        
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)
        
    if len(message.command) > 1:
        data = message.command[1]
        if data.startswith('getfile'):
            message.text = data.split("-", 1)[1].replace('-', ' ') 
            try: await auto_filter(client, message) 
            except Exception as e: await message.reply_text(f"<b>❌ Error searching:</b> {e}")
            return
            
        if data.startswith("BATCH"):
            sts = await message.reply("<b>Please wait...⏳</b>")
            file_id = data.split("-", 1)[1]
            msgs = BATCH_FILES.get(file_id)
            if not msgs:
                file = await client.download_media(file_id)
                with open(file) as f: msgs = json.loads(f.read())
                os.remove(file)
                BATCH_FILES[file_id] = msgs

            for msg in msgs:
                btn = [[InlineKeyboardButton('📌 ᴊᴏɪɴ ᴜᴘᴅᴀᴛᴇꜱ 📌', url=f"https://t.me/{OWNER_USERNAME}")]]
                try: await client.send_cached_media(chat_id=message.from_user.id, file_id=msg.get("file_id"), caption=msg.get("caption"), reply_markup=InlineKeyboardMarkup(btn))
                except FloodWait as e:
                    await asyncio.sleep(e.value + 1)
                    await client.send_cached_media(chat_id=message.from_user.id, file_id=msg.get("file_id"), caption=msg.get("caption"), reply_markup=InlineKeyboardMarkup(btn))
                await asyncio.sleep(1)
            await sts.delete()
            return

    text = f"**Welcome to the Ultimate Anime & Manga Downloader, {message.from_user.first_name}! 🌟**\n\nChoose an option below to get started:"
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📺 Browse Anime", callback_data="browse_anime"),
         InlineKeyboardButton("📖 Browse Manga", callback_data="browse_manga")],
        [InlineKeyboardButton("🔍 Inline Search", switch_inline_query_current_chat=""),
         InlineKeyboardButton("🆘 Help Guide", callback_data="help")]
    ])
    await message.reply_photo(photo=HELP_BANNER, caption=text, reply_markup=buttons)

@Client.on_callback_query(filters.regex(r"^start$"))
async def start_cb(client, query):
    text = f"**Welcome to the Ultimate Anime & Manga Downloader, {query.from_user.first_name}! 🌟**"
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📺 Browse Anime", callback_data="browse_anime"), InlineKeyboardButton("📖 Browse Manga", callback_data="browse_manga")],
        [InlineKeyboardButton("🔍 Inline Search", switch_inline_query_current_chat=""), InlineKeyboardButton("🆘 Help Guide", callback_data="help")]
    ])
    await query.message.edit_caption(caption=text, reply_markup=buttons)

# =========================================
# 🔠 A-Z ALPHABETICAL INDEX CALLBACKS
# =========================================
@Client.on_callback_query(filters.regex(r"^browse_(anime|manga)$"))
async def browse_callback(client, query):
    category = query.data.split("_")[1]
    buttons = []
    row = []
    for letter in string.ascii_uppercase:
        row.append(InlineKeyboardButton(letter, callback_data=f"letter_{category}_{letter}"))
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row: buttons.append(row)
    buttons.append([InlineKeyboardButton("0-9 (Numbers)", callback_data=f"letter_{category}_num")])
    buttons.append([InlineKeyboardButton("🔙 Back to Home", callback_data="start")])
    
    await query.message.edit_caption(caption=f"<b>🗂️ {category.capitalize()} Alphabetical Index</b>\n\nSelect a starting letter:", reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^letter_(anime|manga)_"))
async def show_letter_results(client, query):
    _, category, letter = query.data.split("_")
    await query.answer("Fetching titles... ⏳", show_alert=False)
    
    regex_pattern = r"^[0-9]" if letter == "num" else f"^{letter}"
    cursor1 = Media.find({"file_name": {"$regex": regex_pattern, "$options": "i"}, "category": category})
    cursor2 = Media2.find({"file_name": {"$regex": regex_pattern, "$options": "i"}, "category": category})
    
    files = await cursor1.to_list(length=300) + await cursor2.to_list(length=300)
    
    if not files:
        return await query.message.edit_caption(caption=f"<b>❌ No files found starting with '{letter}'</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"browse_{category}")]]))
        
    names = set()
    for f in files:
        clean_name = re.sub(r'\[.*?\]|\(.*?\)', '', f.file_name)
        clean_name = re.sub(r'\.(mkv|mp4|avi|mpe?g|pdf|cbz|cbr)$', '', clean_name, flags=re.IGNORECASE)
        clean_name = re.split(r'\s-\s|\sEp\s|\sE\d', clean_name)[0]
        clean_name = clean_name.replace(".", " ").replace("_", " ").strip()
        
        if clean_name and (letter == "num" or clean_name.upper().startswith(letter)):
            names.add(clean_name)
            
    sorted_names = sorted(names)
    text = f"<b>📁 Available titles starting with '{letter}'</b>\n\n"
    bot_username = client.me.username if client.me else temp.U_NAME
    
    for name in sorted_names[:60]:
        safe_link = name.replace(" ", "-")
        text += f"▪️ <a href='https://t.me/{bot_username}?start=getfile-{safe_link}'>{name}</a>\n"
        
    await query.message.edit_caption(caption=text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"browse_{category}")]]), disable_web_page_preview=True)

# =========================================
# 🔍 HELP & REQUEST COMMANDS
# =========================================
@Client.on_message(filters.command("help"))
async def help_cmd(client, message):
    text = "**🤖 Bot Commands:**\n\n➤ `/search <name>` — Find Anime or Manga\n➤ `/anime <name>` — Find Anime ONLY\n➤ `/manga <name>` — Find Manga ONLY\n➤ `/ongoing` — Airing Anime\n➤ `/ongoing_manga` — Airing Manga\n➤ `/watchlist` — Saved Anime\n➤ `/library` — Saved Manga\n➤ `/todayschedule` — Today's schedule\n➤ `/request <name>` — Request add"
    await message.reply_photo(photo=HELP_BANNER, caption=text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Close", callback_data="close_data")]]))

@Client.on_message(filters.command("request") & filters.private)
async def request_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply("⚠️ **Usage:** `/request <Anime/Manga Name>`\n\nExample: `/request Solo Leveling`")
    
    req_name = message.text.split(" ", 1)[1]
    text = f"**🆕 New Request:**\n\n**Name:** `{req_name}`\n**Requested By:** {message.from_user.mention} (`{message.from_user.id}`)"
    
    try:
        if INDEX_REQ_CHANNEL:
            await client.send_message(INDEX_REQ_CHANNEL, text)
        await message.reply(f"✅ Your request for **{req_name}** has been sent to the admins!")
    except Exception:
        await message.reply(f"✅ Request logged: **{req_name}**")

# ==========================================
# ⭐ WATCHLIST & LIBRARY
# ==========================================
@Client.on_message(filters.command("watchlist"))
async def watchlist_cmd(client, message):
    user_id = message.from_user.id
    saved_anime = await get_watchlist(user_id, "anime")
    if not saved_anime:
        return await message.reply("🥺 **Your Anime Watchlist is empty!**\nSearch for anime and click **⭐ ADD TO WATCHLIST** to save them.")
        
    text = "**📺 Your Saved Anime Watchlist:**\n\n"
    bot_username = client.me.username if client.me else temp.U_NAME
    for item in saved_anime:
        safe_link = item['title'].replace(" ", "-")
        text += f"▪️ <a href='https://t.me/{bot_username}?start=getfile-{safe_link}'>**{item['title']}**</a>\n\n"
    
    btn = [[InlineKeyboardButton("❌ Close", callback_data="close_data")]]
    await message.reply_photo(photo=HELP_BANNER, caption=text, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)

@Client.on_message(filters.command(["library", "readlist"]))
async def library_cmd(client, message):
    user_id = message.from_user.id
    saved_manga = await get_watchlist(user_id, "manga")
    if not saved_manga:
        return await message.reply("🥺 **Your Manga Library is empty!**\nSearch for manga and click **📁 ADD TO LIBRARY** to save them.")
        
    text = "**📚 Your Saved Manga & Manhwa:**\n\n"
    bot_username = client.me.username if client.me else temp.U_NAME
    for item in saved_manga:
        safe_link = item['title'].replace(" ", "-")
        text += f"▪️ <a href='https://t.me/{bot_username}?start=getfile-{safe_link}'>**{item['title']}**</a>\n\n"
        
    btn = [[InlineKeyboardButton("❌ Close", callback_data="close_data")]]
    await message.reply_photo(photo=HELP_BANNER, caption=text, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)


# ==========================================
# 📅 ONGOING 7-DAYS UI (ANIME & MANGA)
# ==========================================
async def fetch_anilist_data(query, variables):
    url = 'https://graphql.anilist.co'
    headers = {
        "Content-Type": "application/json", 
        "Accept": "application/json", 
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={'query': query, 'variables': variables}, headers=headers) as resp:
                if resp.status == 200: return await resp.json()
    except Exception as e:
        logger.error(f"Anilist API Error: {e}")
    return None

def get_day_timestamps(day_name):
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    today = datetime.datetime.now()
    target_idx = days.index(day_name)
    current_idx = today.weekday()
    diff = target_idx - current_idx
    target_date = today + datetime.timedelta(days=diff)
    start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + datetime.timedelta(days=1)
    return int(start_of_day.timestamp()), int(end_of_day.timestamp())

def get_ongoing_keyboard(category):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Monday", callback_data=f"ongoing_{category}_Monday"), 
         InlineKeyboardButton("Tuesday", callback_data=f"ongoing_{category}_Tuesday")],
        [InlineKeyboardButton("Wednesday", callback_data=f"ongoing_{category}_Wednesday"), 
         InlineKeyboardButton("Thursday", callback_data=f"ongoing_{category}_Thursday")],
        [InlineKeyboardButton("Friday", callback_data=f"ongoing_{category}_Friday"), 
         InlineKeyboardButton("Saturday", callback_data=f"ongoing_{category}_Saturday")],
        [InlineKeyboardButton("Sunday", callback_data=f"ongoing_{category}_Sunday")],
        [InlineKeyboardButton("❌ Close", callback_data="close_data")]
    ])

@Client.on_message(filters.command(["ongoing", "todayschedule", "schedule"]))
async def ongoing_anime_cmd(client, message):
    text = "**📅 Select a day to view the Anime Release Schedule:**"
    await message.reply_photo(photo=ONGOING_ANIME_BANNER, caption=text, reply_markup=get_ongoing_keyboard("anime"))

@Client.on_message(filters.command("ongoing_manga"))
async def ongoing_manga_cmd(client, message):
    text = "**📅 Select a day to view Ongoing Manga:**\n\n*(Note: Manga doesn't have a fixed exact day schedule, so this shows top ongoing series paginated by day!)*"
    await message.reply_photo(photo=ONGOING_MANGA_BANNER, caption=text, reply_markup=get_ongoing_keyboard("manga"))

@Client.on_callback_query(filters.regex(r"^ongoing_anime_"))
async def ongoing_anime_cb(client, query):
    day = query.data.split("_")[-1]
    await query.answer(f"Fetching Anime schedule for {day}...", show_alert=False)
    
    start_ts, end_ts = get_day_timestamps(day)
    # 🔥 FETCHING ENGLISH TITLES 🔥
    graphql_query = '''
    query($start: Int, $end: Int) { Page(page: 1, perPage: 15) { airingSchedules(airingAt_greater: $start, airingAt_lesser: $end, sort: TIME) { episode media { title { english romaji } } } } }
    '''
    data = await fetch_anilist_data(graphql_query, {"start": start_ts, "end": end_ts})
    
    if not data or 'data' not in data:
        return await query.message.edit_caption("❌ Failed to fetch schedule from Anilist.", reply_markup=get_ongoing_keyboard("anime"))
        
    schedule_list = data['data']['Page']['airingSchedules']
    if not schedule_list:
        text = f"📅 **Anime Airing on {day}:**\n\n❌ No major anime scheduled for this day."
    else:
        text = f"📅 **Anime Airing on {day}:**\n\n"
        for item in schedule_list:
            title_dict = item['media']['title']
            title = title_dict.get('english') or title_dict.get('romaji')
            ep = item['episode']
            text += f"⏰ **{title}** - Episode {ep}\n"
            
    await query.message.edit_caption(caption=text, reply_markup=get_ongoing_keyboard("anime"))

@Client.on_callback_query(filters.regex(r"^ongoing_manga_"))
async def ongoing_manga_cb(client, query):
    day = query.data.split("_")[-1]
    await query.answer(f"Fetching Manga for {day}...", show_alert=False)
    
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    page_num = days.index(day) + 1 
    
    # 🔥 FETCHING ENGLISH TITLES 🔥
    graphql_query = '''
    query($page: Int) { Page(page: $page, perPage: 15) { media(status: RELEASING, type: MANGA, sort: POPULARITY_DESC) { title { english romaji } chapters } } }
    '''
    data = await fetch_anilist_data(graphql_query, {"page": page_num})
    
    if not data or 'data' not in data:
        return await query.message.edit_caption("❌ Failed to fetch data from Anilist.", reply_markup=get_ongoing_keyboard("manga"))
        
    manga_list = data['data']['Page']['media']
    text = f"📚 **Top Releasing Manga (Page {page_num} - {day}):**\n\n"
    for manga in manga_list:
        title_dict = manga['title']
        title = title_dict.get('english') or title_dict.get('romaji')
        chaps = manga.get('chapters') or "?"
        text += f"📖 **{title}** (Ch: {chaps})\n"
        
    await query.message.edit_caption(caption=text, reply_markup=get_ongoing_keyboard("manga"))

@Client.on_callback_query(filters.regex(r"^help$"))
async def help_cb(client, query):
    text = "**🤖 Bot Commands:**\n\n➤ `/search <name>` — Find Anime or Manga\n➤ `/anime <name>` — Find Anime ONLY\n➤ `/manga <name>` — Find Manga ONLY\n➤ `/ongoing` — Airing Anime\n➤ `/ongoing_manga` — Airing Manga\n➤ `/watchlist` — Saved Anime\n➤ `/library` — Saved Manga\n➤ `/todayschedule` — Today's schedule\n➤ `/request <name>` — Request add"
    await query.message.edit_caption(caption=text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="start")]]))
    
