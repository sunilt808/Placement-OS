"""
Dry-run: report which stored opportunities would be fixed, without writing.
"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import connect_db, close_db, opportunities_col, messages_col
from scripts.fix_company_names import is_bad_company, is_bad_role

async def main():
    await connect_db()
    col = opportunities_col()
    bad_c = bad_r = total = 0
    names = []
    async for opp in col.find({}):
        total += 1
        c, r = opp.get("company"), opp.get("role")
        if is_bad_company(c):
            bad_c += 1
            names.append(("COMPANY", c))
        if is_bad_role(r):
            bad_r += 1
            names.append(("ROLE", r))
    print(f"Total opportunities: {total}")
    print(f"Bad company names  : {bad_c}")
    print(f"Bad role names     : {bad_r}")
    print("=" * 55)
    for kind, val in names[:60]:
        print(f"  {kind}: {val!r}")
    await close_db()

asyncio.run(main())
