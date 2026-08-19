import asyncio
import logging
import json
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, 
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# ==========================================
# 1. TIZIM SOZLAMALARI VA TARIFLAR
# ==========================================
MAKER_BOT_TOKEN = "8708370464:AAEohNE68EdRuzn8H6bN0oZAD224jAMajoM"
ADMIN_ID = 7849637859  # Asosiy Admin Telegram IDsi

# Tariflar va Shartlar
PRICE_INITIAL = 35000   # 35,000 UZS (17 kun)
PRICE_RENEWAL = 11000   # 11,000 UZS (17 kun uzaytirish)
DURATION_DAYS = 17      # 17 kun faollik

# Referal va Almos
DEFAULT_REF_DIAMONDS = 5   # Har bir referal uchun 5 almos
DEFAULT_MIN_WITHDRAW = 210  # Minimal yechish: 210 almos

# Xotira bazasi (Production uchun PostgreSQL / SQLAlchemy ishlatiladi)
DB = {
    "users": {},        # {user_id: {"balance": 0, "diamonds": 0, "ref_by": None}}
    "bots": {},         # {bot_token: {"owner_id": 123, "type": 1, "expires": "..."}, "channels": [], "buttons": []}
    "movies": {},       # {"30224030": {"title": "Kino nomi", "file_id": "ABC123xyz"}}
    "withdraws": []     # Yechib olish so'rovlari
}

bot = Bot(token=MAKER_BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# FSM Holatlari
class BotCreation(StatesGroup):
    waiting_for_token = State()

class AddMovie(StatesGroup):
    waiting_for_code = State()
    waiting_for_file = State()

# ==========================================
# 2. MAKER BOT - ASOSIY PANEL VA BOT YARATISH
# ==========================================
@dp.message(Command("start"))
async def cmd_start(msg: types.Message, command: CommandObject = None):
    user_id = msg.from_user.id
    
    # Referal tizimi
    if user_id not in DB["users"]:
        ref_id = None
        if command and command.args and command.args.isdigit():
            possible_ref = int(command.args)
            if possible_ref != user_id and possible_ref in DB["users"]:
                ref_id = possible_ref
                DB["users"][ref_id]["diamonds"] += DEFAULT_REF_DIAMONDS
                
        DB["users"][user_id] = {"balance": 0.0, "diamonds": 0, "ref_by": ref_id}

    text = (
        "<b>🌍 BUTUN DUNYODA YAGONA — MAKER BOT PLATFORMASI</b>\n\n"
        "Yangi bot yaratish: <b>35,000 so'm</b> (17 kunlik faoliyat).\n"
        "Uzaytirish to'lovi: Har 17 kunda <b>11,000 so'm</b>.\n\n"
        "💎 <b>Referal Tizimi:</b>\n"
        "• Har bir chaqirilgan do'st uchun: <b>5 Almos</b>\n"
        "• Minimal yechib olish: <b>210 Almos</b>\n\n"
        "Kerakli bo'limni tanlang:"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Yangi Bot Yaratish (35,000 UZS)", callback_data="create_bot")],
        [InlineKeyboardButton(text="📚 20 ta Bot Katalogi", callback_data="catalog")],
        [InlineKeyboardButton(text="💎 Referal va Almoslarim", callback_data="ref_info")],
        [InlineKeyboardButton(text="⚙️ Admin Panel", callback_data="admin_panel")]
    ])
    await msg.answer(text, parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "catalog")
async def show_catalog(call: types.CallbackQuery):
    text = (
        "<b>📋 YARATISH MUMKIN BO'LGAN 20 TA BOT:</b>\n\n"
        "1. 🎬 Kino Bot (Kodli va obunali - @30224030 analogi)\n"
        "2. 🎁 Referal / Konkurs Bot\n"
        "3. 🛒 E-Commerce Do'kon Bot\n"
        "4. 💬 Anonim Chat Bot\n"
        "5. 🧠 AI Sun'iy Intellekt Bot\n"
        "6. 📥 Downloader Bot (Insta, TikTok, YT)\n"
        "7. 📝 Test / Viktorina Bot\n"
        "8. 🛡 VPN Sotuvchi Bot\n"
        "9. 🎵 Musiqa Qidiruv (Shazam) Bot\n"
        "10. 🔱 Valyuta Konverter Bot\n"
        "11. 📩 Temp SMS / Mail Bot\n"
        "12. 📄 PDF Konverter Bot\n"
        "13. ✍️ Auto-Format Text Bot\n"
        "14. 💼 Portfolio / Rezyume Bot\n"
        "15. 📈 Crypto Price Alert Bot\n"
        "16. 🔮 Horoscope / Bashorat Bot\n"
        "17. 📞 Feedback / Murojaat Bot\n"
        "18. 🎮 Mini Game Bot\n"
        "19. 🔗 URL Shortener Bot\n"
        "20. 🛠 Universal Constructor Bot"
    )
    await call.message.edit_text(text, parse_mode="HTML")

@dp.callback_query(F.data == "ref_info")
async def ref_info(call: types.CallbackQuery):
    user_id = call.from_user.id
    diamonds = DB["users"][user_id]["diamonds"]
    me = await bot.get_me()
    ref_link = f"https://t.me/{me.username}?start={user_id}"
    
    text = (
        f"💎 <b>Sizning Almoslaringiz:</b> {diamonds} ta\n"
        f"🔗 <b>Referal havolangiz:</b>\n<code>{ref_link}</code>\n\n"
        f"• 1 ta referal uchun = 5 almos.\n"
        f"• Minimal yechib olish = 210 almos."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Almoslarni Yechib Olish", callback_data="withdraw_diamonds")]
    ])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "withdraw_diamonds")
async def withdraw(call: types.CallbackQuery):
    user_id = call.from_user.id
    diamonds = DB["users"][user_id]["diamonds"]
    if diamonds < DEFAULT_MIN_WITHDRAW:
        await call.answer(f"❌ Yechish uchun kamida {DEFAULT_MIN_WITHDRAW} almos kerak! Sizda: {diamonds} ta.", show_alert=True)
    else:
        DB["users"][user_id]["diamonds"] -= DEFAULT_MIN_WITHDRAW
        DB["withdraws"].append({"user_id": user_id, "amount": DEFAULT_MIN_WITHDRAW})
        await call.answer("✅ Yechib olish so'rovi adminga yuborildi!", show_alert=True)

@dp.callback_query(F.data == "create_bot")
async def process_create_bot(call: types.CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    user_bal = DB["users"][user_id]["balance"]
    
    if user_bal < PRICE_INITIAL:
        await call.message.answer(
            f"❌ Balansingizda yetarli mablag' yo'q!\n"
            f"Bot yaratish narxi: <b>35,000 so'm</b> (17 kun uchun).\n"
            f"Sizning balansingiz: <b>{user_bal} so'm</b>.",
            parse_mode="HTML"
        )
        return

    await state.set_state(BotCreation.waiting_for_token)
    await call.message.answer("🤖 BotFather'dan olingan Bot Tokenini yuboring:")

@dp.message(BotCreation.waiting_for_token)
async def receive_bot_token(msg: types.Message, state: FSMContext):
    token = msg.text.strip()
    user_id = msg.from_user.id
    
    # Balansdan ayirish va botni ro'yxatga olish
    DB["users"][user_id]["balance"] -= PRICE_INITIAL
    expires = datetime.now() + timedelta(days=DURATION_DAYS)
    
    DB["bots"][token] = {
        "owner_id": user_id,
        "type": 1,  # Defolt: 1-Kino Bot
        "expires": expires.strftime("%Y-%m-%d %H:%M"),
        "channels": [],
        "buttons": []
    }
    
    await state.clear()
    await msg.answer(
        f"✅ Bot muvaffaqiyatli yaratildi!\n"
        f"📅 Faoliyat muddati: <b>17 kun</b> (Tugash vaqti: {expires.strftime('%Y-%m-%d')})\n"
        f"🔄 Keyingi uzaytirish: <b>11,000 so'm</b>.",
        parse_mode="HTML"
    )

# ==========================================
# 3. YARATILADIGAN 20 TA BOT ENGINE SHABLONI
# ==========================================
class BotEngine:
    def __init__(self, token: str, bot_type: int):
        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        self.bot_type = bot_type
        self.token = token
        self.register_handlers()

    async def check_sub(self, user_id: int) -> bool:
        channels = DB["bots"].get(self.token, {}).get("channels", [])
        for ch in channels:
            try:
                member = await self.bot.get_chat_member(chat_id=ch, user_id=user_id)
                if member.status in ["left", "kicked"]:
                    return False
            except Exception:
                pass
        return True

    def register_handlers(self):
        # 1. Kino Bot (@30224030 style)
        if self.bot_type == 1:
            @self.dp.message(Command("start"))
            async def k_start(msg: types.Message):
                await msg.answer("🎬 Kino kodi yoki nomini kiriting (Masalan: 30224030):")

            @self.dp.message(F.text)
            async def k_search(msg: types.Message):
                if not await self.check_sub(msg.from_user.id):
                    await msg.answer("❌ Kinoni ko'rish uchun avval majburiy kanallarga obuna bo'ling!")
                    return
                code = msg.text.strip()
                if code in DB["movies"]:
                    movie = DB["movies"][code]
                    await msg.answer_video(video=movie["file_id"], caption=f"🎥 {movie['title']}")
                else:
                    await msg.answer(f"❌ {code} kodli kino topilmadi.")

        # 2. Referal Bot
        elif self.bot_type == 2:
            @self.dp.message(Command("start"))
            async def r_start(msg: types.Message):
                me = await self.bot.get_me()
                link = f"https://t.me/{me.username}?start={msg.from_user.id}"
                await msg.answer(f"🎁 Referal havolangiz:\n{link}\n\nHar bir taklif uchun 5 almos bering!")

        # 3. E-Commerce Do'kon Bot
        elif self.bot_type == 3:
            @self.dp.message(Command("start"))
            async def s_start(msg: types.Message):
                await msg.answer("🛒 Do'konimizga xush kelibsiz! Mahsulotlar katalogi yuklanmoqda...")

        # 4. Anonim Chat Bot
        elif self.bot_type == 4:
            @self.dp.message(Command("start"))
            async def a_start(msg: types.Message):
                await msg.answer("💬 Tasodifiy suhbatdosh qidirilmoqda...")

        # 5. AI Bot
        elif self.bot_type == 5:
            @self.dp.message(F.text)
            async def ai_chat(msg: types.Message):
                await msg.answer(f"🧠 AI Javobi: '{msg.text}' bo'yicha tahlil yakunlandi.")

        # 6. Downloader Bot
        elif self.bot_type == 6:
            @self.dp.message(F.text.contains("http"))
            async def dl_media(msg: types.Message):
                await msg.answer("📥 Media yuklab olinmoqda, kuting...")

        # 7-20. Qolgan botlar uchun universal handlerlar
        else:
            @self.dp.message(Command("start"))
            async def gen_start(msg: types.Message):
                await msg.answer(f"🤖 Bot №{self.bot_type} ishga tushdi! Admin panel orqali sozlashingiz mumkin.")

    async def start(self):
        await self.dp.start_polling(self.bot)

# ==========================================
# 4. ADMIN PANEL VA KINO YUKLASH TIZIMI
# ==========================================
@dp.callback_query(F.data == "admin_panel")
async def admin_panel_handler(call: types.CallbackQuery):
    user_id = call.from_user.id
    if user_id != ADMIN_ID:
        await call.answer("❌ Bu bo'lim faqat bosh admin uchun!", show_alert=True)
        return

    text = (
        "<b>⚙️ MAKER BOT ADMIN PANELI</b>\n\n"
        f"• Jami foydalanuvchilar: {len(DB['users'])}\n"
        f"• Yaratilgan botlar: {len(DB['bots'])}\n"
        f"• Bazadagi kinolar: {len(DB['movies'])}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 Kinoga Kod va Video Qo'shish", callback_data="add_movie")],
        [InlineKeyboardButton(text="📢 Majburiy Obuna Qo'shish", callback_data="add_sub_channel")],
        [InlineKeyboardButton(text="🔘 Tugma Qo'shish / O'zgartirish", callback_data="edit_buttons")]
    ])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "add_movie")
async def add_movie_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddMovie.waiting_for_code)
    await call.message.answer("🎬 Kinoga kod qo'ying (Masalan: 30224030):")

@dp.message(AddMovie.waiting_for_code)
async def add_movie_code(msg: types.Message, state: FSMContext):
    await state.update_data(code=msg.text.strip())
    await state.set_state(AddMovie.waiting_for_file)
    await call_or_msg_answer(msg, "🎥 Endi ushbu kodga tegishli video faylini yuboring:")

@dp.message(AddMovie.waiting_for_file, F.video)
async def add_movie_file(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    code = data["code"]
    file_id = msg.video.file_id
    caption = msg.caption or f"Kino {code}"

    DB["movies"][code] = {"title": caption, "file_id": file_id}
    await state.clear()
    await msg.answer(f"✅ Kino muvaffaqiyatli saqlandi!\nKod: <b>{code}</b>", parse_mode="HTML")

async def call_or_msg_answer(msg: types.Message, text: str):
    await msg.answer(text)

# ==========================================
# 5. SERVERDA ISHGA TUSHIRISH
# ==========================================
async def main():
    print("Maker Bot Platforma muvaffaqiyatli ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
