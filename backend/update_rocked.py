import asyncio
from database import connect_db, opportunities_col

async def run():
    await connect_db()
    c = opportunities_col()
    result = await c.update_many({"company": {"$regex": "RockED"}}, {"$set": {"cse_relevance_score": 60, "is_cse_relevant": True}})
    print("Updated:", result.modified_count)

if __name__ == "__main__":
    asyncio.run(run())
