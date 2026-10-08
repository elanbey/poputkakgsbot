import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
import aiosqlite
from dotenv import load_dotenv

# Жүктөө / Загрузка переменных окружения
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "ВСТАВЬ_СЮДА_ТОКЕН_ОТ_BOTFATHER")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- БАЗА ДАННЫХ (SQLite) ---
async def init_db():
    async with aiosqlite.connect("poputka.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS rides (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                driver_id INTEGER,
                driver_name TEXT,
                phone TEXT,
                from_city TEXT,
                to_city TEXT,
                date_time TEXT,
                car_info TEXT,
                seats INTEGER,
                price INTEGER,
                parcels_ok INTEGER,
                is_active INTEGER DEFAULT 1
            )
        """)
        await db.commit()

# --- СОСТОЯНИЯ (FSM) ---
class NewRide(StatesGroup):
    direction = State()
    date_time = State()
    car_info = State()
    seats = State()
    price = State()
    parcels = State()
    phone = State()

class SearchRide(StatesGroup):
    direction = State()

# --- КЛАВИАТУРЫ ---
def get_main_menu(lang='ru'):
    if lang == 'ky':
        kb = [
            [KeyboardButton(text="🚗 Сапар кошуу (Айдоочу)"), KeyboardButton(text="🔍 Унаа издөө (Жүргүнчү)")],
            [KeyboardButton(text="📦 Посылка жөнөтүү"), KeyboardButton(text="🌐 Тилди алмаштыруу")]
        ]
    else:
        kb = [
            [KeyboardButton(text="🚗 Добавить поездку (Водитель)"), KeyboardButton(text="🔍 Найти машину (Пассажир)")],
            [KeyboardButton(text="📦 Отправить посылку"), KeyboardButton(text="🌐 Сменить язык")]
        ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_routes_kb():
    routes = [
        ("Бишкек ➡️ Ош", "Бишкек-Ош"),
        ("Ош ➡️ Бишкек", "Ош-Бишкек"),
        ("Бишкек ➡️ Каракол", "Бишкек-Каракол"),
        ("Каракол ➡️ Бишкек", "Каракол-Бишкек"),
        ("Бишкек ➡️ Нарын", "Бишкек-Нарын"),
        ("Бишкек ➡️ Талас", "Бишкек-Талас")
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=f"route_{data}")] for text, data in routes]
    )

# --- ОБРАБОТЧИКИ (HANDLERS) ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Кыргызча 🇰🇬", callback_data="lang_ky")],
        [InlineKeyboardButton(text="Русский 🇷🇺", callback_data="lang_ru")]
    ])
    await message.answer("Саламатсызбы! БТБ Жолго сервисине кош келдиңиз! Тилди тандаңыз / Здравствуйте! Выберите язык:", reply_markup=kb)

@dp.callback_query(F.data.startswith("lang_"))
async def set_language(call: types.CallbackQuery):
    lang = call.data.split("_")[1]
    msg = "Башкы меню (БТБ Жолго - Бай Түшүм Банк):" if lang == "ky" else "Главное меню (БТБ Жолго - Бай Тушум Банк):"
    await call.message.delete()
    await call.message.answer(msg, reply_markup=get_main_menu(lang))

# --- ВОДИТЕЛЬ: СОЗДАНИЕ ПОЕЗДКИ ---
@dp.message(F.text.in_(["🚗 Добавить поездку (Водитель)", "🚗 Сапар кошуу (Айдоочу)"]))
async def driver_start(message: types.Message, state: FSMContext):
    await state.set_state(NewRide.direction)
    await message.answer("Маршрутту тандаңыз / Выберите направление:", reply_markup=get_routes_kb())

@dp.callback_query(F.data.startswith("route_"), NewRide.direction)
async def driver_route(call: types.CallbackQuery, state: FSMContext):
    route_raw = call.data.replace("route_", "")
    from_c, to_c = route_raw.split("-")
    await state.update_data(from_city=from_c, to_city=to_c)
    await state.set_state(NewRide.date_time)
    await call.message.answer("Кетүүчү убактысы жана күнү? (Мисалы: Бүгүн 19:00 же 12-Октябрь 09:00)\n\nДата и время выезда:")

@dp.message(NewRide.date_time)
async def driver_time(message: types.Message, state: FSMContext):
    await state.update_data(date_time=message.text)
    await state.set_state(NewRide.car_info)
    await message.answer("Машинанын маркасы жана номери? (Мисалы: Toyota Alphard 01KG777ABC)\n\nМарка и госномер машины:")

@dp.message(NewRide.car_info)
async def driver_car(message: types.Message, state: FSMContext):
    await state.update_data(car_info=message.text)
    await state.set_state(NewRide.seats)
    await message.answer("Канча бош орун бар? (Сан менен: 3)\n\nСколько свободных мест? (Укажите цифру):")

@dp.message(NewRide.seats)
async def driver_seats(message: types.Message, state: FSMContext):
    try:
        seats = int(message.text.strip())
        await state.update_data(seats=seats)
        await state.set_state(NewRide.price)
        await message.answer("Бир орундун баасы (сом менен)?\n\nЦена за 1 место (в сомах):")
    except ValueError:
        await message.answer("Сураныч, сан менен жазыңыз (мисалы: 4):")

@dp.message(NewRide.price)
async def driver_price(message: types.Message, state: FSMContext):
    try:
        price = int(message.text.strip())
        await state.update_data(price=price)
        await state.set_state(NewRide.parcels)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Ооба / Да 📦", callback_data="parcel_1")],
            [InlineKeyboardButton(text="Жок / Нет ❌", callback_data="parcel_0")]
        ])
        await message.answer("Посылка / жүк аласызбы? / Берете ли посылки?", reply_markup=kb)
    except ValueError:
        await message.answer("Бааны сан менен жазыңыз / Введите сумму числом:")

@dp.callback_query(F.data.startswith("parcel_"), NewRide.parcels)
async def driver_parcel(call: types.CallbackQuery, state: FSMContext):
    parcels_ok = int(call.data.split("_")[1])
    await state.update_data(parcels_ok=parcels_ok)
    await state.set_state(NewRide.phone)
    btn = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📱 Номерди жөнөтүү", request_contact=True)]], resize_keyboard=True)
    await call.message.answer("Байланыш телефонуңузду жазыңыз (0700123456):\n\nОтправьте ваш номер телефона:", reply_markup=btn)

@dp.message(NewRide.phone)
async def driver_finish(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number if message.contact else message.text
    data = await state.get_data()
    
    async with aiosqlite.connect("poputka.db") as db:
        await db.execute("""
            INSERT INTO rides (driver_id, driver_name, phone, from_city, to_city, date_time, car_info, seats, price, parcels_ok)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            message.from_user.id,
            message.from_user.full_name,
            phone,
            data['from_city'],
            data['to_city'],
            data['date_time'],
            data['car_info'],
            data['seats'],
            data['price'],
            data['parcels_ok']
        ))
        await db.commit()
    
    await state.clear()
    await message.answer("✅ Сапарыңыз БТБ Жолго сервисине кошулду! Жүргүнчүлөр сиз менен түздөн-түз WhatsApp аркылуу байланышат.\n\nПоездка опубликована!", reply_markup=get_main_menu('ky'))

# --- ПАССАЖИР: ПОИСК ПОЕЗДКИ ---
@dp.message(F.text.in_(["🔍 Найти машину (Пассажир)", "🔍 Унаа издөө (Жүргүнчү)", "📦 Посылка жөнөтүү", "📦 Отправить посылку"]))
async def search_start(message: types.Message, state: FSMContext):
    await state.set_state(SearchRide.direction)
    await message.answer("Кайсы багыт боюнча керек? / Выберите маршрут:", reply_markup=get_routes_kb())

@dp.callback_query(F.data.startswith("route_"), SearchRide.direction)
async def search_results(call: types.CallbackQuery, state: FSMContext):
    route_raw = call.data.replace("route_", "")
    from_c, to_c = route_raw.split("-")
    
    async with aiosqlite.connect("poputka.db") as db:
        async with db.execute("""
            SELECT id, driver_name, phone, date_time, car_info, seats, price, parcels_ok 
            FROM rides 
            WHERE from_city = ? AND to_city = ? AND is_active = 1 
            ORDER BY id DESC LIMIT 5
        """, (from_c, to_c)) as cursor:
            rows = await cursor.fetchall()
            
    await state.clear()
    if not rows:
        await call.message.answer(f"😔 Азырынча {from_c} ➡️ {to_c} багыты боюнча активдүү унаалар жок.\n\nПока нет активных машин по этому маршруту.", reply_markup=get_main_menu())
        return

    for r in rows:
        parcels_str = "✅ Алат / Берет" if r[7] == 1 else "❌ Албайт / Не берет"
        clean_phone = r[2].replace("+", "").replace(" ", "")
        wa_link = f"https://wa.me/{clean_phone}"
        
        card = (
            f"🚘 <b>{r[4]}</b>\n"
            f"📍 {from_c} ➡️ {to_c}\n"
            f"⏰ <b>Убактысы/Время:</b> {r[3]}\n"
            f"💺 <b>Бош орун/Мест:</b> {r[5]}\n"
            f"💰 <b>Баасы/Цена:</b> {r[6]} сом\n"
            f"📦 <b>Посылка:</b> {parcels_str}\n"
            f"👤 <b>Айдоочу/Водитель:</b> {r[1]}\n"
            f"📞 <b>Тел:</b> {r[2]}"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 WhatsApp аркылуу жазуу", url=wa_link)]
        ])
        await call.message.answer(card, parse_mode="HTML", reply_markup=kb)

async def main():
    await init_db()
    print(">>> Бот БТБ Жолго ийгиликтүү иштеди! Бот запущен и ожидает сообщений...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())