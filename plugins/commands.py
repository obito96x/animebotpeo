import os
import re, sys
import json
import base64
import logging
import random
import asyncio
import string
import time
import pytz
from datetime import datetime
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup

from database.verify_db import vr_db
from .pmfilter import auto_filter 
from Script import script
from database.refer import referdb
from database.config_db import mdb
from database.ia_filterdb import Media, Media2, get_file_details, unpack_new_file_id, get_bad_files
from database.users_chats_db import db, delete_all_msg
from info import *
from utils import *
from database.connections_mdb import active_connection

# Anilist Fetcher (Agar available hai)
try:
    from plugins.anilist import fetch_anime_details as get_anime_info
except ImportError:
    get_anime_info = None

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

TIMEZONE = "Asia/Kolkata"
BATCH_FILES = {}

# --- HELPER FUNCTION ---
def get_greeting():
    curr_time = datetime.now(pytz.timezone(TIMEZONE)).hour        
    if curr_time < 12: return "ɢᴏᴏᴅ ᴍᴏʀɴɪɴɢ 👋" 
    elif curr_time < 17: return "ɢᴏᴏᴅ ᴀғᴛᴇʀɴᴏᴏɴ 👋" 
    elif curr_time < 21: return "ɢᴏᴏᴅ ᴇᴠᴇɴɪɴɢ 👋"
    else: return "ɢᴏᴏᴅ ɴɪɢʜᴛ 👋"

# =========================================
# 🚀 START COMMAND & DEEP LINKS
# =========================================
@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
    if EMOJI_MODE:    
        await message.react(emoji=random.choice(REACTIONS), big=True) 
        
    # GROUP START
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        buttons = [[
                    InlineKeyboardButton('➕ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ᴄʜᴀᴛ ➕', url=f'http://t.me/{temp.U_NAME}?startgroup=true')
                ],[
                    InlineKeyboardButton('👨‍💻 ᴏᴡɴᴇʀ', url=f"https://t.me/{OWNER_USERNAME}"),
                    InlineKeyboardButton('📢 ᴜᴘᴅᴀᴛᴇꜱ', url=f"https://t.me/{OWNER_USERNAME}") 
                ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply(script.GSTART_TXT.format(message.from_user.mention if message.from_user else message.chat.title, temp.U_NAME, temp.B_NAME), reply_markup=reply_markup, disable_web_page_preview=True)
        await asyncio.sleep(2) 
        if not await db.get_chat(message.chat.id):
            total=await client.get_chat_members_count(message.chat.id)
            await client.send_message(LOG_CHANNEL, script.LOG_TEXT_G.format(message.chat.title, message.chat.id, total, "Unknown"))       
            await db.add_chat(message.chat.id, message.chat.title)
        return 
        
    # NEW USER ENTRY
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)
        await client.send_message(LOG_CHANNEL, script.LOG_TEXT_P.format(message.from_user.id, message.from_user.mention))
        
    # PRIVATE START MENU (VIOLET BOT STYLE)
    if len(message.command) == 1:
        text = (
            f"**Welcome to the Ultimate Anime & Manga Downloader, {message.from_user.first_name}! 🌟**\n\n"
            "Explore complete collections, ongoing series, and download instantly.\n"
            "Choose an option below to get started:"
        )
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📺 Browse Anime", callback_data="browse_anime"),
                InlineKeyboardButton("📖 Browse Manga", callback_data="browse_manga")
            ],
            [
                InlineKeyboardButton("🔍 Inline Search", switch_inline_query_current_chat=""),
                InlineKeyboardButton("🆘 Help Guide", callback_data="help")
            ],
            [
                InlineKeyboardButton("👨‍💻 Admin", url=f"https://t.me/{OWNER_USERNAME}")
            ]
        ])
        
        await message.reply_photo(
            photo=random.choice(PICS),
            caption=text,
            reply_markup=buttons,
            parse_mode=enums.ParseMode.HTML
        )
        return

    # DEEP LINKS HANDLING (Files, Batch, GetFile)
    if len(message.command) == 2 and message.command[1].startswith('getfile'):
        movies = message.command[1].split("-", 1)[1] 
        movie = movies.replace('-',' ')
        message.text = movie 
        await auto_filter(client, message) 
        return
        
    data = message.command[1]
    try:
        pre, file_id = data.split('_', 1)
    except:
        file_id = data
        pre = ""

    if data.split("-", 1)[0] == "BATCH":
        sts = await message.reply("<b>Please wait...</b>")
        file_id = data.split("-", 1)[1]
        msgs = BATCH_FILES.get(file_id)
        if not msgs:
            file = await client.download_media(file_id)
            try:
                with open(file) as file_data:
                    msgs = json.loads(file_data.read())
            except:
                await sts.edit("FAILED")
                return await client.send_message(LOG_CHANNEL, "UNABLE TO OPEN FILE.")
            os.remove(file)
            BATCH_FILES[file_id] = msgs

        for msg in msgs:
            title = msg.get("title")
            size = get_size(int(msg.get("size", 0)))
            f_caption = msg.get("caption", f"{title}")

            btn = [[InlineKeyboardButton('📌 ᴊᴏɪɴ ᴜᴘᴅᴀᴛᴇꜱ 📌', url=f"https://t.me/{OWNER_USERNAME}")]]
            try:
                await client.send_cached_media(
                    chat_id=message.from_user.id, file_id=msg.get("file_id"),
                    caption=f_caption, protect_content=msg.get('protect', False),
                    reply_markup=InlineKeyboardMarkup(btn)
                )
            except FloodWait as e:
                await asyncio.sleep(e.value)
                await client.send_cached_media(
                    chat_id=message.from_user.id, file_id=msg.get("file_id"),
                    caption=f_caption, protect_content=msg.get('protect', False),
                    reply_markup=InlineKeyboardMarkup(btn)
                )
            except Exception as e:
                logger.warning(e, exc_info=True)
            await asyncio.sleep(1)
        await sts.delete()
        return

# =========================================
# 🔠 A-Z ALPHABETICAL INDEX CALLBACKS
# =========================================
@Client.on_callback_query(filters.regex(r"^start$"))
async def start_cb(client, query):
    text = (
        f"**Welcome to the Ultimate Anime & Manga Downloader, {query.from_user.first_name}! 🌟**\n\n"
        "Explore complete collections, ongoing series, and download instantly.\n"
        "Choose an option below to get started:"
    )
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📺 Browse Anime", callback_data="browse_anime"),
            InlineKeyboardButton("📖 Browse Manga", callback_data="browse_manga")
        ],
        [
            InlineKeyboardButton("🔍 Inline Search", switch_inline_query_current_chat=""),
            InlineKeyboardButton("🆘 Help Guide", callback_data="help")
        ],
        [
            InlineKeyboardButton("👨‍💻 Admin", url=f"https://t.me/{OWNER_USERNAME}")
        ]
    ])
    await query.message.edit_caption(caption=text, reply_markup=buttons, parse_mode=enums.ParseMode.HTML)

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
    if row:
        buttons.append(row)
        
    buttons.append([InlineKeyboardButton("0-9 (Numbers)", callback_data=f"letter_{category}_num")])
    buttons.append([InlineKeyboardButton("🔙 Back to Home", callback_data="start")])
    
    await query.message.edit_caption(
        caption=f"<b>🗂️ {category.capitalize()} Alphabetical Index</b>\n\nSelect a starting letter to view available titles:", 
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex(r"^letter_(anime|manga)_"))
async def show_letter_results(client, query):
    _, category, letter = query.data.split("_")
    await query.answer("Fetching titles... ⏳", show_alert=False)
    
    regex_pattern = r"^[0-9]" if letter == "num" else f"^{letter}"
    
    # Query specific category from existing database (Anime ya Manga)
    cursor1 = Media.find({"file_name": {"$regex": regex_pattern, "$options": "i"}, "category": category})
    cursor2 = Media2.find({"file_name": {"$regex": regex_pattern, "$options": "i"}, "category": category})
    
    files = await cursor1.to_list(length=100) + await cursor2.to_list(length=100)
    
    if not files:
        return await query.message.edit_caption(
            caption=f"<b>❌ No {category.capitalize()} found starting with '{letter}'</b>", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"browse_{category}")]])
        )
        
    names = set()
    for f in files:
        clean_name = re.sub(r'\[.*?\]|\(.*?\)', '', f.file_name)
        clean_name = clean_name.replace(".", " ").replace("_", " ").split('-')[0].strip()
        if clean_name:
            names.add(clean_name)
            
    text = f"<b>📁 Available {category.capitalize()} starting with '{letter}'</b>\n\n"
    # Copy karne ke liye mono format use kar rahe hain
    for name in sorted(names)[:50]:
        text += f"▪️ <code>{name}</code>\n"
        
    await query.message.edit_caption(
        caption=text, 
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"browse_{category}")]])
    )

# =========================================
# 🔍 SEARCH COMMAND (ANILIST INTEGRATED)
# =========================================
@Client.on_message(filters.command(["search", "s"]))
async def search_anime_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply_text("<b>❌ Please provide an Anime/Manga name to search!</b>\n\nExample: `/search Naruto`")
        
    search_query = " ".join(message.command[1:])
    message.text = search_query 
    
    # Call the AniList integrated filter directly from pmfilter.py
    await auto_filter(client, message)

# =========================================
# 📥 REQUEST COMMAND (ANILIST INTEGRATED)
# =========================================
@Client.on_message(filters.command(["request", "req"]))
async def request_anime(client, message):
    if len(message.command) < 2:
        return await message.reply_text("<b>❌ Please provide an Anime/Manga name to request!</b>\n\nExample: `/request Solo Leveling`")
        
    search_query = " ".join(message.command[1:])
    
    if get_anime_info:
        anime_info = await get_anime_info(search_query)
        if anime_info:
            cap = f"📝 **Do you want to request this Anime/Manga?**\n\n"
            cap += f"🎬 **Name:** {anime_info.get('title', search_query)}\n"
            cap += f"🔢 **Episodes:** {anime_info.get('episodes', 'Unknown')}\n"
            
            btn = [[
                InlineKeyboardButton("✅ Yes, Request", callback_data=f"req_submit_{anime_info.get('id', search_query)}"),
                InlineKeyboardButton("❌ Cancel", callback_data="close_data")
            ]]
            
            cover_img = anime_info.get('cover_image')
            if cover_img:
                await message.reply_photo(photo=cover_img, caption=cap, reply_markup=InlineKeyboardMarkup(btn))
            else:
                await message.reply_text(cap, reply_markup=InlineKeyboardMarkup(btn))
            return

    btn = [[
        InlineKeyboardButton('✅ Submit Request', callback_data=f'req_submit_text'),
        InlineKeyboardButton('❌ Cancel', callback_data='close_data')
    ]]
    await message.reply_text(f"<b>📝 ʀᴇǫᴜᴇꜱᴛ :</b> <u>{search_query}</u>\n\nDo you want to submit this to admins?", reply_markup=InlineKeyboardMarkup(btn))

# =========================================
# ⚙️ ADMIN & SETTINGS COMMANDS
# =========================================
@Client.on_message(filters.command('settings'))
async def settings(client, message):
    userid = message.from_user.id if message.from_user else None
    if not userid: return
    chat_type = message.chat.type

    if chat_type == enums.ChatType.PRIVATE:
        grpid = await active_connection(str(userid))
        if grpid is not None:
            grp_id = grpid
            chat = await client.get_chat(grpid)
            title = chat.title
        else:
            return await message.reply_text("ɪ'ᴍ ɴᴏᴛ ᴄᴏɴɴᴇᴄᴛᴇᴅ ᴛᴏ ᴀɴʏ ɢʀᴏᴜᴘ !", quote=True)
    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        grp_id = message.chat.id
        title = message.chat.title
    else:
        return

    st = await client.get_chat_member(grp_id, userid)
    if st.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER] and str(userid) not in ADMINS:
        return
    
    settings = await get_settings(grp_id)
    
    try:
        from utils import get_settings_buttons
        reply_markup = InlineKeyboardMarkup(get_settings_buttons(settings, grp_id))
    except:
        return await message.reply_text("Error: get_settings_buttons helper not found in utils.py")

    if chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        btn = [[
                InlineKeyboardButton("👤 ᴏᴘᴇɴ ɪɴ ᴘʀɪᴠᴀᴛᴇ ᴄʜᴀᴛ 👤", callback_data=f"opnsetpm#{grp_id}")
              ],[
                InlineKeyboardButton("👥 ᴏᴘᴇɴ ʜᴇʀᴇ 👥", callback_data=f"opnsetgrp#{grp_id}")
              ]]
        await message.reply_text("<b>ᴡʜᴇʀᴇ ᴅᴏ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴏᴘᴇɴ ꜱᴇᴛᴛɪɴɢꜱ ᴍᴇɴᴜ ? ⚙️</b>", reply_markup=InlineKeyboardMarkup(btn), reply_to_message_id=message.id)
    else:
        await message.reply_text(f"<b>ᴄʜᴀɴɢᴇ ʏᴏᴜʀ ꜱᴇᴛᴛɪɴɢꜱ ꜰᴏʀ {title} ⚙</b>", reply_markup=reply_markup, reply_to_message_id=message.id)

@Client.on_message(filters.command("restart") & filters.user(ADMINS))
async def stop_button(bot, message):
    msg = await bot.send_message(text="<b><i>ʙᴏᴛ ɪꜱ ʀᴇꜱᴛᴀʀᴛɪɴɢ...</i></b>", chat_id=message.chat.id)       
    await asyncio.sleep(3)
    await msg.edit("<b><i><u>ʙᴏᴛ ɪꜱ ʀᴇꜱᴛᴀʀᴛᴇᴅ</u> ✅</i></b>")
    os.execl(sys.executable, sys.executable, *sys.argv)

@Client.on_message(filters.command("deletefiles") & filters.user(ADMINS))
async def deletemultiplefiles(bot, message):
    if message.chat.type != enums.ChatType.PRIVATE:
        return await message.reply_text("<b>Works only in PM!</b>")
    try:
        keyword = message.text.split(" ", 1)[1]
    except:
        return await message.reply_text("<b>Give me a keyword to delete files.</b>")
    
    k = await bot.send_message(chat_id=message.chat.id, text=f"<b>Fetching Files for {keyword}...</b>")
    files, total = await get_bad_files(keyword)
    await k.delete()
    
    btn = [[
       InlineKeyboardButton("⚠️ Yes, Continue ! ⚠️", callback_data=f"killfilesdq#{keyword}")
       ],[
       InlineKeyboardButton("❌ No, Abort ! ❌", callback_data="close_data")
    ]]
    await message.reply_text(f"<b>Found {total} files for '{keyword}' !\n\nDo you want to delete?</b>", reply_markup=InlineKeyboardMarkup(btn))
    
