import asyncio
from database import connect_db, messages_col

async def run():
    await connect_db()
    c = messages_col()
    cursor = c.find({"processing_error": {"$ne": None}}).sort("message_date", -1).limit(5)
    async for m in cursor:
        print(m.get("message_date"), repr(m.get("message_text")[:50]), m.get("processing_error"))

if __name__ == "__main__":
    asyncio.run(run())
