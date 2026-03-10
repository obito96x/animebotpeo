import logging
import asyncio
import re
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait
from pyrogram.errors.exceptions.bad_request_400 import ChannelInvalid, ChatAdminRequired, UsernameInvalid, UsernameNotModified
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from info import ADMINS, INDEX_REQ_CHANNEL as LOG_CHANNEL
from database.ia_filterdb import save_file
from utils import temp

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
lock = asyncio.Lock()

# Dictionary to store ongoing conversation state for adding channels
ADD_CHANNEL_CONVERSATION = {}

# ==========================================
# ADMIN INDEX PANEL COMMANDS & CALLBACKS
# ==========================================

@Client.on_message(filters.command("index") & filters.user(ADMINS))
async def index_admin_panel(bot: Client, message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Chnl", callback_data="idx_add_chnl")],
        [InlineKeyboardButton("New Index Chnl", callback_data="idx_new_chnl"), 
         InlineKeyboardButton("Reindex All", callback_data="idx_reindex_all")],
        [InlineKeyboardButton("Refresh", callback_data="idx_refresh"),
         InlineKeyboardButton("Close", callback_data="idx_close")]
    ])
    
    # Yahan tum get_db_stats() jaisa function apne database se bula sakte ho
    total_anime_files = 0  # Replace with DB count
    total_manga_files = 0  # Replace with DB count
    
    text = (
        "**⚙️ Admin Index Management Panel**\n\n"
        f"🎬 **Anime Database:** {total_anime_files} Files\n"
        f"📚 **Manga Database:** {total_manga_files} Files\n\n"
        "Select an option below to manage your indexed channels."
    )
    
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
        await query.edit_message_text("Select the category for the new channel:", reply_markup=keyboard)

    elif data.startswith("idx_category_"):
        category = data.split("_")[2] # 'anime' or 'manga'
        ADD_CHANNEL_CONVERSATION[user_id] = {"category": category}
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="idx_add_chnl"),
             InlineKeyboardButton("Close", callback_data="idx_close")]
        ])
        await query.edit_message_text(
            f"**Step 2: Add {category.capitalize()} Channel**\n\n"
            f"1. Make sure I am an admin in the channel.\n"
            f"2. Forward any recent file/post from the channel here to start indexing.",
            reply_markup=keyboard
        )

    elif data == "idx_back":
        if user_id in ADD_CHANNEL_CONVERSATION:
            del ADD_CHANNEL_CONVERSATION[user_id]
        await index_admin_panel(bot, query.message)
        await query.message.delete()

    elif data == "idx_refresh":
        await query.answer("Refreshed Status", show_alert=False)
        # Update text with fresh counts from DB here
        pass 

    elif data == "idx_close":
        if user_id in ADD_CHANNEL_CONVERSATION:
            del ADD_CHANNEL_CONVERSATION[user_id]
        await query.message.delete()

# ==========================================
# INDEXING REQUEST HANDLERS (FORWARD / LINK)
# ==========================================

@Client.on_message((filters.forwarded | (filters.regex(r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")) & filters.text ) & filters.private & filters.incoming)
async def send_for_index(bot, message):
    # Detect if admin is in the middle of adding a specific category channel
    user_id = message.from_user.id
    category = "anime" # Default
    if user_id in ADD_CHANNEL_CONVERSATION:
        category = ADD_CHANNEL_CONVERSATION[user_id]["category"]
        del ADD_CHANNEL_CONVERSATION[user_id] # Clear state after receiving forward

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
        await bot.get_chat(chat_id)
    except ChannelInvalid:
        return await message.reply('This may be a private channel / group. Make me an admin over there to index the files.')
    except (UsernameInvalid, UsernameNotModified):
        return await message.reply('Invalid Link specified.')
    except Exception as e:
        logger.exception(e)
        return await message.reply(f'Errors - {e}')

    try:
        k = await bot.get_messages(chat_id, last_msg_id)
    except:
        return await message.reply('Make Sure That I am An Admin In The Channel, if channel is private')
    if k.empty:
        return await message.reply('This may be group and I am not an admin of the group.')

    if user_id in ADMINS:
        # Added category to the callback data
        buttons = [
            [InlineKeyboardButton('Yes, Start Indexing', callback_data=f'index#accept#{chat_id}#{last_msg_id}#{user_id}#{category}')],
            [InlineKeyboardButton('Close', callback_data='idx_close')]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        return await message.reply(
            f'**Category:** {category.capitalize()}\n\n'
            f'Do you Want To Index This Channel?\n\n'
            f'Chat ID/ Username: <code>{chat_id}</code>\nLast Message ID: <code>{last_msg_id}</code>\n\n'
            f'Need setskip? 👉🏻 /setskip',
            reply_markup=reply_markup)

    # For normal users requesting index
    if type(chat_id) is int:
        try:
            link = (await bot.create_chat_invite_link(chat_id)).invite_link
        except ChatAdminRequired:
            return await message.reply('Make sure I am an admin in the chat and have permission to invite users.')
    else:
        link = f"@{message.forward_from_chat.username}"
        
    buttons = [
        [InlineKeyboardButton('Accept Index', callback_data=f'index#accept#{chat_id}#{last_msg_id}#{user_id}#anime')],
        [InlineKeyboardButton('Reject Index', callback_data=f'index#reject#{chat_id}#{message.id}#{user_id}#anime')]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    await bot.send_message(LOG_CHANNEL,
                           f'#IndexRequest\n\nBy : {message.from_user.mention} (<code>{message.from_user.id}</code>)\nChat ID/ Username - <code> {chat_id}</code>\nLast Message ID - <code>{last_msg_id}</code>\nInviteLink - {link}',
                           reply_markup=reply_markup)
    await message.reply('Thank You For the Contribution, Wait For My Moderators to verify the files.')


# ==========================================
# INDEXING PROCESS CALLBACK
# ==========================================

@Client.on_callback_query(filters.regex(r'^index#'))
async def index_files_callback(bot, query):
    if query.data.startswith('index_cancel'):
        temp.CANCEL = True
        return await query.answer("Cancelling Indexing")
        
    # Unpack the new data format which includes category
    parts = query.data.split("#")
    if len(parts) == 6:
        _, action, chat, lst_msg_id, from_user, category = parts
    else:
        # Fallback for old buttons
        _, action, chat, lst_msg_id, from_user = parts
        category = "anime"

    if action == 'reject':
        await query.message.delete()
        await bot.send_message(int(from_user),
                               f'Your Submission for indexing {chat} has been declined by our moderators.',
                               reply_to_message_id=int(lst_msg_id))
        return

    if lock.locked():
        return await query.answer('Wait until previous process complete.', show_alert=True)
    msg = query.message

    await query.answer('Processing...⏳', show_alert=True)
    if int(from_user) not in ADMINS:
        await bot.send_message(int(from_user),
                               f'Your Submission for indexing {chat} has been accepted by our moderators and will be added soon.',
                               reply_to_message_id=int(lst_msg_id))
    await msg.edit(
        f"Starting Indexing for Category: **{category.capitalize()}**",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton('Cancel', callback_data='index_cancel')]]
        )
    )
    try:
        chat = int(chat)
    except:
        chat = chat
        
    await index_files_to_db(int(lst_msg_id), chat, msg, bot, category)


@Client.on_message(filters.command('setskip') & filters.user(ADMINS))
async def set_skip_number(bot, message):
    if ' ' in message.text:
        _, skip = message.text.split(" ")
        try:
            skip = int(skip)
        except:
            return await message.reply("Skip number should be an integer.")
        await message.reply(f"Successfully set SKIP number as {skip}")
        temp.CURRENT = int(skip)
    else:
        await message.reply("Give me a skip number")


# ==========================================
# THE INDEXING ENGINE
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
                    await msg.edit(f"Successfully Cancelled!!\n\nSaved <code>{total_files}</code> files to {category.capitalize()} dataBase!\nDuplicate Files Skipped: <code>{duplicate}</code>\nDeleted Messages Skipped: <code>{deleted}</code>\nNon-Media messages skipped: <code>{no_media + unsupported}</code>(Unsupported Media - `{unsupported}` )\nErrors Occurred: <code>{errors}</code>")
                    break
                current += 1
                if current % 80 == 0:
                    can = [[InlineKeyboardButton('Cancel', callback_data='index_cancel')]]
                    reply = InlineKeyboardMarkup(can)
                    await msg.edit_text(
                        text=f"**Category:** {category.capitalize()}\nTotal messages fetched: <code>{current}</code>\nTotal messages saved: <code>{total_files}</code>\nDuplicate Files Skipped: <code>{duplicate}</code>\nDeleted Messages Skipped: <code>{deleted}</code>\nNon-Media messages skipped: <code>{no_media + unsupported}</code>(Unsupported Media - `{unsupported}` )\nErrors Occurred: <code>{errors}</code>",
                        reply_markup=reply)
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
                
                # Attaching the target category (anime/manga) to the media object 
                # so save_file() inside ia_filterdb.py can sort it.
                media.file_type = message.media.value
                media.category = category 
                media.caption = message.caption
                
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
            await msg.edit(f'Successfully saved <code>{total_files}</code> to {category.capitalize()} dataBase!\nDuplicate Files Skipped: <code>{duplicate}</code>\nDeleted Messages Skipped: <code>{deleted}</code>\nNon-Media messages skipped: <code>{no_media + unsupported}</code>(Unsupported Media - `{unsupported}` )\nErrors Occurred: <code>{errors}</code>')
