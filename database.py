import sqlite3, threading, time, secrets
from config import DB_PATH
_lock=threading.RLock()

def db():
    con=sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory=sqlite3.Row
    return con

def init_db():
    with _lock:
        c=db(); c.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY, whisper_id TEXT UNIQUE NOT NULL, username TEXT, created_at INTEGER NOT NULL, last_seen INTEGER NOT NULL, banned INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS groups(chat_id INTEGER PRIMARY KEY, title TEXT, enabled INTEGER DEFAULT 0, created_at INTEGER NOT NULL, plan TEXT DEFAULT 'free', settings_json TEXT DEFAULT '{}', owner_id INTEGER);
        CREATE INDEX IF NOT EXISTS idx_groups_owner ON groups(owner_id);
        CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, chat_id INTEGER, a_id INTEGER NOT NULL, b_id INTEGER NOT NULL, status TEXT NOT NULL, created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS blocks(blocker INTEGER NOT NULL, blocked INTEGER NOT NULL, created_at INTEGER NOT NULL, PRIMARY KEY(blocker,blocked));
        CREATE TABLE IF NOT EXISTS reports(id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, reporter INTEGER, target INTEGER, reason TEXT, created_at INTEGER, status TEXT DEFAULT 'open');
        CREATE TABLE IF NOT EXISTS usage(user_id INTEGER NOT NULL, day TEXT NOT NULL, count INTEGER DEFAULT 0, PRIMARY KEY(user_id,day));
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, chat_id INTEGER, kind TEXT, meta TEXT DEFAULT '', created_at INTEGER);
        CREATE INDEX IF NOT EXISTS idx_sessions_users ON sessions(a_id,b_id,status);
        CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status);
        CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at);
        '''); c.commit()
        # migration سبک برای دیتابیس‌های قدیمی‌تر که ستون owner_id را ندارند
        cols=[r['name'] for r in c.execute('PRAGMA table_info(groups)').fetchall()]
        if 'owner_id' not in cols:
            c.execute('ALTER TABLE groups ADD COLUMN owner_id INTEGER'); c.commit()
        # migration: نجوا دیگه ناشناس نیست - اسم نمایشی هر دو طرف رو نگه می‌داریم
        cols=[r['name'] for r in c.execute('PRAGMA table_info(sessions)').fetchall()]
        if 'a_name' not in cols:
            c.execute('ALTER TABLE sessions ADD COLUMN a_name TEXT'); c.commit()
        if 'b_name' not in cols:
            c.execute('ALTER TABLE sessions ADD COLUMN b_name TEXT'); c.commit()
        c.close()

def ensure_user(user_id, username=None):
    now=int(time.time())
    with _lock:
        c=db(); r=c.execute('SELECT * FROM users WHERE user_id=?',(user_id,)).fetchone()
        if not r:
            while True:
                wid='W-'+str(secrets.randbelow(90000)+10000)
                try:
                    c.execute('INSERT INTO users(user_id,whisper_id,username,created_at,last_seen) VALUES(?,?,?,?,?)',(user_id,wid,username or '',now,now)); break
                except sqlite3.IntegrityError: continue
        else:
            c.execute('UPDATE users SET username=?, last_seen=? WHERE user_id=?',(username if username is not None else r['username'],now,user_id))
        c.commit(); r=c.execute('SELECT * FROM users WHERE user_id=?',(user_id,)).fetchone(); c.close(); return r

def user_by_whisper(wid):
    c=db(); r=c.execute('SELECT * FROM users WHERE whisper_id=?',(wid.upper().strip(),)).fetchone(); c.close(); return r

def group(chat_id,title=''):
    now=int(time.time()); c=db(); r=c.execute('SELECT * FROM groups WHERE chat_id=?',(chat_id,)).fetchone()
    if not r:
        c.execute('INSERT INTO groups(chat_id,title,created_at) VALUES(?,?,?)',(chat_id,title,now)); c.commit(); r=c.execute('SELECT * FROM groups WHERE chat_id=?',(chat_id,)).fetchone()
    elif title and r['title'] != title:
        c.execute('UPDATE groups SET title=? WHERE chat_id=?',(title,chat_id)); c.commit(); r=c.execute('SELECT * FROM groups WHERE chat_id=?',(chat_id,)).fetchone()
    c.close(); return r

def set_group(chat_id,title,enabled=True,plan=None,owner_id=None):
    group(chat_id,title); c=db()
    if plan is None: c.execute('UPDATE groups SET enabled=? WHERE chat_id=?',(int(enabled),chat_id))
    else: c.execute('UPDATE groups SET enabled=?,plan=? WHERE chat_id=?',(int(enabled),plan,chat_id))
    if owner_id is not None:
        c.execute('UPDATE groups SET owner_id=? WHERE chat_id=? AND owner_id IS NULL',(owner_id,chat_id))
    c.commit(); c.close()

def count_active_groups_for_owner(owner_id, exclude_chat_id=None):
    """تعداد گروه‌های فعالی که این owner قبلاً Whisper را در آن‌ها روشن کرده (برای اعمال سقف پلن Free)."""
    c=db()
    r=c.execute('SELECT COUNT(*) n FROM groups WHERE owner_id=? AND enabled=1 AND chat_id!=?',
                (owner_id, exclude_chat_id or 0)).fetchone()
    c.close(); return r['n']

def usage_count(uid):
    day=time.strftime('%Y-%m-%d'); c=db(); r=c.execute('SELECT count FROM usage WHERE user_id=? AND day=?',(uid,day)).fetchone(); c.close(); return r['count'] if r else 0

def inc_usage(uid):
    day=time.strftime('%Y-%m-%d'); c=db(); c.execute('INSERT INTO usage(user_id,day,count) VALUES(?,?,1) ON CONFLICT(user_id,day) DO UPDATE SET count=count+1',(uid,day)); c.commit(); c.close()

def blocked(a,b):
    c=db(); r=c.execute('SELECT 1 FROM blocks WHERE blocker=? AND blocked=?',(a,b)).fetchone(); c.close(); return bool(r)

def toggle_block(a,b):
    c=db(); r=c.execute('SELECT 1 FROM blocks WHERE blocker=? AND blocked=?',(a,b)).fetchone()
    if r: c.execute('DELETE FROM blocks WHERE blocker=? AND blocked=?',(a,b)); val=False
    else: c.execute('INSERT OR IGNORE INTO blocks VALUES(?,?,?)',(a,b,int(time.time()))); val=True
    c.commit(); c.close(); return val

def is_banned(uid):
    c=db(); r=c.execute('SELECT banned FROM users WHERE user_id=?',(uid,)).fetchone(); c.close(); return bool(r and r['banned'])

def set_banned(uid,value):
    ensure_user(uid); c=db(); c.execute('UPDATE users SET banned=? WHERE user_id=?',(int(value),uid)); c.commit(); c.close()

def get_setting(key, default=''):
    c=db(); r=c.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone(); c.close()
    return r['value'] if r else default

def set_setting(key, value):
    c=db(); c.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,value)); c.commit(); c.close()

def create_session(chat_id,a,b,ttl,a_name='',b_name=''):
    sid=secrets.token_urlsafe(9); now=int(time.time()); ttl=max(60,int(ttl))
    c=db(); c.execute(
        'INSERT INTO sessions(id,chat_id,a_id,b_id,status,created_at,expires_at,a_name,b_name) VALUES(?,?,?,?,?,?,?,?,?)',
        (sid,chat_id,a,b,'pending',now,now+ttl,a_name,b_name)
    ); c.commit(); c.close(); return sid

def session(sid):
    c=db(); r=c.execute('SELECT * FROM sessions WHERE id=?',(sid,)).fetchone(); c.close(); return r

def set_session(sid,status):
    c=db(); c.execute('UPDATE sessions SET status=? WHERE id=?',(status,sid)); c.commit(); c.close()

def expire_sessions():
    now=int(time.time()); c=db(); cur=c.execute("UPDATE sessions SET status='expired' WHERE status IN ('pending','active') AND expires_at<=?",(now,)); n=cur.rowcount; c.commit(); c.close(); return n

def active_for(uid):
    c=db(); r=c.execute("SELECT * FROM sessions WHERE (a_id=? OR b_id=?) AND status='active' AND expires_at>? ORDER BY created_at DESC LIMIT 1",(uid,uid,int(time.time()))).fetchone(); c.close(); return r

def pending_for(uid):
    c=db(); r=c.execute("SELECT * FROM sessions WHERE b_id=? AND status='pending' AND expires_at>? ORDER BY created_at DESC LIMIT 1",(uid,int(time.time()))).fetchone(); c.close(); return r

def add_report(sid,reporter,target,reason):
    c=db(); c.execute('INSERT INTO reports(session_id,reporter,target,reason,created_at) VALUES(?,?,?,?,?)',(sid,reporter,target,reason,int(time.time()))); c.commit(); c.close()

def list_reports(limit=20):
    c=db(); rows=c.execute("SELECT * FROM reports WHERE status='open' ORDER BY created_at DESC LIMIT ?",(limit,)).fetchall(); c.close(); return rows

def close_report(report_id):
    c=db(); c.execute("UPDATE reports SET status='closed' WHERE id=?",(report_id,)); c.commit(); c.close()

def log_event(uid,chat_id,kind,meta=''):
    c=db(); c.execute('INSERT INTO events(user_id,chat_id,kind,meta,created_at) VALUES(?,?,?,?,?)',(uid,chat_id,kind,meta,int(time.time()))); c.commit(); c.close()

def stats():
    c=db(); out={
      'users':c.execute('SELECT COUNT(*) n FROM users').fetchone()['n'],
      'groups':c.execute('SELECT COUNT(*) n FROM groups WHERE enabled=1').fetchone()['n'],
      'sessions':c.execute('SELECT COUNT(*) n FROM sessions').fetchone()['n'],
      'active':c.execute("SELECT COUNT(*) n FROM sessions WHERE status='active'").fetchone()['n'],
      'reports':c.execute("SELECT COUNT(*) n FROM reports WHERE status='open'").fetchone()['n'],
      'events24':c.execute('SELECT COUNT(*) n FROM events WHERE created_at>?',(int(time.time())-86400,)).fetchone()['n']
    }; c.close(); return out
