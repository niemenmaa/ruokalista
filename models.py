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


def get_week_dates(week_start: date = None) -> list[date]:
    """Get all dates (Mon-Sun) for a week."""
    if week_start is None:
        week_start = get_week_start()
    return [week_start + timedelta(days=i) for i in range(7)]


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

            -- Meals within templates (just a list of recipes)
            CREATE TABLE IF NOT EXISTS template_meals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_id INTEGER NOT NULL,
                recipe_slug TEXT NOT NULL,
                position INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE CASCADE
            );

            -- Active week plan
            CREATE TABLE IF NOT EXISTS active_week (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week_start DATE NOT NULL UNIQUE,
                template_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (template_id) REFERENCES templates(id)
            );

            -- Meals in active week (flexible: optional date and chef)
            CREATE TABLE IF NOT EXISTS week_meals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week_id INTEGER NOT NULL,
                recipe_slug TEXT NOT NULL,
                meal_date DATE,
                chef TEXT,
                position INTEGER NOT NULL DEFAULT 0,
                is_done BOOLEAN DEFAULT 0,
                FOREIGN KEY (week_id) REFERENCES active_week(id) ON DELETE CASCADE
            );
        ''')


def migrate_db():
    """Migrate old schema to new schema if needed, preserving data."""
    with get_db() as conn:
        # Check if old schema exists (has 'day' column in week_meals)
        cursor = conn.execute("PRAGMA table_info(week_meals)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'day' in columns:
            # Old schema detected, migrate with data preservation

            # 1. Backup existing data
            old_template_meals = conn.execute('SELECT * FROM template_meals').fetchall()
            old_week_meals = conn.execute('SELECT * FROM week_meals').fetchall()

            # Get week_start dates for converting day to meal_date
            weeks = {row['id']: row['week_start'] for row in conn.execute('SELECT id, week_start FROM active_week').fetchall()}

            # 2. Drop old tables
            conn.execute('DROP TABLE IF EXISTS template_meals')
            conn.execute('DROP TABLE IF EXISTS week_meals')

            # 3. Create new tables
            conn.executescript('''
                CREATE TABLE template_meals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_id INTEGER NOT NULL,
                    recipe_slug TEXT NOT NULL,
                    position INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE CASCADE
                );

                CREATE TABLE week_meals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    week_id INTEGER NOT NULL,
                    recipe_slug TEXT NOT NULL,
                    meal_date DATE,
                    chef TEXT,
                    position INTEGER NOT NULL DEFAULT 0,
                    is_done BOOLEAN DEFAULT 0,
                    FOREIGN KEY (week_id) REFERENCES active_week(id) ON DELETE CASCADE
                );
            ''')

            # 4. Migrate template_meals (use day as position)
            for meal in old_template_meals:
                conn.execute(
                    'INSERT INTO template_meals (template_id, recipe_slug, position) VALUES (?, ?, ?)',
                    (meal['template_id'], meal['recipe_slug'], meal['day'])
                )

            # 5. Migrate week_meals (convert day to meal_date)
            for meal in old_week_meals:
                week_start_str = weeks.get(meal['week_id'])
                meal_date = None
                if week_start_str:
                    week_start = date.fromisoformat(week_start_str)
                    meal_date = (week_start + timedelta(days=meal['day'])).isoformat()

                conn.execute(
                    'INSERT INTO week_meals (week_id, recipe_slug, meal_date, position, is_done) VALUES (?, ?, ?, ?, ?)',
                    (meal['week_id'], meal['recipe_slug'], meal_date, meal['day'], meal['is_done'])
                )

            return True
    return False


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


def update_template_name(template_id: int, new_name: str) -> bool:
    """Update a template's name. Returns True if successful."""
    with get_db() as conn:
        cursor = conn.execute(
            'UPDATE templates SET name = ? WHERE id = ?',
            (new_name, template_id)
        )
        return cursor.rowcount > 0


def delete_template(template_id: int):
    """Delete a template and its meals."""
    with get_db() as conn:
        conn.execute('DELETE FROM templates WHERE id = ?', (template_id,))


def get_template_meals(template_id: int):
    """Get all meals for a template."""
    with get_db() as conn:
        return conn.execute(
            'SELECT * FROM template_meals WHERE template_id = ? ORDER BY position',
            (template_id,)
        ).fetchall()


def add_template_meal(template_id: int, recipe_slug: str) -> int:
    """Add a meal to a template, return its ID."""
    with get_db() as conn:
        # Get next position
        row = conn.execute(
            'SELECT COALESCE(MAX(position), -1) + 1 as next_pos FROM template_meals WHERE template_id = ?',
            (template_id,)
        ).fetchone()
        position = row['next_pos']

        cursor = conn.execute(
            'INSERT INTO template_meals (template_id, recipe_slug, position) VALUES (?, ?, ?)',
            (template_id, recipe_slug, position)
        )
        return cursor.lastrowid


def remove_template_meal(template_meal_id: int):
    """Remove a meal from a template."""
    with get_db() as conn:
        conn.execute('DELETE FROM template_meals WHERE id = ?', (template_meal_id,))


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


def get_all_weeks() -> list:
    """Get all weeks, sorted by week_start descending."""
    with get_db() as conn:
        rows = conn.execute(
            'SELECT * FROM active_week ORDER BY week_start DESC'
        ).fetchall()
        return [dict(row) for row in rows]


def apply_template_to_week(template_id: int, week_start: date = None):
    """Copy meals from template to active week (without dates/chefs)."""
    if week_start is None:
        week_start = get_week_start()

    week = get_or_create_active_week(week_start)
    week_id = week['id']

    with get_db() as conn:
        # Clear existing meals
        conn.execute('DELETE FROM week_meals WHERE week_id = ?', (week_id,))

        # Copy from template (just recipes and positions)
        conn.execute('''
            INSERT INTO week_meals (week_id, recipe_slug, position, is_done)
            SELECT ?, recipe_slug, position, 0
            FROM template_meals WHERE template_id = ?
        ''', (week_id, template_id))

        # Update template reference
        conn.execute(
            'UPDATE active_week SET template_id = ? WHERE id = ?',
            (template_id, week_id)
        )


def get_week_meals(week_start: date = None):
    """Get all meals for a week, sorted by date (nulls last) then position."""
    if week_start is None:
        week_start = get_week_start()

    week = get_or_create_active_week(week_start)

    with get_db() as conn:
        return conn.execute(
            '''SELECT * FROM week_meals WHERE week_id = ?
               ORDER BY meal_date IS NULL, meal_date, position''',
            (week['id'],)
        ).fetchall()


def add_week_meal(recipe_slug: str, meal_date: date = None, chef: str = None, week_start: date = None) -> int:
    """Add a meal to the active week, return its ID."""
    if week_start is None:
        week_start = get_week_start()

    week = get_or_create_active_week(week_start)

    with get_db() as conn:
        # Get next position
        row = conn.execute(
            'SELECT COALESCE(MAX(position), -1) + 1 as next_pos FROM week_meals WHERE week_id = ?',
            (week['id'],)
        ).fetchone()
        position = row['next_pos']

        cursor = conn.execute(
            'INSERT INTO week_meals (week_id, recipe_slug, meal_date, chef, position, is_done) VALUES (?, ?, ?, ?, ?, 0)',
            (week['id'], recipe_slug, meal_date.isoformat() if meal_date else None, chef, position)
        )
        return cursor.lastrowid


def update_week_meal(meal_id: int, recipe_slug: str = None, meal_date: date = None, chef: str = None, clear_date: bool = False, clear_chef: bool = False):
    """Update a meal in the active week."""
    with get_db() as conn:
        updates = []
        params = []

        if recipe_slug is not None:
            updates.append('recipe_slug = ?')
            params.append(recipe_slug)

        if clear_date:
            updates.append('meal_date = NULL')
        elif meal_date is not None:
            updates.append('meal_date = ?')
            params.append(meal_date.isoformat())

        if clear_chef:
            updates.append('chef = NULL')
        elif chef is not None:
            updates.append('chef = ?')
            params.append(chef)

        if updates:
            params.append(meal_id)
            conn.execute(f'UPDATE week_meals SET {", ".join(updates)} WHERE id = ?', params)


def remove_week_meal(meal_id: int):
    """Remove a meal from the active week."""
    with get_db() as conn:
        conn.execute('DELETE FROM week_meals WHERE id = ?', (meal_id,))


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
            '''SELECT * FROM week_meals WHERE week_id = ? AND is_done = 0
               ORDER BY meal_date IS NULL, meal_date, position''',
            (week['id'],)
        ).fetchall()


# Initialize and migrate on import
init_db()
migrate_db()
