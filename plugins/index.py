
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

ADD_CHANNEL_CONVERSATION = {}

# ==========================================
# 🧠 ADVANCED REGEX FILE PARSER (FOR DB INDEXING)
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
    (re.compile(rf'\bE{SEP}(\d{{1,4}})(?=[\s\.\-_)\'\]]+|$)(?![\dp])', re.IGNORECASE), (None, 1)),
    (re.compile(rf'\[E{SEP}(\d{{1,4}})\]', re.IGNORECASE), (None, 1)),
    (re.compile(rf'\bEpisode{SEP}(\d{{1,4}})(?=[\s\.\-_)\]]+|$)', re.IGNORECASE), (None, 1)),
    (re.compile(rf'\bEp{SEP}(\d{{1,4}})(?=[\s\.\-_)\]]+|$)', re.IGNORECASE), (None, 1)),
    (re.compile(r'\[(\d{2,3})\](?!p|fps|i)', re.IGNORECASE), (None, 1)),
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
    (re.compile(r'(?:^|[\s\-_.])(\d{2,4})(?=[\s\-_.]|$)(?!p|fps|\d)', re.IGNORECASE), (None, 1)),
    (re.compile(r'\[(\d{2,4})\](?!p|fps)', re.IGNORECASE), (None, 1)),
    (re.compile(r'^S(\d{2})E(\d{2,4})$', re.IGNORECASE), (1, 2)),
    (re.compile(r'^S(\d{2})\s*-\s*E(\d{2,4})$', re.IGNORECASE), (1, 2)),
    (re.compile(r'\[[\s]*(\d{2,4})[\s]*\](?!p|i|fps)', re.IGNORECASE), (None, 1)),
    (re.compile(r'(?:^|[\s\-_.(\[])\s*(\d{2,4})\s*(?=[\s\-_.)\]])', re.IGNORECASE), (None, 1))
]

def extract_file_info(filename, fallback_index=0):
    season = "1"
    episode = str(fallback_index)
    
    for pattern, (s_idx, e_idx) in SEASON_EPISODE_PATTERNS:
        match = pattern.search(filename)
        if match:
            if s_idx is not None:
                try: season = str(int(match.group(s_idx)))
                except: pass
            if e_idx is not None:
                try: episode = str(int(match.group(e_idx)))
                except: pass
            break

    lower_name = filename.lower()
    qual = "Normal"
    if re.search(r'\b(2160p|4k)\b', lower_name): qual = "4K"
    elif re.search(r'\b1080p\b', lower_name): qual = "1080p"
    elif re.search(r'\b720p\b', lower_name): qual = "720p"
    elif re.search(r'\b480p\b', lower_name): qual = "480p"
    
    clean_title = re.sub(r'\.(mkv|mp4|avi|mpe?g)$', '', filename, flags=re.IGNORECASE)
    clean_title = re.sub(r'\[.*?\]|\(.*?\)', '', clean_title)
    
    for pattern, _ in SEASON_EPISODE_PATTERNS:
        m = pattern.search(clean_title)
        if m:
            clean_title = clean_title[:m.start()]
            break
            
    clean_title = clean_title.replace(".", " ").replace("_", " ")
    tags = r'\b(mkv|mp4|avi|hd|1080p|720p|480p|4k|webrip|web-dl|amzn|x265|x264|hevc|hindi|english|dual|audio|dubbed|subbed)\b'
    clean_title = re.sub(tags, '', clean_title, flags=re.IGNORECASE)
    clean_title = re.sub(r'[-–—~]\s*$', '', clean_title.strip()).strip()
    clean_title = " ".join(clean_title.split())
    if not clean_title: clean_title = "Unknown"
    
    return clean_title.title(), season, episode, qual

# ==========================================
# ADMIN INDEX PANEL COMMANDS & CALLBACKS
# ==========================================

@Client.on_message(filters.command("index") & filters.user(ADMINS))
async def index_admin_panel(bot: Client, message):
    await send_index_panel(message)

async def send_index_panel(message):
    # 🧠 LIVE DATABASE COUNTING
    anime_count = await Media.collection.count_documents({"category": "anime"}) + await Media2.collection.count_documents({"category": "anime"})
    manga_count = await Media.collection.count_documents({"category": "manga"}) + await Media2.collection.count_documents({"category": "manga"})
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Chnl", callback_data="idx_add_chnl")],
        [InlineKeyboardButton("Index Chnls", callback_data="idx_list_chnls"), 
         InlineKeyboardButton("Indexlist", callback_data="idx_list_anime")],
        [InlineKeyboardButton("Reindex All", callback_data="idx_reindex_all"),
         InlineKeyboardButton("Refresh", callback_data="idx_refresh")],
        [InlineKeyboardButton("Close", callback_data="idx_close")]
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
             InlineKeyboardButton("Close", callback_data="idx_close")]
        ])
        await query.message.edit_text(
            f"**Step 2: Add {category.capitalize()} Channel**\n\n"
            f"1. Make sure I am an admin in the channel.\n"
            f"2. Forward any recent file/post from the channel here to start indexing.",
            reply_markup=keyboard
        )

    elif data == "idx_list_chnls":
        await query.answer("Fetching Channels...", show_alert=False)
        chat_ids = await Media.collection.distinct("chat_id")
        
        text = "**📡 Indexed Channels (Chat IDs):**\n\n"
        if not chat_ids:
            text += "No channels found or chat_id not saved in DB."
        else:
            for cid in chat_ids:
                if cid: text += f"▪️ `{cid}`\n"
                
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="idx_back")]])
        await query.message.edit_text(text, reply_markup=keyboard)

    elif data == "idx_list_anime":
        await query.answer("Fetching Anime List...", show_alert=False)
        anime_titles = await Media.collection.distinct("clean_title", {"category": "anime"})
        
        text = "**🗂️ Indexed Anime Titles:**\n\n"
        if not anime_titles:
            text += "No anime found in DB."
        else:
            for title in sorted(anime_titles)[:80]: # Showing first 80 to prevent TG message length limit
                if title: text += f"▪️ `{title}`\n"
            if len(anime_titles) > 80:
                text += f"\n*...and {len(anime_titles) - 80} more.*"
                
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="idx_back")]])
        await query.message.edit_text(text, reply_markup=keyboard)

    elif data == "idx_back":
        if user_id in ADD_CHANNEL_CONVERSATION:
            del ADD_CHANNEL_CONVERSATION[user_id]
        await send_index_panel(query)

    elif data == "idx_refresh":
        await send_index_panel(query)
        await query.answer("Panel Refreshed!", show_alert=False)

    elif data == "idx_close":
        if user_id in ADD_CHANNEL_CONVERSATION:
            del ADD_CHANNEL_CONVERSATION[user_id]
        await query.message.delete()

# ==========================================
# INDEXING REQUEST HANDLERS (FORWARD / LINK)
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
        if not match:
            return await message.reply('Invalid link')
        chat_id = match.group(4)
        last_msg_id = int(match.group(5))
        if chat_id.isnumeric():
            chat_id  = int(("-100" + chat_id))
    elif message.forward_from_chat.type == enums.ChatType.CHANNEL:
        last_msg_id = message.forward_from_message_id
        chat_id = message.forward_from_chat.username or message.forward_from_chat.id
    else:
        return

    try:
        k = await bot.get_messages(chat_id, last_msg_id)
    except:
        return await message.reply('Make Sure That I am An Admin In The Channel, if channel is private')

    if user_id in ADMINS:
        buttons = [
            [InlineKeyboardButton('Yes, Start Indexing', callback_data=f'index#accept#{chat_id}#{last_msg_id}#{user_id}#{category}')],
            [InlineKeyboardButton('Close', callback_data='idx_close')]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        return await message.reply(
            f'**Category:** {category.capitalize()}\n\n'
            f'Do you Want To Index This Channel?\n\n'
            f'Chat ID/ Username: <code>{chat_id}</code>\nLast Message ID: <code>{last_msg_id}</code>',
            reply_markup=reply_markup)

# ==========================================
# INDEXING PROCESS CALLBACK
# ==========================================

@Client.on_callback_query(filters.regex(r'^index#'))
async def index_files_callback(bot, query):
    if query.data.startswith('index_cancel'):
        temp.CANCEL = True
        return await query.answer("Cancelling Indexing")
        
    parts = query.data.split("#")
    if len(parts) == 6:
        _, action, chat, lst_msg_id, from_user, category = parts
    else:
        _, action, chat, lst_msg_id, from_user = parts
        category = "anime"

    if action == 'reject':
        return await query.message.delete()

    if lock.locked():
        return await query.answer('Wait until previous process complete.', show_alert=True)
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
# THE INDEXING ENGINE (WITH AI PARSING)
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
            async for message in bot.iter_messages(chat, lst_msg_id, temp.CURRENT):
                if temp.CANCEL:
                    break
                current += 1
                if current % 80 == 0:
                    can = [[InlineKeyboardButton('Cancel', callback_data='index_cancel')]]
                    await msg.edit_text(
                        text=f"**Category:** {category.capitalize()}\nTotal messages fetched: <code>{current}</code>\nTotal messages saved: <code>{total_files}</code>\nDuplicate Files Skipped: <code>{duplicate}</code>",
                        reply_markup=InlineKeyboardMarkup(can))
                if message.empty:
                    deleted += 1
                    continue
                elif not message.media:
                    no_media += 1
                    continue
                elif message.media not in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.AUDIO, enums.MessageMediaType.DOCUMENT]:
                    unsupported += 1
                    continue
                media = getattr(message, message.media.value, None)
                if not media:
                    unsupported += 1
                    continue
                
                # 🔥 THE MAGIC HAPPENS HERE: Parse data BEFORE saving to DB
                filename = getattr(media, 'file_name', 'Unknown')
                title, season, episode, quality = extract_file_info(filename, current)
                
                media.file_type = message.media.value
                media.category = category 
                media.caption = message.caption
                media.chat_id = chat
                
                # Attaching clean extracted data to the media object
                media.clean_title = title
                media.season = season
                media.episode = episode
                media.quality = quality
                
                aynav, vnay = await save_file(bot, media)
                if aynav:
                    total_files += 1
                elif vnay == 0:
                    duplicate += 1
                elif vnay == 2:
                    errors += 1
        except Exception as e:
            logger.exception(e)
            await msg.edit(f'Error: {e}')
        else:
            await msg.edit(f'Successfully saved <code>{total_files}</code> to {category.capitalize()} dataBase!\nDuplicate Files Skipped: <code>{duplicate}</code>\nDeleted Messages Skipped: <code>{deleted}</code>')

