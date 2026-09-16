import os, sqlite3, json
from datetime import datetime, date, timedelta
from functools import wraps
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-change-this-secret')
DB_PATH = os.getenv('SQLITE_DB', os.path.join(os.path.dirname(__file__), 'career.db'))


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def init_db():
    conn = db()
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      email TEXT NOT NULL UNIQUE,
      password_hash TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS preferences (
      user_id INTEGER PRIMARY KEY,
      goal TEXT DEFAULT '', hours REAL DEFAULT 2,
      wake TEXT DEFAULT '06:30', sleep TEXT DEFAULT '23:00',
      available TEXT DEFAULT '', weekdays TEXT DEFAULT 'Monday,Tuesday,Wednesday,Thursday,Friday,Saturday,Sunday',
      level TEXT DEFAULT 'Beginner', updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS tasks (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      title TEXT NOT NULL,
      phase TEXT DEFAULT 'Phase 1',
      task_date TEXT NOT NULL,
      task_time TEXT DEFAULT '18:00',
      duration INTEGER DEFAULT 60,
      notes TEXT DEFAULT '', completed INTEGER DEFAULT 0,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    ''')
    conn.commit(); conn.close()


def current_user():
    uid = session.get('user_id')
    if not uid: return None
    conn = db(); row = conn.execute('SELECT id,name,email FROM users WHERE id=?',(uid,)).fetchone(); conn.close()
    return row


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user(): return jsonify({'error':'Authentication required'}), 401
        return fn(*args, **kwargs)
    return wrapper


def task_json(r):
    d = dict(r); d['completed'] = bool(d['completed']); return d

@app.route('/')
def home():
    return redirect(url_for('dashboard') if current_user() else url_for('login'))

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('index.html', user=current_user())

@app.post('/api/register')
def api_register():
    data=request.get_json(silent=True) or {}; name=str(data.get('name','')).strip(); email=str(data.get('email','')).strip().lower(); password=str(data.get('password',''))
    if len(name)<2 or '@' not in email or len(password)<8: return jsonify({'error':'Enter a valid name, email, and password of at least 8 characters.'}),400
    conn=db()
    try:
        cur=conn.execute('INSERT INTO users(name,email,password_hash) VALUES(?,?,?)',(name,email,generate_password_hash(password)))
        uid=cur.lastrowid
        conn.execute('INSERT INTO preferences(user_id) VALUES(?)',(uid,)); conn.commit()
        session['user_id']=uid
        return jsonify({'ok':True,'redirect':'/dashboard'})
    except sqlite3.IntegrityError: return jsonify({'error':'An account with this email already exists.'}),409
    finally: conn.close()

@app.post('/api/login')
def api_login():
    data=request.get_json(silent=True) or {}; email=str(data.get('email','')).strip().lower(); password=str(data.get('password',''))
    conn=db(); row=conn.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone(); conn.close()
    if not row or not check_password_hash(row['password_hash'],password): return jsonify({'error':'Invalid email or password.'}),401
    session['user_id']=row['id']; return jsonify({'ok':True,'redirect':'/dashboard'})

@app.post('/api/logout')
def api_logout(): session.clear(); return jsonify({'ok':True,'redirect':'/login'})

@app.get('/api/me')
def api_me():
    u=current_user()
    if not u: return jsonify({'authenticated':False})
    return jsonify({'authenticated':True,'user':dict(u)})

@app.get('/api/tasks')
@login_required
def get_tasks():
    conn=db(); rows=conn.execute('SELECT * FROM tasks WHERE user_id=? ORDER BY task_date, task_time, id',(session['user_id'],)).fetchall(); conn.close(); return jsonify([task_json(r) for r in rows])

@app.post('/api/tasks')
@login_required
def create_task():
    data=request.get_json(silent=True) or {}; title=str(data.get('title','')).strip(); td=str(data.get('task_date',date.today().isoformat()));
    if not title: return jsonify({'error':'Task title is required.'}),400
    try: duration=max(5,min(1440,int(data.get('duration',60))))
    except: duration=60
    conn=db(); cur=conn.execute('INSERT INTO tasks(user_id,title,phase,task_date,task_time,duration,notes,completed) VALUES(?,?,?,?,?,?,?,?)',(session['user_id'],title,data.get('phase','Phase 1'),td,data.get('task_time','18:00'),duration,data.get('notes',''),int(bool(data.get('completed',False))))); conn.commit(); row=conn.execute('SELECT * FROM tasks WHERE id=?',(cur.lastrowid,)).fetchone(); conn.close(); return jsonify(task_json(row)),201

@app.put('/api/tasks/<int:tid>')
@login_required
def update_task(tid):
    data=request.get_json(silent=True) or {}; conn=db(); old=conn.execute('SELECT * FROM tasks WHERE id=? AND user_id=?',(tid,session['user_id'])).fetchone()
    if not old: conn.close(); return jsonify({'error':'Task not found.'}),404
    fields=['title','phase','task_date','task_time','duration','notes','completed']; vals=[data.get(f,old[f]) for f in fields]
    try: vals[4]=max(5,min(1440,int(vals[4]))); vals[5]=str(vals[5]); vals[6]=int(bool(vals[6]))
    except: conn.close(); return jsonify({'error':'Invalid task data.'}),400
    conn.execute('UPDATE tasks SET title=?,phase=?,task_date=?,task_time=?,duration=?,notes=?,completed=? WHERE id=? AND user_id=?',(*vals,tid,session['user_id'])); conn.commit(); row=conn.execute('SELECT * FROM tasks WHERE id=?',(tid,)).fetchone(); conn.close(); return jsonify(task_json(row))

@app.delete('/api/tasks/<int:tid>')
@login_required
def delete_task(tid):
    conn=db(); cur=conn.execute('DELETE FROM tasks WHERE id=? AND user_id=?',(tid,session['user_id'])); conn.commit(); conn.close(); return jsonify({'ok':cur.rowcount>0})

@app.get('/api/stats')
@login_required
def stats():
    conn=db(); rows=conn.execute('SELECT completed FROM tasks WHERE user_id=?',(session['user_id'],)).fetchall(); today=conn.execute('SELECT COUNT(*) n FROM tasks WHERE user_id=? AND task_date=?',(session['user_id'],date.today().isoformat())).fetchone()['n']; done=sum(int(r['completed']) for r in rows); total=len(rows); conn.close(); return jsonify({'total':total,'completed':done,'progress':round(done/total*100) if total else 0,'today':today})

@app.route('/api/preferences',methods=['GET','POST'])
@login_required
def preferences():
    conn=db()
    if request.method=='GET':
        r=conn.execute('SELECT * FROM preferences WHERE user_id=?',(session['user_id'],)).fetchone(); conn.close(); return jsonify(dict(r) if r else {})
    data=request.get_json(silent=True) or {}; conn.execute('''INSERT INTO preferences(user_id,goal,hours,wake,sleep,available,weekdays,level,updated_at) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET goal=excluded.goal,hours=excluded.hours,wake=excluded.wake,sleep=excluded.sleep,available=excluded.available,weekdays=excluded.weekdays,level=excluded.level,updated_at=excluded.updated_at''',(session['user_id'],data.get('goal',''),float(data.get('hours',2)),data.get('wake','06:30'),data.get('sleep','23:00'),data.get('available',''),data.get('weekdays','Monday,Tuesday,Wednesday,Thursday,Friday,Saturday,Sunday'),data.get('level','Beginner'),datetime.utcnow().isoformat())); conn.commit(); r=conn.execute('SELECT * FROM preferences WHERE user_id=?',(session['user_id'],)).fetchone(); conn.close(); return jsonify(dict(r))

PHASES=['Phase 1','Phase 2','Phase 3']

def fallback_plan(p):
    goal=p.get('goal') or 'career development'; level=p.get('level') or 'Beginner'; hrs=float(p.get('hours') or 2); days=[x.strip() for x in (p.get('weekdays') or 'Monday,Tuesday,Wednesday,Thursday,Friday,Saturday,Sunday').split(',') if x.strip()]; skills=['LinkedIn & profile','GitHub','Portfolio','Resume','Python / core skill','SQL / technical skill','Excel & Power BI','Project work','Interview preparation']; tasks=[]
    for i,day in enumerate(days[:7]):
        tasks.append({'day':day,'tasks':[{'title':skills[i%len(skills)],'time':'18:00','duration':max(30,int(hrs*60)),'phase':PHASES[min(i//3,2)],'reason':f'Build {goal} skills at {level} level.'}]})
    return {'title':f'{goal.title()} Career Plan','summary':f'A practical weekly plan for a {level} learner with about {hrs:g} hours per study day.','days':tasks,'advice':['Review your progress weekly.','Keep one portfolio project active.','Adjust task duration when your schedule changes.']}

@app.post('/api/ai/schedule')
@login_required
def ai_schedule():
    data=request.get_json(silent=True) or {}; p={**data};
    if not p.get('goal') or not p.get('hours'):
        conn=db(); r=conn.execute('SELECT * FROM preferences WHERE user_id=?',(session['user_id'],)).fetchone(); conn.close(); p={**(dict(r) if r else {}),**p}
    key=os.getenv('OPENAI_API_KEY')
    if not key: return jsonify({'plan':fallback_plan(p),'source':'local'})
    try:
        from openai import OpenAI
        client=OpenAI(api_key=key); model=os.getenv('OPENAI_MODEL','gpt-5-mini')
        prompt=f'''Create a realistic weekly career schedule as JSON. User requirements: {json.dumps(p)}. Return only JSON with title, summary, days (array of {{day,tasks:[{{title,time,duration,phase,reason}}]}}), advice (array). Respect available time, level, preferred weekdays and constraints.''' 
        resp=client.responses.create(model=model,input=prompt)
        text=resp.output_text.strip(); plan=json.loads(text); return jsonify({'plan':plan,'source':'openai'})
    except Exception as e:
        return jsonify({'plan':fallback_plan(p),'source':'local','warning':'AI service unavailable; generated a local plan.'})

@app.errorhandler(404)
def not_found(e): return jsonify({'error':'Not found'}),404

init_db()
if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.getenv('PORT','5000')),debug=os.getenv('FLASK_DEBUG','0')=='1')
