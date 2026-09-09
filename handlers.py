from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import *
from services.whisper import start_request
from services.rate_limit import allow
from services.moderation import looks_spam
from services.licensing import check_license, invalidate
from config import OWNER_ID, FREE_GROUP_LIMIT, FREE_DAILY, APP_URL


def menu():
    rows=[[InlineKeyboardButton('📖 راهنما',callback_data='help'),InlineKeyboardButton('🆔 شناسه من',callback_data='myid')],
          [InlineKeyboardButton('🚫 مدیریت بلاک',callback_data='block_help'),InlineKeyboardButton('🛑 پایان جلسه',callback_data='end_help')]]
    if APP_URL: rows.append([InlineKeyboardButton('🚀 باز کردن Whisper App',web_app={'url':APP_URL})])
    return InlineKeyboardMarkup(rows)

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    u=update.effective_user; ensure_user(u.id,u.username)
    if update.effective_chat.type=='private':
        await update.message.reply_text('🛡️ HEXIRON WHISPER\n\nنجواهای خصوصی و ناشناس داخل گروه‌های تلگرام.\n\nدر گروه روی پیام کاربر Reply کن و /whisper بزن.\n\n⚠️ هویت برای طرف مقابل مخفی است، اما سرویس برای امنیت و رسیدگی به سوءاستفاده متادیتای حداقلی نگه می‌دارد.',reply_markup=menu())

async def whisper(update:Update,context:ContextTypes.DEFAULT_TYPE):
    m=update.effective_message; u=update.effective_user; chat=update.effective_chat
    if chat.type not in ('group','supergroup'):
        return await m.reply_text('این دستور را داخل گروه و به‌صورت Reply روی پیام کاربر استفاده کن.')
    g=group(chat.id,chat.title)
    if not g['enabled']: return await m.reply_text('⛔ Whisper در این گروه فعال نیست. مدیر گروه باید /whisper_on را اجرا کند.')
    lic=await check_license(chat.id)
    daily_limit=lic['limits']['whispers_per_day']
    if daily_limit is not None and not allow(u.id, limit=daily_limit):
        return await m.reply_text(f'⛔ سقف استفاده روزانه پلن {lic.get("plan_label", lic["plan"])} ({daily_limit}) پر شده است. برای نامحدود شدن، پلن گروه را ارتقا بده.')
    if not m.reply_to_message or not m.reply_to_message.from_user:
        return await m.reply_text('🔒 روی پیام شخص موردنظر Reply کن و سپس /whisper بزن.')
    target=m.reply_to_message.from_user
    if target.is_bot or target.id==u.id: return await m.reply_text('این کاربر هدف معتبر نیست.')
    ensure_user(target.id,target.username)
    sid,status=start_request(chat.id,u.id,target.id)
    if not sid:
        return await m.reply_text({'blocked':'🚫 بین شما محدودیت بلاک وجود دارد.','busy':'⏳ یکی از طرفین جلسه فعالی دارد.'}.get(status,'⛔ درخواست قابل ایجاد نیست.'))
    wid=ensure_user(u.id)['whisper_id']
    kb=InlineKeyboardMarkup([[InlineKeyboardButton('✅ قبول',callback_data=f'acc:{sid}'),InlineKeyboardButton('❌ رد',callback_data=f'dec:{sid}')]])
    try:
        await context.bot.send_message(target.id,f'💬 یک درخواست نجوا از یک کاربر این گروه داری.\nشناسه ناشناس درخواست: `{wid}`\n\nاگر قبول کنی، گفت‌وگو در چت خصوصی با ربات انجام می‌شود.',reply_markup=kb,parse_mode='Markdown')
    except Exception:
        set_session(sid,'undelivered')
        return await m.reply_text('⚠️ تحویل درخواست ممکن نشد. کاربر باید ابتدا ربات را در خصوصی با /start باز کند.')
    log_event(u.id,chat.id,'request_created',sid); await m.reply_text('✅ درخواست نجوا ارسال شد. هویت شما برای طرف مقابل نمایش داده نمی‌شود.')

async def callbacks(update:Update,context:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer(); u=q.from_user; data=q.data
    if data=='help': return await q.message.reply_text('💬 /whisper — Reply روی پیام کاربر در گروه\n/block W-12345 — بلاک\n/unblock W-12345 — رفع بلاک\n/end — پایان جلسه\n/report [متن] — گزارش جلسه\n/wstats — آمار مالک')
    if data=='myid': return await q.message.reply_text(f'🆔 Whisper ID شما: `{ensure_user(u.id)["whisper_id"]}`',parse_mode='Markdown')
    if data=='block_help': return await q.message.reply_text('برای بلاک: /block W-12345\nبرای رفع بلاک: /unblock W-12345')
    if data=='end_help': return await q.message.reply_text('برای پایان جلسه در همین چت خصوصی /end را بفرست.')
    if data.startswith('acc:'):
        sid=data[4:]; s=session(sid)
        if not s or s['b_id']!=u.id or s['status']!='pending': return await q.message.reply_text('این درخواست دیگر معتبر نیست.')
        if blocked(s['a_id'],u.id) or blocked(u.id,s['a_id']): set_session(sid,'blocked'); return await q.message.reply_text('🚫 درخواست به‌دلیل محدودیت بلاک رد شد.')
        set_session(sid,'active'); log_event(u.id,s['chat_id'],'session_accepted',sid)
        await q.message.reply_text('✅ جلسه فعال شد. پیام‌ها را همین‌جا برای ربات بفرست؛ محتوای شما بدون نمایش هویت به طرف مقابل منتقل می‌شود.\n\n/end = پایان | /report = گزارش')
        try: await context.bot.send_message(s['a_id'],'✅ درخواست نجوا پذیرفته شد. جلسه فعال است.\n\n/end = پایان | /report = گزارش')
        except Exception: pass
    elif data.startswith('dec:'):
        sid=data[4:]; s=session(sid)
        if s and s['b_id']==u.id: set_session(sid,'declined'); log_event(u.id,s['chat_id'],'session_declined',sid)
        await q.message.reply_text('❌ درخواست رد شد.')

async def private_relay(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type!='private': return
    u=update.effective_user; ensure_user(u.id,u.username); s=active_for(u.id)
    if not s: return
    msg=update.effective_message; text=msg.text or msg.caption or ''
    if text.startswith('/'):
        cmd=text.split()[0].split('@')[0].lower()
        if cmd=='/end':
            set_session(s['id'],'ended'); await msg.reply_text('🛑 جلسه پایان یافت.'); return
        if cmd=='/report':
            other=s['b_id'] if s['a_id']==u.id else s['a_id']; reason=text.partition(' ')[2].strip() or 'user report'; add_report(s['id'],u.id,other,reason); log_event(u.id,s['chat_id'],'report',s['id']); await msg.reply_text('🚨 گزارش ثبت شد. تیم مدیریت می‌تواند آن را بررسی کند.'); return
        if cmd in ('/block','/unblock'):
            parts=text.split(); wid=parts[1] if len(parts)>1 else ''
            target=user_by_whisper(wid)
            if not target: return await msg.reply_text('شناسه Whisper پیدا نشد.')
            val=toggle_block(u.id,target['user_id'])
            return await msg.reply_text(('🚫 بلاک شد.' if val else '✅ رفع بلاک شد.'))
    if looks_spam(text): return await msg.reply_text('🛡️ پیام به‌دلیل کنترل ضداسپم ارسال نشد.')
    other=s['b_id'] if s['a_id']==u.id else s['a_id']
    if blocked(u.id,other) or blocked(other,u.id): set_session(s['id'],'blocked'); return await msg.reply_text('🚫 جلسه متوقف شد.')
    try:
        await context.bot.copy_message(chat_id=other,from_chat_id=u.id,message_id=msg.message_id,protect_content=True)
    except Exception:
        await msg.reply_text('⚠️ ارسال انجام نشد؛ ممکن است نوع پیام توسط Telegram Bot API قابل کپی نباشد.')

async def group_on(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ('group','supergroup'): return
    chat_id=update.effective_chat.id; admin_id=update.effective_user.id
    member=await context.bot.get_chat_member(chat_id,admin_id)
    if member.status not in ('administrator','creator'): return await update.message.reply_text('فقط مدیر گروه می‌تواند Whisper را فعال کند.')
    lic=await check_license(chat_id, force=True)
    group_limit=lic['limits']['groups']
    if group_limit is not None:
        already=count_active_groups_for_owner(admin_id, exclude_chat_id=chat_id)
        if already>=group_limit:
            return await update.message.reply_text(
                f'⛔ سقف گروه‌های فعال برای پلن {lic.get("plan_label", lic["plan"])} ({group_limit} گروه) پر شده است.\n'
                'برای فعال‌سازی این گروه، پلن را ارتقا بده یا یکی از گروه‌های قبلی را با /whisper_off غیرفعال کن.')
    set_group(chat_id,update.effective_chat.title,True,lic['plan'],owner_id=admin_id)
    await update.message.reply_text('🟢 HEXIRON WHISPER فعال شد.\n\nبرای شروع: Reply روی پیام کاربر → /whisper')

async def whisper_refresh(update:Update,context:ContextTypes.DEFAULT_TYPE):
    """بعد از خرید/ارتقای پلن در فروشگاه، مدیر گروه این را بزند تا پلن جدید فوراً اعمال شود (بدون صبر برای انقضای کش)."""
    if update.effective_chat.type not in ('group','supergroup'): return
    chat_id=update.effective_chat.id
    member=await context.bot.get_chat_member(chat_id,update.effective_user.id)
    if member.status not in ('administrator','creator'): return await update.message.reply_text('فقط مدیر گروه.')
    invalidate(chat_id)
    lic=await check_license(chat_id, force=True)
    g=group(chat_id)
    if g['enabled']: set_group(chat_id,update.effective_chat.title,True,lic['plan'])
    limits=lic['limits']
    daily='نامحدود' if limits['whispers_per_day'] is None else limits['whispers_per_day']
    groups_n='نامحدود' if limits['groups'] is None else limits['groups']
    await update.message.reply_text(f'🔄 پلن به‌روزرسانی شد: {lic.get("plan_label", lic["plan"])}\nسقف روزانه: {daily}\nسقف گروه‌ها: {groups_n}')

async def group_off(update,context):
    if update.effective_chat.type not in ('group','supergroup'): return
    member=await context.bot.get_chat_member(update.effective_chat.id,update.effective_user.id)
    if member.status not in ('administrator','creator'): return await update.message.reply_text('فقط مدیر گروه.')
    set_group(update.effective_chat.id,update.effective_chat.title,False); await update.message.reply_text('🔴 Whisper در این گروه غیرفعال شد.')

async def admin(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=OWNER_ID: return
    s=stats(); await update.message.reply_text(f'📊 HEXIRON WHISPER\n\nUsers: {s["users"]}\nGroups: {s["groups"]}\nSessions: {s["sessions"]}\nActive: {s["active"]}\nOpen reports: {s["reports"]}\nEvents/24h: {s["events24"]}')

async def reports(update,context):
    if update.effective_user.id!=OWNER_ID: return
    rows=list_reports(15)
    if not rows: return await update.message.reply_text('✅ گزارشی باز نیست.')
    text='🚨 گزارش‌های باز:\n\n' + '\n'.join(f'#{r["id"]} | reporter={r["reporter"]} | target={r["target"]}\n{r["reason"]}' for r in rows)
    await update.message.reply_text(text[:3900])

async def resolve_report(update,context):
    if update.effective_user.id!=OWNER_ID: return
    parts=update.message.text.split()
    if len(parts)<2 or not parts[1].isdigit(): return await update.message.reply_text('/resolve <report_id>')
    close_report(int(parts[1])); await update.message.reply_text('✅ گزارش بسته شد.')

async def ban_user(update,context):
    if update.effective_user.id!=OWNER_ID: return
    parts=update.message.text.split()
    if len(parts)<2: return await update.message.reply_text('/wban <telegram_user_id>')
    try: uid=int(parts[1]); set_banned(uid,True); await update.message.reply_text('🚫 کاربر از Whisper محروم شد.')
    except ValueError: await update.message.reply_text('شناسه عددی معتبر نیست.')
