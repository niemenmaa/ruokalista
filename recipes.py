"""
Recipe loading and saving for JSON-based recipe format.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Ingredient:
    name: str
    amount: list = field(default_factory=list)  # [value, unit] or []

    def __str__(self):
        if self.amount:
            return f"{self.name} ({' '.join(self.amount)})"
        return self.name


@dataclass
class Phase:
    description: str
    ingredients: list = field(default_factory=list)  # indices into ingredient list
    time: list | None = None  # [value, unit] or None


@dataclass
class Section:
    title: str
    ingredients: list = field(default_factory=list)  # [Ingredient]
    phases: list = field(default_factory=list)  # [Phase]


@dataclass
class Recipe:
    slug: str
    title: str
    ingredients: list = field(default_factory=list)  # [Ingredient]
    phases: list = field(default_factory=list)  # [Phase]
    sections: list = field(default_factory=list)  # [Section]


def _parse_ingredients(raw_list):
    return [Ingredient(name=i["name"], amount=i.get("amount", [])) for i in raw_list]


def _parse_phases(raw_list):
    phases = []
    for p in raw_list:
        phase = Phase(
            description=p["description"],
            ingredients=p.get("ingredients", []),
            time=p.get("time"),
        )
        phases.append(phase)
    return phases


def load_recipe(filepath: Path) -> Recipe:
    """Load a recipe from a .json file."""
    data = json.loads(filepath.read_text(encoding="utf-8"))
    slug = filepath.stem

    if "sections" in data:
        sections = []
        for s in data["sections"]:
            sections.append(Section(
                title=s["title"],
                ingredients=_parse_ingredients(s.get("ingredients", [])),
                phases=_parse_phases(s.get("phases", [])),
            ))
        return Recipe(slug=slug, title=data["title"], sections=sections)
    else:
        return Recipe(
            slug=slug,
            title=data["title"],
            ingredients=_parse_ingredients(data.get("ingredients", [])),
            phases=_parse_phases(data.get("phases", [])),
        )


def load_all_recipes(recipes_dir: Path) -> list[Recipe]:
    """Load all .json recipes from a directory (recursive)."""
    recipes = []
    for json_file in recipes_dir.rglob("*.json"):
        try:
            recipe = load_recipe(json_file)
            recipes.append(recipe)
        except Exception as e:
            print(f"Error loading {json_file}: {e}")
    return sorted(recipes, key=lambda r: r.title)


def save_recipe(filepath: Path, recipe_dict: dict):
    """Write recipe dict as JSON."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(json.dumps(recipe_dict, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def recipe_to_dict(recipe: Recipe) -> dict:
    """Serialize a Recipe to a dict suitable for JSON / template use."""
    def ing_list(ingredients):
        return [{"name": i.name, "amount": i.amount} for i in ingredients]

    def phase_list(phases):
        result = []
        for p in phases:
            d = {"description": p.description}
            if p.ingredients:
                d["ingredients"] = p.ingredients
            if p.time:
                d["time"] = p.time
            result.append(d)
        return result

    if recipe.sections:
        return {
            "title": recipe.title,
            "sections": [
                {
                    "title": s.title,
                    "ingredients": ing_list(s.ingredients),
                    "phases": phase_list(s.phases),
                }
                for s in recipe.sections
            ],
        }
    else:
        return {
            "title": recipe.title,
            "ingredients": ing_list(recipe.ingredients),
            "phases": phase_list(recipe.phases),
        }


def all_ingredients(recipe: Recipe) -> list[Ingredient]:
    """Flat list of all ingredients across sections (or top-level)."""
    if recipe.sections:
        result = []
        for s in recipe.sections:
            result.extend(s.ingredients)
        return result
    return list(recipe.ingredients)


def format_amount(amount: list) -> str:
    """Format amount list as string: ['400', 'g'] -> '400 g', [] -> ''."""
    return " ".join(amount) if amount else ""
