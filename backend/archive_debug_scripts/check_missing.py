import asyncio
from database import connect_db, messages_col

async def run():
    await connect_db()
    c = messages_col()
    cursor = c.find({"message_text": {"$regex": "AXA Global"}})
    async for m in cursor:
        print(m.get("message_date"), m.get("opportunity_id"), m.get("processing_error"), m.get("category"))
    
    print("---")
    cursor = c.find({"message_text": {"$regex": "RockED"}})
    async for m in cursor:
        print(m.get("message_date"), m.get("opportunity_id"), m.get("processing_error"), m.get("category"))

if __name__ == "__main__":
    asyncio.run(run())
