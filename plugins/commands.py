import os
import re, sys
import json
import logging
import asyncio
import string
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database.ia_filterdb import Media  # Removed Media2 to prevent import error
from database.users_chats_db import db
from .pmfilter import auto_filter 
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

# Safe fallback for owner username
MY_OWNER = getattr(temp, 'U_NAME', 'i_killed_my_clan')

@Client.on_message(filters.command("ping"))
async def ping_cmd(client, message):
    await message.reply_text("<b>Pong! Bot is alive and working. 🚀</b>")

# =========================================
# 🚀 START COMMAND (SAFE MODE)
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
        
    if len(message.command) == 1:
        text = (
            f"**Welcome to the Ultimate Anime & Manga Downloader, {message.from_user.first_name}! 🌟**\n\n"
            "Explore complete collections, ongoing series, and download instantly.\n"
            "Choose an option below to get started:"
        )
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("📺 Browse Anime", callback_data="browse_anime"),
             InlineKeyboardButton("📖 Browse Manga", callback_data="browse_manga")],
            [InlineKeyboardButton("🔍 Inline Search", switch_inline_query_current_chat=""),
             InlineKeyboardButton("🆘 Help Guide", callback_data="help")]
        ])
        
        image_url = "https://graph.org/file/99eebf5dbe8a134f548e0.jpg"
        await message.reply_photo(photo=image_url, caption=text, reply_markup=buttons)
        return

    # Deep Links
    data = message.command[1]
    if data.startswith('getfile'):
        movies = data.split("-", 1)[1].replace('-', ' ')
        message.text = movies 
        await auto_filter(client, message) 
        return

# =========================================
# 🔠 A-Z ALPHABETICAL INDEX CALLBACKS
# =========================================
@Client.on_callback_query(filters.regex(r"^start$"))
async def start_cb(client, query):
    text = f"**Welcome to the Ultimate Anime & Manga Downloader, {query.from_user.first_name}! 🌟**"
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📺 Browse Anime", callback_data="browse_anime"),
         InlineKeyboardButton("📖 Browse Manga", callback_data="browse_manga")],
        [InlineKeyboardButton("🔍 Inline Search", switch_inline_query_current_chat=""),
         InlineKeyboardButton("🆘 Help Guide", callback_data="help")]
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
    
    await query.message.edit_caption(caption=f"<b>🗂️ {category.capitalize()} Alphabetical Index</b>", reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^letter_(anime|manga)_"))
async def show_letter_results(client, query):
    _, category, letter = query.data.split("_")
    await query.answer("Fetching titles... ⏳", show_alert=False)
    
    regex_pattern = r"^[0-9]" if letter == "num" else f"^{letter}"
    cursor1 = Media.find({"file_name": {"$regex": regex_pattern, "$options": "i"}, "category": category})
    files = await cursor1.to_list(length=100)
    
    if not files:
        return await query.message.edit_caption(caption=f"<b>❌ No files found starting with '{letter}'</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"browse_{category}")]]))
        
    names = set()
    for f in files:
        clean_name = re.sub(r'\[.*?\]|\(.*?\)', '', f.file_name).replace(".", " ").replace("_", " ").split('-')[0].strip()
        if clean_name: names.add(clean_name)
            
    text = f"<b>📁 Available titles starting with '{letter}'</b>\n\n"
    for name in sorted(names)[:50]:
        text += f"▪️ <code>{name}</code>\n"
        
    await query.message.edit_caption(caption=text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"browse_{category}")]]))

@Client.on_message(filters.command(["search", "s"]))
async def search_anime_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply_text("<b>❌ Provide a name! Example: `/search Naruto`</b>")
    message.text = " ".join(message.command[1:]) 
    await auto_filter(client, message)
    msg = await bot.send_message(text="<b><i>Restarting...</i></b>", chat_id=message.chat.id)       
    await asyncio.sleep(2)
    await msg.edit("<b><i><u>Bot Restarted</u> ✅</i></b>")
    os.execl(sys.executable, sys.executable, *sys.argv)
    
