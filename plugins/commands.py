import os
import re, sys
import json
import logging
import asyncio
import string
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database.ia_filterdb import Media, Media2
from database.users_chats_db import db
from .pmfilter import auto_filter 
from info import *
from utils import get_size, temp

# Anilist Fetcher (Agar available hai)
try:
    from plugins.anilist import fetch_anime_details as get_anime_info
except ImportError:
    get_anime_info = None

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)
BATCH_FILES = {}

# =========================================
# 🚀 START COMMAND (INSTANT - NO ANIMATION)
# =========================================
@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
    # GROUP START
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        buttons = [[
            InlineKeyboardButton('➕ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ᴄʜᴀᴛ ➕', url=f'http://t.me/{temp.U_NAME}?startgroup=true')
        ],[
            InlineKeyboardButton('👨‍💻 ᴏᴡɴᴇʀ', url=f"https://t.me/{OWNER_USERNAME}") 
        ]]
        await message.reply("<b>Bot is Active! Send any Anime name to search.</b>", reply_markup=InlineKeyboardMarkup(buttons))
        
        if not await db.get_chat(message.chat.id):
            await db.add_chat(message.chat.id, message.chat.title)
        return 
        
    # NEW USER ENTRY
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)
        
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
        
        # 🔴 FIX: Hardcoded image url instead of random.choice(PICS) to prevent crash
        image_url = "https://graph.org/file/99eebf5dbe8a134f548e0.jpg"
        
        await message.reply_photo(
            photo=image_url,
            caption=text,
            reply_markup=buttons
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
                await client.send_cached_media(
                    chat_id=message.from_user.id, file_id=msg.get("file_id"),
                    caption=f_caption, reply_markup=InlineKeyboardMarkup(btn)
                )
            except FloodWait as e:
                await asyncio.sleep(e.value)
                await client.send_cached_media(chat_id=message.from_user.id, file_id=msg.get("file_id"), caption=f_caption, reply_markup=InlineKeyboardMarkup(btn))
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
    
    await query.message.edit_caption(
        caption=f"<b>🗂️ {category.capitalize()} Alphabetical Index</b>\n\nSelect a starting letter to view available titles:", 
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex(r"^letter_(anime|manga)_"))
async def show_letter_results(client, query):
    _, category, letter = query.data.split("_")
    await query.answer("Fetching titles... ⏳", show_alert=False)
    
    regex_pattern = r"^[0-9]" if letter == "num" else f"^{letter}"
    
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
        if clean_name: names.add(clean_name)
            
    text = f"<b>📁 Available {category.capitalize()} starting with '{letter}'</b>\n\n"
    for name in sorted(names)[:50]:
        text += f"▪️ <code>{name}</code>\n"
        
    await query.message.edit_caption(
        caption=text, 
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"browse_{category}")]])
    )

# =========================================
# 🔍 SEARCH & REQUEST COMMANDS
# =========================================
@Client.on_message(filters.command(["search", "s"]))
async def search_anime_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply_text("<b>❌ Please provide an Anime/Manga name to search!</b>\n\nExample: `/search Naruto`")
        
    search_query = " ".join(message.command[1:])
    message.text = search_query 
    await auto_filter(client, message)

@Client.on_message(filters.command(["request", "req"]))
async def request_anime(client, message):
    if len(message.command) < 2:
        return await message.reply_text("<b>❌ Please provide an Anime/Manga name to request!</b>")
        
    search_query = " ".join(message.command[1:])
    if get_anime_info:
        anime_info = await get_anime_info(search_query)
        if anime_info:
            cap = f"📝 **Do you want to request this Anime/Manga?**\n\n🎬 **Name:** {anime_info.get('title', search_query)}\n🔢 **Episodes:** {anime_info.get('episodes', 'Unknown')}\n"
            btn = [[InlineKeyboardButton("✅ Yes, Request", callback_data=f"req_submit_{anime_info.get('id', search_query)}")], [InlineKeyboardButton("❌ Cancel", callback_data="close_data")]]
            cover_img = anime_info.get('cover_image')
            if cover_img: await message.reply_photo(photo=cover_img, caption=cap, reply_markup=InlineKeyboardMarkup(btn))
            else: await message.reply_text(cap, reply_markup=InlineKeyboardMarkup(btn))
            return

    btn = [[InlineKeyboardButton('✅ Submit Request', callback_data='req_submit_text'), InlineKeyboardButton('❌ Cancel', callback_data='close_data')]]
    await message.reply_text(f"<b>📝 ʀᴇǫᴜᴇꜱᴛ :</b> <u>{search_query}</u>\n\nDo you want to submit this to admins?", reply_markup=InlineKeyboardMarkup(btn))

@Client.on_message(filters.command("restart") & filters.user(ADMINS))
async def stop_button(bot, message):
    msg = await bot.send_message(text="<b><i>Restarting...</i></b>", chat_id=message.chat.id)       
    await asyncio.sleep(2)
    await msg.edit("<b><i><u>Bot Restarted</u> ✅</i></b>")
    os.execl(sys.executable, sys.executable, *sys.argv)
    
