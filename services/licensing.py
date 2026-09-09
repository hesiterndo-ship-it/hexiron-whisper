import time
import httpx
from config import SALES_API_URL, SALES_API_KEY, PRODUCT_CODE, PLAN_LIMITS, LICENSE_CACHE_TTL, LICENSE_GRACE_SECONDS
from database import group

# کش سبک درون‌حافظه‌ای: از زدن API فروش به‌ازای هر تک /whisper جلوگیری می‌کند
# ساختار: {chat_id: {'result':..., 'ts': fetched_at, 'ok_ts': last_successful_fetch_at}}
_cache = {}

TIER_DISPLAY = {'free': 'Free', 'pro': 'Pro', 'business': 'Business'}


def _limits_for(plan):
    return PLAN_LIMITS.get(plan, PLAN_LIMITS['free'])


def _fallback(chat_id):
    """وقتی Sales تنظیم نشده یا در دسترس نیست: از آخرین پلن معتبر (grace) یا free استفاده کن."""
    entry = _cache.get(chat_id)
    now = time.time()
    if entry and entry.get('ok') and (now - entry['ok_ts']) <= LICENSE_GRACE_SECONDS:
        # هنوز داخل بازه‌ی grace هستیم؛ به کاربر تجاری به‌خاطر قطعی موقت Sales آسیب نزن
        result = dict(entry['result'])
        result['source'] = 'grace'
        return result
    return {'active': False, 'plan': 'free', 'plan_label': 'Free', 'limits': _limits_for('free'), 'source': 'fallback'}


async def check_license(chat_id, force=False):
    now = time.time()
    entry = _cache.get(chat_id)
    if not force and entry and (now - entry['ts']) < LICENSE_CACHE_TTL:
        return entry['result']

    if not SALES_API_URL:
        result = {'active': True, 'plan': 'free', 'plan_label': 'Free', 'limits': _limits_for('free'), 'source': 'no_sales_configured'}
        _cache[chat_id] = {'result': result, 'ts': now, 'ok': True, 'ok_ts': now}
        return result

    headers = {'X-API-Key': SALES_API_KEY} if SALES_API_KEY else {}
    try:
        async with httpx.AsyncClient(timeout=8) as x:
            r = await x.get(
                f'{SALES_API_URL}/api/v1/license',
                params={'product': PRODUCT_CODE, 'group_id': chat_id},
                headers=headers,
            )
            if r.is_success:
                d = r.json() if r.content else {}
                active = bool(d.get('active', d.get('valid', False)))
                if active:
                    # HEXIRON SALES پلن رو با دو فیلد برمی‌گردونه:
                    #   plan  = اسم نمایشی که ادمین موقع ساخت پکیج زده (مثلاً "۱ ماهه")
                    #   tier  = دسته‌ی محدودیت (pro/business) که برای اعمال سقف‌ها استفاده می‌شه
                    tier = str(d.get('tier', 'pro')).lower()
                    if tier not in PLAN_LIMITS or tier == 'free':
                        tier = 'pro'
                    plan_label = d.get('plan') or TIER_DISPLAY.get(tier, tier)
                else:
                    tier = 'free'
                    plan_label = 'Free'
                group(chat_id)
                result = {'active': active, 'plan': tier, 'plan_label': plan_label, 'limits': _limits_for(tier), 'source': 'sales'}
                _cache[chat_id] = {'result': result, 'ts': now, 'ok': True, 'ok_ts': now}
                return result
    except Exception:
        pass

    # درخواست به Sales شکست خورد یا پاسخ ناموفق بود
    result = _fallback(chat_id)
    _cache[chat_id] = {'result': result, 'ts': now, 'ok': False, 'ok_ts': entry['ok_ts'] if entry else 0}
    return result


def invalidate(chat_id):
    """برای فراخوانی دستی بعد از خرید/ارتقای پلن، تا کش قدیمی مانع دیده‌شدن پلن جدید نشود."""
    _cache.pop(chat_id, None)
