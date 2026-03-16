import logging
import asyncio
import re
import random, os
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait
from pyrogram.errors.exceptions.bad_request_400 import ChannelInvalid, ChatAdminRequired, UsernameInvalid, UsernameNotModified
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto

from info import ADMINS, INDEX_REQ_CHANNEL as LOG_CHANNEL
from database.ia_filterdb import save_file, Media, Media2
from utils import temp

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
lock = asyncio.Lock()

PICS = (os.environ.get("PICS", "https://envs.sh/ZUb.png?2ftEB=1 https://envs.sh/ZUi.png?KNgjn=1 https://envs.sh/oD5.jpg https://envs.sh/7nm.jpg https://envs.sh/Chb.jpg")).split()
ADD_CHANNEL_CONVERSATION = {}

# ==========================================
# 🧠 FUZZY MATCHER (60% LOGIC FOR INDEXING)
# ==========================================
def is_similar(t1, t2):
    stop_words = {'the', 'a', 'an', 'of', 'and', 'in', 'to', 'with', 'for', 'is', 'at', 'on', 'part'}
    w1 = [x for x in re.sub(r'[^a-z0-9\s]', '', t1.lower()).split() if x not in stop_words]
    w2 = [x for x in re.sub(r'[^a-z0-9\s]', '', t2.lower()).split() if x not in stop_words]
    
    if not w1 or not w2: return False
    
    s1, s2 = set(w1), set(w2)
    intersection = s1.intersection(s2)
    
    # 60% match hone par same maan lega
    match_ratio = len(intersection) / min(len(s1), len(s2))
    return match_ratio >= 0.60

def extract_file_info(filename, fallback_index=0, category="anime"):
    season = "1"
    episode = str(fallback_index)
    
    # Extract Chapter/Episode Number
    match = re.search(r'(?i)(?:\[C|\[S|ch[\-\s]*|ep[\-\s]*|vol[\-\s]*|v|e|season[\-\s]*)0*(\d+(?:\.\d+)?)', filename)
    if match:
        episode = match.group(1)
    else:
        match = re.search(r'(?i)[- ]\s*0*(\d+(?:\.\d+)?)\s*(?:1080p|720p|480p|mkv|mp4|pdf|cbz|cbr)', filename)
        if match: episode = match.group(1)

    # Clean raw name
    clean_title = filename
    clean_title = re.sub(r'\[.*?\]|\(.*?\)', '', clean_title) 
    clean_title = re.sub(r'\.(mkv|mp4|avi|mpe?g|pdf|cbz|cbr|jpg|png)$', '', clean_title, flags=re.IGNORECASE)
    clean_title = re.sub(r'[^\w\s\.\-]', ' ', clean_title) 
    clean_title = re.split(r'(?i)(?:\s-\s)?\b(?:ch|chapter|ep|episode|vol|volume|season)\b', clean_title)[0] 
    clean_title = re.split(r'(?i)\bs\d{1,2}\b', clean_title)[0] 
    clean_title = re.sub(r'(?i)@\w+', '', clean_title) 
    clean_title = re.sub(r'(?i)\b(1080p|720p|480p|amzn|web|dl|rip|dual|audio|hindi|english|subbed|dubbed)\b', '', clean_title)
    clean_title = re.sub(r'[^a-zA-Z0-9\s]', ' ', clean_title).strip() 
    clean_title = " ".join(clean_title.split()).title()
    
    if not clean_title: clean_title = "Unknown"
    
    qual = "Normal"
    lower_name = filename.lower()
    if re.search(r'\b(2160p|4k)\b', lower_name): qual = "4K"
    elif re.search(r'\b1080p\b', lower_name): qual = "1080p"
    elif re.search(r'\b720p\b', lower_name): qual = "720p"
    elif re.search(r'\b480p\b', lower_name): qual = "480p"
    
    return clean_title, season, episode, qual

# ==========================================
# 🗑️ DELETE CHANNEL DB COMMAND (ADMIN ONLY)
# ==========================================
@Client.on_message(filters.command("delchnl") & filters.user(ADMINS))
async def delete_channel_db(bot, message):
    if len(message.command) < 2:
        return await message.reply("⚠️ **How to use:**\n`/delchnl -10012345678`")
    try: chat_id = int(message.command[1])
    except ValueError: return await message.reply("⚠️ Invalid Chat ID!")

    msg = await message.reply("🗑 Deleting files from database... Please wait.")
    res1 = await Media.collection.delete_many({"chat_id": chat_id})
    res2 = await Media2.collection.delete_many({"chat_id": chat_id})
    total = res1.deleted_count + res2.deleted_count
    await msg.edit(f"✅ **Successfully deleted {total} files** belonging to `{chat_id}` from the database.")

# ==========================================
# ⚙️ ADMIN INDEX PANEL (ADMIN ONLY)
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
    
    text = f"**⚙️ Admin Index Management Panel**\n\n🎬 **Anime Database:** {anime_count} Files\n📚 **Manga Database:** {manga_count} Files\n\nSelect an option below:"
    
    pic = random.choice(PICS)
    
    if isinstance(message, CallbackQuery): 
        # Using edit_media instead of edit_text since we are sending a photo
        await message.message.edit_media(InputMediaPhoto(media=pic, caption=text), reply_markup=keyboard)
    else: 
        await message.reply_photo(photo=pic, caption=text, reply_markup=keyboard)

@Client.on_callback_query(filters.regex(r'^idx_') & filters.user(ADMINS))
async def admin_panel_callbacks(bot: Client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id

    if data == "idx_add_chnl":
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🎬 Anime", callback_data="idx_category_anime"), InlineKeyboardButton("📚 Manga", callback_data="idx_category_manga")], [InlineKeyboardButton("🔙 Back", callback_data="idx_back")]])
        await query.message.edit_caption(caption="Select the category for the new channel:", reply_markup=keyboard)

    elif data.startswith("idx_category_"):
        category = data.split("_")[2]
        ADD_CHANNEL_CONVERSATION[user_id] = {"category": category}
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="idx_add_chnl"), InlineKeyboardButton("❌ Close", callback_data="idx_close")]])
        await query.message.edit_caption(caption=f"**Step 2: Add {category.capitalize()} Channel**\n\n1. Make me admin in the channel.\n2. ⚠️ **Forward the LATEST file** from the channel here.", reply_markup=keyboard)

    elif data == "idx_list_chnls":
        await query.answer("Fetching Channels...", show_alert=False)
        chat_ids1 = await Media.collection.distinct("chat_id")
        chat_ids2 = await Media2.collection.distinct("chat_id")
        all_chats = set(chat_ids1 + chat_ids2)
        text = "**📡 Indexed Channels:**\n\n"
        if not all_chats or all_chats == {0} or all_chats == {None}: text += "No channels found."
        else:
            for cid in all_chats:
                if cid and cid != 0: text += f"▪️ <a href='https://t.me/c/{str(cid).replace('-100', '')}/1'>ID: {cid}</a>\n"
        await query.message.edit_caption(caption=text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="idx_back")]]))

    elif data == "idx_del_menu":
        await query.answer("Loading Delete Menu...", show_alert=False)
        chat_ids1 = await Media.collection.distinct("chat_id")
        chat_ids2 = await Media2.collection.distinct("chat_id")
        all_chats = list(set(chat_ids1 + chat_ids2))
        if not all_chats or all_chats == [0] or all_chats == [None]: return await query.answer("No channels found to delete!", show_alert=True)

        buttons = []
        for cid in all_chats[:50]: 
            if cid and cid != 0: buttons.append([InlineKeyboardButton(f"🗑 Delete Channel: {cid}", callback_data=f"idx_drop_{cid}")])
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data="idx_back")])
        await query.message.edit_caption(caption="⚠️ **WARNING: Click a channel below to PERMANENTLY delete all its files:**", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("idx_drop_"):
        chat_id = int(data.split("_")[2])
        await query.answer(f"Deleting {chat_id}...", show_alert=False)
        res1 = await Media.collection.delete_many({"chat_id": chat_id})
        res2 = await Media2.collection.delete_many({"chat_id": chat_id})
        await query.answer(f"✅ Deleted {res1.deleted_count + res2.deleted_count} files from {chat_id}!", show_alert=True)
        await send_index_panel(query)

    elif data.startswith("idx_list_titles_"):
        cat = data.split("_")[3]
        await query.answer(f"Fetching {cat.capitalize()} List...", show_alert=False)
        titles1 = await Media.collection.distinct("clean_title", {"category": cat})
        titles2 = await Media2.collection.distinct("clean_title", {"category": cat})
        all_titles = list(set(titles1 + titles2))
        text = f"**🗂️ Indexed {cat.capitalize()} Titles:**\n\n"
        if not all_titles or all_titles == ["Unknown"]: text += f"No {cat} found in DB."
        else:
            for title in sorted(all_titles)[:80]:
                if title and title != "Unknown": text += f"▪️ {title}\n"
            if len(all_titles) > 80: text += f"\n*...and {len(all_titles) - 80} more.*"
        await query.message.edit_caption(caption=text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="idx_back")]]))

    elif data == "idx_back" or data == "idx_refresh":
        if user_id in ADD_CHANNEL_CONVERSATION: del ADD_CHANNEL_CONVERSATION[user_id]
        await send_index_panel(query)

    elif data == "idx_close":
        if user_id in ADD_CHANNEL_CONVERSATION: del ADD_CHANNEL_CONVERSATION[user_id]
        await query.message.delete()

# ==========================================
# 📥 FORWARD RECEIVER & FAST INDEXER LOGIC
# ==========================================
@Client.on_message((filters.forwarded | filters.regex(r"(https://)?(t\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")) & filters.private & filters.incoming & filters.user(ADMINS))
async def send_for_index(bot, message):
    user_id = message.from_user.id
    category = "anime" 
    if user_id in ADD_CHANNEL_CONVERSATION:
        category = ADD_CHANNEL_CONVERSATION[user_id]["category"]
        del ADD_CHANNEL_CONVERSATION[user_id]

    if message.text:
        regex = re.compile(r"(https://)?(t\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")
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

    buttons = [
        [InlineKeyboardButton('Yes, Start Indexing', callback_data=f'index#accept#{chat_id}#{last_msg_id}#{user_id}#{category}')],
        [InlineKeyboardButton('Close', callback_data='idx_close')]
    ]
    return await message.reply_photo(photo=random.choice(PICS), caption=f'**Category:** {category.capitalize()}\n\nDo you Want To Index This Channel?\nChat ID: `{chat_id}`', reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_message(filters.command('setskip') & filters.user(ADMINS))
async def set_skip_number(bot, message):
    if ' ' in message.text:
        _, skip = message.text.split(" ")
        try: skip = int(skip)
        except: return await message.reply("Skip number should be an integer.")
        await message.reply(f"Successfully set SKIP number as {skip}")
        temp.CURRENT = int(skip)
    else: await message.reply("Give me a skip number")

@Client.on_callback_query(filters.regex(r'^index#') & filters.user(ADMINS))
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
    await msg.edit_caption(caption=f"Starting Indexing for Category: **{category.capitalize()}**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Cancel', callback_data='index_cancel')]]))
    
    try: chat = int(chat)
    except: chat = chat
        
    await index_files_to_db(int(lst_msg_id), chat, msg, bot, category)

async def index_files_to_db(lst_msg_id, chat, msg, bot, category="anime"):
    total_files = 0
    duplicate = 0
    errors = 0
    deleted = 0
    no_media = 0
    unsupported = 0
    
    # 🔥 PRE-FETCH EXISTING DB TITLES FOR FUZZY MATCHING
    existing_titles1 = await Media.collection.distinct("clean_title", {"category": category})
    existing_titles2 = await Media2.collection.distinct("clean_title", {"category": category})
    known_titles = list(set(existing_titles1 + existing_titles2))
    
    async with lock:
        try:
            current = temp.CURRENT
            temp.CANCEL = False
            
            async for message in bot.iter_messages(chat, lst_msg_id, temp.CURRENT):
                if temp.CANCEL: break
                current += 1
                
                if current % 50 == 0:
                    can = [[InlineKeyboardButton('Cancel', callback_data='index_cancel')]]
                    await msg.edit_caption(caption=f"**Category:** {category.capitalize()}\nMessages checked: <code>{current}</code>\nSaved: <code>{total_files}</code>\nDuplicates: <code>{duplicate}</code>", reply_markup=InlineKeyboardMarkup(can))
                        
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
                
                filename = getattr(media, 'file_name', '')
                if not filename:
                    if message.caption: filename = message.caption.split('\n')[0][:80]
                    elif message.media == enums.MessageMediaType.PHOTO: filename = f"Photo_{message.id}.jpg"
                    else: filename = f"Unknown_File_{message.id}"
                        
                media.file_name = filename
                if not hasattr(media, 'mime_type') or not media.mime_type:
                    if message.media == enums.MessageMediaType.PHOTO: media.mime_type = "image/jpeg"
                    else: media.mime_type = "application/octet-stream"
                
                # EXTRACT RAW TITLE
                raw_title, season, episode, quality = extract_file_info(filename, current, category)
                
                # 🔥 THE MAIN ATTRACTION: Check if it 60% matches an already known title
                final_title = raw_title
                for kt in known_titles:
                    if kt and is_similar(raw_title, kt):
                        # Use the better/longer title.
                        if len(kt) > len(final_title): final_title = kt
                        break
                
                # If completely new, add to our active memory
                if final_title not in known_titles:
                    known_titles.append(final_title)
                
                media.file_type = message.media.value
                media.category = category 
                media.caption = message.caption
                media.chat_id = chat
                
                # 🎯 Assigned the 60% matched title
                media.clean_title = final_title
                media.season = season
                media.episode = episode
                media.quality = quality
                
                aynav, vnay = await save_file(bot, media)
                if aynav: total_files += 1
                elif vnay == 0: duplicate += 1
                elif vnay == 2: errors += 1
                
        except Exception as e:
            logger.exception(e)
            await msg.edit_caption(caption=f'Error: {e}')
        else:
            await msg.edit_caption(caption=f'Successfully saved <code>{total_files}</code> files to {category.capitalize()} dataBase!\nDuplicate Files Skipped: <code>{duplicate}</code>\nErrors/Unsupported: <code>{errors + unsupported}</code>')
