"""Health-screening capture + storage (AIDSTATION Health Screening Spec v2).

One current-state row per user in `health_screening`: the structured `flags`
(PAR-Q+-derived, Spec §4/§5), optional per-flag free-text `details` (sensitive —
stored only under explicit opt-in, Spec §7.2), the acknowledgment, and the
annual-reassessment timestamps (Spec §9). The flow is acknowledgment-only and
non-blocking: flags are coaching context, never a plan-gen gate (Spec §2.3).

The screens live in `routes/onboarding.py`; this module owns the question set,
the flag taxonomy, answer parsing, and the upsert. Mirrors the structured-capture
repo pattern (`pack_load_repo`): `?` placeholders, user-scoped, caller commits.
"""

from __future__ import annotations

import json

# Bumping the question set / flag taxonomy requires a version bump (Spec §5).
SCREENING_VERSION = "v1"

# Spec §4 — 10 plain-English yes/no questions. A "yes" sets the flag code.
QUESTIONS = (
    {"num": 1, "code": "CARDIO_CHEST_PAIN",
     "text": "Have you had chest pain or discomfort at rest, or pain that gets "
             "worse with activity?"},
    {"num": 2, "code": "CARDIO_SYNCOPE",
     "text": "Have you lost balance because of dizziness, or lost consciousness, "
             "in the past 12 months?"},
    {"num": 3, "code": "CARDIO_CONDITION",
     "text": "Have you been diagnosed with a heart condition, high blood "
             "pressure, or do you have a family history of early cardiac events?"},
    {"num": 4, "code": "METABOLIC_CONDITION",
     "text": "Do you have diabetes, kidney disease, liver disease, or another "
             "metabolic disorder?"},
    {"num": 5, "code": "MSK_CONDITION",
     "text": "Do you have a bone, joint, soft tissue, or chronic pain condition "
             "currently affected by exercise, or have you had surgery in the "
             "past 6 months?"},
    {"num": 6, "code": "ED_CONDITION",
     "text": "Do you have, or have you had, an eating disorder, or do you "
             "currently have concerns about disordered eating?"},
    {"num": 7, "code": "MH_CONDITION",
     "text": "Are you currently being treated for a mental health condition, "
             "including depression or anxiety?"},
    {"num": 8, "code": "PREGNANCY",
     "text": "Are you currently pregnant, or within 6 months postpartum?"},
    {"num": 9, "code": "PRESCRIPTION_OTHER",
     "text": "Do you take prescription medication for any condition not already "
             "noted above?"},
    {"num": 10, "code": "OTHER_CONDITION",
     "text": "Is there any other condition for which you believe you should "
             "consult a physician before exercise?"},
)

# Spec §5 — canonical taxonomy → acknowledgment plain-language string.
FLAG_LABELS = {
    "CARDIO_CHEST_PAIN": "Chest pain at rest or worsened by activity",
    "CARDIO_SYNCOPE": "Dizziness causing loss of balance, or loss of "
                      "consciousness, in the past 12 months",
    "CARDIO_CONDITION": "Diagnosed heart condition, high blood pressure, or "
                        "family history of cardiac events",
    "METABOLIC_CONDITION": "Diabetes, kidney disease, liver disease, or other "
                           "metabolic disorder",
    "MSK_CONDITION": "Bone, joint, soft tissue, or chronic pain condition, or "
                     "recent surgery",
    "ED_CONDITION": "Current or past eating disorder, or current concerns about "
                    "disordered eating",
    "MH_CONDITION": "Mental health condition currently being treated",
    "PREGNANCY": "Currently pregnant or within 6 months postpartum",
    "PRESCRIPTION_OTHER": "Prescription medication for a condition not already "
                          "noted",
    "OTHER_CONDITION": "Other condition warranting medical consultation",
}

PREGNANCY_FLAG = "PREGNANCY"


def _is_yes(value) -> bool:
    return (value or "").strip().lower() == "yes"


def parse_answers(form) -> tuple[list[str], dict, bool]:
    """Parse the questions form into `(flags, details, details_optin)`.

    - `flags`: codes whose `q{num}` answer is "yes", in question order.
    - `details`: `{code: text}` for flagged items with non-empty free text —
      only when the sensitive-storage opt-in is on (Spec §7.2).
    - `details_optin`: the opt-in checkbox state.
    """
    optin = (form.get("details_optin") or "").strip().lower() in ("on", "1", "true")
    flags: list[str] = []
    details: dict[str, str] = {}
    for q in QUESTIONS:
        if _is_yes(form.get(f"q{q['num']}")):
            code = q["code"]
            flags.append(code)
            if optin:
                text = (form.get(f"detail_{code}") or "").strip()
                if text:
                    details[code] = text
    return flags, details, optin


def flag_descriptions(flags) -> list[str]:
    """Plain-language strings for the acknowledgment screen, in `flags` order."""
    return [FLAG_LABELS[c] for c in flags if c in FLAG_LABELS]


def get_screening(db, user_id) -> dict | None:
    """The user's current acknowledged screening, or None.

    `reassessment_overdue` is computed live (Spec §6.2): true when the due date
    has passed. JSONB `flags`/`details` round-trip as Python list/dict.
    """
    if user_id is None:
        return None
    row = db.execute(
        "SELECT user_id, screening_version, flags, details, details_optin, "
        "       acknowledged, acknowledged_at, last_assessed_at, "
        "       reassessment_due_at, "
        "       (reassessment_due_at IS NOT NULL "
        "        AND reassessment_due_at < NOW()) AS reassessment_overdue "
        "  FROM health_screening "
        " WHERE user_id = ? AND acknowledged = TRUE",
        (user_id,),
    ).fetchone()
    return dict(row) if row else None


def save_screening(db, user_id, *, flags, details, details_optin) -> None:
    """Upsert the user's screening as acknowledged now (Spec §3.3).

    `last_assessed_at`/`acknowledged_at` = NOW(); `reassessment_due_at` =
    NOW() + 365 days (Spec §9.1). `details` is persisted only under opt-in
    (Spec §7.2); otherwise stored empty. Caller commits.
    """
    stored_details = details if details_optin else {}
    db.execute(
        """INSERT INTO health_screening
               (user_id, screening_version, flags, details, details_optin,
                acknowledged, acknowledged_at, last_assessed_at,
                reassessment_due_at, updated_at)
            VALUES (?, ?, ?, ?, ?, TRUE, NOW(), NOW(),
                    NOW() + INTERVAL '365 days', NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                screening_version = EXCLUDED.screening_version,
                flags = EXCLUDED.flags,
                details = EXCLUDED.details,
                details_optin = EXCLUDED.details_optin,
                acknowledged = TRUE,
                acknowledged_at = NOW(),
                last_assessed_at = NOW(),
                reassessment_due_at = NOW() + INTERVAL '365 days',
                updated_at = NOW()""",
        (
            user_id,
            SCREENING_VERSION,
            json.dumps(list(flags)),
            json.dumps(stored_details),
            bool(details_optin),
        ),
    )
