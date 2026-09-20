import logging

from telegram.ext import Application,CommandHandler,CallbackQueryHandler,MessageHandler,filters
from config import BOT_TOKEN, TELEGRAM_PROXY_URL
from database import init_db,expire_sessions
from handlers import start,whisper,callbacks,private_relay,group_on,group_off,admin,reports,resolve_report,ban_user,whisper_refresh,set_channel

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def expiry_job(context):
    expire_sessions()


async def on_error(update, context):
    logger.error("خطای پیش‌بینی‌نشده: %s", context.error, exc_info=context.error)


def main():
    if not BOT_TOKEN: raise SystemExit('BOT_TOKEN is required')
    init_db()

    builder = Application.builder().token(BOT_TOKEN)
    if TELEGRAM_PROXY_URL:
        # بدون get_updates_proxy، خودِ polling (گرفتن آپدیت‌ها) هنگ می‌کنه، حتی
        # اگه proxy معمولی رو ست کرده باشیم - هر دو باید ست بشن.
        builder = builder.proxy(TELEGRAM_PROXY_URL).get_updates_proxy(TELEGRAM_PROXY_URL)
        logger.info("پروکسی SOCKS5 فعال شد.")
    else:
        logger.warning(
            "SOCKS5_PROXY_URL تنظیم نشده. اگه سرور مستقیم به تلگرام دسترسی نداشته باشه، "
            "ربات همینجا بی‌صدا هنگ می‌کنه (هیچ آپدیتی نمی‌گیره) بدون هیچ خطای دیگه‌ای."
        )

    app = builder.build()
    app.add_handler(CommandHandler('start',start))
    app.add_handler(CommandHandler('whisper',whisper))
    app.add_handler(CommandHandler('whisper_on',group_on))
    app.add_handler(CommandHandler('whisper_off',group_off))
    app.add_handler(CommandHandler('whisper_refresh',whisper_refresh))
    app.add_handler(CommandHandler('wstats',admin))
    app.add_handler(CommandHandler('wreports',reports))
    app.add_handler(CommandHandler('resolve',resolve_report))
    app.add_handler(CommandHandler('wban',ban_user))
    app.add_handler(CommandHandler('setchannel',set_channel))
    app.add_handler(CallbackQueryHandler(callbacks))
    # معادل فارسی /start توی پیوی (باید قبل از هندلر عمومی پیوی ثبت بشه)
    app.add_handler(MessageHandler(filters.Regex('^(شروع|استارت)$') & filters.ChatType.PRIVATE, start))
    # نوشتن «نجوا» به‌عنوان Reply روی پیام کاربر در گروه، دقیقاً معادل /whisper
    app.add_handler(MessageHandler(filters.Regex('^نجوا$') & filters.ChatType.GROUPS & filters.REPLY, whisper))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE,private_relay))
    app.add_error_handler(on_error)
    if app.job_queue is None:
        logger.warning("JobQueue فعال نیست - پاک‌سازی خودکار سشن‌های منقضی (expiry_job) کار نمی‌کنه.")
    else:
        app.job_queue.run_repeating(expiry_job,interval=60,first=10)
    logger.info("🤖 HEXIRON WHISPER شروع به کار کرد...")
    app.run_polling(allowed_updates=['message','callback_query'])


if __name__=='__main__': main()
