import os, json, logging, asyncio, string, aiohttp, datetime
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto

from database.watchlist_db import get_watchlist, get_random_pic, set_autodelete_time, get_autodelete_time, set_sticker, get_sticker, add_pic, remove_pic, get_all_pics
from database.ia_filterdb import Media, Media2
from database.users_chats_db import db
from plugins.pmfilter import auto_filter 
from info import *
from utils import temp

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)
BATCH_FILES = {}

# Default Fallback Images
DEF_BANNER = "https://graph.org/file/99eebf5dbe8a134f548e0.jpg"
OWNER_USERNAME = environ.get('OWNER_USERNAME', 'i_killed_my_clan')

async def auto_delete_task(messages, timer):
    await asyncio.sleep(timer)
    for msg in messages:
        try:
            if msg: await msg.delete()
        except: pass

# =========================================
# 🚀 SEARCH CATEGORY ROUTERS
# =========================================
@Client.on_message(filters.command(["search", "s"]))
async def search_all(client, message):
    if len(message.command) < 2: return await message.reply_text("<b>❌ Provide a name!\nExample:</b> `/search Naruto`")
    message.text = " ".join(message.command[1:])
    try: await auto_filter(client, message, req_cat=None) 
    except Exception as e: await message.reply_text(f"<b>❌ Error:</b> {e}")

@Client.on_message(filters.command(["anime"]))
async def search_anime(client, message):
    if len(message.command) < 2: return await message.reply_text("<b>❌ Provide an Anime name!</b>")
    message.text = " ".join(message.command[1:])
    try: await auto_filter(client, message, req_cat="anime") 
    except Exception as e: await message.reply_text(f"<b>❌ Error:</b> {e}")

@Client.on_message(filters.command(["manga"]))
async def search_manga(client, message):
    if len(message.command) < 2: return await message.reply_text("<b>❌ Provide a Manga name!</b>")
    message.text = " ".join(message.command[1:])
    try: await auto_filter(client, message, req_cat="manga") 
    except Exception as e: await message.reply_text(f"<b>❌ Error:</b> {e}")

# =========================================
# 🚀 START COMMAND (FILE DEEP LINK FIX)
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
        
        # 🔥 FIX: Sending specific file from Inline Button
        if data.startswith('file_'):
            file_id = data.split('_', 1)[1]
            try:
                sent_msg = await client.send_cached_media(chat_id=message.from_user.id, file_id=file_id)
                timer = await get_autodelete_time()
                stk_id = await get_sticker()
                stk_msg, warn_msg = None, None
                
                if stk_id: stk_msg = await client.send_sticker(message.from_user.id, stk_id)
                if timer > 0:
                    warn_msg = await message.reply(f"⚠️ **Note:** This file will be auto-deleted in {timer//60} minutes to prevent copyright issues.")
                    asyncio.create_task(auto_delete_task([sent_msg, stk_msg, warn_msg], timer))
            except Exception as e:
                await message.reply(f"❌ Error sending file: Try searching manually.")
            return

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

            sent_msgs = []
            for msg in msgs:
                btn = [[InlineKeyboardButton('📌 ᴊᴏɪɴ ᴜᴘᴅᴀᴛᴇꜱ 📌', url=f"https://t.me/{OWNER_USERNAME}")]]
                try: 
                    m = await client.send_cached_media(chat_id=message.from_user.id, file_id=msg.get("file_id"), caption=msg.get("caption"), reply_markup=InlineKeyboardMarkup(btn))
                    sent_msgs.append(m)
                except FloodWait as e:
                    await asyncio.sleep(e.value + 1)
                    m = await client.send_cached_media(chat_id=message.from_user.id, file_id=msg.get("file_id"), caption=msg.get("caption"), reply_markup=InlineKeyboardMarkup(btn))
                    sent_msgs.append(m)
                await asyncio.sleep(1)
            await sts.delete()
            
            # Batch Auto Delete
            timer = await get_autodelete_time()
            stk_id = await get_sticker()
            stk_msg, warn_msg = None, None
            if stk_id and sent_msgs: stk_msg = await client.send_sticker(message.from_user.id, stk_id)
            if timer > 0 and sent_msgs:
                warn_msg = await message.reply(f"⚠️ **Note:** Above files will be auto-deleted in {timer//60} minutes.")
                asyncio.create_task(auto_delete_task(sent_msgs + [stk_msg, warn_msg], timer))
            return

    # NORMAL START MENU
    pic = await get_random_pic('start', DEF_BANNER)
    text = f"**Welcome to the Ultimate Anime & Manga Downloader, {message.from_user.first_name}! 🌟**"
    buttons = InlineKeyboardMarkup([[InlineKeyboardButton("📺 Browse Anime", callback_data="browse_anime"), InlineKeyboardButton("📖 Browse Manga", callback_data="browse_manga")], [InlineKeyboardButton("🔍 Inline Search", switch_inline_query_current_chat=""), InlineKeyboardButton("🆘 Help Guide", callback_data="help")]])
    await message.reply_photo(photo=pic, caption=text, reply_markup=buttons)

@Client.on_callback_query(filters.regex(r"^start$"))
async def start_cb(client, query):
    pic = await get_random_pic('start', DEF_BANNER)
    text = f"**Welcome to the Ultimate Anime & Manga Downloader, {query.from_user.first_name}! 🌟**"
    buttons = InlineKeyboardMarkup([[InlineKeyboardButton("📺 Browse Anime", callback_data="browse_anime"), InlineKeyboardButton("📖 Browse Manga", callback_data="browse_manga")], [InlineKeyboardButton("🔍 Inline Search", switch_inline_query_current_chat=""), InlineKeyboardButton("🆘 Help Guide", callback_data="help")]])
    await query.message.edit_media(InputMediaPhoto(media=pic, caption=text))
    await query.message.edit_reply_markup(reply_markup=buttons)

# =========================================
# ⚙️ ADMIN ON-BOT SETTINGS (TIMER & STICKER)
# =========================================
@Client.on_message(filters.command("set_timer") & filters.user(ADMINS))
async def set_timer_cmd(client, message):
    if len(message.command) > 1 and message.command[1].isdigit():
        await set_autodelete_time(int(message.command[1]))
        await message.reply(f"✅ Auto-delete timer set to **{int(message.command[1]) // 60} minutes** ({message.command[1]} seconds).")
    else:
        await message.reply("⚠️ **Usage:** `/set_timer 300` (time in seconds, use 0 to disable)")

@Client.on_message(filters.command("set_sticker") & filters.user(ADMINS))
async def set_sticker_cmd(client, message):
    if message.reply_to_message and message.reply_to_message.sticker:
        await set_sticker(message.reply_to_message.sticker.file_id)
        await message.reply("✅ Sticker saved successfully! Bot will send this after sending files.")
    elif len(message.command) > 1 and message.command[1] == "off":
        await set_sticker(None)
        await message.reply("✅ Sticker disabled.")
    else:
        await message.reply("⚠️ **Usage:** Reply to a sticker with `/set_sticker` to set it.\nUse `/set_sticker off` to disable.")

# =========================================
# 🖼️ PICTURE MANAGEMENT UI (/pic)
# =========================================
@Client.on_message(filters.command("pic") & filters.user(ADMINS))
async def pic_manager(client, message):
    btn = [
        [InlineKeyboardButton("🚀 Start Pic", callback_data="pic_cat_start"), InlineKeyboardButton("🆘 Help Pic", callback_data="pic_cat_help")],
        [InlineKeyboardButton("🔍 Search Pic", callback_data="pic_cat_search"), InlineKeyboardButton("📅 Schedule Pics", callback_data="pic_menu_schedule")],
        [InlineKeyboardButton("❌ Close", callback_data="close_data")]
    ]
    await message.reply("<b>🖼️ Bot Picture Management</b>\n\nSelect a category to manage images:", reply_markup=InlineKeyboardMarkup(btn))

@Client.on_callback_query(filters.regex(r"^pic_menu_schedule$") & filters.user(ADMINS))
async def pic_schedule_menu(client, query):
    btn = [
        [InlineKeyboardButton("Main Schedule Menu", callback_data="pic_cat_schedule")],
        [InlineKeyboardButton("Monday", callback_data="pic_cat_monday"), InlineKeyboardButton("Tuesday", callback_data="pic_cat_tuesday")],
        [InlineKeyboardButton("Wednesday", callback_data="pic_cat_wednesday"), InlineKeyboardButton("Thursday", callback_data="pic_cat_thursday")],
        [InlineKeyboardButton("Friday", callback_data="pic_cat_friday"), InlineKeyboardButton("Saturday", callback_data="pic_cat_saturday")],
        [InlineKeyboardButton("Sunday", callback_data="pic_cat_sunday")],
        [InlineKeyboardButton("🔙 Back", callback_data="pic_main_menu")]
    ]
    await query.message.edit_text("<b>📅 Schedule Picture Management</b>\n\nSelect a day to set specific pictures:", reply_markup=InlineKeyboardMarkup(btn))

@Client.on_callback_query(filters.regex(r"^pic_main_menu$") & filters.user(ADMINS))
async def pic_main_menu(client, query):
    btn = [
        [InlineKeyboardButton("🚀 Start Pic", callback_data="pic_cat_start"), InlineKeyboardButton("🆘 Help Pic", callback_data="pic_cat_help")],
        [InlineKeyboardButton("🔍 Search Pic", callback_data="pic_cat_search"), InlineKeyboardButton("📅 Schedule Pics", callback_data="pic_menu_schedule")],
        [InlineKeyboardButton("❌ Close", callback_data="close_data")]
    ]
    await query.message.edit_text("<b>🖼️ Bot Picture Management</b>\n\nSelect a category to manage images:", reply_markup=InlineKeyboardMarkup(btn))

@Client.on_callback_query(filters.regex(r"^pic_cat_") & filters.user(ADMINS))
async def pic_manage_category(client, query):
    cat = query.data.replace("pic_cat_", "")
    pics = await get_all_pics(cat)
    text = f"<b>🖼️ Category: {cat.replace('_', ' ').title()}</b>\n\nTotal Images currently active: <b>{len(pics)}</b>\n\nChoose an action below:"
    btn = [[InlineKeyboardButton("➕ Add Image", callback_data=f"pic_add_{cat}")], [InlineKeyboardButton("➖ Remove Image", callback_data=f"pic_rem_{cat}")], [InlineKeyboardButton("🔙 Back", callback_data="pic_main_menu")]]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))

@Client.on_callback_query(filters.regex(r"^pic_add_") & filters.user(ADMINS))
async def add_pic_process(client, query):
    cat = query.data.replace("pic_add_", "")
    try:
        set_msg = await client.ask(chat_id=query.from_user.id, text=f"<b>Send me the direct Image URL (Telegra.ph or similar) to add for <code>{cat}</code></b>\n\n<i>Time limit: 60s</i>", timeout=60)
        url = set_msg.text.strip()
        if not url.startswith("http"): return await set_msg.reply("❌ Invalid URL!")
        await add_pic(cat, url)
        await set_msg.reply(f"✅ Image successfully added to <b>{cat}</b>!\nSend `/pic` to manage more.")
    except Exception:
        await client.send_message(query.from_user.id, "❌ Request Timeout.")

@Client.on_callback_query(filters.regex(r"^pic_rem_") & filters.user(ADMINS))
async def rem_pic_process(client, query):
    cat = query.data.replace("pic_rem_", "")
    pics = await get_all_pics(cat)
    if not pics: return await query.answer("❌ No images in this category to remove!", show_alert=True)
    text = f"<b>Images in {cat}:</b>\n\n"
    for i, p in enumerate(pics, 1): text += f"{i}. <a href='{p}'>Image {i}</a>\n"
    try:
        set_msg = await client.ask(chat_id=query.from_user.id, text=text + "\n<b>Send the Exact URL from above that you want to delete.</b>", timeout=60, disable_web_page_preview=True)
        await remove_pic(cat, set_msg.text.strip())
        await set_msg.reply(f"✅ Image removed from <b>{cat}</b>!\nSend `/pic` to manage more.")
    except Exception:
        await client.send_message(query.from_user.id, "❌ Request Timeout.")

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
    
    if not files: return await query.message.edit_caption(caption=f"<b>❌ No files found starting with '{letter}'</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"browse_{category}")]]))
    names = set()
    for f in files:
        clean_name = re.sub(r'\[.*?\]|\(.*?\)', '', f.file_name)
        clean_name = re.sub(r'\.(mkv|mp4|avi|mpe?g|pdf|cbz|cbr)$', '', clean_name, flags=re.IGNORECASE)
        clean_name = re.split(r'\s-\s|\sEp\s|\sE\d', clean_name)[0].replace(".", " ").replace("_", " ").strip()
        if clean_name and (letter == "num" or clean_name.upper().startswith(letter)): names.add(clean_name)
            
    text = f"<b>📁 Available titles starting with '{letter}'</b>\n\n"
    bot_username = client.me.username if client.me else temp.U_NAME
    for name in sorted(names)[:60]:
        safe_link = name.replace(" ", "-")
        text += f"▪️ <a href='https://t.me/{bot_username}?start=getfile-{safe_link}'>{name}</a>\n"
    await query.message.edit_caption(caption=text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"browse_{category}")]]), disable_web_page_preview=True)

# =========================================
# 🔍 HELP & REQUEST COMMANDS
# =========================================
@Client.on_message(filters.command("help"))
async def help_cmd(client, message):
    pic = await get_random_pic('help', DEF_BANNER)
    text = "**🤖 Bot Commands:**\n\n➤ `/search <name>` — Find Anime or Manga\n➤ `/anime <name>` — Find Anime ONLY\n➤ `/manga <name>` — Find Manga ONLY\n➤ `/ongoing` — Airing Anime\n➤ `/ongoing_manga` — Airing Manga\n➤ `/watchlist` — Saved Anime\n➤ `/library` — Saved Manga\n➤ `/todayschedule` — Today's schedule\n➤ `/request <name>` — Request add"
    await message.reply_photo(photo=pic, caption=text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Close", callback_data="close_data")]]))

@Client.on_callback_query(filters.regex(r"^help$"))
async def help_cb(client, query):
    pic = await get_random_pic('help', DEF_BANNER)
    text = "**🤖 Bot Commands:**\n\n➤ `/search <name>` — Find Anime or Manga\n➤ `/anime <name>` — Find Anime ONLY\n➤ `/manga <name>` — Find Manga ONLY\n➤ `/ongoing` — Airing Anime\n➤ `/ongoing_manga` — Airing Manga\n➤ `/watchlist` — Saved Anime\n➤ `/library` — Saved Manga\n➤ `/todayschedule` — Today's schedule\n➤ `/request <name>` — Request add"
    await query.message.edit_media(InputMediaPhoto(media=pic, caption=text))
    await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="start")]]))

@Client.on_message(filters.command("request") & filters.private)
async def request_cmd(client, message):
    if len(message.command) < 2: return await message.reply("⚠️ **Usage:** `/request <Anime/Manga Name>`")
    req_name = message.text.split(" ", 1)[1]
    text = f"**🆕 New Request:**\n\n**Name:** `{req_name}`\n**Requested By:** {message.from_user.mention} (`{message.from_user.id}`)"
    try:
        if INDEX_REQ_CHANNEL: await client.send_message(INDEX_REQ_CHANNEL, text)
        await message.reply(f"✅ Your request for **{req_name}** has been sent to the admins!")
    except Exception: await message.reply(f"✅ Request logged: **{req_name}**")

# ==========================================
# ⭐ WATCHLIST & LIBRARY
# ==========================================
@Client.on_message(filters.command("watchlist"))
async def watchlist_cmd(client, message):
    user_id = message.from_user.id
    saved_anime = await get_watchlist(user_id, "anime")
    if not saved_anime: return await message.reply("🥺 **Your Anime Watchlist is empty!**")
    text = "**📺 Your Saved Anime Watchlist:**\n\n"
    bot_username = client.me.username if client.me else temp.U_NAME
    for item in saved_anime:
        safe_link = item['title'].replace(" ", "-")
        text += f"▪️ <a href='https://t.me/{bot_username}?start=getfile-{safe_link}'>**{item['title']}**</a>\n\n"
    pic = await get_random_pic('start', DEF_BANNER)
    await message.reply_photo(photo=pic, caption=text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Close", callback_data="close_data")]]), disable_web_page_preview=True)

@Client.on_message(filters.command(["library", "readlist"]))
async def library_cmd(client, message):
    user_id = message.from_user.id
    saved_manga = await get_watchlist(user_id, "manga")
    if not saved_manga: return await message.reply("🥺 **Your Manga Library is empty!**")
    text = "**📚 Your Saved Manga & Manhwa:**\n\n"
    bot_username = client.me.username if client.me else temp.U_NAME
    for item in saved_manga:
        safe_link = item['title'].replace(" ", "-")
        text += f"▪️ <a href='https://t.me/{bot_username}?start=getfile-{safe_link}'>**{item['title']}**</a>\n\n"
    pic = await get_random_pic('start', DEF_BANNER)
    await message.reply_photo(photo=pic, caption=text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Close", callback_data="close_data")]]), disable_web_page_preview=True)

# ==========================================
# 📅 ONGOING 7-DAYS UI (DYNAMIC PICS ADDED)
# ==========================================
async def fetch_anilist_data(query, variables):
    url = 'https://graphql.anilist.co'
    headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={'query': query, 'variables': variables}, headers=headers) as resp:
                if resp.status == 200: return await resp.json()
    except Exception: pass
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
        [InlineKeyboardButton("Monday", callback_data=f"ongoing_{category}_Monday"), InlineKeyboardButton("Tuesday", callback_data=f"ongoing_{category}_Tuesday")],
        [InlineKeyboardButton("Wednesday", callback_data=f"ongoing_{category}_Wednesday"), InlineKeyboardButton("Thursday", callback_data=f"ongoing_{category}_Thursday")],
        [InlineKeyboardButton("Friday", callback_data=f"ongoing_{category}_Friday"), InlineKeyboardButton("Saturday", callback_data=f"ongoing_{category}_Saturday")],
        [InlineKeyboardButton("Sunday", callback_data=f"ongoing_{category}_Sunday")],
        [InlineKeyboardButton("❌ Close", callback_data="close_data")]
    ])

@Client.on_message(filters.command(["ongoing", "todayschedule", "schedule"]))
async def ongoing_anime_cmd(client, message):
    pic = await get_random_pic('schedule', DEF_BANNER)
    text = "**📅 Select a day to view the Anime Release Schedule:**"
    await message.reply_photo(photo=pic, caption=text, reply_markup=get_ongoing_keyboard("anime"))

@Client.on_message(filters.command("ongoing_manga"))
async def ongoing_manga_cmd(client, message):
    pic = await get_random_pic('schedule', DEF_BANNER)
    text = "**📅 Select a day to view Ongoing Manga:**"
    await message.reply_photo(photo=pic, caption=text, reply_markup=get_ongoing_keyboard("manga"))

@Client.on_callback_query(filters.regex(r"^ongoing_anime_"))
async def ongoing_anime_cb(client, query):
    day = query.data.split("_")[-1]
    await query.answer(f"Fetching {day} schedule...", show_alert=False)
    start_ts, end_ts = get_day_timestamps(day)
    graphql_query = '''query($start: Int, $end: Int) { Page(page: 1, perPage: 15) { airingSchedules(airingAt_greater: $start, airingAt_lesser: $end, sort: TIME) { episode media { title { english romaji } } } } }'''
    data = await fetch_anilist_data(graphql_query, {"start": start_ts, "end": end_ts})
    
    # 🔥 DYNAMIC PIC PER DAY
    pic = await get_random_pic(day.lower(), DEF_BANNER)
    
    if not data or 'data' not in data:
        return await query.message.edit_media(InputMediaPhoto(media=pic, caption="❌ Failed to fetch schedule."))
        
    schedule_list = data['data']['Page']['airingSchedules']
    text = f"📅 **Anime Airing on {day}:**\n\n"
    if not schedule_list: text += "❌ No major anime scheduled for this day."
    else:
        for item in schedule_list:
            t = item['media']['title']
            title = t.get('english') or t.get('romaji')
            text += f"⏰ **{title}** - Episode {item['episode']}\n"
            
    await query.message.edit_media(InputMediaPhoto(media=pic, caption=text))
    await query.message.edit_reply_markup(reply_markup=get_ongoing_keyboard("anime"))

@Client.on_callback_query(filters.regex(r"^ongoing_manga_"))
async def ongoing_manga_cb(client, query):
    day = query.data.split("_")[-1]
    await query.answer(f"Fetching {day} manga...", show_alert=False)
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    page_num = days.index(day) + 1 
    graphql_query = '''query($page: Int) { Page(page: $page, perPage: 15) { media(status: RELEASING, type: MANGA, sort: POPULARITY_DESC) { title { english romaji } chapters } } }'''
    data = await fetch_anilist_data(graphql_query, {"page": page_num})
    
    # 🔥 DYNAMIC PIC PER DAY
    pic = await get_random_pic(day.lower(), DEF_BANNER)
    
    if not data or 'data' not in data:
        return await query.message.edit_media(InputMediaPhoto(media=pic, caption="❌ Failed to fetch data."))
        
    manga_list = data['data']['Page']['media']
    text = f"📚 **Top Releasing Manga (Page {page_num} - {day}):**\n\n"
    for manga in manga_list:
        t = manga['title']
        title = t.get('english') or t.get('romaji')
        text += f"📖 **{title}** (Ch: {manga.get('chapters') or '?'})\n"
        
    await query.message.edit_media(InputMediaPhoto(media=pic, caption=text))
    await query.message.edit_reply_markup(reply_markup=get_ongoing_keyboard("manga"))
