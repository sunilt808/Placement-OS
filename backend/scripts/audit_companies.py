"""
Check all company names in DB and list ones that look bad
"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import connect_db, opportunities_col

async def main():
    await connect_db()
    col = opportunities_col()
    print("All company names in DB:")
    print("=" * 60)
    async for opp in col.find({}, {"company": 1, "role": 1}):
        company = opp.get("company")
        role = opp.get("role")
        print(f"Company: {repr(company):40s} | Role: {repr(role)}")

asyncio.run(main())
