"""
Ruokalista - Simple Cooklang recipe manager with meal planning.
"""
from flask import Flask, render_template, request, redirect, url_for, flash
from pathlib import Path
from datetime import date, timedelta

from cooklang import load_all_recipes, load_recipe, save_recipe, parse_recipe
from models import (
    get_week_start, get_all_templates, get_template, create_template, 
    delete_template, get_template_meals, set_template_meal, remove_template_meal,
    get_or_create_active_week, apply_template_to_week, get_week_meals,
    set_week_meal, remove_week_meal, toggle_meal_done, get_undone_meals
)
from git_sync import sync, get_status

app = Flask(__name__)
app.secret_key = 'change-this-in-production'

RECIPES_PATH = Path(__file__).parent / "reseptit"
DAYS_FI = ['Maanantai', 'Tiistai', 'Keskiviikko', 'Torstai', 'Perjantai', 'Lauantai', 'Sunnuntai']


def get_recipes_dict():
    """Load recipes as a dict keyed by slug."""
    recipes = load_all_recipes(RECIPES_PATH)
    return {r.slug: r for r in recipes}


# ============ Home / Week View ============

@app.route('/')
def index():
    """Home page - this week's meals."""
    week_start = get_week_start()
    week_meals = get_week_meals(week_start)
    recipes = get_recipes_dict()
    today = date.today().weekday()
    
    # Organize by day
    meals_by_day = {i: [] for i in range(7)}
    for meal in week_meals:
        recipe = recipes.get(meal['recipe_slug'])
        meals_by_day[meal['day']].append({
            'id': meal['id'],
            'recipe': recipe,
            'slug': meal['recipe_slug'],
            'is_done': meal['is_done'],
            'meal_type': meal['meal_type']
        })
    
    return render_template('week.html',
        meals_by_day=meals_by_day,
        days=DAYS_FI,
        today=today,
        week_start=week_start,
        week_end=week_start + timedelta(days=6)
    )


@app.route('/meal/<int:meal_id>/toggle', methods=['POST'])
def toggle_meal(meal_id):
    """Toggle meal done status."""
    is_done = toggle_meal_done(meal_id)
    if request.headers.get('HX-Request'):
        return f'<span class="{"done" if is_done else ""}">{("✓" if is_done else "○")}</span>'
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
        flash('Reseptiä ei löydy', 'error')
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
        slug = slug.lower().replace(' ', '-').replace('ä', 'a').replace('ö', 'o').replace('å', 'a')
        
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
    return render_template('templates.html', templates=all_templates, days=DAYS_FI)


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
    
    # Organize by day
    meals_by_day = {i: None for i in range(7)}
    for meal in meals:
        recipe = recipes.get(meal['recipe_slug'])
        meals_by_day[meal['day']] = {
            'recipe': recipe,
            'slug': meal['recipe_slug']
        }
    
    return render_template('template_detail.html',
        template=template,
        meals_by_day=meals_by_day,
        days=DAYS_FI,
        all_recipes=list(recipes.values())
    )


@app.route('/template/<int:template_id>/set-meal', methods=['POST'])
def set_template_meal_route(template_id):
    """Set a meal in a template."""
    day = int(request.form.get('day', 0))
    recipe_slug = request.form.get('recipe_slug', '')
    
    if recipe_slug:
        set_template_meal(template_id, day, recipe_slug)
    else:
        remove_template_meal(template_id, day)
    
    if request.headers.get('HX-Request'):
        return redirect(url_for('template_detail', template_id=template_id))
    return redirect(url_for('template_detail', template_id=template_id))


@app.route('/template/<int:template_id>/delete', methods=['POST'])
def delete_template_route(template_id):
    """Delete a template."""
    delete_template(template_id)
    flash('Pohja poistettu', 'success')
    return redirect(url_for('templates'))


# ============ Week Setup ============

@app.route('/week/setup')
def week_setup():
    """Setup this week's meals."""
    all_templates = get_all_templates()
    week_start = get_week_start()
    week = get_or_create_active_week(week_start)
    current_meals = get_week_meals(week_start)
    recipes = get_recipes_dict()
    
    # Organize current meals by day
    meals_by_day = {i: None for i in range(7)}
    for meal in current_meals:
        recipe = recipes.get(meal['recipe_slug'])
        meals_by_day[meal['day']] = {
            'recipe': recipe,
            'slug': meal['recipe_slug']
        }
    
    return render_template('week_setup.html',
        templates=all_templates,
        meals_by_day=meals_by_day,
        days=DAYS_FI,
        all_recipes=list(recipes.values()),
        week_start=week_start,
        current_template_id=week.get('template_id')
    )


@app.route('/week/apply-template', methods=['POST'])
def apply_template():
    """Apply a template to this week."""
    template_id = int(request.form.get('template_id', 0))
    if template_id:
        apply_template_to_week(template_id)
        flash('Pohja asetettu viikolle', 'success')
    return redirect(url_for('week_setup'))


@app.route('/week/set-meal', methods=['POST'])
def set_week_meal_route():
    """Set a meal in the current week."""
    day = int(request.form.get('day', 0))
    recipe_slug = request.form.get('recipe_slug', '')
    
    if recipe_slug:
        set_week_meal(day, recipe_slug)
    else:
        remove_week_meal(day)
    
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
            meal_list.append({
                'day': DAYS_FI[meal['day']],
                'recipe': recipe
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
