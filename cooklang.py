"""
Minimal Cooklang parser for extracting recipe data.
"""
import re
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class Ingredient:
    name: str
    amount: str = ""
    
    def __str__(self):
        if self.amount:
            return f"{self.name} ({self.amount})"
        return self.name


@dataclass
class Recipe:
    slug: str
    title: str
    sections: list = field(default_factory=list)  # [(section_name, [steps])]
    ingredients: list = field(default_factory=list)  # [Ingredient]
    raw_content: str = ""


def parse_ingredient(match: str) -> Ingredient:
    """Parse @ingredient{amount} or @ingredient{}"""
    # Match: @name{amount} or @name{}
    pattern = r'@([a-zA-ZäöåÄÖÅ_\-]+)\{([^}]*)\}'
    m = re.match(pattern, match)
    if m:
        return Ingredient(name=m.group(1).replace('_', ' '), amount=m.group(2))
    # Match: @name (no braces, single word)
    pattern2 = r'@([a-zA-ZäöåÄÖÅ_\-]+)'
    m2 = re.match(pattern2, match)
    if m2:
        return Ingredient(name=m2.group(1).replace('_', ' '))
    return Ingredient(name=match)


def parse_recipe(content: str, slug: str = "") -> Recipe:
    """Parse a .cook file content into a Recipe object."""
    lines = content.strip().split('\n')
    
    title = slug.replace('-', ' ').title()
    sections = []
    ingredients = []
    current_section = "Ohjeet"
    current_steps = []
    
    # Find all ingredients in the content
    ingredient_pattern = r'@([a-zA-ZäöåÄÖÅ_\-]+)\{([^}]*)\}'
    for match in re.finditer(ingredient_pattern, content):
        name = match.group(1).replace('_', ' ')
        amount = match.group(2)
        ing = Ingredient(name=name, amount=amount)
        # Avoid duplicates by name
        if not any(i.name == ing.name for i in ingredients):
            ingredients.append(ing)
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Recipe title: >> Title
        if line.startswith('>>'):
            title = line[2:].strip()
            continue
        
        # Section header: # Section Name
        if line.startswith('#') and not line.startswith('##'):
            # Save previous section
            if current_steps:
                sections.append((current_section, current_steps))
            current_section = line[1:].strip()
            current_steps = []
            continue
        
        # Regular step line - convert cooklang markup to readable text
        readable_line = line
        # Replace @ingredient{amount} with just ingredient name
        readable_line = re.sub(r'@([a-zA-ZäöåÄÖÅ_\-]+)\{[^}]*\}', 
                               lambda m: m.group(1).replace('_', ' '), 
                               readable_line)
        # Replace #tool{} with tool name
        readable_line = re.sub(r'#([a-zA-ZäöåÄÖÅ_\-]+)\{[^}]*\}',
                               lambda m: m.group(1).replace('_', ' '),
                               readable_line)
        # Replace ~{time} with time
        readable_line = re.sub(r'~\{([^}]*)\}', r'\1', readable_line)
        
        if readable_line.strip():
            current_steps.append(readable_line.strip())
    
    # Don't forget the last section
    if current_steps:
        sections.append((current_section, current_steps))
    
    return Recipe(
        slug=slug,
        title=title,
        sections=sections,
        ingredients=ingredients,
        raw_content=content
    )


def load_recipe(filepath: Path) -> Recipe:
    """Load a recipe from a .cook file."""
    content = filepath.read_text(encoding='utf-8')
    slug = filepath.stem
    return parse_recipe(content, slug)


def load_all_recipes(recipes_dir: Path) -> list[Recipe]:
    """Load all .cook recipes from a directory (recursive)."""
    recipes = []
    for cook_file in recipes_dir.rglob('*.cook'):
        try:
            recipe = load_recipe(cook_file)
            recipes.append(recipe)
        except Exception as e:
            print(f"Error loading {cook_file}: {e}")
    return sorted(recipes, key=lambda r: r.title)


def save_recipe(filepath: Path, content: str):
    """Save recipe content to a .cook file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content, encoding='utf-8')
