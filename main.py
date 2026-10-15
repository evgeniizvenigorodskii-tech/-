import asyncio
import socket
import sqlite3
from datetime import datetime
from urllib.parse import quote
from aiohttp import TCPConnector
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# =====================================================================
# 🔑 8940583712:AAEHTlsV8AmRjewdv_-cxvF0ZCIKtChzjzw
# =====================================================================
BOT_TOKEN = "8940583712:AAEHTlsV8AmRjewdv_-cxvF0ZCIKtChzjzw"

# Регистрационные данные твоей Elantra XD
CAR_PROFILE = {
    "model": "Hyundai Elantra XD (2005)",
    "body_type": "Легковой хэтчбек (комби)",
    "color": "Бежевый",
    "vin": "KMHDN51BP5U157400",
    "plate": "М684ЕТ156",
    "sts": "9923768949",
    "pts": "Оригинал",
    "engine": "G4ED (1 599 см³ / 105 л.с.)",
    "engine_num": "5039717 G4ED",
    "transmission": "Автомат (4-ст. АКПП F4A42)"
}

# Регламенты ТО (в км)
INTERVALS = {
    "oil_engine": {"name": "🛢 Масло ДВС + фильтр", "interval": 7500},
    "oil_atf": {"name": "⚙️ Масло АКПП (ATF SP-III)", "interval": 40000},
    "grm": {"name": "⛓ Ремень ГРМ + ролики + цепь", "interval": 60000},
    "drive_belts": {"name": "➰ Приводные ремни (ГУР/Ген/Конд)", "interval": 40000},
    "spark_plugs": {"name": "⚡ Свечи зажигания", "interval": 30000},
    "brake_fluid": {"name": "🛑 Тормозная жидкость (DOT-4)", "interval": 40000},
    "coolant": {"name": "❄️ Антифриз (G11 / Карбоксилатный)", "interval": 60000},
}

# База новых запчастей с ТОП-аналогами и привязкой к Autodoc
DEFAULT_PARTS = [
    # ТО и Фильтры
    ("ТО и фильтры", "Масляный фильтр ДВС", "26300-35505",
     "ТОП аналоги: Mann W811/80 (идёт в оригинале), Knecht/Mahle OC205, Vic C-307"),
    ("ТО и фильтры", "Шайба сливной пробки поддона", "21513-23001",
     "ТОП аналоги: Elring 813.036, Masuma M-49 (менять при каждой замене масла)"),
    ("ТО и фильтры", "Воздушный фильтр ДВС", "28113-2D000",
     "ТОП аналоги: Filtron AP183/1, Mann C2620, Parts-Mall PAA-018"),
    ("ТО и фильтры", "Салонный фильтр", "97133-2D000",
     "ТОП аналоги: Raf Filter RF001HY, TSN 9.7.115 (угольный), Filtron K1169"),
    ("ТО и фильтры", "Свечи зажигания (комплект 4 шт.)", "18814-11051",
     "ТОП аналоги: NGK BKR5ES-11 (лежит в оригинале), Denso K16PR-U11"),

    # Ремни и ГРМ (Мотор G4ED)
    ("Ремни и ГРМ", "Ремень ГРМ (111 зубьев)", "24312-26050",
     "ТОП аналоги: Gates 5479XS (лучший выбор), Contitech CT942, Dongil (оригинал конвейера)"),
    ("Ремни и ГРМ", "Ролик натяжителя ГРМ", "24410-26000",
     "ТОП аналоги: GMB GT10022 (идёт в оригинале!), INA 531 0118 20"),
    ("Ремни и ГРМ", "Ролик обводной ГРМ", "24810-26020",
     "ТОП аналоги: GMB GT10140 (идёт в оригинале!), INA 532 0309 20"),
    ("Ремни и ГРМ", "Межвальная цепь распредвалов", "24321-26020",
     "Ставить строго Оригинал Hyundai/Kia + прокладка клапанной крышки 22441-26020 (оригинал/Elring)"),
    ("Ремни и ГРМ", "Помпа (водяной насос)", "25100-26902",
     "ТОП аналоги: GMB GWHY-23A (поставляется на конвейер), Hepu P7797, Valeo WP-5016"),
    ("Ремни и ГРМ", "Ремень генератора и помпы", "25212-26021",
     "Размер 4PK875. ТОП аналоги: Gates 4PK875, Contitech 4PK875, Mitsuboshi"),
    ("Ремни и ГРМ", "Ремень компрессора кондиционера", "97713-2D100",
     "Размер 4PK850. ТОП аналоги: Gates 4PK850, Contitech 4PK850"),
    ("Ремни и ГРМ", "Ремень ГУР", "57170-2D101",
     "Клиновой ремень. ТОП аналоги: Gates 6461MC, Dongil, Contitech AVX13X865"),

    # АКПП (F4A42)
    ("АКПП", "Фильтр АКПП (внутренний)", "46321-22731",
     "Ставить Оригинал Hyundai/Kia или JS Asakashi JT426K (идёт сразу с прокладкой)"),
    ("АКПП", "Прокладка поддона АКПП", "45285-22010",
     "Оригинал Hyundai/Kia (либо сажать на серый герметик Reinz Reinzosil / Permatex)"),

    # Ходовка и Тормоза
    ("Ходовка и тормоза", "Стойка стабилизатора передняя (2 шт. одинаковые)", "54830-2D000",
     "ТОП аналоги: CTR CLKH-15 (идёт в оригинале, ходит по 50+ тыс. км), Lemforder"),
    ("Ходовка и тормоза", "Стойка стабилизатора задняя", "55530-29500",
     "ТОП аналоги: CTR CLKH-5 (поставщик конвейера), 555"),
    ("Ходовка и тормоза", "Шаровая опора переднего рычага", "54503-38A00",
     "ТОП аналоги: CTR CBKH-7 (лежит в коробке оригинала), Lemforder"),
    ("Ходовка и тормоза", "Сайлентблок переднего рычага задний (вертикальный)", "54584-2D000",
     "ТОП аналоги: CTR CVKH-19, Оригинал Hyundai"),
    ("Ходовка и тормоза", "Колодки тормозные передние", "58101-2DA50",
     "ТОП аналоги: Sangsin Hi-Q SP1147 (мягкие, не скрипят), Hankook Frixa FPH04, Kashiyama"),
    ("Ходовка и тормоза", "Колодки тормозные задние (дисковые)", "58302-2DA00",
     "ТОП аналоги: Sangsin Hi-Q SP1116, ICER, TRW"),
    ("Ходовка и тормоза", "Амортизаторы передние (Левый / Правый)", "54651-2D100",
     "ТОП аналоги: Mando EX546512D100 (оригинал с завода), Kayaba (KYB) 333305 / 333304")
]

# Популярные позиции для поиска Б/У на Авито (разборки Москва и МО)
AVITO_BU_PARTS = [
    ("⚙️ АКПП в сборе (4-ст. F4A42 под 1.6 G4ED)", "АКПП Hyundai Elantra XD 1.6 F4A42"),
    ("🔩 Двигатель G4ED 1.6 (столбик / с навесным)", "Двигатель G4ED 1.6 Hyundai Elantra XD"),
    ("🦴 Подрамник передний / задняя балка (живые без гнили)", "Подрамник балка Hyundai Elantra XD"),
    ("🚪 Крышка багажника Хэтчбек (5-я дверь)", "Крышка багажника Hyundai Elantra XD хэтчбек"),
    ("🛡 Крылья передние / Капот / Бампер", "Крыло капот бампер Hyundai Elantra XD"),
    ("🔌 Генератор / Стартер / Компрессор кондиционера", "Генератор стартер Hyundai Elantra XD G4ED"),
    ("🕹 Привод в сборе (ШРУС левый / правый АКПП)", "Привод Hyundai Elantra XD 1.6 АКПП"),
    ("💡 Фары передние / Фонари задние (хэтчбек)", "Фара фонарь Hyundai Elantra XD хэтчбек"),
]

DB_NAME = "elantra_garage.db"
router = Router()

# =====================================================================
# 🗄 БАЗА ДАННЫХ (SQLite)
# =====================================================================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS state_info (
            key TEXT PRIMARY KEY,
            val INTEGER
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS service_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            mileage INTEGER,
            category TEXT,
            description TEXT,
            cost INTEGER
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            name TEXT,
            article TEXT,
            note TEXT
        )
    """)
    defaults = [
        ("current_mileage", 0),
        ("owner_chat_id", 0),
        ("last_oil_engine", 0),
        ("last_oil_atf", 0),
        ("last_grm", 0),
        ("last_drive_belts", 0),
        ("last_spark_plugs", 0),
        ("last_brake_fluid", 0),
        ("last_coolant", 0),
    ]
    for k, v in defaults:
        cur.execute("INSERT OR IGNORE INTO state_info (key, val) VALUES (?, ?)", (k, v))

    # Обновим справочник артикулов до версии 2.0 (сохраняя пользовательские записи)
    cur.execute("SELECT COUNT(*) FROM parts")
    if cur.fetchone()[0] <= 14:
        cur.execute("DELETE FROM parts")
        cur.executemany(
            "INSERT INTO parts (category, name, article, note) VALUES (?, ?, ?, ?)",
            DEFAULT_PARTS
        )
    conn.commit()
    conn.close()

def get_state_val(key: str) -> int:
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT val FROM state_info WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 0

def set_state_val(key: str, val: int):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO state_info (key, val) VALUES (?, ?)", (key, val))
    conn.commit()
    conn.close()

def get_due_warnings() -> list[str]:
    curr = get_state_val("current_mileage")
    if curr == 0:
        return []
    alerts = []
    for key, info in INTERVALS.items():
        last_m = get_state_val(f"last_{key}")
        if last_m > 0:
            left = (last_m + info["interval"]) - curr
            if left <= 0:
                alerts.append(f"🔴 <b>{info['name']}</b> — ПРОСРОЧЕНО на <b>{abs(left):,} км</b>!".replace(",", " "))
            elif left <= 1000:
                alerts.append(f"🟡 <b>{info['name']}</b> — скоро замена (осталось <b>{left:,} км</b>)".replace(",", " "))
    return alerts

# =====================================================================
# 🔄 СОСТОЯНИЯ (FSM)
# =====================================================================
class Form(StatesGroup):
    update_mileage = State()
    log_mileage = State()
    log_category = State()
    log_desc = State()
    log_cost = State()
    part_category = State()
    part_name = State()
    part_article = State()
    part_note = State()
    avito_custom = State()

# =====================================================================
# ⌨️ ГЛАВНОЕ МЕНЮ
# =====================================================================
def main_menu_kb() -> InlineKeyboardMarkup:
    mileage = get_state_val("current_mileage")
    m_str = f"{mileage:,} км".replace(",", " ") if mileage > 0 else "Задать пробег"
    alerts = get_due_warnings()
    to_badge = f"⏳ Регламент ТО ({len(alerts)} ⚠️)" if alerts else "⏳ Регламент и Напоминания"

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 ПТС / СТС / VIN", callback_data="car_info"),
            InlineKeyboardButton(text=f"📟 Пробег: {m_str}", callback_data="set_mileage")
        ],
        [
            InlineKeyboardButton(text="🛒 Новые запчасти + Аналоги (Autodoc)", callback_data="parts_menu")
        ],
        [
            InlineKeyboardButton(text="♻️ Б/У запчасти и Разборки (Авито)", callback_data="avito_menu")
        ],
        [
            InlineKeyboardButton(text="🧪 Жидкости и Объёмы", callback_data="fluids_info"),
            InlineKeyboardButton(text="⚠️ Болячки по пробегу", callback_data="quirks_menu")
        ],
        [
            InlineKeyboardButton(text="🏢 Проверенные сервисы (Москва и МО)", callback_data="services_msk")
        ],
        [
            InlineKeyboardButton(text=to_badge, callback_data="intervals_menu")
        ],
        [
            InlineKeyboardButton(text="➕ Записать ремонт", callback_data="add_log"),
            InlineKeyboardButton(text="📓 История и расходы", callback_data="view_logs")
        ]
    ])

def back_home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="home")]
    ])

# =====================================================================
# 🚀 ОБРАБОТЧИКИ МЕНЮ
# =====================================================================
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    set_state_val("owner_chat_id", message.chat.id)
    alerts = get_due_warnings()
    alert_block = ("\n\n🔔 <b>Внимание по ТО:</b>\n" + "\n".join(alerts)) if alerts else ""

    await message.answer(
        f"🚗 <b>Бортжурнал {CAR_PROFILE['model']} v2.0</b>\n"
        f"Госномер: <code>{CAR_PROFILE['plate']}</code> | ДВС: <b>G4ED (1.6 АКПП)</b>"
        f"{alert_block}\n\n"
        f"Выбери нужный раздел:",
        reply_markup=main_menu_kb()
    )

@router.callback_query(F.data == "home")
async def cb_home(call: CallbackQuery, state: FSMContext):
    await state.clear()
    set_state_val("owner_chat_id", call.message.chat.id)
    alerts = get_due_warnings()
    alert_block = ("\n\n🔔 <b>Внимание по ТО:</b>\n" + "\n".join(alerts)) if alerts else ""

    await call.message.edit_text(
        f"🚗 <b>Бортжурнал {CAR_PROFILE['model']} v2.0</b>\n"
        f"Госномер: <code>{CAR_PROFILE['plate']}</code> | ДВС: <b>G4ED (1.6 АКПП)</b>"
        f"{alert_block}\n\n"
        f"Выбери нужный раздел:",
        reply_markup=main_menu_kb()
    )

# --- 1. ПАСПОРТ АВТО ---
@router.callback_query(F.data == "car_info")
async def cb_car_info(call: CallbackQuery):
    vin_autodoc = f"https://www.autodoc.ru/catalogs/original?vin={CAR_PROFILE['vin']}"
    text = (
        f"📋 <b>Паспорт автомобиля</b>\n"
        f"<i>(Нажми на любой номер, чтобы скопировать в буфер)</i>\n\n"
        f"🚘 <b>Модель:</b> {CAR_PROFILE['model']}\n"
        f"🎨 <b>Цвет / Кузов:</b> {CAR_PROFILE['color']} — {CAR_PROFILE['body_type']}\n"
        f"🔑 <b>VIN / Кузов:</b> <code>{CAR_PROFILE['vin']}</code>\n"
        f"🔢 <b>Госномер:</b> <code>{CAR_PROFILE['plate']}</code>\n"
        f"🪪 <b>Номер СТС:</b> <code>{CAR_PROFILE['sts']}</code>\n"
        f"📄 <b>Тип ПТС:</b> {CAR_PROFILE['pts']}\n"
        f"⚙️ <b>Двигатель:</b> {CAR_PROFILE['engine']}\n"
        f"🔩 <b>Номер ДВС:</b> <code>{CAR_PROFILE['engine_num']}</code>\n"
        f"🕹 <b>Коробка:</b> {CAR_PROFILE['transmission']}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Открыть каталог по твоему VIN на Autodoc", url=vin_autodoc)],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="home")]
    ])
    await call.message.edit_text(text, reply_markup=kb)

# --- 2. ОБНОВЛЕНИЕ ПРОБЕГА + ПРОВЕРКА НАПОМИНАНИЙ ---
@router.callback_query(F.data == "set_mileage")
async def cb_set_mileage(call: CallbackQuery, state: FSMContext):
    curr = get_state_val("current_mileage")
    await state.set_state(Form.update_mileage)
    await call.message.edit_text(
        f"📟 Текущий записанный пробег: <b>{curr:,} км</b>\n\n"
        f"Введи актуальный пробег с одометра (только цифры, например <code>248500</code>):".replace(",", " "),
        reply_markup=back_home_kb()
    )

@router.message(Form.update_mileage)
async def process_mileage(message: Message, state: FSMContext):
    raw = message.text.replace(" ", "").strip()
    if not raw.isdigit():
        await message.answer("⚠️ Введи пробег только цифрами (например: 248500):")
        return
    new_m = int(raw)
    set_state_val("current_mileage", new_m)
    set_state_val("owner_chat_id", message.chat.id)
    await state.clear()

    alerts = get_due_warnings()
    warn_text = ("\n\n🔔 <b>Напоминание о подходящем ТО:</b>\n" + "\n".join(alerts)) if alerts else "\n\n✅ Все узлы в пределах регламента!"

    await message.answer(
        f"✅ Пробег обновлён: <b>{new_m:,} км</b>{warn_text}".replace(",", " "),
        reply_markup=main_menu_kb()
    )

# --- 3. НОВЫЕ ЗАПЧАСТИ + ТОП АНАЛОГИ + AUTODOC ---
@router.callback_query(F.data == "parts_menu")
async def cb_parts_menu(call: CallbackQuery):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT category FROM parts")
    categories = [r[0] for r in cur.fetchall()]
    conn.close()

    kb_rows = [[InlineKeyboardButton(text=f"📁 {cat}", callback_data=f"pcat:{cat}")] for cat in categories]
    kb_rows.append([InlineKeyboardButton(text="➕ Добавить свой артикул", callback_data="add_part")])
    kb_rows.append([InlineKeyboardButton(text="⬅️ В главное меню", callback_data="home")])

    await call.message.edit_text(
        "🛒 <b>Новые запчасти и ТОП-аналоги (Autodoc)</b>\n\n"
        "В каждой категории собраны оригинальные номера под <b>G4ED (1.6 АКПП)</b>, "
        "лучшие проверенные заменители (которые реально ходят) и прямые кнопки заказа на <b>Autodoc.ru</b>:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows)
    )

@router.callback_query(F.data.startswith("pcat:"))
async def cb_parts_category(call: CallbackQuery):
    cat = call.data.split(":", 1)[1]
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT name, article, note FROM parts WHERE category = ?", (cat,))
    rows = cur.fetchall()
    conn.close()

    lines = [f"📁 <b>{cat}</b>\n<i>(Нажми на артикул для копирования или кнопку внизу для открытия цен в Autodoc)</i>\n"]
    kb_rows = []
    for name, art, note in rows:
        clean_art = art.replace("-", "").strip()
        autodoc_url = f"https://www.autodoc.ru/price/579/{quote(clean_art)}"
        lines.append(
            f"🔹 <b>{name}</b>\n"
            f"   Ориг. артикул: <code>{art}</code>\n"
            f"   ⭐ <i>{note}</i>\n"
        )
        kb_rows.append([
            InlineKeyboardButton(text=f"🛒 Autodoc: {name[:24]} ({art})", url=autodoc_url)
        ])

    kb_rows.append([InlineKeyboardButton(text="➕ Добавить свою деталь", callback_data="add_part")])
    kb_rows.append([InlineKeyboardButton(text="⬅️ Назад к категориям", callback_data="parts_menu")])
    await call.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))

@router.callback_query(F.data == "add_part")
async def cb_add_part(call: CallbackQuery, state: FSMContext):
    await state.set_state(Form.part_category)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="ТО и фильтры", callback_data="setpcat:ТО и фильтры"),
            InlineKeyboardButton(text="Ходовка и тормоза", callback_data="setpcat:Ходовка и тормоза")
        ],
        [
            InlineKeyboardButton(text="Ремни и ГРМ", callback_data="setpcat:Ремни и ГРМ"),
            InlineKeyboardButton(text="АКПП", callback_data="setpcat:АКПП")
        ],
        [InlineKeyboardButton(text="Электрика / Кузов", callback_data="setpcat:Электрика / Кузов")],
        [InlineKeyboardButton(text="⬅️ Отмена", callback_data="parts_menu")]
    ])
    await call.message.edit_text("Выбери категорию для новой запчасти:", reply_markup=kb)

@router.callback_query(Form.part_category, F.data.startswith("setpcat:"))
async def process_part_cat(call: CallbackQuery, state: FSMContext):
    cat = call.data.split(":", 1)[1]
    await state.update_data(category=cat)
    await state.set_state(Form.part_name)
    await call.message.edit_text(f"Категория: <b>{cat}</b>\nВведи название детали:")

@router.message(Form.part_name)
async def process_part_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(Form.part_article)
    await message.answer("Введи артикул детали (например: <code>54830-2D000</code>):")

@router.message(Form.part_article)
async def process_part_article(message: Message, state: FSMContext):
    await state.update_data(article=message.text.strip())
    await state.set_state(Form.part_note)
    await message.answer("Введи качественный аналог или заметку:")

@router.message(Form.part_note)
async def process_part_note(message: Message, state: FSMContext):
    data = await state.get_data()
    note = message.text.strip()
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO parts (category, name, article, note) VALUES (?, ?, ?, ?)",
        (data["category"], data["name"], data["article"], note)
    )
    conn.commit()
    conn.close()
    await state.clear()
    await message.answer(
        f"✅ Запчасть добавлена и привязана к Autodoc!\n<b>{data['name']}</b> — <code>{data['article']}</code>",
        reply_markup=main_menu_kb()
    )

# --- 4. Б/У ЗАПЧАСТИ И РАЗБОРКИ (АВИТО МОСКВА И МО) ---
@router.callback_query(F.data == "avito_menu")
async def cb_avito_menu(call: CallbackQuery):
    text = (
        "♻️ <b>Поиск Б/У запчастей и авторазборок на Авито (Москва и МО)</b>\n\n"
        "Крупные агрегаты, кузовню (особенно 5-ю дверь хэтчбека и оригинальные крылья), "
        "подрамники и навесное выгоднее искать с живых разборок.\n\n"
        "Нажми на нужный узел для мгновенного открытия свежих объявлений в Москве и МО:"
    )
    kb_rows = []
    for title, query_str in AVITO_BU_PARTS:
        url = f"https://www.avito.ru/moskva_i_mo/zapchasti_i_aksessuary?q={quote(query_str)}"
        kb_rows.append([InlineKeyboardButton(text=title, url=url)])

    kb_rows.append([InlineKeyboardButton(text="🔎 Найти любую другую деталь на Авито / Autodoc", callback_data="avito_custom_search")])
    kb_rows.append([InlineKeyboardButton(text="⬅️ В главное меню", callback_data="home")])
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))

@router.callback_query(F.data == "avito_custom_search")
async def cb_avito_custom(call: CallbackQuery, state: FSMContext):
    await state.set_state(Form.avito_custom)
    await call.message.edit_text(
        "🔎 <b>Быстрый поиск по Новым и Б/У запчастям</b>\n\n"
        "Напиши в чат название детали или её артикул (например: <i>Рулевая рейка</i> или <i>57700-2D000</i>), "
        "и я сгенерирую тебе прямые ссылки сразу на <b>Autodoc (Новое)</b> и на <b>Авито Разборки (Б/У)</b>:",
        reply_markup=back_home_kb()
    )

@router.message(Form.avito_custom)
async def process_avito_custom(message: Message, state: FSMContext):
    q = message.text.strip()
    await state.clear()
    clean_q = q.replace("-", "")
    autodoc_url = f"https://www.autodoc.ru/price/579/{quote(clean_q)}"
    avito_url = f"https://www.avito.ru/moskva_i_mo/zapchasti_i_aksessuary?q={quote('Hyundai Elantra XD ' + q)}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🆕 Смотреть НОВОЕ на Autodoc ({q})", url=autodoc_url)],
        [InlineKeyboardButton(text=f"♻️ Искать Б/У на Авито Москва/МО ({q})", url=avito_url)],
        [InlineKeyboardButton(text="🔎 Искать ещё деталь", callback_data="avito_custom_search")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="home")]
    ])
    await message.answer(
        f"✅ Ссылки для поиска <b>«{q}»</b> на твою Elantra XD готовы:",
        reply_markup=kb
    )

# --- 5. РЕКОМЕНДУЕМЫЕ ЖИДКОСТИ И ЗАПРАВОЧНЫЕ ОБЪЁМЫ ---
@router.callback_query(F.data == "fluids_info")
async def cb_fluids_info(call: CallbackQuery):
    text = (
        "🧪 <b>Рекомендуемые жидкости и объёмы (Elantra XD 1.6 G4ED АКПП)</b>\n\n"
        "🛢 <b>1. Моторное масло (ДВС G4ED):</b>\n"
        "• <b>Объём при замене:</b> <code>3.3 л</code> (с фильтром)\n"
        "• <b>Вязкость и допуск:</b> <b>5W-30</b> или <b>5W-40</b> (API SL/SM/SN, ACEA A3/B4 или ILSAC GF-4/5). На пробегах 200к+ отлично подходит 5W-30/5W-40 A3/B4 (меньше угар и тише работают гидрокомпенсаторы).\n"
        "• <b>Проверенные варианты:</b> ZIC X9 5W-30 / 5W-40, Kixx G1 5W-30, S-Oil Seven Red #9 5W-30, Lukoil Genesis Armortech HK 5W-30.\n\n"
        "⚙️ <b>2. Жидкость АКПП (4-ст. автомат F4A42):</b>\n"
        "• <b>Допуск СТРОГО:</b> <b>Mitsubishi / Hyundai ATF SP-III</b> (никаких Dexron или мультижидкостей без SP-III — коробка начнёт пинаться при переключении со 2 на 3!).\n"
        "• <b>Объём:</b> полный <code>7.8 л</code> / частичная замена (слил-залил) около <code>3.8 – 4.2 л</code>.\n"
        "• <b>Проверенные варианты (4л):</b> ZIC ATF SP 3 (<code>162627</code> — он же залит в оригинале!), Hyundai Mobis ATF SP-III (<code>04500-00400</code>), Kixx ATF SP-III.\n\n"
        "🛑 <b>3. Тормозная жидкость:</b>\n"
        "• <b>Допуск и объём:</b> <b>DOT-4</b>, объём системы <code>0.7 – 0.8 л</code> (бери 1 литр на полную прокачку).\n"
        "• <b>Проверенные варианты:</b> TRW PFB401, RosDot 4 Class 6, Bosch ENV6.\n\n"
        "❄️ <b>4. Охлаждающая жидкость (Антифриз):</b>\n"
        "• <b>Допуск и объём:</b> для алюминиевых блоков корейцев (Фосфатный лобридный P-OAT / G11 зелёный или сине-зелёный). Полный объём <code>6.0 л</code> (при сливе с радиатора и блока уходит ~4.5–5 л).\n"
        "• <b>Проверенные варианты:</b> Coolstream A-110 (официальный допуск Hyundai, артикул <code>CS-010502</code>), Hyundai Crown LLC A-110.\n\n"
        "🛞 <b>5. Жидкость ГУР:</b>\n"
        "• <b>Допуск и объём:</b> <b>PSF-3</b> (или Dexron III), объём <code>0.9 л</code>.\n"
        "• <b>Проверенный артикул:</b> Hyundai PSF-3 (<code>03100-00100</code>) или ZIC PSF 3."
    )
    await call.message.edit_text(text, reply_markup=back_home_kb())

# --- 6. НЮАНСЫ И БОЛЯЧКИ ПО ПРОБЕГАМ (ОПЫТ ELANTRA-CLUB) ---
@router.callback_query(F.data == "quirks_menu")
async def cb_quirks_menu(call: CallbackQuery):
    text = (
        "⚠️ <b>Нюансы и болячки Hyundai Elantra XD по пробегам</b>\n"
        "<i>Сводка реального опыта владельцев с форума Elantra-Club.ru для 1.6 G4ED + АКПП (Хэтчбек):</i>\n\n"
        "🔹 <b>Каждые 50 000 – 60 000 км:</b>\n"
        "• <b>Ремень ГРМ:</b> на G4ED при обрыве ремня ГРМ <b>ГНЁТ КЛАПАНА</b>! Не тяни до 90 тыс., меняй строго раз в 55–60 тыс. км.\n"
        "• <b>Гофра глушителя:</b> из-за жёсткости выхлопа прогорает раз в 2–3 года (размер гофры <code>50x200</code> трёхслойная Interlock).\n\n"
        "🔸 <b>Пробег 120 000 – 160 000 км:</b>\n"
        "• <b>Цокот на холодную (Межвальная цепь и гидрики):</b> между распредвалами стоит короткая цепь (<code>24321-26020</code>) без натяжителя. К 150к она растягивается и дизелит/звенит — менять при замене ГРМ.\n"
        "• <b>Радиатор охлаждения:</b> течёт по верхнему пластиковому бачку из-за закисшего клапана крышки радиатора (<code>25330-17000</code> — крышку на 0.9 бар лучше менять раз в 2 года!).\n"
        "• <b>Вибрация на D + тормоз:</b> проседают подушки ДВС (особенно правая гидроопора и нижняя «лыжа»). Если ставить неоригинал — вибрация часто становится ещё сильнее!\n\n"
        "🔴 <b>Пробег 200 000 – 250 000+ км (Возрастные болячки):</b>\n"
        "• <b>Задний подрамник (балка) и продольные рычаги:</b> главная беда XD в Москве! Подрамник гниёт изнутри от реагентов. При каждом ТО на подъёмнике простукивать молотком и заливать антикором/пушсалом.\n"
        "• <b>Развальные болты задней подвески:</b> намертво закисают во втулках сайлентблоков. Перед сход-развалом готовить новые эксцентриковые болты (<code>55220-2D000</code>).\n"
        "• <b>Пинки АКПП (F4A42) при переключении 2→3 или 3→2:</b> чаще всего виноват не износ фрикционов, а датчики оборотов входного/выходного вала (<code>42620-39051</code> и <code>42621-39052</code>) или обрыв проводки к ним.\n"
        "• <b>Жгут проводов в гофре 5-й двери (Хэтчбек):</b> на морозе переламываются провода в резиновой гофре крышки багажника — перестаёт работать задний дворник, обогрев стекла или замок.\n"
        "• <b>Масложор G4ED:</b> к 200к+ дубеют маслосъёмные колпачки и залегают маслосъёмные кольца. Помогает замена колпачков и раскоксовка."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Открыть форум Elantra-Club.ru", url="https://elantra-club.ru/forum/")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="home")]
    ])
    await call.message.edit_text(text, reply_markup=kb)

# --- 7. ПРОВЕРЕННЫЕ СЕРВИСЫ (МОСКВА И МО) ---
@router.callback_query(F.data == "services_msk")
async def cb_services_msk(call: CallbackQuery):
    text = (
        "🏢 <b>Проверенные клубные сервисы Hyundai Elantra (Москва и МО)</b>\n"
        "<i>По рекомендациям участников форума elantra-club.ru, которые знают специфику кузова XD, мотора G4ED и АКПП F4A42:</i>\n\n"
        "1️⃣ <b>Клубный техцентр «AVIS-Motors» (ЮВАО)</b>\n"
        "• 📍 <b>Адрес:</b> Москва, Михайловский проезд, д. 3, стр. 5 (м. Волгоградский пр-т / Пролетарская)\n"
        "• 📞 <b>Телефон:</b> <code>+7 (495) 228-03-50</code>\n"
        "• 🛠 <b>Плюсы:</b> Официальный партнёр клубов Hyundai с 2005 года. Знают Elantra XD вдоль и поперёк, дают гарантию 60 000 км на замену ГРМ, свой склад запчастей, не разводят на лишние работы.\n\n"
        "2️⃣ <b>Клубный сервис «Большой Кореец» (СВАО / ЗАО / МО Дзержинский)</b>\n"
        "• 📍 <b>Север (СВАО):</b> Москва, Берёзовая аллея, 4А | 📞 <code>+7 (906) 084-16-12</code>\n"
        "• 📍 <b>Запад (ЗАО):</b> Москва, Рябиновая ул., 34В, стр. 1 | 📞 <code>+7 (964) 648-30-28</code>\n"
        "• 📍 <b>МО (Белая Дача):</b> г. Дзержинский, ул. Энергетиков, д. 28 | 📞 <code>+7 (964) 649-91-89</code>\n"
        "• 🛠 <b>Плюсы:</b> Узкая специализация только на Hyundai/Kia, огромная база расходников и запчастей в наличии, грамотная переборка подвески и спиливание закисших развальных болтов.\n\n"
        "3️⃣ <b>СпецСервис «Корея-Авто / ОЕМ-Зап» (СВАО / ЮАО)</b>\n"
        "• 📍 <b>Адрес:</b> Москва, Алтуфьевское ш., 48 к. 4 / ул. Речников, 19\n"
        "• 🛠 <b>Плюсы:</b> Хорошая диагностика электрики, ремонт двигателей G4ED и обслуживание 4-ступенчатых автоматов."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Сайт AVIS-Motors (раздел Elantra XD)", url="https://www.avis-motors.ru/remont/hyundai/elantra-j3-xd/")],
        [InlineKeyboardButton(text="🌐 Сайт клубного сервиса Большой Кореец", url="https://bigk.su/")],
        [InlineKeyboardButton(text="💬 Отзывы о сервисах на форуме Elantra-Club", url="https://elantra-club.ru/forum/")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="home")]
    ])
    await call.message.edit_text(text, reply_markup=kb)

# --- 8. РЕГЛАМЕНТЫ И НАПОМИНАНИЯ О ТО ---
def build_intervals_view():
    curr = get_state_val("current_mileage")
    lines = [
        "⏳ <b>Контроль регламентов и Напоминания о ТО</b>",
        "<i>Бот автоматически проверяет пробег и присылает уведомление, когда до ТО остаётся меньше 1 000 км.</i>"
    ]
    if curr == 0:
        lines.append("\n⚠️ <b>Сначала укажи актуальный пробег в главном меню!</b>\n")
    else:
        lines.append(f"\n📟 Текущий пробег: <b>{curr:,} км</b>\n".replace(",", " "))

    kb_rows = []
    for key, info in INTERVALS.items():
        last_m = get_state_val(f"last_{key}")
        interval = info["interval"]
        if last_m == 0:
            status = "⚪ Не задано (нажми кнопку ниже после замены)"
        else:
            next_m = last_m + interval
            left = next_m - curr
            if left > 1000:
                status = f"След. на <b>{next_m:,} км</b> (осталось 🟢 <b>{left:,} км</b>)".replace(",", " ")
            elif left > 0:
                status = f"След. на <b>{next_m:,} км</b> (СКОРО ТО 🟡 <b>{left:,} км</b>)".replace(",", " ")
            else:
                status = f"🔴 <b>ПРОСРОЧЕНО на {abs(left):,} км!</b> (менялось на {last_m:,} км)".replace(",", " ")

        lines.append(f"{info['name']} (интервал {interval:,} км):\n└ {status}\n".replace(",", " "))
        kb_rows.append([
            InlineKeyboardButton(
                text=f"✅ Я заменил: {info['name']} (на {curr} км)",
                callback_data=f"reset_int:{key}"
            )
        ])

    kb_rows.append([InlineKeyboardButton(text="⬅️ В главное меню", callback_data="home")])
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=kb_rows)

@router.callback_query(F.data == "intervals_menu")
async def cb_intervals(call: CallbackQuery):
    text, kb = build_intervals_view()
    await call.message.edit_text(text, reply_markup=kb)

@router.callback_query(F.data.startswith("reset_int:"))
async def cb_reset_interval(call: CallbackQuery):
    key = call.data.split(":")[1]
    curr = get_state_val("current_mileage")
    if curr == 0:
        await call.answer("Сначала задай текущий пробег в главном меню!", show_alert=True)
        return
    set_state_val(f"last_{key}", curr)
    await call.answer(f"Отлично! Замена зафиксирована на {curr} км.")
    text, kb = build_intervals_view()
    await call.message.edit_text(text, reply_markup=kb)

# --- 9. ЗАПИСЬ РЕМОНТОВ И ИСТОРИЯ РАСХОДОВ ---
@router.callback_query(F.data == "add_log")
async def cb_add_log(call: CallbackQuery, state: FSMContext):
    curr = get_state_val("current_mileage")
    await state.set_state(Form.log_mileage)
    await call.message.edit_text(
        f"➕ <b>Новая запись в бортжурнал</b>\n\n"
        f"Введи пробег, на котором проводились работы (текущий: <code>{curr}</code>):",
        reply_markup=back_home_kb()
    )

@router.message(Form.log_mileage)
async def process_log_mileage(message: Message, state: FSMContext):
    raw = message.text.replace(" ", "").strip()
    if not raw.isdigit():
        await message.answer("⚠️ Введи пробег только цифрами:")
        return
    m = int(raw)
    await state.update_data(mileage=m)
    if m > get_state_val("current_mileage"):
        set_state_val("current_mileage", m)

    await state.set_state(Form.log_category)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🛢 Плановое ТО", callback_data="logcat:ТО"),
            InlineKeyboardButton(text="🔩 Ходовка / Тормоза", callback_data="logcat:Ходовка")
        ],
        [
            InlineKeyboardButton(text="⚙️ Двигатель / АКПП", callback_data="logcat:ДВС и АКПП"),
            InlineKeyboardButton(text="🧰 Кузов / Прочее", callback_data="logcat:Ремонт")
        ]
    ])
    await message.answer("Выбери категорию работ:", reply_markup=kb)

@router.callback_query(Form.log_category, F.data.startswith("logcat:"))
async def process_log_cat(call: CallbackQuery, state: FSMContext):
    cat = call.data.split(":", 1)[1]
    await state.update_data(category=cat)
    await state.set_state(Form.log_desc)
    await call.message.edit_text(f"Категория: <b>{cat}</b>\nОпиши, что было сделано и какие запчасти поставили:")

@router.message(Form.log_desc)
async def process_log_desc(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await state.set_state(Form.log_cost)
    await message.answer("Введи общую стоимость (запчасти + работа) в рублях цифрами (если бесплатно — <code>0</code>):")

@router.message(Form.log_cost)
async def process_log_cost(message: Message, state: FSMContext):
    raw = message.text.replace(" ", "").strip()
    if not raw.isdigit():
        await message.answer("⚠️ Введи сумму только цифрами:")
        return
    cost = int(raw)
    data = await state.get_data()
    now_str = datetime.now().strftime("%d.%m.%Y")

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO service_log (date, mileage, category, description, cost) VALUES (?, ?, ?, ?, ?)",
        (now_str, data["mileage"], data["category"], data["description"], cost)
    )
    conn.commit()
    conn.close()
    await state.clear()

    await message.answer(
        f"✅ <b>Запись сохранена!</b>\n\n"
        f"📅 Дата: {now_str} | 📟 Пробег: {data['mileage']:,} км\n"
        f"🛠 [{data['category']}] {data['description']}\n"
        f"💰 Сумма: {cost:,} ₽".replace(",", " "),
        reply_markup=main_menu_kb()
    )

@router.callback_query(F.data == "view_logs")
async def cb_view_logs(call: CallbackQuery):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT SUM(cost), COUNT(*) FROM service_log")
    total_cost, total_count = cur.fetchone()
    total_cost = total_cost or 0

    cur.execute(
        "SELECT date, mileage, category, description, cost FROM service_log ORDER BY mileage DESC, id DESC LIMIT 10"
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        text = "📓 <b>Бортжурнал пока пуст.</b>\nДобавь первую запись через меню!"
    else:
        lines = [
            f"📓 <b>История обслуживания (последние 10 записей)</b>",
            f"💰 Всего вложено: <b>{total_cost:,} ₽</b> (всего записей: {total_count})\n".replace(",", " ")
        ]
        for date, mileage, cat, desc, cost in rows:
            lines.append(
                f"🔹 <b>{mileage:,} км</b> ({date}) — <b>[{cat}]</b>\n"
                f"   {desc}\n"
                f"   💵 <b>{cost:,} ₽</b>\n".replace(",", " ")
            )
        text = "\n".join(lines)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить запись", callback_data="add_log")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="home")]
    ])
    await call.message.edit_text(text, reply_markup=kb)

# =====================================================================
# 🔔 ФОНОВЫЙ ТАЙМЕР АВТО-НАПОМИНАНИЙ О ТО
# =====================================================================
async def auto_reminder_loop(bot: Bot):
    while True:
        await asyncio.sleep(12 * 3600)  # Проверка каждые 12 часов
        chat_id = get_state_val("owner_chat_id")
        alerts = get_due_warnings()
        if chat_id and alerts:
            try:
                await bot.send_message(
                    chat_id,
                    "🔔 <b>Плановое напоминание по твоей Hyundai Elantra XD:</b>\n\n"
                    + "\n".join(alerts)
                    + "\n\nЗагляни в раздел <b>«⏳ Регламент и Напоминания»</b> или закажи запчасти заранее!",
                    reply_markup=main_menu_kb()
                )
            except Exception:
                pass

# =====================================================================
# ▶️ ЗАПУСК С ПРИНУДИТЕЛЬНЫМ IPv4 (БЕЗ ОШИБКИ ТАЙМАУТА)
# =====================================================================
class IPv4Session(AiohttpSession):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._connector_type = TCPConnector
        self._connector_init["family"] = socket.AF_INET

async def main():
    init_db()
    session = IPv4Session()
    bot = Bot(
        token=BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    dp.include_router(router)
    asyncio.create_task(auto_reminder_loop(bot))
    print("🚗 Бортжурнал Hyundai Elantra XD v2.0 запущен! Нажми Ctrl+C для остановки.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
