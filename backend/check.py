import asyncio
import pprint
from database import connect_db, opportunities_col

async def main():
    await connect_db()
    col = opportunities_col()
    async for opp in col.find().limit(3):
        pprint.pprint(opp)

asyncio.run(main())
