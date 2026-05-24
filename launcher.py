"""
╔══════════════════════════════════════════════╗
║           WORK SUITE  — Launcher             ║
║  Unified hub with light theme                ║
╚══════════════════════════════════════════════╝
"""

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import sys
from pathlib import Path
from datetime import datetime

if getattr(sys, "frozen", False):
    BASE = Path(sys.executable).parent
else:
    BASE = Path(__file__).parent

# ─── Soft Color Palette (shared across all apps) ─────────────────────────────
sys.path.insert(0, str(BASE))
try:
    from worksuite_db import get_palette, WorkSuiteDB, PALETTES
    C = get_palette()
except Exception:
    C = {
        "bg": "#f0f1f5", "surface": "#ffffff", "card": "#f8f9fc", "border": "#dfe2ea",
        "accent": "#6c7bd8", "accent2": "#9b7ed8", "success": "#5bb98c", "warning": "#d4a03c",
        "danger": "#d4645c", "text": "#2d3142", "muted": "#7c8091", "white": "#ffffff",
        "hover": "#ebedf5", "anime": "#7b8cde", "manga": "#d89b6c", "bar_bg": "#e8eaf0",
    }


def launch_app(script_name):
    target = BASE / script_name
    if not target.exists():
        messagebox.showerror("Not Found",
            f"Could not find:\n{target}\n\nMake sure all files are in the same folder.")
        return
    if getattr(sys, "frozen", False):
        exe_name = script_name.replace(".py", ".exe")
        exe_path = BASE / exe_name
        if exe_path.exists():
            subprocess.Popen([str(exe_path)])
        else:
            messagebox.showerror("Not Found", f"Could not find {exe_name}")
    else:
        subprocess.Popen([sys.executable, str(target)])


class WorkSuiteLauncher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Work Suite")
        self.geometry("860x560")
        self.resizable(False, False)
        self.configure(bg=C["bg"])
        self._build_ui()

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg=C["surface"], height=64)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(hdr, text="⚡  Work Suite",
                 font=("Inter", 17, "bold"),
                 bg=C["surface"], fg=C["text"]).pack(side="left", padx=24, pady=14)

        tk.Label(hdr, text=datetime.now().strftime("%A, %d %B %Y"),
                 font=("Inter", 9),
                 bg=C["surface"], fg=C["muted"]).pack(side="right", padx=24)

        # Subtitle
        tk.Label(self, text="Your personal work management hub",
                 font=("Inter", 10), bg=C["bg"], fg=C["muted"]).pack(pady=(20, 2))
        tk.Label(self, text="Select an app to launch",
                 font=("Inter", 9), bg=C["bg"], fg=C["border"]).pack(pady=(0, 20))

        # App tiles
        tiles = tk.Frame(self, bg=C["bg"])
        tiles.pack(expand=True)

        apps = [
            {"icon": "⏱", "title": "Overtime\nTracker",
             "desc": "Log overwork & overtime\nTrack payments & history",
             "color": C["accent"], "script": "overtime_tracker.py"},
            {"icon": "💶", "title": "Payslip\nTracker",
             "desc": "Monthly salary & bonuses\nEaster, Christmas, Summer",
             "color": C["success"], "script": "payslip_tracker.py"},
            {"icon": "🎌", "title": "Anime &\nManga",
             "desc": "Track anime episodes\n& manga chapters",
             "color": C["anime"], "script": "animanga_tracker.py"},
        ]

        for i, app in enumerate(apps):
            self._make_tile(tiles, app, i)

        # Bottom bar
        bot = tk.Frame(self, bg=C["surface"], height=46)
        bot.pack(fill="x", side="bottom")
        bot.pack_propagate(False)

        tk.Label(bot, text=f"  Data:  {BASE / 'worksuite_data'}",
                 font=("Inter", 8), bg=C["surface"], fg=C["muted"]).pack(side="left", padx=14, pady=12)

        tk.Button(bot, text="  📖  Database Guide  ",
                  font=("Inter", 8, "bold"),
                  bg=C["accent2"], fg=C["white"], relief="flat",
                  cursor="hand2", padx=10, pady=4,
                  command=self._show_db_guide).pack(side="right", padx=(0, 14), pady=8)

        # Theme toggle
        self._theme_btn = tk.Button(bot, text="",
                  font=("Inter", 8, "bold"),
                  bg=C["border"], fg=C["text"], relief="flat",
                  cursor="hand2", padx=10, pady=4,
                  command=self._toggle_theme)
        self._theme_btn.pack(side="right", padx=(0, 6), pady=8)
        self._update_theme_btn()

    def _update_theme_btn(self):
        try:
            db = WorkSuiteDB()
            current = db.get_theme()
            db.close()
        except Exception:
            current = "light"
        label = "🎨  Switch to Gray" if current == "light" else "🎨  Switch to Light"
        self._theme_btn.config(text=f"  {label}  ")

    def _toggle_theme(self):
        try:
            db = WorkSuiteDB()
            current = db.get_theme()
            new_theme = "gray" if current == "light" else "light"
            db.set_theme(new_theme)
            db.close()
            self._update_theme_btn()
            messagebox.showinfo("Theme Changed",
                f"Theme set to '{new_theme.title()}'.\n\n"
                f"Relaunch any open apps to see the change.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not change theme:\n{e}")

    def _make_tile(self, parent, app, col):
        card = tk.Frame(parent, bg=C["surface"], width=230, height=270,
                        highlightthickness=1, highlightbackground=C["border"],
                        cursor="hand2")
        card.grid(row=0, column=col, padx=14, pady=8)
        card.pack_propagate(False)

        tk.Frame(card, bg=app["color"], height=4).pack(fill="x")

        tk.Label(card, text=app["icon"], font=("Inter", 36),
                 bg=C["surface"], fg=app["color"]).pack(pady=(14, 6))

        tk.Label(card, text=app["title"], font=("Inter", 12, "bold"),
                 bg=C["surface"], fg=C["text"], justify="center").pack()

        tk.Label(card, text=app["desc"], font=("Inter", 8),
                 bg=C["surface"], fg=C["muted"], justify="center").pack(pady=(6, 14))

        btn = tk.Button(card, text="  Open  ▶  ",
                        font=("Inter", 9, "bold"),
                        bg=app["color"], fg=C["white"], relief="flat",
                        cursor="hand2", padx=8, pady=3,
                        command=lambda s=app["script"]: launch_app(s))
        btn.pack()
        btn.bind("<Enter>", lambda e: btn.config(bg=C["accent"]))
        btn.bind("<Leave>", lambda e, c=app["color"]: btn.config(bg=c))

        for w in (card,):
            w.bind("<Button-1>", lambda e, s=app["script"]: launch_app(s))
            w.bind("<Enter>", lambda e, c=card: c.config(highlightbackground=app["color"]))
            w.bind("<Leave>", lambda e, c=card: c.config(highlightbackground=C["border"]))

    def _show_db_guide(self):
        try:
            sys.path.insert(0, str(BASE))
            from worksuite_db import WorkSuiteDB
            db = WorkSuiteDB()
            guide = db.get_schema_guide()
            db.close()
        except Exception as e:
            messagebox.showerror("Error", f"Could not load database:\n{e}")
            return

        win = tk.Toplevel(self)
        win.title("Database Guide")
        win.geometry("720x600")
        win.configure(bg=C["bg"])

        tk.Frame(win, bg=C["accent2"], height=4).pack(fill="x")

        hdr = tk.Frame(win, bg=C["surface"])
        hdr.pack(fill="x")
        tk.Label(hdr, text="  📖  Database Guide — worksuite.db",
                 font=("Inter", 13, "bold"),
                 bg=C["surface"], fg=C["text"]).pack(anchor="w", padx=16, pady=12)
        tk.Label(hdr, text=f"  Location: {guide['database']}",
                 font=("Inter", 8), bg=C["surface"], fg=C["muted"]).pack(anchor="w", padx=16, pady=(0, 8))

        # Scrollable body
        canvas = tk.Canvas(win, bg=C["bg"], highlightthickness=0)
        sb = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=C["bg"])
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw", tags="inner")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig("inner", width=e.width))

        def _mw(event):
            if event.delta:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _mw)
        win.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>") if e.widget == win else None)

        colors = [C["accent"], C["success"], C["anime"], C["manga"]]

        for i, schema in enumerate(guide["schemas"]):
            color = colors[i % len(colors)]

            s_frame = tk.Frame(inner, bg=C["surface"],
                               highlightthickness=1, highlightbackground=C["border"])
            s_frame.pack(fill="x", padx=16, pady=8)

            tk.Frame(s_frame, bg=color, height=3).pack(fill="x")
            tk.Label(s_frame, text=f"  {schema['name']}",
                     font=("Inter", 11, "bold"),
                     bg=C["surface"], fg=color).pack(anchor="w", padx=12, pady=(10, 4))

            for t in schema["tables"]:
                t_frame = tk.Frame(s_frame, bg=C["card"])
                t_frame.pack(fill="x", padx=12, pady=4)

                tk.Label(t_frame, text=f"  {t['name']}",
                         font=("Inter", 10, "bold"),
                         bg=C["card"], fg=C["text"]).pack(anchor="w", padx=8, pady=(6, 0))
                tk.Label(t_frame, text=f"  {t['desc']}",
                         font=("Inter", 8),
                         bg=C["card"], fg=C["muted"]).pack(anchor="w", padx=8)
                tk.Label(t_frame, text=f"  Columns: {t['columns']}",
                         font=("Inter", 8),
                         bg=C["card"], fg=C["muted"]).pack(anchor="w", padx=8)
                if t.get("notes"):
                    tk.Label(t_frame, text=f"  ℹ {t['notes']}",
                             font=("Inter", 7),
                             bg=C["card"], fg=C["accent2"],
                             wraplength=600, justify="left").pack(anchor="w", padx=8, pady=(0, 4))
                tk.Frame(t_frame, bg=C["card"], height=4).pack()

            tk.Label(s_frame, text="  Relationships:",
                     font=("Inter", 9, "bold"),
                     bg=C["surface"], fg=C["muted"]).pack(anchor="w", padx=12, pady=(4, 0))
            for line in schema["relationships"].split("\n"):
                tk.Label(s_frame, text=f"    {line}",
                         font=("Inter", 8),
                         bg=C["surface"], fg=C["text"]).pack(anchor="w", padx=12)
            tk.Frame(s_frame, bg=C["surface"], height=8).pack()

        # Sample queries
        q_frame = tk.Frame(inner, bg=C["surface"],
                           highlightthickness=1, highlightbackground=C["border"])
        q_frame.pack(fill="x", padx=16, pady=8)

        tk.Frame(q_frame, bg=C["accent2"], height=3).pack(fill="x")
        tk.Label(q_frame, text="  📝  Useful SQL Queries",
                 font=("Inter", 11, "bold"),
                 bg=C["surface"], fg=C["accent2"]).pack(anchor="w", padx=12, pady=(10, 8))

        for title, sql in guide["useful_queries"]:
            tk.Label(q_frame, text=f"  {title}",
                     font=("Inter", 9, "bold"),
                     bg=C["surface"], fg=C["text"]).pack(anchor="w", padx=12, pady=(4, 0))
            sql_box = tk.Text(q_frame, font=("Consolas", 9),
                              bg=C["card"], fg=C["text"],
                              relief="flat", height=sql.count("\n") + 1, width=70,
                              highlightthickness=1, highlightbackground=C["border"])
            sql_box.pack(padx=16, pady=(2, 8))
            sql_box.insert("1.0", sql)
            sql_box.config(state="disabled")

        tk.Frame(inner, bg=C["bg"], height=20).pack()


if __name__ == "__main__":
    app = WorkSuiteLauncher()
    app.mainloop()
