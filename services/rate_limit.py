import time
from database import usage_count,inc_usage
from config import FREE_DAILY

_buckets={}

def allow(user_id,limit=FREE_DAILY):
    now=time.time(); bucket=_buckets.get(user_id,[]); bucket=[t for t in bucket if now-t<60]
    if len(bucket)>=8: _buckets[user_id]=bucket; return False
    if usage_count(user_id)>=limit: return False
    bucket.append(now); _buckets[user_id]=bucket; inc_usage(user_id); return True
