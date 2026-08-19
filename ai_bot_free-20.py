import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# ==========================================
# 1. PLATFORMA SOZLAMALARI VA BAZA
# ==========================================
MAKER_BOT_TOKEN = "8708370464:AAEQZdIAU2va3scvDgrly-mzgLl9LwdsC4E"  # Asosiy Maker Bot Tokeni
ADMIN_ID = 7849637859                           # Bosh Admin Telegram ID

PRICE_INITIAL = 35000.0   # Bot yaratish narxi (so'm)
PRICE_RENEWAL = 11000.0   # Uzaytirish narxi
DURATION_DAYS = 17        # Boshlang'ich muddat

CARD_NUMBER = "5440 8103 1990 4917"
CARD_HOLDER = "g/n"

DB = {
    "users": {},      # {user_id: {"balance": 0.0, "diamonds": 0, "ref_by": None}}
    "bots": {},       # {token: {"owner": id, "type": int, "expires": datetime, "channels": [], "custom_buttons": []}}
    "movies": {},     # {code: {"title": str, "file_id": str}}
    "sub_users": {}   # {token: {user_id: {"diamonds": 0, "rank": "Bronze", "spins": 3}}}
}

RUNNING_BOTS = {}

bot = Bot(token=MAKER_BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# FSM Holatlari
class BotCreation(StatesGroup):
    waiting_for_token = State()

class Deposit(StatesGroup):
    waiting_for_amount = State()
    waiting_for_receipt = State()

class MainAdminEdit(StatesGroup):
    waiting_for_days = State()

class SubBotAdmin(StatesGroup):
    waiting_for_btn_name = State()
    waiting_for_btn_reply = State()
    waiting_for_channel = State()
    waiting_for_movie_code = State()
    waiting_for_movie_file = State()

# ==========================================
# 2. SUB-BOT ENGINE (Fonda barcha botlarni yurgizish)
# ==========================================
def build_pro_keyboard(token: str):
    """3-rasmdagi 'Bepul Olov Uz' uslubidagi dinamik tugmalar"""
    custom_btns = DB["bots"].get(token, {}).get("custom_buttons", [])
    
    kb = [
        [KeyboardButton(text="🤖 Sun'iy Intellekt")],
        [KeyboardButton(text="💎 Almaz ishlash"), KeyboardButton(text="🤝 Sheriklar")],
        [KeyboardButton(text="🎰 Spin"), KeyboardButton(text="⚙️ Telefonga Nastroyka")],
        [KeyboardButton(text="📊 Profilim"), KeyboardButton(text="🏅 Mening darajam")],
        [KeyboardButton(text="🏆 Reyting"), KeyboardButton(text="🤝 Sherik Topish")],
        [KeyboardButton(text="🛒 O'yin Do'koni"), KeyboardButton(text="🎥 Youtuber Xizmatlari")],
        [KeyboardButton(text="📢 Reklama va yangiliklar")]
    ]
    for btn in custom_btns:
        kb.append([KeyboardButton(text=btn["name"])])
        
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

async def check_sub_channels(sub_bot: Bot, token: str, user_id: int) -> bool:
    channels = DB["bots"].get(token, {}).get("channels", [])
    for ch in channels:
        try:
            member = await sub_bot.get_chat_member(chat_id=ch, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            pass
    return True

async def start_sub_bot(token: str, bot_type: int):
    try:
        sub_bot = Bot(token=token)
        sub_dp = Dispatcher(storage=MemoryStorage())

        # --- MIDDLEWARE / CHECK SUBSCRIBERS ---
        @sub_dp.message(Command("start"))
        async def sub_start(msg: types.Message, command: CommandObject = None):
            uid = msg.from_user.id
            if token not in DB["sub_users"]:
                DB["sub_users"][token] = {}
            if uid not in DB["sub_users"][token]:
                DB["sub_users"][token][uid] = {"diamonds": 0, "rank": "Silver", "spins": 5}

            # Majburiy obunani tekshirish
            if not await check_sub_channels(sub_bot, token, uid):
                channels = DB["bots"][token]["channels"]
                kb_lines = [[InlineKeyboardButton(text=f"📢 Kanal {i+1}", url=f"https://t.me/{ch.replace('@','')}") ] for i, ch in enumerate(channels)]
                kb_lines.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub_status")])
                await msg.answer("⚠️ **Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:**", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_lines), parse_mode="Markdown")
                return

            if bot_type == 2: # Pro Referal Bot
                await msg.answer(f"✨ **Xush kelibsiz, {msg.from_user.first_name}!**\nBosh menyudan kerakli bo'limni tanlang 👇", reply_markup=build_pro_keyboard(token), parse_mode="Markdown")
            else:
                await msg.answer(f"🤖 **Bot №{bot_type} faol holatda!**\nBuyruqlardan foydalanishingiz mumkin.", reply_markup=build_pro_keyboard(token))

        @sub_dp.callback_query(F.data == "check_sub_status")
        async def check_sub_cb(call: types.CallbackQuery):
            if await check_sub_channels(sub_bot, token, call.from_user.id):
                await call.message.delete()
                await call.message.answer("✅ Rahmat! Obuna tasdiqlandi. /start bosing.")
            else:
                await call.answer("❌ Hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)

        # --- PRO REFERAL BOT TUGMALARI ---
        @sub_dp.message(F.text == "💎 Almaz ishlash")
        async def ref_link(msg: types.Message):
            me = await sub_bot.get_me()
            await msg.answer(f"🔗 **Sizning referal havolangiz:**\n`https://t.me/{me.username}?start={msg.from_user.id}`\n\nDo'stlaringizni taklif qiling va 5 Almaz oling!", parse_mode="Markdown")

        @sub_dp.message(F.text == "📊 Profilim")
        async def profile(msg: types.Message):
            u = DB["sub_users"][token].get(msg.from_user.id, {"diamonds": 0, "rank": "Silver", "spins": 0})
            await msg.answer(f"👤 **Profilingiz:**\n\n💎 Almazlar: **{u['diamonds']} ta**\n🏅 Darajangiz: **{u['rank']}**\n🎰 Spinlar: **{u['spins']} ta**", parse_mode="Markdown")

        @sub_dp.message(F.text == "🎰 Spin")
        async def spin(msg: types.Message):
            await msg.answer("🎰 Spin aylantirildi! 🎉 Siz **3 ta Almaz** yutib oldingiz!", parse_mode="Markdown")

        # --- SUB-BOT ADMIN PANEL (Bot egasi uchun) ---
        @sub_dp.message(Command("admin"))
        async def sub_admin_panel(msg: types.Message):
            owner_id = DB["bots"][token]["owner"]
            if msg.from_user.id != owner_id and msg.from_user.id != ADMIN_ID:
                return
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Tugma qo'shish", callback_data="add_custom_btn"), InlineKeyboardButton(text="🗑 Tugmalarni o'chirish", callback_data="clear_custom_btns")],
                [InlineKeyboardButton(text="📢 Majburiy obuna kanal qo'shish", callback_data="add_sub_channel")]
            ])
            await msg.answer("⚙️ **SUB-BOT ADMIN PANELI**\nO'z botingizni sozlang:", reply_markup=kb, parse_mode="Markdown")

        @sub_dp.callback_query(F.data == "add_custom_btn")
        async def add_btn_start(call: types.CallbackQuery, state: FSMContext):
            await state.set_state(SubBotAdmin.waiting_for_btn_name)
            await call.message.answer("📝 Tugma nomini kiriting:")

        @sub_dp.message(SubBotAdmin.waiting_for_btn_name)
        async def add_btn_name(msg: types.Message, state: FSMContext):
            await state.update_data(btn_name=msg.text.strip())
            await state.set_state(SubBotAdmin.waiting_for_btn_reply)
            await msg.answer("💬 Usbu tugma bosilganda bot qanday javob qaytarsin?")

        @sub_dp.message(SubBotAdmin.waiting_for_btn_reply)
        async def add_btn_reply(msg: types.Message, state: FSMContext):
            data = await state.get_data()
            DB["bots"][token]["custom_buttons"].append({"name": data["btn_name"], "reply": msg.text.strip()})
            await state.clear()
            await msg.answer("✅ **Tugma muvaffaqiyatli qo'shildi!** /start bosing.", parse_mode="Markdown")

        @sub_dp.callback_query(F.data == "clear_custom_btns")
        async def clear_btns(call: types.CallbackQuery):
            DB["bots"][token]["custom_buttons"] = []
            await call.answer("🗑 Qo'shilgan barcha maxsus tugmalar o'chirildi!", show_alert=True)

        @sub_dp.callback_query(F.data == "add_sub_channel")
        async def add_chan_start(call: types.CallbackQuery, state: FSMContext):
            await state.set_state(SubBotAdmin.waiting_for_channel)
            await call.message.answer("📢 Kanal username'ini yuboring (Masalan: `@kanalim`):")

        @sub_dp.message(SubBotAdmin.waiting_for_channel)
        async def add_chan_save(msg: types.Message, state: FSMContext):
            ch = msg.text.strip()
            if not ch.startswith("@"):
                ch = "@" + ch
            DB["bots"][token]["channels"].append(ch)
            await state.clear()
            await msg.answer(f"✅ Kanal qo'shildi: **{ch}**\n*(Eslatib o'tamiz, botingiz ushbu kanalda admin bo'lishi shart!)*", parse_mode="Markdown")

        # Dynamic Button Handler
        @sub_dp.message(F.text)
        async def handle_custom_buttons(msg: types.Message):
            btns = DB["bots"][token].get("custom_buttons", [])
            for b in btns:
                if b["name"] == msg.text:
                    await msg.answer(b["reply"])
                    return

        RUNNING_BOTS[token] = sub_bot
        asyncio.create_task(sub_dp.start_polling(sub_bot))
    except Exception as e:
        logging.error(f"Sub-bot start error: {e}")

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
        "<b>🌍 DUNYODA YAGONA — MAKER BOT PLATFORMASI</b>\n\n"
        f"💳 Balansingiz: <b>{bal:,.0f} so'm</b>\n"
        f"🤖 Yaratilgan botlar: <b>{len(DB['bots'])} ta</b>\n\n"
        "• Yangi bot yaratish: <b>35,000 so'm</b> (17 kun)\n"
        "• Uzaytirish: <b>11,000 so'm</b> / 17 kun\n\n"
        "Kerakli bo'limni tanlang:"
    )

    kb_list = [
        [InlineKeyboardButton(text="🤖 Yangi Bot Yaratish (30 ta Bot)", callback_data="catalog")],
        [InlineKeyboardButton(text="💳 Balans To'ldirish", callback_data="deposit")],
        [InlineKeyboardButton(text="👑 Bosh Admin Panel", callback_data="main_admin")]
    ]
    await msg.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_list))

@dp.callback_query(F.data == "catalog")
async def show_30_bots(call: types.CallbackQuery):
    bot_list = [
        "1. 🎬 Kino Bot Pro", "2. 🎁 Referal / Olov Uz Bot", "3. 🛒 Shop / Do'kon Bot",
        "4. 💬 Anonim Chat Bot", "5. 🧠 ChatGPT AI Bot", "6. 📥 Universal Downloader",
        "7. 🛡 VPN Sotuv Bot", "8. 📝 Test Builder Bot", "9. 🎵 Music Finder Bot",
        "10. 💱 Valyuta Kurslari", "11. 📩 Temp Mail Bot", "12. 📄 PDF Converter",
        "13. ✍️ Auto Format Bot", "14. 💼 Portfolio Bot", "15. 📈 Crypto Signals",
        "16. 🔮 Horoscope Bot", "17. 📞 Feedback Bot", "18. 🎮 Mini Game Bot",
        "19. 🔗 URL Shortener", "20. ⚙️ Universal Builder", "21. 📢 Auto Post Bot",
        "22. 💎 Top-Up Store Bot", "23. 📣 SMS Mailer Bot", "24. 🏆 Tournament Bot",
        "25. 🏦 P2P Exchange Bot", "26. 🎟 Ticket Sales Bot", "27. 🏥 Booking Bot",
        "28. 🍕 Delivery Order Bot", "29. 🚗 Auto Rent Bot", "30. 🎓 Online Course Bot"
    ]
    
    rows = []
    for i in range(0, 30, 2):
        rows.append([
            InlineKeyboardButton(text=bot_list[i], callback_data=f"create_{i+1}"),
            InlineKeyboardButton(text=bot_list[i+1], callback_data=f"create_{i+2}")
        ])
    
    await call.message.edit_text("🔥 **30 ta Pro Bot katalogidan birini tanlang:**", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@dp.callback_query(F.data.startswith("create_"))
async def select_bot_to_create(call: types.CallbackQuery, state: FSMContext):
    b_type = int(call.data.split("_")[1])
    uid = call.from_user.id

    if DB["users"][uid]["balance"] < PRICE_INITIAL:
        await call.answer(f"❌ Balans yetarli emas! Kamida {PRICE_INITIAL:,.0f} so'm kerak.", show_alert=True)
        return

    await state.update_data(b_type=b_type)
    await state.set_state(BotCreation.waiting_for_token)
    await call.message.answer("🔑 BotFather'dan olingan **Bot Tokenini** yuboring:", parse_mode="Markdown")

@dp.message(BotCreation.waiting_for_token)
async def process_create_token(msg: types.Message, state: FSMContext):
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
        "custom_buttons": []
    }

    # Botni fonda ishga tushirish
    await start_sub_bot(token, b_type)
    await state.clear()
    await msg.answer(f"✅ **Bot №{b_type} muvaffaqiyatli yaratildi va ishga tushdi!**\n\n📅 Amal qilish muddati: **17 kun** ({expires.strftime('%Y-%m-%d')})\n🤖 Botingizga kirib /start bosing hamda /admin orqali boshqaring!", parse_mode="Markdown")

# ==========================================
# 4. KARTA ORQALI BALANS TO'LDIRISH
# ==========================================
@dp.callback_query(F.data == "deposit")
async def dep_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(Deposit.waiting_for_amount)
    await call.message.answer("💳 Qancha summa (so'mda) to'lamoqchisiz? (Masalan: 35000):")

@dp.message(Deposit.waiting_for_amount)
async def dep_amount(msg: types.Message, state: FSMContext):
    if not msg.text.isdigit():
        await msg.answer("❌ Faqat raqamlarda kiriting!")
        return
    await state.update_data(amount=int(msg.text))
    await state.set_state(Deposit.waiting_for_receipt)
    
    text = (
        f"💳 **To'lov Rekvizitlari:**\n\n"
        f"Karta: `{CARD_NUMBER}`\n"
        f"Egasining ismi: **{CARD_HOLDER}**\n\n"
        "To'lovni amalga oshirgach, **chek rasmini (screenshot)** ushbu chatga yuboring:"
    )
    await msg.answer(text, parse_mode="Markdown")

@dp.message(Deposit.waiting_for_receipt, F.photo)
async def dep_receipt(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    amount = data["amount"]
    uid = msg.from_user.id

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"app_{uid}_{amount}"),
         InlineKeyboardButton(text="❌ Rad etish", callback_data=f"rej_{uid}")]
    ])
    await bot.send_photo(chat_id=ADMIN_ID, photo=msg.photo[-1].file_id, caption=f"💸 **To'lov so'rovi!**\nID: `{uid}`\nSumma: **{amount:,.0f} so'm**", parse_mode="Markdown", reply_markup=kb)
    await state.clear()
    await msg.answer("⏳ Chek adminga yuborildi! Tasdiqlangach, balansingiz to'ldiriladi.")

@dp.callback_query(F.data.startswith("app_"))
async def dep_approve(call: types.CallbackQuery):
    _, uid, amount = call.data.split("_")
    uid, amount = int(uid), float(amount)
    DB["users"][uid]["balance"] += amount
    await call.message.edit_caption(caption=f"✅ **To'lov tasdiqlandi! (+{amount:,.0f} so'm)**", parse_mode="Markdown")
    await bot.send_message(chat_id=uid, text=f"🎉 **To'lovingiz tasdiqlandi!** Balansingizga +{amount:,.0f} so'm qo'shildi.", parse_mode="Markdown")

@dp.callback_query(F.data.startswith("rej_"))
async def dep_reject(call: types.CallbackQuery):
    uid = int(call.data.split("_")[1])
    await call.message.edit_caption(caption="❌ **To'lov rad etildi.**", parse_mode="Markdown")
    await bot.send_message(chat_id=uid, text="❌ Yuborgan chekingiz rad etildi.")

# ==========================================
# 5. MAKER BOT BOSH ADMIN PANELI (Barcha Botlarni Boshqarish)
# ==========================================
@dp.callback_query(F.data == "main_admin")
async def main_admin_menu(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("❌ Siz Bosh Admin emassiz!", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Odamlarning Botlari Ro'yxati", callback_data="admin_bot_list")]
    ])
    await call.message.edit_text("👑 **MAKER BOT BOSH ADMIN PANELI**", parse_mode="Markdown", reply_markup=kb)

@dp.callback_query(F.data == "admin_bot_list")
async def admin_bot_list(call: types.CallbackQuery):
    if not DB["bots"]:
        await call.answer("Ayni vaqtda hech qanday bot yaratilmagan.", show_alert=True)
        return

    rows = []
    for token, bdata in DB["bots"].items():
        exp = bdata["expires"].strftime("%Y-%m-%d")
        t_short = token[:10] + "..."
        btn_text = f"🤖 Owner: {bdata['owner']} | {exp}"
        rows.append([InlineKeyboardButton(text=btn_text, callback_data=f"manage_bot_{token[:12]}")])

    await call.message.edit_text("👥 **Yaratilgan Barcha Botlar Ro'yxati:**", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

# ==========================================
# 6. ISHGA TUSHIRISH
# ==========================================
async def main():
    logging.basicConfig(level=logging.INFO)
    print("Dunyoda yagona Maker Bot ishga tushmoqda...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
