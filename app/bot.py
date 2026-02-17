import os
import logging
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .database import AsyncSessionLocal
from .models import User, Listing, Stat
from .parser import CITY_MAPPING, run_parser

logger = logging.getLogger(__name__)

# Constants
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Initialize Bot
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage()) # Memory is fine for FSM flow if we persist result

class UserState(StatesGroup):
    choosing_city = State()
    asking_price_limit = State()

async def log_stat(user_id, action, details=None):
    async with AsyncSessionLocal() as session:
        session.add(Stat(user_id=user_id, action=action, details=details))
        await session.commit()

async def get_or_create_user(user_id, username, first_name):
    async with AsyncSessionLocal() as session:
        stmt = pg_insert(User).values(
            user_id=user_id,
            username=username,
            first_name=first_name
        ).on_conflict_do_update(
            index_elements=['user_id'],
            set_={'last_interaction': pg_insert(User).excluded.last_interaction}
        )
        await session.execute(stmt)
        await session.commit()

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    await get_or_create_user(user_id, message.from_user.username, message.from_user.first_name)
    await log_stat(user_id, "start")
    
    cities = sorted(list(set(CITY_MAPPING.values())))
    keyboard = [[types.KeyboardButton(text=city)] for city in cities]
    markup = types.ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await message.answer(
        "Привет! Это бот для поиска жилья в аренду. Ежедневно в 10 утра (UTC) он присылает обновления. Для начала выберите город:",
        reply_markup=markup
    )
    await state.set_state(UserState.choosing_city)

@dp.message(Command("restart"))
async def cmd_restart(message: types.Message, state: FSMContext):
    await log_stat(message.from_user.id, "restart")
    await state.clear()
    await cmd_start(message, state)

@dp.message(Command("info"))
async def cmd_info(message: types.Message):
    await message.answer("Этот бот ищет аренду жилья. /restart чтобы начать заново.")

@dp.message(UserState.choosing_city)
async def process_city(message: types.Message, state: FSMContext):
    city = message.text
    valid_cities = set(CITY_MAPPING.values())
    
    if city not in valid_cities:
        await message.answer("Пожалуйста, выберите город из списка.")
        return

    await state.update_data(city=city)
    
    # Save preference to DB
    async with AsyncSessionLocal() as session:
        stmt = update(User).where(User.user_id == message.from_user.id).values(selected_city=city)
        await session.execute(stmt)
        await session.commit()
    
    await log_stat(message.from_user.id, "choose_city", city)
    
    # Send histogram (Placeholder for now, or generate on fly)
    # await generate_histogram(city) 
    
    await message.answer(
        f"Вы выбрали {city}. Укажите ваш бюджет в USD (минимум и максимум через пробел, например: 300 1000):",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(UserState.asking_price_limit)

@dp.message(UserState.asking_price_limit)
async def process_price(message: types.Message, state: FSMContext):
    try:
        parts = message.text.split()
        if len(parts) != 2:
            raise ValueError
        min_p, max_p = map(int, parts)
        if min_p < 0 or max_p < min_p:
            raise ValueError
    except ValueError:
        await message.answer("Введите два числа через пробел (минимум и максимум). Например: 200 800")
        return

    data = await state.get_data()
    city = data.get("city")
    
    # Save to DB
    async with AsyncSessionLocal() as session:
        stmt = update(User).where(User.user_id == message.from_user.id).values(min_price=min_p, max_price=max_p)
        await session.execute(stmt)
        await session.commit()
        
        # Fetch Top 5
        result = await session.execute(
            select(Listing)
            .where(Listing.city == city)
            .where(Listing.price_usd >= min_p)
            .where(Listing.price_usd <= max_p)
            .order_by(Listing.date.desc())
            .limit(5)
        )
        listings = result.scalars().all()

    await log_stat(message.from_user.id, "set_price", f"{min_p}-{max_p}")

    response = "Готово! Подписка оформлена.\n\nТоп последних предложений:\n"
    if listings:
        for l in listings:
            response += f"📅 {l.date.strftime('%Y-%m-%d')} | 💰 {l.price_usd} USD\n🔗 {l.link}\n\n"
    else:
        response += "Пока ничего не найдено в этом диапазоне."

    await message.answer(response)
    
    # Optional: Offer to restart or change city
    markup = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="Сменить город")]], 
        resize_keyboard=True
    )
    await message.answer("Ждите ежедневную рассылку!", reply_markup=markup)
    await state.clear() # Clear state but keep User in DB

@dp.message(F.text == "Сменить город")
async def change_city(message: types.Message, state: FSMContext):
    await cmd_restart(message, state)

async def send_daily_notifications():
    logger.info("Starting daily notifications...")
    async with AsyncSessionLocal() as session:
        # Get all users
        result = await session.execute(select(User).where(User.is_active == True))
        users = result.scalars().all()
        
        for user in users:
            try:
                # Find new listings? Or just top listings for today?
                # "Ежедневно в 10 утра он присылает обновления по вашему запросу." - implies fresh items or best items.
                # Let's get items from the last 24 hours.
                since = datetime.utcnow() - timedelta(days=1)
                
                res = await session.execute(
                    select(Listing)
                    .where(Listing.city == user.selected_city)
                    .where(Listing.price_usd >= user.min_price)
                    .where(Listing.price_usd <= user.max_price)
                    .where(Listing.date >= since)
                    .order_by(Listing.date.desc())
                    .limit(5)
                )
                listings = res.scalars().all()
                
                if listings:
                    msg = "🔔 Ежедневная подборка:\n\n"
                    for l in listings:
                        msg += f"📅 {l.date.strftime('%Y-%m-%d')} | 💰 {l.price_usd} USD\n🔗 {l.link}\n\n"
                    await bot.send_message(user.user_id, msg)
                    await log_stat(user.user_id, "notification_sent")
                else:
                    # Optional: send "nothing new today" or stay silent
                    pass
            except Exception as e:
                logger.error(f"Failed to send to {user.user_id}: {e}")

