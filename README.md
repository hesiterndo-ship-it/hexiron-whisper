# HEXIRON WHISPER v2 — Commercial Core

نسخه ارتقایافته برای نجواهای ناشناس در گروه‌های Telegram.

## امکانات
- Anonymous-to-other-user whisper با Reply + `/whisper`
- Request → Accept / Decline
- Session TTL و انقضای خودکار
- Relay پیام خصوصی و مدیای قابل‌کپی توسط Bot API با `copy_message`
- Whisper ID تصادفی مثل `W-58321`
- Block / Unblock
- Report با ثبت رویداد
- Anti-spam پایه + rate limit
- Ban مدیریتی
- گزارش‌های باز و Resolve
- آمار کاربران، گروه‌ها، جلسات، گزارش‌ها و رخدادهای 24 ساعت اخیر
- اتصال آماده به HEXIRON SALES روی `/api/v1/license` با کش و fail-open کنترل‌شده
- اعمال واقعی سقف پلن‌ها (نجوای روزانه و تعداد گروه) بر اساس Free/Pro/Business
- SQLite با WAL و دیسک `/data`
- Docker + Liara
- Mini App shell برای توسعه UI تجاری

## راه‌اندازی
1. در BotFather ربات را بساز.
2. `BOT_TOKEN` و `OWNER_ID` را در محیط قرار بده.
3. اگر Sales داری، `SALES_API_URL` و `SALES_API_KEY` را تنظیم کن.
4. ربات را به گروه اضافه کن.
5. مدیر گروه `/whisper_on` بزند.
6. روی پیام کاربر Reply و `/whisper` اجرا شود.
7. گیرنده باید حداقل یک‌بار ربات را در خصوصی با `/start` باز کرده باشد تا ربات بتواند درخواست را تحویل دهد.

## متغیرهای محیطی
- `BOT_TOKEN`
- `OWNER_ID`
- `SALES_API_URL`
- `SALES_API_KEY`
- `DB_PATH=/data/hexiron_whisper.db`
- `WHISPER_DEFAULT_TTL=3600`
- `SESSION_MAX_SECONDS=7200`
- `FREE_DAILY_WHISPERS=50`
- `FREE_GROUP_LIMIT=1`
- `RETENTION_DAYS=30`
- `PRODUCT_CODE=whisper`
- `APP_URL=`

## دستورات
کاربر:
- `/start`
- `/whisper` در گروه، روی Reply
- `/end`
- `/report [reason]`
- `/block W-12345`
- `/unblock W-12345`

مدیر گروه:
- `/whisper_on`
- `/whisper_off`
- `/whisper_refresh` — بعد از خرید/ارتقای پلن در فروشگاه، پلن رو فوراً (بدون صبر برای انقضای کش) به‌روزرسانی می‌کند

مالک:
- `/wstats`
- `/wreports`
- `/resolve 123`
- `/wban 123456789`

## Privacy / Safety
این محصول «ناشناس برای طرف مقابل» است، نه «غیرقابل‌ردیابی». برای مقابله با سوءاستفاده، شناسه‌های داخلی، زمان جلسه و رخدادهای حداقلی ثبت می‌شوند. متن پیام‌ها در دیتابیس ذخیره نمی‌شوند.

برای انتخاب هدف، Reply + `/whisper` استفاده شده تا ربات مجبور نباشد همه پیام‌های عادی گروه را جمع‌آوری کند.

## Liara
دیسک پایدار را روی `/data` نگه دار. `liara.json` از قبل دیسک `data` را تعریف کرده است.

## اتصال به فروشگاه (HEXIRON SALES)
راهنمای کامل اتصال این بات به‌عنوان یک محصول جدید در `hexiron-sales`، شامل قرارداد API لایسنس و
فایل آماده‌ی listing، در پوشه‌ی [`sales/`](sales/README.md) قرار دارد.

## توسعه بعدی
- پنل مدیریتی کامل وب
- Mini App کامل با inbox/session UI
- پلن Free / Pro / Business از Sales
- Voice Whisper و کنترل رسانه
- analytics dashboard
- تنظیمات جداگانه برای هر گروه
- AI moderation اختیاری با privacy-first retention
