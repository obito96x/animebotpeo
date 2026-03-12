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

# ==========================================
# ⚙️ INLINE ADMIN PANEL
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

    if data == "idx_add_chnl":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="idx_back")]
        ])
        await query.message.edit_text(
            "**Step 2: Add Channel**\n\n"
            "1. Make sure I am an admin in the channel.\n"
            "2. **Forward any file/post** from the channel here to start indexing.",
            reply_markup=keyboard
        )

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

    elif data == "idx_del_menu":
        await query.answer("Loading Delete Menu...", show_alert=False)
        chat_ids1 = await Media.collection.distinct("chat_id")
        chat_ids2 = await Media2.collection.distinct("chat_id")
        all_chats = list(set(chat_ids1 + chat_ids2))
        
        if not all_chats or all_chats == [0] or all_chats == [None]: 
            await query.answer("No channels found to delete!", show_alert=True)
            return

        buttons = []
        for cid in all_chats[:50]: 
            if cid and cid != 0: 
                buttons.append([InlineKeyboardButton(f"🗑 Delete Channel: {cid}", callback_data=f"idx_drop_{cid}")])
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data="idx_back")])
        
        await query.message.edit_text("⚠️ **Click a channel below to PERMANENTLY delete all its files:**", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("idx_drop_"):
        chat_id = int(data.split("_")[2])
        await query.answer(f"Deleting {chat_id}...", show_alert=False)
        
        res1 = await Media.collection.delete_many({"chat_id": chat_id})
        res2 = await Media2.collection.delete_many({"chat_id": chat_id})
        total = res1.deleted_count + res2.deleted_count
        
        await query.answer(f"✅ Deleted {total} files from {chat_id}!", show_alert=True)
        await send_index_panel(query)

    elif data.startswith("idx_list_titles_"):
        cat = data.split("_")[3]
        await query.answer(f"Fetching {cat.capitalize()} List...", show_alert=False)
        
        titles1 = await Media.collection.distinct("clean_title", {"category": cat})
        titles2 = await Media.collection.distinct("clean_title", {"category": cat})
        all_titles = list(set(titles1 + titles2))
        
        text = f"**🗂️ Indexed {cat.capitalize()} Titles:**\n\n"
        if not all_titles or all_titles == ["Unknown", ""]:
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
        if data == "idx_refresh": await query.answer("Refreshed!", show_alert=False)
        await send_index_panel(query)

    elif data == "idx_close":
        await query.message.delete()


# ==========================================
# 📥 FORWARD / LINK CATCHER
# ==========================================
@Client.on_message((filters.forwarded | (filters.regex(r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")) & filters.text ) & filters.private & filters.incoming)
async def send_for_index(bot, message):
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

    if message.from_user.id in ADMINS:
        buttons = [
            [InlineKeyboardButton('🎬 Anime', callback_data=f'index#accept#{chat_id}#{last_msg_id}#{message.from_user.id}#anime'),
             InlineKeyboardButton('📚 Manga', callback_data=f'index#accept#{chat_id}#{last_msg_id}#{message.from_user.id}#manga')],
            [InlineKeyboardButton('Close', callback_data='idx_close')]
        ]
        return await message.reply(
            f'Do you Want To Index This Channel?\n\n'
            f'Chat ID: <code>{chat_id}</code>\nForwarded Message ID: <code>{last_msg_id}</code>\n\nSelect the category below:',
            reply_markup=InlineKeyboardMarkup(buttons))


# ==========================================
# 🔄 RAW FAST INDEXING ENGINE
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
        return

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


@Client.on_message(filters.command('setskip') & filters.user(ADMINS))
async def set_skip_number(bot, message):
    if ' ' in message.text:
        _, skip = message.text.split(" ")
        try: skip = int(skip)
        except: return await message.reply("Skip number should be an integer.")
        await message.reply(f"Successfully set SKIP number as {skip}")
        temp.CURRENT = int(skip)
    else:
        await message.reply("Give me a skip number")


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
            
            # 🔥 ORIGINAL RAW METHOD: iter_messages (Super Fast)
            async for message in bot.iter_messages(chat, lst_msg_id, temp.CURRENT):
                if temp.CANCEL:
                    await msg.edit(f"Successfully Cancelled!!\n\nSaved <code>{total_files}</code> files to {category} dataBase!\nDuplicate Files Skipped: <code>{duplicate}</code>\nDeleted Messages Skipped: <code>{deleted}</code>\nNon-Media messages skipped: <code>{no_media + unsupported}</code>\nErrors Occurred: <code>{errors}</code>")
                    break
                
                current += 1
                if current % 50 == 0:
                    can = [[InlineKeyboardButton('Cancel', callback_data='index_cancel')]]
                    await msg.edit_text(
                        text=f"Total messages fetched: <code>{current}</code>\nTotal messages saved: <code>{total_files}</code>\nDuplicate Files Skipped: <code>{duplicate}</code>\nDeleted Messages Skipped: <code>{deleted}</code>\nNon-Media messages skipped: <code>{no_media + unsupported}</code>\nErrors Occurred: <code>{errors}</code>",
                        reply_markup=InlineKeyboardMarkup(can))
                        
                if message.empty:
                    deleted += 1
                    continue
                elif not message.media:
                    no_media += 1
                    continue
                    
                # 📸 SUPPORT FOR PHOTOS (MANGA) IN RAW ENGINE
                if message.media not in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.AUDIO, enums.MessageMediaType.DOCUMENT, enums.MessageMediaType.PHOTO]:
                    unsupported += 1
                    continue
                    
                media = getattr(message, message.media.value, None)
                if not media:
                    unsupported += 1
                    continue
                
                # Assign File Name for Photos
                filename = getattr(media, 'file_name', '')
                if not filename:
                    if message.caption:
                        filename = message.caption.split('\n')[0][:80]
                    elif message.media == enums.MessageMediaType.PHOTO:
                        filename = f"Photo_{message.id}.jpg"
                    else:
                        filename = f"Unknown_File_{message.id}"
                
                media.file_name = filename
                
                # Assign Mime Type for Photos
                if not hasattr(media, 'mime_type') or not media.mime_type:
                    if message.media == enums.MessageMediaType.PHOTO:
                        media.mime_type = "image/jpeg"
                    else:
                        media.mime_type = "application/octet-stream"

                media.file_type = message.media.value
                media.caption = message.caption
                
                # Assign New DB Fields
                media.category = category
                media.chat_id = chat
                
                # We extract simple Clean Title so Admin Panel works
                clean_title = re.sub(r'\.(mkv|mp4|avi|mpe?g|pdf|cbz|cbr|zip|rar|jpg|jpeg|png)$', '', filename, flags=re.IGNORECASE)
                clean_title = re.sub(r'\[.*?\]|\(.*?\)', '', clean_title)
                clean_title = re.sub(r'[-–—~]\s*$', '', clean_title.strip()).strip()
                media.clean_title = clean_title.title()
                
                # Simple extraction for PM Filter Engine
                media.season = "1"
                match_ep = re.search(r'(?i)(?:Chapter|Ch|Ep|Episode|E)\s*(\d+(?:\.\d+)?)', filename)
                media.episode = match_ep.group(1) if match_ep else "0"
                media.quality = "Normal"
                
                # Save to DB (Passing bot as required by ia_filterdb)
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
            await msg.edit(f'Successfully saved <code>{total_files}</code> to {category} dataBase!\nDuplicate Files Skipped: <code>{duplicate}</code>\nDeleted Messages Skipped: <code>{deleted}</code>\nNon-Media messages skipped: <code>{no_media + unsupported}</code>\nErrors Occurred: <code>{errors}</code>')
