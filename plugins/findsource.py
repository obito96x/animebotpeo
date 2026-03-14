import os
import requests
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from PicImageSearch import Network, SauceNAO, Ascii2D

SAUCE_API = os.environ.get("SAUCE_API", "245871b3ccabe1cf391295fc340c5fa94dd15276")
GROUP_LINK = os.environ.get("GROUP_LINK", "https://t.me/Shidoteshika1")

async def get_anilist_banner_and_trailer(anilist_id):
    query = """
    query ($id: Int) {
      Media (id: $id, type: ANIME) {
        title { english romaji }
        bannerImage
        coverImage { extraLarge }
        trailer { id site }
      }
    }
    """
    try:
        response = requests.post(
            "https://graphql.anilist.co",
            json={"query": query, "variables": {"id": anilist_id}},
        ).json()

        media = response["data"]["Media"]
        title = media["title"]["english"] or media["title"]["romaji"]
        image = media["bannerImage"] or media["coverImage"]["extraLarge"]
        
        trailer = None
        if media["trailer"] and media["trailer"]["site"] == "youtube":
            trailer = f"https://youtube.com/watch?v={media['trailer']['id']}"

        return title, image, trailer
    except Exception:
        return None, None, None

async def yandex_reverse(file_path):
    try:
        with open(file_path, "rb") as f:
            r = requests.post(
                "https://yandex.com/images/search",
                files={"upfile": f},
                data={"rpt": "imageview"},
                allow_redirects=False,
            )
        url = r.headers.get("Location")
        if url:
            html = requests.get("https://yandex.com" + url).text
            if "similar" in html.lower():
                return "Possible match found on Yandex"
    except Exception:
        pass
    return None

@Client.on_message(filters.command(["findanime", "trace", "sauce", "findcharacter"]) & filters.private)
async def hybrid_search(client: Client, message: Message):
    if not message.reply_to_message or not message.reply_to_message.photo:
        return await message.reply("⚠️ **Please reply to an image to use this command.**")

    msg = await message.reply("🔍 **Scanning the image...**")
    file_path = await message.reply_to_message.download()

    try:
        # ==========================================
        # 1. TRACE.MOE (For Exact Anime Scenes)
        # ==========================================
        try:
            with open(file_path, "rb") as f:
                res = requests.post("https://api.trace.moe/search", files={"image": f}).json()

            if res.get("result"):
                best = res["result"][0]
                similarity = round(best["similarity"] * 100, 2)

                if similarity >= 80:
                    anilist_id = best["anilist"]
                    ep = best.get("episode", "N/A")
                    title, banner, trailer = await get_anilist_banner_and_trailer(anilist_id)
                    safe_title = title[:30] if title else "Unknown" # Safe string length for callback

                    caption = (
                        f"🎯 **Anime Match Found!**\n\n"
                        f"📺 **Name:** `{title}`\n"
                        f"🎬 **Episode:** `{ep}`\n"
                        f"📊 **Similarity:** `{similarity}%`"
                    )

                    buttons = []
                    row = []
                    if trailer:
                        row.append(InlineKeyboardButton("🎥 Trailer", url=trailer))
                    row.append(InlineKeyboardButton("ℹ️ AniList", url=f"https://anilist.co/anime/{anilist_id}"))
                    buttons.append(row)

                    # 🔥 INTEGRATED DB BUTTONS (Watchlist & Get Anime)
                    buttons.append([
                        InlineKeyboardButton("🎬 Watch / Download", callback_data=f"find_anime#{safe_title}"),
                        InlineKeyboardButton("⭐ Add to Watchlist", callback_data=f"addwatch#{safe_title}#anime")
                    ])
                    buttons.append([InlineKeyboardButton("💬 Ask in Group", url=GROUP_LINK)])

                    await msg.delete()
                    if banner:
                        return await message.reply_photo(banner, caption=caption, reply_markup=InlineKeyboardMarkup(buttons))
                    else:
                        return await message.reply_text(caption, reply_markup=InlineKeyboardMarkup(buttons))
        except Exception as e:
            print("Trace.moe error:", e)

        # ==========================================
        # 2. SAUCENAO (For Manga & Fanart)
        # ==========================================
        if SAUCE_API:
            await msg.edit("🔍 **Checking Manga & Art databases...**")
            try:
                async with Network() as c:
                    saucenao = SauceNAO(client=c, api_key=SAUCE_API)
                    res = await saucenao.search(file=file_path)

                    if res.raw:
                        best = res.raw[0]
                        if best.similarity > 70:
                            title = getattr(best, "title", "") or getattr(best, "source", "") or "Unknown Artwork"
                            
                            btn = [[InlineKeyboardButton("🔍 Search Anime/Manga", callback_data=f"find_anime#{title[:30]}")]]
                            return await msg.edit(
                                f"🎯 **Artwork Match Found!**\n\n🖼 `{title}`\n📊 **Similarity:** `{best.similarity}%`",
                                reply_markup=InlineKeyboardMarkup(btn)
                            )
            except Exception as e:
                print("SauceNAO error:", e)

        # ==========================================
        # 3. ASCII2D (For Japanese Anime Art Servers)
        # ==========================================
        await msg.edit("🔍 **Searching Anime Art servers...**")
        try:
            async with Network() as c:
                ascii2d = Ascii2D(client=c)
                res = await ascii2d.search(file=file_path)

                if res.raw:
                    best = res.raw[0]
                    title = best.title or "Unknown Illustration"
                    
                    btn = [[InlineKeyboardButton("🔍 Search Title", callback_data=f"find_anime#{title[:30]}")]]
                    return await msg.edit(
                        f"🎯 **Possible Match Found!**\n\n🖼 `{title}`",
                        reply_markup=InlineKeyboardMarkup(btn)
                    )
        except Exception as e:
            print("Ascii2D error:", e)

        # ==========================================
        # 4. YANDEX FALLBACK (Deep Search)
        # ==========================================
        await msg.edit("🔍 **Deep searching the web...**")
        guess = await yandex_reverse(file_path)

        if guess:
            await msg.edit("🔎 **Image found on the web.**\n\nTry using Google Lens or Yandex Reverse Search manually to identify the character.")
        else:
            await msg.edit("❌ **Could not identify the character/anime.**\n\nThe image might be original fanart, heavily edited, or not in our databases.")

    finally:
        # 🔥 SAFELY REMOVE FILE TO PREVENT STORAGE LEAK
        if os.path.exists(file_path):
            os.remove(file_path)
