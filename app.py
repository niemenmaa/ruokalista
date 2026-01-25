"""
Ruokalista - Simple Cooklang recipe manager with meal planning.
"""
import os
from flask import Flask, render_template, request, redirect, url_for, flash
from pathlib import Path
from datetime import date, timedelta

from cooklang import load_all_recipes, load_recipe, save_recipe, parse_recipe
from models import (
    get_week_start, get_week_dates, get_all_templates, get_template, create_template,
    delete_template, update_template_name, get_template_meals, add_template_meal, remove_template_meal,
    get_or_create_active_week, apply_template_to_week, get_week_meals,
    add_week_meal, update_week_meal, remove_week_meal, toggle_meal_done, get_undone_meals
)
from git_sync import sync, get_status

app = Flask(__name__)
app.secret_key = 'change-this-in-production'

RECIPES_PATH = Path(__file__).parent / "reseptit"
DAYS_FI = ['Maanantai', 'Tiistai', 'Keskiviikko', 'Torstai', 'Perjantai', 'Lauantai', 'Sunnuntai']

# Configuration from environment
CHEFS = [c.strip() for c in os.environ.get('CHEFS', '').split(',') if c.strip()]
MEAL_SLOTS = int(os.environ.get('MEAL_SLOTS', '5'))


def get_recipes_dict():
    """Load recipes as a dict keyed by slug."""
    recipes = load_all_recipes(RECIPES_PATH)
    return {r.slug: r for r in recipes}


def format_date_fi(d: date) -> str:
    """Format date as Finnish weekday + date."""
    return f"{DAYS_FI[d.weekday()]} {d.day}.{d.month}."


# ============ Home / Week View ============

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


@app.route('/meal/<int:meal_id>/toggle', methods=['POST'])
def toggle_meal(meal_id):
    """Toggle meal done status."""
    is_done = toggle_meal_done(meal_id)
    if request.headers.get('HX-Request'):
        return f'<span class="toggle {"done" if is_done else ""}">{("✓" if is_done else "○")}</span>'
    return redirect(url_for('index'))


# ============ Recipes ============

@app.route('/recipes')
def recipes():
    """List all recipes."""
    all_recipes = load_all_recipes(RECIPES_PATH)
    return render_template('recipes.html', recipes=all_recipes)


@app.route('/recipe/<slug>')
def recipe(slug):
    """View a single recipe."""
    recipes = get_recipes_dict()
    recipe = recipes.get(slug)
    if not recipe:
        flash('Reseptia ei löydy', 'error')
        return redirect(url_for('recipes'))
    return render_template('recipe.html', recipe=recipe)


@app.route('/recipe/<slug>/edit', methods=['GET', 'POST'])
def edit_recipe(slug):
    """Edit a recipe."""
    filepath = None
    for f in RECIPES_PATH.rglob('*.cook'):
        if f.stem == slug:
            filepath = f
            break

    if request.method == 'POST':
        content = request.form.get('content', '')
        if filepath:
            save_recipe(filepath, content)
        else:
            # New recipe
            new_slug = request.form.get('slug', slug)
            filepath = RECIPES_PATH / "arkiruuat" / f"{new_slug}.cook"
            save_recipe(filepath, content)
        flash('Resepti tallennettu', 'success')
        return redirect(url_for('recipe', slug=filepath.stem))

    content = ""
    if filepath:
        content = filepath.read_text(encoding='utf-8')

    return render_template('editor.html', slug=slug, content=content, is_new=filepath is None)


@app.route('/recipe/new', methods=['GET', 'POST'])
def new_recipe():
    """Create a new recipe."""
    if request.method == 'POST':
        slug = request.form.get('slug', '').strip()
        content = request.form.get('content', '')

        if not slug:
            flash('Anna reseptille nimi', 'error')
            return render_template('editor.html', slug='', content=content, is_new=True)

        # Sanitize slug
        slug = slug.lower().replace(' ', '-').replace('a', 'a').replace('o', 'o').replace('a', 'a')

        filepath = RECIPES_PATH / "arkiruuat" / f"{slug}.cook"
        if filepath.exists():
            flash('Samanniminen resepti on jo olemassa', 'error')
            return render_template('editor.html', slug=slug, content=content, is_new=True)

        save_recipe(filepath, content)
        flash('Resepti luotu', 'success')
        return redirect(url_for('recipe', slug=slug))

    # Default template for new recipe
    template = """>> Reseptin nimi

Lisää @raaka-aine{määrä}.
Sekoita ja tarjoile.
"""
    return render_template('editor.html', slug='', content=template, is_new=True)


# ============ Templates ============

@app.route('/templates')
def templates():
    """List meal plan templates."""
    all_templates = get_all_templates()
    return render_template('templates.html', templates=all_templates)


@app.route('/template/new', methods=['POST'])
def new_template():
    """Create a new template."""
    name = request.form.get('name', '').strip()
    if name:
        create_template(name)
        flash(f'Pohja "{name}" luotu', 'success')
    return redirect(url_for('templates'))


@app.route('/template/<int:template_id>')
def template_detail(template_id):
    """View/edit a template."""
    template = get_template(template_id)
    if not template:
        flash('Pohjaa ei löydy', 'error')
        return redirect(url_for('templates'))

    meals = get_template_meals(template_id)
    recipes = get_recipes_dict()

    meal_list = []
    for meal in meals:
        recipe = recipes.get(meal['recipe_slug'])
        meal_list.append({
            'id': meal['id'],
            'recipe': recipe,
            'slug': meal['recipe_slug']
        })

    return render_template('template_detail.html',
        template=template,
        meals=meal_list,
        all_recipes=list(recipes.values())
    )


@app.route('/template/<int:template_id>/add-meal', methods=['POST'])
def add_template_meal_route(template_id):
    """Add a meal to a template."""
    recipe_slug = request.form.get('recipe_slug', '')

    if recipe_slug:
        add_template_meal(template_id, recipe_slug)

    return redirect(url_for('template_detail', template_id=template_id))


@app.route('/template/<int:template_id>/remove-meal/<int:meal_id>', methods=['POST'])
def remove_template_meal_route(template_id, meal_id):
    """Remove a meal from a template."""
    remove_template_meal(meal_id)
    return redirect(url_for('template_detail', template_id=template_id))


@app.route('/template/<int:template_id>/delete', methods=['POST'])
def delete_template_route(template_id):
    """Delete a template."""
    delete_template(template_id)
    flash('Pohja poistettu', 'success')
    return redirect(url_for('templates'))


@app.route('/template/<int:template_id>/rename', methods=['POST'])
def rename_template_route(template_id):
    """Rename a template."""
    new_name = request.form.get('name', '').strip()
    if not new_name:
        flash('Nimi ei voi olla tyhjä', 'error')
        return redirect(url_for('template_detail', template_id=template_id))

    if update_template_name(template_id, new_name):
        flash('Nimi päivitetty', 'success')
    else:
        flash('Nimen päivitys epäonnistui', 'error')

    return redirect(url_for('template_detail', template_id=template_id))


# ============ Week Setup ============

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


@app.route('/week/apply-template', methods=['POST'])
def apply_template():
    """Apply a template to this week."""
    template_id = int(request.form.get('template_id', 0))
    if template_id:
        apply_template_to_week(template_id)
        flash('Pohja asetettu viikolle', 'success')
    return redirect(url_for('week_setup'))


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


@app.route('/week/update-meal/<int:meal_id>', methods=['POST'])
def update_week_meal_route(meal_id):
    """Update a meal in the current week."""
    recipe_slug = request.form.get('recipe_slug', '')
    meal_date_str = request.form.get('meal_date', '')
    chef = request.form.get('chef', '')

    if not recipe_slug:
        # Empty recipe means remove
        remove_week_meal(meal_id)
    else:
        meal_date = date.fromisoformat(meal_date_str) if meal_date_str else None
        update_week_meal(
            meal_id,
            recipe_slug=recipe_slug,
            meal_date=meal_date,
            chef=chef if chef else None,
            clear_date=not meal_date_str,
            clear_chef=not chef
        )

    return redirect(url_for('week_setup'))


@app.route('/week/remove-meal/<int:meal_id>', methods=['POST'])
def remove_week_meal_route(meal_id):
    """Remove a meal from the current week."""
    remove_week_meal(meal_id)
    return redirect(url_for('week_setup'))


# ============ Shopping List ============

@app.route('/shopping')
def shopping():
    """Shopping list from undone meals."""
    undone = get_undone_meals()
    recipes = get_recipes_dict()

    # Aggregate ingredients
    ingredients = {}
    meal_list = []

    for meal in undone:
        recipe = recipes.get(meal['recipe_slug'])
        if recipe:
            meal_date = date.fromisoformat(meal['meal_date']) if meal['meal_date'] else None
            meal_list.append({
                'date_fi': format_date_fi(meal_date) if meal_date else 'Ei pvm',
                'recipe': recipe,
                'chef': meal['chef']
            })
            for ing in recipe.ingredients:
                key = ing.name.lower()
                if key in ingredients:
                    # Try to combine amounts
                    if ing.amount and ingredients[key]['amount']:
                        ingredients[key]['amount'] += f", {ing.amount}"
                    elif ing.amount:
                        ingredients[key]['amount'] = ing.amount
                else:
                    ingredients[key] = {
                        'name': ing.name,
                        'amount': ing.amount
                    }

    return render_template('shopping.html',
        ingredients=sorted(ingredients.values(), key=lambda x: x['name']),
        meals=meal_list
    )


# ============ Git Sync ============

@app.route('/sync')
def sync_page():
    """Git sync page."""
    status = get_status()
    return render_template('sync.html', status=status)


@app.route('/sync/do', methods=['POST'])
def do_sync():
    """Perform git sync."""
    result = sync()
    if result['success']:
        flash(result['message'], 'success')
    else:
        flash(result['message'], 'error')
    return redirect(url_for('sync_page'))


# ============ Run ============

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
