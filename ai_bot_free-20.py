import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# ==========================================
# 1. SOZLAMALAR VA BAZA
# ==========================================
MAKER_BOT_TOKEN = "8708370464:AAEMJn5gULP7Q-suO1_7PUdz3-glZsaOCgc"  # BotFather'dan olingan asosiy token
ADMIN_ID = 7849637859                           # Admin Telegram ID

PRICE_INITIAL = 35000.0   # Bot yaratish (17 kun)
PRICE_RENEWAL = 11000.0   # Uzaytirish
DURATION_DAYS = 17

CARD_NUMBER = "5440 8103 1990 4917"  # To'lov uchun karta raqamingiz
CARD_HOLDER = "g/n"

DB = {
    "users": {},        # {user_id: {"balance": 0.0, "diamonds": 0, "ref_by": None}}
    "bots": {},         # {token: {"owner": id, "type": 1, "expires": datetime, "channels": []}}
    "movies": {},       # {code: {"title": str, "file_id": str}}
    "payments": {}      # {pay_id: {"user_id": id, "amount": int, "status": "pending"}}
}

# Yaratilgan barcha kichik botlarni saqlash va boshqarish uchun
RUNNING_BOTS = {}

bot = Bot(token=MAKER_BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# FSM Holatlari
class BotCreation(StatesGroup):
    waiting_for_type = State()
    waiting_for_token = State()

class Deposit(StatesGroup):
    waiting_for_amount = State()
    waiting_for_receipt = State()

class AddMovie(StatesGroup):
    waiting_for_code = State()
    waiting_for_file = State()

# ==========================================
# 2. DYNAMIC BOT ENGINE (Yaratilgan botlarni fonda yurgizish)
# ==========================================
async def start_sub_bot(token: str, bot_type: int):
    """Foydalanuvchi yaratgan botni fonda alohida ishga tushirish engine'i"""
    try:
        sub_bot = Bot(token=token)
        sub_dp = Dispatcher()

        if bot_type == 1: # Kino Bot
            @sub_dp.message(Command("start"))
            async def sub_start(msg: types.Message):
                await msg.answer("🎬 **Kino Botga xush kelibsiz!**\nKino kodini kiriting (Masalan: 30224030):")

            @sub_dp.message(F.text)
            async def sub_search(msg: types.Message):
                code = msg.text.strip()
                if code in DB["movies"]:
                    m = DB["movies"][code]
                    await msg.answer_video(video=m["file_id"], caption=f"🎥 **{m['title']}**")
                else:
                    await msg.answer(f"❌ '{code}' kodli kino topilmadi.")

        else: # Boshqa bot turlari uchun unversal menyu
            @sub_dp.message(Command("start"))
            async def sub_gen(msg: types.Message):
                await msg.answer(f"🤖 **Bot №{bot_type} muvaffaqiyatli ishlamoqda!**\nBarcha tizimlar aktiv statusda.")

        RUNNING_BOTS[token] = sub_bot
        asyncio.create_task(sub_dp.start_polling(sub_bot))
    except Exception as e:
        logging.error(f"Botni ishga tushirishda xatolik ({token}): {e}")

# ==========================================
# 3. ASOSIY MAKER BOT LOGIKASI
# ==========================================
@dp.message(Command("start"))
async def cmd_start(msg: types.Message, command: CommandObject = None):
    user_id = msg.from_user.id
    if user_id not in DB["users"]:
        ref_id = int(command.args) if (command and command.args and command.args.isdigit() and int(command.args) != user_id) else None
        if ref_id and ref_id in DB["users"]:
            DB["users"][ref_id]["diamonds"] += 5
        DB["users"][user_id] = {"balance": 0.0, "diamonds": 0, "ref_by": ref_id}

    bal = DB["users"][user_id]["balance"]
    diamonds = DB["users"][user_id]["diamonds"]

    text = (
        "<b>🌍 MAKER BOT — PROFESSIONAL BOT YARATISH PLATFORMASI</b>\n\n"
        f"💳 Balansingiz: <b>{bal:,.0f} so'm</b>\n"
        f"💎 Almoslaringiz: <b>{diamonds} ta</b>\n\n"
        "• Yangi bot yaratish: <b>35,000 so'm</b> (17 kun)\n"
        "• Botni uzaytirish: <b>11,000 so'm</b> / 17 kun\n\n"
        "Kerakli bo'limni tanlang:"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Yangi Bot Yaratish", callback_data="create_bot"), InlineKeyboardButton(text="💳 Balans To'ldirish", callback_data="deposit")],
        [InlineKeyboardButton(text="📚 20 ta Bot Katalogi", callback_data="catalog"), InlineKeyboardButton(text="💎 Referal Tizimi", callback_data="ref_info")],
        [InlineKeyboardButton(text="⚙️ Admin Panel", callback_data="admin_panel")]
    ])
    await msg.answer(text, parse_mode="HTML", reply_markup=kb)

# --- BALANS TO'LDIRISH (KARTA ORQALI) ---
@dp.callback_query(F.data == "deposit")
async def deposit_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(Deposit.waiting_for_amount)
    await call.message.answer("💳 Qancha summap (so'mda) to'lamoqchisiz? (Masalan: 35000):")

@dp.message(Deposit.waiting_for_amount)
async def deposit_amount(msg: types.Message, state: FSMContext):
    if not msg.text.isdigit():
        await msg.answer("❌ Fikr faqat raqamlardan iborat bo'lishi kerak!")
        return
    
    amount = int(msg.text)
    await state.update_data(amount=amount)
    await state.set_state(Deposit.waiting_for_receipt)

    text = (
        f"📥 <b>To'lov miqdori:</b> {amount:,.0f} so'm\n\n"
        f"Quyidagi kartaga o'tkazmani amalga oshiring:\n"
        f"💳 Karta: <code>{CARD_NUMBER}</code>\n"
        f"👤 Egasining ismi: <b>{CARD_HOLDER}</b>\n\n"
        "To'lovni amalga oshirgach, <b>chek rasmini (screenshot)</b> ushbu chatga yuboring:"
    )
    await msg.answer(text, parse_mode="HTML")

@dp.message(Deposit.waiting_for_receipt, F.photo)
async def deposit_receipt(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    amount = data["amount"]
    user_id = msg.from_user.id
    photo_id = msg.photo[-1].file_id

    # Admin tasdiqlashiga yuborish
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"app_pay_{user_id}_{amount}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"rej_pay_{user_id}")
        ]
    ])
    
    await bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo_id,
        caption=f"💸 <b>Yangi To'lov So'rovi!</b>\n\nFoydalanuvchi: ID {user_id}\nSumma: <b>{amount:,.0f} so'm</b>",
        parse_mode="HTML",
        reply_markup=kb
    )
    
    await state.clear()
    await msg.answer("⏳ Chek adminga yuborildi! Tasdiqlangach, balansingizga pul qo'shiladi.")

# --- BOT YARATISH ---
@dp.callback_query(F.data == "create_bot")
async def create_bot_start(call: types.CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if DB["users"][user_id]["balance"] < PRICE_INITIAL:
        await call.answer(f"❌ Balans yetarli emas! Bot yaratish: {PRICE_INITIAL:,.0f} so'm.", show_alert=True)
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 1. Kino Bot", callback_data="select_type_1")],
        [InlineKeyboardButton(text="🎁 2. Referal Bot", callback_data="select_type_2")],
        [InlineKeyboardButton(text="💬 3. Anonim Chat Bot", callback_data="select_type_3")]
    ])
    await call.message.answer("🤖 Qaysi turdagi botni yaratmoqchisiz?", reply_markup=kb)

@dp.callback_query(F.data.startswith("select_type_"))
async def select_bot_type(call: types.CallbackQuery, state: FSMContext):
    b_type = int(call.data.split("_")[-1])
    await state.update_data(b_type=b_type)
    await state.set_state(BotCreation.waiting_for_token)
    await call.message.answer("🔑 BotFather'dan olingan <b>Bot Tokenini</b> yuboring:", parse_mode="HTML")

@dp.message(BotCreation.waiting_for_token)
async def receive_token(msg: types.Message, state: FSMContext):
    token = msg.text.strip()
    user_id = msg.from_user.id
    data = await state.get_data()
    b_type = data["b_type"]

    # Balansdan ayirish
    DB["users"][user_id]["balance"] -= PRICE_INITIAL
    expires = datetime.now() + timedelta(days=DURATION_DAYS)

    DB["bots"][token] = {
        "owner": user_id,
        "type": b_type,
        "expires": expires.strftime("%Y-%m-%d %H:%M")
    }

    # Yangi botni fonda ishga tushirish!
    await start_sub_bot(token, b_type)

    await state.clear()
    await msg.answer(
        f"✅ <b>Botingiz muvaffaqiyatli ishga tushdi!</b>\n\n"
        f"📅 Faoliyat muddati: <b>17 kun</b> ({expires.strftime('%Y-%m-%d')})\n"
        f"🤖 Botingizga kirib /start bosing!",
        parse_mode="HTML"
    )

# --- ADMIN TO'LOV TASDIQLASH ---
@dp.callback_query(F.data.startswith("app_pay_"))
async def approve_payment(call: types.CallbackQuery):
    parts = call.data.split("_")
    target_id, amount = int(parts[2]), float(parts[3])

    DB["users"][target_id]["balance"] += amount
    await call.message.edit_caption(caption=f"✅ To'lov tasdiqlandi! +{amount:,.0f} so'm qo'shildi.")
    await bot.send_message(chat_id=target_id, text=f"🎉 <b>To'lovingiz tasdiqlandi!</b>\nBalansingizga <b>{amount:,.0f} so'm</b> qo'shildi.", parse_mode="HTML")

@dp.callback_query(F.data.startswith("rej_pay_"))
async def reject_payment(call: types.CallbackQuery):
    target_id = int(call.data.split("_")[2])
    await call.message.edit_caption(caption="❌ To'lov rad etildi.")
    await bot.send_message(chat_id=target_id, text="❌ Yuborgan chekingiz rad etildi.")

# --- KINO KODLARI ADMIN PANEL ---
@dp.callback_query(F.data == "admin_panel")
async def admin_panel(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("❌ Faqat admin kirishi mumkin!", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 Kinoga Kod va Video Qo'shish", callback_data="add_movie")]
    ])
    await call.message.answer("⚙️ <b>Admin Panel:</b>", parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "add_movie")
async def add_movie_code(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddMovie.waiting_for_code)
    await call.message.answer("🎬 Kino kodi (Masalan: 30224030):")

@dp.message(AddMovie.waiting_for_code)
async def movie_code_received(msg: types.Message, state: FSMContext):
    await state.update_data(code=msg.text.strip())
    await state.set_state(AddMovie.waiting_for_file)
    await msg.answer("🎥 Endi kodingiz uchun Video faylini yuboring:")

@dp.message(AddMovie.waiting_for_file, F.video)
async def movie_file_received(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    code = data["code"]
    DB["movies"][code] = {"title": msg.caption or f"Kino {code}", "file_id": msg.video.file_id}
    await state.clear()
    await msg.answer(f"✅ Kino saqlandi! Kod: <b>{code}</b>", parse_mode="HTML")

# ==========================================
# 4. ISHGA TUSHIRISH
# ==========================================
async def main():
    logging.basicConfig(level=logging.INFO)
    print("Maker Bot va Sub-botlar Tizimi Ishga Tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
