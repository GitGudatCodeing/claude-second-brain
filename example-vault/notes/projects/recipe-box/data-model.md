# Recipe box data model

## Tables
- `recipe`: id, title, servings, notes, source_person, card_photo_path.
- `ingredient`: id, recipe_id, position, quantity, unit, name.
- `step`: id, recipe_id, position, text.
- `user`: id, email, display_name, last_login.

## Units
- Store quantities as decimals in the unit written on the card. Convert only when displaying.
- "A pinch" and "to taste" have no quantity; quantity is NULL and scaling leaves them unchanged.

## Search
- SQLite FTS5 over title and ingredient names, so "leek" finds "leeks".
