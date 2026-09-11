import os
from dotenv import load_dotenv
load_dotenv()
BOT_TOKEN=os.getenv('BOT_TOKEN','')
OWNER_ID=int(os.getenv('OWNER_ID','0'))

# پروکسی SOCKS5 برای اتصال به تلگرام - اگه سرور مستقیم به تلگرام دسترسی نداشته باشه
# (مثلاً روی سرورهای داخل ایران)، بدون این، ربات هیچ‌وقت آپدیت نمی‌گیره و کاملاً
# بی‌جواب می‌مونه، بدون هیچ خطای واضحی. مقدار مثل بقیه‌ی ربات‌های همین مجموعه:
#   SOCKS5_PROXY_URL=socks5://user:pass@host:1080
TELEGRAM_PROXY_URL = os.getenv('SOCKS5_PROXY_URL', '').strip() or os.getenv('TELEGRAM_PROXY_URL', '').strip()

SALES_API_URL=os.getenv('SALES_API_URL','').rstrip('/')
SALES_API_KEY=os.getenv('SALES_API_KEY','')
DB_PATH=os.getenv('DB_PATH','/data/hexiron_whisper.db')
DEFAULT_TTL=int(os.getenv('WHISPER_DEFAULT_TTL','3600'))
SESSION_MAX=int(os.getenv('SESSION_MAX_SECONDS','7200'))
FREE_DAILY=int(os.getenv('FREE_DAILY_WHISPERS','50'))
FREE_GROUP_LIMIT=int(os.getenv('FREE_GROUP_LIMIT','1'))
RETENTION_DAYS=int(os.getenv('RETENTION_DAYS','30'))
PRODUCT_CODE=os.getenv('PRODUCT_CODE','whisper')
PUBLIC_CHANNEL_ID=os.getenv('PUBLIC_CHANNEL_ID','')
APP_URL=os.getenv('APP_URL','').rstrip('/')

# مدت زمان کش نتیجه‌ی استعلام لایسنس از HEXIRON SALES (ثانیه) تا هر /whisper مستقیم API نزند
LICENSE_CACHE_TTL=int(os.getenv('LICENSE_CACHE_TTL','300'))
# اگر Sales در دسترس نبود، تا این مدت (ثانیه) از آخرین پلن معتبرِ کش‌شده استفاده کن (fail-open کنترل‌شده)
LICENSE_GRACE_SECONDS=int(os.getenv('LICENSE_GRACE_SECONDS','21600'))

# سقف/محدودیت هر پلن؛ اعداد Pro/Business مطابق جدول پلن‌های تجاری (schematic) است.
# whispers_per_day=None یعنی نامحدود. groups=None یعنی نامحدود.
PLAN_LIMITS={
    'free':    {'whispers_per_day': FREE_DAILY, 'groups': FREE_GROUP_LIMIT},
    'pro':     {'whispers_per_day': None,       'groups': 10},
    'business':{'whispers_per_day': None,       'groups': None},
}
