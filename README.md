# Work Suite

A desktop productivity suite built with Python and tkinter. Five modules sharing a single SQLite database — tracks overtime hours, payslips, anime episodes, and manga chapters.

4,700+ lines of Python. 8 database tables. MyAnimeList API integration. Two themes. Auto-migration from legacy data.

---

## Screenshots

| Launcher | Overtime Tracker | Payslip Tracker | Anime Library |
|----------|-----------------|-----------------|---------------|
| ![Launcher](screenshots/launcher.png) | ![Overtime](screenshots/overtime.png) | ![Payslip](screenshots/payslip.png) | ![Anime](screenshots/anime.png) |

---

## What's Inside

### Launcher (`launcher.py`)

The hub that ties everything together. Three app tiles, a database schema guide for exploring the SQLite structure, and a theme toggle between light and gray modes.

### Overtime Tracker (`overtime_tracker.py`)

Log work hours with automatic split calculation — first hour at x1.2 (overwork), remaining hours at x1.4 (overtime). Includes a custom calendar date picker, filterable history with paid/unpaid tracking, bulk operations, CSV export, and an earnings dashboard with breakdown by type.

### Payslip Tracker (`payslip_tracker.py`)

Track monthly salary alongside Easter, Christmas, and Summer bonuses. The dashboard shows a 12-month breakdown table with salary, overtime, and gross columns, plus a separate bonus section. Duplicate detection prevents accidental overwrites.

### Anime & Manga Tracker (`animanga_tracker.py`)

The largest module at 2,600+ lines. Uses a franchise-based approach where one entry holds multiple seasons, movies, and OVAs, each with individual episode progress tracking.

Notable features:

- **MyAnimeList API search** — search directly from the app, auto-fill episode counts, durations, and cover art
- **Scrollable search popups** — browse up to 25 API results and add seasons or movies with one click
- **Smart manga progress** — continuation mode calculates progress relative to a starting chapter, not the total
- **Editable titles** — double-click to rename entries, dedicated rename button for seasons
- **Image caching** — covers loaded once and cached in memory for smooth scrolling
- **Responsive grid** — columns adjust automatically to window width, configurable gap setting
- **Dashboard** — stats cards, status breakdown, score distribution, yearly table, top rated list

---

## Database Architecture

All apps share a single SQLite database (`worksuite_data/worksuite.db`) with cascading foreign keys:

```
anime
  |-- anime_seasons -- episode_progress (watched flag + filler flag per episode)
  |-- anime_extras (movies and OVAs)

manga (standalone with chapter continuation tracking)

overtime_entries + overtime_settings
payslip_entries (unique constraint on year + month + category)
```

8 tables, 5 indexes, WAL mode, cascade deletes. The launcher includes a built-in Database Guide showing every table, column, relationship, and sample queries you can run.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3 |
| GUI | tkinter |
| Database | SQLite |
| API | Jikan v4 (MyAnimeList) |
| Images | Pillow |
| Architecture | Shared database module imported by all apps |

---

## Setup

```bash
# Install the only external dependency
pip install Pillow

# Run the launcher
python launcher.py
```

All five .py files need to be in the same folder. On first launch, the app creates a `worksuite_data/` directory and auto-migrates any legacy JSON data it finds.

---

## File Structure

```
project/
  launcher.py              -- hub app
  worksuite_db.py          -- shared database module
  overtime_tracker.py      -- overtime tracking
  payslip_tracker.py       -- payslip and bonus tracking
  animanga_tracker.py      -- anime and manga tracking
  worksuite_data/          -- created automatically
    worksuite.db           -- SQLite database
    covers/                -- downloaded cover images
    cache/                 -- API response cache
```


## Author

Dimitris Arvanitidis — dmarvanitidis@gmail.com

## License

MIT
