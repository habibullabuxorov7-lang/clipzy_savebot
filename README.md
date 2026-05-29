# 🎬 Clipzy Save Bot

Telegram-da video yuklovchi bot. YouTube, TikTok, Instagram, Facebook va boshqa saytlardan videolarni yuklash uchun.

## ✨ Xususiyatlari

- 📥 **Video yuklash** - YouTube, TikTok, Instagram, Facebook va boshqa saytlardan
- 👥 **Referral sistema** - Do'stlaringizni taklif qiling
- 📊 **Admin panel** - Statistika va foydalanuvchi boshqarish
- 🚫 **Bloklash sistema** - Xirij foydalanuvchilarni bloklash
- 🔐 **Kanal tekshirish** - Faqat a'zo bo'lgan foydalanuvchilar foydalanishi mumkin
- ⏱ **Rate limiting** - Tezlik cheklovlari
- 📝 **Database** - Foydalanuvchi va yuklamalari logi

## 🚀 O'rnatish

### 1. Oracle Cloud-da VM yaratish

```bash
# SSH orqali VM-ga ulanish
ssh -i /path/to/key.key ubuntu@YOUR_PUBLIC_IP

# Python va kutubxonalarni o'rnatish
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip git -y
pip3 install -r requirements.txt
```

### 2. Repository-ni klonlash

```bash
git clone https://github.com/habibullabuxorov7-lang/clipzy_savebot.git
cd clipzy_savebot
```

### 3. .env faylini yaratish

```bash
cp .env.example .env
nano .env
```

Quyidagini kiriting:
```
TELEGRAM_BOT_TOKEN=8604348453:AAHA8zhxeA89-1UfY7_UEQD1-GKFTqUBk3c
ADMIN_ID=1920773269
REQUIRED_CHANNEL=@clipzy_download
```

### 4. Bot-ni test qilish

```bash
python3 main.py
```

### 5. Systemd service-ni o'rnatish (24/7)

```bash
sudo nano /etc/systemd/system/clipzy_savebot.service
```

Quyidagini yozing:
```ini
[Unit]
Description=Clipzy Save Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/clipzy_savebot
ExecStart=/usr/bin/python3 /home/ubuntu/clipzy_savebot/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Saqlash: `Ctrl+X` → `Y` → `Enter`

### 6. Systemd-ni ishga tushirish

```bash
sudo systemctl daemon-reload
sudo systemctl enable clipzy_savebot
sudo systemctl start clipzy_savebot
sudo systemctl status clipzy_savebot
```

## 📋 Komandalar

### User komandalar

- `/start` - Bot-ni ishga tushirish
- `📥 Video yuklash` - Video linkini yuboring
- `📊 Mening hisobim` - Hisobim ma'lumotlari
- `👥 Referral` - Referral linkini olish
- `❓ Yordam` - Yordam
- `📞 Admin bilan aloqa` - Admin bilan bog'lanish

### Admin komandalar

- `/ban [user_id]` - Foydalanuvchini bloklash
- `/unban [user_id]` - Blokdan ochish
- `/broadcast [xabar]` - Barcha foydalanuvchilarga xabar yuborish
- `📊 Statistika` - Bot statistikasi
- `📋 Foydalanuvchilar ro'yxati` - So'ngi 20 ta foydalanuvchi

## 🛠️ Muammoni hal qilish

### Bot loglarini ko'rish

```bash
sudo journalctl -u clipzy_savebot -f
```

### Bot-ni qayta ishga tushirish

```bash
sudo systemctl restart clipzy_savebot
```

### Bot-ni to'xtatish

```bash
sudo systemctl stop clipzy_savebot
```

### SSH orqali yangi terminal ochish (Bot ishlab tursin)

```bash
screen -S telegrambot
python3 main.py
# Ctrl+A > D (chiqish)
```

## 📊 Database

Bot quyidagi jadvallardan foydalanadi:

### users
- `id` - Telegram user ID
- `username` - Telegram username
- `first_name` - Foydalanuvchi ismi
- `ref` - Referral ID
- `balance` - Balans
- `joined_at` - Qo'shilgan sana
- `is_banned` - Bloklangan yo'q

### downloads
- `id` - Yuklash ID
- `user_id` - Foydalanuvchi ID
- `url` - Video URL
- `downloaded_at` - Yuklangan sana
- `status` - Yuklash statusi (SUCCESS, FAILED)

## 📝 Lisenziya

MIT License

## 👨‍💻 Muallif

**Habibulla Buxorov**

---

**Bot: @clipzy_save_dowlbot**

**Kanal: @clipzy_download**