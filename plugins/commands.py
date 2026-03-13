import os
import re, sys
import json
import logging
import asyncio
import string
import aiohttp
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.watchlist_db import get_watchlist
from database.ia_filterdb import Media, Media2
from database.users_chats_db import db
from plugins.pmfilter import auto_filter 
from info import *
from utils import get_size, temp

# Anilist Fetcher
try:
    from plugins.anilist import fetch_anime_details as get_anime_info
except ImportError:
    get_anime_info = None

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)
BATCH_FILES = {}

HELP_BANNER = "https://graph.org/file/99eebf5dbe8a134f548e0.jpg"
OWNER_USERNAME = "i_killed_my_clan"

# =========================================
# 🚀 START COMMAND & DEEP LINKS
# =========================================
@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        buttons = [[
            InlineKeyboardButton('➕ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ᴄʜᴀᴛ ➕', url=f'http://t.me/{temp.U_NAME}?startgroup=true')
        ]]
        await message.reply("<b>Bot is Active! Send any Anime name to search.</b>", reply_markup=InlineKeyboardMarkup(buttons))
        if not await db.get_chat(message.chat.id):
            await db.add_chat(message.chat.id, message.chat.title)
        return 
        
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)
        
    # 🔴 DEEP LINK HANDLING (This makes the A-Z list Clickable)
    if len(message.command) > 1:
        data = message.command[1]
        
        # When user clicks a name from the index list
        if data.startswith('getfile'):
            movies = data.split("-", 1)[1].replace('-', ' ')
            message.text = movies # Spoof message text to trigger search
            try:
                await auto_filter(client, message) 
            except Exception as e:
                await message.reply_text(f"<b>❌ Error searching:</b> {e}")
            return
            
        # Batch Files Handling
        if data.startswith("BATCH"):
            sts = await message.reply("<b>Please wait...</b>")
            file_id = data.split("-", 1)[1]
            msgs = BATCH_FILES.get(file_id)
            if not msgs:
                file = await client.download_media(file_id)
                try:
                    with open(file) as file_data:
                        msgs = json.loads(file_data.read())
                except:
                    return await sts.edit("FAILED TO OPEN BATCH FILE.")
                os.remove(file)
                BATCH_FILES[file_id] = msgs

            for msg in msgs:
                title = msg.get("title")
                f_caption = msg.get("caption", f"{title}")
                btn = [[InlineKeyboardButton('📌 ᴊᴏɪɴ ᴜᴘᴅᴀᴛᴇꜱ 📌', url=f"https://t.me/{OWNER_USERNAME}")]]
                try:
                    await client.send_cached_media(chat_id=message.from_user.id, file_id=msg.get("file_id"), caption=f_caption, reply_markup=InlineKeyboardMarkup(btn))
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    await client.send_cached_media(chat_id=message.from_user.id, file_id=msg.get("file_id"), caption=f_caption, reply_markup=InlineKeyboardMarkup(btn))
                await asyncio.sleep(1)
            await sts.delete()
            return

    # NORMAL START MENU
    text = (
        f"**Welcome to the Ultimate Anime & Manga Downloader, {message.from_user.first_name}! 🌟**\n\n"
        "Explore complete collections, ongoing series, and download instantly.\n"
        "Choose an option below to get started:"
    )
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📺 Browse Anime", callback_data="browse_anime"),
         InlineKeyboardButton("📖 Browse Manga", callback_data="browse_manga")],
        [InlineKeyboardButton("🔍 Inline Search", switch_inline_query_current_chat=""),
         InlineKeyboardButton("🆘 Help Guide", callback_data="help")],
        [InlineKeyboardButton("👨‍💻 Admin", url=f"https://t.me/{OWNER_USERNAME}")]
    ])
    
    await message.reply_photo(photo=HELP_BANNER, caption=text, reply_markup=buttons)

# =========================================
# 🔠 A-Z ALPHABETICAL INDEX CALLBACKS
# =========================================
@Client.on_callback_query(filters.regex(r"^start$"))
async def start_cb(client, query):
    text = f"**Welcome to the Ultimate Anime & Manga Downloader, {query.from_user.first_name}! 🌟**\n\nExplore complete collections, ongoing series, and download instantly."
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📺 Browse Anime", callback_data="browse_anime"),
         InlineKeyboardButton("📖 Browse Manga", callback_data="browse_manga")],
        [InlineKeyboardButton("🔍 Inline Search", switch_inline_query_current_chat=""),
         InlineKeyboardButton("🆘 Help Guide", callback_data="help")],
        [InlineKeyboardButton("👨‍💻 Admin", url=f"https://t.me/{OWNER_USERNAME}")]
    ])
    await query.message.edit_caption(caption=text, reply_markup=buttons)

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
        
    await query.message.edit_caption(caption=text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"browse_{category}")]]))

# =========================================
# 🔍 SEARCH & HELP COMMANDS
# =========================================
@Client.on_message(filters.command(["search", "s"]))
async def search_anime_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply_text("<b>❌ Provide an Anime/Manga name!\nExample:</b> `/search Naruto`")
    
    query_text = " ".join(message.command[1:])
    message.text = query_text 
    
    try:
        await auto_filter(client, message)
    except Exception as e:
        await message.reply_text(f"<b>❌ Error:</b> {e}")

@Client.on_message(filters.command("help"))
async def help_cmd(client, message):
    text = (
        "**🤖 Bot Commands List:**\n\n"
        "➤ `/search <name>` — Find Anime or Manga\n"
        "➤ `/ongoing` — See currently airing Anime\n"
        "➤ `/ongoing_manga` — See currently releasing Manga\n"
        "➤ `/watchlist` — View your saved Anime\n"
        "➤ `/library` — View your saved Manga/Manhwa\n"
        "➤ `/todayschedule` — View today's anime release schedule\n"
        "➤ `/request <name>` — Request an anime/manga to be added\n"
    )
    btn = [[InlineKeyboardButton("❌ Close", callback_data="close_data")]]
    await message.reply_photo(photo=HELP_BANNER, caption=text, reply_markup=InlineKeyboardMarkup(btn))

@Client.on_message(filters.command("request") & filters.private)
async def request_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply("⚠️ **Usage:** `/request <Anime/Manga Name>`\n\nExample: `/request Solo Leveling`")
    
    req_name = message.text.split(" ", 1)[1]
    user = message.from_user
    
    text = f"**🆕 New Request:**\n\n**Name:** `{req_name}`\n**Requested By:** {user.mention} (`{user.id}`)"
    if INDEX_REQ_CHANNEL:
        await client.send_message(INDEX_REQ_CHANNEL, text)
    await message.reply(f"✅ Your request for **{req_name}** has been sent to the admins!")

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
    for item in saved_anime:
        title = item['title']
        text += f"▪️ **{title}**\n↳ 🔎 `/search {title}`\n\n"
        
    btn = [[InlineKeyboardButton("❌ Close", callback_data="close_data")]]
    await message.reply_photo(photo=HELP_BANNER, caption=text, reply_markup=InlineKeyboardMarkup(btn))

@Client.on_message(filters.command(["library", "readlist"]))
async def library_cmd(client, message):
    user_id = message.from_user.id
    saved_manga = await get_watchlist(user_id, "manga")
    
    if not saved_manga:
        return await message.reply("🥺 **Your Manga Library is empty!**\nSearch for manga and click **📁 ADD TO LIBRARY** to save them.")
        
    text = "**📚 Your Saved Manga & Manhwa:**\n\n"
    for item in saved_manga:
        title = item['title']
        text += f"▪️ **{title}**\n↳ 🔎 `/search {title}`\n\n"
        
    btn = [[InlineKeyboardButton("❌ Close", callback_data="close_data")]]
    await message.reply_photo(photo=HELP_BANNER, caption=text, reply_markup=InlineKeyboardMarkup(btn))

# ==========================================
# 🌐 100% FIXED ANILIST LIVE DATA ENGINE
# ==========================================
async def fetch_anilist_data(query, variables):
    url = 'https://graphql.anilist.co'
    # 🔥 THIS IS THE FIX: Added Browser Headers to bypass Anilist Blocks
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={'query': query, 'variables': variables}, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    logger.error(f"Anilist Error: {resp.status}")
                    return None
    except Exception as e:
        logger.error(f"Anilist Exception: {e}")
        return None

@Client.on_message(filters.command("ongoing"))
async def ongoing_anime_cmd(client, message):
    msg = await message.reply("🔄 Fetching live ongoing anime...")
    query = '''
    query { Page(page: 1, perPage: 15) { media(status: RELEASING, type: ANIME, sort: POPULARITY_DESC) { title { romaji } episodes } } }
    '''
    data = await fetch_anilist_data(query, {})
    if not data or 'data' not in data:
        return await msg.edit_text("❌ Failed to fetch data from Anilist. (API Blocked or Timeout)")
        
    anime_list = data['data']['Page']['media']
    text = "**🔥 Top 15 Ongoing Anime:**\n\n"
    for anime in anime_list:
        title = anime['title']['romaji']
        eps = anime.get('episodes') or "?"
        text += f"📺 **{title}** (Eps: {eps})\n"
        
    await msg.edit_text(text)

@Client.on_message(filters.command("ongoing_manga"))
async def ongoing_manga_cmd(client, message):
    msg = await message.reply("🔄 Fetching live ongoing manga...")
    query = '''
    query { Page(page: 1, perPage: 15) { media(status: RELEASING, type: MANGA, sort: POPULARITY_DESC) { title { romaji } chapters } } }
    '''
    data = await fetch_anilist_data(query, {})
    if not data or 'data' not in data:
        return await msg.edit_text("❌ Failed to fetch data from Anilist. (API Blocked or Timeout)")
        
    manga_list = data['data']['Page']['media']
    text = "**🔥 Top 15 Ongoing Manga/Manhwa:**\n\n"
    for manga in manga_list:
        title = manga['title']['romaji']
        chaps = manga.get('chapters') or "?"
        text += f"📚 **{title}** (Ch: {chaps})\n"
        
    await msg.edit_text(text)

@Client.on_message(filters.command(["todayschedule", "schedule"]))
async def todayschedule_cmd(client, message):
    msg = await message.reply("🔄 Fetching today's anime schedule...")
    import time
    current_time = int(time.time())
    query = '''
    query($start: Int, $end: Int) { Page(page: 1, perPage: 15) { airingSchedules(airingAt_greater: $start, airingAt_lesser: $end, sort: TIME) { episode media { title { romaji } } } } }
    '''
    variables = {"start": current_time, "end": current_time + 86400}
    data = await fetch_anilist_data(query, variables)
    
    if not data or 'data' not in data:
        return await msg.edit_text("❌ Failed to fetch schedule from Anilist. (API Blocked or Timeout)")
        
    schedule_list = data['data']['Page']['airingSchedules']
    if not schedule_list:
        return await msg.edit_text("❌ No major anime releasing today.")
        
    text = "**📅 Today's Anime Schedule:**\n\n"
    for item in schedule_list:
        title = item['media']['title']['romaji']
        ep = item['episode']
        text += f"⏰ **{title}** - Episode {ep}\n"
        
    await msg.edit_text(text)
                   
