# AIDSTATION — Database Reference

**This file is a stale duplicate, retired 2026-05-16 (PR14 doc-sweep).**

The live database reference for the v1 Flask app lives at the **repo root: `DATABASE.md`**. That document was rewritten 2026-05-16 (PR13) for the PG-only / Vercel-only deployment posture and is kept current as schema lands.

This copy diverged from the root over the v2 design wave (≈200 lines short of the root, missing later v1-maintenance additions like the `admin_audit` table + `/admin/audit` page). Rather than re-sync line-by-line, the duplicate is collapsed to this pointer so there is one source of truth.

**For current schema reality:**

- Live source of truth: root `DATABASE.md` (overview + architecture) + `init_db.py`'s `PG_SCHEMA` + `_PG_MIGRATIONS` list (the actual on-disk migration history).
- `layer0.*` catalog schema: `Layer0_ETL_Spec_v7.md` (in this directory).
- Integration tables (`provider_auth`, `polar_*`, `wahoo_*`, `coros_*`, webhook_events, etc.): `Athlete_Data_Integration_Spec_v5.md` (in this directory) + `PROVIDERS_SCHEMA.md` (repo root).

**For v2 design-wave-specific schema decisions** that this duplicate historically captured (the dual-backend strategy, type-compat notes, the multi-user scoping doctrine in §3): those are now stale (dual-backend retired 2026-05-16, PR13). The doctrinal content lives in the layer specs that consumed it; the table reference content has rotted past the point of useful repair without a full rewrite.

If a forward-looking equivalent of this doc is wanted in `aidstation-sources/` later, it should be re-derived from the live root `DATABASE.md` rather than rebuilt from this stale text.

---

*End of pointer. Original v2-design-wave content available in git history pre-PR14 if needed for archaeology.*
