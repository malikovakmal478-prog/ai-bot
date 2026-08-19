import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# ==========================================
# 1. PLATFORMA BAZASI VA SOZLAMALARI
# ==========================================
MAKER_BOT_TOKEN = "8708370464:AAH5B72gKwwPqVvSy1lUUxtJjkkGdMJfkjI"  # Asosiy Maker Bot Tokeni
ADMIN_ID = 7849637859                           # Bosh Admin Telegram ID

PRICE_INITIAL = 35000.0   # Bot yaratish narxi (so'm)
PRICE_RENEWAL = 11000.0   # Uzaytirish narxi
DURATION_DAYS = 17        # Boshlang'ich muddat

CARD_NUMBER = "5440 8103 1990 4917"
CARD_HOLDER = "g/n"

# Ma'lumotlar xotirasi (Production uchun JSON/SQLite ishlatish tavsiya etiladi)
DB = {
    "users": {},     # {user_id: {"balance": 0.0, "diamonds": 0, "ref_by": None}}
    "bots": {},      # {token: {"owner": id, "type": 1, "expires": datetime, "channels": [], "buttons": []}}
    "movies": {},    # {code: {"title": str, "file_id": str}}
    "sub_users": {}  # {token: {user_id: {"diamonds": 0, "rank": "Bronze", "spins": 3}}}
}

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

class AdminEditBot(StatesGroup):
    waiting_for_days = State()
    waiting_for_channel = State()

class SubBotEditButtons(StatesGroup):
    waiting_for_button_text = State()

# ==========================================
# 2. PRO REFERAL BOT & SUB-BOT ENGINE
# ==========================================
def get_pro_ref_keyboard(token: str):
    """3-rasmdagi 'Bepul Olov Uz' uslubidagi Reply menyu"""
    custom_btns = DB["bots"].get(token, {}).get("buttons", [])
    
    kb_list = [
        [KeyboardButton(text="🤖 Sun'iy Intellekt")],
        [KeyboardButton(text="💎 Almaz ishlash"), KeyboardButton(text="🤝 Sheriklar")],
        [KeyboardButton(text="🎰 Spin"), KeyboardButton(text="⚙️ Telefonga Nastroyka")],
        [KeyboardButton(text="📊 Profilim"), KeyboardButton(text="🏅 Mening darajam")],
        [KeyboardButton(text="🏆 Reyting"), KeyboardButton(text="🤝 Sherik Topish")],
        [KeyboardButton(text="🛒 O'yin Do'koni"), KeyboardButton(text="🎥 Youtuber Xizmatlari")],
        [KeyboardButton(text="📢 Reklama va yangiliklar")]
    ]
    
    # Foydalanuvchi qo'shgan maxsus tugmalar
    for btn_text in custom_btns:
        kb_list.append([KeyboardButton(text=btn_text)])
        
    return ReplyKeyboardMarkup(keyboard=kb_list, resize_keyboard=True)

async def start_sub_bot(token: str, bot_type: int):
    """Yaratilgan botni alohida va to'liq mantiq bilan fonda yurgizish"""
    try:
        sub_bot = Bot(token=token)
        sub_dp = Dispatcher()

        # --- SUB-BOT MAJBURiY OBUNA TEKSHIRUVI ---
        async def check_sub_channels(user_id: int) -> bool:
            channels = DB["bots"].get(token, {}).get("channels", [])
            for ch in channels:
                try:
                    member = await sub_bot.get_chat_member(chat_id=ch, user_id=user_id)
                    if member.status in ["left", "kicked"]:
                        return False
                except Exception:
                    pass
            return True

        # --- 3-RASMDAGI PRO REFERAL BOT MANTIQI (Type 2) ---
        if bot_type == 2:
            @sub_dp.message(Command("start"))
            async def ref_start(msg: types.Message, command: CommandObject = None):
                uid = msg.from_user.id
                if token not in DB["sub_users"]:
                    DB["sub_users"][token] = {}
                
                if uid not in DB["sub_users"][token]:
                    DB["sub_users"][token][uid] = {"diamonds": 0, "rank": "Silver", "spins": 5}

                if not await check_sub_channels(uid):
                    channels = DB["bots"][token]["channels"]
                    kb_lines = [[InlineKeyboardButton(text=f"Kanal {i+1}", url=f"https://t.me/{ch.replace('@','')}")] for i, ch in enumerate(channels)]
                    kb_lines.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")])
                    await msg.answer("⚠️ Botdan foydalanish uchun kanallarga obuna bo'ling:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_lines))
                    return

                await msg.answer(f"✨ **Xush kelibsiz, {msg.from_user.first_name}!**\n\nQuyidagi menyudan keragini tanlang 👇", parse_mode="Markdown", reply_markup=get_pro_ref_keyboard(token))

            @sub_dp.message(F.text == "💎 Almaz ishlash")
            async def get_ref_link(msg: types.Message):
                me = await sub_bot.get_me()
                link = f"https://t.me/{me.username}?start={msg.from_user.id}"
                await msg.answer(f"🔗 **Sizning referal havolangiz:**\n`{link}`\n\nHar bir taklif uchun 5 Almaz beriladi!", parse_mode="Markdown")

            @sub_dp.message(F.text == "📊 Profilim")
            async def get_profile(msg: types.Message):
                u = DB["sub_users"][token].get(msg.from_user.id, {"diamonds": 0, "rank": "Silver", "spins": 0})
                await msg.answer(f"👤 **Profilingiz:**\n\n💎 Almazlar: {u['diamonds']} ta\n🏅 Daraja: {u['rank']}\n🎰 Spinlar: {u['spins']} ta")

            @sub_dp.message(F.text == "🎰 Spin")
            async def spin_game(msg: types.Message):
                await msg.answer("🎰 Spin aylantirildi! 🎉 Siz 2 ta Almaz yutib oldingiz!")

            @sub_dp.message(Command("admin"))
            async def sub_admin_panel(msg: types.Message):
                owner_id = DB["bots"][token]["owner"]
                if msg.from_user.id != owner_id:
                    return
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Tugma qo'shish", callback_data="add_btn"), InlineKeyboardButton(text="🗑 Tugma o'chirish", callback_data="del_btn")],
                    [InlineKeyboardButton(text="📢 Majburiy Obuna Kanal Qo'shish", callback_data="add_chan")]
                ])
                await msg.answer("⚙️ **Botingiz Admin Paneli:**", parse_mode="Markdown", reply_markup=kb)

            @sub_dp.callback_query(F.data == "add_btn")
            async def sub_add_btn(call: types.CallbackQuery, state: FSMContext):
                await state.set_state(SubBotEditButtons.waiting_for_button_text)
                await call.message.answer("📝 Yangi tugma nomini kiriting:")

            @sub_dp.message(SubBotEditButtons.waiting_for_button_text)
            async def sub_save_btn(msg: types.Message, state: FSMContext):
                DB["bots"][token]["buttons"].append(msg.text.strip())
                await state.clear()
                await msg.answer("✅ Tugma menyuga qo'shildi! /start bosing.")

        # --- QOLGAN BOTLAR UCHUN UNiVERSAL ENGINE ---
        else:
            @sub_dp.message(Command("start"))
            async def gen_start(msg: types.Message):
                await msg.answer(f"🤖 **Professional Bot №{bot_type} ishchi holatda!**")

        RUNNING_BOTS[token] = sub_bot
        asyncio.create_task(sub_dp.start_polling(sub_bot))
    except Exception as e:
        logging.error(f"Sub-bot xatosi ({token}): {e}")

# ==========================================
# 3. MAKER BOT - ASOSIY PANEL VA KATALOG
# ==========================================
@dp.message(Command("start"))
async def cmd_start(msg: types.Message, command: CommandObject = None):
    uid = msg.from_user.id
    if uid not in DB["users"]:
        DB["users"][uid] = {"balance": 0.0, "diamonds": 0, "ref_by": None}

    bal = DB["users"][uid]["balance"]
    text = (
        "<b>🌍 DUNYODA YAGONA — PROFESSIONAL MAKER BOT</b>\n\n"
        f"💳 Balansingiz: <b>{bal:,.0f} so'm</b>\n"
        "• Yangi bot yaratish: <b>35,000 so'm</b> (17 kun)\n"
        "• Uzaytirish: <b>11,000 so'm</b>\n\n"
        "Kerakli bo'limni tanlang:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Yangi Bot Yaratish (30 ta Pro Bot)", callback_data="create_bot")],
        [InlineKeyboardButton(text="💳 Balans To'ldirish", callback_data="deposit"), InlineKeyboardButton(text="👑 Bosh Admin Panel", callback_data="main_admin")]
    ])
    await msg.answer(text, parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "create_bot")
async def create_bot_catalog(call: types.CallbackQuery):
    # 30 ta Eng ommabop Pro Botlar Ro'yxati
    bot_types = [
        "1. 🎬 Kino Bot Pro", "2. 🎁 Referal / Olov Uz Bot", "3. 🛒 Shop / E-Commerce Bot",
        "4. 💬 Anonim Chat Bot", "5. 🧠 ChatGPT 4o AI Bot", "6. 📥 Universal Downloader",
        "7. 🛡 VPN Sotuv Bot", "8. 📝 Test Builder Bot", "9. 🎵 Shazam Music Bot",
        "10. 💱 Valyuta Kurslari", "11. 📩 Temp Mail Bot", "12. 📄 PDF Converter",
        "13. ✍️ Text Auto-Format", "14. 💼 Resume / Portfolio", "15. 📈 Crypto Signals",
        "16. 🔮 Horoscope Bot", "17. 📞 Murojaat / Feedback", "18. 🎮 Mini Game Center",
        "19. 🔗 URL Shortener", "20. ⚙️ Universal Constructor", "21. 📢 Auto Post Bot",
        "22. 💎 Diamond / Top-Up Bot", "23. 📣 SMS Mailer Bot", "24. 🏆 Tournament Bot",
        "25. 🏦 P2P Exchange Bot", "26. 🎟 Ticket Sales Bot", "27. 🏥 Clinic Booking Bot",
        "28. 🍕 Delivery Order Bot", "29. 🚗 Auto Rent Bot", "30. 🎓 Online Course Bot"
    ]
    
    kb_rows = []
    for i in range(0, 30, 2):
        kb_rows.append([
            InlineKeyboardButton(text=bot_types[i], callback_data=f"sel_type_{i+1}"),
            InlineKeyboardButton(text=bot_types[i+1], callback_data=f"sel_type_{i+2}")
        ])
    
    await call.message.edit_text("🔥 **Kerakli bot turini tanlang (30 ta Pro Bot):**", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))

@dp.callback_query(F.data.startswith("sel_type_"))
async def select_type_action(call: types.CallbackQuery, state: FSMContext):
    b_type = int(call.data.split("_")[-1])
    uid = call.from_user.id
    if DB["users"][uid]["balance"] < PRICE_INITIAL:
        await call.answer("❌ Balans yetarli emas! Avval balansingizni to'ldiring.", show_alert=True)
        return

    await state.update_data(b_type=b_type)
    await state.set_state(BotCreation.waiting_for_token)
    await call.message.answer("🔑 BotFather'dan olingan **Bot Tokenini** yuboring:", parse_mode="Markdown")

@dp.message(BotCreation.waiting_for_token)
async def process_token(msg: types.Message, state: FSMContext):
    token = msg.text.strip()
    uid = msg.from_user.id
    data = await state.get_data()
    b_type = data["b_type"]

    DB["users"][uid]["balance"] -= PRICE_INITIAL
    expires = datetime.now() + timedelta(days=DURATION_DAYS)

    DB["bots"][token] = {
        "owner": uid,
        "type": b_type,
        "expires": expires,
        "channels": [],
        "buttons": []
    }

    # Botni fonda ishga tushirish
    await start_sub_bot(token, b_type)
    await state.clear()
    await msg.answer(f"🎉 **Bot №{b_type} muvaffaqiyatli yaratildi va ishga tushdi!**\n\n📅 Amal qilish muddati: {expires.strftime('%Y-%m-%d')}\n🤖 Botingizga kirib /start bosing!")

# ==========================================
# 4. MAKER BOT BOSH ADMIN PANELI
# ==========================================
@dp.callback_query(F.data == "main_admin")
async def main_admin_panel(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("❌ Faqat Bosh Admin uchun!", show_alert=True)
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Odamlarning Botlari", callback_data="manage_user_bots")],
        [InlineKeyboardButton(text="➕ Balans Qo'shish / Ayirish", callback_data="edit_user_balance")]
    ])
    await call.message.edit_text("👑 **MAKER BOT BOSH ADMIN PANELI**\n\nBarcha tizimlarni boshqarish bo'limi:", parse_mode="Markdown", reply_markup=kb)

@dp.callback_query(F.data == "manage_user_bots")
async def show_all_user_bots(call: types.CallbackQuery):
    if not DB["bots"]:
        await call.answer("Hozircha hech kim bot yaratgani yo'q.", show_alert=True)
        return

    kb_rows = []
    for token, info in DB["bots"].items():
        owner_id = info["owner"]
        exp = info["expires"].strftime("%Y-%m-%d")
        btn_text = f"🤖 ID:{owner_id} | Type:{info['type']} | {exp}"
        kb_rows.append([InlineKeyboardButton(text=btn_text, callback_data=f"bot_manage_{token[:10]}")])

    await call.message.edit_text("👥 **Yaratilgan barcha botlar ro'yxati:**\nBoshqarish uchun botni tanlang:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))

# ==========================================
# 5. ISHGA TUSHIRISH
# ==========================================
async def main():
    logging.basicConfig(level=logging.INFO)
    print("Dunyoda yagona Maker Bot platformasi ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
