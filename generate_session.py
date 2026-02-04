from telethon.sync import TelegramClient
from telethon.sessions import StringSession

# Get these from https://my.telegram.org
API_ID = input("Enter API_ID: ")
API_HASH = input("Enter API_HASH: ")

with TelegramClient(StringSession(), API_ID, API_HASH) as client:
    print("\n--- COPY THE SESSION STRING BELOW ---")
    print(client.session.save())
    print("-------------------------------------")
    print("Paste this into your Railway Environment Variables as TELETHON_SESSION")
