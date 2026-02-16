import os
import re
import logging
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient
from telethon.sessions import StringSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from .database import AsyncSessionLocal
from .database import AsyncSessionLocal
from .models import Listing, Channel

try:
    from currency_converter import CurrencyConverter
    currency_converter = CurrencyConverter()
except Exception as e:
    logging.getLogger(__name__).warning(f"Could not init CurrencyConverter: {e}. Using fallback rates.")
    currency_converter = None

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
    prices = re.findall(r'\d+\s*(?:\$|USD|долл|€|евро|лир|TL|AMD|֏|драм)', text, re.IGNORECASE)
    valid_prices = [float(re.sub(r'[^\d.]', '', price)) for price in prices if
                    100 < float(re.sub(r'[^\d.]', '', price)) < 1000000]
    if valid_prices:
        return valid_prices[0]
    return None

def detect_currency(text):
    if not text:
        return None
    t = text.upper()
    if any(x in t for x in ['$', 'USD', 'ДОЛЛ']):
        return 'USD'
    if any(x in t for x in ['€', 'ЕВРО', 'EUR']):
        return 'EUR'
    if any(x in t for x in ['ЛИР', 'TL', 'TRY']):
        return 'TRY'
    if any(x in t for x in ['РУБ', '₽', 'RUB']):
        return 'RUB'
    if any(x in t for x in ['֏', 'AMD', 'ДРАМ']):
        return 'AMD'
    return None

def convert_to_usd(price, currency):
    if not price or not currency:
        return None
    
    # Fallback rates
    rates = {
        'USD': 1.0,
        'EUR': 1.15, # EUR to USD
        'TRY': 0.023, # TRY to USD
        'RUB': 0.011, # RUB to USD
        'AMD': 0.0025 # AMD to USD
    }
    
    if currency == 'USD':
        return price

    if currency_converter:
        try:
            # CurrencyConverter uses standard codes
            code_map = {
                'EUR': 'EUR',
                'TRY': 'TRY',
                'RUB': 'RUB', # Might be outdated in some free datasets, but standard
                'AMD': 'AMD'  # Note: CurrencyConverter might not have AMD. Checking...
            }
            # If not in code_map, it might rely on library support. 
            # CurrencyConverter mainly supports ECB rates.
            # ECB rates usually include EUR, USD, TRY, etc. RUB is suspended.
            
            # Let's try to use it if standard code exists
            if currency in ['EUR', 'TRY']:
                return round(currency_converter.convert(price, currency, 'USD'), 2)
        except Exception:
            pass # Fallback

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
            # Fetch channels from DB
            result = await db_session.execute(select(Channel).where(Channel.status != 'inactive'))
            db_channels = result.scalars().all()
            
            if not db_channels:
                logger.warning("No channels found in DB to parse.")
                return

            for channel in db_channels:
                channel_username = channel.username
                try:
                    logger.info(f"Parsing channel: {channel_username}")
                    
                    # Update status to running? Or just log time
                    
                    try:
                        entity = await client.get_entity(channel_username)
                    except ValueError:
                         logger.error(f"Channel not found: {channel_username}")
                         channel.status = 'error'
                         channel.error_count += 1
                         await db_session.commit()
                         continue
                         
                    messages = await client.get_messages(entity, limit=100)
                    
                    batch_values = []

                    for message in messages:
                        if not message.text:
                            continue
                            
                        # Keywords filter
                        keywords = ['$', 'USD', 'долл', 'EUR', '€', 'евро', 'TL', 'лир', '֏', 'драм', 'AMD']
                        if not any(k in message.text for k in keywords):
                            continue
                            
                        # Extract data
                        price = extract_prices(message.text)
                        if not price:
                            continue
                            
                        currency = detect_currency(message.text)
                        usd_price = convert_to_usd(price, currency)
                        
                        # Use city from DB channel record
                        city = channel.city
                        
                        link = f'https://t.me/{channel_username}/{message.id}'
                        
                        batch_values.append({
                            'message_id': message.id,
                            'channel_username': channel_username,
                            'date': message.date.astimezone(timezone.utc).replace(tzinfo=None),
                            'text': message.text,
                            'link': link,
                            'price_original': price,
                            'currency': currency,
                            'price_usd': usd_price,
                            'city': city
                        })

                    if batch_values:
                        stmt = insert(Listing).values(batch_values)
                        stmt = stmt.on_conflict_do_update(
                            index_elements=['link'],
                            set_={
                                'price_usd': stmt.excluded.price_usd,
                                'text': stmt.excluded.text
                            }
                        )
                        await db_session.execute(stmt)
                        
                    # Update Channel stats
                    channel.last_parsed_at = datetime.now(timezone.utc)
                    channel.status = 'active'
                    channel.error_count = 0 
                    await db_session.commit()
                    
                    logger.info(f"Upserted {len(batch_values)} listings for {channel_username}")
                    
                except Exception as e:
                    logger.error(f"Error parsing {channel_username}: {e}")
                    channel.status = 'error'
                    channel.error_count += 1
                    try:
                        await db_session.commit()
                    except:
                        await db_session.rollback()

    logger.info("Parser finished.")
