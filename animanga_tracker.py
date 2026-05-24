"""
╔══════════════════════════════════════════════════╗
║       ANIME & MANGA TRACKER  —  v1.0             ║
║  Franchise-based tracking with unified stats     ║
╚══════════════════════════════════════════════════╝
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import sys
import shutil
import math
import time
import threading
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime
from pathlib import Path

# ─── Paths ────────────────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    BASE = Path(sys.executable).parent
else:
    BASE = Path(__file__).parent

DATA_DIR   = BASE / "worksuite_data"
COVERS_DIR = DATA_DIR / "covers"
ANIME_FILE = DATA_DIR / "anime.json"
MANGA_FILE = DATA_DIR / "manga.json"

CACHE_DIR = DATA_DIR / "cache"

for d in (DATA_DIR, COVERS_DIR, CACHE_DIR):
    d.mkdir(parents=True, exist_ok=True)

DEFAULT_EP_DURATION = 24  # minutes


# ─── Jikan API Client ────────────────────────────────────────────────────────
JIKAN_BASE = "https://api.jikan.moe/v4"
_last_request_time = 0.0
_jikan_lock = threading.Lock()

def _jikan_get(endpoint, params=None):
    """Rate-limited GET to Jikan API. Returns parsed JSON or None."""
    global _last_request_time
    with _jikan_lock:
        elapsed = time.time() - _last_request_time
        if elapsed < 1.1:
            time.sleep(1.1 - elapsed)
        _last_request_time = time.time()

    url = f"{JIKAN_BASE}/{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AnimangaTracker/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[Jikan] Error: {e}")
        return None


def jikan_search_anime(query, limit=10):
    """Search anime by title. Returns list of results."""
    data = _jikan_get("anime", {"q": query, "limit": limit, "sfw": "true"})
    if data and "data" in data:
        return data["data"]
    return []


def jikan_search_manga(query, limit=10):
    """Search manga by title. Returns list of results."""
    data = _jikan_get("manga", {"q": query, "limit": limit, "sfw": "true"})
    if data and "data" in data:
        return data["data"]
    return []


def jikan_get_anime(mal_id):
    """Get full anime details by MAL ID."""
    cache_file = CACHE_DIR / f"anime_{mal_id}.json"
    if cache_file.exists():
        age = time.time() - cache_file.stat().st_mtime
        if age < 86400 * 7:  # 7-day cache
            with open(cache_file, "r") as f:
                return json.load(f)

    data = _jikan_get(f"anime/{mal_id}")
    if data and "data" in data:
        with open(cache_file, "w") as f:
            json.dump(data["data"], f)
        return data["data"]
    return None


def jikan_get_manga(mal_id):
    """Get full manga details by MAL ID."""
    cache_file = CACHE_DIR / f"manga_{mal_id}.json"
    if cache_file.exists():
        age = time.time() - cache_file.stat().st_mtime
        if age < 86400 * 7:
            with open(cache_file, "r") as f:
                return json.load(f)

    data = _jikan_get(f"manga/{mal_id}")
    if data and "data" in data:
        with open(cache_file, "w") as f:
            json.dump(data["data"], f)
        return data["data"]
    return None


def download_cover(url, entry_id):
    """Download cover image to covers dir. Returns local path or None."""
    if not url:
        return None
    try:
        ext = ".jpg"
        dest = COVERS_DIR / f"{entry_id}{ext}"
        req = urllib.request.Request(url, headers={"User-Agent": "AnimangaTracker/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            with open(dest, "wb") as f:
                f.write(resp.read())
        return str(dest)
    except Exception as e:
        print(f"[Cover] Download error: {e}")
        return None

# ─── Dynamic Color Palette ────────────────────────────────────────────────────
try:
    from worksuite_db import get_palette
    C = get_palette()
except Exception:
    C = {
        "bg": "#f0f1f5", "surface": "#ffffff", "card": "#f8f9fc", "border": "#dfe2ea",
        "accent": "#6c7bd8", "accent2": "#9b7ed8", "success": "#5bb98c", "warning": "#d4a03c",
        "danger": "#d4645c", "text": "#2d3142", "muted": "#7c8091", "white": "#ffffff",
        "hover": "#ebedf5", "anime": "#7b8cde", "manga": "#d89b6c", "bar_bg": "#e8eaf0",
    }

# Status colors (always derived from the active palette)
C.setdefault("watching",  C["accent"])
C.setdefault("reading",   C["accent"])
C.setdefault("completed", C.get("completed", C["success"]))
C.setdefault("on_hold",   C["warning"])
C.setdefault("dropped",   C["danger"])
C.setdefault("planned",   C["muted"])

STATUS_COLORS = {
    "Watching":      C["watching"],
    "Reading":       C["reading"],
    "Completed":     C["completed"],
    "On Hold":       C["on_hold"],
    "Dropped":       C["dropped"],
    "Plan to Watch": C["planned"],
    "Plan to Read":  C["planned"],
}

ANIME_STATUSES = ["Watching", "Completed", "On Hold", "Dropped", "Plan to Watch"]
MANGA_STATUSES = ["Reading", "Completed", "On Hold", "Dropped", "Plan to Read"]

def new_id():
    return datetime.now().strftime("%Y%m%d%H%M%S%f")



# ─── Stat Helpers ─────────────────────────────────────────────────────────────
def anime_stats(data):
    total = len(data)
    completed = sum(1 for e in data if e.get("status") == "Completed")
    watching  = sum(1 for e in data if e.get("status") == "Watching")
    on_hold   = sum(1 for e in data if e.get("status") == "On Hold")
    dropped   = sum(1 for e in data if e.get("status") == "Dropped")
    planned   = sum(1 for e in data if e.get("status") == "Plan to Watch")
    total_eps = 0
    total_min = 0
    for e in data:
        for s in e.get("seasons", []):
            watched = sum(1 for w in s.get("ep_watched", []) if w)
            total_eps += watched
            dur = s.get("ep_duration", DEFAULT_EP_DURATION)
            total_min += watched * dur
        for cat in ("movies", "ovas"):
            for item in e.get(cat, []):
                if item.get("watched"):
                    total_eps += 1
                    total_min += item.get("duration", 90 if cat == "movies" else DEFAULT_EP_DURATION)
    hours = total_min / 60
    days  = hours / 24
    return {
        "total": total, "completed": completed, "watching": watching,
        "on_hold": on_hold, "dropped": dropped, "planned": planned,
        "episodes": total_eps, "minutes": total_min, "hours": round(hours, 1),
        "days": round(days, 1),
    }

def manga_stats(data):
    total = len(data)
    completed = sum(1 for e in data if e.get("status") == "Completed")
    reading   = sum(1 for e in data if e.get("status") == "Reading")
    total_ch  = sum(e.get("chapters_read", 0) for e in data)
    est_min   = total_ch * 5  # ~5 min per chapter estimate
    return {
        "total": total, "completed": completed, "reading": reading,
        "chapters": total_ch, "hours": round(est_min / 60, 1),
    }

def franchise_ep_summary(entry):
    """Returns (watched, total) across all seasons."""
    watched = total = 0
    for s in entry.get("seasons", []):
        total   += s.get("episodes", 0)
        watched += sum(1 for w in s.get("ep_watched", []) if w)
    return watched, total


# ─── Enhanced Stat Helpers ─────────────────────────────────────────────────────
def anime_yearly_stats(data):
    """Returns {year: {episodes, minutes, entries_added, completed}} for each year."""
    years = {}
    for e in data:
        y = e.get("added", "")[:4]
        if not y or not y.isdigit():
            continue
        y = int(y)
        if y not in years:
            years[y] = {"episodes": 0, "minutes": 0, "added": 0, "completed": 0}
        years[y]["added"] += 1
        if e.get("status") == "Completed":
            years[y]["completed"] += 1
        for s in e.get("seasons", []):
            watched = sum(1 for w in s.get("ep_watched", []) if w)
            dur = s.get("ep_duration", DEFAULT_EP_DURATION)
            years[y]["episodes"] += watched
            years[y]["minutes"]  += watched * dur
        for cat in ("movies", "ovas"):
            for item in e.get(cat, []):
                if item.get("watched"):
                    years[y]["episodes"] += 1
                    years[y]["minutes"]  += item.get("duration", 90 if cat == "movies" else DEFAULT_EP_DURATION)
    return dict(sorted(years.items()))

def manga_yearly_stats(data):
    """Returns {year: {chapters, added, completed}}."""
    years = {}
    for e in data:
        y = e.get("added", "")[:4]
        if not y or not y.isdigit():
            continue
        y = int(y)
        if y not in years:
            years[y] = {"chapters": 0, "added": 0, "completed": 0}
        years[y]["added"] += 1
        years[y]["chapters"] += e.get("chapters_read", 0)
        if e.get("status") == "Completed":
            years[y]["completed"] += 1
    return dict(sorted(years.items()))

def score_distribution(data):
    """Returns list of 10 buckets [0-9, 10-19, ..., 90-100] with counts."""
    buckets = [0] * 10
    for e in data:
        s = e.get("score")
        if s is not None:
            idx = min(s // 10, 9)
            buckets[idx] += 1
    return buckets

def top_rated(data, n=10):
    """Returns top n entries by score."""
    scored = [e for e in data if e.get("score") is not None]
    scored.sort(key=lambda e: e["score"], reverse=True)
    return scored[:n]

def average_score(data):
    scored = [e["score"] for e in data if e.get("score") is not None]
    if not scored:
        return 0
    return round(sum(scored) / len(scored), 1)

def completion_rate(data, completed_status="Completed"):
    total = len(data)
    if total == 0:
        return 0
    done = sum(1 for e in data if e.get("status") == completed_status)
    return round(done / total * 100, 1)


# ─── Scrollable Frame ─────────────────────────────────────────────────────────
class ScrollableFrame(tk.Frame):
    """Robust scrollable frame that works on Windows, macOS, and Linux."""

    # Class-level stack to track which scrollable is active
    _active_stack = []

    def __init__(self, parent, bg_color=None, **kw):
        super().__init__(parent, **kw)
        self._bg = bg_color or C["bg"]
        self.canvas = tk.Canvas(self, bg=self._bg, highlightthickness=0, bd=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=self._bg)

        self.inner.bind("<Configure>", self._on_inner_configure)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.canvas.bind("<Configure>", self._on_canvas_resize)

        # Bind on ALL children recursively using bind_class workaround
        self.canvas.bind("<Enter>", self._activate)
        self.canvas.bind("<Leave>", self._deactivate)
        self.inner.bind("<Enter>", self._activate)

        # Also bind directly on this frame
        self.bind("<Enter>", self._activate)
        self.bind("<Leave>", self._deactivate)

    def _on_inner_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_resize(self, event):
        self.canvas.itemconfig(self._window, width=event.width)

    def _on_mousewheel(self, event):
        # Don't scroll if content fits on screen
        bbox = self.canvas.bbox("all")
        if bbox:
            content_h = bbox[3] - bbox[1]
            canvas_h = self.canvas.winfo_height()
            if content_h <= canvas_h:
                # Reset to top if somehow scrolled
                self.canvas.yview_moveto(0)
                return

        if event.delta:
            units = int(-1 * (event.delta / 120))
            if units == 0:
                units = -1 if event.delta > 0 else 1
            self.canvas.yview_scroll(units * 2, "units")
        elif event.num == 4:
            self.canvas.yview_scroll(-4, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(4, "units")

    def _activate(self, event=None):
        ScrollableFrame._active_stack.append(self)
        self.canvas.bind_all("<MouseWheel>", self._dispatch_scroll)
        self.canvas.bind_all("<Button-4>", self._dispatch_scroll)
        self.canvas.bind_all("<Button-5>", self._dispatch_scroll)

    def _deactivate(self, event=None):
        if self in ScrollableFrame._active_stack:
            ScrollableFrame._active_stack.remove(self)

    @staticmethod
    def _dispatch_scroll(event):
        """Route scroll event to the most recently activated scrollable."""
        if ScrollableFrame._active_stack:
            ScrollableFrame._active_stack[-1]._on_mousewheel(event)


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════
class AnimangaTracker(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Anime & Manga Tracker")
        self.geometry("1100x740")
        self.minsize(960, 640)
        self.configure(bg=C["bg"])

        sys.path.insert(0, str(BASE))
        from worksuite_db import WorkSuiteDB
        self.db = WorkSuiteDB()
        self.anime_data = self.db.get_all_anime()
        self.manga_data = self.db.get_all_manga()

        # Grid display settings (stored in DB)
        self._grid_gap = 10
        self._load_grid_settings()

        self._setup_styles()
        self._build_ui()

    # ── Styles ────────────────────────────────────────────────────────────────
    def _setup_styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TNotebook", background=C["bg"], borderwidth=0)
        s.configure("TNotebook.Tab",
                    background=C["surface"], foreground=C["muted"],
                    padding=[22, 10], font=("Segoe UI", 10, "bold"),
                    borderwidth=0, focuscolor=C["bg"])
        s.map("TNotebook.Tab",
              background=[("selected", C["white"])],
              foreground=[("selected", C["accent"])])
        s.configure("Vertical.TScrollbar",
                    background=C["border"], troughcolor=C["bg"],
                    arrowcolor=C["muted"], borderwidth=0)

    # ── Build UI ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg=C["surface"], height=58)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(hdr, text="🎌  Anime & Manga Tracker",
                 font=("Segoe UI", 15, "bold"),
                 bg=C["surface"], fg=C["text"]).pack(side="left", padx=24, pady=12)

        self.hdr_stats = tk.Label(hdr, text="", font=("Segoe UI", 9),
                                   bg=C["surface"], fg=C["muted"])
        self.hdr_stats.pack(side="right", padx=24)

        # Main notebook
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        self.tab_anime_dash = tk.Frame(nb, bg=C["bg"])
        self.tab_anime_lib  = tk.Frame(nb, bg=C["bg"])
        self.tab_manga_dash = tk.Frame(nb, bg=C["bg"])
        self.tab_manga_lib  = tk.Frame(nb, bg=C["bg"])

        nb.add(self.tab_anime_dash, text="  📊 Anime Stats  ")
        nb.add(self.tab_anime_lib,  text="  🎬 Anime Library  ")
        nb.add(self.tab_manga_dash, text="  📊 Manga Stats  ")
        nb.add(self.tab_manga_lib,  text="  📖 Manga Library  ")

        self._build_anime_dashboard(self.tab_anime_dash)
        self._build_library(self.tab_anime_lib, "anime")
        self._build_manga_dashboard(self.tab_manga_dash)
        self._build_library(self.tab_manga_lib, "manga")

        self.refresh_all()

        # Re-flow grid on window WIDTH change only (debounced)
        self._resize_after_id = None
        self._last_width = self.winfo_width()
        def _on_resize(event):
            if event.widget != self:
                return
            new_w = event.width
            if new_w == self._last_width:
                return
            self._last_width = new_w
            if self._resize_after_id:
                self.after_cancel(self._resize_after_id)
            self._resize_after_id = self.after(400, lambda: (
                self.refresh_library("anime"),
                self.refresh_library("manga"),
            ))
        self.bind("<Configure>", _on_resize)

    # ══════════════════════════════════════════════════════════════════════════
    #  ANIME DASHBOARD
    # ══════════════════════════════════════════════════════════════════════════
    def _load_grid_settings(self):
        try:
            r = self.db.conn.execute("SELECT value FROM overtime_settings WHERE key='grid_gap'").fetchone()
            if r: self._grid_gap = int(r[0])
        except Exception:
            pass

    def _save_grid_settings(self):
        self.db.conn.execute(
            "INSERT OR REPLACE INTO overtime_settings (key, value) VALUES ('grid_gap', ?)",
            (str(self._grid_gap),))
        self.db.conn.commit()

    def _open_grid_settings(self):
        win = tk.Toplevel(self)
        win.title("Library Settings")
        win.configure(bg=C["bg"])
        win.resizable(False, False)
        win.grab_set()
        win.attributes("-topmost", True)

        # Center on parent window
        win.update_idletasks()
        pw, ph = self.winfo_width(), self.winfo_height()
        px, py = self.winfo_rootx(), self.winfo_rooty()
        ww, wh = 320, 220
        x = px + (pw - ww) // 2
        y = py + (ph - wh) // 2
        win.geometry(f"{ww}x{wh}+{x}+{y}")

        tk.Frame(win, bg=C["accent"], height=3).pack(fill="x")

        card = tk.Frame(win, bg=C["surface"],
                        highlightthickness=1, highlightbackground=C["border"])
        card.pack(fill="both", expand=True, padx=16, pady=16)

        tk.Label(card, text="Library Display", font=("Segoe UI", 12, "bold"),
                 bg=C["surface"], fg=C["text"]).pack(anchor="w", padx=16, pady=(14, 6))

        tk.Label(card, text="Columns adjust automatically to window size",
                 font=("Segoe UI", 8), bg=C["surface"], fg=C["muted"]).pack(anchor="w", padx=16, pady=(0, 8))

        # Gap size
        row = tk.Frame(card, bg=C["surface"])
        row.pack(fill="x", padx=16, pady=4)
        tk.Label(row, text="Gap between cards:", font=("Segoe UI", 10),
                 bg=C["surface"], fg=C["text"]).pack(side="left")
        gap_var = tk.IntVar(value=self._grid_gap)
        gap_spin = tk.Spinbox(row, from_=2, to=30, textvariable=gap_var, width=4,
                               font=("Segoe UI", 11), bg=C["card"], fg=C["text"],
                               relief="flat", highlightthickness=1,
                               highlightbackground=C["border"])
        gap_spin.pack(side="right")

        def apply():
            try:
                self._grid_gap = max(2, min(30, int(gap_var.get())))
                self._save_grid_settings()
                self.refresh_library("anime")
                self.refresh_library("manga")
                win.destroy()
            except ValueError:
                pass

        tk.Button(card, text="  ✓  Apply  ", font=("Segoe UI", 10, "bold"),
                  bg=C["accent"], fg=C["white"], relief="flat",
                  cursor="hand2", padx=16, pady=8,
                  command=apply).pack(pady=(10, 14))

    def _build_anime_dashboard(self, parent):
        self._anime_dash_frame = ScrollableFrame(parent, bg=C["bg"])
        self._anime_dash_frame.pack(fill="both", expand=True)

    def _refresh_anime_dashboard(self):
        inner = self._anime_dash_frame.inner
        for w in inner.winfo_children():
            w.destroy()

        pad = tk.Frame(inner, bg=C["bg"])
        pad.pack(fill="x", padx=30, pady=24)

        hdr_row = tk.Frame(pad, bg=C["bg"])
        hdr_row.pack(fill="x", pady=(0, 18))
        tk.Label(hdr_row, text="Anime Overview",
                 font=("Segoe UI", 16, "bold"),
                 bg=C["bg"], fg=C["text"]).pack(side="left")
        tk.Button(hdr_row, text="  ↻  Refresh  ",
                  font=("Segoe UI", 8, "bold"),
                  bg=C["border"], fg=C["text"], relief="flat",
                  cursor="hand2", padx=8, pady=3,
                  command=self.refresh_all).pack(side="right")

        st = anime_stats(self.anime_data)

        # ── Stat cards row 1 ──────────────────────────────────────────────
        cards1 = tk.Frame(pad, bg=C["bg"])
        cards1.pack(fill="x")

        card_data1 = [
            ("Total Anime",     str(st["total"]),              C["accent"]),
            ("Episodes Watched",str(st["episodes"]),           C["anime"]),
            ("Watch Time",      f"{st['hours']}h ({st['days']}d)", C["accent2"]),
            ("Completed",       str(st["completed"]),          C["completed"]),
            ("Watching",        str(st["watching"]),            C["watching"]),
        ]

        for i, (label, value, color) in enumerate(card_data1):
            self._stat_card(cards1, label, value, color, i)
            cards1.columnconfigure(i, weight=1)

        # ── Stat cards row 2 ──────────────────────────────────────────────
        cards2 = tk.Frame(pad, bg=C["bg"])
        cards2.pack(fill="x", pady=(8, 0))

        avg  = average_score(self.anime_data)
        comp = completion_rate(self.anime_data)

        card_data2 = [
            ("Average Score",    f"{avg}/100" if avg else "—",  C["warning"]),
            ("Completion Rate",  f"{comp}%",                    C["success"]),
            ("On Hold",          str(st["on_hold"]),            C["on_hold"]),
            ("Dropped",          str(st["dropped"]),            C["danger"]),
            ("Plan to Watch",    str(st["planned"]),            C["planned"]),
        ]

        for i, (label, value, color) in enumerate(card_data2):
            self._stat_card(cards2, label, value, color, i)
            cards2.columnconfigure(i, weight=1)

        # ── Status breakdown ──────────────────────────────────────────────
        breakdown = tk.Frame(pad, bg=C["bg"])
        breakdown.pack(fill="x", pady=(20, 0))
        self._status_bar(breakdown, st, "anime")

        # ── Two-column section: Score + Yearly ────────────────────────────
        two_col = tk.Frame(pad, bg=C["bg"])
        two_col.pack(fill="x", pady=(16, 0))
        two_col.columnconfigure(0, weight=1)
        two_col.columnconfigure(1, weight=1)

        self._score_distribution_chart(two_col, self.anime_data, C["anime"], 0)
        self._yearly_stats_table(two_col, anime_yearly_stats(self.anime_data), "anime", 1)

        # ── Top rated ─────────────────────────────────────────────────────
        top_f = tk.Frame(pad, bg=C["bg"])
        top_f.pack(fill="x", pady=(16, 0))
        self._top_rated_list(top_f, self.anime_data, "anime")

        # ── Recently added ────────────────────────────────────────────────
        recent_f = tk.Frame(pad, bg=C["bg"])
        recent_f.pack(fill="x", pady=(16, 0))
        self._recent_list(recent_f, self.anime_data, "anime")

    # ══════════════════════════════════════════════════════════════════════════
    #  MANGA DASHBOARD
    # ══════════════════════════════════════════════════════════════════════════
    def _build_manga_dashboard(self, parent):
        self._manga_dash_frame = ScrollableFrame(parent, bg=C["bg"])
        self._manga_dash_frame.pack(fill="both", expand=True)

    def _refresh_manga_dashboard(self):
        inner = self._manga_dash_frame.inner
        for w in inner.winfo_children():
            w.destroy()

        pad = tk.Frame(inner, bg=C["bg"])
        pad.pack(fill="x", padx=30, pady=24)

        hdr_row = tk.Frame(pad, bg=C["bg"])
        hdr_row.pack(fill="x", pady=(0, 18))
        tk.Label(hdr_row, text="Manga Overview",
                 font=("Segoe UI", 16, "bold"),
                 bg=C["bg"], fg=C["text"]).pack(side="left")
        tk.Button(hdr_row, text="  ↻  Refresh  ",
                  font=("Segoe UI", 8, "bold"),
                  bg=C["border"], fg=C["text"], relief="flat",
                  cursor="hand2", padx=8, pady=3,
                  command=self.refresh_all).pack(side="right")

        st = manga_stats(self.manga_data)

        # ── Stat cards row 1 ──────────────────────────────────────────────
        cards1 = tk.Frame(pad, bg=C["bg"])
        cards1.pack(fill="x")

        card_data1 = [
            ("Total Manga",     str(st["total"]),      C["manga"]),
            ("Chapters Read",   str(st["chapters"]),   C["accent"]),
            ("Est. Read Time",  f"{st['hours']}h",     C["accent2"]),
            ("Completed",       str(st["completed"]),  C["completed"]),
            ("Reading",         str(st["reading"]),     C["reading"]),
        ]

        for i, (label, value, color) in enumerate(card_data1):
            self._stat_card(cards1, label, value, color, i)
            cards1.columnconfigure(i, weight=1)

        # ── Stat cards row 2 ──────────────────────────────────────────────
        cards2 = tk.Frame(pad, bg=C["bg"])
        cards2.pack(fill="x", pady=(8, 0))

        avg  = average_score(self.manga_data)
        comp = completion_rate(self.manga_data)
        cont = sum(1 for e in self.manga_data if e.get("continued_from_anime"))

        card_data2 = [
            ("Average Score",    f"{avg}/100" if avg else "—",  C["warning"]),
            ("Completion Rate",  f"{comp}%",                    C["success"]),
            ("Continued from Anime", str(cont),                 C["anime"]),
        ]

        for i, (label, value, color) in enumerate(card_data2):
            self._stat_card(cards2, label, value, color, i)
            cards2.columnconfigure(i, weight=1)

        # ── Two-column: Score + Yearly ────────────────────────────────────
        two_col = tk.Frame(pad, bg=C["bg"])
        two_col.pack(fill="x", pady=(16, 0))
        two_col.columnconfigure(0, weight=1)
        two_col.columnconfigure(1, weight=1)

        self._score_distribution_chart(two_col, self.manga_data, C["manga"], 0)
        self._yearly_stats_table(two_col, manga_yearly_stats(self.manga_data), "manga", 1)

        # ── Top rated ─────────────────────────────────────────────────────
        top_f = tk.Frame(pad, bg=C["bg"])
        top_f.pack(fill="x", pady=(16, 0))
        self._top_rated_list(top_f, self.manga_data, "manga")

        # ── Recently added ────────────────────────────────────────────────
        recent_f = tk.Frame(pad, bg=C["bg"])
        recent_f.pack(fill="x", pady=(16, 0))
        self._recent_list(recent_f, self.manga_data, "manga")

    # ── Shared dashboard widgets ──────────────────────────────────────────────
    def _stat_card(self, parent, label, value, color, col):
        card = tk.Frame(parent, bg=C["surface"],
                        highlightthickness=1, highlightbackground=C["border"])
        card.grid(row=0, column=col, padx=6, pady=4, sticky="ew", ipadx=12, ipady=10)

        tk.Frame(card, bg=color, height=3).pack(fill="x")
        tk.Label(card, text=label, font=("Segoe UI", 9),
                 bg=C["surface"], fg=C["muted"]).pack(anchor="w", padx=12, pady=(10, 2))
        tk.Label(card, text=value, font=("Segoe UI", 20, "bold"),
                 bg=C["surface"], fg=color).pack(anchor="w", padx=12, pady=(0, 10))

    def _status_bar(self, parent, st, kind):
        card = tk.Frame(parent, bg=C["surface"],
                        highlightthickness=1, highlightbackground=C["border"])
        card.pack(fill="x")

        tk.Label(card, text="  Status Breakdown", font=("Segoe UI", 10, "bold"),
                 bg=C["surface"], fg=C["text"]).pack(anchor="w", padx=12, pady=(12, 8))

        bar_outer = tk.Frame(card, bg=C["bar_bg"], height=18)
        bar_outer.pack(fill="x", padx=12, pady=(0, 8))
        bar_outer.update_idletasks()

        total = st["total"] or 1
        segments = [
            ("completed", st["completed"],  C["completed"]),
            ("watching",  st.get("watching", st.get("reading", 0)), C["watching"]),
            ("on_hold",   st.get("on_hold", 0),   C["on_hold"]),
            ("dropped",   st.get("dropped", 0),    C["dropped"]),
            ("planned",   st.get("planned", 0),     C["planned"]),
        ]

        x_offset = 0.0
        for _, count, color in segments:
            if count > 0:
                w = count / total
                seg = tk.Frame(bar_outer, bg=color, height=18)
                seg.place(relx=x_offset, relwidth=w, relheight=1)
                x_offset += w

        # Legend
        legend = tk.Frame(card, bg=C["surface"])
        legend.pack(anchor="w", padx=12, pady=(0, 12))
        for lbl, count, color in segments:
            if count > 0:
                tk.Label(legend, text="●", font=("Segoe UI", 8),
                         bg=C["surface"], fg=color).pack(side="left", padx=(0, 2))
                tk.Label(legend, text=f"{lbl.replace('_',' ').title()} {count}",
                         font=("Segoe UI", 8),
                         bg=C["surface"], fg=C["muted"]).pack(side="left", padx=(0, 12))

    def _recent_list(self, parent, data, kind):
        card = tk.Frame(parent, bg=C["surface"],
                        highlightthickness=1, highlightbackground=C["border"])
        card.pack(fill="x")

        tk.Label(card, text="  Recently Added", font=("Segoe UI", 10, "bold"),
                 bg=C["surface"], fg=C["text"]).pack(anchor="w", padx=12, pady=(12, 8))

        recent = sorted(data, key=lambda e: e.get("added", ""), reverse=True)[:8]
        if not recent:
            tk.Label(card, text="Nothing here yet. Add your first entry!",
                     font=("Segoe UI", 9), bg=C["surface"], fg=C["muted"]).pack(pady=16)
            return

        for e in recent:
            row = tk.Frame(card, bg=C["surface"])
            row.pack(fill="x", padx=12, pady=3)

            sc = STATUS_COLORS.get(e.get("status", ""), C["muted"])
            tk.Label(row, text="●", font=("Segoe UI", 8),
                     bg=C["surface"], fg=sc).pack(side="left", padx=(0, 6))

            tk.Label(row, text=e.get("title", ""), font=("Segoe UI", 9),
                     bg=C["surface"], fg=C["text"]).pack(side="left")

            if kind == "anime":
                w, t = franchise_ep_summary(e)
                info = f"{w}/{t} eps" if t else "No seasons"
            else:
                info = f"{e.get('chapters_read', 0)} ch"

            tk.Label(row, text=info, font=("Segoe UI", 8),
                     bg=C["surface"], fg=C["muted"]).pack(side="right", padx=(0, 8))

            score = e.get("score")
            if score is not None:
                tk.Label(row, text=f"★ {score}", font=("Segoe UI", 8, "bold"),
                         bg=C["surface"], fg=C["warning"]).pack(side="right", padx=(0, 10))

        tk.Frame(card, bg=C["surface"], height=10).pack()

    # ── Score Distribution Chart ──────────────────────────────────────────────
    def _score_distribution_chart(self, parent, data, color, col):
        card = tk.Frame(parent, bg=C["surface"],
                        highlightthickness=1, highlightbackground=C["border"])
        card.grid(row=0, column=col, padx=6, pady=4, sticky="nsew")

        tk.Label(card, text="  Score Distribution", font=("Segoe UI", 10, "bold"),
                 bg=C["surface"], fg=C["text"]).pack(anchor="w", padx=12, pady=(12, 8))

        buckets = score_distribution(data)
        max_val = max(buckets) if any(buckets) else 1
        labels  = ["0–9","10–19","20–29","30–39","40–49","50–59","60–69","70–79","80–89","90–100"]

        chart = tk.Frame(card, bg=C["surface"])
        chart.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        BAR_H = 120
        for i, (count, lbl) in enumerate(zip(buckets, labels)):
            col_f = tk.Frame(chart, bg=C["surface"])
            col_f.grid(row=0, column=i, padx=2, sticky="s")

            # Bar
            h = int((count / max_val) * BAR_H) if max_val > 0 else 0
            h = max(h, 2) if count > 0 else 2

            # Count label
            if count > 0:
                tk.Label(col_f, text=str(count), font=("Segoe UI", 7),
                         bg=C["surface"], fg=C["muted"]).pack()

            bar = tk.Frame(col_f, bg=color if count > 0 else C["bar_bg"],
                           width=22, height=h)
            bar.pack_propagate(False)
            bar.pack()

            # Range label
            tk.Label(col_f, text=lbl.split("–")[0], font=("Segoe UI", 6),
                     bg=C["surface"], fg=C["muted"]).pack()

            chart.columnconfigure(i, weight=1)

    # ── Yearly Stats Table ────────────────────────────────────────────────────
    def _yearly_stats_table(self, parent, year_data, kind, col):
        card = tk.Frame(parent, bg=C["surface"],
                        highlightthickness=1, highlightbackground=C["border"])
        card.grid(row=0, column=col, padx=6, pady=4, sticky="nsew")

        tk.Label(card, text="  Yearly Breakdown", font=("Segoe UI", 10, "bold"),
                 bg=C["surface"], fg=C["text"]).pack(anchor="w", padx=12, pady=(12, 8))

        if not year_data:
            tk.Label(card, text="No data yet.",
                     font=("Segoe UI", 9), bg=C["surface"], fg=C["muted"]).pack(pady=16)
            return

        # Header
        hdr = tk.Frame(card, bg=C["border"])
        hdr.pack(fill="x", padx=12, pady=(0, 4))

        if kind == "anime":
            cols = [("Year", 8), ("Added", 8), ("Done", 8), ("Eps", 8), ("Hours", 8)]
        else:
            cols = [("Year", 8), ("Added", 8), ("Done", 8), ("Chapters", 10)]

        for lbl, w in cols:
            tk.Label(hdr, text=lbl, font=("Segoe UI", 8, "bold"),
                     bg=C["border"], fg=C["muted"], width=w, anchor="w"
                     ).pack(side="left", padx=4, pady=3)

        # Rows
        for i, (year, st) in enumerate(year_data.items()):
            row_bg = C["card"] if i % 2 == 0 else C["surface"]
            row = tk.Frame(card, bg=row_bg)
            row.pack(fill="x", padx=12)

            color_yr = C["anime"] if kind == "anime" else C["manga"]
            tk.Label(row, text=str(year), font=("Segoe UI", 8, "bold"),
                     bg=row_bg, fg=color_yr, width=8, anchor="w").pack(side="left", padx=4, pady=2)
            tk.Label(row, text=str(st["added"]), font=("Segoe UI", 8),
                     bg=row_bg, fg=C["text"], width=8, anchor="w").pack(side="left", padx=4)
            tk.Label(row, text=str(st["completed"]), font=("Segoe UI", 8),
                     bg=row_bg, fg=C["completed"], width=8, anchor="w").pack(side="left", padx=4)

            if kind == "anime":
                tk.Label(row, text=str(st["episodes"]), font=("Segoe UI", 8),
                         bg=row_bg, fg=C["text"], width=8, anchor="w").pack(side="left", padx=4)
                hrs = round(st["minutes"] / 60, 1)
                tk.Label(row, text=f"{hrs}h", font=("Segoe UI", 8),
                         bg=row_bg, fg=C["accent2"], width=8, anchor="w").pack(side="left", padx=4)
            else:
                tk.Label(row, text=str(st["chapters"]), font=("Segoe UI", 8),
                         bg=row_bg, fg=C["text"], width=10, anchor="w").pack(side="left", padx=4)

        tk.Frame(card, bg=C["surface"], height=8).pack()

    # ── Top Rated List ────────────────────────────────────────────────────────
    def _top_rated_list(self, parent, data, kind):
        card = tk.Frame(parent, bg=C["surface"],
                        highlightthickness=1, highlightbackground=C["border"])
        card.pack(fill="x")

        color = C["anime"] if kind == "anime" else C["manga"]

        tk.Label(card, text="  Top Rated", font=("Segoe UI", 10, "bold"),
                 bg=C["surface"], fg=C["text"]).pack(anchor="w", padx=12, pady=(12, 8))

        top = top_rated(data, 10)
        if not top:
            tk.Label(card, text="No scored entries yet.",
                     font=("Segoe UI", 9), bg=C["surface"], fg=C["muted"]).pack(pady=12)
            tk.Frame(card, bg=C["surface"], height=6).pack()
            return

        for i, e in enumerate(top):
            row_bg = C["card"] if i % 2 == 0 else C["surface"]
            row = tk.Frame(card, bg=row_bg)
            row.pack(fill="x", padx=12, pady=1)

            rank = f"#{i+1}"
            tk.Label(row, text=rank, font=("Segoe UI", 9, "bold"),
                     bg=row_bg, fg=C["muted"], width=4).pack(side="left", padx=(4, 8), pady=4)

            # Score bar
            score = e.get("score", 0)
            bar_w = 60
            bar_f = tk.Frame(row, bg=C["bar_bg"], width=bar_w, height=12)
            bar_f.pack_propagate(False)
            bar_f.pack(side="left", padx=(0, 8), pady=4)
            fill_w = int(bar_w * score / 100)
            bar_color = C["completed"] if score >= 80 else (C["warning"] if score >= 50 else C["danger"])
            tk.Frame(bar_f, bg=bar_color, width=fill_w, height=12).place(x=0, y=0, relheight=1)

            tk.Label(row, text=f"★ {score}", font=("Segoe UI", 9, "bold"),
                     bg=row_bg, fg=C["warning"], width=6).pack(side="left", padx=(0, 8))

            tk.Label(row, text=e.get("title", ""), font=("Segoe UI", 9),
                     bg=row_bg, fg=C["text"]).pack(side="left")

            sc = STATUS_COLORS.get(e.get("status", ""), C["muted"])
            tk.Label(row, text=e.get("status", ""), font=("Segoe UI", 7),
                     bg=row_bg, fg=sc).pack(side="right", padx=8)

        tk.Frame(card, bg=C["surface"], height=8).pack()

    # ══════════════════════════════════════════════════════════════════════════
    #  LIBRARY TAB (shared anime/manga)
    # ══════════════════════════════════════════════════════════════════════════
    def _build_library(self, parent, kind):
        toolbar = tk.Frame(parent, bg=C["bg"])
        toolbar.pack(fill="x", padx=20, pady=(14, 8))

        color = C["anime"] if kind == "anime" else C["manga"]
        label = "Anime" if kind == "anime" else "Manga"

        tk.Label(toolbar, text=f"{label} Library",
                 font=("Segoe UI", 14, "bold"),
                 bg=C["bg"], fg=C["text"]).pack(side="left")

        right = tk.Frame(toolbar, bg=C["bg"])
        right.pack(side="right")

        # Status filter
        statuses = ["All"] + (ANIME_STATUSES if kind == "anime" else MANGA_STATUSES)
        sf = ttk.Combobox(right, values=statuses, width=16,
                          state="readonly", font=("Segoe UI", 9))
        sf.set("All")
        sf.pack(side="left", padx=(0, 8))
        setattr(self, f"{kind}_filter_status", sf)

        # Search
        search_var = tk.StringVar()
        se = tk.Entry(right, textvariable=search_var,
                      font=("Segoe UI", 10), bg=C["surface"], fg=C["text"],
                      insertbackground=C["text"], relief="flat", width=20,
                      highlightthickness=1, highlightbackground=C["border"],
                      highlightcolor=C["accent"])
        se.pack(side="left", ipady=5, padx=(0, 8))
        se.insert(0, "Search...")
        se.bind("<FocusIn>",  lambda e, w=se: w.delete(0, "end") if w.get() == "Search..." else None)
        se.bind("<FocusOut>", lambda e, w=se: w.insert(0, "Search...") if not w.get() else None)
        setattr(self, f"{kind}_search_var", search_var)

        search_var.trace_add("write", lambda *a: self.refresh_library(kind))
        sf.bind("<<ComboboxSelected>>", lambda e: self.refresh_library(kind))

        # Add button
        tk.Button(right, text=f"  +  Add {label}  ",
                  font=("Segoe UI", 10, "bold"),
                  bg=color, fg=C["white"], relief="flat",
                  cursor="hand2", padx=14, pady=6,
                  command=lambda: self.open_add_dialog(kind)).pack(side="left", padx=(0, 6))

        # Grid settings button
        tk.Button(right, text="⚙",
                  font=("Segoe UI", 12), bg=C["border"], fg=C["text"],
                  relief="flat", cursor="hand2", padx=6, pady=4,
                  command=self._open_grid_settings).pack(side="left")

        # Grid
        grid_outer = ScrollableFrame(parent, bg=C["bg"])
        grid_outer.pack(fill="both", expand=True, padx=20, pady=(0, 8))
        setattr(self, f"{kind}_grid", grid_outer.inner)

        # Count
        bot = tk.Frame(parent, bg=C["surface"], height=30)
        bot.pack(fill="x", side="bottom")
        bot.pack_propagate(False)
        lbl = tk.Label(bot, text="", font=("Segoe UI", 8),
                       bg=C["surface"], fg=C["muted"])
        lbl.pack(side="left", padx=14, pady=6)
        setattr(self, f"{kind}_count_lbl", lbl)

    # ── Refresh library grid ──────────────────────────────────────────────────
    def refresh_library(self, kind):
        grid = getattr(self, f"{kind}_grid")
        for w in grid.winfo_children():
            w.destroy()

        data   = self.anime_data if kind == "anime" else self.manga_data
        status = getattr(self, f"{kind}_filter_status").get()
        search = getattr(self, f"{kind}_search_var").get().lower()
        if search == "search...":
            search = ""

        filtered = [e for e in data
                    if (status == "All" or e.get("status") == status)
                    and (not search or search in e.get("title", "").lower())]
        filtered.sort(key=lambda e: e.get("title", "").lower())

        CARD_W = 182  # card width + border
        GAP = self._grid_gap
        grid.update_idletasks()
        avail = grid.winfo_toplevel().winfo_width() - 60
        if avail < 400:
            avail = 800
        COLS = max(2, min(10, avail // (CARD_W + GAP)))
        # Reset all columns
        for c in range(20):
            grid.columnconfigure(c, weight=0, uniform="", minsize=0)
        # Weighted columns that spread evenly
        for c in range(COLS):
            grid.columnconfigure(c, weight=1)
        for i, entry in enumerate(filtered):
            r, c = divmod(i, COLS)
            cell = tk.Frame(grid, bg=C["bg"])
            cell.grid(row=r, column=c, padx=GAP, pady=GAP, sticky="new")
            card = self._make_card(cell, entry, kind)
            card.pack(anchor="n")

        getattr(self, f"{kind}_count_lbl").config(
            text=f"  {len(filtered)} of {len(data)} entries")
        self._update_header()

    # ── Entry card ────────────────────────────────────────────────────────────
    def _make_card(self, parent, entry, kind):
        color = C["anime"] if kind == "anime" else C["manga"]
        sc    = STATUS_COLORS.get(entry.get("status", ""), C["muted"])

        card = tk.Frame(parent, bg=C["surface"], width=180, height=350,
                        highlightthickness=1, highlightbackground=C["border"],
                        cursor="hand2")
        card.pack_propagate(False)

        # Cover — fills card edge to edge
        cover_f = tk.Frame(card, bg=C["surface"], height=220)
        cover_f.pack(fill="x")
        cover_f.pack_propagate(False)
        self._render_cover(cover_f, entry, color, 180, 220)

        # Status indicator
        tk.Frame(card, bg=sc, height=3).pack(fill="x")

        # Title
        title = entry.get("title", "Unknown")
        short = title[:24] + ("…" if len(title) > 24 else "")
        tk.Label(card, text=short, font=("Segoe UI", 10, "bold"),
                 bg=C["surface"], fg=C["text"], wraplength=160,
                 justify="left").pack(anchor="w", padx=8, pady=(6, 1))

        # Subtitle
        if kind == "anime":
            w, t = franchise_ep_summary(entry)
            sub = f"{w}/{t} eps" if t else "No seasons yet"
        else:
            r = entry.get("chapters_read", 0)
            t = entry.get("chapters_total", 0)
            sub = f"{r}/{t} ch" if t else f"{r} ch read"

        tk.Label(card, text=sub, font=("Segoe UI", 9),
                 bg=C["surface"], fg=C["muted"]).pack(anchor="w", padx=8)

        # Progress mini-bar
        if kind == "anime":
            w, t = franchise_ep_summary(entry)
        else:
            w = entry.get("chapters_read", 0)
            t = entry.get("chapters_total", 0)
        if t > 0:
            bar = tk.Frame(card, bg=C["bar_bg"], height=4)
            bar.pack(fill="x", padx=8, pady=(4, 0))
            pct = min(w / t, 1.0)
            fill_color = C["completed"] if pct >= 1.0 else color
            tk.Frame(bar, bg=fill_color, height=4).place(relwidth=pct, relheight=1)

        # Score
        score = entry.get("score")
        if score is not None:
            tk.Label(card, text=f"★ {score}/100", font=("Segoe UI", 8, "bold"),
                     bg=C["surface"], fg=C["warning"]).pack(anchor="w", padx=8, pady=(2, 0))

        # Click handler
        for w2 in self._all_children(card):
            w2.bind("<Button-1>", lambda e, en=entry, k=kind: self.open_detail(en, k))
            w2.bind("<Enter>", lambda e, c=card: c.config(highlightbackground=color))
            w2.bind("<Leave>", lambda e, c=card: c.config(highlightbackground=C["border"]))

        return card

    # Image cache to avoid reloading from disk on every refresh
    _cover_cache = {}

    def _render_cover(self, parent, entry, color, w, h, crop_fill=False):
        cover_path = entry.get("cover")
        if cover_path and Path(cover_path).exists():
            try:
                from PIL import Image, ImageTk
                cache_key = f"{cover_path}_{w}x{h}_{'fill' if crop_fill else 'fit'}"
                if cache_key not in AnimangaTracker._cover_cache:
                    img = Image.open(cover_path)
                    img_w, img_h = img.size
                    if crop_fill:
                        # Crop to fill: scale to cover the box, then crop from top
                        scale = max(w / img_w, h / img_h)
                        new_w = int(img_w * scale)
                        new_h = int(img_h * scale)
                        img = img.resize((new_w, new_h), Image.LANCZOS)
                        # Crop: center horizontally, anchor to top vertically
                        left = (new_w - w) // 2
                        img = img.crop((left, 0, left + w, h))
                    else:
                        # Fit inside: preserve aspect ratio with padding
                        scale = min(w / img_w, h / img_h)
                        new_w = int(img_w * scale)
                        new_h = int(img_h * scale)
                        img = img.resize((new_w, new_h), Image.LANCZOS)
                    AnimangaTracker._cover_cache[cache_key] = ImageTk.PhotoImage(img)
                photo = AnimangaTracker._cover_cache[cache_key]
                lbl = tk.Label(parent, image=photo, bg=parent.cget("bg"))
                lbl.image = photo
                lbl.pack(expand=True, fill="both")
                return
            except Exception:
                pass
        icon = "🎬" if color == C["anime"] else "📖"
        tk.Label(parent, text=icon, font=("Segoe UI", 40),
                 bg=C["bar_bg"], fg=color).pack(expand=True)

    def _all_children(self, widget):
        children = [widget]
        for child in widget.winfo_children():
            children.extend(self._all_children(child))
        return children

    # ══════════════════════════════════════════════════════════════════════════
    #  ADD DIALOG (with API search)
    # ══════════════════════════════════════════════════════════════════════════
    def open_add_dialog(self, kind):
        win = tk.Toplevel(self)
        color = C["anime"] if kind == "anime" else C["manga"]
        label = "Anime" if kind == "anime" else "Manga"
        win.title(f"Add {label}")
        win.geometry("520x480")
        win.configure(bg=C["bg"])
        win.resizable(False, False)
        win.grab_set()

        tk.Frame(win, bg=color, height=4).pack(fill="x")

        # ── Search section ────────────────────────────────────────────────
        search_f = tk.Frame(win, bg=C["surface"])
        search_f.pack(fill="x", padx=20, pady=(16, 0))

        tk.Label(search_f, text=f"🔍  Search {label} (Jikan/MAL)",
                 font=("Segoe UI", 10, "bold"),
                 bg=C["surface"], fg=C["text"]).pack(anchor="w", padx=12, pady=(10, 6))

        search_row = tk.Frame(search_f, bg=C["surface"])
        search_row.pack(fill="x", padx=12, pady=(0, 8))

        search_entry = tk.Entry(search_row, font=("Segoe UI", 10),
                                bg=C["card"], fg=C["text"],
                                insertbackground=C["text"], relief="flat", width=32,
                                highlightthickness=1, highlightbackground=C["border"],
                                highlightcolor=C["accent"])
        search_entry.pack(side="left", ipady=5, padx=(0, 8))

        search_status = tk.Label(search_row, text="", font=("Segoe UI", 8),
                                  bg=C["surface"], fg=C["muted"])
        search_status.pack(side="left", padx=4)

        search_btn = tk.Button(search_row, text="  Search  ",
                               font=("Segoe UI", 9, "bold"),
                               bg=color, fg=C["white"], relief="flat",
                               cursor="hand2", padx=10, pady=4)
        search_btn.pack(side="right")

        _api_results = []
        _selected_result = [None]

        def do_search():
            query = search_entry.get().strip()
            if not query:
                return
            search_status.config(text="Searching...", fg=C["accent"])
            search_btn.config(state="disabled")
            win.update_idletasks()

            def _search_thread():
                if kind == "anime":
                    results = jikan_search_anime(query, limit=25)
                else:
                    results = jikan_search_manga(query, limit=25)
                _api_results.clear()
                _api_results.extend(results)
                win.after(0, lambda: _open_results_popup(query))

            threading.Thread(target=_search_thread, daemon=True).start()

        def _open_results_popup(query):
            search_btn.config(state="normal")

            if not _api_results:
                search_status.config(text="No results found.", fg=C["danger"])
                return

            search_status.config(text=f"{len(_api_results)} results — pick one", fg=C["success"])

            # ── Popup window ──────────────────────────────────────────────
            popup = tk.Toplevel(win)
            popup.title(f"Search Results: {query}")
            popup.geometry("520x460")
            popup.configure(bg=C["bg"])
            popup.resizable(False, True)
            popup.grab_set()

            tk.Frame(popup, bg=color, height=3).pack(fill="x")

            hdr = tk.Frame(popup, bg=C["surface"])
            hdr.pack(fill="x")
            tk.Label(hdr, text=f"  {len(_api_results)} results for '{query}'",
                     font=("Segoe UI", 10, "bold"),
                     bg=C["surface"], fg=C["text"]).pack(anchor="w", padx=12, pady=10)

            # Scrollable results
            list_f = tk.Frame(popup, bg=C["bg"])
            list_f.pack(fill="both", expand=True)

            canvas = tk.Canvas(list_f, bg=C["bg"], highlightthickness=0)
            sb = ttk.Scrollbar(list_f, orient="vertical", command=canvas.yview)
            inner = tk.Frame(canvas, bg=C["bg"])
            inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.create_window((0, 0), window=inner, anchor="nw", tags="inner")
            canvas.configure(yscrollcommand=sb.set)
            canvas.pack(side="left", fill="both", expand=True)
            sb.pack(side="right", fill="y")
            canvas.bind("<Configure>", lambda e: canvas.itemconfig("inner", width=e.width))

            def _popup_mousewheel(event):
                if event.delta:
                    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                elif event.num == 4:
                    canvas.yview_scroll(-3, "units")
                elif event.num == 5:
                    canvas.yview_scroll(3, "units")

            canvas.bind_all("<MouseWheel>", _popup_mousewheel)
            canvas.bind_all("<Button-4>", _popup_mousewheel)
            canvas.bind_all("<Button-5>", _popup_mousewheel)

            def _on_popup_close():
                canvas.unbind_all("<MouseWheel>")
                canvas.unbind_all("<Button-4>")
                canvas.unbind_all("<Button-5>")
                popup.destroy()

            popup.protocol("WM_DELETE_WINDOW", _on_popup_close)

            for i, r in enumerate(_api_results):
                title_api = r.get("title", "")
                title_en  = r.get("title_english") or ""
                eps = r.get("episodes") or r.get("chapters") or "?"
                score_api = r.get("score", "—")
                mal_type  = r.get("type", "")
                status_api = r.get("status", "")
                year = ""
                aired = r.get("aired") or r.get("published")
                if aired and aired.get("from"):
                    year = aired["from"][:4]

                row_bg = C["surface"] if i % 2 == 0 else C["card"]
                row = tk.Frame(inner, bg=row_bg, cursor="hand2")
                row.pack(fill="x", pady=1, padx=8)

                # Left: info
                info = tk.Frame(row, bg=row_bg)
                info.pack(side="left", fill="x", expand=True, padx=8, pady=6)

                tk.Label(info, text=title_api[:60], font=("Segoe UI", 9, "bold"),
                         bg=row_bg, fg=C["text"], anchor="w").pack(anchor="w")

                if title_en and title_en != title_api:
                    tk.Label(info, text=title_en[:50], font=("Segoe UI", 7),
                             bg=row_bg, fg=C["muted"], anchor="w").pack(anchor="w")

                unit = "eps" if kind == "anime" else "ch"
                sub = f"{mal_type}  ·  {eps} {unit}  ·  ★{score_api}  ·  {year}  ·  {status_api}"
                tk.Label(info, text=sub, font=("Segoe UI", 7),
                         bg=row_bg, fg=C["muted"], anchor="w").pack(anchor="w")

                # Right: select button
                tk.Button(row, text="Select",
                          font=("Segoe UI", 8, "bold"),
                          bg=color, fg=C["white"], relief="flat",
                          cursor="hand2", padx=10, pady=4,
                          command=lambda result=r: _pick_result(result, popup)
                          ).pack(side="right", padx=8, pady=8)

        def _pick_result(result, popup):
            _selected_result[0] = result
            _fill_from_api(result)
            search_status.config(
                text=f"Selected: {result.get('title', '')[:30]}",
                fg=C["success"])
            popup.destroy()

        search_btn.config(command=do_search)
        search_entry.bind("<Return>", lambda e: do_search())

        # ── Divider ───────────────────────────────────────────────────────
        tk.Frame(win, bg=C["border"], height=1).pack(fill="x", padx=20, pady=8)

        tk.Label(win, text="Fill manually or select a search result above to auto-fill ↓",
                 font=("Segoe UI", 8), bg=C["bg"], fg=C["muted"]).pack(padx=20)

        # ── Manual form ───────────────────────────────────────────────────
        form = tk.Frame(win, bg=C["bg"])
        form.pack(fill="both", expand=True, padx=30, pady=(8, 20))

        def make_field(row, lbl, **kw):
            tk.Label(form, text=lbl, font=("Segoe UI", 9),
                     bg=C["bg"], fg=C["muted"]).grid(row=row, column=0,
                                                       sticky="w", pady=4, padx=(0, 14))
            e = tk.Entry(form, font=("Segoe UI", 10),
                         bg=C["surface"], fg=C["text"],
                         insertbackground=C["text"], relief="flat", width=30,
                         highlightthickness=1, highlightbackground=C["border"],
                         highlightcolor=C["accent"], **kw)
            e.grid(row=row, column=1, pady=4, ipady=4)
            return e

        title_e = make_field(0, "Title")

        tk.Label(form, text="Status", font=("Segoe UI", 9),
                 bg=C["bg"], fg=C["muted"]).grid(row=1, column=0, sticky="w", pady=4)
        statuses = ANIME_STATUSES if kind == "anime" else MANGA_STATUSES
        status_cb = ttk.Combobox(form, values=statuses, width=28,
                                  state="readonly", font=("Segoe UI", 10))
        status_cb.set(statuses[0])
        status_cb.grid(row=1, column=1, pady=4)

        score_e = make_field(2, "Score (0–100)")

        tk.Label(form, text="Notes", font=("Segoe UI", 9),
                 bg=C["bg"], fg=C["muted"]).grid(row=3, column=0, sticky="nw", pady=4)
        notes_t = tk.Text(form, font=("Segoe UI", 9),
                          bg=C["surface"], fg=C["text"],
                          insertbackground=C["text"], relief="flat",
                          width=30, height=2,
                          highlightthickness=1, highlightbackground=C["border"])
        notes_t.grid(row=3, column=1, pady=4)

        _cover_url = [None]  # store API cover URL
        _mal_id = [None]

        def _fill_from_api(result):
            _mal_id[0] = result.get("mal_id")
            # Title
            title_e.delete(0, "end")
            title_e.insert(0, result.get("title", ""))
            # Score
            score_e.delete(0, "end")
            # Cover URL
            images = result.get("images", {}).get("jpg", {})
            _cover_url[0] = images.get("large_image_url") or images.get("image_url")

        def submit():
            title = title_e.get().strip()
            if not title:
                messagebox.showerror("Required", "Title is required.", parent=win)
                return
            score = None
            sr = score_e.get().strip()
            if sr:
                try:
                    score = int(sr)
                    if not (0 <= score <= 100):
                        raise ValueError
                except ValueError:
                    messagebox.showerror("Invalid", "Score must be 0–100.", parent=win)
                    return

            eid = new_id()
            entry = {
                "id":     eid,
                "mal_id": _mal_id[0],
                "title":  title,
                "status": status_cb.get(),
                "score":  score,
                "notes":  notes_t.get("1.0", "end").strip(),
                "cover":  None,
                "added":  datetime.now().strftime("%Y-%m-%d"),
                "seasons": [],
                "movies":  [],
                "ovas":    [],
                "chapters_total":  0,
                "chapters_read":   0,
                "chapter_start":   0,
                "continued_from_anime": False,
            }

            # If API result selected and anime, try to get episode/duration info
            sel = _selected_result[0]
            if sel and kind == "anime":
                eps = sel.get("episodes")
                dur_raw = sel.get("duration", "")
                dur = DEFAULT_EP_DURATION
                if dur_raw:
                    # Parse "24 min per ep" or "1 hr 30 min"
                    import re
                    hr_match = re.search(r"(\d+)\s*hr", dur_raw)
                    min_match = re.search(r"(\d+)\s*min", dur_raw)
                    dur = 0
                    if hr_match:
                        dur += int(hr_match.group(1)) * 60
                    if min_match:
                        dur += int(min_match.group(1))
                    if dur == 0:
                        dur = DEFAULT_EP_DURATION

                if eps:
                    entry["seasons"].append({
                        "name": sel.get("title", title),
                        "episodes": eps,
                        "ep_watched": [False] * eps,
                        "ep_duration": dur,
                    })

            if sel and kind == "manga":
                chs = sel.get("chapters")
                if chs:
                    entry["chapters_total"] = chs

            def _finish():
                if kind == "anime":
                    self.db.save_anime(entry)
                    self.anime_data.append(entry)
                else:
                    self.db.save_manga(entry)
                    self.manga_data.append(entry)
                win.destroy()
                self.refresh_all()
                self.open_detail(entry, kind)

            if _cover_url[0]:
                def _download():
                    cover_path = download_cover(_cover_url[0], eid)
                    if cover_path:
                        entry["cover"] = cover_path
                    win.after(0, _finish)
                threading.Thread(target=_download, daemon=True).start()
            else:
                _finish()

        tk.Button(form, text=f"  +  Create {label}  ",
                  font=("Segoe UI", 10, "bold"),
                  bg=color, fg=C["white"], relief="flat",
                  cursor="hand2", padx=14, pady=8, command=submit
                  ).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))

    # ══════════════════════════════════════════════════════════════════════════
    #  DETAIL WINDOW
    # ══════════════════════════════════════════════════════════════════════════
    def open_detail(self, entry, kind):
        data = self.anime_data if kind == "anime" else self.manga_data
        live = next((e for e in data if e["id"] == entry["id"]), None)
        if not live:
            return

        win = tk.Toplevel(self)
        win.title(live["title"])
        win.geometry("920x680")
        win.configure(bg=C["bg"])
        win.minsize(840, 600)

        color = C["anime"] if kind == "anime" else C["manga"]
        tk.Frame(win, bg=color, height=4).pack(fill="x")

        body = tk.Frame(win, bg=C["bg"])
        body.pack(fill="both", expand=True)

        # ── Left sidebar ──────────────────────────────────────────────────
        left = tk.Frame(body, bg=C["surface"], width=220)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        # Cover
        cf = tk.Frame(left, bg=C["bar_bg"], width=200, height=280,
                      highlightthickness=1, highlightbackground=C["border"])
        cf.pack(padx=10, pady=12)
        cf.pack_propagate(False)
        self._render_cover(cf, live, color, 200, 280)

        tk.Button(left, text="🖼  Change Cover",
                  font=("Segoe UI", 8), bg=C["border"], fg=C["text"],
                  relief="flat", cursor="hand2", pady=4,
                  command=lambda: self._pick_cover(live, kind, cf, color, win)
                  ).pack(fill="x", padx=10, pady=(0, 10))

        # Meta
        meta = tk.Frame(left, bg=C["surface"])
        meta.pack(fill="x", padx=10)

        statuses = ANIME_STATUSES if kind == "anime" else MANGA_STATUSES
        status_var = tk.StringVar(value=live.get("status", statuses[0]))
        score_var  = tk.StringVar(value=str(live["score"]) if live.get("score") is not None else "")

        tk.Label(meta, text="Status", font=("Segoe UI", 8),
                 bg=C["surface"], fg=C["muted"]).grid(row=0, column=0, sticky="w", pady=4)
        status_cb = ttk.Combobox(meta, values=statuses, textvariable=status_var,
                                  width=14, state="readonly", font=("Segoe UI", 9))
        status_cb.grid(row=0, column=1, pady=4, sticky="w")
        status_cb.bind("<<ComboboxSelected>>",
                       lambda e: self._update_field(live, kind, "status", status_var.get()))

        tk.Label(meta, text="Score", font=("Segoe UI", 8),
                 bg=C["surface"], fg=C["muted"]).grid(row=1, column=0, sticky="w", pady=4)
        score_e = tk.Entry(meta, textvariable=score_var, width=6,
                           font=("Segoe UI", 10, "bold"),
                           bg=C["card"], fg=C["warning"],
                           insertbackground=C["text"], relief="flat",
                           highlightthickness=1, highlightbackground=C["border"])
        score_e.grid(row=1, column=1, pady=4, sticky="w", ipady=3)
        score_e.bind("<FocusOut>", lambda e: self._save_score(live, kind, score_var))

        tk.Label(meta, text="Added", font=("Segoe UI", 8),
                 bg=C["surface"], fg=C["muted"]).grid(row=2, column=0, sticky="w", pady=4)
        tk.Label(meta, text=live.get("added", ""), font=("Segoe UI", 8),
                 bg=C["surface"], fg=C["text"]).grid(row=2, column=1, sticky="w")

        # Notes
        tk.Label(left, text="Notes", font=("Segoe UI", 8),
                 bg=C["surface"], fg=C["muted"]).pack(anchor="w", padx=10, pady=(12, 2))
        notes_t = tk.Text(left, font=("Segoe UI", 8),
                          bg=C["card"], fg=C["text"],
                          insertbackground=C["text"], relief="flat",
                          width=24, height=4,
                          highlightthickness=1, highlightbackground=C["border"])
        notes_t.pack(padx=10, pady=(0, 4))
        notes_t.insert("1.0", live.get("notes", ""))
        notes_t.bind("<FocusOut>", lambda e: self._save_notes(live, kind, notes_t))

        # Delete
        tk.Button(left, text="Delete Entry",
                  font=("Segoe UI", 8), bg=C["danger"], fg=C["white"],
                  relief="flat", cursor="hand2", pady=4,
                  command=lambda: self._delete_entry(live, kind, win)
                  ).pack(fill="x", padx=10, pady=(10, 12))

        # ── Right content ─────────────────────────────────────────────────
        right = tk.Frame(body, bg=C["bg"])
        right.pack(side="left", fill="both", expand=True)

        title_row = tk.Frame(right, bg=C["bg"])
        title_row.pack(fill="x", padx=16, pady=(14, 0))

        title_lbl = tk.Label(title_row, text=live["title"],
                             font=("Segoe UI", 15, "bold"),
                             bg=C["bg"], fg=color, cursor="hand2")
        title_lbl.pack(side="left")

        tk.Label(title_row, text="  ✏", font=("Segoe UI", 10),
                 bg=C["bg"], fg=C["muted"]).pack(side="left", padx=(4, 0))

        def _edit_title(event=None):
            current = live["title"]
            edit_e = tk.Entry(title_row, font=("Segoe UI", 15, "bold"),
                              bg=C["surface"], fg=color,
                              insertbackground=C["text"], relief="flat", width=40,
                              highlightthickness=1, highlightbackground=C["accent"],
                              highlightcolor=C["accent"])
            edit_e.insert(0, current)
            title_lbl.pack_forget()
            edit_e.pack(side="left")
            edit_e.focus_set()
            edit_e.select_range(0, "end")
            def _save_title(ev=None):
                new_val = edit_e.get().strip()
                if new_val and new_val != current:
                    live["title"] = new_val
                    self._save(kind, live)
                    self.refresh_library(kind)
                    win.title(live["title"])
                edit_e.destroy()
                title_lbl.config(text=live["title"])
                title_lbl.pack(side="left")
            edit_e.bind("<Return>", _save_title)
            edit_e.bind("<FocusOut>", _save_title)
            edit_e.bind("<Escape>", lambda e: (edit_e.destroy(), title_lbl.pack(side="left")))

        title_lbl.bind("<Double-1>", _edit_title)

        if kind == "anime":
            nb = ttk.Notebook(right)
            nb.pack(fill="both", expand=True, padx=12, pady=10)

            t_seasons = tk.Frame(nb, bg=C["bg"])
            t_movies  = tk.Frame(nb, bg=C["bg"])
            t_ovas    = tk.Frame(nb, bg=C["bg"])
            nb.add(t_seasons, text="  📺 Seasons  ")
            nb.add(t_movies,  text="  🎬 Movies   ")
            nb.add(t_ovas,    text="  ✨ OVAs     ")

            self._build_seasons_panel(t_seasons, live, kind)
            self._build_simple_list(t_movies, live, kind, "movies",  "Movie")
            self._build_simple_list(t_ovas,   live, kind, "ovas",    "OVA")
        else:
            self._build_manga_panel(right, live, kind)

    def _pick_cover(self, entry, kind, cf, color, win):
        path = filedialog.askopenfilename(
            title="Select Cover Image",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.webp *.gif")],
            parent=win)
        if not path:
            return
        ext  = Path(path).suffix
        dest = COVERS_DIR / f"{entry['id']}{ext}"
        shutil.copy2(path, dest)
        entry["cover"] = str(dest)
        self._save(kind, entry)
        for w in cf.winfo_children():
            w.destroy()
        self._render_cover(cf, entry, color, 200, 280)
        self.refresh_library(kind)

    # ══════════════════════════════════════════════════════════════════════════
    #  SEASONS PANEL (anime)
    # ══════════════════════════════════════════════════════════════════════════
    def _build_seasons_panel(self, parent, entry, kind):
        for w in parent.winfo_children():
            w.destroy()

        toolbar = tk.Frame(parent, bg=C["bg"])
        toolbar.pack(fill="x", padx=8, pady=(10, 6))
        tk.Label(toolbar, text="Seasons", font=("Segoe UI", 11, "bold"),
                 bg=C["bg"], fg=C["text"]).pack(side="left")
        tk.Button(toolbar, text="  +  Manual  ",
                  font=("Segoe UI", 9, "bold"),
                  bg=C["accent"], fg=C["white"], relief="flat",
                  cursor="hand2", padx=8, pady=4,
                  command=lambda: self._add_season_dialog(entry, kind, parent)
                  ).pack(side="right")
        tk.Button(toolbar, text="  🔍  Search MAL  ",
                  font=("Segoe UI", 9, "bold"),
                  bg=C["anime"], fg=C["white"], relief="flat",
                  cursor="hand2", padx=8, pady=4,
                  command=lambda: self._search_add_season(entry, kind, parent)
                  ).pack(side="right", padx=(0, 6))

        sf = ScrollableFrame(parent, bg=C["bg"])
        sf.pack(fill="both", expand=True, padx=8)

        if not entry.get("seasons"):
            tk.Label(sf.inner, text="No seasons yet. Click '+ Add Season' to start.",
                     font=("Segoe UI", 9), bg=C["bg"], fg=C["muted"]).pack(pady=30)
            return

        for s_idx, season in enumerate(entry["seasons"]):
            self._render_season_card(sf.inner, entry, kind, s_idx, season, parent)

    def _render_season_card(self, parent, entry, kind, s_idx, season, tab_parent):
        ep_total  = season.get("episodes", 0)
        ep_list   = season.setdefault("ep_watched", [False] * ep_total)
        while len(ep_list) < ep_total:
            ep_list.append(False)
        ep_watched = sum(1 for w in ep_list if w)
        pct = int(ep_watched / ep_total * 100) if ep_total else 0
        dur = season.get("ep_duration", DEFAULT_EP_DURATION)
        time_min = ep_watched * dur

        card = tk.Frame(parent, bg=C["surface"],
                        highlightthickness=1, highlightbackground=C["border"])
        card.pack(fill="x", pady=6)

        # Header
        hdr = tk.Frame(card, bg=C["surface"])
        hdr.pack(fill="x", padx=12, pady=(10, 4))

        s_name_lbl = tk.Label(hdr, text=season["name"],
                             font=("Segoe UI", 10, "bold"),
                             bg=C["surface"], fg=C["anime"], cursor="hand2")
        s_name_lbl.pack(side="left")

        tk.Label(hdr, text=f"{ep_watched}/{ep_total} eps  ·  {pct}%  ·  {dur} min/ep  ·  {time_min} min watched",
                 font=("Segoe UI", 8),
                 bg=C["surface"], fg=C["muted"]).pack(side="left", padx=12)

        # Season actions
        btn_frame = tk.Frame(hdr, bg=C["surface"])
        btn_frame.pack(side="right")

        tk.Button(btn_frame, text="🗑",
                  font=("Segoe UI", 8), bg=C["surface"], fg=C["danger"],
                  relief="flat", cursor="hand2",
                  command=lambda: self._delete_season(entry, kind, s_idx, tab_parent)
                  ).pack(side="right", padx=2)

        tk.Button(btn_frame, text="✏",
                  font=("Segoe UI", 8), bg=C["surface"], fg=C["muted"],
                  relief="flat", cursor="hand2",
                  command=lambda si=s_idx, lbl=s_name_lbl: self._rename_season(entry, kind, si, lbl, tab_parent)
                  ).pack(side="right", padx=2)

        # Progress bar
        bar = tk.Frame(card, bg=C["bar_bg"], height=6)
        bar.pack(fill="x", padx=12, pady=(0, 6))
        if pct > 0:
            fill_c = C["completed"] if pct >= 100 else C["anime"]
            tk.Frame(bar, bg=fill_c, height=6).place(relwidth=pct/100, relheight=1)

        # Bulk actions
        bulk = tk.Frame(card, bg=C["surface"])
        bulk.pack(fill="x", padx=12, pady=(0, 4))

        tk.Button(bulk, text="✓ Watch All",
                  font=("Segoe UI", 8), bg=C["completed"], fg=C["white"],
                  relief="flat", cursor="hand2", padx=6, pady=2,
                  command=lambda si=s_idx: self._bulk_watch(entry, kind, si, 0, ep_total-1, True, tab_parent)
                  ).pack(side="left", padx=(0, 4))

        tk.Button(bulk, text="✗ Unwatch All",
                  font=("Segoe UI", 8), bg=C["border"], fg=C["text"],
                  relief="flat", cursor="hand2", padx=6, pady=2,
                  command=lambda si=s_idx: self._bulk_watch(entry, kind, si, 0, ep_total-1, False, tab_parent)
                  ).pack(side="left", padx=(0, 8))

        # Range input
        tk.Label(bulk, text="Range:", font=("Segoe UI", 8),
                 bg=C["surface"], fg=C["muted"]).pack(side="left", padx=(8, 4))

        from_e = tk.Entry(bulk, width=5, font=("Segoe UI", 8),
                          bg=C["card"], fg=C["text"], relief="flat",
                          insertbackground=C["text"],
                          highlightthickness=1, highlightbackground=C["border"])
        from_e.pack(side="left", ipady=2)

        tk.Label(bulk, text="–", font=("Segoe UI", 8),
                 bg=C["surface"], fg=C["muted"]).pack(side="left", padx=2)

        to_e = tk.Entry(bulk, width=5, font=("Segoe UI", 8),
                        bg=C["card"], fg=C["text"], relief="flat",
                        insertbackground=C["text"],
                        highlightthickness=1, highlightbackground=C["border"])
        to_e.pack(side="left", ipady=2)

        tk.Button(bulk, text="Mark Watched",
                  font=("Segoe UI", 8), bg=C["accent"], fg=C["white"],
                  relief="flat", cursor="hand2", padx=6, pady=2,
                  command=lambda si=s_idx: self._range_watch(entry, kind, si, from_e, to_e, True, tab_parent)
                  ).pack(side="left", padx=(6, 0))

        # Episode grid
        ep_frame = tk.Frame(card, bg=C["surface"])
        ep_frame.pack(fill="x", padx=12, pady=(4, 10))

        ECOLS = 16
        for ep in range(ep_total):
            r, c = divmod(ep, ECOLS)
            is_w = ep_list[ep]
            bg = C["completed"] if is_w else C["bar_bg"]
            fg = C["white"] if is_w else C["muted"]
            btn = tk.Button(ep_frame, text=str(ep+1),
                            font=("Segoe UI", 7), bg=bg, fg=fg,
                            relief="flat", cursor="hand2",
                            width=3, height=1,
                            command=lambda e=ep, si=s_idx: self._toggle_ep(entry, kind, si, e, tab_parent))
            btn.grid(row=r, column=c, padx=1, pady=1)

    def _add_season_dialog(self, entry, kind, tab_parent):
        win = tk.Toplevel(self)
        win.title("Add Season")
        win.geometry("380x260")
        win.configure(bg=C["bg"])
        win.resizable(False, False)
        win.grab_set()

        form = tk.Frame(win, bg=C["bg"])
        form.pack(fill="both", expand=True, padx=24, pady=20)

        n = len(entry.get("seasons", [])) + 1
        tk.Label(form, text="Add Season", font=("Segoe UI", 12, "bold"),
                 bg=C["bg"], fg=C["text"]).grid(row=0, column=0, columnspan=2,
                                                  sticky="w", pady=(0, 14))

        tk.Label(form, text="Name", font=("Segoe UI", 9),
                 bg=C["bg"], fg=C["muted"]).grid(row=1, column=0, sticky="w", pady=5, padx=(0, 14))
        name_e = tk.Entry(form, font=("Segoe UI", 10),
                          bg=C["surface"], fg=C["text"],
                          insertbackground=C["text"], relief="flat", width=22,
                          highlightthickness=1, highlightbackground=C["border"])
        name_e.insert(0, f"Season {n}")
        name_e.grid(row=1, column=1, pady=5, ipady=5)

        tk.Label(form, text="Episodes", font=("Segoe UI", 9),
                 bg=C["bg"], fg=C["muted"]).grid(row=2, column=0, sticky="w", pady=5)
        ep_e = tk.Entry(form, font=("Segoe UI", 10),
                        bg=C["surface"], fg=C["text"],
                        insertbackground=C["text"], relief="flat", width=22,
                        highlightthickness=1, highlightbackground=C["border"])
        ep_e.grid(row=2, column=1, pady=5, ipady=5)

        tk.Label(form, text="Duration (min/ep)", font=("Segoe UI", 9),
                 bg=C["bg"], fg=C["muted"]).grid(row=3, column=0, sticky="w", pady=5)
        dur_e = tk.Entry(form, font=("Segoe UI", 10),
                         bg=C["surface"], fg=C["text"],
                         insertbackground=C["text"], relief="flat", width=22,
                         highlightthickness=1, highlightbackground=C["border"])
        dur_e.insert(0, str(DEFAULT_EP_DURATION))
        dur_e.grid(row=3, column=1, pady=5, ipady=5)

        def submit():
            name = name_e.get().strip() or f"Season {n}"
            try:
                eps = int(ep_e.get())
                if eps <= 0: raise ValueError
            except ValueError:
                messagebox.showerror("Invalid", "Enter a valid episode count.", parent=win)
                return
            try:
                dur = int(dur_e.get())
                if dur <= 0: raise ValueError
            except ValueError:
                dur = DEFAULT_EP_DURATION

            entry.setdefault("seasons", []).append({
                "name":        name,
                "episodes":    eps,
                "ep_watched":  [False] * eps,
                "ep_duration": dur,
            })
            self._save(kind, entry)
            win.destroy()
            self._build_seasons_panel(tab_parent, entry, kind)
            self.refresh_library(kind)

        tk.Button(form, text="  +  Add Season  ",
                  font=("Segoe UI", 10, "bold"),
                  bg=C["accent"], fg=C["white"], relief="flat",
                  cursor="hand2", padx=12, pady=8, command=submit
                  ).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(12, 0))

    def _rename_season(self, entry, kind, s_idx, lbl, tab_parent):
        current = entry["seasons"][s_idx]["name"]
        win = tk.Toplevel(self)
        win.title("Rename Season")
        win.geometry("360x140")
        win.configure(bg=C["bg"])
        win.resizable(False, False)
        win.grab_set()

        form = tk.Frame(win, bg=C["bg"])
        form.pack(fill="both", expand=True, padx=24, pady=20)

        tk.Label(form, text="Rename Season", font=("Segoe UI", 12, "bold"),
                 bg=C["bg"], fg=C["text"]).pack(anchor="w", pady=(0, 10))

        name_e = tk.Entry(form, font=("Segoe UI", 11),
                          bg=C["surface"], fg=C["text"],
                          insertbackground=C["text"], relief="flat", width=32,
                          highlightthickness=1, highlightbackground=C["border"],
                          highlightcolor=C["accent"])
        name_e.insert(0, current)
        name_e.pack(fill="x", ipady=5, pady=(0, 10))
        name_e.focus_set()
        name_e.select_range(0, "end")

        def save():
            new_name = name_e.get().strip()
            if new_name and new_name != current:
                entry["seasons"][s_idx]["name"] = new_name
                self._save(kind, entry)
                self._build_seasons_panel(tab_parent, entry, kind)
                self.refresh_library(kind)
            win.destroy()

        name_e.bind("<Return>", lambda e: save())
        tk.Button(form, text="  Save  ", font=("Segoe UI", 9, "bold"),
                  bg=C["accent"], fg=C["white"], relief="flat",
                  cursor="hand2", padx=12, pady=6, command=save).pack(anchor="e")

    def _search_add_season(self, entry, kind, tab_parent):
        """Search MAL for a season and add it with auto-filled data."""
        import re as _re

        win = tk.Toplevel(self)
        win.title(f"Search Season — {entry['title']}")
        win.geometry("540x500")
        win.configure(bg=C["bg"])
        win.resizable(False, True)
        win.grab_set()

        color = C["anime"]
        tk.Frame(win, bg=color, height=3).pack(fill="x")

        # Search bar
        top = tk.Frame(win, bg=C["surface"])
        top.pack(fill="x")

        tk.Label(top, text=f"  Search MAL for a season of '{entry['title']}'",
                 font=("Segoe UI", 10, "bold"),
                 bg=C["surface"], fg=C["text"]).pack(anchor="w", padx=12, pady=(10, 6))

        search_row = tk.Frame(top, bg=C["surface"])
        search_row.pack(fill="x", padx=12, pady=(0, 10))

        search_e = tk.Entry(search_row, font=("Segoe UI", 10),
                            bg=C["card"], fg=C["text"],
                            insertbackground=C["text"], relief="flat", width=30,
                            highlightthickness=1, highlightbackground=C["border"],
                            highlightcolor=C["accent"])
        search_e.insert(0, entry["title"])
        search_e.pack(side="left", ipady=5, padx=(0, 8))

        status_lbl = tk.Label(search_row, text="", font=("Segoe UI", 8),
                               bg=C["surface"], fg=C["muted"])
        status_lbl.pack(side="left", padx=4)

        search_btn = tk.Button(search_row, text="  Search  ",
                               font=("Segoe UI", 9, "bold"),
                               bg=color, fg=C["white"], relief="flat",
                               cursor="hand2", padx=10, pady=4)
        search_btn.pack(side="right")

        # Results area with scroll
        results_outer = tk.Frame(win, bg=C["bg"])
        results_outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(results_outer, bg=C["bg"], highlightthickness=0)
        sb = ttk.Scrollbar(results_outer, orient="vertical", command=canvas.yview)
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
            elif event.num == 4:
                canvas.yview_scroll(-3, "units")
            elif event.num == 5:
                canvas.yview_scroll(3, "units")

        canvas.bind_all("<MouseWheel>", _mw)
        canvas.bind_all("<Button-4>", _mw)
        canvas.bind_all("<Button-5>", _mw)

        def _on_close():
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", _on_close)

        def do_search():
            query = search_e.get().strip()
            if not query:
                return
            status_lbl.config(text="Searching...", fg=C["accent"])
            search_btn.config(state="disabled")
            win.update_idletasks()

            def _thread():
                results = jikan_search_anime(query, limit=25)
                win.after(0, lambda: show_results(results))

            threading.Thread(target=_thread, daemon=True).start()

        def show_results(results):
            search_btn.config(state="normal")
            for w in inner.winfo_children():
                w.destroy()

            if not results:
                status_lbl.config(text="No results.", fg=C["danger"])
                return

            status_lbl.config(text=f"{len(results)} results", fg=C["success"])

            for i, r in enumerate(results):
                title_api = r.get("title", "")
                title_en  = r.get("title_english") or ""
                eps       = r.get("episodes") or "?"
                score_api = r.get("score", "—")
                mal_type  = r.get("type", "")
                dur_raw   = r.get("duration", "")
                status_api = r.get("status", "")
                year = ""
                aired = r.get("aired")
                if aired and aired.get("from"):
                    year = aired["from"][:4]

                row_bg = C["surface"] if i % 2 == 0 else C["card"]
                row = tk.Frame(inner, bg=row_bg)
                row.pack(fill="x", pady=1, padx=8)

                info = tk.Frame(row, bg=row_bg)
                info.pack(side="left", fill="x", expand=True, padx=8, pady=6)

                tk.Label(info, text=title_api[:55], font=("Segoe UI", 9, "bold"),
                         bg=row_bg, fg=C["text"], anchor="w").pack(anchor="w")

                if title_en and title_en != title_api:
                    tk.Label(info, text=title_en[:50], font=("Segoe UI", 7),
                             bg=row_bg, fg=C["muted"], anchor="w").pack(anchor="w")

                sub = f"{mal_type} · {eps} eps · {dur_raw} · ★{score_api} · {year} · {status_api}"
                tk.Label(info, text=sub, font=("Segoe UI", 7),
                         bg=row_bg, fg=C["muted"], anchor="w").pack(anchor="w")

                tk.Button(row, text="+ Add as Season",
                          font=("Segoe UI", 8, "bold"),
                          bg=C["success"], fg=C["white"], relief="flat",
                          cursor="hand2", padx=10, pady=4,
                          command=lambda res=r: add_from_result(res)
                          ).pack(side="right", padx=8, pady=8)

        def add_from_result(r):
            title_api = r.get("title", "Season")
            eps       = r.get("episodes")
            dur_raw   = r.get("duration", "")

            # Parse duration
            dur = DEFAULT_EP_DURATION
            if dur_raw:
                hr_match  = _re.search(r"(\d+)\s*hr", dur_raw)
                min_match = _re.search(r"(\d+)\s*min", dur_raw)
                dur = 0
                if hr_match:
                    dur += int(hr_match.group(1)) * 60
                if min_match:
                    dur += int(min_match.group(1))
                if dur == 0:
                    dur = DEFAULT_EP_DURATION

            if not eps or eps == "?":
                messagebox.showwarning("Unknown Episodes",
                    f"'{title_api}' has no episode count on MAL.\n"
                    f"You can add it manually instead.", parent=win)
                return

            entry.setdefault("seasons", []).append({
                "name":        title_api,
                "episodes":    eps,
                "ep_watched":  [False] * eps,
                "ep_duration": dur,
                "mal_id":      r.get("mal_id"),
            })
            self._save(kind, entry)
            self._build_seasons_panel(tab_parent, entry, kind)
            self.refresh_library(kind)
            status_lbl.config(text=f"Added: {title_api} ({eps} eps, {dur}min/ep)", fg=C["success"])

        search_btn.config(command=do_search)
        search_e.bind("<Return>", lambda e: do_search())

    def _toggle_ep(self, entry, kind, s_idx, ep_idx, tab_parent):
        wl = entry["seasons"][s_idx]["ep_watched"]
        wl[ep_idx] = not wl[ep_idx]
        self._save(kind, entry)
        self._build_seasons_panel(tab_parent, entry, kind)
        self.refresh_library(kind)

    def _bulk_watch(self, entry, kind, s_idx, start, end, value, tab_parent):
        wl = entry["seasons"][s_idx]["ep_watched"]
        for i in range(start, min(end + 1, len(wl))):
            wl[i] = value
        self._save(kind, entry)
        self._build_seasons_panel(tab_parent, entry, kind)
        self.refresh_library(kind)

    def _range_watch(self, entry, kind, s_idx, from_e, to_e, value, tab_parent):
        try:
            start = int(from_e.get()) - 1
            end   = int(to_e.get()) - 1
            if start < 0 or end < start:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Range", "Enter valid episode numbers (e.g. 1 – 12).")
            return
        self._bulk_watch(entry, kind, s_idx, start, end, value, tab_parent)

    def _delete_season(self, entry, kind, s_idx, tab_parent):
        if not messagebox.askyesno("Delete Season", "Delete this season and all its data?"):
            return
        entry["seasons"].pop(s_idx)
        self._save(kind, entry)
        self._build_seasons_panel(tab_parent, entry, kind)
        self.refresh_library(kind)

    # ══════════════════════════════════════════════════════════════════════════
    #  MOVIES / OVAs LIST
    # ══════════════════════════════════════════════════════════════════════════
    def _build_simple_list(self, parent, entry, kind, field, label):
        for w in parent.winfo_children():
            w.destroy()

        toolbar = tk.Frame(parent, bg=C["bg"])
        toolbar.pack(fill="x", padx=8, pady=(10, 6))
        tk.Label(toolbar, text=f"{label}s", font=("Segoe UI", 11, "bold"),
                 bg=C["bg"], fg=C["text"]).pack(side="left")
        tk.Button(toolbar, text=f"  +  Manual  ",
                  font=("Segoe UI", 9, "bold"),
                  bg=C["accent2"], fg=C["white"], relief="flat",
                  cursor="hand2", padx=8, pady=4,
                  command=lambda: self._add_simple_item(entry, kind, field, label, parent)
                  ).pack(side="right")
        if kind == "anime":
            tk.Button(toolbar, text=f"  🔍  Search MAL  ",
                      font=("Segoe UI", 9, "bold"),
                      bg=C["anime"], fg=C["white"], relief="flat",
                      cursor="hand2", padx=8, pady=4,
                      command=lambda: self._search_add_simple(entry, kind, field, label, parent)
                      ).pack(side="right", padx=(0, 6))

        items = entry.get(field, [])
        if not items:
            tk.Label(parent, text=f"No {label}s added yet.",
                     font=("Segoe UI", 9), bg=C["bg"], fg=C["muted"]).pack(pady=30)
            return

        for i, item in enumerate(items):
            row = tk.Frame(parent, bg=C["surface"],
                           highlightthickness=1, highlightbackground=C["border"])
            row.pack(fill="x", padx=8, pady=3)

            is_w = item.get("watched", False)
            tc = C["completed"] if is_w else C["bar_bg"]
            tk.Button(row, text="✔" if is_w else "○",
                      font=("Segoe UI", 10, "bold"),
                      bg=tc, fg=C["white"] if is_w else C["muted"],
                      relief="flat", cursor="hand2", width=3, pady=6,
                      command=lambda idx=i: self._toggle_simple(entry, kind, field, label, idx, parent)
                      ).pack(side="left", padx=(8, 10), pady=6)

            tk.Label(row, text=item.get("title", f"{label} {i+1}"),
                     font=("Segoe UI", 10),
                     bg=C["surface"], fg=C["text"]).pack(side="left")

            dur = item.get("duration", "")
            if dur:
                tk.Label(row, text=f"{dur} min",
                         font=("Segoe UI", 8), bg=C["surface"], fg=C["muted"]).pack(side="left", padx=10)

            tk.Button(row, text="🗑", font=("Segoe UI", 8),
                      bg=C["surface"], fg=C["danger"], relief="flat", cursor="hand2",
                      command=lambda idx=i: self._delete_simple(entry, kind, field, label, idx, parent)
                      ).pack(side="right", padx=8)

    def _add_simple_item(self, entry, kind, field, label, tab_parent):
        win = tk.Toplevel(self)
        win.title(f"Add {label}")
        win.geometry("380x220")
        win.configure(bg=C["bg"])
        win.resizable(False, False)
        win.grab_set()

        form = tk.Frame(win, bg=C["bg"])
        form.pack(fill="both", expand=True, padx=24, pady=20)

        tk.Label(form, text=f"Add {label}", font=("Segoe UI", 12, "bold"),
                 bg=C["bg"], fg=C["text"]).grid(row=0, column=0, columnspan=2,
                                                  sticky="w", pady=(0, 14))

        tk.Label(form, text="Title", font=("Segoe UI", 9),
                 bg=C["bg"], fg=C["muted"]).grid(row=1, column=0, sticky="w", pady=5, padx=(0, 14))
        t_e = tk.Entry(form, font=("Segoe UI", 10),
                       bg=C["surface"], fg=C["text"],
                       insertbackground=C["text"], relief="flat", width=22,
                       highlightthickness=1, highlightbackground=C["border"])
        t_e.grid(row=1, column=1, pady=5, ipady=5)

        tk.Label(form, text="Duration (min)", font=("Segoe UI", 9),
                 bg=C["bg"], fg=C["muted"]).grid(row=2, column=0, sticky="w", pady=5)
        d_e = tk.Entry(form, font=("Segoe UI", 10),
                       bg=C["surface"], fg=C["text"],
                       insertbackground=C["text"], relief="flat", width=22,
                       highlightthickness=1, highlightbackground=C["border"])
        d_e.insert(0, "90" if field == "movies" else str(DEFAULT_EP_DURATION))
        d_e.grid(row=2, column=1, pady=5, ipady=5)

        def submit():
            title = t_e.get().strip()
            if not title:
                messagebox.showerror("Required", "Title is required.", parent=win)
                return
            try:
                dur = int(d_e.get())
            except ValueError:
                dur = 90 if field == "movies" else DEFAULT_EP_DURATION
            entry.setdefault(field, []).append({
                "title": title, "duration": dur, "watched": False,
            })
            self._save(kind, entry)
            win.destroy()
            self._build_simple_list(tab_parent, entry, kind, field, label)

        tk.Button(form, text=f"  +  Add {label}  ",
                  font=("Segoe UI", 10, "bold"),
                  bg=C["accent2"], fg=C["white"], relief="flat",
                  cursor="hand2", padx=12, pady=8, command=submit
                  ).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(12, 0))

    def _search_add_simple(self, entry, kind, field, label, tab_parent):
        """Search MAL for a movie/OVA and add it."""
        import re as _re

        win = tk.Toplevel(self)
        search_type = "Movie" if field == "movies" else "OVA"
        win.title(f"Search {search_type} — {entry['title']}")
        win.geometry("540x460")
        win.configure(bg=C["bg"])
        win.resizable(False, True)
        win.grab_set()

        tk.Frame(win, bg=C["accent2"], height=3).pack(fill="x")

        top = tk.Frame(win, bg=C["surface"])
        top.pack(fill="x")
        tk.Label(top, text=f"  Search MAL for {search_type}s",
                 font=("Segoe UI", 10, "bold"),
                 bg=C["surface"], fg=C["text"]).pack(anchor="w", padx=12, pady=(10, 6))

        search_row = tk.Frame(top, bg=C["surface"])
        search_row.pack(fill="x", padx=12, pady=(0, 10))

        search_e = tk.Entry(search_row, font=("Segoe UI", 10),
                            bg=C["card"], fg=C["text"],
                            insertbackground=C["text"], relief="flat", width=30,
                            highlightthickness=1, highlightbackground=C["border"])
        search_e.insert(0, entry["title"] + f" {search_type.lower()}")
        search_e.pack(side="left", ipady=5, padx=(0, 8))

        status_lbl = tk.Label(search_row, text="", font=("Segoe UI", 8),
                               bg=C["surface"], fg=C["muted"])
        status_lbl.pack(side="left", padx=4)

        search_btn = tk.Button(search_row, text="  Search  ",
                               font=("Segoe UI", 9, "bold"),
                               bg=C["accent2"], fg=C["white"], relief="flat",
                               cursor="hand2", padx=10, pady=4)
        search_btn.pack(side="right")

        results_outer = tk.Frame(win, bg=C["bg"])
        results_outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(results_outer, bg=C["bg"], highlightthickness=0)
        sb = ttk.Scrollbar(results_outer, orient="vertical", command=canvas.yview)
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
            elif event.num == 4:
                canvas.yview_scroll(-3, "units")
            elif event.num == 5:
                canvas.yview_scroll(3, "units")

        canvas.bind_all("<MouseWheel>", _mw)
        canvas.bind_all("<Button-4>", _mw)
        canvas.bind_all("<Button-5>", _mw)

        def _on_close():
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", _on_close)

        def do_search():
            query = search_e.get().strip()
            if not query:
                return
            status_lbl.config(text="Searching...", fg=C["accent"])
            search_btn.config(state="disabled")
            win.update_idletasks()

            def _thread():
                results = jikan_search_anime(query, limit=25)
                win.after(0, lambda: show_results(results))

            threading.Thread(target=_thread, daemon=True).start()

        def show_results(results):
            search_btn.config(state="normal")
            for w in inner.winfo_children():
                w.destroy()

            if not results:
                status_lbl.config(text="No results.", fg=C["danger"])
                return

            status_lbl.config(text=f"{len(results)} results", fg=C["success"])

            for i, r in enumerate(results):
                title_api = r.get("title", "")
                mal_type  = r.get("type", "")
                dur_raw   = r.get("duration", "")
                score_api = r.get("score", "—")
                year = ""
                aired = r.get("aired")
                if aired and aired.get("from"):
                    year = aired["from"][:4]

                row_bg = C["surface"] if i % 2 == 0 else C["card"]
                row = tk.Frame(inner, bg=row_bg)
                row.pack(fill="x", pady=1, padx=8)

                info = tk.Frame(row, bg=row_bg)
                info.pack(side="left", fill="x", expand=True, padx=8, pady=6)

                tk.Label(info, text=title_api[:55], font=("Segoe UI", 9, "bold"),
                         bg=row_bg, fg=C["text"], anchor="w").pack(anchor="w")

                sub = f"{mal_type} · {dur_raw} · ★{score_api} · {year}"
                tk.Label(info, text=sub, font=("Segoe UI", 7),
                         bg=row_bg, fg=C["muted"], anchor="w").pack(anchor="w")

                tk.Button(row, text=f"+ Add as {label}",
                          font=("Segoe UI", 8, "bold"),
                          bg=C["success"], fg=C["white"], relief="flat",
                          cursor="hand2", padx=10, pady=4,
                          command=lambda res=r: add_from_result(res)
                          ).pack(side="right", padx=8, pady=8)

        def add_from_result(r):
            title_api = r.get("title", label)
            dur_raw   = r.get("duration", "")

            dur = 90 if field == "movies" else DEFAULT_EP_DURATION
            if dur_raw:
                hr_match  = _re.search(r"(\d+)\s*hr", dur_raw)
                min_match = _re.search(r"(\d+)\s*min", dur_raw)
                parsed = 0
                if hr_match:
                    parsed += int(hr_match.group(1)) * 60
                if min_match:
                    parsed += int(min_match.group(1))
                if parsed > 0:
                    dur = parsed

            entry.setdefault(field, []).append({
                "title":   title_api,
                "duration": dur,
                "watched": False,
                "mal_id":  r.get("mal_id"),
            })
            self._save(kind, entry)
            self._build_simple_list(tab_parent, entry, kind, field, label)
            status_lbl.config(text=f"Added: {title_api} ({dur}min)", fg=C["success"])

        search_btn.config(command=do_search)
        search_e.bind("<Return>", lambda e: do_search())

    def _toggle_simple(self, entry, kind, field, label, idx, tab_parent):
        entry[field][idx]["watched"] = not entry[field][idx].get("watched", False)
        self._save(kind, entry)
        self._build_simple_list(tab_parent, entry, kind, field, label)
        self.refresh_library(kind)

    def _delete_simple(self, entry, kind, field, label, idx, tab_parent):
        if not messagebox.askyesno(f"Delete {label}", f"Delete this {label}?"):
            return
        entry[field].pop(idx)
        self._save(kind, entry)
        self._build_simple_list(tab_parent, entry, kind, field, label)
        self.refresh_library(kind)

    # ══════════════════════════════════════════════════════════════════════════
    #  MANGA PANEL
    # ══════════════════════════════════════════════════════════════════════════
    def _build_manga_panel(self, parent, entry, kind):
        frame = tk.Frame(parent, bg=C["bg"])
        frame.pack(fill="both", expand=True, padx=16, pady=10)

        # ── Continuation from anime ───────────────────────────────────────
        cont_card = tk.Frame(frame, bg=C["surface"],
                             highlightthickness=1, highlightbackground=C["border"])
        cont_card.pack(fill="x", pady=(0, 12))

        tk.Label(cont_card, text="  Manga Continuation", font=("Segoe UI", 10, "bold"),
                 bg=C["surface"], fg=C["text"]).pack(anchor="w", padx=12, pady=(12, 4))

        tk.Label(cont_card,
                 text="If you're continuing the manga from where the anime stopped,\nenter the starting chapter below.",
                 font=("Segoe UI", 8), bg=C["surface"], fg=C["muted"],
                 justify="left").pack(anchor="w", padx=12, pady=(0, 8))

        cont_row = tk.Frame(cont_card, bg=C["surface"])
        cont_row.pack(fill="x", padx=12, pady=(0, 12))

        cont_var = tk.BooleanVar(value=entry.get("continued_from_anime", False))
        tk.Checkbutton(cont_row, text="Continued from anime",
                       variable=cont_var, font=("Segoe UI", 9),
                       bg=C["surface"], fg=C["text"],
                       selectcolor=C["card"], activebackground=C["surface"],
                       command=lambda: self._update_field(entry, kind, "continued_from_anime", cont_var.get())
                       ).pack(side="left")

        tk.Label(cont_row, text="Starting Chapter:", font=("Segoe UI", 9),
                 bg=C["surface"], fg=C["muted"]).pack(side="left", padx=(16, 6))
        start_var = tk.StringVar(value=str(entry.get("chapter_start", 0)))
        start_e = tk.Entry(cont_row, textvariable=start_var, width=7,
                           font=("Segoe UI", 10, "bold"),
                           bg=C["card"], fg=C["manga"],
                           insertbackground=C["text"], relief="flat",
                           highlightthickness=1, highlightbackground=C["border"])
        start_e.pack(side="left", ipady=3)
        start_e.bind("<FocusOut>", lambda e: self._save_chapter_start(entry, kind, start_var))

        # ── Chapter progress ──────────────────────────────────────────────
        prog_card = tk.Frame(frame, bg=C["surface"],
                             highlightthickness=1, highlightbackground=C["border"])
        prog_card.pack(fill="x", pady=(0, 12))

        tk.Label(prog_card, text="  Chapter Progress", font=("Segoe UI", 10, "bold"),
                 bg=C["surface"], fg=C["text"]).pack(anchor="w", padx=12, pady=(12, 8))

        prog_row = tk.Frame(prog_card, bg=C["surface"])
        prog_row.pack(fill="x", padx=12, pady=(0, 6))

        tk.Label(prog_row, text="Chapters Read:", font=("Segoe UI", 9),
                 bg=C["surface"], fg=C["muted"]).pack(side="left", padx=(0, 6))
        read_var = tk.StringVar(value=str(entry.get("chapters_read", 0)))
        read_e = tk.Entry(prog_row, textvariable=read_var, width=7,
                          font=("Segoe UI", 11, "bold"),
                          bg=C["card"], fg=C["manga"],
                          insertbackground=C["text"], relief="flat",
                          highlightthickness=1, highlightbackground=C["border"])
        read_e.pack(side="left", ipady=4, padx=(0, 16))

        tk.Label(prog_row, text="Total Chapters:", font=("Segoe UI", 9),
                 bg=C["surface"], fg=C["muted"]).pack(side="left", padx=(0, 6))
        total_var = tk.StringVar(value=str(entry.get("chapters_total", 0)))
        total_e = tk.Entry(prog_row, textvariable=total_var, width=7,
                           font=("Segoe UI", 11, "bold"),
                           bg=C["card"], fg=C["muted"],
                           insertbackground=C["text"], relief="flat",
                           highlightthickness=1, highlightbackground=C["border"])
        total_e.pack(side="left", ipady=4)

        tk.Label(prog_row, text="(0 = ongoing)",
                 font=("Segoe UI", 7), bg=C["surface"], fg=C["muted"]).pack(side="left", padx=6)

        # Quick actions
        action_row = tk.Frame(prog_card, bg=C["surface"])
        action_row.pack(fill="x", padx=12, pady=(4, 6))

        def mark_rest_read():
            try:
                total = int(total_var.get() or 0)
                start = int(start_var.get() or 0)
                if total > 0 and start > 0:
                    remaining = total - start
                    if remaining > 0:
                        read_var.set(str(remaining))
                        update()
                elif total > 0:
                    read_var.set(str(total))
                    update()
            except ValueError:
                pass

        tk.Button(action_row, text="  ✓  Read All Remaining  ",
                  font=("Segoe UI", 8, "bold"),
                  bg=C["success"], fg=C["white"], relief="flat",
                  cursor="hand2", padx=8, pady=3,
                  command=mark_rest_read).pack(side="left", padx=(0, 8))

        # Progress bar + summary
        bar_frame = tk.Frame(prog_card, bg=C["surface"])
        bar_frame.pack(fill="x", padx=12, pady=(0, 4))

        bar = tk.Frame(bar_frame, bg=C["bar_bg"], height=10)
        bar.pack(fill="x")
        fill = tk.Frame(bar, bg=C["manga"], height=10)

        summary_lbl = tk.Label(prog_card, text="", font=("Segoe UI", 9),
                               bg=C["surface"], fg=C["text"])
        summary_lbl.pack(anchor="w", padx=12, pady=(2, 12))

        def update():
            try:
                read  = int(read_var.get() or 0)
                total = int(total_var.get() or 0)
                start = int(start_var.get() or 0)
                entry["chapters_read"]  = max(0, read)
                entry["chapters_total"] = max(0, total)
                self._save(kind, entry)

                # Smart progress calculation
                if start > 0 and total > 0:
                    # Continuation mode: progress is relative to start→total
                    chapters_remaining = total - start
                    if chapters_remaining > 0:
                        pct = min(read / chapters_remaining, 1.0)
                    else:
                        pct = 1.0 if read > 0 else 0.0
                    fill.place(relwidth=pct, relheight=1)
                    fill.config(bg=C["success"] if pct >= 1.0 else C["manga"])
                    current_ch = start + read
                    txt = f"{read} / {chapters_remaining} chapters  ({int(pct*100)}%)"
                    txt += f"  ·  ch. {start} → ch. {current_ch}"
                    if pct >= 1.0:
                        txt += "  ✓ Finished!"
                elif total > 0:
                    # Normal mode: read / total
                    pct = min(read / total, 1.0)
                    fill.place(relwidth=pct, relheight=1)
                    fill.config(bg=C["success"] if pct >= 1.0 else C["manga"])
                    txt = f"{read} / {total} chapters  ({int(pct*100)}%)"
                    if pct >= 1.0:
                        txt += "  ✓ Finished!"
                else:
                    fill.place(relwidth=0, relheight=1)
                    txt = f"{read} chapters read (ongoing)"
                    if start > 0:
                        txt += f"  ·  started from ch. {start}  →  currently at ch. {start + read}"

                summary_lbl.config(text=txt)
                self.refresh_library(kind)
            except ValueError:
                pass

        read_e.bind("<FocusOut>",  lambda e: update())
        total_e.bind("<FocusOut>", lambda e: update())
        update()

    def _save_chapter_start(self, entry, kind, var):
        try:
            entry["chapter_start"] = max(0, int(var.get() or 0))
        except ValueError:
            entry["chapter_start"] = 0
        self._save(kind, entry)

    # ══════════════════════════════════════════════════════════════════════════
    #  SHARED HELPERS
    # ══════════════════════════════════════════════════════════════════════════
    def _update_field(self, entry, kind, field, value):
        entry[field] = value
        self._save(kind, entry)
        self.refresh_library(kind)

    def _save_score(self, entry, kind, var):
        raw = var.get().strip()
        if not raw:
            entry["score"] = None
        else:
            try:
                s = int(raw)
                entry["score"] = max(0, min(100, s))
                var.set(str(entry["score"]))
            except ValueError:
                var.set("")
                entry["score"] = None
        self._save(kind, entry)
        self.refresh_library(kind)

    def _save_notes(self, entry, kind, widget):
        entry["notes"] = widget.get("1.0", "end").strip()
        self._save(kind, entry)

    def _save(self, kind, entry=None):
        if entry:
            # Save a specific entry
            if kind == "anime":
                self.db.save_anime(entry)
            else:
                self.db.save_manga(entry)
        else:
            # Save all (fallback)
            data = self.anime_data if kind == "anime" else self.manga_data
            for e in data:
                if kind == "anime":
                    self.db.save_anime(e)
                else:
                    self.db.save_manga(e)

    def _delete_entry(self, entry, kind, win):
        if not messagebox.askyesno("Delete", f"Delete '{entry['title']}' permanently?"):
            return
        if kind == "anime":
            self.db.delete_anime(entry["id"])
            self.anime_data = [e for e in self.anime_data if e["id"] != entry["id"]]
        else:
            self.db.delete_manga(entry["id"])
            self.manga_data = [e for e in self.manga_data if e["id"] != entry["id"]]
        win.destroy()
        self.refresh_all()

    def _update_header(self):
        a = anime_stats(self.anime_data)
        m = manga_stats(self.manga_data)
        self.hdr_stats.config(
            text=f"Anime: {a['total']} ({a['episodes']} eps · {a['hours']}h)   "
                 f"·   Manga: {m['total']} ({m['chapters']} ch)"
        )

    def refresh_all(self):
        # Reload from database
        self.anime_data = self.db.get_all_anime()
        self.manga_data = self.db.get_all_manga()
        self.refresh_library("anime")
        self.refresh_library("manga")
        self._refresh_anime_dashboard()
        self._refresh_manga_dashboard()
        self._update_header()


# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = AnimangaTracker()
    app.protocol("WM_DELETE_WINDOW", lambda: (app.db.close(), app.destroy()))
    app.mainloop()
