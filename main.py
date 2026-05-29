import os
import asyncio
import time
import logging
from datetime import datetime
from typing import Optional

import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, 
    CallbackQuery, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    FSInputFile,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from aiogram.filters import Command
from aiogram.enums import ParseMode
from yt_dlp import YoutubeDL

# ==================== LOGGING ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== ENVIRONMENT VARIABLES ====================
from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "")

if not TOKEN:
    raise ValueError("❌ TELEGRAM_BOT_TOKEN topilmadi! .env faylga qo'shing.")
if not REQUIRED_CHANNEL:
    raise ValueError("❌ REQUIRED_CHANNEL topilmadi! .env faylga qo'shing.")

# ==================== INIT ====================
bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Rate limit
user_last_request = {}
user_warnings = {}

# ==================== DATABASE ====================
async def init_db():
    """Bazani ishga tushirish"""
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                ref INTEGER,
                balance INTEGER DEFAULT 0,
                joined_at TEXT,
                is_banned INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS downloads(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                url TEXT,
                downloaded_at TEXT,
                status TEXT
            )
        """)
        await db.commit()
        logger.info("✅ Baza ishga tushdi")

async def add_user(user_id: int, username: str, first_name: str, ref: Optional[int] = None):
    """Foydalanuvchi qo'shish"""
    async with aiosqlite.connect("bot.db") as db:
        cur = await db.execute("SELECT id FROM users WHERE id=?", (user_id,))
        if not await cur.fetchone():
            await db.execute(
                "INSERT INTO users(id, username, first_name, ref, joined_at) VALUES(?,?,?,?,?)",
                (user_id, username, first_name, ref, datetime.now().isoformat())
            )
            await db.commit()
            logger.info(f"👤 Yangi foydalanuvchi: {user_id}")

async def get_user(user_id: int):
    """Foydalanuvchi ma'lumotlari"""
    async with aiosqlite.connect("bot.db") as db:
        cur = await db.execute("SELECT * FROM users WHERE id=?", (user_id,))
        return await cur.fetchone()

async def ban_user(user_id: int):
    """Foydalanuvchini bloklash"""
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("UPDATE users SET is_banned=1 WHERE id=?", (user_id,))
        await db.commit()

async def unban_user(user_id: int):
    """Blokni olish"""
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("UPDATE users SET is_banned=0 WHERE id=?", (user_id,))
        await db.commit()

async def count_users():
    """Jami foydalanuvchilar"""
    async with aiosqlite.connect("bot.db") as db:
        cur = await db.execute("SELECT COUNT(*) FROM users")
        return (await cur.fetchone())[0]

async def count_banned():
    """Bloklangan foydalanuvchilar"""
    async with aiosqlite.connect("bot.db") as db:
        cur = await db.execute("SELECT COUNT(*) FROM users WHERE is_banned=1")
        return (await cur.fetchone())[0]

async def add_download_log(user_id: int, url: str, status: str):
    """Yuklash logi"""
    async with aiosqlite.connect("bot.db") as db:
        await db.execute(
            "INSERT INTO downloads(user_id, url, downloaded_at, status) VALUES(?,?,?,?)",
            (user_id, url, datetime.now().isoformat(), status)
        )
        await db.commit()

# ==================== CHANNEL CHECK ====================
async def is_user_subscribed(user_id: int) -> bool:
    """Foydalanuvchi kanalga a'zo mi?"""
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.error(f"Kanal tekshirish xatosi: {e}")
        return False

def get_subscription_keyboard() -> InlineKeyboardMarkup:
    """A'zo boʻlish tugmalari"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📢 Kanalga a'zo boʻlish", url=f"https://t.me/{REQUIRED_CHANNEL.replace('@', '')}")
        ],
        [
            InlineKeyboardButton(text="✅ A'zo boʻldim", callback_data="check_subscription")
        ]
    ])

# ==================== MAIN MENU ====================
def get_main_menu() -> ReplyKeyboardMarkup:
    """Asosiy menyu tugmalari"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📥 Video yuklash")],
            [KeyboardButton(text="📊 Mening hisobim"), KeyboardButton(text="👥 Referral")],
            [KeyboardButton(text="❓ Yordam"), KeyboardButton(text="📞 Admin bilan aloqa")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Menyudan tanlang..."
    )

def get_admin_menu() -> ReplyKeyboardMarkup:
    """Admin menyu tugmalari"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Statistika")],
            [KeyboardButton(text="📢 Xabar yuborish"), KeyboardButton(text="🚫 Bloklash")],
            [KeyboardButton(text="✅ Blokdan ochish"), KeyboardButton(text="📋 Foydalanuvchilar ro'yxati")],
            [KeyboardButton(text="🔙 Asosiy menyu")]
        ],
        resize_keyboard=True
    )

# ==================== DOWNLOAD ====================
def download_video(url: str) -> str:
    """Video yuklash"""
    ydl_opts = {
        "outtmpl": f"{DOWNLOAD_DIR}/%(title).50s.%(ext)s",
        "format": "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "merge_output_format": "mp4",
        "quiet": True,
        "noplaylist": True,
        "cookiefile": None,
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        file_path = ydl.prepare_filename(info)
        
        if not file_path.endswith(".mp4"):
            file_path = file_path.rsplit(".", 1)[0] + ".mp4"
            
        return file_path

# ==================== HANDLERS ====================
@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Start komandasi"""
    user_id = message.from_user.id
    username = message.from_user.username or "Noma'lum"
    first_name = message.from_user.first_name or "Foydalanuvchi"
    
    # Referral
    ref = None
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("ref"):
        try:
            ref = int(args[1].replace("ref", ""))
        except:
            pass
    
    # Baza ga qo'shish
    await add_user(user_id, username, first_name, ref)
    
    # Blok tekshirish
    user = await get_user(user_id)
    if user and user[6] == 1:  # is_banned
        await message.answer("🚫 Siz botdan bloklangansiz.")
        return
    
    # Kanal tekshirish
    if not await is_user_subscribed(user_id):
        await message.answer(
            f"👋 <b>Assalomu alaykum, {first_name}!</b>\n\n"
            f"📢 Botdan foydalanish uchun kanalimizga a'zo boʻling:\n"
            f"{REQUIRED_CHANNEL}\n\n"
            f"✅ A'zo boʻlgach, \"A'zo boʻldim\" tugmasini bosing.",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    # Asosiy menyu
    await message.answer(
        f"🎬 <b>Clipzy Bot</b> ga xush kelibsiz!\n\n"
        f"📥 Video yuklash uchun link yuboring\n"
        f"👥 Do'stlaringizni taklif qiling va bonus oling\n\n"
        f"Quyidagi tugmalardan foydalaning 👇",
        reply_markup=get_main_menu()
    )

@dp.callback_query(F.data == "check_subscription")
async def check_subscription(callback: CallbackQuery):
    """A'zolik tekshirish"""
    user_id = callback.from_user.id
    
    if await is_user_subscribed(user_id):
        await callback.message.delete()
        await callback.message.answer(
            "✅ A'zolik tasdiqlandi!\n\n"
            "🎬 <b>Clipzy Bot</b> ga xush kelibsiz!\n"
            "📥 Video yuklash uchun link yuboring",
            reply_markup=get_main_menu()
        )
    else:
        await callback.answer("❌ Hali kanalga a'zo emassiz!", show_alert=True)

@dp.message(F.text == "📥 Video yuklash")
async def btn_download(message: Message):
    """Video yuklash tugmasi"""
    await message.answer(
        "📎 Video linkini yuboring:\n\n"
        "Qo'llab-quvvatlanadi:\n"
        "• YouTube\n"
        "• TikTok\n"
        "• Instagram\n"
        "• Facebook\n"
        "• Va boshqalar..."
    )

@dp.message(F.text == "📊 Mening hisobim")
async def btn_account(message: Message):
    """Mening hisobim"""
    user = await get_user(message.from_user.id)
    if user:
        await message.answer(
            f"📊 <b>Mening hisobim</b>\n\n"
            f"👤 ID: <code>{message.from_user.id}</code>\n"
            f"💰 Balans: {user[4]} so'm\n"
            f"📅 Qo'shilgan: {user[5][:10]}\n\n"
            f"👥 Taklif qilganlar: {user[3] or 0}"
        )

@dp.message(F.text == "👥 Referral")
async def btn_referral(message: Message):
    """Referral"""
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=ref{message.from_user.id}"
    await message.answer(
        f"👥 <b>Referral dasturi</b>\n\n"
        f"Do'stlaringizni taklif qiling va har bir taklif uchun bonus oling!\n\n"
        f"Sizning referral linkingiz:\n"
        f"<code>{link}</code>\n\n"
        f"Ulashish tugmasi 👇",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Ulashish", url=f"https://t.me/share/url?url={link}&text=🎬%20Eng%20zo'r%20video%20yuklovchi%20bot!")]
        ])
    )

@dp.message(F.text == "❓ Yordam")
async def btn_help(message: Message):
    """Yordam"""
    await message.answer(
        "❓ <b>Yordam markazi</b>\n\n"
        "📥 <b>Video yuklash:</b>\n"
        "Link yuboring — bot avtomatik yuklab beradi\n\n"
        "🔗 <b>Qo'llab-quvvatlanadi:</b>\n"
        "YouTube, TikTok, Instagram, Facebook, Twitter\n\n"
        "⏱ <b>Limit:</b>\n"
        "Har 3 soniyada 1 ta so'rov\n\n"
        "👥 <b>Referral:</b>\n"
        "Do'stlaringizni taklif qiling\n\n"
        "📞 Muammo bo'lsa admin bilan bog'laning"
    )

@dp.message(F.text == "📞 Admin bilan aloqa")
async def btn_contact(message: Message):
    """Admin bilan aloqa"""
    await message.answer(
        "📞 <b>Admin bilan aloqa</b>\n\n"
        "Muammo yoki takliflar uchun admin bilan bog'laning:\n"
        f"👤 Admin ID: <code>{ADMIN_ID}</code>\n\n"
        f"Yoki shu yerda xabar qoldiring, admin ko'rib chiqadi."
    )

@dp.message(F.text == "📊 Statistika")
async def admin_stats(message: Message):
    """Admin statistika"""
    if message.from_user.id != ADMIN_ID:
        return
    
    users = await count_users()
    banned = await count_banned()
    
    await message.answer(
        f"📊 <b>ADMIN STATISTIKA</b>\n\n"
        f"👥 Jami foydalanuvchilar: {users}\n"
        f"🚫 Bloklangan: {banned}\n"
        f"✅ Faol: {users - banned}\n"
        f"📅 Sana: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"⚡ Bot status: <b>ACTIVE</b>"
    )

@dp.message(F.text == "📢 Xabar yuborish")
async def admin_broadcast(message: Message):
    """Xabar yuborish (admin)"""
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(
        "📢 <b>Xabar yuborish</b>\n\n"
        "Barcha foydalanuvchilarga xabar yuborish uchun:\n"
        "/broadcast [xabar]\n\n"
        "Misol: /broadcast 🎉 Yangi yangilik!"
    )

@dp.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    """Broadcast"""
    if message.from_user.id != ADMIN_ID:
        return
    
    text = message.text.replace("/broadcast", "").strip()
    if not text:
        await message.answer("❌ Xabar matnini kiriting!")
        return
    
    async with aiosqlite.connect("bot.db") as db:
        cur = await db.execute("SELECT id FROM users WHERE is_banned=0")
        users = await cur.fetchall()
    
    sent = 0
    failed = 0
    
    for user in users:
        try:
            await bot.send_message(user[0], f"📢 <b>Xabar:</b>\n\n{text}")
            sent += 1
        except:
            failed += 1
    
    await message.answer(f"✅ Yuborildi: {sent}\n❌ Xatolik: {failed}")

@dp.message(F.text == "🚫 Bloklash")
async def admin_ban(message: Message):
    """Bloklash"""
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(
        "🚫 <b>Foydalanuvchini bloklash</b>\n\n"
        "Format: /ban [user_id]\n"
        "Misol: /ban 123456789"
    )

@dp.message(Command("ban"))
async def cmd_ban(message: Message):
    """Ban komandasi"""
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        user_id = int(message.text.split()[1])
        await ban_user(user_id)
        await message.answer(f"🚫 Foydalanuvchi {user_id} bloklandi!")
    except:
        await message.answer("❌ Format: /ban [user_id]")

@dp.message(F.text == "✅ Blokdan ochish")
async def admin_unban(message: Message):
    """Blokdan ochish"""
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(
        "✅ <b>Blokdan ochish</b>\n\n"
        "Format: /unban [user_id]\n"
        "Misol: /unban 123456789"
    )

@dp.message(Command("unban"))
async def cmd_unban(message: Message):
    """Unban komandasi"""
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        user_id = int(message.text.split()[1])
        await unban_user(user_id)
        await message.answer(f"✅ Foydalanuvchi {user_id} blokdan olindi!")
    except:
        await message.answer("❌ Format: /unban [user_id]")

@dp.message(F.text == "📋 Foydalanuvchilar ro'yxati")
async def admin_users(message: Message):
    """Foydalanuvchilar ro'yxati"""
    if message.from_user.id != ADMIN_ID:
        return
    
    async with aiosqlite.connect("bot.db") as db:
        cur = await db.execute("SELECT id, username, first_name, joined_at FROM users ORDER BY joined_at DESC LIMIT 20")
        users = await cur.fetchall()
    
    text = "📋 <b>So'ngi 20 foydalanuvchi:</b>\n\n"
    for u in users:
        text += f"• {u[2]} (@{u[1] or 'N/A'}) — ID: <code>{u[0]}</code>\n"
    
    await message.answer(text)

@dp.message(F.text == "🔙 Asosiy menyu")
async def back_main(message: Message):
    """Asosiy menyuga qaytish"""
    await message.answer("🔙 Asosiy menyu", reply_markup=get_main_menu())

@dp.message(F.text.startswith("http"))
async def process_download(message: Message):
    """Video yuklash"""
    user_id = message.from_user.id
    
    # Blok tekshirish
    user = await get_user(user_id)
    if user and user[6] == 1:
        await message.answer("🚫 Siz botdan bloklangansiz.")
        return
    
    # Kanal tekshirish
    if not await is_user_subscribed(user_id):
        await message.answer(
            "❌ Botdan foydalanish uchun kanalga a'zo boʻling!",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    # Rate limit
    now = time.time()
    if user_id in user_last_request and now - user_last_request[user_id] < 3:
        await message.answer("⏳ Juda tez yuboryapsiz, 3 soniya kuting...")
        return
    user_last_request[user_id] = now
    
    msg = await message.answer("⏬ <b>Video yuklanmoqda...</b>\nIltimos, kuting ⏳")
    
    try:
        file_path = await asyncio.to_thread(download_video, message.text)
        
        # Fayl hajmi tekshirish (50MB dan katta bo'lmasin)
        file_size = os.path.getsize(file_path)
        if file_size > 50 * 1024 * 1024:  # 50MB
            os.remove(file_path)
            await msg.edit_text("❌ Video hajmi 50MB dan katta. Kichikroq video tanlang.")
            await add_download_log(user_id, message.text, "FAILED - LARGE FILE")
            return
        
        await msg.edit_text("📤 <b>Video yuborilmoqda...</b>")
        
        video = FSInputFile(file_path)
        await message.answer_video(
            video,
            caption="✅ <b>Video muvaffaqiyatli yuklandi!</b>\n\n"
                    "🎬 @ClipzyBot — Eng zo'r video yuklovchi bot"
        )
        
        os.remove(file_path)
        await msg.delete()
        await add_download_log(user_id, message.text, "SUCCESS")
        
    except Exception as e:
        logger.error(f"Yuklash xatosi: {e}")
        await msg.edit_text(f"❌ <b>Xatolik yuz berdi!</b>\n\n"
                           f"Sabablari:\n"
                           f"• Video yashirin bo'lishi mumkin\n"
                           f"• Link noto'g'ri\n"
                           f"• Sayt qo'llab-quvvatlanmaydi\n\n"
                           f"Qayta urinib ko'ring yoki admin bilan bog'laning.")
        await add_download_log(user_id, message.text, f"FAILED - {str(e)}")

@dp.message()
async def unknown_message(message: Message):
    """Noma'lum xabar"""
    await message.answer(
        "❓ <b>Tushunmadim</b>\n\n"
        "Iltimos, quyidagilardan birini tanlang yoki video link yuboring 👇",
        reply_markup=get_main_menu()
    )

# ==================== MAIN ====================
async def main():
    await init_db()
    logger.info("🚀 Bot ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())