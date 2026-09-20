from database import *
from config import DEFAULT_TTL, SESSION_MAX

def can_start(a,b):
    if a==b or is_banned(a) or is_banned(b): return False,'blocked'
    if blocked(a,b) or blocked(b,a): return False,'blocked'
    if active_for(a) or active_for(b): return False,'busy'
    return True,'ok'

def start_request(chat_id,a,b,ttl=DEFAULT_TTL,a_name='',b_name=''):
    ensure_user(a); ensure_user(b)
    ok,reason=can_start(a,b)
    if not ok: return None,reason
    return create_session(chat_id,a,b,min(ttl,SESSION_MAX),a_name,b_name),'ok'
