import os
import requests
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from PicImageSearch import Network, SauceNAO, Ascii2D

from plugins.anilist import fetch_anime_details

SAUCE_API = os.environ.get("SAUCE_API", "245871b3ccabe1cf391295fc340c5fa94dd15276")
GROUP_LINK = "https://t.me/Shidoteshika1"


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

        media = response.get("data", {}).get("Media", {})

        if not media:
            return None, None, None

        title = media.get("title", {}).get("english") or media.get("title", {}).get(
            "romaji"
        )

        image = media.get("bannerImage") or media.get("coverImage", {}).get("extraLarge")

        trailer_link = None
        trailer = media.get("trailer")

        if trailer and trailer.get("site") == "youtube":
            trailer_link = f"https://youtube.com/watch?v={trailer.get('id')}"

        return title, image, trailer_link

    except Exception as e:
        print(f"AniList Banner Fetch Error: {e}")
        return None, None, None


@Client.on_message(filters.command(["findanime", "trace", "findcharacter", "sauce"]) & filters.private)
async def hybrid_image_search(client: Client, message: Message):

    if not message.reply_to_message or not message.reply_to_message.photo:
        return await message.reply(
            "⚠️ **Kripya kisi image/screenshot par reply karke command use karein.**"
        )

    msg = await message.reply(
        "🔍 **Scanning image...**\n_Checking anime databases..._"
    )

    file_path = await message.reply_to_message.download()

    # ---------------- TRACE.MOE ---------------- #

    try:

        with open(file_path, "rb") as f:
            response = requests.post(
                "https://api.trace.moe/search", files={"image": f}
            ).json()

        if response.get("result"):

            best = response["result"][0]

            similarity = round(best["similarity"] * 100, 2)

            if similarity >= 85:

                anilist_id = best["anilist"]

                episode = best.get("episode", "N/A")

                title, banner_img, trailer = await get_anilist_banner_and_trailer(
                    anilist_id
                )

                title = title if title else best["filename"]

                caption = f"🎯 **AniCrew Match Found!**\n\n"
                caption += f"📺 **Name:** `{title}`\n"
                caption += f"🎬 **Episode:** `{episode}`\n"
                caption += f"📊 **Match:** `{similarity}%`\n"

                buttons = []

                row = []

                if trailer:
                    row.append(
                        InlineKeyboardButton("🎥 Trailer", url=trailer)
                    )

                row.append(
                    InlineKeyboardButton(
                        "ℹ️ AniList", url=f"https://anilist.co/anime/{anilist_id}"
                    )
                )

                buttons.append(row)

                buttons.append(
                    [
                        InlineKeyboardButton(
                            "🎬 Watch / Download",
                            callback_data=f"try_anime_{title[:20]}",
                        ),
                        InlineKeyboardButton(
                            "➕ Add to Watchlist",
                            callback_data=f"watchlist_{anilist_id}",
                        ),
                    ]
                )

                buttons.append(
                    [InlineKeyboardButton("💬 Ask in Group", url=GROUP_LINK)]
                )

                await msg.delete()

                if banner_img:
                    await message.reply_photo(
                        banner_img,
                        caption=caption,
                        reply_markup=InlineKeyboardMarkup(buttons),
                    )
                else:
                    await message.reply_text(
                        caption, reply_markup=InlineKeyboardMarkup(buttons)
                    )

                os.remove(file_path)

                return

    except Exception as e:
        print(f"Trace.moe Error: {e}")

    # ---------------- SAUCENAO ---------------- #

    await msg.edit_text("🔍 **Checking manga / art databases...**")

    match_found = False
    title_found = ""

    if SAUCE_API:

        try:

            async with Network() as c:

                saucenao = SauceNAO(client=c, api_key=SAUCE_API)

                results = await saucenao.search(file=file_path)

                if results.raw:

                    best = results.raw[0]

                    if best.similarity > 70:

                        title_found = (
                            getattr(best, "title", "")
                            or getattr(best, "source", "")
                            or getattr(best, "author", "")
                            or "Unknown Artwork"
                        )

                        match_found = True

        except Exception as e:
            print(f"SauceNAO Error: {e}")

    # ---------------- ASCII2D ---------------- #

    if not match_found:

        await msg.edit_text("🔍 **Scanning anime art servers...**")

        try:

            async with Network() as c:

                ascii2d = Ascii2D(client=c)

                results = await ascii2d.search(file=file_path)

                if results.raw:

                    best = results.raw[0]

                    title_found = best.title or "Unknown Illustration"

                    match_found = True

        except Exception as e:
            print(f"Ascii2D Error: {e}")

    # ---------------- RESULT ---------------- #

    if match_found:

        text = f"🎯 **Character / Artwork Match Found!**\n\n"
        text += f"🖼 **Source:** `{title_found}`"

        buttons = [
            [InlineKeyboardButton("💬 Ask in Group", url=GROUP_LINK)]
        ]

        await msg.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    else:

        await msg.edit_text(
            "❌ **No match found in databases.**\n\n"
            "_Tip: Try uncropped or higher quality image._"
        )

    if os.path.exists(file_path):
        os.remove(file_path)
