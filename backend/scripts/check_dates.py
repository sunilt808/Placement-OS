import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import connect_db, opportunities_col

async def check():
    await connect_db()
    col = opportunities_col()
    async for opp in col.find({}, {'telegram_message_date': 1, 'company': 1}):
        print(opp)

if __name__ == "__main__":
    asyncio.run(check())
