"""Structured §B health-input capture — health conditions + medications.

Lights up the Layer 2E supplement contraindication screening (§5.5): a logged
supplement is auto-removed + flagged when it contraindicates with an active
health condition (`system_category`) or medication (`medication_class`). Those
inputs had schema (`health_conditions_log` / `medications_log`) + Layer 1
readers but no capture surface; this module powers it on the profile, mirroring
the structured supplement capture (`athlete_supplements_repo`).

Closed vocabs are the §B enums (`athlete.KNOWN_SYSTEM_CATEGORIES` /
`KNOWN_MEDICATION_CLASSES`) — a posted value outside the set is rejected so a
crafted POST can't store a junk token. Capture writes current/active rows
(`status='Active'`, open `stopped_at`); the Resolved/history split is a later
enhancement.
"""

from __future__ import annotations

from athlete import KNOWN_MEDICATION_CLASSES, KNOWN_SYSTEM_CATEGORIES

# Token -> display label for the pickers + list rendering. Keys mirror the §B
# closed enums; any enum value without an explicit label falls back to a
# title-cased form at render time.
SYSTEM_CATEGORY_LABELS: dict[str, str] = {
    "cardiac": "Cardiac",
    "respiratory": "Respiratory",
    "metabolic": "Metabolic",
    "neurological": "Neurological",
    "gi_immune": "GI / Immune",
    "musculoskeletal": "Musculoskeletal",
    "endocrine": "Endocrine",
    "other": "Other",
}
MEDICATION_CLASS_LABELS: dict[str, str] = {
    "beta_blocker": "Beta blocker",
    "diuretic": "Diuretic",
    "nsaid_chronic": "NSAID (chronic)",
    "hrt": "Hormone therapy (HRT)",
    "ssri": "SSRI",
    "stimulant_adhd": "ADHD stimulant",
    "corticosteroid_chronic": "Corticosteroid (chronic)",
    "anticoagulant": "Anticoagulant",
    "thyroid_medication": "Thyroid medication",
    "pde5_inhibitor": "PDE5 inhibitor",
    "other": "Other",
}

# Ordered (value, label) choice lists for the add-form selects.
SYSTEM_CATEGORY_CHOICES: list[tuple[str, str]] = [
    (c, SYSTEM_CATEGORY_LABELS.get(c, c.replace("_", " ").title()))
    for c in KNOWN_SYSTEM_CATEGORIES
]
MEDICATION_CLASS_CHOICES: list[tuple[str, str]] = [
    (m, MEDICATION_CLASS_LABELS.get(m, m.replace("_", " ").title()))
    for m in KNOWN_MEDICATION_CLASSES
]

# Curated, training-relevant condition vocab per system category (#543), sourced
# from the reviewed `research/Vocabulary_Audit_v3.md` §2.2 canonical list mapped
# onto the live 8-category enum. Drives the add-form's system-filtered Condition
# select so capture is structured, not free text. The `other` category carries
# no list (free text only); each listed category also offers an "Other (not
# listed)" escape in the UI that *keeps* the system_category — so the Layer 2E
# screen (which keys on `system_category`, not the name) never loses signal.
#
# Inclusion rule (Andy 2026-06-17): list a condition ONLY if it changes *how*
# training is prescribed (HR ceilings, fueling, load/recovery management,
# return-to-load gating). Dropped: conditions with no training-prescription
# impact, conditions that outright prohibit the training this app programs
# (e.g. HCM), and mental-health conditions (no physical-training impact).
CONDITIONS_BY_CATEGORY: dict[str, list[str]] = {
    "cardiac": [
        # HR-ceiling enforcement; avoid max-effort / high-HR-spike work.
        "Hypertension", "Arrhythmia", "Post-MI / cardiac event",
        "Heart valve disorder",
    ],
    "respiratory": [
        # Interval-intensity management; cold-air / altitude protocols.
        "Asthma", "Exercise-induced bronchoconstriction", "COPD",
        "Post-COVID respiratory",
    ],
    "metabolic": [
        # Carb / fuel timing around sessions.
        "Type 1 diabetes", "Type 2 diabetes",
    ],
    "endocrine": [
        # Volume-ramp and cortisol-aware load management.
        "Hypothyroidism", "Hyperthyroidism", "Adrenal insufficiency",
    ],
    "gi_immune": [
        # Race-fueling / aid-station strategy; flare-aware load + recovery.
        "IBS", "IBD / Crohn's / colitis", "Celiac disease",
        "Chronic reflux (GERD)", "Rheumatoid arthritis", "Lupus", "MCAS",
    ],
    "musculoskeletal": [
        # Permanent regression chains; flare-aware load management.
        "Osteoarthritis", "Fibromyalgia", "Hypermobility / EDS",
    ],
    "neurological": [
        # Return-to-load gating; coordination / seizure-risk caution.
        "Concussion history", "Migraine", "Epilepsy / seizure disorder",
        "Multiple sclerosis", "Peripheral neuropathy",
    ],
}


def clean_severity(value: str | None) -> int | None:
    """1–5 or None — anything else (blank, out of range, non-numeric) → None."""
    try:
        sev = int((value or "").strip())
    except (ValueError, TypeError):
        return None
    return sev if 1 <= sev <= 5 else None


# ─── Health conditions ──────────────────────────────────────────────────────


def list_health_conditions(db, user_id) -> list[dict]:
    """The athlete's active health-condition records, newest first."""
    if user_id is None:
        return []
    rows = db.execute(
        "SELECT id, system_category, condition_name, severity, notes "
        "  FROM health_conditions_log "
        " WHERE user_id = ? AND status = 'Active' "
        " ORDER BY created_at DESC, id DESC",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def add_health_condition(
    db, user_id, *, system_category: str, condition_name: str,
    severity: int | None, notes: str | None,
) -> bool:
    """Insert one active condition. Returns False (no insert) when the category
    isn't in the §B vocab or the name is blank. Caller commits."""
    if system_category not in KNOWN_SYSTEM_CATEGORIES:
        return False
    name = (condition_name or "").strip()
    if not name:
        return False
    db.execute(
        "INSERT INTO health_conditions_log "
        "  (user_id, system_category, condition_name, severity, notes, status) "
        "VALUES (?, ?, ?, ?, ?, 'Active')",
        (user_id, system_category, name, severity, notes),
    )
    return True


def delete_health_condition(db, user_id, condition_id) -> None:
    """Delete one condition, scoped on `user_id` so a crafted POST can't reach
    another athlete's row. Caller commits."""
    db.execute(
        "DELETE FROM health_conditions_log WHERE id = ? AND user_id = ?",
        (condition_id, user_id),
    )


# ─── Medications ────────────────────────────────────────────────────────────


def list_medications(db, user_id) -> list[dict]:
    """The athlete's active (not-stopped) medication records, newest first."""
    if user_id is None:
        return []
    rows = db.execute(
        "SELECT id, medication_class, medication_name, notes "
        "  FROM medications_log "
        " WHERE user_id = ? AND stopped_at IS NULL "
        " ORDER BY created_at DESC, id DESC",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def add_medication(
    db, user_id, *, medication_class: str, medication_name: str | None,
    notes: str | None,
) -> bool:
    """Insert one active medication. Returns False (no insert) when the class
    isn't in the §B vocab. Caller commits."""
    if medication_class not in KNOWN_MEDICATION_CLASSES:
        return False
    db.execute(
        "INSERT INTO medications_log "
        "  (user_id, medication_class, medication_name, notes) "
        "VALUES (?, ?, ?, ?)",
        (user_id, medication_class, (medication_name or "").strip() or None, notes),
    )
    return True


def delete_medication(db, user_id, medication_id) -> None:
    """Delete one medication, scoped on `user_id`. Caller commits."""
    db.execute(
        "DELETE FROM medications_log WHERE id = ? AND user_id = ?",
        (medication_id, user_id),
    )
