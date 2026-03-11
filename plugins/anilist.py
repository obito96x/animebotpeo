"""
AniList GraphQL API integration
Enhanced with better poster generation
From MangaPoster repo - DO NOT MODIFY
"""

import aiohttp
from typing import Optional, Dict, Any
import re

ANILIST_API = "https://graphql.anilist.co"

MANGA_QUERY = """
query ($search: String) {
  Media(search: $search, type: MANGA) {
    id
    title {
      romaji
      english
      native
    }
    format
    status
    chapters
    averageScore
    meanScore
    genres
    countryOfOrigin
    seasonYear
    startDate {
      year
    }
    description(asHtml: false)
    coverImage {
      extraLarge
      large
      medium
    }
  }
}
"""

ANIME_QUERY = """
query ($search: String) {
  Media(search: $search, type: ANIME) {
    id
    title {
      romaji
      english
      native
    }
    format
    status
    episodes
    averageScore
    meanScore
    genres
    season
    seasonYear
    startDate {
      year
    }
    description(asHtml: false)
    coverImage {
      extraLarge
      large
      medium
    }
  }
}
"""

SEARCH_QUERY = """
query ($search: String, $type: MediaType) {
  Page(perPage: 10) {
    media(search: $search, type: $type) {
      id
      title {
        romaji
        english
        native
      }
      format
      status
      seasonYear
      startDate {
        year
      }
      coverImage {
        medium
      }
    }
  }
}
"""

async def search_anilist(query: str, media_type: str = "MANGA") -> list:
    """Search for multiple Media results on AniList"""
    variables = {"search": query, "type": media_type.upper()}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                ANILIST_API,
                json={"query": SEARCH_QUERY, "variables": variables},
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status != 200: return []
                data = await response.json()
                
                if "errors" in data:
                    print(f"AniList API Error: {data['errors']}")
                    return []
                
                media_list = data.get("data", {}).get("Page", {}).get("media", [])
                
                results = []
                for m in media_list:
                    title_data = m.get("title", {})
                    title = title_data.get("english") or title_data.get("romaji") or title_data.get("native")
                    # Try seasonYear first, then startDate year
                    year = m.get("seasonYear") or (m.get("startDate") or {}).get("year") or "N/A"
                    results.append({
                        "id": m["id"],
                        "title": title,
                        "year": year,
                        "type": (m.get("format") or "N/A").replace("_", " ").title()
                    })
                return results
    except Exception as e:
        print(f"AniList Search Error: {e}")
        return []

async def fetch_manga_details(manga_name: str = None, anilist_id: int = None) -> Optional[Dict[str, Any]]:
    """
    Fetch manga details from AniList API
    Returns formatted data ready for poster generation
    """
    if anilist_id:
        query = MANGA_QUERY.replace("query ($search: String)", "query ($id: Int)").replace("search: $search", "id: $id")
        variables = {"id": anilist_id}
    else:
        query = MANGA_QUERY
        variables = {"search": manga_name}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                ANILIST_API,
                json={"query": query, "variables": variables},
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                
                if "errors" in data:
                    return None
                
                media = data.get("data", {}).get("Media")
                if not media:
                    return None
                
                # Extract title (priority: english > romaji > native)
                title = media["title"].get("english") or media["title"].get("romaji") or media["title"].get("native")
                
                # Format manga type (Detect Manhwa/Manhua)
                country = media.get("countryOfOrigin")
                manga_format = media.get("format", "MANGA")
                
                if country == "KR":
                    manga_type = "Manhwa"
                elif country == "CN":
                    manga_type = "Manhua"
                else:
                    manga_type = manga_format.replace("_", " ").title() if manga_format else "Manga"
                
                # Format status
                status = media.get("status", "Unknown")
                if status:
                    status = status.replace("_", " ").title()
                
                # Get chapters
                chapters = media.get("chapters")
                chapters_str = str(chapters) if chapters else "Unknown"
                
                # If chapters are Unknown, search on websites
                if chapters_str == "Unknown":
                    try:
                        from TG.search import search_all
                        from TG.storage import web_data
                        
                        # Create a dummy status object for search_all
                        class DummyStatus:
                            async def edit_message_caption(self, text):
                                pass  # Silent
                        
                        dummy_sts = DummyStatus()
                        
                        print(f"🔍 Searching websites for '{manga_name}' chapters...")
                        
                        # Search for manga on all websites
                        results, _, _ = await search_all(manga_name, dummy_sts, max_concurrent=3)
                        
                        if results and len(results) > 0:
                            # Get the first result and fetch its chapters
                            first_result = results[0]
                            
                            # Find the web instance for this result
                            web_instance = None
                            for web_name, web in web_data.items():
                                if hasattr(web, 'url') and web.url in first_result.get('url', ''):
                                    web_instance = web
                                    break
                            
                            if web_instance:
                                try:
                                    # Fetch manga details with chapters
                                    manga_data = await web_instance.get_chapters(first_result)
                                    
                                    if manga_data and 'chapters' in manga_data and manga_data['chapters']:
                                        # Extract chapter numbers from chapter list
                                        max_chapter = 0
                                        for chapter_info in manga_data['chapters']:
                                            chapter_name = chapter_info[0] if isinstance(chapter_info, (list, tuple)) else str(chapter_info)
                                            
                                            # Extract numbers from chapter name
                                            numbers = re.findall(r'\d+(?:\.\d+)?', chapter_name)
                                            if numbers:
                                                try:
                                                    chapter_num = float(numbers[0])
                                                    if chapter_num > max_chapter:
                                                        max_chapter = chapter_num
                                                except:
                                                    pass
                                        
                                        if max_chapter > 0:
                                            chapters_str = str(int(max_chapter))
                                            print(f"✅ Found latest chapter from {web_instance.sf}: {chapters_str}")
                                except Exception as e:
                                    print(f"⚠️ Error fetching chapters from website: {e}")
                    except Exception as e:
                        print(f"⚠️ Could not search websites for chapters: {e}")
                        import traceback
                        traceback.print_exc()
                
                # Get rating
                rating = media.get("meanScore") or media.get("averageScore")
                rating_str = f"{rating}%" if rating else "Not Rated"
                
                # Get year
                year = media.get("seasonYear") or (media.get("startDate") or {}).get("year") or ""
                
                # Get genres
                genres = media.get("genres", [])
                genres_str = ", ".join(genres) if genres else "Unknown"
                
                # Clean synopsis
                synopsis = media.get("description", "No synopsis available")
                
                # Remove HTML tags first
                synopsis = synopsis.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
                synopsis = synopsis.replace("<i>", "").replace("</i>", "")
                synopsis = synopsis.replace("<b>", "").replace("</b>", "")
                synopsis = synopsis.replace("<p>", "").replace("</p>", "")
                synopsis = synopsis.replace("<em>", "").replace("</em>", "")
                synopsis = synopsis.replace("<strong>", "").replace("</strong>", "")
                
                # Clean HTML entities
                synopsis = synopsis.replace("&quot;", '"').replace("&#039;", "'")
                synopsis = synopsis.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                synopsis = synopsis.replace("&nbsp;", " ").replace("&ndash;", "-").replace("&mdash;", "—")
                
                # Remove any remaining HTML-like patterns
                synopsis = re.sub(r'&[a-z]+;', '', synopsis)  # Remove any other HTML entities
                synopsis = re.sub(r'<[^>]+>', '', synopsis)    # Remove any remaining HTML tags
                
                # Clean up whitespace
                synopsis = " ".join(synopsis.split())
                
                # Limit synopsis length to 400 characters
                if len(synopsis) > 400:
                    synopsis = synopsis[:397] + "..."
                
                # Get cover image (highest quality available)
                cover_image = media.get("coverImage", {})
                cover_url = cover_image.get("extraLarge") or cover_image.get("large") or cover_image.get("medium")
                
                # AniList provides ready-made poster images at img.anili.st
                anilist_id = media.get("id")
                poster_url = f"https://img.anili.st/media/{anilist_id}" if anilist_id else None
                
                return {
                    "id": anilist_id,
                    "title": title,
                    "type": manga_type,
                    "status": status,
                    "chapters": chapters_str,
                    "rating": rating_str,
                    "genres": genres_str,
                    "synopsis": synopsis,
                    "cover_image": cover_url,
                    "poster_url": poster_url,
                    "year": str(year)
                }
                
    except Exception as e:
        print(f"❌ Error fetching manga from AniList: {e}")
        import traceback
        traceback.print_exc()
        return None

async def fetch_anime_details(anime_name: str = None, anilist_id: int = None) -> Optional[Dict[str, Any]]:
    """Fetch anime details from AniList API"""
    if anilist_id:
        query = ANIME_QUERY.replace("query ($search: String)", "query ($id: Int)").replace("search: $search", "id: $id")
        variables = {"id": anilist_id}
    else:
        query = ANIME_QUERY
        variables = {"search": anime_name}
        
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                ANILIST_API,
                json={"query": query, "variables": variables},
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status != 200: return None
                data = await response.json()
                media = data.get("data", {}).get("Media")
                if not media: return None
                
                title = media["title"].get("english") or media["title"].get("romaji") or media["title"].get("native")
                status = media.get("status", "Unknown").replace("_", " ").title()
                episodes = str(media.get("episodes") or "Unknown")
                year = str(media.get("seasonYear") or "")
                anime_format = media.get("format", "TV").replace("_", " ").title()
                
                rating = media.get("meanScore") or media.get("averageScore")
                rating_str = f"{rating}%" if rating else "Not Rated"
                genres_str = ", ".join(media.get("genres", [])) or "Unknown"
                
                synopsis = media.get("description", "No synopsis available")
                synopsis = re.sub(r'<[^>]+>', '', synopsis)
                synopsis = " ".join(synopsis.split())
                if len(synopsis) > 400: synopsis = synopsis[:397] + "..."
                
                cover_image = media.get("coverImage", {}).get("extraLarge")
                
                return {
                    "id": media.get("id"),
                    "title": title,
                    "type": anime_format,
                    "status": status,
                    "episodes": episodes,
                    "rating": rating_str,
                    "genres": genres_str,
                    "synopsis": synopsis,
                    "cover_image": cover_image,
                    "year": year
                }
    except Exception as e:
        print(f"AniList Anime Error: {e}")
        return None
