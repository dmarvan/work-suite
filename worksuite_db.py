"""
╔══════════════════════════════════════════════╗
║       WORK SUITE — Shared Database           ║
║  Single SQLite DB for all apps               ║
╚══════════════════════════════════════════════╝
"""

import sqlite3
import json
import time
from pathlib import Path
from datetime import datetime

DEFAULT_EP_DURATION = 24

def get_base():
    import sys
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent

BASE = get_base()
DATA_DIR   = BASE / "worksuite_data"
COVERS_DIR = DATA_DIR / "covers"
CACHE_DIR  = DATA_DIR / "cache"
DB_FILE    = DATA_DIR / "worksuite.db"

for d in (DATA_DIR, COVERS_DIR, CACHE_DIR):
    d.mkdir(parents=True, exist_ok=True)

# Legacy paths for migration
LEGACY_ANIME_JSON    = BASE / "animanga_data" / "anime.json"
LEGACY_MANGA_JSON    = BASE / "animanga_data" / "manga.json"
LEGACY_ANIMANGA_DB   = BASE / "animanga_data" / "animanga.db"
LEGACY_OVERTIME_JSON = BASE / "overtime_tracker_data.json"
LEGACY_PAYSLIP_JSON  = BASE / "payslip_tracker_data.json"

# Also check new data dir for files
NEW_OVERTIME_JSON    = DATA_DIR / "overtime_tracker_data.json"
NEW_PAYSLIP_JSON     = DATA_DIR / "payslip_tracker_data.json"


class WorkSuiteDB:
    """Unified SQLite database for all Work Suite apps."""

    def __init__(self):
        self.conn = sqlite3.connect(str(DB_FILE))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._create_all_tables()
        self._auto_migrate()

    # ══════════════════════════════════════════════════════════════════════
    #  SCHEMA
    # ══════════════════════════════════════════════════════════════════════
    def _create_all_tables(self):
        self.conn.executescript("""

            -- ═══════════════════════════════════════════════════════════════
            --  OVERTIME SCHEMA
            -- ═══════════════════════════════════════════════════════════════
            CREATE TABLE IF NOT EXISTS overtime_settings (
                key    TEXT PRIMARY KEY,
                value  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS overtime_entries (
                id     TEXT PRIMARY KEY,
                date   TEXT NOT NULL,
                type   TEXT NOT NULL CHECK(type IN ('overwork', 'overtime')),
                hours  REAL NOT NULL,
                rate   REAL NOT NULL,
                mult   REAL NOT NULL,
                pay    REAL NOT NULL,
                note   TEXT DEFAULT '',
                paid   INTEGER NOT NULL DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_overtime_date ON overtime_entries(date);
            CREATE INDEX IF NOT EXISTS idx_overtime_paid ON overtime_entries(paid);

            -- ═══════════════════════════════════════════════════════════════
            --  PAYSLIP SCHEMA
            -- ═══════════════════════════════════════════════════════════════
            CREATE TABLE IF NOT EXISTS payslip_entries (
                id       TEXT PRIMARY KEY,
                month    INTEGER NOT NULL,
                year     INTEGER NOT NULL,
                category TEXT NOT NULL DEFAULT 'salary'
                         CHECK(category IN ('salary', 'easter_bonus', 'christmas_bonus', 'summer_bonus')),
                salary   REAL NOT NULL DEFAULT 0,
                overtime REAL NOT NULL DEFAULT 0,
                gross    REAL NOT NULL DEFAULT 0,
                note     TEXT DEFAULT '',
                logged   TEXT,
                UNIQUE(year, month, category)
            );

            CREATE INDEX IF NOT EXISTS idx_payslip_year ON payslip_entries(year);

            -- ═══════════════════════════════════════════════════════════════
            --  ANIME SCHEMA
            -- ═══════════════════════════════════════════════════════════════
            CREATE TABLE IF NOT EXISTS anime (
                id         TEXT PRIMARY KEY,
                mal_id     INTEGER,
                title      TEXT NOT NULL,
                status     TEXT DEFAULT 'Watching',
                score      INTEGER,
                notes      TEXT DEFAULT '',
                cover      TEXT,
                added      TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS anime_seasons (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                anime_id    TEXT NOT NULL REFERENCES anime(id) ON DELETE CASCADE,
                name        TEXT NOT NULL,
                episodes    INTEGER NOT NULL DEFAULT 0,
                ep_duration INTEGER NOT NULL DEFAULT 24,
                mal_id      INTEGER,
                sort_order  INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS episode_progress (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                season_id   INTEGER NOT NULL REFERENCES anime_seasons(id) ON DELETE CASCADE,
                episode_num INTEGER NOT NULL,
                watched     INTEGER NOT NULL DEFAULT 0,
                is_filler   INTEGER NOT NULL DEFAULT 0,
                UNIQUE(season_id, episode_num)
            );

            CREATE TABLE IF NOT EXISTS anime_extras (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                anime_id  TEXT NOT NULL REFERENCES anime(id) ON DELETE CASCADE,
                category  TEXT NOT NULL CHECK(category IN ('movie', 'ova')),
                title     TEXT NOT NULL,
                duration  INTEGER DEFAULT 24,
                watched   INTEGER NOT NULL DEFAULT 0,
                mal_id    INTEGER
            );

            CREATE INDEX IF NOT EXISTS idx_anime_status ON anime(status);
            CREATE INDEX IF NOT EXISTS idx_seasons_anime ON anime_seasons(anime_id);
            CREATE INDEX IF NOT EXISTS idx_episodes_season ON episode_progress(season_id);
            CREATE INDEX IF NOT EXISTS idx_extras_anime ON anime_extras(anime_id);

            -- ═══════════════════════════════════════════════════════════════
            --  MANGA SCHEMA
            -- ═══════════════════════════════════════════════════════════════
            CREATE TABLE IF NOT EXISTS manga (
                id                   TEXT PRIMARY KEY,
                mal_id               INTEGER,
                title                TEXT NOT NULL,
                status               TEXT DEFAULT 'Reading',
                score                INTEGER,
                notes                TEXT DEFAULT '',
                cover                TEXT,
                added                TEXT,
                chapters_total       INTEGER DEFAULT 0,
                chapters_read        INTEGER DEFAULT 0,
                chapter_start        INTEGER DEFAULT 0,
                continued_from_anime INTEGER DEFAULT 0,
                created_at           TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_manga_status ON manga(status);
        """)
        self.conn.commit()

    # ══════════════════════════════════════════════════════════════════════
    #  AUTO-MIGRATION
    # ══════════════════════════════════════════════════════════════════════
    def _auto_migrate(self):
        self._migrate_animanga_db()
        self._migrate_overtime_json()
        self._migrate_payslip_json()

    def _migrate_animanga_db(self):
        """Migrate from old animanga.db if it exists and our anime table is empty."""
        anime_count = self.conn.execute("SELECT COUNT(*) FROM anime").fetchone()[0]
        if anime_count > 0:
            return

        old_db = LEGACY_ANIMANGA_DB
        if not old_db.exists():
            return

        print(f"[Migration] Found legacy animanga.db, importing...")
        src = sqlite3.connect(str(old_db))
        src.row_factory = sqlite3.Row

        # Anime
        for a in src.execute("SELECT * FROM anime").fetchall():
            self.conn.execute(
                "INSERT OR IGNORE INTO anime (id, mal_id, title, status, score, notes, cover, added, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (a["id"], a["mal_id"], a["title"], a["status"], a["score"],
                 a["notes"], a["cover"], a["added"], a["created_at"]))

        for s in src.execute("SELECT * FROM anime_seasons").fetchall():
            self.conn.execute(
                "INSERT INTO anime_seasons (id, anime_id, name, episodes, ep_duration, mal_id, sort_order) "
                "VALUES (?,?,?,?,?,?,?)",
                (s["id"], s["anime_id"], s["name"], s["episodes"],
                 s["ep_duration"], s["mal_id"], s["sort_order"]))

        for ep in src.execute("SELECT * FROM episode_progress").fetchall():
            self.conn.execute(
                "INSERT OR IGNORE INTO episode_progress (id, season_id, episode_num, watched, is_filler) "
                "VALUES (?,?,?,?,?)",
                (ep["id"], ep["season_id"], ep["episode_num"], ep["watched"], ep["is_filler"]))

        for ex in src.execute("SELECT * FROM anime_extras").fetchall():
            self.conn.execute(
                "INSERT INTO anime_extras (id, anime_id, category, title, duration, watched, mal_id) "
                "VALUES (?,?,?,?,?,?,?)",
                (ex["id"], ex["anime_id"], ex["category"], ex["title"],
                 ex["duration"], ex["watched"], ex["mal_id"]))

        # Fix autoincrement sequences
        max_season = src.execute("SELECT MAX(id) FROM anime_seasons").fetchone()[0] or 0
        max_ep = src.execute("SELECT MAX(id) FROM episode_progress").fetchone()[0] or 0
        max_ex = src.execute("SELECT MAX(id) FROM anime_extras").fetchone()[0] or 0
        self.conn.execute("INSERT OR REPLACE INTO sqlite_sequence (name, seq) VALUES ('anime_seasons', ?)", (max_season,))
        self.conn.execute("INSERT OR REPLACE INTO sqlite_sequence (name, seq) VALUES ('episode_progress', ?)", (max_ep,))
        self.conn.execute("INSERT OR REPLACE INTO sqlite_sequence (name, seq) VALUES ('anime_extras', ?)", (max_ex,))

        # Manga
        for m in src.execute("SELECT * FROM manga").fetchall():
            self.conn.execute(
                "INSERT OR IGNORE INTO manga (id, mal_id, title, status, score, notes, cover, added, "
                "chapters_total, chapters_read, chapter_start, continued_from_anime, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (m["id"], m["mal_id"], m["title"], m["status"], m["score"],
                 m["notes"], m["cover"], m["added"], m["chapters_total"],
                 m["chapters_read"], m["chapter_start"], m["continued_from_anime"],
                 m["created_at"]))

        self.conn.commit()
        src.close()

        # Also copy covers
        old_covers = BASE / "animanga_data" / "covers"
        if old_covers.exists():
            import shutil
            for f in old_covers.iterdir():
                dest = COVERS_DIR / f.name
                if not dest.exists():
                    shutil.copy2(f, dest)

        print(f"[Migration] Anime/manga migration complete")

    def _migrate_overtime_json(self):
        """Migrate from overtime_tracker_data.json."""
        count = self.conn.execute("SELECT COUNT(*) FROM overtime_entries").fetchone()[0]
        if count > 0:
            return

        for json_path in (LEGACY_OVERTIME_JSON, NEW_OVERTIME_JSON):
            if json_path.exists():
                data = json.loads(json_path.read_text(encoding="utf-8"))
                rate = data.get("hourly_rate", 10.0)
                self.conn.execute(
                    "INSERT OR REPLACE INTO overtime_settings (key, value) VALUES ('hourly_rate', ?)",
                    (str(rate),))
                for e in data.get("entries", []):
                    self.conn.execute(
                        "INSERT OR IGNORE INTO overtime_entries (id, date, type, hours, rate, mult, pay, note, paid) "
                        "VALUES (?,?,?,?,?,?,?,?,?)",
                        (e["id"], e["date"], e["type"], e["hours"], e["rate"],
                         e["mult"], e["pay"], e.get("note", ""), 1 if e.get("paid") else 0))
                self.conn.commit()
                print(f"[Migration] Overtime migrated from {json_path.name}")
                return

    def _migrate_payslip_json(self):
        """Migrate from payslip_tracker_data.json."""
        count = self.conn.execute("SELECT COUNT(*) FROM payslip_entries").fetchone()[0]
        if count > 0:
            return

        for json_path in (LEGACY_PAYSLIP_JSON, NEW_PAYSLIP_JSON):
            if json_path.exists():
                data = json.loads(json_path.read_text(encoding="utf-8"))
                for e in data.get("entries", []):
                    self.conn.execute(
                        "INSERT OR IGNORE INTO payslip_entries (id, month, year, category, salary, overtime, gross, note, logged) "
                        "VALUES (?,?,?,?,?,?,?,?,?)",
                        (e["id"], e["month"], e["year"], "salary",
                         e["salary"], e["overtime"], e["gross"],
                         e.get("note", ""), e.get("logged", "")))
                self.conn.commit()
                print(f"[Migration] Payslips migrated from {json_path.name}")
                return

    # ══════════════════════════════════════════════════════════════════════
    #  OVERTIME CRUD
    # ══════════════════════════════════════════════════════════════════════
    # ══════════════════════════════════════════════════════════════════════
    #  THEME PREFERENCE
    # ══════════════════════════════════════════════════════════════════════
    def get_theme(self):
        r = self.conn.execute("SELECT value FROM overtime_settings WHERE key='theme'").fetchone()
        return r[0] if r else "light"

    def set_theme(self, theme):
        self.conn.execute(
            "INSERT OR REPLACE INTO overtime_settings (key, value) VALUES ('theme', ?)",
            (theme,))
        self.conn.commit()

    # ══════════════════════════════════════════════════════════════════════
    #  OVERTIME CRUD
    # ══════════════════════════════════════════════════════════════════════
    def get_hourly_rate(self):
        r = self.conn.execute("SELECT value FROM overtime_settings WHERE key='hourly_rate'").fetchone()
        return float(r[0]) if r else 10.0

    def set_hourly_rate(self, rate):
        self.conn.execute(
            "INSERT OR REPLACE INTO overtime_settings (key, value) VALUES ('hourly_rate', ?)",
            (str(rate),))
        self.conn.commit()

    def get_overtime_entries(self):
        return [dict(r) for r in
                self.conn.execute("SELECT * FROM overtime_entries ORDER BY date DESC").fetchall()]

    def add_overtime_entry(self, entry):
        self.conn.execute(
            "INSERT INTO overtime_entries (id, date, type, hours, rate, mult, pay, note, paid) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (entry["id"], entry["date"], entry["type"], entry["hours"],
             entry["rate"], entry["mult"], entry["pay"], entry.get("note", ""),
             1 if entry.get("paid") else 0))
        self.conn.commit()

    def delete_overtime_entries(self, ids):
        if not ids:
            return
        placeholders = ",".join("?" * len(ids))
        self.conn.execute(f"DELETE FROM overtime_entries WHERE id IN ({placeholders})", list(ids))
        self.conn.commit()

    def set_overtime_paid(self, ids, paid):
        if not ids:
            return
        placeholders = ",".join("?" * len(ids))
        self.conn.execute(
            f"UPDATE overtime_entries SET paid=? WHERE id IN ({placeholders})",
            [1 if paid else 0] + list(ids))
        self.conn.commit()

    # ══════════════════════════════════════════════════════════════════════
    #  PAYSLIP CRUD
    # ══════════════════════════════════════════════════════════════════════
    def get_payslip_entries(self):
        return [dict(r) for r in
                self.conn.execute("SELECT * FROM payslip_entries ORDER BY year DESC, month DESC").fetchall()]

    def save_payslip(self, entry):
        self.conn.execute(
            "INSERT OR REPLACE INTO payslip_entries (id, month, year, category, salary, overtime, gross, note, logged) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (entry["id"], entry["month"], entry["year"], entry.get("category", "salary"),
             entry["salary"], entry["overtime"], entry["gross"],
             entry.get("note", ""), entry.get("logged", "")))
        self.conn.commit()

    def delete_payslip_entries(self, ids):
        if not ids:
            return
        placeholders = ",".join("?" * len(ids))
        self.conn.execute(f"DELETE FROM payslip_entries WHERE id IN ({placeholders})", list(ids))
        self.conn.commit()

    # ══════════════════════════════════════════════════════════════════════
    #  ANIME CRUD
    # ══════════════════════════════════════════════════════════════════════
    def get_all_anime(self):
        rows = self.conn.execute("SELECT * FROM anime ORDER BY title").fetchall()
        result = []
        for r in rows:
            entry = dict(r)
            entry["seasons"] = self._get_anime_seasons(entry["id"])
            entry["movies"]  = self._get_anime_extras(entry["id"], "movie")
            entry["ovas"]    = self._get_anime_extras(entry["id"], "ova")
            result.append(entry)
        return result

    def _get_anime_seasons(self, anime_id):
        rows = self.conn.execute(
            "SELECT * FROM anime_seasons WHERE anime_id=? ORDER BY sort_order",
            (anime_id,)).fetchall()
        seasons = []
        for r in rows:
            s = dict(r)
            eps = self.conn.execute(
                "SELECT episode_num, watched, is_filler FROM episode_progress "
                "WHERE season_id=? ORDER BY episode_num", (s["id"],)).fetchall()
            s["ep_watched"] = [bool(ep["watched"]) for ep in eps]
            s["ep_filler"]  = [bool(ep["is_filler"]) for ep in eps]
            seasons.append(s)
        return seasons

    def _get_anime_extras(self, anime_id, category):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM anime_extras WHERE anime_id=? AND category=?",
            (anime_id, category)).fetchall()]

    def save_anime(self, entry):
        c = self.conn
        c.execute(
            "INSERT OR IGNORE INTO anime (id, mal_id, title, status, score, notes, cover, added) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (entry["id"], entry.get("mal_id"), entry["title"], entry.get("status"),
             entry.get("score"), entry.get("notes", ""), entry.get("cover"), entry.get("added")))
        c.execute(
            "UPDATE anime SET mal_id=?, title=?, status=?, score=?, notes=?, cover=?, added=? WHERE id=?",
            (entry.get("mal_id"), entry["title"], entry.get("status"),
             entry.get("score"), entry.get("notes", ""), entry.get("cover"), entry.get("added"),
             entry["id"]))

        existing_ids = set(r[0] for r in c.execute(
            "SELECT id FROM anime_seasons WHERE anime_id=?", (entry["id"],)).fetchall())
        new_ids = set()

        for s_idx, s in enumerate(entry.get("seasons", [])):
            if "id" in s and s["id"] in existing_ids:
                c.execute(
                    "UPDATE anime_seasons SET name=?, episodes=?, ep_duration=?, mal_id=?, sort_order=? WHERE id=?",
                    (s["name"], s["episodes"], s.get("ep_duration", DEFAULT_EP_DURATION),
                     s.get("mal_id"), s_idx, s["id"]))
                season_id = s["id"]
                new_ids.add(season_id)
            else:
                c.execute(
                    "INSERT INTO anime_seasons (anime_id, name, episodes, ep_duration, mal_id, sort_order) "
                    "VALUES (?,?,?,?,?,?)",
                    (entry["id"], s["name"], s["episodes"],
                     s.get("ep_duration", DEFAULT_EP_DURATION), s.get("mal_id"), s_idx))
                season_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
                s["id"] = season_id
                new_ids.add(season_id)

            c.execute("DELETE FROM episode_progress WHERE season_id=?", (season_id,))
            ep_watched = s.get("ep_watched", [])
            ep_filler  = s.get("ep_filler", [])
            for ep_num in range(s["episodes"]):
                watched = ep_watched[ep_num] if ep_num < len(ep_watched) else False
                filler  = ep_filler[ep_num] if ep_num < len(ep_filler) else False
                c.execute(
                    "INSERT INTO episode_progress (season_id, episode_num, watched, is_filler) VALUES (?,?,?,?)",
                    (season_id, ep_num + 1, 1 if watched else 0, 1 if filler else 0))

        for old_id in existing_ids - new_ids:
            c.execute("DELETE FROM anime_seasons WHERE id=?", (old_id,))

        for cat_key, cat_val in [("movies", "movie"), ("ovas", "ova")]:
            c.execute("DELETE FROM anime_extras WHERE anime_id=? AND category=?", (entry["id"], cat_val))
            for item in entry.get(cat_key, []):
                c.execute(
                    "INSERT INTO anime_extras (anime_id, category, title, duration, watched, mal_id) VALUES (?,?,?,?,?,?)",
                    (entry["id"], cat_val, item["title"], item.get("duration", 24),
                     1 if item.get("watched") else 0, item.get("mal_id")))
        c.commit()

    def delete_anime(self, entry_id):
        self.conn.execute("DELETE FROM anime WHERE id=?", (entry_id,))
        self.conn.commit()

    # ══════════════════════════════════════════════════════════════════════
    #  MANGA CRUD
    # ══════════════════════════════════════════════════════════════════════
    def get_all_manga(self):
        rows = self.conn.execute("SELECT * FROM manga ORDER BY title").fetchall()
        result = []
        for r in rows:
            entry = dict(r)
            entry["continued_from_anime"] = bool(entry.get("continued_from_anime", 0))
            entry.setdefault("seasons", [])
            entry.setdefault("movies", [])
            entry.setdefault("ovas", [])
            result.append(entry)
        return result

    def save_manga(self, entry):
        self.conn.execute(
            "INSERT OR REPLACE INTO manga (id, mal_id, title, status, score, notes, cover, added, "
            "chapters_total, chapters_read, chapter_start, continued_from_anime) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (entry["id"], entry.get("mal_id"), entry["title"], entry.get("status"),
             entry.get("score"), entry.get("notes", ""), entry.get("cover"), entry.get("added"),
             entry.get("chapters_total", 0), entry.get("chapters_read", 0),
             entry.get("chapter_start", 0), 1 if entry.get("continued_from_anime") else 0))
        self.conn.commit()

    def delete_manga(self, entry_id):
        self.conn.execute("DELETE FROM manga WHERE id=?", (entry_id,))
        self.conn.commit()

    # ══════════════════════════════════════════════════════════════════════
    #  DB GUIDE (schema description for the user)
    # ══════════════════════════════════════════════════════════════════════
    def get_schema_guide(self):
        """Returns a structured guide of all tables and their relationships."""
        return {
            "database": str(DB_FILE),
            "schemas": [
                {
                    "name": "Overtime Tracker",
                    "tables": [
                        {
                            "name": "overtime_settings",
                            "desc": "Key-value store for settings (e.g. hourly_rate)",
                            "columns": "key (PK), value",
                        },
                        {
                            "name": "overtime_entries",
                            "desc": "Each row is one overtime/overwork entry",
                            "columns": "id (PK), date, type, hours, rate, mult, pay, note, paid",
                            "notes": "type is 'overwork' (×1.2) or 'overtime' (×1.4). paid is 0/1.",
                        },
                    ],
                    "relationships": "No foreign keys — flat structure.",
                },
                {
                    "name": "Payslip Tracker",
                    "tables": [
                        {
                            "name": "payslip_entries",
                            "desc": "One row per payslip (monthly salary or bonus)",
                            "columns": "id (PK), month, year, category, salary, overtime, gross, note, logged",
                            "notes": "category: 'salary', 'easter_bonus', 'christmas_bonus', 'summer_bonus'. "
                                     "UNIQUE(year, month, category) prevents duplicates.",
                        },
                    ],
                    "relationships": "No foreign keys — flat structure.",
                },
                {
                    "name": "Anime Tracker",
                    "tables": [
                        {"name": "anime", "desc": "One row per franchise",
                         "columns": "id (PK), mal_id, title, status, score, notes, cover, added"},
                        {"name": "anime_seasons", "desc": "Seasons within a franchise",
                         "columns": "id (PK, auto), anime_id (FK→anime), name, episodes, ep_duration, mal_id, sort_order"},
                        {"name": "episode_progress", "desc": "Per-episode tracking",
                         "columns": "id (PK, auto), season_id (FK→anime_seasons), episode_num, watched, is_filler",
                         "notes": "UNIQUE(season_id, episode_num). is_filler for future filler filtering."},
                        {"name": "anime_extras", "desc": "Movies and OVAs",
                         "columns": "id (PK, auto), anime_id (FK→anime), category, title, duration, watched, mal_id",
                         "notes": "category is 'movie' or 'ova'."},
                    ],
                    "relationships": "anime → anime_seasons (1:N via anime_id)\n"
                                     "anime_seasons → episode_progress (1:N via season_id)\n"
                                     "anime → anime_extras (1:N via anime_id)\n"
                                     "All cascade on delete.",
                },
                {
                    "name": "Manga Tracker",
                    "tables": [
                        {"name": "manga", "desc": "One row per manga",
                         "columns": "id (PK), mal_id, title, status, score, notes, cover, added, "
                                    "chapters_total, chapters_read, chapter_start, continued_from_anime"},
                    ],
                    "relationships": "No foreign keys — flat structure.",
                },
            ],
            "useful_queries": [
                ("Total watched episodes per anime",
                 "SELECT a.title, COUNT(*) as watched\nFROM anime a\nJOIN anime_seasons s ON s.anime_id = a.id\nJOIN episode_progress ep ON ep.season_id = s.id\nWHERE ep.watched = 1\nGROUP BY a.title\nORDER BY watched DESC"),
                ("Canon (non-filler) episodes watched",
                 "SELECT a.title, COUNT(*) as canon_watched\nFROM anime a\nJOIN anime_seasons s ON s.anime_id = a.id\nJOIN episode_progress ep ON ep.season_id = s.id\nWHERE ep.watched = 1 AND ep.is_filler = 0\nGROUP BY a.title"),
                ("Total overtime pay by month",
                 "SELECT strftime('%Y-%m', date) as month, SUM(pay) as total\nFROM overtime_entries\nGROUP BY month\nORDER BY month DESC"),
                ("Unpaid overtime total",
                 "SELECT SUM(pay) as unpaid\nFROM overtime_entries\nWHERE paid = 0"),
                ("Yearly gross income from payslips",
                 "SELECT year, SUM(gross) as total\nFROM payslip_entries\nGROUP BY year"),
            ],
        }

    def close(self):
        self.conn.close()


# ══════════════════════════════════════════════════════════════════════════════
#  SHARED COLOR PALETTES — all apps import get_palette()
# ══════════════════════════════════════════════════════════════════════════════

PALETTE_LIGHT = {
    "bg":       "#f0f1f5",
    "surface":  "#ffffff",
    "card":     "#f8f9fc",
    "border":   "#dfe2ea",
    "accent":   "#6c7bd8",
    "accent2":  "#9b7ed8",
    "success":  "#5bb98c",
    "warning":  "#d4a03c",
    "danger":   "#d4645c",
    "text":     "#2d3142",
    "muted":    "#7c8091",
    "white":    "#ffffff",
    "hover":    "#ebedf5",
    "anime":    "#7b8cde",
    "manga":    "#d89b6c",
    "bar_bg":   "#e8eaf0",
    "overwork": "#5b9bd5",
    "overtime": "#9b7ed8",
    "salary":   "#5bb98c",
    "bonus":    "#d4a03c",
    "completed":"#5bb98c",
}

PALETTE_GRAY = {
    "bg":       "#e2e4e8",
    "surface":  "#f0f0f2",
    "card":     "#eaebef",
    "border":   "#c8cbd4",
    "accent":   "#5566b8",
    "accent2":  "#7b5fad",
    "success":  "#3f9e6e",
    "warning":  "#b8882e",
    "danger":   "#b84f48",
    "text":     "#1a1d2b",
    "muted":    "#505566",
    "white":    "#ffffff",
    "hover":    "#d6d8e0",
    "anime":    "#5c6dc0",
    "manga":    "#b87a4a",
    "bar_bg":   "#d0d2da",
    "overwork": "#4080b8",
    "overtime": "#7b5fad",
    "salary":   "#3f9e6e",
    "bonus":    "#b8882e",
    "completed":"#3f9e6e",
}

PALETTES = {"light": PALETTE_LIGHT, "gray": PALETTE_GRAY}


def get_palette():
    """Read the saved theme preference from the DB and return the right palette."""
    try:
        db = WorkSuiteDB()
        theme = db.get_theme()
        db.close()
        return PALETTES.get(theme, PALETTE_LIGHT)
    except Exception:
        return PALETTE_LIGHT
