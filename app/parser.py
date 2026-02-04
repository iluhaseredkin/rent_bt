import os
import re
import logging
from datetime import datetime, timedelta
from telethon import TelegramClient
from telethon.sessions import StringSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from .database import AsyncSessionLocal
from .models import Listing

logger = logging.getLogger(__name__)

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
TELETHON_SESSION = os.getenv("TELETHON_SESSION")

# From qu_parse.py
CITY_MAPPING = {
    'batumi_arendaa': 'Batumi',
    'kvartiravbatumi': 'Batumi',
    'kobuletiarenda': 'Kobuleti',
    'arenda_v_tbilise': 'Tbilisi',
    'tbilisi_arendaa': 'Tbilisi',
    'alaniya_arenda': 'Alanya',
    'apartamenty_alanya': 'Alanya',
    'alania_tipical': 'Alanya',
    'antaliya_arenda': 'Antalya',
    'Antalya_realestates': 'Antalya',
    'stambyl_arenda': 'Istanbul',
    'Istanbul_shat': 'Istanbul',
    'novisad_stan': 'NoviSad',
    'erevan_kvartira': 'Yerevan',
    'standardrealty': 'Yerevan',
    'kvartiraverevane1': 'Yerevan',
    'chernogoria_realty': 'Montenegro',
    'Montenegro_sell_rent': 'Montenegro',
    'serbiya_arenda': 'Serbia',
    'rentalserbia': 'Serbia',
    'beograd_stan': 'Belgrade',
    'flattorentbelgrade': 'Belgrade',
    'fethiye_rent': 'Fethiye',
    'housemarmaris': 'Marmaris',
    'rentinlisbon': 'Lisbon',
    'belkaspain': 'Barcelona'
}

CHANNELS = list(CITY_MAPPING.keys())

def extract_prices(text):
    if not text:
        return None
    prices = re.findall(r'\d+\s*(?:\$|USD|долл|€|евро|лир|TL|AMD|֏|драм)', text)
    valid_prices = [float(re.sub(r'[^\d.]', '', price)) for price in prices if
                    100 < float(re.sub(r'[^\d.]', '', price)) < 1000000]
    if valid_prices:
        return valid_prices[0]
    return None

def detect_currency(text):
    if not text:
        return None
    if any(x in text for x in ['$', 'USD', 'долл']):
        return 'USD'
    if any(x in text for x in ['€', 'евро']):
        return 'EUR'
    if any(x in text for x in ['лир', 'TL']):
        return 'TRY'
    if any(x in text for x in ['руб', '₽']):
        return 'RUB'
    if any(x in text for x in ['֏', 'AMD', 'драм']):
        return 'AMD'
    return None

def convert_to_usd(price, currency):
    if not price or not currency:
        return None
    
    # Updated rates (approx)
    rates = {
        'USD': 1.0,
        'EUR': 1.08, # EUR to USD
        'TRY': 0.03, # TRY to USD
        'RUB': 0.011, # RUB to USD
        'AMD': 0.0025 # AMD to USD
    }
    
    rate = rates.get(currency, 1.0)
    return round(price * rate, 2)

async def run_parser():
    if not TELETHON_SESSION:
        logger.error("TELETHON_SESSION is missing. Parser cannot start.")
        return

    logger.info("Starting parser...")
    
    async with TelegramClient(StringSession(TELETHON_SESSION), API_ID, API_HASH) as client:
        # Check auth
        if not await client.is_user_authorized():
             logger.error("Client is not authorized. Please generate a valid session string.")
             return

        async with AsyncSessionLocal() as db_session:
            for channel_username in CHANNELS:
                try:
                    logger.info(f"Parsing channel: {channel_username}")
                    entity = await client.get_entity(channel_username)
                    messages = await client.get_messages(entity, limit=50) # Limit per run to avoid spamming
                    
                    for message in messages:
                        if not message.text:
                            continue
                            
                        # Keywords filter logic from original
                        keywords = ['$', 'USD', 'долл', 'EUR', '€', 'евро', 'TL', 'лир', '֏', 'драм', 'AMD']
                        if not any(k in message.text for k in keywords):
                            continue
                            
                        # Extract data
                        price = extract_prices(message.text)
                        if not price:
                            continue
                            
                        currency = detect_currency(message.text)
                        usd_price = convert_to_usd(price, currency)
                        city = CITY_MAPPING.get(channel_username, "Unknown")
                        link = f'https://t.me/{channel_username}/{message.id}'
                        
                        # Upsert logic
                        stmt = insert(Listing).values(
                            message_id=message.id,
                            channel_username=channel_username,
                            date=message.date.replace(tzinfo=None), # naive for DB
                            text=message.text,
                            link=link,
                            price_original=price,
                            currency=currency,
                            price_usd=usd_price,
                            city=city
                        ).on_conflict_do_update(
                            index_elements=['link'],
                            set_={
                                'price_usd': usd_price,
                                'text': message.text
                            }
                        )
                        await db_session.execute(stmt)
                    
                    await db_session.commit()
                except Exception as e:
                    logger.error(f"Error parsing {channel_username}: {e}")
                    await db_session.rollback()

    logger.info("Parser finished.")
