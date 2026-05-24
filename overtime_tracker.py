"""
╔══════════════════════════════════════════════╗
║         OVERTIME TRACKER  — v2.0             ║
║  Light theme · SQLite via worksuite_db       ║
╚══════════════════════════════════════════════╝
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv
import sys
import calendar
from datetime import datetime, date
from pathlib import Path

if getattr(sys, "frozen", False):
    BASE = Path(sys.executable).parent
else:
    BASE = Path(__file__).parent

sys.path.insert(0, str(BASE))
from worksuite_db import WorkSuiteDB, get_palette

OVERWORK_MULTIPLIER = 1.2
OVERTIME_MULTIPLIER = 1.4

# ─── Dynamic Color Palette ────────────────────────────────────────────────────
C = get_palette()

MONTHS = ["All", "January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]
MONTH_NAMES = ["January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]


# ─── Calendar Popup ───────────────────────────────────────────────────────────
class CalendarPopup(tk.Toplevel):
    def __init__(self, parent, initial_date=None, callback=None):
        super().__init__(parent)
        self.callback = callback
        self.overrideredirect(True)
        self.configure(bg=C["border"])
        self.resizable(False, False)
        if initial_date:
            try: self._cur = datetime.strptime(initial_date, "%Y-%m-%d").date()
            except: self._cur = date.today()
        else:
            self._cur = date.today()
        self._view_year = self._cur.year
        self._view_month = self._cur.month
        self._build()
        self._position(parent)
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()
        self.focus_set()
        self.bind("<ButtonPress>", self._on_click)

    def _on_click(self, event):
        self.update_idletasks()
        x, y = self.winfo_rootx(), self.winfo_rooty()
        w, h = self.winfo_width(), self.winfo_height()
        if not (x <= event.x_root <= x + w and y <= event.y_root <= y + h):
            self.destroy()

    def _position(self, parent):
        self.update_idletasks()
        x = parent.winfo_rootx()
        y = parent.winfo_rooty() + parent.winfo_height() + 2
        self.geometry(f"+{x}+{y}")

    def _build(self):
        for w in self.winfo_children(): w.destroy()
        outer = tk.Frame(self, bg=C["surface"], highlightthickness=1, highlightbackground=C["border"])
        outer.pack(padx=1, pady=1)
        nav = tk.Frame(outer, bg=C["card"])
        nav.pack(fill="x")
        tk.Button(nav, text="◀", font=("Inter", 10, "bold"), bg=C["card"], fg=C["accent"],
                  relief="flat", cursor="hand2", bd=0, padx=10, pady=6,
                  command=self._prev_month).pack(side="left")
        self._header_lbl = tk.Label(nav, text=f"{MONTH_NAMES[self._view_month-1]}  {self._view_year}",
                                     font=("Inter", 10, "bold"), bg=C["card"], fg=C["text"])
        self._header_lbl.pack(side="left", expand=True)
        tk.Button(nav, text="▶", font=("Inter", 10, "bold"), bg=C["card"], fg=C["accent"],
                  relief="flat", cursor="hand2", bd=0, padx=10, pady=6,
                  command=self._next_month).pack(side="right")
        days_frame = tk.Frame(outer, bg=C["surface"])
        days_frame.pack(fill="x", padx=6, pady=(6, 0))
        for i, d in enumerate(["Mo","Tu","We","Th","Fr","Sa","Su"]):
            clr = C["danger"] if i >= 5 else C["muted"]
            tk.Label(days_frame, text=d, font=("Inter", 8, "bold"),
                     bg=C["surface"], fg=clr, width=4).grid(row=0, column=i, pady=(0, 4))
        grid = tk.Frame(outer, bg=C["surface"])
        grid.pack(padx=6, pady=(0, 8))
        cal = calendar.monthcalendar(self._view_year, self._view_month)
        today = date.today()
        for r, week in enumerate(cal):
            for c, day in enumerate(week):
                if day == 0:
                    tk.Label(grid, text="", width=4, bg=C["surface"]).grid(row=r, column=c)
                    continue
                d = date(self._view_year, self._view_month, day)
                is_today = (d == today)
                is_selected = (d == self._cur)
                if is_selected: bg, fg = C["accent"], C["white"]
                elif is_today: bg, fg = C["hover"], C["accent"]
                else: bg, fg = C["surface"], (C["danger"] if c >= 5 else C["text"])
                btn = tk.Button(grid, text=str(day), width=4, font=("Inter", 9),
                                bg=bg, fg=fg, relief="flat", cursor="hand2",
                                command=lambda _d=d: self._select(_d))
                btn.grid(row=r, column=c, padx=1, pady=1, ipady=3)
        tk.Button(outer, text="Today", font=("Inter", 8), bg=C["card"], fg=C["muted"],
                  relief="flat", cursor="hand2", pady=4,
                  command=lambda: self._select(date.today())).pack(fill="x")

    def _prev_month(self):
        if self._view_month == 1: self._view_month, self._view_year = 12, self._view_year - 1
        else: self._view_month -= 1
        self._build()

    def _next_month(self):
        if self._view_month == 12: self._view_month, self._view_year = 1, self._view_year + 1
        else: self._view_month += 1
        self._build()

    def _select(self, d):
        self._cur = d
        if self.callback: self.callback(d.strftime("%Y-%m-%d"))
        self.destroy()


class DateEntry(tk.Frame):
    def __init__(self, parent, initial="", **kw):
        super().__init__(parent, bg=kw.pop("frame_bg", C["surface"]))
        self._var = tk.StringVar(value=initial)
        self.entry = tk.Entry(self, textvariable=self._var, font=("Inter", 10),
                              bg=C["card"], fg=C["text"], insertbackground=C["text"],
                              relief="flat", width=14, highlightthickness=1,
                              highlightbackground=C["border"], highlightcolor=C["accent"])
        self.entry.pack(side="left", ipady=5)
        tk.Button(self, text="📅", font=("Inter", 10), bg=C["border"], fg=C["text"],
                  relief="flat", cursor="hand2", bd=0, padx=6, pady=4,
                  command=self._open_cal).pack(side="left", padx=(2, 0))

    def _open_cal(self):
        CalendarPopup(self.entry, initial_date=self._var.get(), callback=self._set_date)

    def _set_date(self, ds): self._var.set(ds)
    def get(self): return self._var.get()


# ═══════════════════════════════════════════════════════════════════════════════
class OvertimeTracker(tk.Tk):
    def __init__(self):
        super().__init__()
        self.db = WorkSuiteDB()
        self.title("Overtime Tracker")
        self.geometry("1000x700")
        self.minsize(900, 620)
        self.configure(bg=C["bg"])
        self._setup_styles()
        self._build_ui()
        self.update_dashboard()

    def _setup_styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TNotebook", background=C["bg"], borderwidth=0)
        s.configure("TNotebook.Tab", background=C["card"], foreground=C["muted"],
                    padding=[20, 10], font=("Inter", 10, "bold"), borderwidth=0, focuscolor=C["bg"])
        s.map("TNotebook.Tab", background=[("selected", C["white"])], foreground=[("selected", C["accent"])])
        s.configure("Treeview", background=C["surface"], foreground=C["text"],
                    fieldbackground=C["surface"], rowheight=34,
                    font=("Inter", 10), borderwidth=0)
        s.configure("Treeview.Heading", background=C["border"], foreground=C["muted"],
                    font=("Inter", 9, "bold"), relief="flat")
        s.map("Treeview", background=[("selected", C["accent"])], foreground=[("selected", C["white"])])

    def _build_ui(self):
        hdr = tk.Frame(self, bg=C["surface"], height=58)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="⏱  Overtime Tracker", font=("Inter", 15, "bold"),
                 bg=C["surface"], fg=C["text"]).pack(side="left", padx=24, pady=12)
        self.header_rate_var = tk.StringVar()
        self._update_header_rate()
        tk.Label(hdr, textvariable=self.header_rate_var, font=("Inter", 9),
                 bg=C["surface"], fg=C["muted"]).pack(side="right", padx=24)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        self.tab_dash = tk.Frame(nb, bg=C["bg"])
        self.tab_log = tk.Frame(nb, bg=C["bg"])
        self.tab_hist = tk.Frame(nb, bg=C["bg"])
        self.tab_set = tk.Frame(nb, bg=C["bg"])

        nb.add(self.tab_dash, text="  📊  Dashboard  ")
        nb.add(self.tab_log, text="  ➕  Log Hours  ")
        nb.add(self.tab_hist, text="  📋  History    ")
        nb.add(self.tab_set, text="  ⚙️  Settings   ")

        self._build_dashboard(self.tab_dash)
        self._build_log(self.tab_log)
        self._build_history(self.tab_hist)
        self._build_settings(self.tab_set)

    def _update_header_rate(self):
        rate = self.db.get_hourly_rate()
        self.header_rate_var.set(f"Current Rate: €{rate:.2f}/hr")

    # ── Dashboard ─────────────────────────────────────────────────────────
    def _build_dashboard(self, parent):
        self.dash_pad = tk.Frame(parent, bg=C["bg"])
        self.dash_pad.pack(fill="both", expand=True, padx=30, pady=24)

    def update_dashboard(self):
        for w in self.dash_pad.winfo_children(): w.destroy()

        entries = self.db.get_overtime_entries()
        now = datetime.now()

        total_ow_h = sum(e["hours"] for e in entries if e["type"] == "overwork")
        total_ot_h = sum(e["hours"] for e in entries if e["type"] == "overtime")
        total_ow_e = sum(e["pay"] for e in entries if e["type"] == "overwork")
        total_ot_e = sum(e["pay"] for e in entries if e["type"] == "overtime")
        total_hours = total_ow_h + total_ot_h
        total_earn = total_ow_e + total_ot_e

        month_entries = [e for e in entries if e["date"].startswith(f"{now.year}-{now.month:02d}")]
        month_earn = sum(e["pay"] for e in month_entries)
        month_hrs = sum(e["hours"] for e in month_entries)

        tk.Label(self.dash_pad, text="Overview", font=("Inter", 14, "bold"),
                 bg=C["bg"], fg=C["text"]).pack(anchor="w", pady=(0, 16))

        cards = tk.Frame(self.dash_pad, bg=C["bg"])
        cards.pack(fill="x")
        for i, (lbl, val, clr) in enumerate([
            ("Total Earned", f"€{total_earn:,.2f}", C["success"]),
            ("Total Hours", f"{total_hours:.1f} h", C["accent"]),
            (f"{now.strftime('%B')} Earned", f"€{month_earn:,.2f}", C["warning"]),
            (f"{now.strftime('%B')} Hours", f"{month_hrs:.1f} h", C["accent2"]),
        ]):
            card = tk.Frame(cards, bg=C["surface"], highlightthickness=1, highlightbackground=C["border"])
            card.grid(row=0, column=i, padx=6, pady=4, sticky="ew", ipadx=12, ipady=10)
            cards.columnconfigure(i, weight=1)
            tk.Frame(card, bg=clr, height=3).pack(fill="x")
            tk.Label(card, text=lbl, font=("Inter", 9), bg=C["surface"], fg=C["muted"]).pack(anchor="w", padx=12, pady=(10, 2))
            tk.Label(card, text=val, font=("Inter", 18, "bold"), bg=C["surface"], fg=clr).pack(anchor="w", padx=12, pady=(0, 10))

        # Breakdown
        bk = tk.Frame(self.dash_pad, bg=C["surface"], highlightthickness=1, highlightbackground=C["border"])
        bk.pack(fill="x", pady=(16, 0))
        tk.Label(bk, text="  Breakdown by Type", font=("Inter", 10, "bold"),
                 bg=C["surface"], fg=C["text"]).pack(anchor="w", padx=12, pady=(10, 6))
        row = tk.Frame(bk, bg=C["surface"])
        row.pack(fill="x", padx=12, pady=(0, 12))
        for lbl, hrs, earn, clr in [("Overwork (×1.2)", total_ow_h, total_ow_e, C["overwork"]),
                                     ("Overtime (×1.4)", total_ot_h, total_ot_e, C["overtime"])]:
            col = tk.Frame(row, bg=C["card"], highlightthickness=1, highlightbackground=C["border"])
            col.pack(side="left", expand=True, fill="x", padx=6, ipadx=10, ipady=8)
            tk.Label(col, text=f"● {lbl}", font=("Inter", 9, "bold"), bg=C["card"], fg=clr).pack(anchor="w", padx=10, pady=(6, 0))
            tk.Label(col, text=f"€{earn:,.2f}  ·  {hrs:.1f} h", font=("Inter", 10), bg=C["card"], fg=C["text"]).pack(anchor="w", padx=10, pady=(0, 6))

        # Recent entries
        rec = tk.Frame(self.dash_pad, bg=C["surface"],
                        highlightthickness=1, highlightbackground=C["border"])
        rec.pack(fill="both", expand=True, pady=(16, 0))

        tk.Label(rec, text="  Recent Entries", font=("Inter", 10, "bold"),
                 bg=C["surface"], fg=C["text"]).pack(anchor="w", padx=14, pady=(12, 4))

        recent = sorted(entries, key=lambda e: e["date"], reverse=True)[:6]
        if not recent:
            tk.Label(rec, text="No entries yet — go to 'Log Hours' to add some!",
                     font=("Inter", 9), bg=C["surface"], fg=C["muted"]).pack(pady=20)
        else:
            for e in recent:
                color = C["overwork"] if e["type"] == "overwork" else C["overtime"]
                paid_icon = "✔" if e.get("paid") else "◌"
                row = tk.Frame(rec, bg=C["surface"])
                row.pack(fill="x", padx=14, pady=3)
                tk.Label(row, text=paid_icon, font=("Inter", 9),
                         bg=C["surface"], fg=C["success"] if e.get("paid") else C["muted"]
                         ).pack(side="left", padx=(0, 6))
                tk.Label(row, text=e["date"], font=("Inter", 9),
                         bg=C["surface"], fg=C["muted"], width=10, anchor="w").pack(side="left")
                tk.Label(row, text=e["type"].title(), font=("Inter", 9, "bold"),
                         bg=C["surface"], fg=color, width=9, anchor="w").pack(side="left")
                tk.Label(row, text=f"{e['hours']:.1f} h", font=("Inter", 9),
                         bg=C["surface"], fg=C["text"], width=6, anchor="w").pack(side="left")
                tk.Label(row, text=f"€{e['pay']:.2f}", font=("Inter", 9, "bold"),
                         bg=C["surface"], fg=C["success"], width=8, anchor="w").pack(side="left")
                if e.get("note"):
                    tk.Label(row, text=f"— {e['note'][:35]}", font=("Inter", 8),
                             bg=C["surface"], fg=C["muted"]).pack(side="left", padx=(4, 0))
        tk.Frame(rec, bg=C["surface"], height=10).pack()

        self.refresh_history()

    # ── Log Hours ─────────────────────────────────────────────────────────
    def _build_log(self, parent):
        center = tk.Frame(parent, bg=C["bg"])
        center.place(relx=0.5, rely=0.5, anchor="center")
        card = tk.Frame(center, bg=C["surface"], highlightthickness=1, highlightbackground=C["border"])
        card.pack(ipadx=40, ipady=30)

        tk.Label(card, text="Log New Hours", font=("Inter", 14, "bold"),
                 bg=C["surface"], fg=C["text"]).grid(row=0, column=0, columnspan=2, pady=(0, 24), sticky="w")

        tk.Label(card, text="Date", font=("Inter", 9), bg=C["surface"], fg=C["muted"]).grid(row=1, column=0, sticky="w", pady=6, padx=(0, 20))
        self.date_entry = DateEntry(card, initial=date.today().strftime("%Y-%m-%d"), frame_bg=C["surface"])
        self.date_entry.grid(row=1, column=1, pady=6, padx=4, sticky="w")

        for i, (lbl, attr) in enumerate([("Hours Worked", "hours_entry"), ("Note (optional)", "note_entry")], start=2):
            tk.Label(card, text=lbl, font=("Inter", 9), bg=C["surface"], fg=C["muted"]).grid(row=i, column=0, sticky="w", pady=6, padx=(0, 20))
            e = tk.Entry(card, font=("Inter", 10), bg=C["card"], fg=C["text"],
                         insertbackground=C["text"], relief="flat", width=26,
                         highlightthickness=1, highlightbackground=C["border"], highlightcolor=C["accent"])
            e.grid(row=i, column=1, pady=6, ipady=6, padx=4)
            setattr(self, attr, e)

        info_frame = tk.Frame(card, bg=C["border"])
        info_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 4), ipady=8)
        tk.Label(info_frame, text="  ℹ  Auto-split: 1st hour → Overwork (×1.2)  ·  rest → Overtime (×1.4)",
                 font=("Inter", 8), bg=C["border"], fg=C["muted"]).pack(anchor="w", padx=8)

        self.preview_var = tk.StringVar(value="")
        tk.Label(card, textvariable=self.preview_var, font=("Inter", 9),
                 bg=C["surface"], fg=C["success"], justify="left").grid(row=5, column=0, columnspan=2, pady=(8, 0), sticky="w")
        self.hours_entry.bind("<KeyRelease>", self._update_preview)

        btn = tk.Button(card, text="  +  Add Entry  ", font=("Inter", 10, "bold"),
                        bg=C["accent"], fg=C["white"], relief="flat", cursor="hand2",
                        padx=16, pady=10, command=self.submit_entry)
        btn.grid(row=6, column=0, columnspan=2, pady=(16, 0), sticky="ew")

    def _split_hours(self, total):
        if total <= 0: return 0.0, 0.0
        return min(1.0, total), max(0.0, total - 1.0)

    def _update_preview(self, *_):
        try:
            hours = float(self.hours_entry.get())
            if hours <= 0: raise ValueError
            rate = self.db.get_hourly_rate()
            ow_h, ot_h = self._split_hours(hours)
            ow_pay = round(ow_h * rate * OVERWORK_MULTIPLIER, 2)
            ot_pay = round(ot_h * rate * OVERTIME_MULTIPLIER, 2)
            total = round(ow_pay + ot_pay, 2)
            lines = [f"  ● Overwork  {ow_h:.1f}h × €{rate:.2f} × 1.2  =  €{ow_pay:.2f}"]
            if ot_h > 0: lines.append(f"  ● Overtime  {ot_h:.1f}h × €{rate:.2f} × 1.4  =  €{ot_pay:.2f}")
            lines.append(f"  Total Pay:  €{total:.2f}")
            self.preview_var.set("\n".join(lines))
        except ValueError:
            self.preview_var.set("")

    def submit_entry(self):
        raw_date = self.date_entry.get().strip()
        raw_hours = self.hours_entry.get().strip()
        note = self.note_entry.get().strip()
        try: datetime.strptime(raw_date, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Invalid Date", "Use YYYY-MM-DD")
            return
        try:
            hours = float(raw_hours)
            if hours <= 0: raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Hours", "Enter a positive number.")
            return

        rate = self.db.get_hourly_rate()
        ow_h, ot_h = self._split_hours(hours)
        now_id = datetime.now().strftime("%Y%m%d%H%M%S%f")

        self.db.add_overtime_entry({
            "id": now_id + "_ow", "date": raw_date, "type": "overwork",
            "hours": ow_h, "rate": rate, "mult": OVERWORK_MULTIPLIER,
            "pay": round(ow_h * rate * OVERWORK_MULTIPLIER, 4), "note": note})

        if ot_h > 0:
            self.db.add_overtime_entry({
                "id": now_id + "_ot", "date": raw_date, "type": "overtime",
                "hours": ot_h, "rate": rate, "mult": OVERTIME_MULTIPLIER,
                "pay": round(ot_h * rate * OVERTIME_MULTIPLIER, 4), "note": note})

        self.hours_entry.delete(0, "end")
        self.note_entry.delete(0, "end")
        self.date_entry.entry.delete(0, "end")
        self.date_entry.entry.insert(0, date.today().strftime("%Y-%m-%d"))
        self.preview_var.set(f"  ✓  Logged {hours}h")
        self.update_dashboard()

    # ── History ───────────────────────────────────────────────────────────
    def _build_history(self, parent):
        top = tk.Frame(parent, bg=C["bg"])
        top.pack(fill="x", padx=20, pady=(16, 8))
        tk.Label(top, text="History", font=("Inter", 13, "bold"),
                 bg=C["bg"], fg=C["text"]).pack(side="left")

        filter_outer = tk.Frame(top, bg=C["bg"])
        filter_outer.pack(side="right")

        row1 = tk.Frame(filter_outer, bg=C["bg"])
        row1.pack(anchor="e", pady=(0, 4))

        for lbl, attr, vals, default, w in [
            ("Month:", "filter_month", MONTHS, "All", 11),
            ("Year:", "filter_year", ["All"] + [str(y) for y in range(2020, datetime.now().year + 2)], str(datetime.now().year), 7),
            ("Type:", "filter_type", ["All", "Overwork", "Overtime"], "All", 9),
            ("Status:", "filter_paid", ["All", "Paid", "Unpaid"], "All", 8),
        ]:
            tk.Label(row1, text=lbl, font=("Inter", 9), bg=C["bg"], fg=C["muted"]).pack(side="left", padx=(8, 4))
            cb = ttk.Combobox(row1, values=vals, width=w, state="readonly", font=("Inter", 9))
            cb.set(default)
            cb.pack(side="left", padx=2)
            setattr(self, attr, cb)

        row2 = tk.Frame(filter_outer, bg=C["bg"])
        row2.pack(anchor="e")
        tk.Label(row2, text="From:", font=("Inter", 9), bg=C["bg"], fg=C["muted"]).pack(side="left", padx=(0, 4))
        self.filter_date_from = DateEntry(row2, initial="", frame_bg=C["bg"])
        self.filter_date_from.pack(side="left", padx=4)
        tk.Label(row2, text="To:", font=("Inter", 9), bg=C["bg"], fg=C["muted"]).pack(side="left", padx=(8, 4))
        self.filter_date_to = DateEntry(row2, initial="", frame_bg=C["bg"])
        self.filter_date_to.pack(side="left", padx=4)
        tk.Button(row2, text="Apply", font=("Inter", 9, "bold"),
                  bg=C["accent"], fg=C["white"], relief="flat", cursor="hand2", padx=10, pady=4,
                  command=self.refresh_history).pack(side="left", padx=(8, 0))

        tree_frame = tk.Frame(parent, bg=C["bg"])
        tree_frame.pack(fill="both", expand=True, padx=20, pady=4)

        cols = ("status", "date", "type", "hours", "rate", "mult", "pay", "note")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="extended")
        for col, (label, w) in zip(cols, [("Status", 80), ("Date", 100), ("Type", 90), ("Hours", 70),
                                           ("Rate €/h", 80), ("Mult", 70), ("Pay €", 90), ("Note", 180)]):
            self.tree.heading(col, text=label)
            self.tree.column(col, width=w, anchor="center")
        self.tree.column("note", anchor="w")
        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.tag_configure("overwork", foreground=C["overwork"])
        self.tree.tag_configure("overtime", foreground=C["overtime"])
        self.tree.bind("<Double-1>", self._on_tree_double_click)

        bot = tk.Frame(parent, bg=C["surface"])
        bot.pack(fill="x", side="bottom")

        sr = tk.Frame(bot, bg=C["surface"])
        sr.pack(fill="x", padx=14, pady=(8, 4))
        self.pill_paid = tk.Label(sr, text="", font=("Inter", 9, "bold"), bg=C["success"], fg=C["white"], padx=10, pady=4)
        self.pill_paid.pack(side="left", padx=(0, 6))
        self.pill_unpaid = tk.Label(sr, text="", font=("Inter", 9, "bold"), bg=C["warning"], fg=C["white"], padx=10, pady=4)
        self.pill_unpaid.pack(side="left", padx=(0, 6))
        self.pill_total = tk.Label(sr, text="", font=("Inter", 9), bg=C["surface"], fg=C["muted"])
        self.pill_total.pack(side="left", padx=(4, 0))

        ar = tk.Frame(bot, bg=C["surface"])
        ar.pack(fill="x", padx=14, pady=(0, 8))
        tk.Label(ar, text="Double-click to toggle paid/unpaid", font=("Inter", 8), bg=C["surface"], fg=C["border"]).pack(side="left")
        for txt, clr, cmd in [
            ("🗑  Delete", C["danger"], self.delete_entry),
            ("📤  Export CSV", C["border"], self.export_csv),
            ("✓  Mark Paid", C["success"], lambda: self._set_paid(True)),
            ("✕  Mark Unpaid", C["warning"], lambda: self._set_paid(False)),
        ]:
            tk.Button(ar, text=txt, font=("Inter", 9, "bold"), bg=clr, fg=C["white"] if clr != C["border"] else C["text"],
                      relief="flat", cursor="hand2", padx=10, pady=3, command=cmd).pack(side="right", padx=3)

    def _filtered_entries(self):
        entries = self.db.get_overtime_entries()
        month_sel = self.filter_month.get()
        year_sel = self.filter_year.get()
        type_sel = self.filter_type.get().lower()
        paid_sel = self.filter_paid.get().lower()
        raw_from = self.filter_date_from.get().strip()
        raw_to = self.filter_date_to.get().strip()

        date_from = date_to = None
        if raw_from:
            try: date_from = datetime.strptime(raw_from, "%Y-%m-%d").date()
            except: pass
        if raw_to:
            try: date_to = datetime.strptime(raw_to, "%Y-%m-%d").date()
            except: pass
        use_range = date_from is not None or date_to is not None

        result = []
        for e in entries:
            try: d = datetime.strptime(e["date"], "%Y-%m-%d").date()
            except: continue
            if use_range:
                if date_from and d < date_from: continue
                if date_to and d > date_to: continue
            else:
                if month_sel != "All" and d.month != MONTHS.index(month_sel): continue
                if year_sel != "All" and d.year != int(year_sel): continue
            if type_sel != "all" and e["type"] != type_sel: continue
            if paid_sel == "paid" and not e.get("paid"): continue
            if paid_sel == "unpaid" and e.get("paid"): continue
            result.append(e)
        return result

    def refresh_history(self):
        for row in self.tree.get_children(): self.tree.delete(row)
        entries = sorted(self._filtered_entries(), key=lambda e: e["date"], reverse=True)
        paid_pay = unpaid_pay = total_hrs = 0.0
        for e in entries:
            is_paid = bool(e.get("paid"))
            status_icon = "✔ Paid" if is_paid else "◌ Unpaid"
            self.tree.insert("", "end", iid=e["id"], tags=(e["type"],),
                             values=(status_icon, e["date"], e["type"].title(),
                                     f"{e['hours']:.2f}", f"€{e['rate']:.2f}",
                                     f"×{e['mult']}", f"€{e['pay']:.2f}", e.get("note", "")))
            total_hrs += e["hours"]
            if is_paid: paid_pay += e["pay"]
            else: unpaid_pay += e["pay"]
        self.pill_paid.config(text=f"✔ Paid €{paid_pay:,.2f}")
        self.pill_unpaid.config(text=f"◌ Unpaid €{unpaid_pay:,.2f}")
        self.pill_total.config(text=f"  {len(entries)} entries · {total_hrs:.1f}h · €{paid_pay+unpaid_pay:,.2f} total")

    def _on_tree_double_click(self, event):
        sel = self.tree.selection()
        if not sel: return
        ids = list(sel)
        first = next((e for e in self.db.get_overtime_entries() if e["id"] == ids[0]), None)
        new_state = not bool(first.get("paid")) if first else True
        self.db.set_overtime_paid(ids, new_state)
        self.refresh_history()

    def _set_paid(self, val):
        sel = self.tree.selection()
        if not sel: messagebox.showinfo("No Selection", "Select one or more entries."); return
        self.db.set_overtime_paid(list(sel), val)
        self.refresh_history()

    def delete_entry(self):
        sel = self.tree.selection()
        if not sel: messagebox.showinfo("No Selection", "Select entries to delete."); return
        if not messagebox.askyesno("Confirm", f"Delete {len(sel)} entries permanently?"): return
        self.db.delete_overtime_entries(list(sel))
        self.refresh_history()
        self.update_dashboard()

    def export_csv(self):
        entries = self._filtered_entries()
        if not entries: messagebox.showinfo("No Data", "No entries to export."); return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path: return
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["date", "type", "hours", "rate", "mult", "pay", "note", "paid"])
            w.writeheader(); w.writerows(entries)
        messagebox.showinfo("Exported", f"Saved {len(entries)} entries.")

    # ── Settings ──────────────────────────────────────────────────────────
    def _build_settings(self, parent):
        center = tk.Frame(parent, bg=C["bg"])
        center.place(relx=0.5, rely=0.4, anchor="center")
        card = tk.Frame(center, bg=C["surface"], highlightthickness=1, highlightbackground=C["border"])
        card.pack(ipadx=40, ipady=30)

        tk.Label(card, text="Settings", font=("Inter", 14, "bold"),
                 bg=C["surface"], fg=C["text"]).grid(row=0, column=0, columnspan=2, pady=(0, 24), sticky="w")

        tk.Label(card, text="Hourly Rate (€)", font=("Inter", 9),
                 bg=C["surface"], fg=C["muted"]).grid(row=1, column=0, sticky="w", pady=6, padx=(0, 20))
        self.rate_entry = tk.Entry(card, font=("Inter", 12, "bold"),
                                   bg=C["card"], fg=C["success"], insertbackground=C["text"],
                                   relief="flat", width=16, highlightthickness=1,
                                   highlightbackground=C["border"], highlightcolor=C["accent"])
        self.rate_entry.insert(0, f"{self.db.get_hourly_rate():.2f}")
        self.rate_entry.grid(row=1, column=1, pady=6, ipady=8, padx=4)

        tk.Label(card, text="⚠ Changing rate only affects NEW entries.\n  Historical entries keep their original rate.",
                 font=("Inter", 8), bg=C["surface"], fg=C["warning"], justify="left"
                 ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 16))

        for i, (lbl, mult, clr) in enumerate([("Overwork", "×1.2", C["overwork"]),
                                                ("Overtime", "×1.4", C["overtime"])], start=3):
            tk.Label(card, text=f"  ● {lbl}", font=("Inter", 10, "bold"),
                     bg=C["surface"], fg=clr).grid(row=i, column=0, sticky="w", pady=4)
            tk.Label(card, text=mult, font=("Inter", 10),
                     bg=C["surface"], fg=C["text"]).grid(row=i, column=1, sticky="w", pady=4)

        btn = tk.Button(card, text="  💾  Save Rate  ", font=("Inter", 10, "bold"),
                        bg=C["success"], fg=C["white"], relief="flat", cursor="hand2",
                        padx=16, pady=10, command=self.save_rate)
        btn.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(12, 0))

        self.rate_status = tk.Label(card, text="", font=("Inter", 9), bg=C["surface"], fg=C["success"])
        self.rate_status.grid(row=6, column=0, columnspan=2, pady=(10, 0))

    def save_rate(self):
        try:
            rate = float(self.rate_entry.get())
            if rate <= 0: raise ValueError
        except ValueError:
            messagebox.showerror("Invalid", "Enter a valid positive rate."); return
        self.db.set_hourly_rate(rate)
        self.rate_status.config(text=f"✓ Rate updated to €{rate:.2f}/hr")
        self._update_header_rate()


if __name__ == "__main__":
    app = OvertimeTracker()
    app.protocol("WM_DELETE_WINDOW", lambda: (app.db.close(), app.destroy()))
    app.mainloop()
