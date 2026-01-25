# Flexible Meal Planning Design

## Overview

Replace fixed 7-day weekday structure with flexible N-meal planning. Add optional date and chef assignment for each meal.

## Data Model

### template_meals (updated)
- `id` INTEGER PRIMARY KEY
- `template_id` INTEGER (FK)
- `recipe_slug` TEXT
- `position` INTEGER (for ordering)

### week_meals (updated)
- `id` INTEGER PRIMARY KEY
- `week_id` INTEGER (FK)
- `recipe_slug` TEXT
- `meal_date` DATE (nullable - within current week)
- `chef` TEXT (nullable - from CHEFS env)
- `position` INTEGER (for ordering)
- `is_done` INTEGER

### Environment Variables
- `CHEFS=Name1,Name2,Name3` - comma-separated list of chefs
- `MEAL_SLOTS=5` - default number of meal slots (optional, defaults to 5)

## UI Changes

### Weekly View
- Single list of meals (not 7 day sections)
- Each card shows: recipe, date, chef, done toggle
- Sorted by date (nulls last), then position

### Week Setup
- List of meal rows with dropdowns: recipe, date, chef
- Date dropdown: Finnish weekday + date (e.g., "Maanantai 20.1.")
- Chef dropdown: names from CHEFS env
- 5 default slots, "Lisää ruoka" button for more
- X button to remove meals

### Templates
- Simple recipe list with ordering
- Applying copies recipes without dates/chefs

## Implementation Tasks

1. Update `models.py` - new schema and functions
2. Update `app.py` - CHEFS parsing, updated routes
3. Update `week.html` - new list-based view
4. Update `week_setup.html` - new editing UI
5. Update `template_detail.html` - simplified recipe list
