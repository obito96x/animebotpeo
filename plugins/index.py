import logging
import asyncio
import re
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait
from pyrogram.errors.exceptions.bad_request_400 import ChannelInvalid, ChatAdminRequired, UsernameInvalid, UsernameNotModified
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from info import ADMINS, INDEX_REQ_CHANNEL as LOG_CHANNEL
from database.ia_filterdb import save_file, Media, Media2
from utils import temp

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
lock = asyncio.Lock()

# Dictionary to store ongoing conversation state for adding channels
ADD_CHANNEL_CONVERSATION = {}

# ==========================================
# 🧠 PRO REGEX CLEANER (MANGA & ANIME)
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
    (re.compile(r'^S(\d{2})E(\d{2,4})$', re.IGNORECASE), (1, 2)),
    (re.compile(r'^S(\d{2})\s*-\s*E(\d{2,4})$', re.IGNORECASE), (1, 2))
]

def extract_file_info(filename, fallback_index=0, category="anime"):
    season = "1"
    episode = str(fallback_index)
    
    clean_title = re.sub(r'\.(mkv|mp4|avi|mpe?g|pdf|cbz|cbr|zip|rar|jpg|jpeg|png)$', '', filename, flags=re.IGNORECASE)
    clean_title = re.sub(r'\[.*?\]|\(.*?\)', '', clean_title)
    
    if category == "manga":
        match = re.search(r'(?i)(?:Chapter|Ch|Chap|Vol|Volume)\s*(\d+(?:\.\d+)?)', filename)
        if match:
            episode = match.group(1)
            m = re.search(r'(?i)(?:Chapter|Ch|Chap|Vol|Volume)\s*\d+(?:\.\d+)?', clean_title)
            if m: clean_title = clean_title[:m.start()]
        else:
            match = re.search(r'(?i)\s-\s(\d+(?:\.\d+)?)$', clean_title)
            if match:
                episode = match.group(1)
                clean_title = clean_title[:match.start()]
            else:
                match = re.search(r'\s(\d+(?:\.\d+)?)$', clean_title)
                if match:
                    episode = match.group(1)
                    clean_title = clean_title[:match.start()]
    else:
        for pattern, (s_idx, e_idx) in SEASON_EPISODE_PATTERNS:
            match = pattern.search(filename)
            if match:
                if s_idx is not None:
                    try: season = str(int(match.group(s_idx)))
                    except: pass
                if e_idx is not None:
                    try: episode = str(int(match.group(e_idx)))
                    except: pass
                m = pattern.search(clean_title)
                if m: clean_title = clean_title[:m.start()]
                break

    lower_name = filename.lower()
    qual = "Normal"
    if re.search(r'\b(2160p|4k)\b', lower_name): qual = "4K"
    elif re.search(r'\b1080p\b', lower_name): qual = "1080p"
    elif re.search(r'\b720p\b', lower_name): qual = "720p"
    elif re.search(r'\b480p\b', lower_name): qual = "480p"
    
    clean_title = clean_title.replace(".", " ").replace("_", " ")
    tags = r'\b(mkv|mp4|avi|hd|1080p|720p|480p|4k|webrip|web-dl|amzn|x265|x264|hevc|hindi|english|dual|audio|dubbed|subbed)\b'
    clean_title = re.sub(tags, '', clean_title, flags=re.IGNORECASE)
    clean_title = re.sub(r'[-–—~]\s*$', '', clean_title.strip()).strip()
    clean_title = " ".join(clean_title.split())
    if not clean_title: clean_title = "Unknown"
    
    return clean_title.title(), season, episode, qual

# ==========================================
# 🗑️ DELETE CHANNEL DB COMMAND
# ==========================================
@Client.on_message(filters.command("delchnl") & filters.user(ADMINS))
async def delete_channel_db(bot, message):
    if len(message.command) < 2:
        return await message.reply("⚠️ **How to use:**\n`/delchnl -10012345678`\n\n(Replace the number with your channel ID)")
    
    try: 
        chat_id = int(message.command[1])
    except ValueError: 
        return await message.reply("⚠️ Invalid Chat ID! Must be a number.")

    msg = await message.reply("🗑 Deleting files from database... Please wait.")
    
    res1 = await Media.collection.delete_many({"chat_id": chat_id})
    res2 = await Media2.collection.delete_many({"chat_id": chat_id})
    total = res1.deleted_count + res2.deleted_count

    await msg.edit(f"✅ **Successfully deleted {total} files** belonging to `{chat_id}` from the database.")

# ==========================================
# ⚙️ ADMIN INDEX PANEL COMMANDS & CALLBACKS
# ==========================================
@Client.on_message(filters.command("index") & filters.user(ADMINS))
async def index_admin_panel(bot: Client, message):
    await send_index_panel(message)

async def send_index_panel(message):
    anime_count = await Media.collection.count_documents({"category": "anime"}) + await Media2.collection.count_documents({"category": "anime"})
    manga_count = await Media.collection.count_documents({"category": "manga"}) + await Media2.collection.count_documents({"category": "manga"})
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Chnl", callback_data="idx_add_chnl"),
         InlineKeyboardButton("🗑 Delete Chnl", callback_data="idx_del_menu")],
        [InlineKeyboardButton("📡 Index Chnls", callback_data="idx_list_chnls")],
        [InlineKeyboardButton("🎬 Anime Indexlist", callback_data="idx_list_titles_anime"),
         InlineKeyboardButton("📚 Manga Indexlist", callback_data="idx_list_titles_manga")],
        [InlineKeyboardButton("🔄 Refresh", callback_data="idx_refresh"),
         InlineKeyboardButton("❌ Close", callback_data="idx_close")]
    ])
    
    text = (
        "**⚙️ Admin Index Management Panel**\n\n"
        f"🎬 **Anime Database:** {anime_count} Files\n"
        f"📚 **Manga Database:** {manga_count} Files\n\n"
        "Select an option below to manage your indexed channels."
    )
    
    if isinstance(message, CallbackQuery):
        await message.message.edit_text(text, reply_markup=keyboard)
    else:
        await message.reply_text(text, reply_markup=keyboard)

@Client.on_callback_query(filters.regex(r'^idx_') & filters.user(ADMINS))
async def admin_panel_callbacks(bot: Client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id

    # Add Channel
    if data == "idx_add_chnl":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎬 Anime", callback_data="idx_category_anime"),
             InlineKeyboardButton("📚 Manga", callback_data="idx_category_manga")],
            [InlineKeyboardButton("🔙 Back", callback_data="idx_back")]
        ])
        await query.message.edit_text("Select the category for the new channel:", reply_markup=keyboard)

    elif data.startswith("idx_category_"):
        category = data.split("_")[2]
        ADD_CHANNEL_CONVERSATION[user_id] = {"category": category}
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="idx_add_chnl"),
             InlineKeyboardButton("❌ Close", callback_data="idx_close")]
        ])
        await query.message.edit_text(
            f"**Step 2: Add {category.capitalize()} Channel**\n\n"
            f"1. Make sure I am an admin in the channel.\n"
            f"2. ⚠️ **Forward the LATEST (Newest) file/photo** from the channel here to start indexing the full channel backwards.",
            reply_markup=keyboard
        )

    # List Indexed Channels
    elif data == "idx_list_chnls":
        await query.answer("Fetching Channels...", show_alert=False)
        chat_ids1 = await Media.collection.distinct("chat_id")
        chat_ids2 = await Media2.collection.distinct("chat_id")
        all_chats = set(chat_ids1 + chat_ids2)
        
        text = "**📡 Indexed Channels:**\n\n"
        if not all_chats or all_chats == {0} or all_chats == {None}: 
            text += "No channels found."
        else:
            for cid in all_chats:
                if cid and cid != 0: 
                    clean_id = str(cid).replace('-100', '')
                    text += f"▪️ <a href='https://t.me/c/{clean_id}/1'>ID: {cid}</a>\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="idx_back")]
        ])            
        await query.message.edit_text(text, reply_markup=keyboard, disable_web_page_preview=True)

    # 🔥 INLINE DELETE MENU
    elif data == "idx_del_menu":
        await query.answer("Loading Delete Menu...", show_alert=False)
        chat_ids1 = await Media.collection.distinct("chat_id")
        chat_ids2 = await Media2.collection.distinct("chat_id")
        all_chats = list(set(chat_ids1 + chat_ids2))
        
        if not all_chats or all_chats == [0] or all_chats == [None]: 
            await query.answer("No channels found to delete!", show_alert=True)
            return

        buttons = []
        for cid in all_chats[:50]: # Safely show up to 50 channels
            if cid and cid != 0: 
                buttons.append([InlineKeyboardButton(f"🗑 Delete Channel: {cid}", callback_data=f"idx_drop_{cid}")])
        
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data="idx_back")])
        
        await query.message.edit_text(
            "⚠️ **WARNING: Click a channel below to PERMANENTLY delete all its files from the database.**",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    # 🔥 ACTUAL DELETE ACTION
    elif data.startswith("idx_drop_"):
        chat_id = int(data.split("_")[2])
        await query.answer(f"Deleting {chat_id}...", show_alert=False)
        
        res1 = await Media.collection.delete_many({"chat_id": chat_id})
        res2 = await Media2.collection.delete_many({"chat_id": chat_id})
        total = res1.deleted_count + res2.deleted_count
        
        await query.answer(f"✅ Deleted {total} files from {chat_id}!", show_alert=True)
        await send_index_panel(query) # Return to home after delete

    # List Indexed Titles
    elif data.startswith("idx_list_titles_"):
        cat = data.split("_")[3]
        await query.answer(f"Fetching {cat.capitalize()} List...", show_alert=False)
        
        titles1 = await Media.collection.distinct("clean_title", {"category": cat})
        titles2 = await Media2.collection.distinct("clean_title", {"category": cat})
        all_titles = list(set(titles1 + titles2))
        
        text = f"**🗂️ Indexed {cat.capitalize()} Titles:**\n\n"
        if not all_titles or all_titles == ["Unknown"]:
            text += f"No {cat} found in DB."
        else:
            bot_username = bot.me.username if bot.me else temp.U_NAME
            for title in sorted(all_titles)[:80]:
                if title and title != "Unknown": 
                    safe_link = title.replace(" ", "-")
                    text += f"▪️ <a href='https://t.me/{bot_username}?start=getfile-{safe_link}'>{title}</a>\n"
            if len(all_titles) > 80:
                text += f"\n*...and {len(all_titles) - 80} more.*"
                
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="idx_back")]]), disable_web_page_preview=True)

    elif data == "idx_back" or data == "idx_refresh":
        if user_id in ADD_CHANNEL_CONVERSATION: del ADD_CHANNEL_CONVERSATION[user_id]
        if data == "idx_refresh": await query.answer("Refreshed!", show_alert=False)
        await send_index_panel(query)

    elif data == "idx_close":
        if user_id in ADD_CHANNEL_CONVERSATION: del ADD_CHANNEL_CONVERSATION[user_id]
        await query.message.delete()

# ==========================================
# 📥 INDEXING REQUEST HANDLERS (FORWARD / LINK)
# ==========================================
@Client.on_message((filters.forwarded | (filters.regex(r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")) & filters.text ) & filters.private & filters.incoming)
async def send_for_index(bot, message):
    user_id = message.from_user.id
    category = "anime" 
    if user_id in ADD_CHANNEL_CONVERSATION:
        category = ADD_CHANNEL_CONVERSATION[user_id]["category"]
        del ADD_CHANNEL_CONVERSATION[user_id]

    if message.text:
        regex = re.compile(r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")
        match = regex.match(message.text)
        if not match: return await message.reply('Invalid link')
        chat_id = match.group(4)
        last_msg_id = int(match.group(5))
        if chat_id.isnumeric(): chat_id  = int(("-100" + chat_id))
    elif message.forward_from_chat.type == enums.ChatType.CHANNEL:
        last_msg_id = message.forward_from_message_id
        chat_id = message.forward_from_chat.username or message.forward_from_chat.id
    else: return

    try: await bot.get_chat(chat_id)
    except: return await message.reply('This may be a private channel. Make me an admin!')

    if user_id in ADMINS:
        buttons = [
            [InlineKeyboardButton('Yes, Start Indexing', callback_data=f'index#accept#{chat_id}#{last_msg_id}#{user_id}#{category}')],
            [InlineKeyboardButton('Close', callback_data='idx_close')]
        ]
        return await message.reply(
            f'**Category:** {category.capitalize()}\n\n'
            f'Do you Want To Index This Channel?\n\n'
            f'Chat ID: <code>{chat_id}</code>\nForwarded Message ID: <code>{last_msg_id}</code>',
            reply_markup=InlineKeyboardMarkup(buttons))

# ==========================================
# 🔄 INDEXING PROCESS CALLBACK
# ==========================================
@Client.on_callback_query(filters.regex(r'^index#'))
async def index_files_callback(bot, query):
    if query.data.startswith('index_cancel'):
        temp.CANCEL = True
        return await query.answer("Cancelling Indexing")
        
    parts = query.data.split("#")
    if len(parts) == 6: _, action, chat, lst_msg_id, from_user, category = parts
    else: return

    if lock.locked(): return await query.answer('Wait until previous process complete.', show_alert=True)
    
    msg = query.message
    await query.answer('Processing...⏳', show_alert=True)
    await msg.edit(
        f"Starting Indexing for Category: **{category.capitalize()}**",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Cancel', callback_data='index_cancel')]])
    )
    try: chat = int(chat)
    except: chat = chat
        
    await index_files_to_db(int(lst_msg_id), chat, msg, bot, category)

# ==========================================
# 🚀 THE ULTIMATE BOT-SAFE INDEXING ENGINE
# ==========================================
async def index_files_to_db(lst_msg_id, chat, msg, bot, category="anime"):
    total_files = 0
    duplicate = 0
    errors = 0
    deleted = 0
    no_media = 0
    unsupported = 0
    
    async with lock:
        try:
            current = temp.CURRENT
            temp.CANCEL = False
            
            # Fetch message IDs from latest down to 1
            message_ids = list(range(lst_msg_id - current, 0, -1))
            
            # Fetch in chunks of 200 (Safe for Telegram Bots)
            for i in range(0, len(message_ids), 200):
                if temp.CANCEL: break
                chunk = message_ids[i:i+200]
                
                try:
                    messages = await bot.get_messages(chat, chunk)
                except FloodWait as e:
                    await asyncio.sleep(e.value + 1)
                    messages = await bot.get_messages(chat, chunk)
                except Exception as e:
                    logger.error(f"Failed to fetch chunk: {e}")
                    continue

                for message in messages:
                    if temp.CANCEL: break
                    current += 1
                    
                    if current % 100 == 0:
                        can = [[InlineKeyboardButton('Cancel', callback_data='index_cancel')]]
                        await msg.edit_text(
                            text=f"**Category:** {category.capitalize()}\nMessages checked: <code>{current}</code>\nSaved: <code>{total_files}</code>\nDuplicates: <code>{duplicate}</code>",
                            reply_markup=InlineKeyboardMarkup(can))
                            
                    if message.empty:
                        deleted += 1
                        continue
                    elif not message.media:
                        no_media += 1
                        continue
                    elif message.media not in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.AUDIO, enums.MessageMediaType.DOCUMENT, enums.MessageMediaType.PHOTO]:
                        unsupported += 1
                        continue
                        
                    media = getattr(message, message.media.value, None)
                    if not media:
                        unsupported += 1
                        continue
                    
                    # Extract file name safely for Manga Photos
                    filename = getattr(media, 'file_name', '')
                    if not filename:
                        if message.caption:
                            filename = message.caption.split('\n')[0][:80]
                        elif message.media == enums.MessageMediaType.PHOTO:
                            filename = f"Manga_Photo_Ch_{message.id}.jpg"
                        else:
                            filename = f"Unknown_File_{message.id}"
                    
                    title, season, episode, quality = extract_file_info(filename, current, category)
                    
                    media.file_type = message.media.value
                    media.category = category 
                    media.caption = message.caption
                    media.chat_id = chat
                    
                    media.clean_title = title
                    media.season = season
                    media.episode = episode
                    media.quality = quality
                    
                    aynav, vnay = await save_file(bot, media)
                    if aynav: total_files += 1
                    elif vnay == 0: duplicate += 1
                    elif vnay == 2: errors += 1
                    
        except Exception as e:
            logger.exception(e)
            await msg.edit(f'Error: {e}')
        else:
            await msg.edit(f'Successfully saved <code>{total_files}</code> files to {category.capitalize()} dataBase!\nDuplicate Files Skipped: <code>{duplicate}</code>\nErrors/Unsupported: <code>{errors + unsupported}</code>')
