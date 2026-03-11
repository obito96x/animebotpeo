import os
import re, sys
import json
import logging
import asyncio
import string
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database.ia_filterdb import Media
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
    
    image_url = "https://graph.org/file/99eebf5dbe8a134f548e0.jpg"
    await message.reply_photo(photo=image_url, caption=text, reply_markup=buttons)

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
    cursor = Media.find({"file_name": {"$regex": regex_pattern, "$options": "i"}, "category": category})
    files = await cursor.to_list(length=300) # Fetch up to 300 to ensure we get good coverage
    
    if not files:
        return await query.message.edit_caption(caption=f"<b>❌ No files found starting with '{letter}'</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"browse_{category}")]]))
        
    names = set()
    for f in files:
        # 🔥 ADVANCED CLEANER: Removes [Erai-raws], (1080p), .mkv, and episode numbers like "- 01"
        clean_name = re.sub(r'\[.*?\]|\(.*?\)', '', f.file_name)
        clean_name = re.sub(r'\.(mkv|mp4|avi|mpe?g)$', '', clean_name, flags=re.IGNORECASE)
        clean_name = re.split(r'\s-\s|\sEp\s|\sE\d', clean_name)[0]
        clean_name = clean_name.replace(".", " ").replace("_", " ").strip()
        
        # Double check letter matches (to avoid tags messing up order)
        if clean_name and (letter == "num" or clean_name.upper().startswith(letter)):
            names.add(clean_name)
            
    # Sort names alphabetically
    sorted_names = sorted(names)
    text = f"<b>📁 Available titles starting with '{letter}'</b>\n\n"
    
    bot_username = client.me.username if client.me else temp.U_NAME
    
    for name in sorted_names[:60]: # Limit to 60 distinct anime to avoid message length limits
        safe_link = name.replace(" ", "-")
        # 🔥 CLICK TO SEARCH MAGIC: Creates a deep link that auto searches the anime
        text += f"▪️ <a href='https://t.me/{bot_username}?start=getfile-{safe_link}'>{name}</a>\n"
        
    await query.message.edit_caption(caption=text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"browse_{category}")]]))

# =========================================
# 🔍 SEARCH COMMAND FIX
# =========================================
@Client.on_message(filters.command(["search", "s"]))
async def search_anime_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply_text("<b>❌ Provide an Anime/Manga name!\nExample:</b> `/search Naruto`")
    
    # Send the correct search string to the engine
    query_text = " ".join(message.command[1:])
    message.text = query_text 
    
    try:
        await auto_filter(client, message)
    except Exception as e:
        await message.reply_text(f"<b>❌ Error:</b> {e}")
        
