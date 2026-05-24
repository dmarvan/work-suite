"""
╔══════════════════════════════════════════════╗
║         PAYSLIP TRACKER  — v2.0              ║
║  Light theme · SQLite · Bonus categories     ║
╚══════════════════════════════════════════════╝
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv
import sys
from datetime import datetime, date
from pathlib import Path

if getattr(sys, "frozen", False):
    BASE = Path(sys.executable).parent
else:
    BASE = Path(__file__).parent

sys.path.insert(0, str(BASE))
from worksuite_db import WorkSuiteDB, get_palette

# ─── Dynamic Color Palette ────────────────────────────────────────────────────
C = get_palette()

MONTH_NAMES = ["January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]

CATEGORIES = [
    ("salary",          "Monthly Salary"),
    ("easter_bonus",    "Easter Bonus"),
    ("christmas_bonus", "Christmas Bonus"),
    ("summer_bonus",    "Summer Bonus"),
]

CAT_LABELS = {k: v for k, v in CATEGORIES}
CAT_COLORS = {
    "salary": C["salary"],
    "easter_bonus": C["warning"],
    "christmas_bonus": C["danger"],
    "summer_bonus": C["accent"],
}


class PayslipTracker(tk.Tk):
    def __init__(self):
        super().__init__()
        self.db = WorkSuiteDB()
        self.title("Payslip Tracker")
        self.geometry("1000x700")
        self.minsize(900, 600)
        self.configure(bg=C["bg"])
        self._setup_styles()
        self._build_ui()
        self.refresh_all()

    def _setup_styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TNotebook", background=C["bg"], borderwidth=0)
        s.configure("TNotebook.Tab", background=C["card"], foreground=C["muted"],
                    padding=[20, 10], font=("Inter", 10, "bold"), borderwidth=0,
                    focuscolor=C["bg"])
        s.map("TNotebook.Tab", background=[("selected", C["white"])],
              foreground=[("selected", C["accent"])])
        s.configure("Treeview", background=C["surface"], foreground=C["text"],
                    fieldbackground=C["surface"], rowheight=34,
                    font=("Inter", 10), borderwidth=0)
        s.configure("Treeview.Heading", background=C["border"], foreground=C["muted"],
                    font=("Inter", 9, "bold"), relief="flat")
        s.map("Treeview", background=[("selected", C["accent"])],
              foreground=[("selected", C["white"])])

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg=C["surface"], height=58)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="💶  Payslip Tracker", font=("Inter", 15, "bold"),
                 bg=C["surface"], fg=C["text"]).pack(side="left", padx=24, pady=12)
        self.hdr_summary = tk.Label(hdr, text="", font=("Inter", 9),
                                     bg=C["surface"], fg=C["muted"])
        self.hdr_summary.pack(side="right", padx=24)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        self.tab_dash = tk.Frame(nb, bg=C["bg"])
        self.tab_log = tk.Frame(nb, bg=C["bg"])
        self.tab_hist = tk.Frame(nb, bg=C["bg"])

        nb.add(self.tab_dash, text="  📊  Dashboard  ")
        nb.add(self.tab_log, text="  ➕  Log Payslip  ")
        nb.add(self.tab_hist, text="  📋  History    ")

        self._build_dashboard(self.tab_dash)
        self._build_log(self.tab_log)
        self._build_history(self.tab_hist)

    # ══════════════════════════════════════════════════════════════════════
    #  DASHBOARD
    # ══════════════════════════════════════════════════════════════════════
    def _build_dashboard(self, parent):
        self.dash_frame = tk.Frame(parent, bg=C["bg"])
        self.dash_frame.pack(fill="both", expand=True, padx=30, pady=24)

    def _refresh_dashboard(self):
        for w in self.dash_frame.winfo_children():
            w.destroy()

        entries = self.db.get_payslip_entries()
        now = datetime.now()
        year = now.year

        year_entries = [e for e in entries if e["year"] == year]
        salary_entries = [e for e in year_entries if e["category"] == "salary"]
        bonus_entries = [e for e in year_entries if e["category"] != "salary"]

        total_salary = sum(e["salary"] for e in salary_entries)
        total_ot = sum(e["overtime"] for e in salary_entries)
        total_gross = sum(e["gross"] for e in year_entries)
        total_bonus_gross = sum(e["gross"] for e in bonus_entries)

        hdr_row = tk.Frame(self.dash_frame, bg=C["bg"])
        hdr_row.pack(fill="x", pady=(0, 16))
        tk.Label(hdr_row, text=f"{year} Overview",
                 font=("Inter", 14, "bold"),
                 bg=C["bg"], fg=C["text"]).pack(side="left")
        tk.Button(hdr_row, text="  ↻  Refresh  ",
                  font=("Inter", 8, "bold"),
                  bg=C["border"], fg=C["text"], relief="flat",
                  cursor="hand2", padx=8, pady=3,
                  command=self.refresh_all).pack(side="right")

        # Summary cards
        cards = tk.Frame(self.dash_frame, bg=C["bg"])
        cards.pack(fill="x")
        for i, (lbl, val, clr) in enumerate([
            ("Total Gross", f"€{total_gross:,.2f}", C["success"]),
            ("Total Salary", f"€{total_salary:,.2f}", C["accent"]),
            ("Total Overtime", f"€{total_ot:,.2f}", C["overtime"]),
            ("Total Bonuses", f"€{total_bonus_gross:,.2f}", C["bonus"]),
        ]):
            card = tk.Frame(cards, bg=C["surface"],
                            highlightthickness=1, highlightbackground=C["border"])
            card.grid(row=0, column=i, padx=6, pady=4, sticky="ew", ipadx=12, ipady=10)
            cards.columnconfigure(i, weight=1)
            tk.Frame(card, bg=clr, height=3).pack(fill="x")
            tk.Label(card, text=lbl, font=("Inter", 9),
                     bg=C["surface"], fg=C["muted"]).pack(anchor="w", padx=12, pady=(10, 2))
            tk.Label(card, text=val, font=("Inter", 18, "bold"),
                     bg=C["surface"], fg=clr).pack(anchor="w", padx=12, pady=(0, 10))

        # Monthly table
        table_frame = tk.Frame(self.dash_frame, bg=C["surface"],
                                highlightthickness=1, highlightbackground=C["border"])
        table_frame.pack(fill="x", pady=(16, 0))

        tk.Label(table_frame, text=f"  Monthly Breakdown — {year}",
                 font=("Inter", 10, "bold"),
                 bg=C["surface"], fg=C["text"]).pack(anchor="w", padx=12, pady=(10, 8))

        # Table header
        header_row = tk.Frame(table_frame, bg=C["border"])
        header_row.pack(fill="x", padx=12)
        headers = ["Month", "Salary", "Overtime", "Gross"]
        widths = [120, 100, 100, 100]
        for h, w in zip(headers, widths):
            tk.Label(header_row, text=h, font=("Inter", 9, "bold"),
                     bg=C["border"], fg=C["muted"], width=w // 8,
                     anchor="w").pack(side="left", padx=6, pady=5)

        # Table rows (only salary entries)
        for m in range(1, 13):
            entry = next((e for e in salary_entries if e["month"] == m), None)
            row_bg = C["card"] if m % 2 == 0 else C["surface"]
            row = tk.Frame(table_frame, bg=row_bg)
            row.pack(fill="x", padx=12)

            is_future = m > now.month
            fg = C["muted"] if is_future and not entry else C["text"]

            tk.Label(row, text=MONTH_NAMES[m - 1], font=("Inter", 9),
                     bg=row_bg, fg=fg, width=15, anchor="w").pack(side="left", padx=6, pady=4)

            if entry:
                tk.Label(row, text=f"€{entry['salary']:,.2f}", font=("Inter", 9),
                         bg=row_bg, fg=C["salary"], width=12, anchor="w").pack(side="left", padx=6)
                tk.Label(row, text=f"€{entry['overtime']:,.2f}", font=("Inter", 9),
                         bg=row_bg, fg=C["overtime"], width=12, anchor="w").pack(side="left", padx=6)
                tk.Label(row, text=f"€{entry['gross']:,.2f}", font=("Inter", 9, "bold"),
                         bg=row_bg, fg=C["text"], width=12, anchor="w").pack(side="left", padx=6)
            else:
                tk.Label(row, text="—", font=("Inter", 9),
                         bg=row_bg, fg=C["border"], width=36, anchor="w").pack(side="left", padx=6)

        # Bonus section
        if bonus_entries:
            tk.Label(table_frame, text="  Bonuses",
                     font=("Inter", 10, "bold"),
                     bg=C["surface"], fg=C["bonus"]).pack(anchor="w", padx=12, pady=(12, 4))

            for e in bonus_entries:
                row = tk.Frame(table_frame, bg=C["card"])
                row.pack(fill="x", padx=12, pady=1)
                cat_label = CAT_LABELS.get(e["category"], e["category"])
                tk.Label(row, text=f"  {cat_label} ({MONTH_NAMES[e['month']-1]})",
                         font=("Inter", 9, "bold"),
                         bg=C["card"], fg=CAT_COLORS.get(e["category"], C["text"]),
                         width=25, anchor="w").pack(side="left", padx=6, pady=4)
                tk.Label(row, text=f"€{e['gross']:,.2f}",
                         font=("Inter", 9, "bold"),
                         bg=C["card"], fg=C["text"]).pack(side="left", padx=6)

        tk.Frame(table_frame, bg=C["surface"], height=10).pack()

    # ══════════════════════════════════════════════════════════════════════
    #  LOG PAYSLIP
    # ══════════════════════════════════════════════════════════════════════
    def _build_log(self, parent):
        center = tk.Frame(parent, bg=C["bg"])
        center.place(relx=0.5, rely=0.5, anchor="center")

        card = tk.Frame(center, bg=C["surface"],
                        highlightthickness=1, highlightbackground=C["border"])
        card.pack(ipadx=40, ipady=30)

        tk.Label(card, text="Log Payslip", font=("Inter", 14, "bold"),
                 bg=C["surface"], fg=C["text"]).grid(row=0, column=0, columnspan=2,
                                                       pady=(0, 24), sticky="w")

        # Category
        tk.Label(card, text="Category", font=("Inter", 9),
                 bg=C["surface"], fg=C["muted"]).grid(row=1, column=0, sticky="w", pady=6, padx=(0, 20))
        self.cat_var = tk.StringVar(value="salary")
        cat_cb = ttk.Combobox(card, textvariable=self.cat_var,
                               values=[k for k, v in CATEGORIES],
                               width=22, state="readonly", font=("Inter", 10))
        cat_cb.grid(row=1, column=1, pady=6, padx=4, sticky="w")

        # Category display label
        self.cat_display = tk.Label(card, text="Monthly Salary", font=("Inter", 8),
                                     bg=C["surface"], fg=C["accent"])
        self.cat_display.grid(row=1, column=1, pady=6, padx=(200, 0), sticky="w")
        cat_cb.bind("<<ComboboxSelected>>",
                    lambda e: self.cat_display.config(text=CAT_LABELS.get(self.cat_var.get(), "")))

        # Month & Year
        tk.Label(card, text="Month", font=("Inter", 9),
                 bg=C["surface"], fg=C["muted"]).grid(row=2, column=0, sticky="w", pady=6, padx=(0, 20))
        month_frame = tk.Frame(card, bg=C["surface"])
        month_frame.grid(row=2, column=1, pady=6, padx=4, sticky="w")

        self.month_cb = ttk.Combobox(month_frame, values=MONTH_NAMES, width=12,
                                      state="readonly", font=("Inter", 10))
        self.month_cb.set(MONTH_NAMES[datetime.now().month - 1])
        self.month_cb.pack(side="left", padx=(0, 8))

        tk.Label(month_frame, text="Year", font=("Inter", 9),
                 bg=C["surface"], fg=C["muted"]).pack(side="left", padx=(0, 6))
        self.year_cb = ttk.Combobox(month_frame,
                                     values=[str(y) for y in range(2020, datetime.now().year + 3)],
                                     width=6, state="readonly", font=("Inter", 10))
        self.year_cb.set(str(datetime.now().year))
        self.year_cb.pack(side="left")

        # Salary, Overtime
        for i, (lbl, attr) in enumerate([
            ("Base Amount (€)", "salary_entry"),
            ("Overtime (€)", "overtime_entry"),
        ], start=3):
            tk.Label(card, text=lbl, font=("Inter", 9),
                     bg=C["surface"], fg=C["muted"]).grid(row=i, column=0, sticky="w", pady=6, padx=(0, 20))
            e = tk.Entry(card, font=("Inter", 10),
                         bg=C["card"], fg=C["text"],
                         insertbackground=C["text"], relief="flat", width=26,
                         highlightthickness=1, highlightbackground=C["border"],
                         highlightcolor=C["accent"])
            e.grid(row=i, column=1, pady=6, ipady=6, padx=4)
            setattr(self, attr, e)

        # Note
        tk.Label(card, text="Note (optional)", font=("Inter", 9),
                 bg=C["surface"], fg=C["muted"]).grid(row=5, column=0, sticky="w", pady=6, padx=(0, 20))
        self.note_entry = tk.Entry(card, font=("Inter", 10),
                                    bg=C["card"], fg=C["text"],
                                    insertbackground=C["text"], relief="flat", width=26,
                                    highlightthickness=1, highlightbackground=C["border"],
                                    highlightcolor=C["accent"])
        self.note_entry.grid(row=5, column=1, pady=6, ipady=6, padx=4)

        # Auto-calculate gross
        self.gross_lbl = tk.Label(card, text="Gross: —", font=("Inter", 10, "bold"),
                                   bg=C["surface"], fg=C["success"])
        self.gross_lbl.grid(row=6, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.salary_entry.bind("<KeyRelease>", self._update_gross_preview)
        self.overtime_entry.bind("<KeyRelease>", self._update_gross_preview)

        btn = tk.Button(card, text="  +  Save Payslip  ",
                        font=("Inter", 10, "bold"),
                        bg=C["success"], fg=C["white"], relief="flat",
                        cursor="hand2", padx=16, pady=10,
                        command=self.submit_payslip)
        btn.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(16, 0))

        self.log_status = tk.Label(card, text="", font=("Inter", 9),
                                    bg=C["surface"], fg=C["success"])
        self.log_status.grid(row=8, column=0, columnspan=2, pady=(10, 0))

    def _update_gross_preview(self, *_):
        try:
            sal = float(self.salary_entry.get() or 0)
            ot = float(self.overtime_entry.get() or 0)
            self.gross_lbl.config(text=f"Gross: €{sal + ot:,.2f}")
        except ValueError:
            self.gross_lbl.config(text="Gross: —")

    def submit_payslip(self):
        cat = self.cat_var.get()
        month_name = self.month_cb.get()
        year_str = self.year_cb.get()

        if month_name not in MONTH_NAMES:
            messagebox.showerror("Invalid", "Select a valid month.")
            return
        month = MONTH_NAMES.index(month_name) + 1
        try:
            year = int(year_str)
        except ValueError:
            messagebox.showerror("Invalid", "Select a valid year.")
            return

        try:
            sal = float(self.salary_entry.get() or 0)
            ot = float(self.overtime_entry.get() or 0)
        except ValueError:
            messagebox.showerror("Invalid", "Enter valid amounts.")
            return

        gross = round(sal + ot, 2)
        note = self.note_entry.get().strip()

        entry_id = f"{year}-{month:02d}-{cat}"

        # Check for duplicates
        existing = self.db.get_payslip_entries()
        dup = next((e for e in existing
                     if e["year"] == year and e["month"] == month and e["category"] == cat), None)
        if dup:
            cat_label = CAT_LABELS.get(cat, cat)
            if not messagebox.askyesno("Duplicate",
                f"A {cat_label} entry for {month_name} {year} already exists.\n"
                f"Existing: €{dup['gross']:,.2f}\n\nReplace it?"):
                return

        self.db.save_payslip({
            "id": entry_id, "month": month, "year": year,
            "category": cat, "salary": sal, "overtime": ot,
            "gross": gross, "note": note,
            "logged": date.today().strftime("%Y-%m-%d"),
        })

        self.salary_entry.delete(0, "end")
        self.overtime_entry.delete(0, "end")
        self.note_entry.delete(0, "end")
        self.gross_lbl.config(text="Gross: —")
        self.log_status.config(text=f"✓  Saved {CAT_LABELS.get(cat, cat)} for {month_name} {year}")
        self.refresh_all()

    # ══════════════════════════════════════════════════════════════════════
    #  HISTORY
    # ══════════════════════════════════════════════════════════════════════
    def _build_history(self, parent):
        top = tk.Frame(parent, bg=C["bg"])
        top.pack(fill="x", padx=20, pady=(16, 8))
        tk.Label(top, text="History", font=("Inter", 13, "bold"),
                 bg=C["bg"], fg=C["text"]).pack(side="left")

        filter_row = tk.Frame(top, bg=C["bg"])
        filter_row.pack(side="right")

        tk.Label(filter_row, text="Year:", font=("Inter", 9),
                 bg=C["bg"], fg=C["muted"]).pack(side="left", padx=(0, 4))
        self.filter_year = ttk.Combobox(filter_row,
            values=["All"] + [str(y) for y in range(2020, datetime.now().year + 3)],
            width=7, state="readonly", font=("Inter", 9))
        self.filter_year.set(str(datetime.now().year))
        self.filter_year.pack(side="left", padx=4)

        tk.Label(filter_row, text="Category:", font=("Inter", 9),
                 bg=C["bg"], fg=C["muted"]).pack(side="left", padx=(12, 4))
        self.filter_cat = ttk.Combobox(filter_row,
            values=["All"] + [v for _, v in CATEGORIES],
            width=16, state="readonly", font=("Inter", 9))
        self.filter_cat.set("All")
        self.filter_cat.pack(side="left", padx=4)

        tk.Button(filter_row, text="Apply", font=("Inter", 9, "bold"),
                  bg=C["accent"], fg=C["white"], relief="flat",
                  cursor="hand2", padx=10, pady=4,
                  command=self.refresh_history).pack(side="left", padx=(8, 0))

        # Treeview
        tree_frame = tk.Frame(parent, bg=C["bg"])
        tree_frame.pack(fill="both", expand=True, padx=20, pady=4)

        cols = ("month", "year", "category", "salary", "overtime", "gross", "note", "logged")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="extended")
        for col, (label, w) in zip(cols, [
            ("Month", 90), ("Year", 60), ("Category", 130),
            ("Salary €", 90), ("Overtime €", 90), ("Gross €", 100),
            ("Note", 160), ("Logged", 90)
        ]):
            self.tree.heading(col, text=label)
            self.tree.column(col, width=w, anchor="center")
        self.tree.column("note", anchor="w")

        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.tree.tag_configure("salary", foreground=C["salary"])
        self.tree.tag_configure("easter_bonus", foreground=C["bonus"])
        self.tree.tag_configure("christmas_bonus", foreground=C["danger"])
        self.tree.tag_configure("summer_bonus", foreground=C["accent"])

        # Bottom bar
        bot = tk.Frame(parent, bg=C["surface"])
        bot.pack(fill="x", side="bottom")

        sr = tk.Frame(bot, bg=C["surface"])
        sr.pack(fill="x", padx=14, pady=(8, 4))
        self.pill_salary = tk.Label(sr, text="", font=("Inter", 9, "bold"),
                                     bg=C["salary"], fg=C["white"], padx=10, pady=4)
        self.pill_salary.pack(side="left", padx=(0, 6))
        self.pill_ot = tk.Label(sr, text="", font=("Inter", 9, "bold"),
                                 bg=C["overtime"], fg=C["white"], padx=10, pady=4)
        self.pill_ot.pack(side="left", padx=(0, 6))
        self.pill_gross = tk.Label(sr, text="", font=("Inter", 9, "bold"),
                                    bg=C["accent"], fg=C["white"], padx=10, pady=4)
        self.pill_gross.pack(side="left")

        ar = tk.Frame(bot, bg=C["surface"])
        ar.pack(fill="x", padx=14, pady=(0, 8))

        for txt, clr, cmd in [
            ("🗑  Delete", C["danger"], self.delete_selected),
            ("📤  Export CSV", C["border"], self.export_csv),
        ]:
            tk.Button(ar, text=txt, font=("Inter", 9, "bold"),
                      bg=clr, fg=C["white"] if clr != C["border"] else C["text"],
                      relief="flat", cursor="hand2", padx=10, pady=3,
                      command=cmd).pack(side="right", padx=3)

    def _filtered_entries(self):
        entries = self.db.get_payslip_entries()
        year_sel = self.filter_year.get()
        cat_sel = self.filter_cat.get()

        result = []
        for e in entries:
            if year_sel != "All" and e["year"] != int(year_sel):
                continue
            if cat_sel != "All":
                cat_key = next((k for k, v in CATEGORIES if v == cat_sel), None)
                if cat_key and e["category"] != cat_key:
                    continue
            result.append(e)
        return result

    def refresh_history(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        entries = self._filtered_entries()
        total_sal = total_ot = total_gross = 0.0

        for e in entries:
            cat_label = CAT_LABELS.get(e["category"], e["category"])
            self.tree.insert("", "end", iid=e["id"],
                             tags=(e["category"],),
                             values=(
                                 MONTH_NAMES[e["month"] - 1],
                                 e["year"],
                                 cat_label,
                                 f"€{e['salary']:,.2f}",
                                 f"€{e['overtime']:,.2f}",
                                 f"€{e['gross']:,.2f}",
                                 e.get("note", ""),
                                 e.get("logged", ""),
                             ))
            total_sal += e["salary"]
            total_ot += e["overtime"]
            total_gross += e["gross"]

        self.pill_salary.config(text=f"Salary €{total_sal:,.2f}")
        self.pill_ot.config(text=f"Overtime €{total_ot:,.2f}")
        self.pill_gross.config(text=f"Gross €{total_gross:,.2f}")

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("No Selection", "Select entries to delete.")
            return
        if not messagebox.askyesno("Confirm", f"Delete {len(sel)} entries permanently?"):
            return
        self.db.delete_payslip_entries(list(sel))
        self.refresh_all()

    def export_csv(self):
        entries = self._filtered_entries()
        if not entries:
            messagebox.showinfo("No Data", "No entries to export.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["month", "year", "category", "salary", "overtime", "gross", "note", "logged"])
            w.writeheader()
            w.writerows(entries)
        messagebox.showinfo("Exported", f"Saved {len(entries)} entries.")

    # ══════════════════════════════════════════════════════════════════════
    #  REFRESH
    # ══════════════════════════════════════════════════════════════════════
    def refresh_all(self):
        entries = self.db.get_payslip_entries()
        year = datetime.now().year
        year_gross = sum(e["gross"] for e in entries if e["year"] == year)
        count = len([e for e in entries if e["year"] == year])
        self.hdr_summary.config(text=f"{year}: {count} entries · €{year_gross:,.2f} gross")
        self._refresh_dashboard()
        self.refresh_history()


if __name__ == "__main__":
    app = PayslipTracker()
    app.protocol("WM_DELETE_WINDOW", lambda: (app.db.close(), app.destroy()))
    app.mainloop()
