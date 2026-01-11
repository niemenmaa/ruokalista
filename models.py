"""
SQLite database models for meal planning.
"""
import sqlite3
from pathlib import Path
from datetime import date, datetime, timedelta
from contextlib import contextmanager

DATABASE_PATH = Path(__file__).parent / "data.db"


def get_week_start(d: date = None) -> date:
    """Get Monday of the week for a given date."""
    if d is None:
        d = date.today()
    return d - timedelta(days=d.weekday())


@contextmanager
def get_db():
    """Database connection context manager."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Initialize database schema."""
    with get_db() as conn:
        conn.executescript('''
            -- Weekly meal plan templates
            CREATE TABLE IF NOT EXISTS templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Meals within templates (day 0=Monday, 6=Sunday)
            CREATE TABLE IF NOT EXISTS template_meals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_id INTEGER NOT NULL,
                day INTEGER NOT NULL CHECK (day >= 0 AND day <= 6),
                recipe_slug TEXT NOT NULL,
                meal_type TEXT DEFAULT 'dinner',
                FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE CASCADE,
                UNIQUE(template_id, day, meal_type)
            );
            
            -- Active week plan
            CREATE TABLE IF NOT EXISTS active_week (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week_start DATE NOT NULL UNIQUE,
                template_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (template_id) REFERENCES templates(id)
            );
            
            -- Meals in active week
            CREATE TABLE IF NOT EXISTS week_meals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week_id INTEGER NOT NULL,
                day INTEGER NOT NULL CHECK (day >= 0 AND day <= 6),
                recipe_slug TEXT NOT NULL,
                meal_type TEXT DEFAULT 'dinner',
                is_done BOOLEAN DEFAULT 0,
                FOREIGN KEY (week_id) REFERENCES active_week(id) ON DELETE CASCADE,
                UNIQUE(week_id, day, meal_type)
            );
        ''')


# Template functions
def get_all_templates():
    """Get all meal plan templates."""
    with get_db() as conn:
        return conn.execute('SELECT * FROM templates ORDER BY name').fetchall()


def get_template(template_id: int):
    """Get a single template by ID."""
    with get_db() as conn:
        return conn.execute('SELECT * FROM templates WHERE id = ?', (template_id,)).fetchone()


def create_template(name: str) -> int:
    """Create a new template, return its ID."""
    with get_db() as conn:
        cursor = conn.execute('INSERT INTO templates (name) VALUES (?)', (name,))
        return cursor.lastrowid


def delete_template(template_id: int):
    """Delete a template and its meals."""
    with get_db() as conn:
        conn.execute('DELETE FROM templates WHERE id = ?', (template_id,))


def get_template_meals(template_id: int):
    """Get all meals for a template."""
    with get_db() as conn:
        return conn.execute(
            'SELECT * FROM template_meals WHERE template_id = ? ORDER BY day',
            (template_id,)
        ).fetchall()


def set_template_meal(template_id: int, day: int, recipe_slug: str, meal_type: str = 'dinner'):
    """Set/update a meal in a template."""
    with get_db() as conn:
        conn.execute('''
            INSERT INTO template_meals (template_id, day, recipe_slug, meal_type)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(template_id, day, meal_type) DO UPDATE SET recipe_slug = ?
        ''', (template_id, day, recipe_slug, meal_type, recipe_slug))


def remove_template_meal(template_id: int, day: int, meal_type: str = 'dinner'):
    """Remove a meal from a template."""
    with get_db() as conn:
        conn.execute(
            'DELETE FROM template_meals WHERE template_id = ? AND day = ? AND meal_type = ?',
            (template_id, day, meal_type)
        )


# Active week functions
def get_or_create_active_week(week_start: date = None) -> dict:
    """Get or create the active week entry."""
    if week_start is None:
        week_start = get_week_start()
    
    with get_db() as conn:
        row = conn.execute(
            'SELECT * FROM active_week WHERE week_start = ?',
            (week_start.isoformat(),)
        ).fetchone()
        
        if row:
            return dict(row)
        
        cursor = conn.execute(
            'INSERT INTO active_week (week_start) VALUES (?)',
            (week_start.isoformat(),)
        )
        return {
            'id': cursor.lastrowid,
            'week_start': week_start.isoformat(),
            'template_id': None
        }


def apply_template_to_week(template_id: int, week_start: date = None):
    """Copy meals from template to active week."""
    if week_start is None:
        week_start = get_week_start()
    
    week = get_or_create_active_week(week_start)
    week_id = week['id']
    
    with get_db() as conn:
        # Clear existing meals
        conn.execute('DELETE FROM week_meals WHERE week_id = ?', (week_id,))
        
        # Copy from template
        conn.execute('''
            INSERT INTO week_meals (week_id, day, recipe_slug, meal_type, is_done)
            SELECT ?, day, recipe_slug, meal_type, 0
            FROM template_meals WHERE template_id = ?
        ''', (week_id, template_id))
        
        # Update template reference
        conn.execute(
            'UPDATE active_week SET template_id = ? WHERE id = ?',
            (template_id, week_id)
        )


def get_week_meals(week_start: date = None):
    """Get all meals for a week."""
    if week_start is None:
        week_start = get_week_start()
    
    week = get_or_create_active_week(week_start)
    
    with get_db() as conn:
        return conn.execute(
            'SELECT * FROM week_meals WHERE week_id = ? ORDER BY day',
            (week['id'],)
        ).fetchall()


def set_week_meal(day: int, recipe_slug: str, meal_type: str = 'dinner', week_start: date = None):
    """Set/update a meal in the active week."""
    if week_start is None:
        week_start = get_week_start()
    
    week = get_or_create_active_week(week_start)
    
    with get_db() as conn:
        conn.execute('''
            INSERT INTO week_meals (week_id, day, recipe_slug, meal_type, is_done)
            VALUES (?, ?, ?, ?, 0)
            ON CONFLICT(week_id, day, meal_type) DO UPDATE SET recipe_slug = ?
        ''', (week['id'], day, recipe_slug, meal_type, recipe_slug))


def remove_week_meal(day: int, meal_type: str = 'dinner', week_start: date = None):
    """Remove a meal from the active week."""
    if week_start is None:
        week_start = get_week_start()
    
    week = get_or_create_active_week(week_start)
    
    with get_db() as conn:
        conn.execute(
            'DELETE FROM week_meals WHERE week_id = ? AND day = ? AND meal_type = ?',
            (week['id'], day, meal_type)
        )


def toggle_meal_done(meal_id: int) -> bool:
    """Toggle the is_done status of a meal, return new status."""
    with get_db() as conn:
        conn.execute(
            'UPDATE week_meals SET is_done = NOT is_done WHERE id = ?',
            (meal_id,)
        )
        row = conn.execute(
            'SELECT is_done FROM week_meals WHERE id = ?',
            (meal_id,)
        ).fetchone()
        return bool(row['is_done']) if row else False


def get_undone_meals(week_start: date = None):
    """Get all undone meals for shopping list."""
    if week_start is None:
        week_start = get_week_start()
    
    week = get_or_create_active_week(week_start)
    
    with get_db() as conn:
        return conn.execute(
            'SELECT * FROM week_meals WHERE week_id = ? AND is_done = 0 ORDER BY day',
            (week['id'],)
        ).fetchall()


# Initialize on import
init_db()
