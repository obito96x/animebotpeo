import os, json, logging, asyncio, string, aiohttp, datetime
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
import random

from database.watchlist_db import get_watchlist, set_autodelete_time, get_autodelete_time, set_sticker, get_sticker
from database.ia_filterdb import Media, Media2
from database.users_chats_db import db
from plugins.pmfilter import auto_filter 
from info import *
from utils import temp

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)
BATCH_FILES = {}
OWNER_USERNAME = environ.get('OWNER_USERNAME', 'i_killed_my_clan')

# 🔥 ROCK-SOLID PICS ARRAY
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

DEL_MSG = """<b>⚠️ Dᴜᴇ ᴛᴏ Cᴏᴘʏʀɪɢʜᴛ ɪssᴜᴇs....
<blockquote>Yᴏᴜʀ ғɪʟᴇs ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇᴅ ᴡɪᴛʜɪɴ <a href="https://t.me/{username}">{time}</a>. Sᴏ ᴘʟᴇᴀsᴇ ғᴏʀᴡᴀʀᴅ ᴛʜᴇᴍ ᴛᴏ ᴀɴʏ ᴏᴛʜᴇʀ ᴘʟᴀᴄᴇ ғᴏʀ ғᴜᴛᴜʀᴇ ᴀᴠᴀɪʟᴀʙɪʟɪᴛʏ.</blockquote></b>"""

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
# 🚀 START COMMAND & FILE DELIVERY FIX
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
        
        # 🔥 SINGLE FILE FIX: Fetching short UUID from Cache
        if data.startswith('file_'):
            short_id = data.split('_', 1)[1]
            if not hasattr(temp, 'FILES_CACHE'): temp.FILES_CACHE = {}
            file_id = temp.FILES_CACHE.get(short_id)
            
            if not file_id:
                return await message.reply("<b>❌ Link Expired!</b> Please search for the Anime/Manga again to get a fresh link.")
                
            try:
                sent_msg = await client.send_cached_media(chat_id=message.from_user.id, file_id=file_id)
                timer = await get_autodelete_time()
                stk_id = await get_sticker()
                stk_msg = None
                if stk_id: stk_msg = await client.send_sticker(message.from_user.id, stk_id)
                
                if timer > 0:
                    asyncio.create_task(auto_del_notification(client, message.from_user.id, [sent_msg, stk_msg], timer, transfer=f"file_{short_id}"))
            except Exception:
                await message.reply(f"❌ Error sending file.")
            return

        if data.startswith('getfile'):
            message.text = data.split("-", 1)[1].replace('-', ' ') 
            try: await auto_filter(client, message) 
            except Exception as e: await message.reply_text(f"<b>❌ Error searching:</b> {e}")
            return
            
        # 🟢 BATCH FILES HANDLING + VIP AUTO DELETE
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
            
            timer = await get_autodelete_time()
            stk_id = await get_sticker()
            if stk_id and sent_msgs: 
                s_msg = await client.send_sticker(message.from_user.id, stk_id)
                sent_msgs.append(s_msg)
            if timer > 0 and sent_msgs:
                asyncio.create_task(auto_del_notification(client, message.from_user.id, sent_msgs, timer, transfer=f"BATCH-{file_id}"))
            return

    # NORMAL START MENU
    text = f"**Welcome to the Ultimate Anime & Manga Downloader, {message.from_user.first_name}! 🌟**"
    buttons = InlineKeyboardMarkup([[InlineKeyboardButton("📺 Browse Anime", callback_data="browse_anime"), InlineKeyboardButton("📖 Browse Manga", callback_data="browse_manga")], [InlineKeyboardButton("🔍 Inline Search", switch_inline_query_current_chat=""), InlineKeyboardButton("🆘 Help Guide", callback_data="help")]])
    await message.reply_photo(photo=random.choice(PICS), caption=text, reply_markup=buttons)

@Client.on_callback_query(filters.regex(r"^start$"))
async def start_cb(client, query):
    text = f"**Welcome to the Ultimate Anime & Manga Downloader, {query.from_user.first_name}! 🌟**"
    buttons = InlineKeyboardMarkup([[InlineKeyboardButton("📺 Browse Anime", callback_data="browse_anime"), InlineKeyboardButton("📖 Browse Manga", callback_data="browse_manga")], [InlineKeyboardButton("🔍 Inline Search", switch_inline_query_current_chat=""), InlineKeyboardButton("🆘 Help Guide", callback_data="help")]])
    await query.message.edit_media(InputMediaPhoto(media=random.choice(PICS), caption=text))
    await query.message.edit_reply_markup(reply_markup=buttons)

# =========================================
# ⚙️ ADMIN ON-BOT SETTINGS (TIMER & STICKER)
# =========================================
@Client.on_message(filters.command("set_timer") & filters.user(ADMINS))
async def set_timer_cmd(client, message):
    if len(message.command) > 1 and message.command[1].isdigit():
        await set_autodelete_time(int(message.command[1]))
        await message.reply(f"✅ Auto-delete timer set to **{convert_time(int(message.command[1]))}**.")
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
    text = "**🤖 Bot Commands:**\n\n➤ `/search <name>` — Find Anime or Manga\n➤ `/anime <name>` — Find Anime ONLY\n➤ `/manga <name>` — Find Manga ONLY\n➤ `/ongoing` — Airing Anime\n➤ `/ongoing_manga` — Airing Manga\n➤ `/watchlist` — Saved Anime\n➤ `/library` — Saved Manga\n➤ `/todayschedule` — Today's schedule\n➤ `/request <name>` — Request add"
    await message.reply_photo(photo=random.choice(PICS), caption=text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Close", callback_data="close_data")]]))

@Client.on_callback_query(filters.regex(r"^help$"))
async def help_cb(client, query):
    text = "**🤖 Bot Commands:**\n\n➤ `/search <name>` — Find Anime or Manga\n➤ `/anime <name>` — Find Anime ONLY\n➤ `/manga <name>` — Find Manga ONLY\n➤ `/ongoing` — Airing Anime\n➤ `/ongoing_manga` — Airing Manga\n➤ `/watchlist` — Saved Anime\n➤ `/library` — Saved Manga\n➤ `/todayschedule` — Today's schedule\n➤ `/request <name>` — Request add"
    await query.message.edit_media(InputMediaPhoto(media=random.choice(PICS), caption=text))
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
    await message.reply_photo(photo=random.choice(PICS), caption=text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Close", callback_data="close_data")]]), disable_web_page_preview=True)

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
    await message.reply_photo(photo=random.choice(PICS), caption=text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Close", callback_data="close_data")]]), disable_web_page_preview=True)

# ==========================================
# 📅 ONGOING 7-DAYS UI 
# ==========================================
async def fetch_anilist_data(query, variables):
    url = 'https://graphql.anilist.co'
    headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "Mozilla/5.0"}
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
    text = "**📅 Select a day to view the Anime Release Schedule:**"
    await message.reply_photo(photo=random.choice(PICS), caption=text, reply_markup=get_ongoing_keyboard("anime"))

@Client.on_message(filters.command("ongoing_manga"))
async def ongoing_manga_cmd(client, message):
    text = "**📅 Select a day to view Ongoing Manga:**"
    await message.reply_photo(photo=random.choice(PICS), caption=text, reply_markup=get_ongoing_keyboard("manga"))

@Client.on_callback_query(filters.regex(r"^ongoing_anime_"))
async def ongoing_anime_cb(client, query):
    day = query.data.split("_")[-1]
    await query.answer(f"Fetching {day} schedule...", show_alert=False)
    start_ts, end_ts = get_day_timestamps(day)
    
    graphql_query = '''
    query($start: Int, $end: Int) { 
        Page(page: 1, perPage: 15) { 
            airingSchedules(airingAt_greater: $start, airingAt_lesser: $end, sort: TIME) { 
                episode
