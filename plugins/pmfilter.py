import asyncio, re, math, logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database.users_chats_db import db
from database.ia_filterdb import get_search_results
from utils import get_settings, temp, get_size
from info import *

# Anilist fetcher import
try:
    from plugins.anilist import fetch_anime_details as get_anime_info
except ImportError:
    get_anime_info = None

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

FRESH = {}
temp.GETALL = {}

# ==========================================
# 🗑️ HELPER: AUTO DELETE
# ==========================================
async def auto_delete_msg(message, delay):
    await asyncio.sleep(delay)
    try: await message.delete()
    except: pass

# ==========================================
# 💬 MESSAGE HANDLERS (GROUP & PM)
# ==========================================
@Client.on_message(filters.group & filters.text & filters.incoming)
async def group_search(client, message):
    if message.text.startswith("/") or message.text.startswith("#"): return
    settings = await get_settings(message.chat.id)
    if settings.get('auto_ffilter', True):
        await auto_filter(client, message)

@Client.on_message(filters.private & filters.text & filters.incoming)
async def pm_search_handler(bot, message):
    if message.text.startswith("/") or message.text.startswith("#"): return  
    
    pm_search_enabled = await db.pm_search_status(bot.me.id)
    if pm_search_enabled:
        await auto_filter(bot, message)
    else:
        await message.reply_text(
            f"<b>🙋 ʜᴇʏ {message.from_user.first_name} 😍 ,\n\n𝒀𝒐𝒖 𝒄𝒂𝒏 𝒔𝒆𝒂𝒓𝒄𝒉 𝒇𝒐𝒓 𝑨𝒏𝒊𝒎𝒆/𝑴𝒂𝒏𝒈𝒂 𝒐𝒏𝒍𝒚 𝒐𝒏 𝒐𝒖𝒓 𝑮𝒓𝒐𝒖𝒑 👇</b>",   
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📝 ʀᴇǫᴜᴇsᴛ ʜᴇʀᴇ ", url=GRP_LNK)]])
        )

# ==========================================
# 🔍 CORE SEARCH ENGINE (VIOLET UI)
# ==========================================
async def auto_filter(client, msg):
    search = msg.text.lower()
    if len(search) < 2 or len(search) > 100: return
    
    m = await msg.reply_text(f'**🔎 sᴇᴀʀᴄʜɪɴɢ...** `{search}`')
    search = re.sub(r"[:-]", "", search.replace("-", " ")).strip()
    
    # DB se files nikalna
    files, offset, total_results = await get_search_results(msg.chat.id, search, offset=0, filter=True)
    
    if not files:
        return await m.edit("<b>❌ No Anime/Manga found with this name. Check spelling!</b>")

    key = f"{msg.chat.id}-{msg.id}"
    FRESH[key] = search
    temp.GETALL[key] = files
    settings = await get_settings(msg.chat.id)

    # 🎛️ BUTTONS GENERATION
    btn = [[InlineKeyboardButton("📤 Sᴇɴᴅ Aʟʟ", callback_data=f"sendfiles#{key}")]]
    
    for f in files:
        fname = ' '.join(filter(lambda x: not x.startswith('['), f.file_name.split()))
        btn.append([InlineKeyboardButton(f"📁 {get_size(f.file_size)} ▷ {fname}", callback_data=f'file#{f.file_id}')])
    
    # Pagination
    if offset:
        btn.append([InlineKeyboardButton("ᴘᴀɢᴇ", callback_data="pages"), InlineKeyboardButton(f"1/{math.ceil(total_results/10)}", callback_data="pages"), InlineKeyboardButton("ɴᴇxᴛ ⋟", callback_data=f"next_{msg.from_user.id}_{key}_{offset}")])
    else:
        btn.append([InlineKeyboardButton("↭ ɴᴏ ᴍᴏʀᴇ ᴘᴀɢᴇꜱ ᴀᴠᴀɪʟᴀʙʟᴇ ↭", callback_data="pages")])
        
    btn.append([InlineKeyboardButton("👨‍💻 ᴀᴅᴍɪɴ", url=f"https://t.me/{OWNER_USERNAME}")])

    # 🌟 ANILIST API FETCH
    anime_info = await get_anime_info(search) if get_anime_info else None

    if anime_info:
        cap = f"🎬 <b>Nᴀᴍᴇ :</b> <code>{anime_info.get('title', search)}</code>\n"
        cap += f"✨ <b>Eᴘɪsᴏᴅᴇs :</b> <code>{anime_info.get('episodes', 'Unknown')}</code>\n"
        status = anime_info.get('status', 'Completed')
        cap += f"⚡ <b>Sᴛᴀᴛᴜs :</b> <code>{status}</code>\n"
        cap += f"👤 <b>Cʜᴀʀᴀᴄᴛᴇʀ :</b> <code>{anime_info.get('character', 'N/A')}</code>\n\n"
        
        description = anime_info.get('description', '')[:150]
        if description: cap += f"<b>Iɴғᴏ :</b> {description}...\n\n"
        
        trailer = anime_info.get('trailer')
        if trailer: cap += f"🎥 <b>Tʀᴀɪʟᴇʀ : <a href='{trailer}'>Wᴀᴛᴄʜ Hᴇʀᴇ</a></b>\n\n"
        
        cap += "<b>📚 Yᴏᴜʀ Rᴇǫᴜᴇsᴛᴇᴅ Fɪʟᴇs 👇</b>\n\n"
        cover_image = anime_info.get('cover_image')
    else:
        cap = f"🎬 <b>Nᴀᴍᴇ :</b> <code>{search}</code>\n✨ <b>Tᴏᴛᴀʟ Fɪʟᴇs :</b> <code>{total_results}</code>\n👤 <b>Rᴇǫᴜᴇsᴛᴇᴅ Bʏ :</b> {msg.from_user.mention}\n\n<b>📚 Yᴏᴜʀ Rᴇǫᴜᴇsᴛᴇᴅ Fɪʟᴇs 👇</b>\n\n"
        cover_image = None

    if cover_image:
        final_msg = await msg.reply_photo(photo=cover_image, caption=cap, reply_markup=InlineKeyboardMarkup(btn))
    else:
        final_msg = await msg.reply_text(text=cap, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
    
    await m.delete()
    if settings.get('auto_delete', True):
        asyncio.create_task(auto_delete_msg(final_msg, DELETE_TIME))
        asyncio.create_task(auto_delete_msg(msg, DELETE_TIME))

# ==========================================
# 🎛️ CALLBACKS (PAGINATION & FILE SENDING)
# ==========================================
@Client.on_callback_query(filters.regex(r"^next"))
async def next_page(bot, query):
    ident, req, key, offset = query.data.split("_")
    if int(req) not in [query.from_user.id, 0]: return await query.answer("Not for you!", show_alert=True)
    
    offset = int(offset)
    search = FRESH.get(key)
    if not search: return await query.answer("Query Expired! Search again.", show_alert=True)

    files, n_offset, total = await get_search_results(query.message.chat.id, search, offset=offset, filter=True)
    if not files: return
    
    temp.GETALL[key] = files
    btn = [[InlineKeyboardButton("📤 Sᴇɴᴅ Aʟʟ", callback_data=f"sendfiles#{key}")]]
    
    for f in files:
        fname = ' '.join(filter(lambda x: not x.startswith('['), f.file_name.split()))
        btn.append([InlineKeyboardButton(f"📁 {get_size(f.file_size)} ▷ {fname}", callback_data=f'file#{f.file_id}')])
        
    page_btn = [InlineKeyboardButton(f"{math.ceil(offset/10)+1} / {math.ceil(total/10)}", callback_data="pages")]
    off_set = 0 if 0 < offset <= 10 else (None if offset == 0 else offset - 10)
    
    if n_offset == 0:
        btn.append([InlineKeyboardButton("⋞ ʙᴀᴄᴋ", callback_data=f"next_{req}_{key}_{off_set}")] + page_btn)
    elif off_set is None:
        btn.append([InlineKeyboardButton("ᴘᴀɢᴇ", callback_data="pages")] + page_btn + [InlineKeyboardButton("ɴᴇxᴛ ⋟", callback_data=f"next_{req}_{key}_{n_offset}")])
    else:
        btn.append([InlineKeyboardButton("⋞ ʙᴀᴄᴋ", callback_data=f"next_{req}_{key}_{off_set}")] + page_btn + [InlineKeyboardButton("ɴᴇxᴛ ⋟", callback_data=f"next_{req}_{key}_{n_offset}")])

    btn.append([InlineKeyboardButton("👨‍💻 ᴀᴅᴍɪɴ", url=f"https://t.me/{OWNER_USERNAME}")])
    
    await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
    await query.answer()

@Client.on_callback_query(filters.regex(r"^file#"))
async def single_file_cb(bot, query):
    _, file_id = query.data.split("#")
    await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start=file_{file_id}")

@Client.on_callback_query(filters.regex(r"^sendfiles#"))
async def send_all_cb(bot, query):
    _, key = query.data.split("#")
    await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start=allfiles_{key}")

@Client.on_callback_query(filters.regex(r"^pages$"))
async def pages_cb(bot, query):
    await query.answer()

@Client.on_callback_query(filters.regex(r"^close_data$"))
async def close_cb(bot, query):
    await query.message.delete()
  
