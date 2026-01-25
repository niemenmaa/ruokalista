# Template Rename & Week History Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable editing template names and add week navigation with history page for planning future weeks.

**Architecture:** Add rename route for templates, modify week views to accept date parameter, create new weeks listing page. No schema changes needed.

**Tech Stack:** Flask, SQLite, Jinja2, Pico CSS

---

## Task 1: Add Template Rename Function

**Files:**
- Modify: `models.py`

**Step 1: Add update_template_name function**

Add after `create_template` function (around line 164):

```python
def update_template_name(template_id: int, new_name: str) -> bool:
    """Update a template's name. Returns True if successful."""
    with get_db() as conn:
        cursor = conn.execute(
            'UPDATE templates SET name = ? WHERE id = ?',
            (new_name, template_id)
        )
        return cursor.rowcount > 0
```

**Step 2: Commit**

```bash
git add models.py
git commit -m "feat: add update_template_name function"
```

---

## Task 2: Add Template Rename Route

**Files:**
- Modify: `app.py`

**Step 1: Add rename route**

Add after `delete_template_route` (around line 227):

```python
@app.route('/template/<int:template_id>/rename', methods=['POST'])
def rename_template_route(template_id):
    """Rename a template."""
    new_name = request.form.get('name', '').strip()
    if not new_name:
        flash('Nimi ei voi olla tyhjä', 'error')
        return redirect(url_for('template_detail', template_id=template_id))

    from models import update_template_name
    if update_template_name(template_id, new_name):
        flash('Nimi päivitetty', 'success')
    else:
        flash('Nimen päivitys epäonnistui', 'error')

    return redirect(url_for('template_detail', template_id=template_id))
```

**Step 2: Add import if needed**

At the top of app.py, ensure `update_template_name` is imported. Find the line with model imports and add it:

```python
from models import (
    # ... existing imports ...
    update_template_name
)
```

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat: add template rename route"
```

---

## Task 3: Update Template Detail UI for Rename

**Files:**
- Modify: `templates/template_detail.html`

**Step 1: Replace header with editable form**

Replace lines 6-8:
```html
<header class="top-header">
    <h1>{{ template.name }}</h1>
</header>
```

With:
```html
<header class="top-header">
    <form method="post" action="{{ url_for('rename_template_route', template_id=template.id) }}" style="display: flex; align-items: center; gap: 0.5rem;">
        <input type="text" name="name" value="{{ template.name }}"
               style="font-size: 1.25rem; font-weight: bold; background: transparent; border: none; border-bottom: 1px solid rgba(255,255,255,0.3); color: white; padding: 0; margin: 0; flex: 1;"
               required>
        <button type="submit" style="background: rgba(255,255,255,0.2); border: none; padding: 0.25rem 0.5rem; font-size: 0.75rem; margin: 0;">Tallenna</button>
    </form>
</header>
```

**Step 2: Commit**

```bash
git add templates/template_detail.html
git commit -m "feat: add inline template name editing"
```

---

## Task 4: Add Week Navigation to Index Route

**Files:**
- Modify: `app.py`

**Step 1: Modify index function to accept week parameter**

Replace the `index` function (lines 41-68) with:

```python
@app.route('/')
def index():
    """Home page - this week's meals."""
    # Get week_start from query param or default to current week
    start_param = request.args.get('start')
    if start_param:
        try:
            week_start = date.fromisoformat(start_param)
            # Normalize to Monday
            week_start = week_start - timedelta(days=week_start.weekday())
        except ValueError:
            week_start = get_week_start()
    else:
        week_start = get_week_start()

    week_meals = get_week_meals(week_start)
    recipes = get_recipes_dict()
    today = date.today()

    meals = []
    for meal in week_meals:
        recipe = recipes.get(meal['recipe_slug'])
        meal_date = date.fromisoformat(meal['meal_date']) if meal['meal_date'] else None
        meals.append({
            'id': meal['id'],
            'recipe': recipe,
            'slug': meal['recipe_slug'],
            'is_done': meal['is_done'],
            'meal_date': meal_date,
            'meal_date_fi': format_date_fi(meal_date) if meal_date else None,
            'chef': meal['chef'],
            'is_today': meal_date == today if meal_date else False
        })

    # Calculate prev/next week dates
    prev_week = week_start - timedelta(days=7)
    next_week = week_start + timedelta(days=7)
    current_week_start = get_week_start()

    return render_template('week.html',
        meals=meals,
        week_start=week_start,
        week_end=week_start + timedelta(days=6),
        prev_week=prev_week,
        next_week=next_week,
        is_current_week=(week_start == current_week_start)
    )
```

**Step 2: Commit**

```bash
git add app.py
git commit -m "feat: add week navigation parameter to index route"
```

---

## Task 5: Update Week Template with Navigation

**Files:**
- Modify: `templates/week.html`

**Step 1: Replace header with navigation**

Replace lines 6-9:
```html
<header class="top-header">
    <h1>Tämän viikon ruuat</h1>
    <small>{{ week_start.strftime('%d.%m.') }} - {{ week_end.strftime('%d.%m.%Y') }}</small>
</header>
```

With:
```html
<header class="top-header">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <a href="{{ url_for('index', start=prev_week.isoformat()) }}" style="color: white; text-decoration: none; padding: 0.5rem;">← Edellinen</a>
        <div style="text-align: center;">
            <h1 style="margin: 0;">{% if is_current_week %}Tämän viikon ruuat{% else %}Viikon ruuat{% endif %}</h1>
            <small>{{ week_start.strftime('%d.%m.') }} - {{ week_end.strftime('%d.%m.%Y') }}</small>
        </div>
        <a href="{{ url_for('index', start=next_week.isoformat()) }}" style="color: white; text-decoration: none; padding: 0.5rem;">Seuraava →</a>
    </div>
</header>
```

**Step 2: Update "Muokkaa viikkoa" link to pass week_start**

Replace line 12:
```html
    <a href="{{ url_for('week_setup') }}" role="button" class="outline">Muokkaa viikkoa</a>
```

With:
```html
    <a href="{{ url_for('week_setup', start=week_start.isoformat()) }}" role="button" class="outline">Muokkaa viikkoa</a>
```

**Step 3: Commit**

```bash
git add templates/week.html
git commit -m "feat: add week navigation arrows to week view"
```

---

## Task 6: Add Week Navigation to Setup Route

**Files:**
- Modify: `app.py`

**Step 1: Modify week_setup function to accept week parameter**

Replace the `week_setup` function (lines 234-272) with:

```python
@app.route('/week/setup')
def week_setup():
    """Setup this week's meals."""
    # Get week_start from query param or default to current week
    start_param = request.args.get('start')
    if start_param:
        try:
            week_start = date.fromisoformat(start_param)
            # Normalize to Monday
            week_start = week_start - timedelta(days=week_start.weekday())
        except ValueError:
            week_start = get_week_start()
    else:
        week_start = get_week_start()

    all_templates = get_all_templates()
    week = get_or_create_active_week(week_start)
    current_meals = get_week_meals(week_start)
    recipes = get_recipes_dict()
    week_dates = get_week_dates(week_start)

    meals = []
    for meal in current_meals:
        recipe = recipes.get(meal['recipe_slug'])
        meal_date = date.fromisoformat(meal['meal_date']) if meal['meal_date'] else None
        meals.append({
            'id': meal['id'],
            'recipe': recipe,
            'slug': meal['recipe_slug'],
            'meal_date': meal_date,
            'meal_date_iso': meal['meal_date'],
            'chef': meal['chef']
        })

    # Ensure we have at least MEAL_SLOTS entries for display
    empty_slots = max(0, MEAL_SLOTS - len(meals))

    # Format week dates for dropdown
    date_options = [{'date': d, 'iso': d.isoformat(), 'label': format_date_fi(d)} for d in week_dates]

    # Calculate prev/next week dates
    prev_week = week_start - timedelta(days=7)
    next_week = week_start + timedelta(days=7)
    current_week_start = get_week_start()

    return render_template('week_setup.html',
        templates=all_templates,
        meals=meals,
        empty_slots=empty_slots,
        all_recipes=list(recipes.values()),
        week_start=week_start,
        current_template_id=week.get('template_id'),
        date_options=date_options,
        chefs=CHEFS,
        prev_week=prev_week,
        next_week=next_week,
        is_current_week=(week_start == current_week_start)
    )
```

**Step 2: Commit**

```bash
git add app.py
git commit -m "feat: add week navigation parameter to setup route"
```

---

## Task 7: Update Week Setup Template with Navigation

**Files:**
- Modify: `templates/week_setup.html`

**Step 1: Replace header with navigation**

Replace lines 6-9:
```html
<header class="top-header">
    <h1>Viikon suunnittelu</h1>
    <small>{{ week_start.strftime('%d.%m.') }} alkaen</small>
</header>
```

With:
```html
<header class="top-header">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <a href="{{ url_for('week_setup', start=prev_week.isoformat()) }}" style="color: white; text-decoration: none; padding: 0.5rem;">← Edellinen</a>
        <div style="text-align: center;">
            <h1 style="margin: 0;">Viikon suunnittelu</h1>
            <small>{{ week_start.strftime('%d.%m.') }} alkaen{% if is_current_week %} (tämä viikko){% endif %}</small>
        </div>
        <a href="{{ url_for('week_setup', start=next_week.isoformat()) }}" style="color: white; text-decoration: none; padding: 0.5rem;">Seuraava →</a>
    </div>
</header>
```

**Step 2: Update "Valmis" button to return to correct week**

Replace line 114:
```html
    <a href="{{ url_for('index') }}" role="button">Valmis</a>
```

With:
```html
    <a href="{{ url_for('index', start=week_start.isoformat()) }}" role="button">Valmis</a>
```

**Step 3: Update add_week_meal forms to include week_start**

For all forms that POST to `add_week_meal_route`, add a hidden field. Find the forms (around lines 64, 89) and add inside each:
```html
    <input type="hidden" name="week_start" value="{{ week_start.isoformat() }}">
```

**Step 4: Commit**

```bash
git add templates/week_setup.html
git commit -m "feat: add week navigation to setup view"
```

---

## Task 8: Update Add Week Meal Route to Accept Week

**Files:**
- Modify: `app.py`

**Step 1: Modify add_week_meal_route to use week_start from form**

Find `add_week_meal_route` and update it to use the week_start from form data:

```python
@app.route('/week/meal/add', methods=['POST'])
def add_week_meal_route():
    """Add a meal to the week."""
    recipe_slug = request.form.get('recipe_slug')
    if not recipe_slug:
        return redirect(request.referrer or url_for('week_setup'))

    meal_date = request.form.get('meal_date') or None
    chef = request.form.get('chef') or None

    # Get week_start from form or default
    week_start_str = request.form.get('week_start')
    if week_start_str:
        try:
            week_start = date.fromisoformat(week_start_str)
        except ValueError:
            week_start = get_week_start()
    else:
        week_start = get_week_start()

    add_week_meal(recipe_slug, meal_date, chef, week_start)
    return redirect(url_for('week_setup', start=week_start.isoformat()))
```

**Step 2: Commit**

```bash
git add app.py
git commit -m "feat: add_week_meal_route accepts week_start parameter"
```

---

## Task 9: Add Get All Weeks Function

**Files:**
- Modify: `models.py`

**Step 1: Add get_all_weeks function**

Add after `get_or_create_active_week` (around line 228):

```python
def get_all_weeks() -> list:
    """Get all weeks, sorted by week_start descending."""
    with get_db() as conn:
        rows = conn.execute(
            'SELECT * FROM active_week ORDER BY week_start DESC'
        ).fetchall()
        return [dict(row) for row in rows]
```

**Step 2: Commit**

```bash
git add models.py
git commit -m "feat: add get_all_weeks function"
```

---

## Task 10: Add Weeks History Route

**Files:**
- Modify: `app.py`

**Step 1: Add weeks route**

Add before the index route (or after sync routes):

```python
@app.route('/weeks')
def weeks():
    """View all weeks history."""
    from models import get_all_weeks
    all_weeks = get_all_weeks()
    current_week_start = get_week_start()

    weeks_list = []
    for week in all_weeks:
        week_start = date.fromisoformat(week['week_start'])
        week_end = week_start + timedelta(days=6)
        weeks_list.append({
            'id': week['id'],
            'week_start': week_start,
            'week_end': week_end,
            'is_current': week_start == current_week_start,
            'is_future': week_start > current_week_start
        })

    return render_template('weeks.html',
        weeks=weeks_list,
        current_week_start=current_week_start
    )
```

**Step 2: Add import**

Add `get_all_weeks` to the imports from models at the top.

**Step 3: Add create week route**

```python
@app.route('/weeks/new', methods=['POST'])
def new_week():
    """Create a new week."""
    week_start_str = request.form.get('week_start')
    if not week_start_str:
        flash('Valitse päivämäärä', 'error')
        return redirect(url_for('weeks'))

    try:
        week_start = date.fromisoformat(week_start_str)
        # Normalize to Monday
        week_start = week_start - timedelta(days=week_start.weekday())
    except ValueError:
        flash('Virheellinen päivämäärä', 'error')
        return redirect(url_for('weeks'))

    get_or_create_active_week(week_start)
    return redirect(url_for('week_setup', start=week_start.isoformat()))
```

**Step 4: Commit**

```bash
git add app.py
git commit -m "feat: add weeks history and new week routes"
```

---

## Task 11: Create Weeks History Template

**Files:**
- Create: `templates/weeks.html`

**Step 1: Create the template**

```html
{% extends "base.html" %}

{% block title %}Viikot - Ruokalista{% endblock %}

{% block content %}
<header class="top-header">
    <h1>Viikot</h1>
</header>

<form method="post" action="{{ url_for('new_week') }}" class="form-row" style="align-items: stretch; margin-bottom: 1.5rem;">
    <input type="date" name="week_start" required style="flex: 1; margin: 0;">
    <button type="submit" style="white-space: nowrap; margin: 0;">Luo uusi viikko</button>
</form>

{% if weeks %}
<div class="week-list">
    {% for week in weeks %}
    <a href="{{ url_for('index', start=week.week_start.isoformat()) }}" class="meal-card" style="justify-content: space-between;">
        <div>
            <strong>{{ week.week_start.strftime('%d.%m.') }} - {{ week.week_end.strftime('%d.%m.%Y') }}</strong>
            {% if week.is_current %}
                <span style="background: var(--primary); color: white; padding: 0.1rem 0.4rem; border-radius: 4px; font-size: 0.75rem; margin-left: 0.5rem;">tämä viikko</span>
            {% elif week.is_future %}
                <span style="background: var(--pico-secondary-background); padding: 0.1rem 0.4rem; border-radius: 4px; font-size: 0.75rem; margin-left: 0.5rem;">tuleva</span>
            {% endif %}
        </div>
        <span style="color: var(--pico-muted-color);">→</span>
    </a>
    {% endfor %}
</div>
{% else %}
<p class="empty">Ei vielä viikkoja. Luo ensimmäinen yllä tai <a href="{{ url_for('index') }}">siirry tälle viikolle</a>.</p>
{% endif %}

{% endblock %}
```

**Step 2: Commit**

```bash
git add templates/weeks.html
git commit -m "feat: add weeks history template"
```

---

## Task 12: Add Weeks Link to Navigation

**Files:**
- Modify: `templates/base.html`

**Step 1: Add Viikot link to bottom nav**

Find the bottom nav (lines 329-346) and add a new link. Update to:

```html
    <nav class="bottom-nav">
        <a href="{{ url_for('index') }}" class="{{ 'active' if request.endpoint == 'index' else '' }}">
            <span class="nav-icon">📅</span>
            Viikko
        </a>
        <a href="{{ url_for('weeks') }}" class="{{ 'active' if request.endpoint == 'weeks' else '' }}">
            <span class="nav-icon">📆</span>
            Viikot
        </a>
        <a href="{{ url_for('recipes') }}" class="{{ 'active' if request.endpoint in ['recipes', 'recipe', 'edit_recipe'] else '' }}">
            <span class="nav-icon">📖</span>
            Reseptit
        </a>
        <a href="{{ url_for('templates') }}" class="{{ 'active' if request.endpoint in ['templates', 'template_detail'] else '' }}">
            <span class="nav-icon">📋</span>
            Pohjat
        </a>
        <a href="{{ url_for('shopping') }}" class="{{ 'active' if request.endpoint == 'shopping' else '' }}">
            <span class="nav-icon">🛒</span>
            Ostokset
        </a>
    </nav>
```

**Step 2: Commit**

```bash
git add templates/base.html
git commit -m "feat: add Viikot link to navigation"
```

---

## Task 13: Final Testing

**Step 1: Run the app and test all features**

```bash
cd /Users/anttoni-eventilla/personal/ruokalista
python app.py
```

Test manually:
1. Go to a template, edit its name, verify it saves
2. Navigate weeks with arrows on main page
3. Navigate weeks with arrows on setup page
4. Go to /weeks, see the history
5. Create a new week from history page
6. Verify all links pass correct week parameters

**Step 2: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: any final adjustments"
```
