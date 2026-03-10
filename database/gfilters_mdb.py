import logging
from motor.motor_asyncio import AsyncIOMotorClient
from info import DATABASE_URI, DATABASE_NAME

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

# Use AsyncIOMotorClient instead of synchronous pymongo
myclient = AsyncIOMotorClient(DATABASE_URI)
mydb = myclient[DATABASE_NAME]

async def add_gfilter(gfilters, text, reply_text, btn, file, alert):
    mycol = mydb[str(gfilters)]
    data = {
        'text': str(text),
        'reply': str(reply_text),
        'btn': str(btn),
        'file': str(file),
        'alert': str(alert)
    }

    try:
        await mycol.update_one({'text': str(text)}, {"$set": data}, upsert=True)
    except Exception as e:
        logger.exception('Some error occurred!', exc_info=True)
             
async def find_gfilter(gfilters, name):
    mycol = mydb[str(gfilters)]
    
    query = mycol.find({"text": name})
    try:
        async for file in query:
            reply_text = file.get('reply')
            btn = file.get('btn')
            fileid = file.get('file')
            alert = file.get('alert')
            return reply_text, btn, alert, fileid
    except:
        pass
    return None, None, None, None

async def get_gfilters(gfilters):
    mycol = mydb[str(gfilters)]
    texts = []
    query = mycol.find()
    try:
        async for file in query:
            text = file.get('text')
            if text:
                texts.append(text)
    except:
        pass
    return texts

async def delete_gfilter(message, text, gfilters):
    mycol = mydb[str(gfilters)]
    myquery = {'text': text}
    
    count = await mycol.count_documents(myquery)
    if count >= 1:
        await mycol.delete_one(myquery)
        await message.reply_text(
            f"'`{text}`' deleted. I'll not respond to that gfilter anymore.",
            quote=True
        )
    else:
        await message.reply_text("Couldn't find that gfilter!", quote=True)

async def del_allg(message, gfilters):
    collection_names = await mydb.list_collection_names()
    if str(gfilters) not in collection_names:
        await message.edit_text("Nothing to Remove!")
        return

    mycol = mydb[str(gfilters)]
    try:
        await mycol.drop()
        await message.edit_text("All gfilters have been removed!")
    except:
        await message.edit_text("Couldn't remove all gfilters!")
        return

async def count_gfilters(gfilters):
    mycol = mydb[str(gfilters)]
    count = await mycol.count_documents({})
    return False if count == 0 else count

async def gfilter_stats():
    collections = await mydb.list_collection_names()

    if "CONNECTION" in collections:
        collections.remove("CONNECTION")

    totalcount = 0
    for collection in collections:
        mycol = mydb[collection]
        count = await mycol.count_documents({})
        totalcount += count

    totalcollections = len(collections)
    return totalcollections, totalcount
