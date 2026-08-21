"""
setup_session.py — One-time script to generate a Telethon session string.

Run this ONCE to authenticate with your Telegram account.
The resulting session string goes into .env as TELEGRAM_SESSION_STRING.

Usage:
  python setup_session.py

You will be prompted for your phone number and the code Telegram sends you.
After that, a session string is printed — copy it to .env.
"""
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

print("=" * 60)
print("  Telethon Session Setup")
print("  Get credentials from: https://my.telegram.org")
print("=" * 60)

api_id = int(input("Enter your api_id: ").strip())
api_hash = input("Enter your api_hash: ").strip()


async def main():
    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.start()

    session_string = client.session.save()
    print("\n" + "=" * 60)
    print("✅ Session string generated successfully!")
    print("Copy the line below into your .env file:\n")
    print(f"TELEGRAM_SESSION_STRING={session_string}")
    print("=" * 60)

    # Find your group ID
    print("\nYour Telegram groups/channels:")
    async for dialog in client.iter_dialogs():
        if dialog.is_group or dialog.is_channel:
            print(f"  ID: {dialog.id}  |  Name: {dialog.name}")

    print("\nCopy the group ID you want to monitor and add it as:")
    print("PLACEMENT_GROUP_ID=<the_id>")

    await client.disconnect()


asyncio.run(main())
