import asyncio
import csv
import io
import os
import socket
import sqlite3
from datetime import datetime
from urllib.parse import quote
from aiohttp import TCPConnector
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, BotCommand, BufferedInputFile
)
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# =====================================================================
# 🔑 ТОКЕН ТВОЕГО БОТА
# =====================================================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8940583712:AAEHTlsV8AmRjewdv_-cxvF0ZCIKtChzjzw")

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
    "coolant": {"name": "❄️ Антифриз (Coolstream A-110)", "interval": 60000},
}

# =====================================================================
# 🔧 ПОЛНЫЙ КАТАЛОГ УЗЛОВ И ЗАПЧАСТЕЙ (ВСЕ КНОПКИ РАЗДЕЛЕНЫ ПО ОТДЕЛЬНОСТИ)
# Формат: (Участок авто, Название узла, Оригинальный артикул, Лучшие аналоги, Запрос для Б/У на Авито)
# =====================================================================
DEFAULT_PARTS = [
    # 1. Расходники для ТО
    ("🛢 Расходники для ТО", "Масляный фильтр ДВС", "26300-35505",
     "Mann W811/80 (идёт в оригинале), Knecht/Mahle OC205, Vic C-307", "Фильтр масляный 26300-35505"),
    ("🛢 Расходники для ТО", "Шайба сливной пробки поддона ДВС", "21513-23001",
     "Elring 813.036, Masuma M-49", "Шайба сливной пробки 21513-23001"),
    ("🛢 Расходники для ТО", "Воздушный фильтр ДВС", "28113-2D000",
     "Filtron AP183/1, Mann C2620, Parts-Mall PAA-018", "Корпус воздушного фильтра Elantra XD"),
    ("🛢 Расходники для ТО", "Салонный фильтр", "97133-2D000",
     "Raf Filter RF001HY, TSN 9.7.115 (угольный), Filtron K1169", "Салонный фильтр Elantra XD"),
    ("🛢 Расходники для ТО", "Свечи зажигания (комплект 4 шт.)", "18814-11051",
     "NGK BKR5ES-11 (лежит в оригинале), Denso K16PR-U11", "Свечи зажигания NGK BKR5ES-11"),
    ("🛢 Расходники для ТО", "Топливный фильтр (в баке)", "31911-2D000",
     "Оригинал Hyundai/Kia, Nipparts J1330514", "Топливный фильтр модуль Elantra XD"),

    # 2. ДВС (G4ED 1.6) и ГРМ
    ("⚙️ ДВС (G4ED) и ГРМ", "Двигатель G4ED 1.6 в сборе (столбик)", "G4ED",
     "При покупке контрактного ДВС проверять эндоскопом хон и отсутствие трещин в выпускном коллекторе", "Двигатель G4ED 1.6 Hyundai Elantra XD"),
    ("⚙️ ДВС (G4ED) и ГРМ", "Ремень ГРМ (111 зубьев)", "24312-26050",
     "Gates 5479XS, Contitech CT942, Dongil (поставщик конвейера)", "Ремень ГРМ 24312-26050"),
    ("⚙️ ДВС (G4ED) и ГРМ", "Ролик натяжителя ГРМ", "24410-26000",
     "GMB GT10022 (идёт в оригинале), INA 531 0118 20", "Ролик ГРМ 24410-26000"),
    ("⚙️ ДВС (G4ED) и ГРМ", "Ролик обводной (паразитный) ГРМ", "24810-26020",
     "GMB GT10140 (идёт в оригинале), INA 532 0309 20", "Ролик обводной 24810-26020"),
    ("⚙️ ДВС (G4ED) и ГРМ", "Межвальная цепь распредвалов", "24321-26020",
     "Ставить строго Оригинал Hyundai/Kia!", "Цепь распредвалов G4ED 24321-26020"),
    ("⚙️ ДВС (G4ED) и ГРМ", "Прокладка клапанной крышки", "22441-26020",
     "Оригинал Hyundai/Kia (только оригинал не течёт!), Elring 027.950", "Клапанная крышка G4ED Elantra XD"),
    ("⚙️ ДВС (G4ED) и ГРМ", "Гидрокомпенсаторы (нужно 16 шт.)", "24610-22600",
     "INA 420 0094 10, Оригинал Hyundai/Kia", "Гидрокомпенсаторы G4ED 24610-22600"),
    ("⚙️ ДВС (G4ED) и ГРМ", "Опора (подушка) ДВС правая верхняя (гидро)", "21810-2D000",
     "Ставить Оригинал Hyundai/Kia (на аналогах идёт вибрация по кузову)", "Подушка двигателя правая Elantra XD 21810-2D000"),
    ("⚙️ ДВС (G4ED) и ГРМ", "Опора ДВС передняя / задняя на лыже", "21910-2D000",
     "Оригинал Hyundai/Kia, CTR", "Опора двигателя балка лыжа Elantra XD"),

    # 3. АКПП (4-ст. F4A42) и Приводы
    ("🕹 АКПП и Приводы", "АКПП 4-ст. F4A42 в сборе (контракт)", "F4A42",
     "Искать контрактную коробку с малым пробегом, проверять маркировку колокола под G4ED", "АКПП Hyundai Elantra XD 1.6 F4A42"),
    ("🕹 АКПП и Приводы", "Фильтр АКПП (внутренний)", "46321-22731",
     "Оригинал Hyundai/Kia, JS Asakashi JT426K (с прокладкой)", "Фильтр АКПП 46321-22731"),
    ("🕹 АКПП и Приводы", "Прокладка поддона АКПП", "45285-22010",
     "Оригинал Hyundai/Kia или серый герметик Victor Reinz Reinzosil", "Поддон АКПП Elantra XD F4A42"),
    ("🕹 АКПП и Приводы", "Датчик оборотов входного вала АКПП", "42620-39051",
     "Оригинал Hyundai/Kia (частая причина пинков и аварийного режима 3-й передачи)", "Датчик входного вала АКПП 42620-39051"),
    ("🕹 АКПП и Приводы", "Датчик оборотов выходного вала АКПП", "42621-39052",
     "Оригинал Hyundai/Kia", "Датчик выходного вала АКПП 42621-39052"),
    ("🕹 АКПП и Приводы", "Привод передний левый в сборе (АКПП)", "49501-2D510",
     "ШРУС наружный HDK HY-011A44, GKN/Loebro", "Привод левый Hyundai Elantra XD 1.6 АКПП"),
    ("🕹 АКПП и Приводы", "Привод передний правый в сборе (АКПП)", "49500-2D510",
     "ШРУС наружный HDK HY-011A44, GKN/Loebro", "Привод правый Hyundai Elantra XD 1.6 АКПП"),

    # 4. Навесное оборудование и Электрика (КАЖДЫЙ УЗЕЛ ОТДЕЛЬНО!)
    ("⚡️ Навесное и Электрика", "Генератор (80A / 90A для G4ED)", "37300-22650",
     "Valeo / Mando (идут в оригинале), Krauf ALV1650", "Генератор Hyundai Elantra XD 1.6 G4ED"),
    ("⚡️ Навесное и Электрика", "Стартер (под АКПП G4ED)", "36100-22855",
     "Valeo / Mando, Krauf STV1855", "Стартер Hyundai Elantra XD 1.6 АКПП G4ED"),
    ("⚡️ Навесное и Электрика", "Компрессор кондиционера", "97701-2D100",
     "HCC / Halla (оригинал конвейера), Luzar, Nissens", "Компрессор кондиционера Hyundai Elantra XD G4ED"),
    ("⚡️ Навесное и Электрика", "Насос ГУР (гидроусилителя руля)", "57100-2D100",
     "Оригинал Hyundai/Kia, Mando, MSG HY003", "Насос ГУР Hyundai Elantra XD 1.6 G4ED"),
    ("⚡️ Навесное и Электрика", "Катушка зажигания (модуль)", "27301-26600",
     "Оригинал Hyundai/Kia, NGK U4008, Bremi, Mando", "Катушка зажигания G4ED Elantra XD"),
    ("⚡️ Навесное и Электрика", "Высоковольтные провода зажигания (комплект)", "27501-26D00",
     "NGK RC-HY1207, Оригинал Hyundai, Mando", "Бронепровода G4ED Elantra XD"),
    ("⚡️ Навесное и Электрика", "Ремень генератора и помпы (4PK875)", "25212-26021",
     "Gates 4PK875, Contitech 4PK875, Mitsuboshi", "Ремень генератора 4PK875"),
    ("⚡️ Навесное и Электрика", "Ремень компрессора кондиционера (4PK850)", "97713-2D100",
     "Gates 4PK850, Contitech 4PK850", "Ремень кондиционера 4PK850"),
    ("⚡️ Навесное и Электрика", "Ремень насоса ГУР", "57170-2D101",
     "Gates 6461MC, Contitech AVX13X865, Dongil", "Ремень ГУР 57170-2D101"),

    # 5. Охлаждение и Отопление
    ("❄️ Охлаждение и Печка", "Радиатор охлаждения ДВС (под АКПП!)", "25310-2D110",
     "HCC/Halla (оригинал), Nissens 67638, Koyorad, Luzar (важно: со штуцерами охлаждения АКПП внизу!)", "Радиатор охлаждения Hyundai Elantra XD АКПП"),
    ("❄️ Охлаждение и Печка", "Крышка радиатора (0.9 бар)", "25330-17000",
     "Ставить строго Оригинал Hyundai/Kia (менять раз в 2 года, чтобы не лопнул радиатор)", "Крышка радиатора 25330-17000"),
    ("❄️ Охлаждение и Печка", "Помпа (водяной насос охлаждения)", "25100-26902",
     "GMB GWHY-23A (лежит в оригинале), Hepu P7797, Valeo WP-5016", "Помпа водяной насос G4ED"),
    ("❄️ Охлаждение и Печка", "Термостат (82°C)", "25500-23010",
     "Оригинал Hyundai/Kia, Vernet TH6295.82J, Gates", "Корпус термостата G4ED Elantra XD"),
    ("❄️ Охлаждение и Печка", "Радиатор кондиционера (конденсор)", "97606-2D000",
     "HCC/Halla, Nissens 94592, Luzar", "Радиатор кондиционера Hyundai Elantra XD"),
    ("❄️ Охлаждение и Печка", "Моторчик печки (вентилятор салона)", "97113-2D000",
     "HCC/Halla, Mando, Luzar LFh 082D", "Моторчик печки Hyundai Elantra XD"),

    # 6. Передняя подвеска и Рулевое
    ("🔩 Передняя подвеска и Руль", "Подрамник передний (балка ДВС)", "62410-2D000",
     "На разборках искать живой без сквозной коррозии с южных распилов", "Подрамник передний Hyundai Elantra XD"),
    ("🔩 Передняя подвеска и Руль", "Рулевая рейка в сборе (ГУР)", "57700-2D000",
     "Mando EX577002D000 (идёт с завода!), MSG HY205", "Рулевая рейка Hyundai Elantra XD"),
    ("🔩 Передняя подвеска и Руль", "Рычаг передний левый в сборе", "54500-2D002",
     "CTR CQKH-15L (поставляется на конвейер!), Оригинал Hyundai", "Рычаг передний левый Hyundai Elantra XD"),
    ("🔩 Передняя подвеска и Руль", "Рычаг передний правый в сборе", "54501-2D002",
     "CTR CQKH-15R (поставляется на конвейер!), Оригинал Hyundai", "Рычаг передний правый Hyundai Elantra XD"),
    ("🔩 Передняя подвеска и Руль", "Шаровая опора переднего рычага", "54503-38A00",
     "CTR CBKH-7 (лежит в коробке оригинала), Lemforder", "Шаровая опора 54503-38A00"),
    ("🔩 Передняя подвеска и Руль", "Стойка стабилизатора передняя", "54830-2D000",
     "CTR CLKH-15 (идёт в оригинале, левая и правая одинаковые)", "Стойка стабилизатора 54830-2D000"),
    ("🔩 Передняя подвеска и Руль", "Амортизаторы передние (Лев: 54651-2D100 / Прав: 54661-2D100)", "54651-2D100",
     "Mando EX546512D100 / EX546612D100, Kayaba (KYB) 333305 / 333304", "Стойки амортизаторы передние Elantra XD"),
    ("🔩 Передняя подвеска и Руль", "Подшипник передней ступицы", "51720-2D000",
     "Iljin IJ111004 (идёт на конвейер!), SNR, FAG, GMB", "Кулак поворотный ступица передняя Elantra XD"),
    ("🔩 Передняя подвеска и Руль", "Рулевой наконечник (Лев / Прав одинаковые)", "56820-28520",
     "CTR CEKH-7 (оригинал конвейера), Lemforder", "Рулевой наконечник 56820-28520"),

    # 7. Задняя подвеска
    ("🦴 Задняя подвеска", "Балка задней подвески (задний подрамник)", "55410-2D000",
     "Больное место XD! Искать живую контрактную балку и сразу обрабатывать антикором", "Балка задняя подрамник Hyundai Elantra XD"),
    ("🦴 Задняя подвеска", "Амортизаторы задние (Лев: 55351-2D100 / Прав: 55361-2D100)", "55351-2D100",
     "Mando EX553512D100 / EX553612D100, Kayaba (KYB) 333501 / 333500", "Амортизаторы задние Hyundai Elantra XD"),
    ("🦴 Задняя подвеска", "Стойка стабилизатора задняя", "55530-29500",
     "CTR CLKH-5, 555", "Стойка стабилизатора задняя Elantra XD"),
    ("🦴 Задняя подвеска", "Болт развальный задней подвески (эксцентрик)", "55220-2D000",
     "Ставить Оригинал Hyundai + шайба 55223-2D000 + гайка 55229-29000 (смазать графиткой!)", "Рычаги задней подвески Hyundai Elantra XD"),
    ("🦴 Задняя подвеска", "Ступица задняя в сборе с подшипником (с кольцом ABS)", "52710-2D115",
     "Iljin IJ112012 (поставляется в оригинале!), GMB, SNR", "Ступица задняя Hyundai Elantra XD"),

    # 8. Тормозная система
    ("🛑 Тормозная система", "Диск тормозной передний (257 мм, 4x114.3)", "51712-2D000",
     "Sangsin SD1035, TRW DF4192, Zimmerman, Brembo", "Суппорт передний тормозной диск Elantra XD"),
    ("🛑 Тормозная система", "Колодки тормозные передние", "58101-2DA50",
     "Sangsin Hi-Q SP1147 (мягкие, не пылят и не скрипят), Hankook Frixa FPH04", "Колодки передние SP1147"),
    ("🛑 Тормозная система", "Диск тормозной задний", "58411-29310",
     "Sangsin SD1040, TRW DF4045, Otto Zimmermann", "Суппорт задний тормозной диск Elantra XD"),
    ("🛑 Тормозная система", "Колодки тормозные задние (дисковые)", "58302-2DA00",
     "Sangsin Hi-Q SP1116, ICER, TRW", "Колодки задние SP1116"),
    ("🛑 Тормозная система", "Трос стояночного тормоза (ручника) Левый / Правый", "59760-2D300",
     "Левый: 59760-2D300 / Правый: 59770-2D300. Аналоги: Parts-Mall, NK", "Трос ручника Hyundai Elantra XD"),

    # 9. Кузов и Оптика (Хэтчбек 5 дверей)
    ("🚪 Кузов и Оптика (Хэтчбек)", "Крышка багажника (5-я дверь Хэтчбек)", "73700-2D010",
     "Искать живую Б/У в цвет или под покраску с разборки без ржавчины по нижней кромке", "Крышка багажника Hyundai Elantra XD хэтчбек"),
    ("🚪 Кузов и Оптика (Хэтчбек)", "Амортизаторы (газовые упоры) багажника Хэтчбек", "81771-2D210",
     "Lesjofors 8137224, Patron PGS4243VA, Finwhale (держат тяжёлую 5-ю дверь зимой)", "Упоры багажника Hyundai Elantra XD хэтчбек"),
    ("🚪 Кузов и Оптика (Хэтчбек)", "Крыло переднее левое / правое (рестайлинг 2003-2006)", "66311-2D020",
     "Лучше брать живой оригинал Б/У с разборки (тайваньские TYG/API требуют подгонки зазоров)", "Крыло переднее Hyundai Elantra XD рестайлинг"),
    ("🚪 Кузов и Оптика (Хэтчбек)", "Капот (рестайлинг 2003-2006)", "66400-2D020",
     "Оригинал Б/У с разборки (обратить внимание: у рестайлинга своя решётка радиатора!)", "Капот Hyundai Elantra XD рестайлинг"),
    ("🚪 Кузов и Оптика (Хэтчбек)", "Бампер передний (рестайлинг 2003-2006)", "86511-2D010",
     "Оригинал Б/У или TYG", "Бампер передний Hyundai Elantra XD рестайлинг"),
    ("🚪 Кузов и Оптика (Хэтчбек)", "Фара передняя Левая / Правая (рестайлинг)", "92101-2D150",
     "Depo 221-1129L-LD-EM / 221-1129R-LD-EM или оригинал Б/У", "Фара передняя Hyundai Elantra XD"),
    ("🚪 Кузов и Оптика (Хэтчбек)", "Фонарь задний (Хэтчбек!)", "92401-2D250",
     "Важно: у хэтчбека и седана задние фонари разные!", "Фонарь задний Hyundai Elantra XD хэтчбек"),
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
        CREATE TABLE IF NOT EXISTS fuel_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            mileage INTEGER,
            liters REAL,
            cost INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            name TEXT,
            article TEXT,
            note TEXT,
            avito_query TEXT DEFAULT ''
        )
    """)

    # Проверим наличие колонки avito_query при обновлении со старой базы
    cur.execute("PRAGMA table_info(parts)")
    cols = [c[1] for c in cur.fetchall()]
    if "avito_query" not in cols:
        cur.execute("ALTER TABLE parts ADD COLUMN avito_query TEXT DEFAULT ''")

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
        ("parts_catalog_v3", 0),
    ]
    for k, v in defaults:
        cur.execute("INSERT OR IGNORE INTO state_info (key, val) VALUES (?, ?)", (k, v))

    # Обновим каталог до полной поузловой базы v3.0
    cur.execute("SELECT val FROM state_info WHERE key = 'parts_catalog_v3'")
    row = cur.fetchone()
    if not row or row[0] == 0:
        cur.execute("DELETE FROM parts")
        cur.executemany(
            "INSERT INTO parts (category, name, article, note, avito_query) VALUES (?, ?, ?, ?, ?)",
            DEFAULT_PARTS
        )
        cur.execute("INSERT OR REPLACE INTO state_info (key, val) VALUES ('parts_catalog_v3', 1)")

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

    fuel_mileage = State()
    fuel_liters = State()
    fuel_cost = State()

    part_category = State()
    part_name = State()
    part_article = State()
    part_note = State()
    custom_search = State()

# =====================================================================
# ⌨️ ПОСТОЯННАЯ НИЖНЯЯ КЛАВИАТУРА [::] И ГЛАВНОЕ МЕНЮ
# =====================================================================
def persistent_reply_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🏠 Главное меню"),
                KeyboardButton(text="🔧 Узлы и Запчасти"),
                KeyboardButton(text="⛽️ Заправка")
            ],
            [
                KeyboardButton(text="📊 Сводка (ТО / ТР / Бензин)"),
                KeyboardButton(text="⏳ Регламент ТО"),
                KeyboardButton(text="📟 Обновить пробег")
            ]
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Выбери раздел в меню или нажми кнопку..."
    )

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
            InlineKeyboardButton(text="🔧 Каталог по узлам (Артикулы + Autodoc + Авито)", callback_data="parts_menu")
        ],
        [
            InlineKeyboardButton(text="➕ Записать ТО или ТР", callback_data="add_log"),
            InlineKeyboardButton(text="⛽️ Записать заправку", callback_data="fuel_menu")
        ],
        [
            InlineKeyboardButton(text="📊 Полная сводка авто (ТО / ТР / Топливо)", callback_data="view_logs")
        ],
        [
            InlineKeyboardButton(text=to_badge, callback_data="intervals_menu")
        ],
        [
            InlineKeyboardButton(text="🧪 Жидкости и Объёмы", callback_data="fluids_info"),
            InlineKeyboardButton(text="⚠️ Болячки по пробегу", callback_data="quirks_menu")
        ],
        [
            InlineKeyboardButton(text="🏢 Клубные сервисы (МСК)", callback_data="services_msk"),
            InlineKeyboardButton(text="🚨 Шпаргалка (Диски/Лампы)", callback_data="road_help")
        ]
    ])

def back_home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="home")]
    ])

# =====================================================================
# 🚀 ОБРАБОТЧИКИ КОМАНД И СИНЯЯ КНОПКА «МЕНЮ»
# =====================================================================
def build_welcome_text() -> str:
    alerts = get_due_warnings()
    alert_block = ("\n\n🔔 <b>Внимание по ТО:</b>\n" + "\n".join(alerts)) if alerts else ""
    return (
        f"🚗 <b>Бортжурнал {CAR_PROFILE['model']} v3.0</b>\n"
        f"Госномер: <code>{CAR_PROFILE['plate']}</code> | ДВС: <b>G4ED (1.6 АКПП)</b>"
        f"{alert_block}\n\n"
        f"Выбери нужный раздел (также всегда доступны синяя кнопка <b>«Меню»</b> слева и быстрые кнопки внизу экрана):"
    )

@router.message(CommandStart())
@router.message(Command("menu"))
@router.message(F.text == "🏠 Главное меню")
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    set_state_val("owner_chat_id", message.chat.id)
    await message.answer(
        "⌨️ Нижняя панель быстрого доступа активирована.",
        reply_markup=persistent_reply_kb()
    )
    await message.answer(build_welcome_text(), reply_markup=main_menu_kb())

@router.callback_query(F.data == "home")
async def cb_home(call: CallbackQuery, state: FSMContext):
    await state.clear()
    set_state_val("owner_chat_id", call.message.chat.id)
    await call.message.edit_text(build_welcome_text(), reply_markup=main_menu_kb())

# Быстрые команды из синей кнопки «Меню» и нижней клавиатуры
@router.message(Command("parts"))
@router.message(F.text == "🔧 Узлы и Запчасти")
async def msg_parts(message: Message, state: FSMContext):
    await state.clear()
    text, kb = build_parts_categories_view()
    await message.answer(text, reply_markup=kb)

@router.message(Command("fuel"))
@router.message(F.text == "⛽️ Заправка")
async def msg_fuel(message: Message, state: FSMContext):
    await state.clear()
    text, kb = build_fuel_view()
    await message.answer(text, reply_markup=kb)

@router.message(Command("summary"))
@router.message(F.text == "📊 Сводка (ТО / ТР / Бензин)")
async def msg_summary(message: Message, state: FSMContext):
    await state.clear()
    text, kb = build_summary_view()
    await message.answer(text, reply_markup=kb)

@router.message(Command("to"))
@router.message(F.text == "⏳ Регламент ТО")
async def msg_intervals(message: Message, state: FSMContext):
    await state.clear()
    text, kb = build_intervals_view()
    await message.answer(text, reply_markup=kb)

@router.message(Command("mileage"))
@router.message(F.text == "📟 Обновить пробег")
async def msg_mileage(message: Message, state: FSMContext):
    curr = get_state_val("current_mileage")
    await state.set_state(Form.update_mileage)
    await message.answer(
        f"📟 Текущий записанный пробег: <b>{curr:,} км</b>\n\n"
        f"Введи актуальный пробег с одометра (только цифры, например <code>248500</code>):".replace(",", " "),
        reply_markup=back_home_kb()
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
        [InlineKeyboardButton(text="🔍 Открыть оригинальный каталог по VIN на Autodoc", url=vin_autodoc)],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="home")]
    ])
    await call.message.edit_text(text, reply_markup=kb)

# --- 2. ОБНОВЛЕНИЕ ПРОБЕГА ---
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

# --- 3. ПОУЗЛОВОЙ КАТАЛОГ ЗАПЧАСТЕЙ (КАЖДАЯ ДЕТАЛЬ ОТДЕЛЬНО: АРТИКУЛ + AUTODOC + АВИТО) ---
def build_parts_categories_view():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT category, COUNT(*) FROM parts GROUP BY category ORDER BY id")
    categories = cur.fetchall()
    conn.close()

    kb_rows = []
    for idx, (cat, cnt) in enumerate(categories):
        kb_rows.append([InlineKeyboardButton(text=f"{cat} ({cnt} узлов)", callback_data=f"ucat:{idx}")])

    kb_rows.append([InlineKeyboardButton(text="🔎 Найти любую деталь по названию / артикулу", callback_data="custom_search")])
    kb_rows.append([InlineKeyboardButton(text="➕ Добавить свой артикул в базу", callback_data="add_part")])
    kb_rows.append([InlineKeyboardButton(text="⬅️ В главное меню", callback_data="home")])

    text = (
        "🔧 <b>Каталог узлов и запчастей Hyundai Elantra XD (1.6 G4ED АКПП)</b>\n\n"
        "Все детали строго разделены по принадлежности к своему участку авто:\n"
        "1️⃣ Выбери нужный узел (ДВС, АКПП, Навесное, Подвеска и т.д.).\n"
        "2️⃣ Увидишь полный перечень подходящих запчастей и расходников с артикулами.\n"
        "3️⃣ Нажми на любую деталь — откроются отдельные кнопки <b>Autodoc (Новое)</b> и <b>Авито Разборки (Б/У)</b> именно под эту деталь!"
    )
    return text, InlineKeyboardMarkup(inline_keyboard=kb_rows)

@router.callback_query(F.data == "parts_menu")
async def cb_parts_menu(call: CallbackQuery):
    text, kb = build_parts_categories_view()
    await call.message.edit_text(text, reply_markup=kb)

@router.callback_query(F.data.startswith("ucat:"))
async def cb_unit_category(call: CallbackQuery):
    cat_idx = int(call.data.split(":")[1])
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT category FROM parts GROUP BY category ORDER BY id")
    cats = [r[0] for r in cur.fetchall()]
    if cat_idx >= len(cats):
        conn.close()
        return
    cat_name = cats[cat_idx]

    cur.execute("SELECT id, name, article, note FROM parts WHERE category = ?", (cat_name,))
    rows = cur.fetchall()
    conn.close()

    lines = [
        f"📂 <b>Участок: {cat_name}</b>",
        "<i>Полный перечень с артикулами (нажми на номер для копирования, либо выбери конкретную деталь на кнопках ниже для заказа на Autodoc / поиска Б/У на Авито):</i>\n"
    ]
    kb_rows = []
    for part_id, name, art, note in rows:
        lines.append(
            f"▪️ <b>{name}</b>\n"
            f"   Артикул: <code>{art}</code> | <i>{note}</i>"
        )
        kb_rows.append([
            InlineKeyboardButton(text=f"🔩 {name} [{art}]", callback_data=f"pitem:{part_id}:{cat_idx}")
        ])

    kb_rows.append([InlineKeyboardButton(text="⬅️ Назад к выбору узла авто", callback_data="parts_menu")])
    await call.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))

@router.callback_query(F.data.startswith("pitem:"))
async def cb_part_item_detail(call: CallbackQuery):
    _, part_id_str, cat_idx_str = call.data.split(":")
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT category, name, article, note, avito_query FROM parts WHERE id = ?", (int(part_id_str),))
    row = cur.fetchone()
    conn.close()
    if not row:
        await call.answer("Деталь не найдена")
        return

    cat, name, art, note, avito_q = row
    clean_art = art.replace("-", "").strip()
    autodoc_url = f"https://www.autodoc.ru/price/579/{quote(clean_art)}"
    avito_search_str = avito_q if avito_q else f"Hyundai Elantra XD {name} {art}"
    avito_new_or_all_url = f"https://www.avito.ru/moskva_i_mo/zapchasti_i_aksessuary?q={quote(avito_search_str)}"
    avito_art_url = f"https://www.avito.ru/moskva_i_mo/zapchasti_i_aksessuary?q={quote(art)}"

    text = (
        f"🔩 <b>Карточка узла / детали</b>\n\n"
        f"📂 <b>Участок:</b> {cat}\n"
        f"🏷 <b>Наименование:</b> {name}\n"
        f"🔢 <b>Оригинальный артикул:</b> <code>{art}</code> <i>(нажми, чтобы скопировать)</i>\n\n"
        f"⭐ <b>Качественные аналоги и рекомендации:</b>\n{note}\n\n"
        f"👇 <b>Выбери, где искать именно эту деталь:</b>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🛒 Купить НОВОЕ на Autodoc ({art})", url=autodoc_url)],
        [InlineKeyboardButton(text=f"♻️ Найти Б/У на разборке Авито ({name[:22]})", url=avito_new_or_all_url)],
        [InlineKeyboardButton(text=f"🔎 Искать на Авито строго по артикулу {art}", url=avito_art_url)],
        [InlineKeyboardButton(text=f"⬅️ Назад в раздел «{cat}»", callback_data=f"ucat:{cat_idx_str}")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="home")]
    ])
    await call.message.edit_text(text, reply_markup=kb)

@router.callback_query(F.data == "custom_search")
async def cb_custom_search(call: CallbackQuery, state: FSMContext):
    await state.set_state(Form.custom_search)
    await call.message.edit_text(
        "🔎 <b>Универсальный поиск любой детали (Новое + Б/У)</b>\n\n"
        "Напиши в чат название любой запчасти или её артикул (например: <i>Датчик коленвала</i> или <i>39180-22600</i>), "
        "и я сразу выдам отдельные кнопки на <b>Autodoc</b> и на <b>Авито Разборки</b>:",
        reply_markup=back_home_kb()
    )

@router.message(Form.custom_search)
async def process_custom_search(message: Message, state: FSMContext):
    q = message.text.strip()
    await state.clear()
    clean_q = q.replace("-", "")
    autodoc_url = f"https://www.autodoc.ru/price/579/{quote(clean_q)}"
    avito_url = f"https://www.avito.ru/moskva_i_mo/zapchasti_i_aksessuary?q={quote('Hyundai Elantra XD ' + q)}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🛒 Смотреть НОВОЕ на Autodoc ({q})", url=autodoc_url)],
        [InlineKeyboardButton(text=f"♻️ Искать Б/У на Авито Москва/МО ({q})", url=avito_url)],
        [InlineKeyboardButton(text="🔎 Искать другую деталь", callback_data="custom_search")],
        [InlineKeyboardButton(text="⬅️ К узлам автомобиля", callback_data="parts_menu")]
    ])
    await message.answer(f"✅ Ссылки для <b>«{q}»</b> готовы:", reply_markup=kb)

@router.callback_query(F.data == "add_part")
async def cb_add_part(call: CallbackQuery, state: FSMContext):
    await state.set_state(Form.part_category)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🛢 Расходники для ТО", callback_data="setpcat:🛢 Расходники для ТО"),
            InlineKeyboardButton(text="⚙️ ДВС (G4ED) и ГРМ", callback_data="setpcat:⚙️ ДВС (G4ED) и ГРМ")
        ],
        [
            InlineKeyboardButton(text="🕹 АКПП и Приводы", callback_data="setpcat:🕹 АКПП и Приводы"),
            InlineKeyboardButton(text="⚡️ Навесное и Электрика", callback_data="setpcat:⚡️ Навесное и Электрика")
        ],
        [
            InlineKeyboardButton(text="❄️ Охлаждение и Печка", callback_data="setpcat:❄️ Охлаждение и Печка"),
            InlineKeyboardButton(text="🔩 Передняя подвеска и Руль", callback_data="setpcat:🔩 Передняя подвеска и Руль")
        ],
        [
            InlineKeyboardButton(text="🦴 Задняя подвеска", callback_data="setpcat:🦴 Задняя подвеска"),
            InlineKeyboardButton(text="🛑 Тормозная система", callback_data="setpcat:🛑 Тормозная система")
        ],
        [InlineKeyboardButton(text="🚪 Кузов и Оптика (Хэтчбек)", callback_data="setpcat:🚪 Кузов и Оптика (Хэтчбек)")],
        [InlineKeyboardButton(text="⬅️ Отмена", callback_data="parts_menu")]
    ])
    await call.message.edit_text("Выбери узел автомобиля, куда добавить новую запчасть:", reply_markup=kb)

@router.callback_query(Form.part_category, F.data.startswith("setpcat:"))
async def process_part_cat(call: CallbackQuery, state: FSMContext):
    cat = call.data.split(":", 1)[1]
    await state.update_data(category=cat)
    await state.set_state(Form.part_name)
    await call.message.edit_text(f"Узел: <b>{cat}</b>\nВведи точное название детали:")

@router.message(Form.part_name)
async def process_part_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(Form.part_article)
    await message.answer("Введи артикул детали (например: <code>54830-2D000</code>):")

@router.message(Form.part_article)
async def process_part_article(message: Message, state: FSMContext):
    await state.update_data(article=message.text.strip())
    await state.set_state(Form.part_note)
    await message.answer("Введи рекомендованный бренд-аналог или комментарий:")

@router.message(Form.part_note)
async def process_part_note(message: Message, state: FSMContext):
    data = await state.get_data()
    note = message.text.strip()
    avito_q = f"Hyundai Elantra XD {data['name']} {data['article']}"
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO parts (category, name, article, note, avito_query) VALUES (?, ?, ?, ?, ?)",
        (data["category"], data["name"], data["article"], note, avito_q)
    )
    conn.commit()
    conn.close()
    await state.clear()
    await message.answer(
        f"✅ Деталь добавлена в узел <b>{data['category']}</b>!\n"
        f"<b>{data['name']}</b> — <code>{data['article']}</code>",
        reply_markup=main_menu_kb()
    )

# --- 4. УЧЁТ ТОПЛИВА И ЗАПРАВОК ---
def build_fuel_view():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT SUM(cost), SUM(liters), COUNT(*) FROM fuel_log")
    total_fuel_cost, total_liters, count_fuel = cur.fetchone()
    total_fuel_cost = total_fuel_cost or 0
    total_liters = total_liters or 0.0

    cur.execute("SELECT date, mileage, liters, cost FROM fuel_log ORDER BY mileage DESC, id DESC LIMIT 8")
    rows = cur.fetchall()
    conn.close()

    avg_price = (total_fuel_cost / total_liters) if total_liters > 0 else 0

    lines = [
        "⛽️ <b>Журнал заправок и учёт топлива (АИ-92 / АИ-95)</b>\n",
        f"💰 Всего потрачено на бензин: <b>{total_fuel_cost:,} ₽</b>".replace(",", " "),
        f"🛢 Всего залито: <b>{total_liters:.1f} л</b> (заправок: {count_fuel})",
    ]
    if avg_price > 0:
        lines.append(f"📈 Средняя цена литра: <b>{avg_price:.2f} ₽/л</b>")

    if not rows:
        lines.append("\n<i>Записей о заправках пока нет. Нажми «➕ Записать заправку» ниже!</i>")
    else:
        lines.append("\n📋 <b>Последние заправки:</b>")
        for date, mileage, liters, cost in rows:
            p_liter = cost / liters if liters > 0 else 0
            lines.append(
                f"🔸 <b>{date}</b> | Пробег: <code>{mileage:,} км</code>\n"
                f"   Залито: <b>{liters:.1f} л</b> на сумму <b>{cost:,} ₽</b> ({p_liter:.1f} ₽/л)".replace(",", " ")
            )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Записать новую заправку", callback_data="add_fuel")],
        [InlineKeyboardButton(text="📊 Перейти к полной сводке по авто", callback_data="view_logs")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="home")]
    ])
    return "\n".join(lines), kb

@router.callback_query(F.data == "fuel_menu")
async def cb_fuel_menu(call: CallbackQuery):
    text, kb = build_fuel_view()
    await call.message.edit_text(text, reply_markup=kb)

@router.callback_query(F.data == "add_fuel")
async def cb_add_fuel(call: CallbackQuery, state: FSMContext):
    curr = get_state_val("current_mileage")
    await state.set_state(Form.fuel_mileage)
    await call.message.edit_text(
        f"⛽️ <b>Новая заправка</b>\n\n"
        f"Введи текущий пробег на одометре (последний записанный: <code>{curr}</code>):",
        reply_markup=back_home_kb()
    )

@router.message(Form.fuel_mileage)
async def process_fuel_mileage(message: Message, state: FSMContext):
    raw = message.text.replace(" ", "").strip()
    if not raw.isdigit():
        await message.answer("⚠️ Введи пробег только цифрами:")
        return
    m = int(raw)
    await state.update_data(mileage=m)
    if m > get_state_val("current_mileage"):
        set_state_val("current_mileage", m)

    await state.set_state(Form.fuel_liters)
    await message.answer("Сколько литров залил? (например: <code>35</code> или <code>42.5</code>):")

@router.message(Form.fuel_liters)
async def process_fuel_liters(message: Message, state: FSMContext):
    raw = message.text.replace(",", ".").replace(" ", "").strip()
    try:
        liters = float(raw)
    except ValueError:
        await message.answer("⚠️ Введи количество литров числом (например: 40 или 38.5):")
        return
    await state.update_data(liters=liters)
    await state.set_state(Form.fuel_cost)
    await message.answer("На какую сумму в рублях заправился? (например: <code>2350</code>):")

@router.message(Form.fuel_cost)
async def process_fuel_cost(message: Message, state: FSMContext):
    raw = message.text.replace(" ", "").strip()
    if not raw.isdigit():
        await message.answer("⚠️ Введи сумму в рублях целым числом (например: 2350):")
        return
    cost = int(raw)
    data = await state.get_data()
    now_str = datetime.now().strftime("%d.%m.%Y")

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO fuel_log (date, mileage, liters, cost) VALUES (?, ?, ?, ?)",
        (now_str, data["mileage"], data["liters"], cost)
    )
    conn.commit()
    conn.close()
    await state.clear()

    price_per_l = cost / data["liters"] if data["liters"] > 0 else 0
    await message.answer(
        f"✅ <b>Заправка сохранена!</b>\n\n"
        f"📅 Дата: {now_str} | 📟 Пробег: {data['mileage']:,} км\n"
        f"⛽️ Залито: <b>{data['liters']:.1f} л</b> ({price_per_l:.2f} ₽/л)\n"
        f"💰 Сумма: <b>{cost:,} ₽</b>".replace(",", " "),
        reply_markup=main_menu_kb()
    )

# --- 5. ЗАПИСЬ ТО / ТР И ГЛУБОКАЯ СВОДКА ИСТОРИИ АВТО ---
@router.callback_query(F.data == "add_log")
async def cb_add_log(call: CallbackQuery, state: FSMContext):
    curr = get_state_val("current_mileage")
    await state.set_state(Form.log_mileage)
    await call.message.edit_text(
        f"➕ <b>Запись в историю обслуживания авто</b>\n\n"
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
        [InlineKeyboardButton(text="🛢 ТО — Плановое техобслуживание (масла, фильтры, ГРМ)", callback_data="logcat:ТО (Плановое)")],
        [InlineKeyboardButton(text="🔧 ТР — ДВС / АКПП / Навесное", callback_data="logcat:ТР (ДВС и АКПП)")],
        [InlineKeyboardButton(text="🔩 ТР — Ходовка / Подвеска / Тормоза", callback_data="logcat:ТР (Ходовка и Тормоза)")],
        [InlineKeyboardButton(text="🚪 ТР — Кузов / Электрика / Прочее", callback_data="logcat:ТР (Кузов и Электрика)")]
    ])
    await message.answer(
        "Выбери тип работ (<b>ТО</b> — плановое обслуживание или <b>ТР</b> — текущий ремонт):",
        reply_markup=kb
    )

@router.callback_query(Form.log_category, F.data.startswith("logcat:"))
async def process_log_cat(call: CallbackQuery, state: FSMContext):
    cat = call.data.split(":", 1)[1]
    await state.update_data(category=cat)
    await state.set_state(Form.log_desc)
    await call.message.edit_text(
        f"Тип работ: <b>{cat}</b>\n\n"
        f"Подробно опиши, что сделали и какие запчасти (бренды/артикулы) поставили:"
    )

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
        f"✅ <b>Запись сохранена в историю авто!</b>\n\n"
        f"📅 Дата: {now_str} | 📟 Пробег: {data['mileage']:,} км\n"
        f"🏷 Тип: <b>{data['category']}</b>\n"
        f"🛠 Работы: {data['description']}\n"
        f"💰 Сумма: <b>{cost:,} ₽</b>".replace(",", " "),
        reply_markup=main_menu_kb()
    )

def build_summary_view(filter_mode: str = "all"):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # Считаем статистику по Плановому ТО
    cur.execute("SELECT SUM(cost), COUNT(*), MAX(mileage), MAX(date) FROM service_log WHERE category LIKE 'ТО%'")
    to_cost, to_cnt, last_to_m, last_to_date = cur.fetchone()
    to_cost = to_cost or 0

    # Считаем статистику по Текущему Ремонту (ТР)
    cur.execute("SELECT SUM(cost), COUNT(*), MAX(mileage), MAX(date) FROM service_log WHERE category NOT LIKE 'ТО%'")
    tr_cost, tr_cnt, last_tr_m, last_tr_date = cur.fetchone()
    tr_cost = tr_cost or 0

    # Считаем топливо
    cur.execute("SELECT SUM(cost), SUM(liters), COUNT(*) FROM fuel_log")
    fuel_cost, fuel_liters, fuel_cnt = cur.fetchone()
    fuel_cost = fuel_cost or 0
    fuel_liters = fuel_liters or 0.0

    # Считаем пройденный пробег по базе для расчёта стоимости 1 км
    cur.execute("""
        SELECT MIN(m), MAX(m) FROM (
            SELECT mileage AS m FROM service_log WHERE mileage > 0
            UNION ALL
            SELECT mileage AS m FROM fuel_log WHERE mileage > 0
        )
    """)
    min_m, max_m = cur.fetchone()
    curr_m = get_state_val("current_mileage")
    if curr_m > (max_m or 0):
        max_m = curr_m
    tracked_km = (max_m - min_m) if (min_m and max_m and max_m > min_m) else 0

    total_all = to_cost + tr_cost + fuel_cost

    # Выборка записей по фильтру
    if filter_mode == "to":
        cur.execute("SELECT date, mileage, category, description, cost FROM service_log WHERE category LIKE 'ТО%' ORDER BY mileage DESC, id DESC LIMIT 12")
        filter_title = "🛢 Только Плановое ТО"
    elif filter_mode == "tr":
        cur.execute("SELECT date, mileage, category, description, cost FROM service_log WHERE category NOT LIKE 'ТО%' ORDER BY mileage DESC, id DESC LIMIT 12")
        filter_title = "🔧 Только Текущий Ремонт (ТР)"
    else:
        cur.execute("SELECT date, mileage, category, description, cost FROM service_log ORDER BY mileage DESC, id DESC LIMIT 10")
        filter_title = "📋 Все работы (ТО + ТР)"

    rows = cur.fetchall()
    conn.close()

    last_to_str = f"на {last_to_m:,} км ({last_to_date})".replace(",", " ") if last_to_m else "нет записей"
    last_tr_str = f"на {last_tr_m:,} км ({last_tr_date})".replace(",", " ") if last_tr_m else "нет записей"

    lines = [
        f"📊 <b>Глубокая аналитика и сводка по {CAR_PROFILE['model']}</b>\n",
        f"🛢 <b>Плановое ТО:</b> {to_cost:,} ₽ (работ: {to_cnt}) | Последнее: {last_to_str}".replace(",", " "),
        f"🔧 <b>Текущий ремонт (ТР):</b> {tr_cost:,} ₽ (работ: {tr_cnt}) | Последний: {last_tr_str}".replace(",", " "),
        f"⛽️ <b>Топливо (бензин):</b> {fuel_cost:,} ₽ ({fuel_liters:.1f} л / заправок: {fuel_cnt})".replace(",", " "),
        f"━━━━━━━━━━━━━━━",
        f"💰 <b>ИТОГО вложено (ТО + ТР + Топливо):</b> <b>{total_all:,} ₽</b>".replace(",", " ")
    ]
    if tracked_km > 0:
        cost_per_km = total_all / tracked_km
        lines.append(f"🛣 <b>Стоимость 1 км пробега:</b> <b>{cost_per_km:.2f} ₽/км</b> (за {tracked_km:,} км)".replace(",", " "))

    lines.append(f"\n📓 <b>Хронология [{filter_title}]:</b>")
    if not rows:
        lines.append("<i>В этой категории пока нет записей.</i>")
    else:
        for date, mileage, cat, desc, cost in rows:
            icon = "🛢" if cat.startswith("ТО") else "🔧"
            lines.append(
                f"{icon} <b>{mileage:,} км</b> ({date}) — <b>[{cat}]</b>\n"
                f"   └ {desc} — <b>{cost:,} ₽</b>".replace(",", " ")
            )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Все", callback_data="logs_filter:all"),
            InlineKeyboardButton(text="🛢 Только ТО", callback_data="logs_filter:to"),
            InlineKeyboardButton(text="🔧 Только ТР", callback_data="logs_filter:tr")
        ],
        [
            InlineKeyboardButton(text="➕ Записать ТО / ТР", callback_data="add_log"),
            InlineKeyboardButton(text="⛽️ Журнал топлива", callback_data="fuel_menu")
        ],
        [
            InlineKeyboardButton(text="💾 Скачать всю историю в Excel (.csv)", callback_data="export_csv")
        ],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="home")]
    ])
    return "\n".join(lines), kb

@router.callback_query(F.data == "view_logs")
async def cb_view_logs(call: CallbackQuery):
    text, kb = build_summary_view("all")
    await call.message.edit_text(text, reply_markup=kb)

@router.callback_query(F.data.startswith("logs_filter:"))
async def cb_logs_filter(call: CallbackQuery):
    mode = call.data.split(":")[1]
    text, kb = build_summary_view(mode)
    await call.message.edit_text(text, reply_markup=kb)

# --- 6. ВЫГРУЗКА ОТЧЁТА В EXCEL (CSV) ---
@router.callback_query(F.data == "export_csv")
async def cb_export_csv(call: CallbackQuery):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT date, mileage, category, description, cost FROM service_log ORDER BY mileage DESC")
    s_rows = cur.fetchall()
    cur.execute("SELECT date, mileage, liters, cost FROM fuel_log ORDER BY mileage DESC")
    f_rows = cur.fetchall()
    conn.close()

    output = io.StringIO()
    output.write('\ufeff')  # BOM для корректного открытия русского текста в Microsoft Excel
    writer = csv.writer(output, delimiter=';')
    writer.writerow(["Дата", "Пробег (км)", "Тип записи", "Описание / Литры", "Сумма (руб.)"])

    for date, mileage, cat, desc, cost in s_rows:
        writer.writerow([date, mileage, cat, desc, cost])
    for date, mileage, liters, cost in f_rows:
        writer.writerow([date, mileage, "Топливо (АЗС)", f"Заправка {liters} л", cost])

    csv_bytes = output.getvalue().encode("utf-8")
    doc = BufferedInputFile(csv_bytes, filename=f"Elantra_XD_History_{datetime.now().strftime('%Y-%m-%d')}.csv")
    await call.message.answer_document(
        doc,
        caption="📊 <b>Полная выгрузка бортжурнала Hyundai Elantra XD (ТО, ТР и Топливо)</b>\nОткрывается в Excel или Google Таблицах."
    )
    await call.answer("Файл выгружен!")

# --- 7. ШПАРГАЛКА В ДОРОГЕ (РАЗБОЛТОВКА, ШИНЫ, ЛАМПЫ, ЩЁТКИ) ---
@router.callback_query(F.data == "road_help")
async def cb_road_help(call: CallbackQuery):
    text = (
        "🚨 <b>Быстрая шпаргалка по Hyundai Elantra XD (Хэтчбек 1.6)</b>\n\n"
        "🛞 <b>Колёса, диски и давление:</b>\n"
        "• <b>Разболтовка (PCD):</b> <code>4x114.3</code> (Внимание: не 4x100!)\n"
        "• <b>Центральное отверстие (DIA):</b> <code>67.1 мм</code> | Гайки: <code>M12x1.5</code>\n"
        "• <b>Вылет (ET):</b> штатный <code>ET46</code> (подходят 40–46), ширина <code>6J R15</code>\n"
        "• <b>Штатный размер шин:</b> <code>195/60 R15</code> (или <code>185/65 R15</code>) | Давление: <b>2.1 атм</b> (перед и зад)\n\n"
        "💡 <b>Лампы (Рестайлинг):</b>\n"
        "• <b>Ближний свет:</b> <code>H7</code> (55W)\n"
        "• <b>Дальний свет:</b> <code>H1</code> (55W)\n"
        "• <b>Противотуманки (ПТФ):</b> <code>H3</code> (55W)\n"
        "• <b>Передние габариты / подсветка номера:</b> бесцокольные <code>W5W (T10)</code>\n"
        "• <b>Стоп-сигнал / задний габарит:</b> двухнитевая <code>P21/5W</code>\n\n"
        "🌧 <b>Щётки стеклоочистителя (Дворники Хэтчбек):</b>\n"
        "• <b>Водительская (левая):</b> <code>500 мм (20\")</code> — крепление Крючок (Hook)\n"
        "• <b>Пассажирская (правая):</b> <code>450 мм (18\")</code> — крепление Крючок\n"
        "• <b>Задний дворник (5-я дверь Хэтчбека):</b> <code>500 мм (20\")</code>!"
    )
    await call.message.edit_text(text, reply_markup=back_home_kb())

# --- 8. ЖИДКОСТИ, БОЛЯЧКИ И СЕРВИСЫ ---
@router.callback_query(F.data == "fluids_info")
async def cb_fluids_info(call: CallbackQuery):
    text = (
        "🧪 <b>Рекомендуемые жидкости и объёмы (Elantra XD 1.6 G4ED АКПП)</b>\n\n"
        "🛢 <b>1. Моторное масло (ДВС G4ED):</b>\n"
        "• <b>Объём при замене:</b> <code>3.3 л</code> (с фильтром)\n"
        "• <b>Вязкость:</b> <b>5W-30</b> или <b>5W-40</b> (ACEA A3/B4 или API SL/SN/SP).\n"
        "• <b>Топ бренды:</b> ZIC X9 5W-30 / 5W-40, Kixx G1 5W-30, S-Oil Red #9 5W-30, Lukoil Armortech HK 5W-30.\n\n"
        "⚙️ <b>2. Жидкость АКПП (4-ст. автомат F4A42):</b>\n"
        "• <b>Допуск СТРОГО:</b> <b>ATF SP-III</b> (4 л на частичную замену / 7.8 л полный объём).\n"
        "• <b>Топ артикулы (4л):</b> ZIC ATF SP 3 (<code>162627</code>), Hyundai Mobis ATF SP-III (<code>04500-00400</code>).\n\n"
        "🛑 <b>3. Тормозная жидкость:</b>\n"
        "• <b>Допуск:</b> <b>DOT-4</b> (0.8 л). Аналоги: TRW PFB401, RosDot 4 Class 6.\n\n"
        "❄️ <b>4. Антифриз:</b>\n"
        "• <b>Допуск:</b> Фосфатный лобридный P-OAT (6.0 л). Топ: Coolstream A-110 (<code>CS-010502</code>).\n\n"
        "🛞 <b>5. Жидкость ГУР:</b>\n"
        "• <b>Допуск:</b> <b>PSF-3</b> (0.9 л). Топ: Hyundai PSF-3 (<code>03100-00100</code>), ZIC PSF 3."
    )
    await call.message.edit_text(text, reply_markup=back_home_kb())

@router.callback_query(F.data == "quirks_menu")
async def cb_quirks_menu(call: CallbackQuery):
    text = (
        "⚠️ <b>Нюансы и болячки Hyundai Elantra XD по пробегам (опыт Elantra-Club)</b>\n\n"
        "🔹 <b>Каждые 55 000 – 60 000 км:</b>\n"
        "• <b>Ремень ГРМ:</b> на G4ED при обрыве <b>ГНЁТ КЛАПАНА</b>! Менять строго раз в 60 тыс. км.\n"
        "• <b>Гофра глушителя:</b> размер <code>50x200</code> (трёхслойная Interlock).\n\n"
        "🔸 <b>Пробег 120 000 – 160 000 км:</b>\n"
        "• <b>Межвальная цепь распредвалов (<code>24321-26020</code>):</b> растягивается и дизелит на холодную.\n"
        "• <b>Крышка радиатора (<code>25330-17000</code>):</b> если закисает клапан — рвёт верхний бачок радиатора.\n\n"
        "🔴 <b>Пробег 200 000 – 250 000+ км:</b>\n"
        "• <b>Задняя балка (подрамник):</b> гниёт изнутри от реагентов, обязательно антикорить!\n"
        "• <b>Закисшие развальные болты (<code>55220-2D000</code>):</b> смазывать графиткой при замене.\n"
        "• <b>Пинки АКПП 2→3:</b> проверять датчики входного/выходного вала (<code>42620-39051</code> / <code>42621-39052</code>).\n"
        "• <b>Коса 5-й двери (Хэтчбек):</b> переламываются провода в гофре крышки багажника."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Открыть форум Elantra-Club.ru", url="https://elantra-club.ru/forum/")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="home")]
    ])
    await call.message.edit_text(text, reply_markup=kb)

@router.callback_query(F.data == "services_msk")
async def cb_services_msk(call: CallbackQuery):
    text = (
        "🏢 <b>Проверенные клубные сервисы Hyundai Elantra (Москва и МО)</b>\n\n"
        "1️⃣ <b>Клубный техцентр «AVIS-Motors» (ЮВАО)</b>\n"
        "• 📍 Москва, Михайловский проезд, д. 3, стр. 5 | 📞 <code>+7 (495) 228-03-50</code>\n"
        "• 🛠 Специализация на Elantra XD с 2005 года, гарантия на ГРМ, свой склад запчастей.\n\n"
        "2️⃣ <b>Клубный сервис «Большой Кореец» (СВАО / ЗАО / Дзержинский)</b>\n"
        "• 📍 СВАО: Берёзовая аллея, 4А | 📞 <code>+7 (906) 084-16-12</code>\n"
        "• 📍 ЗАО: Рябиновая ул., 34В, стр. 1 | 📞 <code>+7 (964) 648-30-28</code>\n"
        "• 📍 МО: г. Дзержинский, ул. Энергетиков, д. 28 | 📞 <code>+7 (964) 649-91-89</code>\n\n"
        "3️⃣ <b>СпецСервис «ОЕМ-Зап / Корея-Авто» (СВАО / ЮАО)</b>\n"
        "• 📍 Алтуфьевское ш., 48 к. 4 / ул. Речников, 19 (электрика, моторы G4ED, АКПП)."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Сайт AVIS-Motors (Elantra XD)", url="https://www.avis-motors.ru/remont/hyundai/elantra-j3-xd/")],
        [InlineKeyboardButton(text="🌐 Сайт сервиса Большой Кореец", url="https://bigk.su/")],
        [InlineKeyboardButton(text="💬 Ветка сервисов на Elantra-Club.ru", url="https://elantra-club.ru/forum/")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="home")]
    ])
    await call.message.edit_text(text, reply_markup=kb)

# --- 9. РЕГЛАМЕНТ ТО ---
def build_intervals_view():
    curr = get_state_val("current_mileage")
    lines = [
        "⏳ <b>Контроль регламентов и Напоминания о ТО</b>",
        "<i>Бот автоматически проверяет пробег и напоминает, когда до замены остаётся меньше 1 000 км.</i>"
    ]
    if curr == 0:
        lines.append("\n⚠️ <b>Сначала укажи актуальный пробег!</b>\n")
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
    await call.answer(f"Замена зафиксирована на {curr} км!")
    text, kb = build_intervals_view()
    await call.message.edit_text(text, reply_markup=kb)

# =====================================================================
# 🔔 ФОНОВЫЙ ТАЙМЕР И НАСТРОЙКА СИНЕЙ КНОПКИ «МЕНЮ» В TELEGRAM
# =====================================================================
async def auto_reminder_loop(bot: Bot):
    while True:
        await asyncio.sleep(12 * 3600)
        chat_id = get_state_val("owner_chat_id")
        alerts = get_due_warnings()
        if chat_id and alerts:
            try:
                await bot.send_message(
                    chat_id,
                    "🔔 <b>Плановое напоминание по твоей Hyundai Elantra XD:</b>\n\n"
                    + "\n".join(alerts),
                    reply_markup=main_menu_kb()
                )
            except Exception:
                pass

async def setup_bot_menu(bot: Bot):
    commands = [
        BotCommand(command="start", description="🏠 Открыть главное меню"),
        BotCommand(command="parts", description="🔧 Узлы и запчасти (Autodoc + Авито)"),
        BotCommand(command="fuel", description="⛽️ Записать заправку / Топливо"),
        BotCommand(command="summary", description="📊 Полная сводка (ТО / ТР / Расходы)"),
        BotCommand(command="to", description="⏳ Регламент и напоминания о ТО"),
        BotCommand(command="mileage", description="📟 Обновить текущий пробег"),
    ]
    await bot.set_my_commands(commands)

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
    await setup_bot_menu(bot)
    dp = Dispatcher()
    dp.include_router(router)
    asyncio.create_task(auto_reminder_loop(bot))
    print("🚗 Бортжурнал Hyundai Elantra XD v3.0 запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
