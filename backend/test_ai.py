import asyncio
from datetime import datetime
from services.ai_service import classify_and_extract

text1 = """MPORTANT NOTE – Please Read Carefully Before Confirming Your Interest

Work Shift: 10:00 AM to 7:00 PM
Cab Facility: Not Provided
Leave Policy: 1 Leave per Month
Office Location: Bangalore (Candidates should be willing to work from either of the below locations, as no cab facility is provided.)

* Mynata Tech Park
* Ecopolis

PPO (Pre-Placement Offer):
A PPO is not guaranteed. The final placement opportunity will strictly depend on:
Your performance during the apprenticeship, and
The company's hiring requirements and available openings at that time.

Please ensure you are comfortable with the above terms before confirming your participation in the selection process.
____________________________________________________________________

👉Campus Drive - AXA Global Business Services( Apprentice Opportunity) for 2027 Batch

About Company: At AXA Global Business Services, we believe in the power of partnerships, leveraging our expertise in business services and technology to support AXA entities in their core insurance operations, support functions, and digitization processes. We are committed to developing fresh and innovative approaches that surpass expectations and address unique challenges. Our passionate team is dedicated to driving innovation and pushing boundaries further, leveraging unparalleled technical expertise to deliver top-notch solutions that add outstanding value to AXA entities

Website: https://axagbs.com/
Location: Bangalore

Job Roles: 
• AD&M
• Analytics Data Science
• Cyber Security Engineering
• Python C# .Net
• Python Javascript
• Testing & Decom

Eligible Criteria: 
• Education: B.E/B.Tech/M.Tech
• Stream: CSE - Allied Branches 
• Percentage: Above 80% or 8CGPA Throughout at academics
• Passed out: 2027
• No Active Backlogs

Internship Details:
• Duration: 12 months (August 2026 Onwards)
• Stipend: 35,000 per month

Job Description: Refer the attachments

Interview Process:
• Online Test
• Technical
• HR

All students from above mentioned branches who are seriously interested are informed to register on or before 11:00AM 22nd Aug 2025

Registration Link: https://forms.gle/fzGFwyPPVa1tHru4A
"""

async def test():
    import os
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    res, _ = await classify_and_extract(text1, datetime.now())
    print("AXA Category:", res.category)
    print("AXA Company:", res.company)
    print("AXA Role:", res.role)
    print("AXA Confidence:", res.confidence)
    print("AXA is_cse_relevant:", res.is_cse_relevant)
    print("AXA score:", res.cse_relevance_score)

if __name__ == "__main__":
    asyncio.run(test())
