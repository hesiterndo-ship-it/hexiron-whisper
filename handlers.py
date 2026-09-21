import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import *
from services.whisper import start_request
from services.rate_limit import allow
from services.moderation import looks_spam
from services.licensing import check_license, invalidate
from config import OWNER_ID, FREE_GROUP_LIMIT, FREE_DAILY, APP_URL


def _display_name(user):
    """اسم قابل‌نمایش یک کاربر - دیگه ناشناس نیست، همیشه اسم/یوزرنیم واقعی نشون داده می‌شه."""
    if not user:
        return 'کاربر'
    if user.username:
        return f'@{user.username}'
    return user.first_name or 'کاربر'


async def _is_paid_plan(chat_id):
    """اگه گروه پلن پولی (pro/business) فعال داره، محدودیت کانال اجباری برداشته می‌شه."""
    lic = await check_license(chat_id)
    return lic.get('plan') in ('pro', 'business')


def _force_sub_channel():
    return get_setting('force_sub_channel_id', '')


def _force_sub_link():
    link = get_setting('force_sub_channel_link', '')
    if link:
        return link
    channel_id = _force_sub_channel()
    if channel_id.startswith('@'):
        return f'https://t.me/{channel_id.lstrip("@")}'
    return ''


async def _check_force_sub(update: Update, context: ContextTypes.DEFAULT_TYPE, user, chat_id) -> bool:
    """True یعنی کاربر مجازه ادامه بده (یا کانالی تنظیم نشده، یا عضوه، یا گروه پلن پولی داره).
    False یعنی جلوش گرفته شد و پیام «عضو شو یا اشتراک بخر» فرستاده شد."""
    channel_id = _force_sub_channel()
    if not channel_id:
        return True
    if await _is_paid_plan(chat_id):
        return True
    check_error = None
    try:
        member = await context.bot.get_chat_member(channel_id, user.id)
        if member.status in ('member', 'administrator', 'creator'):
            return True
    except Exception as e:
        check_error = str(e)

    if check_error:
        await update.effective_message.reply_text(
            f'⚠️ چک عضویت شکست خورد:\n`{check_error}`\nشناسه‌ی کانال: `{channel_id}`\n\n'
            'این متن رو برای بررسی نگه دار.', parse_mode='Markdown',
        )
        return False

    link = _force_sub_link()
    kb_rows = []
    if link:
        kb_rows.append([InlineKeyboardButton('📢 عضویت در کانال', url=link)])
    kb_rows.append([InlineKeyboardButton('✅ عضو شدم، دوباره چک کن', callback_data='checksub')])
    await update.effective_message.reply_text(
        '🔒 برای استفاده از نجوا باید عضو کانال ما باشی، یا اشتراک ماهانه‌ی گروه رو بخری.\n\n'
        'بعد از عضویت در کانال زیر، روی «عضو شدم» بزن:',
        reply_markup=InlineKeyboardMarkup(kb_rows),
    )
    return False

def menu():
    rows=[[InlineKeyboardButton('📖 راهنما',callback_data='help'),InlineKeyboardButton('🆔 شناسه من',callback_data='myid')],
          [InlineKeyboardButton('🚫 مدیریت بلاک',callback_data='block_help'),InlineKeyboardButton('🛑 پایان جلسه',callback_data='end_help')]]
    if APP_URL: rows.append([InlineKeyboardButton('🚀 باز کردن Whisper App',web_app={'url':APP_URL})])
    return InlineKeyboardMarkup(rows)

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    u=update.effective_user; ensure_user(u.id,u.username)
    if update.effective_chat.type=='private':
        await update.message.reply_text('🛡️ HEXIRON WHISPER\n\nنجواهای خصوصی داخل گروه‌های تلگرام - اسم طرفین برای هم مشخصه.\n\nدر گروه روی پیام کاربر Reply کن و /whisper یا فقط بنویس «نجوا».',reply_markup=menu())

async def whisper(update:Update,context:ContextTypes.DEFAULT_TYPE):
    m=update.effective_message; u=update.effective_user; chat=update.effective_chat
    if chat.type not in ('group','supergroup'):
        return await m.reply_text('این دستور را داخل گروه و به‌صورت Reply روی پیام کاربر استفاده کن.')
    g=group(chat.id,chat.title)
    if not g['enabled']: return await m.reply_text('⛔ Whisper در این گروه فعال نیست. مدیر گروه باید /whisper_on را اجرا کند.')
    if not await _check_force_sub(update, context, u, chat.id):
        return
    lic=await check_license(chat.id)
    daily_limit=lic['limits']['whispers_per_day']
    if daily_limit is not None and not allow(u.id, limit=daily_limit):
        return await m.reply_text(f'⛔ سقف استفاده روزانه پلن {lic.get("plan_label", lic["plan"])} ({daily_limit}) پر شده است. برای نامحدود شدن، پلن گروه را ارتقا بده.')
    if not m.reply_to_message or not m.reply_to_message.from_user:
        return await m.reply_text('🔒 روی پیام شخص موردنظر Reply کن و بنویس «نجوا» یا /whisper بزن.')
    target=m.reply_to_message.from_user
    if target.is_bot or target.id==u.id: return await m.reply_text('این کاربر هدف معتبر نیست.')
    ensure_user(target.id,target.username)
    requester_name=_display_name(u); target_name=_display_name(target)
    sid,status=start_request(chat.id,u.id,target.id,a_name=requester_name,b_name=target_name)
    if not sid:
        return await m.reply_text({'blocked':'🚫 بین شما محدودیت بلاک وجود دارد.','busy':'⏳ یکی از طرفین جلسه فعالی دارد.'}.get(status,'⛔ درخواست قابل ایجاد نیست.'))
    kb=InlineKeyboardMarkup([[InlineKeyboardButton('✅ قبول',callback_data=f'acc:{sid}'),InlineKeyboardButton('❌ رد',callback_data=f'dec:{sid}')]])
    try:
        await context.bot.send_message(target.id,f'💬 {requester_name} یک درخواست نجوا برات فرستاده.\n\nاگه قبول کنی، گفت‌وگو در چت خصوصی با ربات انجام می‌شه.',reply_markup=kb)
    except Exception:
        set_session(sid,'undelivered')
        return await m.reply_text('⚠️ تحویل درخواست ممکن نشد. کاربر باید ابتدا ربات را در خصوصی با /start باز کند.')
    log_event(u.id,chat.id,'request_created',sid)
    await m.reply_text(f'✅ درخواست نجوا ثبت شد و برای {target_name} ارسال شد.\nبعد از تایید می‌تونید صحبت کنید.')

async def callbacks(update:Update,context:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer(); u=q.from_user; data=q.data
    if data=='help': return await q.message.reply_text('💬 /whisper یا بنویس «نجوا» — Reply روی پیام کاربر در گروه\n/block @username — بلاک\n/unblock @username — رفع بلاک\n/end — پایان جلسه\n/report [متن] — گزارش جلسه\n/wstats — آمار مالک')
    if data=='myid': return await q.message.reply_text(f'🆔 Whisper ID شما: `{ensure_user(u.id)["whisper_id"]}`',parse_mode='Markdown')
    if data=='block_help': return await q.message.reply_text('برای بلاک: روی پیام کاربر Reply کن و بنویس /block\nبرای رفع بلاک: روی پیام کاربر Reply کن و بنویس /unblock')
    if data=='end_help': return await q.message.reply_text('برای پایان جلسه در همین چت خصوصی /end را بفرست.')
    if data=='checksub':
        channel_id=_force_sub_channel()
        if not channel_id:
            return await q.message.reply_text('✅ محدودیتی فعال نیست، می‌تونی از نجوا استفاده کنی.')
        try:
            member=await context.bot.get_chat_member(channel_id,u.id)
        except Exception as e:
            # این یعنی خودِ درخواست چک عضویت شکست خورده (نه اینکه عضو نبوده) -
            # معمولاً یعنی channel_id اشتباهه یا ربات توی کانال ادمین نیست.
            return await q.message.reply_text(
                f'⚠️ چک عضویت شکست خورد (نه اینکه عضو نیستی - خودِ درخواست خطا داد):\n`{e}`\n\n'
                f'شناسه‌ی کانالی که چک شد: `{channel_id}`\n\n'
                'این متن خطا رو برای بررسی نگه دار.', parse_mode='Markdown',
            )
        if member.status in ('member','administrator','creator'):
            return await q.message.reply_text('✅ عضویتت تایید شد! حالا برگرد به گروه و دوباره روی پیام موردنظر Reply کن و بنویس «نجوا».')
        return await q.message.reply_text(f'❌ هنوز عضو کانال نشدی (وضعیت فعلی: {member.status}). بعد از عضویت دوباره دکمه رو بزن.')
    if data.startswith('acc:'):
        sid=data[4:]; s=session(sid)
        if not s or s['b_id']!=u.id or s['status']!='pending': return await q.message.reply_text('این درخواست دیگر معتبر نیست.')
        if blocked(s['a_id'],u.id) or blocked(u.id,s['a_id']): set_session(sid,'blocked'); return await q.message.reply_text('🚫 درخواست به‌دلیل محدودیت بلاک رد شد.')
        set_session(sid,'active'); log_event(u.id,s['chat_id'],'session_accepted',sid)
        requester_name=s['a_name'] or 'کاربر'; acceptor_name=_display_name(u)
        await q.message.reply_text(f'✅ جلسه با {requester_name} فعال شد. پیام‌هات مستقیم براش ارسال می‌شه.\n\n/end = پایان | /report = گزارش')
        try: await context.bot.send_message(s['a_id'],f'✅ {acceptor_name} درخواست نجوای شما رو پذیرفت! می‌تونید صحبت کنید.\n\n/end = پایان | /report = گزارش')
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
            target=user_by_whisper(wid) if wid else None
            if not target:
                other=s['b_id'] if s['a_id']==u.id else s['a_id']
                target={'user_id':other}
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
    await update.message.reply_text('🟢 HEXIRON WHISPER فعال شد.\n\nبرای شروع: Reply روی پیام کاربر → بنویس «نجوا» یا /whisper بزن.')

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

async def set_channel(update:Update,context:ContextTypes.DEFAULT_TYPE):
    """پنل ادمین (فقط OWNER_ID) - تنظیم کانال اجباری. کاربرانی که پلن پولی ندارن،
    باید عضو این کانال باشن تا بتونن از نجوا استفاده کنن؛ وگرنه باید اشتراک بخرن."""
    if update.effective_user.id!=OWNER_ID: return
    parts=update.message.text.split(maxsplit=2)
    if len(parts)<2:
        current_id=get_setting('force_sub_channel_id','')
        current_link=get_setting('force_sub_channel_link','')
        return await update.message.reply_text(
            'برای تنظیم کانال اجباری، یکی از این‌ها رو بفرست:\n'
            '/setchannel @channelusername\n'
            '/setchannel https://t.me/channelusername\n'
            'یا برای کانال خصوصی (حتماً هر دو رو بده):\n'
            '/setchannel -100XXXXXXXXXX https://t.me/+XXXXXXXX\n\n'
            f'شناسه‌ی فعلی: {current_id or "تنظیم نشده"}\n'
            f'لینک فعلی: {current_link or "—"}\n\n'
            'برای غیرفعال‌کردن کامل: /setchannel off'
        )
    value=parts[1].strip()
    if value.lower()=='off':
        set_setting('force_sub_channel_id',''); set_setting('force_sub_channel_link','')
        return await update.message.reply_text('✅ کانال اجباری غیرفعال شد.')

    explicit_link=parts[2].strip() if len(parts)>2 else ''
    channel_id=value; link=explicit_link
    warn=''

    if value.startswith('http') or value.startswith('t.me/'):
        if not link:
            link=value if value.startswith('http') else f'https://{value}'
        m=re.search(r't\.me/([A-Za-z0-9_]{5,})/?$', value)
        if m and not value.rstrip('/').split('/')[-1].startswith('+'):
            channel_id='@'+m.group(1)
        else:
            warn=('\n\n⚠️ چون این یک لینک دعوت خصوصیه (نه لینک عمومی کانال)، ربات نمی‌تونه با همین به‌تنهایی '
                  'عضویت رو خودکار چک کنه. برای چک خودکار، شناسه‌ی عددی کانال رو هم بفرست:\n'
                  '/setchannel -100XXXXXXXXXX ' + link)
    elif value.startswith('@'):
        if not link:
            link=f'https://t.me/{value.lstrip("@")}'

    set_setting('force_sub_channel_id',channel_id); set_setting('force_sub_channel_link',link)
    await update.message.reply_text(
        f'✅ کانال اجباری تنظیم شد.\nشناسه: {channel_id}\nلینک عضویت: {link or "—"}{warn}\n\n'
        '⚠️ یادت نره: ربات باید توی این کانال ادمین باشه، وگرنه اصلاً نمی‌تونه عضویت رو چک کنه.'
    )
