import base64
import logging
import requests
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = "8793117472:AAHVJmXwVUlb8LaM24J4Ap2Ugl4REd7ow_U"          # @BotFather'dan
OPENROUTER_API_KEY = "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"  # openrouter.ai/keys dan bepul olinadi
GROQ_API_KEY = "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"        # console.groq.com dan bepul olinadi (ovozli xabarlar uchun)

# Bepul modellar ro'yxati - birinchisi band bo'lsa, navbatdagisi sinaladi
FREE_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-3-12b-it:free",
    "openai/gpt-oss-120b:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
]

# Rasm tushunadigan (vision) bepul modellar
VISION_MODELS = [
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
]

SYSTEM_PROMPT = (
    "Sen do'stona, yordamberuvchi AI yordamchisan. O'zbek tilida, "
    "iliq va tabiiy suhbatlashasan. Javoblaring qisqa va tushunarli bo'lsin."
)

# Har bir foydalanuvchi uchun suhbat tarixi (oddiy, xotira bilan)
user_history = {}
MAX_HISTORY = 10  # necha xabar eslab qolinsin

import time

def ask_ai(chat_id, user_text):
    history = user_history.get(chat_id, [])
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history + [
        {"role": "user", "content": user_text}
    ]

    for model in FREE_MODELS:
        for attempt in range(2):  # har modelni 2 marta sinaymiz (rate-limit uchun)
            try:
                response = requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": messages,
                    },
                    timeout=30
                )
                data = response.json()

                if "error" in data:
                    err = data["error"]
                    logging.warning(f"OpenRouter xatosi ({model}): {err}")
                    if err.get("code") == 429:
                        wait = min(err.get("metadata", {}).get("retry_after_seconds", 6), 10)
                        time.sleep(wait)
                        continue
                    break  # 404 va boshqa xatolar - darhol keyingi modelga o'tamiz

                reply = data["choices"][0]["message"]["content"]

                history.append({"role": "user", "content": user_text})
                history.append({"role": "assistant", "content": reply})
                user_history[chat_id] = history[-MAX_HISTORY:]

                return reply
            except Exception as e:
                logging.warning(f"So'rov xatosi ({model}): {e}")
                break

    return "Kechirasiz, hozir barcha bepul modellar band. Bir necha soniyadan keyin qayta urinib ko'ring 🙏"


def ask_ai_about_image(image_bytes, caption):
    prompt_text = caption.strip() if caption else "Bu rasmda nima ko'rsatilgan? O'zbek tilida tushuntiring."
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_uri = f"data:image/jpeg;base64,{b64}"

    for model in VISION_MODELS:
        for attempt in range(2):
            try:
                response = requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt_text},
                                    {"type": "image_url", "image_url": {"url": data_uri}},
                                ],
                            },
                        ],
                    },
                    timeout=45
                )
                data = response.json()

                if "error" in data:
                    err = data["error"]
                    logging.warning(f"Vision xatosi ({model}): {err}")
                    if err.get("code") == 429:
                        wait = min(err.get("metadata", {}).get("retry_after_seconds", 6), 10)
                        time.sleep(wait)
                        continue
                    break

                return data["choices"][0]["message"]["content"]
            except Exception as e:
                logging.warning(f"Rasm so'rovida xato ({model}): {e}")
                break

    return "Kechirasiz, hozir rasmni tahlil qila olmadim. Birozdan keyin qayta urinib ko'ring 🙏"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salom! 👋 Men sizning AI yordamchingizman.\n\n"
        "Menga istalgan savolingizni yozing, rasm yoki 🎙 ovozli xabar yuboring — tushunib javob beraman.\n\n"
        "🎨 /rasm [tasvir] — rasm chizib beraman (masalan: /rasm kosmosdagi mushuk)\n"
        "/reset — suhbat tarixini tozalash"
    )

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_history.pop(chat_id, None)
    await update.message.reply_text("Suhbat tarixi tozalandi ✅")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    reply = ask_ai(chat_id, text)
    await update.message.reply_text(reply)

def generate_image(prompt: str):
    """Pollinations.ai orqali bepul, kalitsiz rasm generatsiya qiladi."""
    try:
        import urllib.parse
        encoded = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&nologo=true"
        response = requests.get(url, timeout=60)
        if response.status_code == 200 and response.headers.get("content-type", "").startswith("image"):
            return response.content
        return None
    except Exception as e:
        logging.warning(f"Rasm generatsiyasida xato: {e}")
        return None


def transcribe_voice(audio_bytes):
    """Groq Whisper orqali ovozni matnga o'giradi (bepul)."""
    try:
        response = requests.post(
            url="https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            files={"file": ("audio.ogg", audio_bytes, "audio/ogg")},
            data={"model": "whisper-large-v3-turbo", "language": "uz"},
            timeout=40
        )
        data = response.json()
        if "text" in data:
            return data["text"]
        logging.warning(f"Whisper xatosi: {data}")
        return None
    except Exception as e:
        logging.warning(f"Ovozni tanishda xato: {e}")
        return None


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    photo = update.message.photo[-1]  # eng katta o'lchamdagi versiya
    file = await context.bot.get_file(photo.file_id)
    image_bytes = await file.download_as_bytearray()

    caption = update.message.caption or ""
    reply = ask_ai_about_image(bytes(image_bytes), caption)
    await update.message.reply_text(reply)


async def rasm_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Nima rasm chizishimni yozing.\nMasalan: /rasm qor bosgan tog' manzarasi"
        )
        return

    prompt = " ".join(context.args)
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action="upload_photo")
    wait_msg = await update.message.reply_text("🎨 Rasm chizilmoqda, biroz kuting...")

    image_bytes = generate_image(prompt)
    if not image_bytes:
        await wait_msg.edit_text("Kechirasiz, rasm chizib bo'lmadi. Qayta urinib ko'ring 🙏")
        return

    await wait_msg.delete()
    await update.message.reply_photo(photo=image_bytes, caption=f"🎨 {prompt}")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    voice = update.message.voice or update.message.audio
    file = await context.bot.get_file(voice.file_id)
    audio_bytes = await file.download_as_bytearray()

    text = transcribe_voice(bytes(audio_bytes))
    if not text:
        await update.message.reply_text("Kechirasiz, ovozli xabarni tushunolmadim 😕 Matn bilan yozib ko'ring.")
        return

    reply = ask_ai(chat_id, text)
    await update.message.reply_text(f"🎙 Eshitdim: _{text}_\n\n{reply}", parse_mode="Markdown")


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("rasm", rasm_cmd))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("AI bot ishga tushdi...")
    app.run_polling()


# ---------------- RENDER "WEB SERVICE" UCHUN KICHIK SERVER ----------------
# Render'ning bepul tarifi faqat ochiq PORT'ni kutadigan "Web Service"larni
# qo'llab-quvvatlaydi. Shuning uchun botni fon oqimida ishga tushirib,
# asosiy oqimda kichik Flask serverini ochamiz.
def run_keepalive_server():
    import os
    from flask import Flask
    web = Flask(__name__)

    @web.route("/")
    def home():
        return "AI bot ishlayapti ✅"

    port = int(os.environ.get("PORT", 10000))
    web.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    import threading
    threading.Thread(target=main, daemon=True).start()
    run_keepalive_server()
