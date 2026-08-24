import asyncio
import sys
import codecs
from database import connect_db, messages_col

# Force UTF-8 stdout
sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

async def run():
    await connect_db()
    c = messages_col()
    cursor = c.find().sort("message_date", -1).limit(10)
    async for m in cursor:
        text = m.get("message_text", "")
        # Safe print ignoring errors
        print(str(m.get("message_date")), repr(text[:50]), str(m.get("opportunity_id")), str(m.get("category")), str(m.get("processing_error")))

if __name__ == "__main__":
    asyncio.run(run())
