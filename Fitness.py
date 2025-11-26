
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3
import os
import json
import math
import datetime
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from io import BytesIO
from PIL import Image
import base64
import secrets
import hashlib

# Try to import FPDF for PDF export
try:
    from fpdf import FPDF
    HAS_FPDF = True
except Exception:
    HAS_FPDF = False

DB_FILE = "fitness_tracker.db"
GRAPH_DIR = "graphs"
if not os.path.exists(GRAPH_DIR):
    os.makedirs(GRAPH_DIR, exist_ok=True)

SALT_BYTES = 16
HASH_ITERS = 200_000
HASH_NAME = 'sha256'

def make_salt():
    return secrets.token_bytes(SALT_BYTES)

def hash_password(password: str, salt: bytes) -> str:
    dk = hashlib.pbkdf2_hmac(HASH_NAME, password.encode('utf-8'), salt, HASH_ITERS)
    return base64.b64encode(salt + dk).decode('utf-8')

def verify_password(stored_hash: str, password_attempt: str) -> bool:
    try:
        raw = base64.b64decode(stored_hash.encode('utf-8'))
        salt = raw[:SALT_BYTES]
        stored_dk = raw[SALT_BYTES:]
        attempt_dk = hashlib.pbkdf2_hmac(HASH_NAME, password_attempt.encode('utf-8'), salt, HASH_ITERS)
        return secrets.compare_digest(stored_dk, attempt_dk)
    except Exception:
        return False

class DB:
    def __init__(self, path=DB_FILE):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        cur = self.conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                age INTEGER,
                height_cm REAL,
                weight_kg REAL,
                security_q TEXT,
                security_a_hash TEXT
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS daily (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                date TEXT,
                sleep_hrs REAL,
                weight REAL,
                calories REAL,
                steps INTEGER,
                note TEXT,
                FOREIGN KEY(username) REFERENCES users(username)
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS goals (
                username TEXT PRIMARY KEY,
                weight_goal REAL,
                steps_goal INTEGER,
                calories_goal REAL,
                sleep_goal REAL,
                FOREIGN KEY(username) REFERENCES users(username)
            )
        ''')
        self.conn.commit()

    def create_user(self, username, password_hash, age=None, height=None, weight=None, security_q=None, security_a_hash=None):
        cur = self.conn.cursor()
        cur.execute('INSERT INTO users (username, password_hash, age, height_cm, weight_kg, security_q, security_a_hash) VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (username, password_hash, age, height, weight, security_q, security_a_hash))
        self.conn.commit()

    def get_user(self, username):
        cur = self.conn.cursor()
        cur.execute('SELECT * FROM users WHERE username = ?', (username,))
        return cur.fetchone()

    def update_user_info(self, username, age=None, height=None, weight=None):
        cur = self.conn.cursor()
        cur.execute('UPDATE users SET age = ?, height_cm = ?, weight_kg = ? WHERE username = ?', (age, height, weight, username))
        self.conn.commit()

    def set_password(self, username, password_hash):
        cur = self.conn.cursor()
        cur.execute('UPDATE users SET password_hash = ? WHERE username = ?', (password_hash, username))
        self.conn.commit()

    # daily data
    def add_daily(self, username, date_str, sleep, weight, calories, steps, note=None):
        cur = self.conn.cursor()
        cur.execute('INSERT INTO daily (username, date, sleep_hrs, weight, calories, steps, note) VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (username, date_str, sleep, weight, calories, steps, note))
        self.conn.commit()

    def get_daily_range(self, username, start_date=None, end_date=None):
        cur = self.conn.cursor()
        q = 'SELECT date, sleep_hrs, weight, calories, steps FROM daily WHERE username = ?'
        params = [username]
        if start_date:
            q += ' AND date >= ?'
            params.append(start_date)
        if end_date:
            q += ' AND date <= ?'
            params.append(end_date)
        q += ' ORDER BY date'
        cur.execute(q, tuple(params))
        return cur.fetchall()

    def get_last_n_days(self, username, n=30):
        cur = self.conn.cursor()
        cur.execute('SELECT date, sleep_hrs, weight, calories, steps FROM daily WHERE username = ? ORDER BY date DESC LIMIT ?', (username, n))
        rows = cur.fetchall()
        return list(reversed(rows))

    # goals
    def upsert_goals(self, username, weight_goal=None, steps_goal=None, calories_goal=None, sleep_goal=None):
        cur = self.conn.cursor()
        cur.execute('SELECT username FROM goals WHERE username = ?', (username,))
        if cur.fetchone():
            cur.execute('UPDATE goals SET weight_goal = ?, steps_goal = ?, calories_goal = ?, sleep_goal = ? WHERE username = ?',
                        (weight_goal, steps_goal, calories_goal, sleep_goal, username))
        else:
            cur.execute('INSERT INTO goals (username, weight_goal, steps_goal, calories_goal, sleep_goal) VALUES (?, ?, ?, ?, ?)',
                        (username, weight_goal, steps_goal, calories_goal, sleep_goal))
        self.conn.commit()

    def get_goals(self, username):
        cur = self.conn.cursor()
        cur.execute('SELECT * FROM goals WHERE username = ?', (username,))
        return cur.fetchone()


def calc_bmi(weight_kg, height_cm):
    try:
        h = height_cm / 100.0
        bmi = weight_kg / (h*h)
        return round(bmi, 2)
    except Exception:
        return None

def bmi_category(bmi):
    if bmi is None:
        return 'Unknown'
    if bmi < 18.5:
        return 'Underweight'
    if bmi < 25:
        return 'Normal'
    if bmi < 30:
        return 'Overweight'
    return 'Obese'

def calc_bmr(weight, height_cm, age, sex='male'):
    try:
        if sex == 'male':
            bmr = 10*weight + 6.25*height_cm - 5*age + 5
        else:
            bmr = 10*weight + 6.25*height_cm - 5*age - 161
        return round(bmr, 1)
    except Exception:
        return None


def save_graphs_to_png(figures, base_name_prefix):
    paths = []
    for i, fig in enumerate(figures):
        path = os.path.join(GRAPH_DIR, f"{base_name_prefix}_{i+1}.png")
        fig.savefig(path, bbox_inches='tight')
        paths.append(path)
    return paths

def export_report_pdf(username, user_row, analytics_summary, figures, filename=None):
    if filename is None:
        filename = f"{username}_report_{datetime.date.today().isoformat()}.pdf"

    png_paths = save_graphs_to_png(figures, f"{username}_report")

    if HAS_FPDF:
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 10, f"Fitness Report - {username}", ln=True)
        pdf.ln(4)

        pdf.set_font('Arial', '', 12)
        pdf.cell(0, 8, f"Generated: {datetime.datetime.now().isoformat(sep=' ', timespec='seconds')}", ln=True)
        pdf.cell(0, 8, f"Age: {user_row['age']}, Height: {user_row['height_cm']} cm, Weight: {user_row['weight_kg']} kg", ln=True)
        pdf.ln(6)

        pdf.set_font('Arial', 'B', 14)
        pdf.cell(0, 8, 'Summary:', ln=True)
        pdf.set_font('Arial', '', 12)
        for k, v in analytics_summary.items():
            pdf.multi_cell(0, 7, f"- {k}: {v}")

        for p in png_paths:
            pdf.add_page()
            pdf.image(p, x=10, y=20, w=pdf.w - 20)

        pdf.output(filename)
        return filename
    else:
        
        return png_paths[0] if png_paths else None

class FitnessApp:
    def __init__(self, master):
        self.master = master
        self.master.title('Fitness Tracker')
        self.db = DB()
        self.current_user = None
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self._build_login()

    def _build_login(self):
        for widget in self.master.winfo_children():
            widget.destroy()

        frame = ttk.Frame(self.master, padding=20)
        frame.pack(expand=True)

        ttk.Label(frame, text='Welcome to Fitness Tracker', font=('Helvetica', 16, 'bold')).grid(row=0, column=0, columnspan=2, pady=(0,10))

        ttk.Label(frame, text='Username:').grid(row=1, column=0, sticky='e')
        self.login_user = ttk.Entry(frame)
        self.login_user.grid(row=1, column=1)

        ttk.Label(frame, text='Password:').grid(row=2, column=0, sticky='e')
        self.login_pass = ttk.Entry(frame, show='*')
        self.login_pass.grid(row=2, column=1)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=10)

        ttk.Button(btn_frame, text='Login', command=self.login).grid(row=0, column=0, padx=5)
        ttk.Button(btn_frame, text='Signup', command=self._open_signup).grid(row=0, column=1, padx=5)
        ttk.Button(btn_frame, text='Forgot Password', command=self._forgot_password).grid(row=0, column=2, padx=5)

    def _open_signup(self):
        self.signup_win = tk.Toplevel(self.master)
        self.signup_win.title('Signup')

        f = ttk.Frame(self.signup_win, padding=10)
        f.pack()

        ttk.Label(f, text='Choose a username:').grid(row=0, column=0, sticky='e')
        self.su_user = ttk.Entry(f)
        self.su_user.grid(row=0, column=1)

        ttk.Label(f, text='Password:').grid(row=1, column=0, sticky='e')
        self.su_pass = ttk.Entry(f, show='*')
        self.su_pass.grid(row=1, column=1)

        ttk.Label(f, text='Age:').grid(row=2, column=0, sticky='e')
        self.su_age = ttk.Entry(f)
        self.su_age.grid(row=2, column=1)

        ttk.Label(f, text='Height (cm):').grid(row=3, column=0, sticky='e')
        self.su_height = ttk.Entry(f)
        self.su_height.grid(row=3, column=1)

        ttk.Label(f, text='Weight (kg):').grid(row=4, column=0, sticky='e')
        self.su_weight = ttk.Entry(f)
        self.su_weight.grid(row=4, column=1)

        ttk.Label(f, text='Security Question (for password reset)').grid(row=5, column=0, columnspan=2)
        ttk.Label(f, text='(e.g. What is your pet name?)').grid(row=6, column=0, columnspan=2)
        self.su_sec_q = ttk.Entry(f)
        self.su_sec_q.grid(row=7, column=0, columnspan=2, sticky='ew')

        ttk.Label(f, text='Answer:').grid(row=8, column=0, sticky='e')
        self.su_sec_a = ttk.Entry(f, show='*')
        self.su_sec_a.grid(row=8, column=1)

        ttk.Button(f, text='Create Account', command=self._create_account).grid(row=9, column=0, columnspan=2, pady=8)

    def _create_account(self):
        username = self.su_user.get().strip()
        password = self.su_pass.get()
        age = self.su_age.get().strip() or None
        height = self.su_height.get().strip() or None
        weight = self.su_weight.get().strip() or None
        sec_q = self.su_sec_q.get().strip() or None
        sec_a = self.su_sec_a.get()

        if not username or not password:
            messagebox.showerror('Error', 'Username and password required')
            return

        if self.db.get_user(username):
            messagebox.showerror('Error', 'Username already exists')
            return

        salt = make_salt()
        password_hash = hash_password(password, salt)

        sec_a_hash = None
        if sec_a:
            sa_salt = make_salt()
            sec_a_hash = hash_password(sec_a, sa_salt)

        self.db.create_user(username, password_hash, age=int(age) if age else None,
                            height=float(height) if height else None,
                            weight=float(weight) if weight else None,
                            security_q=sec_q, security_a_hash=sec_a_hash)

        messagebox.showinfo('Success', 'Account created. Please login.')
        self.signup_win.destroy()

    def _forgot_password(self):
        username = simpledialog.askstring('Forgot Password', 'Enter your username:', parent=self.master)
        if not username:
            return
        user = self.db.get_user(username)
        if not user:
            messagebox.showerror('Error', 'User not found')
            return
        if not user['security_q']:
            messagebox.showerror('Error', 'No security question set. Contact admin (not implemented).')
            return
        answer = simpledialog.askstring('Security Question', user['security_q'], parent=self.master)
        if not answer:
            return
        if verify_password(user['security_a_hash'], answer):
            newpw = simpledialog.askstring('Reset Password', 'Enter new password:', parent=self.master)
            if newpw:
                salt = make_salt()
                ph = hash_password(newpw, salt)
                self.db.set_password(username, ph)
                messagebox.showinfo('Success', 'Password reset. Please login with new password.')
        else:
            messagebox.showerror('Error', 'Security answer did not match')

    def login(self):
        username = self.login_user.get().strip()
        password = self.login_pass.get()
        user = self.db.get_user(username)
        if not user:
            messagebox.showerror('Error', 'User not found')
            return
        if verify_password(user['password_hash'], password):
            self.current_user = username
            self.user_row = user
            self._build_main()
        else:
            messagebox.showerror('Error', 'Password incorrect')

    def _build_main(self):
        for widget in self.master.winfo_children():
            widget.destroy()

        self.master.geometry('1000x700')
        container = ttk.Frame(self.master)
        container.pack(fill='both', expand=True)

        top_frame = ttk.Frame(container)
        top_frame.pack(fill='x')

        ttk.Label(top_frame, text=f'Hello, {self.current_user}', font=('Helvetica', 14)).pack(side='left', padx=10, pady=8)
        ttk.Button(top_frame, text='Logout', command=self.logout).pack(side='right', padx=10)
        ttk.Button(top_frame, text='Export Report', command=self.export_report).pack(side='right')

        main_pane = ttk.Panedwindow(container, orient='horizontal')
        main_pane.pack(fill='both', expand=True, padx=10, pady=10)

        left = ttk.Frame(main_pane, width=320)
        main_pane.add(left, weight=1)

        ttk.Label(left, text='Quick Entry', font=('Helvetica', 12, 'bold')).pack(pady=(0,6))
        form = ttk.Frame(left)
        form.pack()

        ttk.Label(form, text='Date (YYYY-MM-DD):').grid(row=0, column=0, sticky='e')
        self.entry_date = ttk.Entry(form)
        self.entry_date.grid(row=0, column=1)
        self.entry_date.insert(0, datetime.date.today().isoformat())

        ttk.Label(form, text='Sleep (hrs):').grid(row=1, column=0, sticky='e')
        self.entry_sleep = ttk.Entry(form)
        self.entry_sleep.grid(row=1, column=1)

        ttk.Label(form, text='Weight (kg):').grid(row=2, column=0, sticky='e')
        self.entry_weight = ttk.Entry(form)
        self.entry_weight.grid(row=2, column=1)

        ttk.Label(form, text='Calories Burnt:').grid(row=3, column=0, sticky='e')
        self.entry_cal = ttk.Entry(form)
        self.entry_cal.grid(row=3, column=1)

        ttk.Label(form, text='Steps:').grid(row=4, column=0, sticky='e')
        self.entry_steps = ttk.Entry(form)
        self.entry_steps.grid(row=4, column=1)

        ttk.Button(form, text='Add Entry', command=self.add_entry).grid(row=5, column=0, columnspan=2, pady=8)

        ttk.Separator(left, orient='horizontal').pack(fill='x', pady=8)

        ttk.Label(left, text='Goals', font=('Helvetica', 12, 'bold')).pack()
        gframe = ttk.Frame(left)
        gframe.pack(pady=6)

        ttk.Label(gframe, text='Weight Goal (kg):').grid(row=0, column=0, sticky='e')
        self.goal_weight = ttk.Entry(gframe)
        self.goal_weight.grid(row=0, column=1)

        ttk.Label(gframe, text='Steps Goal:').grid(row=1, column=0, sticky='e')
        self.goal_steps = ttk.Entry(gframe)
        self.goal_steps.grid(row=1, column=1)

        ttk.Label(gframe, text='Calories Goal:').grid(row=2, column=0, sticky='e')
        self.goal_cal = ttk.Entry(gframe)
        self.goal_cal.grid(row=2, column=1)

        ttk.Label(gframe, text='Sleep Goal (hrs):').grid(row=3, column=0, sticky='e')
        self.goal_sleep = ttk.Entry(gframe)
        self.goal_sleep.grid(row=3, column=1)

        ttk.Button(gframe, text='Save Goals', command=self.save_goals).grid(row=4, column=0, columnspan=2, pady=6)

        right = ttk.Frame(main_pane)
        main_pane.add(right, weight=3)

        self.nb = ttk.Notebook(right)
        self.nb.pack(fill='both', expand=True)

        self.tab_dashboard = ttk.Frame(self.nb)
        self.tab_insights = ttk.Frame(self.nb)
        self.tab_history = ttk.Frame(self.nb)

        self.nb.add(self.tab_dashboard, text='Dashboard')
        self.nb.add(self.tab_insights, text='Insights')
        self.nb.add(self.tab_history, text='History')

        self.fig = Figure(figsize=(6,5), dpi=100)
        self.ax_sleep = self.fig.add_subplot(221)
        self.ax_weight = self.fig.add_subplot(222)
        self.ax_cal = self.fig.add_subplot(223)
        self.ax_steps = self.fig.add_subplot(224)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.tab_dashboard)
        self.canvas.get_tk_widget().pack(fill='both', expand=True)

        ttk.Button(self.tab_dashboard, text='Refresh Dashboard', command=self.refresh_dashboard).pack(pady=6)

        self.insight_text = tk.Text(self.tab_insights, height=20)
        self.insight_text.pack(fill='both', expand=True, padx=6, pady=6)
        ttk.Button(self.tab_insights, text='Refresh Insights', command=self.refresh_insights).pack()

        self.tree = ttk.Treeview(self.tab_history, columns=('date','sleep','weight','calories','steps'), show='headings')
        for c in ('date','sleep','weight','calories','steps'):
            self.tree.heading(c, text=c.capitalize())
        self.tree.pack(fill='both', expand=True)
        ttk.Button(self.tab_history, text='Refresh History', command=self.refresh_history).pack(pady=4)

        self._load_goals()
        self.refresh_dashboard()
        self.refresh_insights()
        self.refresh_history()

    def logout(self):
        self.current_user = None
        self._build_login()

    def add_entry(self):
        date_str = self.entry_date.get().strip()
        try:
            _ = datetime.date.fromisoformat(date_str)
        except Exception:
            messagebox.showerror('Error', 'Invalid date format. Use YYYY-MM-DD')
            return

        try:
            sleep = float(self.entry_sleep.get() or 0)
        except:
            sleep = None
        try:
            weight = float(self.entry_weight.get() or 0)
        except:
            weight = None
        try:
            calories = float(self.entry_cal.get() or 0)
        except:
            calories = None
        try:
            steps = int(self.entry_steps.get() or 0)
        except:
            steps = None

        self.db.add_daily(self.current_user, date_str, sleep, weight, calories, steps)
        messagebox.showinfo('Saved', 'Entry added')
        self.refresh_dashboard()
        self.refresh_insights()
        self.refresh_history()

    def save_goals(self):
        try:
            wg = float(self.goal_weight.get()) if self.goal_weight.get().strip() else None
        except:
            wg = None
        try:
            sg = int(self.goal_steps.get()) if self.goal_steps.get().strip() else None
        except:
            sg = None
        try:
            cg = float(self.goal_cal.get()) if self.goal_cal.get().strip() else None
        except:
            cg = None
        try:
            sl = float(self.goal_sleep.get()) if self.goal_sleep.get().strip() else None
        except:
            sl = None
        self.db.upsert_goals(self.current_user, wg, sg, cg, sl)
        messagebox.showinfo('Saved', 'Goals saved')
        self.refresh_insights()

    def _load_goals(self):
        g = self.db.get_goals(self.current_user)
        if g:
            self.goal_weight.delete(0, 'end'); self.goal_steps.delete(0, 'end'); self.goal_cal.delete(0, 'end'); self.goal_sleep.delete(0, 'end')
            if g['weight_goal'] is not None:
                self.goal_weight.insert(0, str(g['weight_goal']))
            if g['steps_goal'] is not None:
                self.goal_steps.insert(0, str(g['steps_goal']))
            if g['calories_goal'] is not None:
                self.goal_cal.insert(0, str(g['calories_goal']))
            if g['sleep_goal'] is not None:
                self.goal_sleep.insert(0, str(g['sleep_goal']))

    # ---------------- Dashboard / Plots ----------------
    def _make_series(self):
        rows = self.db.get_last_n_days(self.current_user, n=90)
        dates = [datetime.date.fromisoformat(r['date']) for r in rows]
        sleep = [r['sleep_hrs'] if r['sleep_hrs'] is not None else float('nan') for r in rows]
        weight = [r['weight'] if r['weight'] is not None else float('nan') for r in rows]
        calories = [r['calories'] if r['calories'] is not None else float('nan') for r in rows]
        steps = [r['steps'] if r['steps'] is not None else float('nan') for r in rows]
        return dates, sleep, weight, calories, steps

    def refresh_dashboard(self):
        dates, sleep, weight, calories, steps = self._make_series()
        self.ax_sleep.clear(); self.ax_weight.clear(); self.ax_cal.clear(); self.ax_steps.clear()

        if dates:
            x = [d.isoformat() for d in dates]
            # Sleep
            self.ax_sleep.plot(x, sleep, marker='o')
            self.ax_sleep.set_title('Sleep (hrs)')
            self.ax_sleep.tick_params(axis='x', rotation=45)

            # Weight
            self.ax_weight.plot(x, weight, marker='o')
            self.ax_weight.set_title('Weight (kg)')
            self.ax_weight.tick_params(axis='x', rotation=45)

            # Calories
            self.ax_cal.plot(x, calories, marker='o')
            self.ax_cal.set_title('Calories Burnt')
            self.ax_cal.tick_params(axis='x', rotation=45)

            # Steps
            self.ax_steps.plot(x, steps, marker='o')
            self.ax_steps.set_title('Steps')
            self.ax_steps.tick_params(axis='x', rotation=45)

        else:
            for ax in (self.ax_sleep, self.ax_weight, self.ax_cal, self.ax_steps):
                ax.text(0.5, 0.5, 'No data', ha='center')

        self.fig.tight_layout()
        self.canvas.draw()

    def refresh_insights(self):
        rows = self.db.get_last_n_days(self.current_user, n=30)
        text = []
        if not rows:
            text.append('No data to analyze')
            self.insight_text.delete('1.0', 'end'); self.insight_text.insert('1.0', '\n'.join(text)); return

        # compute averages and trends
        def numeric_avg(arr):
            s = [float(x) for x in arr if x is not None]
            return sum(s)/len(s) if s else None

        sleeps = [r['sleep_hrs'] for r in rows]
        weights = [r['weight'] for r in rows]
        cals = [r['calories'] for r in rows]
        steps = [r['steps'] for r in rows]

        avg_sleep = numeric_avg(sleeps)
        avg_weight = numeric_avg(weights)
        avg_cal = numeric_avg(cals)
        avg_steps = numeric_avg(steps)

        text.append(f'In the last {len(rows)} days:')
        if avg_sleep: text.append(f'- Average sleep: {avg_sleep:.2f} hrs')
        if avg_weight: text.append(f'- Average weight: {avg_weight:.2f} kg')
        if avg_cal: text.append(f'- Average calories burned: {avg_cal:.1f}')
        if avg_steps: text.append(f'- Average steps: {avg_steps:.0f}')

        # Goal progress
        g = self.db.get_goals(self.current_user)
        if g:
            if g['weight_goal'] and avg_weight:
                diff = avg_weight - g['weight_goal']
                text.append(f"- Weight vs goal: avg {avg_weight:.2f} kg (difference {diff:+.2f} kg)")
            if g['steps_goal'] and avg_steps:
                pct = (avg_steps / g['steps_goal'])*100 if g['steps_goal'] else None
                if pct is not None:
                    text.append(f"- Steps goal attainment (avg/day): {pct:.1f}%")
            if g['calories_goal'] and avg_cal:
                pct = (avg_cal / g['calories_goal'])*100 if g['calories_goal'] else None
                if pct is not None:
                    text.append(f"- Calorie burn goal attainment (avg/day): {pct:.1f}%")
            if g['sleep_goal'] and avg_sleep:
                pct = (avg_sleep / g['sleep_goal'])*100 if g['sleep_goal'] else None
                if pct is not None:
                    text.append(f"- Sleep goal attainment (avg/day): {pct:.1f}%")

        try:
            ws = [w for w in weights if w is not None]
            if len(ws) >= 3:
                xs = list(range(len(ws)))
                mean_x = sum(xs)/len(xs)
                mean_y = sum(ws)/len(ws)
                num = sum((xi-mean_x)*(yi-mean_y) for xi, yi in zip(xs, ws))
                den = sum((xi-mean_x)**2 for xi in xs)
                slope = num/den if den else 0
                text.append(f"- Weight trend: slope {slope:.3f} kg/day ({'losing' if slope<0 else 'gaining' if slope>0 else 'stable'})")
        except Exception:
            pass

        # BMI and BMR
        u = self.db.get_user(self.current_user)
        if u and u['height_cm'] and u['weight_kg'] and u['age']:
            bmi = calc_bmi(u['weight_kg'], u['height_cm'])
            bmr = calc_bmr(u['weight_kg'], u['height_cm'], u['age'])
            text.append(f"- BMI: {bmi} ({bmi_category(bmi)})")
            text.append(f"- Estimated BMR: {bmr} kcal/day")

        self.insight_text.delete('1.0', 'end')
        self.insight_text.insert('1.0', '\n'.join(text))

    
    def refresh_history(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        rows = self.db.get_last_n_days(self.current_user, n=365)
        for r in rows:
            self.tree.insert('', 'end', values=(r['date'], r['sleep_hrs'], r['weight'], r['calories'], r['steps']))

    
    def _gather_figures_for_report(self):
        
        dates, sleep, weight, calories, steps = self._make_series()
        figs = []
        if dates:
            # Sleep
            f1 = Figure(figsize=(8,3))
            ax = f1.add_subplot(111)
            ax.plot([d.isoformat() for d in dates], sleep, marker='o')
            ax.set_title('Sleep (hrs)')
            ax.tick_params(axis='x', rotation=45)
            figs.append(f1)

            f2 = Figure(figsize=(8,3))
            ax = f2.add_subplot(111)
            ax.plot([d.isoformat() for d in dates], weight, marker='o')
            ax.set_title('Weight (kg)')
            ax.tick_params(axis='x', rotation=45)
            figs.append(f2)

            f3 = Figure(figsize=(8,3))
            ax = f3.add_subplot(111)
            ax.plot([d.isoformat() for d in dates], calories, marker='o')
            ax.set_title('Calories Burnt')
            ax.tick_params(axis='x', rotation=45)
            figs.append(f3)

            f4 = Figure(figsize=(8,3))
            ax = f4.add_subplot(111)
            ax.plot([d.isoformat() for d in dates], steps, marker='o')
            ax.set_title('Steps')
            ax.tick_params(axis='x', rotation=45)
            figs.append(f4)
        return figs

    def export_report(self):
        figs = self._gather_figures_for_report()
        if not figs:
            messagebox.showinfo('No Data', 'No data to export')
            return
        # analytics summary
        rows = self.db.get_last_n_days(self.current_user, n=30)
        summary = {'Days analyzed': len(rows)}
        def avg(xs):
            s = [x for x in xs if x is not None]
            return sum(s)/len(s) if s else None
        sleeps = [r['sleep_hrs'] for r in rows]
        weights = [r['weight'] for r in rows]
        cals = [r['calories'] for r in rows]
        steps = [r['steps'] for r in rows]
        if avg(sleeps): summary['Average sleep (hrs)'] = f"{avg(sleeps):.2f}"
        if avg(weights): summary['Average weight (kg)'] = f"{avg(weights):.2f}"
        if avg(cals): summary['Average calories'] = f"{avg(cals):.1f}"
        if avg(steps): summary['Average steps/day'] = f"{avg(steps):.0f}"

        user_row = self.db.get_user(self.current_user)
        filename = export_report_pdf(self.current_user, user_row, summary, figs)
        if filename:
            messagebox.showinfo('Exported', f'Report saved: {filename}')
        else:
            messagebox.showerror('Error', 'Failed to export report. Is fpdf installed?')


def main():
    root = tk.Tk()
    app = FitnessApp(root)
    root.mainloop()

if __name__ == '__main__':
    main()
