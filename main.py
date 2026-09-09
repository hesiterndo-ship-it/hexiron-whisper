from telegram.ext import Application,CommandHandler,CallbackQueryHandler,MessageHandler,filters
from config import BOT_TOKEN
from database import init_db,expire_sessions
from handlers import start,whisper,callbacks,private_relay,group_on,group_off,admin,reports,resolve_report,ban_user,whisper_refresh

async def expiry_job(context):
    expire_sessions()

def main():
    if not BOT_TOKEN: raise SystemExit('BOT_TOKEN is required')
    init_db(); app=Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start',start))
    app.add_handler(CommandHandler('whisper',whisper))
    app.add_handler(CommandHandler('whisper_on',group_on))
    app.add_handler(CommandHandler('whisper_off',group_off))
    app.add_handler(CommandHandler('whisper_refresh',whisper_refresh))
    app.add_handler(CommandHandler('wstats',admin))
    app.add_handler(CommandHandler('wreports',reports))
    app.add_handler(CommandHandler('resolve',resolve_report))
    app.add_handler(CommandHandler('wban',ban_user))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE,private_relay))
    app.job_queue.run_repeating(expiry_job,interval=60,first=10)
    app.run_polling(allowed_updates=['message','callback_query'])
if __name__=='__main__': main()
