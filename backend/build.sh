#!/usr/bin/env bash
# exit on error
set -o errexit

echo "==> Installing dependencies..."
pip install -r requirements.txt

echo "==> Collecting static files..."
python manage.py collectstatic --no-input

echo "==> Running migrations..."
python manage.py migrate

echo "==> Seeding default meat types and cuts..."
python manage.py shell << 'EOF'
from inventory.models import MeatType, MeatCut

# ─────────────────────────────────────────────
# MEAT TYPES
# ─────────────────────────────────────────────
beef,    _ = MeatType.objects.get_or_create(name='Beef',    defaults={'description': 'Cattle meat — the most common butchery meat in Kenya'})
goat,    _ = MeatType.objects.get_or_create(name='Goat',    defaults={'description': 'Goat meat (mbuzi) — widely popular across Kenya'})
mutton,  _ = MeatType.objects.get_or_create(name='Mutton',  defaults={'description': 'Sheep/lamb meat — common in coastal and northern Kenya'})
pork,    _ = MeatType.objects.get_or_create(name='Pork',    defaults={'description': 'Pig meat — popular in western Kenya and urban centres'})
chicken, _ = MeatType.objects.get_or_create(name='Chicken', defaults={'description': 'Poultry — broiler and indigenous (kienyeji) chicken'})
offal,   _ = MeatType.objects.get_or_create(name='Offal',   defaults={'description': 'Organ meats and by-products (matumbo, liver, etc.)'})

# ─────────────────────────────────────────────
# BEEF CUTS  (spoilage_days reflects ~3–5°C cold chain)
# ─────────────────────────────────────────────
beef_cuts = [
    # name                      min_kg  days
    ('Fillet (Tenderloin)',       1.0,   3),
    ('Sirloin Steak',             1.5,   3),
    ('Ribeye',                    1.5,   3),
    ('T-Bone',                    2.0,   3),
    ('Striploin',                 2.0,   3),
    ('Rump Steak',                2.0,   4),
    ('Brisket',                   3.0,   4),
    ('Chuck',                     3.0,   4),
    ('Shoulder (Blade)',          3.0,   4),
    ('Topside',                   3.0,   4),
    ('Silverside',                3.0,   4),
    ('Shank (Mguu)',              2.0,   5),
    ('Oxtail',                    1.0,   4),
    ('Short Ribs',                2.5,   4),
    ('Back Ribs',                 2.5,   4),
    ('Spare Ribs',                2.5,   4),
    ('Mince (Ground Beef)',       5.0,   2),
    ('Stew Pieces (Mchuzi)',      4.0,   3),
    ('Nyama Choma Cuts',          5.0,   3),
    ('Offcut / Trim',             3.0,   2),
    ('Suet (Fat)',                1.0,   3),
    ('Marrow Bones',              1.5,   4),
]
for name, threshold, days in beef_cuts:
    MeatCut.objects.get_or_create(
        meat_type=beef, name=name,
        defaults={'min_stock_threshold': threshold, 'spoilage_days': days}
    )

# ─────────────────────────────────────────────
# GOAT CUTS
# ─────────────────────────────────────────────
goat_cuts = [
    ('Whole Goat (Live Weight)',  5.0,   4),
    ('Chops (Mbavu)',             2.0,   3),
    ('Leg (Mguu)',                2.0,   4),
    ('Shoulder',                  2.0,   4),
    ('Rack',                      1.5,   3),
    ('Saddle',                    2.0,   3),
    ('Loin',                      1.5,   3),
    ('Neck',                      1.5,   4),
    ('Ribs',                      2.0,   4),
    ('Stew Pieces',               3.0,   3),
    ('Nyama Choma Cuts',          3.0,   3),
    ('Mince',                     2.0,   2),
    ('Head (Kichwa)',             1.0,   2),
    ('Trotters (Miguu)',          1.0,   3),
]
for name, threshold, days in goat_cuts:
    MeatCut.objects.get_or_create(
        meat_type=goat, name=name,
        defaults={'min_stock_threshold': threshold, 'spoilage_days': days}
    )

# ─────────────────────────────────────────────
# MUTTON / LAMB CUTS
# ─────────────────────────────────────────────
mutton_cuts = [
    ('Leg',           2.0, 4),
    ('Shoulder',      2.0, 4),
    ('Rack of Lamb',  1.5, 3),
    ('Loin Chops',    1.5, 3),
    ('Rib Chops',     1.5, 3),
    ('Shank',         1.5, 4),
    ('Neck',          1.5, 4),
    ('Breast',        1.5, 3),
    ('Stew Pieces',   2.5, 3),
    ('Mince',         2.0, 2),
]
for name, threshold, days in mutton_cuts:
    MeatCut.objects.get_or_create(
        meat_type=mutton, name=name,
        defaults={'min_stock_threshold': threshold, 'spoilage_days': days}
    )

# ─────────────────────────────────────────────
# PORK CUTS
# ─────────────────────────────────────────────
pork_cuts = [
    ('Pork Chops',            2.0, 3),
    ('Pork Ribs (Spare)',     2.5, 3),
    ('Pork Ribs (Baby Back)', 2.0, 3),
    ('Pork Belly',            2.0, 3),
    ('Pork Shoulder (Butt)',  3.0, 4),
    ('Pork Leg (Ham)',        3.0, 4),
    ('Pork Loin',             2.0, 3),
    ('Tenderloin',            1.0, 3),
    ('Pork Mince',            3.0, 2),
    ('Pork Stew Pieces',      3.0, 3),
    ('Trotters (Miguu)',      1.5, 3),
    ('Pork Skin (Crackling)', 1.0, 2),
    ('Sausage Meat',          3.0, 2),
    ('Bacon Strips',          2.0, 5),
]
for name, threshold, days in pork_cuts:
    MeatCut.objects.get_or_create(
        meat_type=pork, name=name,
        defaults={'min_stock_threshold': threshold, 'spoilage_days': days}
    )

# ─────────────────────────────────────────────
# CHICKEN CUTS
# ─────────────────────────────────────────────
chicken_cuts = [
    ('Whole Chicken (Broiler)',      3.0, 2),
    ('Whole Chicken (Kienyeji)',     2.0, 2),
    ('Chicken Breast (Boneless)',    2.0, 2),
    ('Chicken Breast (Bone-in)',     2.0, 2),
    ('Chicken Thighs (Boneless)',    2.0, 2),
    ('Chicken Thighs (Bone-in)',     2.0, 2),
    ('Chicken Drumsticks',           2.5, 2),
    ('Chicken Wings',                2.0, 2),
    ('Chicken Quarters (Leg)',       2.5, 2),
    ('Chicken Quarters (Breast)',    2.5, 2),
    ('Chicken Back',                 1.5, 2),
    ('Chicken Neck',                 1.0, 2),
    ('Chicken Feet (Makongoro)',     2.0, 2),
    ('Chicken Giblets',              1.0, 1),
    ('Chicken Mince',                2.0, 1),
]
for name, threshold, days in chicken_cuts:
    MeatCut.objects.get_or_create(
        meat_type=chicken, name=name,
        defaults={'min_stock_threshold': threshold, 'spoilage_days': days}
    )

# ─────────────────────────────────────────────
# OFFAL / ORGAN MEATS  (short shelf life)
# ─────────────────────────────────────────────
offal_cuts = [
    ('Liver (Ini)',              2.0, 1),
    ('Kidney (Figo)',            1.5, 1),
    ('Heart (Moyo)',             1.5, 1),
    ('Tripe / Matumbo',         3.0, 1),
    ('Tongue (Ulimi)',           1.0, 2),
    ('Lung (Pafu)',              1.0, 1),
    ('Brain (Ubongo)',           0.5, 1),
    ('Spleen (Wengu)',           0.5, 1),
    ('Intestines (Utumbo)',      1.5, 1),
    ('Cow Skin (Ngozi / Kanda)', 2.0, 2),
    ('Blood Sausage (Mutura)',   1.5, 1),
    ('Testicles',                0.5, 1),
    ('Honeycomb Tripe',          1.5, 1),
    ('Mixed Offal Pack',         2.0, 1),
]
for name, threshold, days in offal_cuts:
    MeatCut.objects.get_or_create(
        meat_type=offal, name=name,
        defaults={'min_stock_threshold': threshold, 'spoilage_days': days}
    )

# ─────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────
total_types = MeatType.objects.count()
total_cuts  = MeatCut.objects.count()
print(f'✅ Seed complete — {total_types} meat types, {total_cuts} cuts created/verified.')
EOF

echo "==> Build complete!"