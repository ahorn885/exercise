from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import get_db

bp = Blueprint('locales', __name__)

LOCALES = ['home', 'hotel', 'partner', 'airport']

EQUIPMENT_CATEGORIES = [
    ('Free Weights', [
        ('barbell',     'Barbell (Olympic)'),
        ('ez_bar',      'EZ Curl Bar'),
        ('tricep_bar',  'Tricep Bar (W-bar)'),
        ('hex_bar',     'Hex / Trap Bar'),
        ('dumbbells',   'Dumbbells'),
        ('kettlebell',  'Kettlebell'),
        ('sandbag',     'Sandbag'),
        ('med_ball',    'Med Ball'),
        ('slam_ball',   'Slam Ball'),
    ]),
    ('Racks & Benches', [
        ('squat_rack',       'Squat Rack / Power Cage'),
        ('smith_machine',    'Smith Machine'),
        ('bench_flat',       'Flat Bench'),
        ('bench_adjustable', 'Adjustable / Incline Bench'),
        ('ghd',              'GHD / Hyperextension Bench'),
        ('preacher_bench',   'Preacher Curl Bench'),
    ]),
    ('Bars & Bodyweight Rigs', [
        ('pull_up_bar', 'Pull-Up Bar'),
        ('dip_bars',    'Dip Bars / Parallel Bars'),
        ('rings',       'Gymnastic Rings'),
    ]),
    ('Leg Machines', [
        ('leg_press',          'Leg Press'),
        ('hack_squat',         'Hack Squat Machine'),
        ('leg_extension',      'Leg Extension Machine'),
        ('leg_curl',           'Leg Curl Machine'),
        ('calf_raise_machine', 'Calf Raise Machine'),
    ]),
    ('Upper Body Machines', [
        ('cable_machine',          'Cable Machine / Crossover'),
        ('lat_pulldown',           'Lat Pulldown Machine'),
        ('seated_row_machine',     'Seated Row Machine'),
        ('pec_deck',               'Pec Deck / Chest Fly Machine'),
        ('shoulder_press_machine', 'Shoulder Press Machine'),
        ('assisted_pullup',        'Assisted Pull-Up / Dip Machine'),
    ]),
    ('Cardio', [
        ('treadmill',       'Treadmill'),
        ('elliptical',      'Elliptical / Cross Trainer'),
        ('stationary_bike', 'Stationary Bike (Upright)'),
        ('recumbent_bike',  'Recumbent Bike'),
        ('spin_bike',       'Spin Bike / Peloton'),
        ('stair_climber',   'Stair Climber / StepMill'),
        ('rowing_erg',      'Rowing Erg (Concept2)'),
        ('air_bike',        'Air Bike / Assault Bike'),
        ('ski_erg',         'SkiErg'),
    ]),
    ('Functional & Conditioning', [
        ('sled',             'Sled'),
        ('battle_ropes',     'Battle Ropes'),
        ('plyo_box',         'Plyo Box'),
        ('resistance_bands', 'Resistance Bands'),
        ('trx',              'TRX / Suspension Trainer'),
        ('weighted_vest',    'Weighted Vest'),
        ('jump_rope',        'Jump Rope'),
    ]),
    ('Accessories', [
        ('stability_ball', 'Stability Ball'),
        ('bosu',           'BOSU Ball'),
        ('ab_wheel',       'Ab Wheel'),
        ('foam_roller',    'Foam Roller'),
        ('rice_bucket',    'Rice Bucket'),
    ]),
    ('Specialty', [
        ('hangboard',     'Hangboard'),
        ('treadwall',     'Treadwall'),
        ('climbing_wall', 'Climbing Wall / Bouldering'),
    ]),
]

# Flat set of all valid tag keys for input validation
ALL_TAGS = {tag for _, items in EQUIPMENT_CATEGORIES for tag, _ in items}


@bp.route('/locales')
def list_profiles():
    db = get_db()
    profiles = {r['locale']: r for r in db.execute('SELECT * FROM locale_profiles').fetchall()}
    return render_template('locales/list.html', locales=LOCALES, profiles=profiles,
                           equipment_categories=EQUIPMENT_CATEGORIES)


@bp.route('/locales/<locale>/edit', methods=['GET', 'POST'])
def edit_profile(locale):
    if locale not in LOCALES:
        flash('Unknown locale.', 'danger')
        return redirect(url_for('locales.list_profiles'))
    db = get_db()
    if request.method == 'POST':
        selected = [t for t in request.form.getlist('equipment') if t in ALL_TAGS]
        notes = request.form.get('notes', '').strip()
        db.execute(
            '''INSERT INTO locale_profiles (locale, equipment, notes, updated_at)
               VALUES (?, ?, ?, datetime('now'))
               ON CONFLICT(locale) DO UPDATE SET
                 equipment=excluded.equipment,
                 notes=excluded.notes,
                 updated_at=excluded.updated_at''',
            (locale, ','.join(selected), notes)
        )
        db.commit()
        flash(f'{locale.title()} profile saved ({len(selected)} items).', 'success')
        return redirect(url_for('locales.list_profiles'))
    profile = db.execute('SELECT * FROM locale_profiles WHERE locale=?', (locale,)).fetchone()
    active = set((profile['equipment'] or '').split(',')) - {''} if profile else set()
    return render_template('locales/form.html', locale=locale,
                           equipment_categories=EQUIPMENT_CATEGORIES,
                           active=active,
                           notes=profile['notes'] if profile else '')
