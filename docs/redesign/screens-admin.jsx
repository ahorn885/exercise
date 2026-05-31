/* AIDSTATION redesign — Admin pages (desktop-only · internal/dev surface)
   ───────────────────────────────────────────────────────────────────
   Extends §19 Admin (users table) with the surfaces its CTAs imply:
     19B · Audit log        (real route: admin.audit)
     19C · User detail      (drill-in from the users table)
     19D · Delete user      (destructive confirm — type-to-confirm)
   Grounded in the real data model: deleting a user cascades across
   25 per-user scoped tables; shared catalogs are untouched; the admin
   user (id 1) cannot be deleted. */

// ─── Shared admin chrome ──────────────────────────────────────────
const AdminTabs = ({ active }) => (
  <div role="tablist" aria-label="Admin sections" style={{ display: "flex", gap: 0, marginBottom: 22, borderBottom: "1px solid var(--hairline-2)" }}>
    {[
      ["users", "Users"],
      ["audit", "Audit log"],
      ["health", "System"],
    ].map(([key, label]) => {
      const on = key === active;
      return (
        <div key={key} role="tab" aria-selected={on ? "true" : "false"} tabIndex={on ? 0 : -1} style={{
          padding: "10px 18px",
          borderBottom: "2px solid " + (on ? "var(--accent)" : "transparent"),
          marginBottom: -1,
          cursor: "pointer",
          fontSize: 14,
          fontWeight: on ? 600 : 500,
          color: on ? "var(--fg)" : "var(--fg-3)",
        }}>{label}</div>
      );
    })}
    <div style={{ flex: 1 }} />
    <div className="mono" style={{ fontSize: 10, letterSpacing: "0.16em", color: "var(--bad)", padding: "12px 0", textTransform: "uppercase" }}>
      ● ADMIN · andrew@aidstation.run
    </div>
  </div>
);

// The 25 per-user scoped tables (real cascade target), with sample counts.
const SCOPED_TABLES = [
  ["strength_logs", 218], ["cardio_logs", 482], ["body_metrics", 96], ["wellness_logs", 142],
  ["condition_logs", 38], ["injury_logs", 4], ["plans", 2], ["plan_versions", 9],
  ["plan_sessions", 612], ["session_completions", 388], ["rx_exercises", 42], ["athlete_skill_toggles", 12],
  ["locations", 3], ["location_equipment", 68], ["fit_uploads", 312], ["fit_records", 41982],
  ["provider_connections", 2], ["oauth_tokens", 2], ["provider_webhooks", 1140], ["performance_baselines", 6],
  ["schedule_windows", 7], ["race_targets", 4], ["notifications", 326], ["notification_prefs", 1],
  ["audit_actor_rows", 204],
];

// ═══════════════════════════════════════════════════════════════════
// 19B. ADMIN · AUDIT LOG  (admin.audit)
// ═══════════════════════════════════════════════════════════════════
const ACTION_TONES = {
  USER_DELETE: "bad", OAUTH_REVOKE: "warn", LOGIN_FAIL: "warn",
  PLAN_GENERATE: "accent", FIT_UPLOAD: null, LOGIN: null,
  OAUTH_CONNECT: "good", PLAN_IMPORT: "accent", ADMIN_VIEW: null, USER_EXPORT: "warn",
};

const ScreenAdminAudit = () => {
  const rows = [
    { t: "2026-05-29 09:14:02", actor: "ahorn", action: "ADMIN_VIEW",    target: "admin/users",            req: "req_8f21a0", result: "200" },
    { t: "2026-05-29 08:52:41", actor: "sarah.k", action: "PLAN_GENERATE", target: "gen_4a1c · Berlin ’26", req: "req_8e02b7", result: "200" },
    { t: "2026-05-29 08:40:18", actor: "marc.w", action: "FIT_UPLOAD",    target: "activity_…1844.fit",     req: "req_8dfa31", result: "201" },
    { t: "2026-05-29 07:33:55", actor: "—",       action: "LOGIN_FAIL",   target: "rp@example.com",          req: "req_8d77c9", result: "401" },
    { t: "2026-05-28 22:10:07", actor: "ahorn",   action: "USER_DELETE",  target: "user:14 · spam.bot",      req: "req_8c4e10", result: "200" },
    { t: "2026-05-28 19:48:33", actor: "jenny.t", action: "OAUTH_CONNECT", target: "wahoo",                  req: "req_8bd221", result: "200" },
    { t: "2026-05-28 18:21:59", actor: "lin.h",   action: "PLAN_IMPORT",  target: "plan_v3 · JSON 41 KB",    req: "req_8b9a04", result: "200" },
    { t: "2026-05-28 16:05:12", actor: "anna.b",  action: "OAUTH_REVOKE", target: "strava",                  req: "req_8b1188", result: "200" },
    { t: "2026-05-28 14:24:07", actor: "darius.j", action: "FIT_UPLOAD",  target: "swim_session.fit",        req: "req_8aef55", result: "422" },
    { t: "2026-05-28 11:02:44", actor: "ahorn",   action: "USER_EXPORT",  target: "user:5 · ramon.p",        req: "req_8a7c01", result: "200" },
    { t: "2026-05-28 09:15:21", actor: "sarah.k", action: "LOGIN",        target: "session start",           req: "req_8a0fd2", result: "200" },
    { t: "2026-05-27 21:40:03", actor: "ahorn",   action: "ADMIN_VIEW",   target: "admin/audit",             req: "req_89c7a8", result: "200" },
  ];
  return (
    <div className="screen">
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <Sidebar active="athlete" />
        <div className="page">
          <TopBar crumbs={["Admin", "Audit log"]} actions={
            <>
              <div className="btn btn-ghost btn-sm"><Ic d={I.clock} size={11} /> Last 7 days</div>
              <div className="btn btn-ghost btn-sm"><Ic d={I.download} size={11} /> Export CSV</div>
            </>
          } />
          <div className="page-body">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 18 }}>
              <div>
                <Eyebrow>Admin · immutable action log</Eyebrow>
                <h1 className="page-title" style={{ marginTop: 8 }}>Audit log</h1>
                <div className="page-sub">Every privileged + state-changing action, append-only. Each row carries a request_id you can match against application logs.</div>
              </div>
              <div style={{ display: "flex", gap: 14 }}>
                {[["Events 7d", "1,204"], ["Deletes", "1"], ["Failures", "2"], ["Admins", "1"]].map(([k, v], i) => (
                  <div key={i} className="stat-card" style={{ minWidth: 96, padding: 14 }}>
                    <div className="k">{k}</div>
                    <div className="v num" style={{ fontSize: 22, color: k === "Deletes" || k === "Failures" ? "var(--bad)" : "var(--fg)" }}>{v}</div>
                  </div>
                ))}
              </div>
            </div>

            <AdminTabs active="audit" />

            {/* Filters */}
            <div className="card" style={{ padding: "10px 16px", marginBottom: 12, display: "flex", gap: 10, alignItems: "center" }}>
              <Ic d={I.search} size={14} />
              <span style={{ flex: 1, color: "var(--fg-3)", fontSize: 13 }}>Filter by actor, action, target, or request_id…</span>
              {["All", "Deletes", "Auth", "OAuth", "Plans", "Uploads", "Failures"].map((f, i) => (
                <Pill key={i} tone={i === 0 ? "accent" : null}>{f.toUpperCase()}</Pill>
              ))}
            </div>

            {/* Log table */}
            <div className="card" style={{ padding: 0 }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr>
                    {["Timestamp (UTC)", "Actor", "Action", "Target", "Request ID", "Result"].map((h, i) => (
                      <th key={i} className="mono" style={{ padding: "12px 16px", textAlign: i === 5 ? "right" : "left", fontSize: 9, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--fg-3)", fontWeight: 500, borderBottom: "1px solid var(--hairline-2)" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => {
                    const fail = r.result !== "200" && r.result !== "201";
                    return (
                      <tr key={i} style={{ borderBottom: i < rows.length - 1 ? "1px solid var(--hairline-2)" : "none" }}>
                        <td className="mono" style={{ padding: "11px 16px", color: "var(--fg-3)", fontSize: 11, whiteSpace: "nowrap" }}>{r.t}</td>
                        <td style={{ padding: "11px 16px", fontWeight: 600, fontFamily: "var(--mono)", fontSize: 12 }}>{r.actor}</td>
                        <td style={{ padding: "11px 16px" }}><Pill tone={ACTION_TONES[r.action]}>{r.action}</Pill></td>
                        <td style={{ padding: "11px 16px", color: "var(--fg-2)", fontFamily: "var(--mono)", fontSize: 12 }}>{r.target}</td>
                        <td className="mono" style={{ padding: "11px 16px", color: "var(--accent)", fontSize: 11 }}>{r.req}</td>
                        <td className="mono num" style={{ padding: "11px 16px", textAlign: "right", fontSize: 12, color: fail ? "var(--bad)" : "var(--good)" }}>{r.result}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <div style={{ padding: "10px 16px", borderTop: "1px solid var(--hairline-2)", display: "flex", justifyContent: "space-between" }}>
                <span className="mono" style={{ fontSize: 9, letterSpacing: "0.16em", color: "var(--fg-3)" }}>SHOWING 12 OF 1,204</span>
                <span className="mono" style={{ fontSize: 9, letterSpacing: "0.16em", color: "var(--accent)" }}>LOAD MORE →</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════
// 19C. ADMIN · USER DETAIL  (drill-in from the users table)
// ═══════════════════════════════════════════════════════════════════
const ScreenAdminUser = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="athlete" />
      <div className="page">
        <TopBar crumbs={["Admin", "Users", "sarah.k"]} actions={
          <>
            <div className="btn btn-ghost btn-sm"><Ic d={I.download} size={11} /> Export data</div>
            <div className="btn btn-ghost btn-sm">Impersonate</div>
          </>
        } />
        <div className="page-body">
          {/* Identity header */}
          <div style={{ display: "flex", gap: 16, alignItems: "center", marginBottom: 20 }}>
            <div style={{ width: 56, height: 56, borderRadius: 8, background: "var(--bg-3)", color: "var(--fg-2)", display: "grid", placeItems: "center", fontFamily: "var(--mono)", fontWeight: 700, fontSize: 20, flexShrink: 0 }}>
              SK
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <h1 className="page-title" style={{ margin: 0 }}>Sarah Kowalski</h1>
                <Pill tone="accent">PRO</Pill>
                <Pill tone="good">ACTIVE</Pill>
              </div>
              <div className="mono" style={{ fontSize: 11, letterSpacing: "0.14em", color: "var(--fg-3)", marginTop: 6, textTransform: "uppercase" }}>
                user:2 · sarah.k · sarah@example.com · member since FEB 2026 · last login TODAY
              </div>
            </div>
          </div>

          {/* Quick stats */}
          <div className="row" style={{ marginBottom: 22 }}>
            {[
              ["Strength logs", "218"], ["Cardio logs", "482"], ["Active plans", "2"],
              ["Connections", "1"], ["FIT files", "312"], ["Storage", "84 MB"],
            ].map(([k, v], i) => (
              <div key={i} className="stat-card col" style={{ padding: 14 }}>
                <div className="k" style={{ fontSize: 9 }}>{k}</div>
                <div className="v num" style={{ fontSize: 22 }}>{v}</div>
              </div>
            ))}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1.3fr 1fr", gap: 18 }}>
            {/* LEFT — data footprint (the cascade target) */}
            <div className="card" style={{ padding: 0 }}>
              <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--hairline-2)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <Eyebrow>Data footprint · 25 scoped tables</Eyebrow>
                <span className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--fg-3)" }}>ROWS THAT DELETE CASCADES</span>
              </div>
              <div style={{ maxHeight: 360, overflow: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                  <tbody>
                    {SCOPED_TABLES.map(([name, count], i) => (
                      <tr key={i} style={{ borderBottom: i < SCOPED_TABLES.length - 1 ? "1px solid var(--hairline-2)" : "none" }}>
                        <td className="mono" style={{ padding: "8px 16px", color: "var(--fg-2)" }}>{name}</td>
                        <td className="mono num" style={{ padding: "8px 16px", textAlign: "right", color: count === 0 ? "var(--fg-4)" : "var(--fg)" }}>{count.toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div style={{ padding: "10px 16px", borderTop: "1px solid var(--hairline-2)", display: "flex", justifyContent: "space-between" }}>
                <span className="mono" style={{ fontSize: 10, letterSpacing: "0.14em", color: "var(--fg-3)" }}>TOTAL ROWS</span>
                <span className="mono num" style={{ fontSize: 12, fontWeight: 700 }}>46,540</span>
              </div>
            </div>

            {/* RIGHT — connections, plans, danger zone */}
            <div className="stack">
              <div className="card" style={{ padding: 18 }}>
                <Eyebrow>Connections · 1 active</Eyebrow>
                <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 8 }}>
                  {[["Strava", "synced today · 482 sessions", "good"], ["Wahoo", "not connected", null]].map(([n, s, tone], i) => (
                    <div key={i} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <div style={{ width: 28, height: 28, borderRadius: 4, background: tone ? "var(--accent)" : "var(--bg-3)", color: tone ? "var(--ink)" : "var(--fg-3)", display: "grid", placeItems: "center", fontFamily: "var(--mono)", fontWeight: 700, fontSize: 11 }}>{n[0]}</div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 13, fontWeight: 600 }}>{n}</div>
                        <div className="mono" style={{ fontSize: 9, letterSpacing: "0.12em", color: "var(--fg-3)", marginTop: 2, textTransform: "uppercase" }}>{s}</div>
                      </div>
                      {tone === "good" && <div className="btn btn-text btn-sm" style={{ color: "var(--bad)" }}>REVOKE</div>}
                    </div>
                  ))}
                </div>
              </div>

              <div className="card" style={{ padding: 18 }}>
                <Eyebrow>Active plans · 2</Eyebrow>
                <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 8 }}>
                  {[["Berlin Marathon ’26", "v4 · Sep 27 · build"], ["Local 10K series", "v1 · Jul 12 · base"]].map(([n, s], i) => (
                    <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "6px 0" }}>
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 600 }}>{n}</div>
                        <div className="mono" style={{ fontSize: 9, letterSpacing: "0.12em", color: "var(--fg-3)", marginTop: 2, textTransform: "uppercase" }}>{s}</div>
                      </div>
                      <Ic d={I.chevR} size={14} />
                    </div>
                  ))}
                </div>
              </div>

              {/* Danger zone */}
              <div style={{ padding: 18, border: "1px solid color-mix(in oklab, var(--bad) 35%, transparent)", borderRadius: 6, background: "color-mix(in oklab, var(--bad) 6%, transparent)" }}>
                <Eyebrow>Danger zone</Eyebrow>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 12, gap: 14 }}>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 600 }}>Delete this user</div>
                    <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 3, lineHeight: 1.45 }}>
                      Removes the <code style={{ fontFamily: "var(--mono)", fontSize: 11 }}>users</code> row and all 46,540 scoped rows. Shared catalogs untouched. Cannot be undone.
                    </div>
                  </div>
                  <div className="btn btn-ghost btn-sm" style={{ color: "var(--bad)", borderColor: "color-mix(in oklab, var(--bad) 40%, transparent)", flexShrink: 0 }}>DELETE →</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// 19D. ADMIN · DELETE USER — destructive confirm (type-to-confirm)
// Shows the User detail behind a modal overlay.
// ═══════════════════════════════════════════════════════════════════
const ScreenAdminUserDelete = () => (
  <div className="screen" style={{ position: "relative" }}>
    {/* Backdrop page — hidden from assistive tech while the dialog is open */}
    <div aria-hidden="true" style={{ display: "flex", flex: 1, minHeight: 0, opacity: 0.32, pointerEvents: "none" }}>
      <Sidebar active="athlete" />
      <div className="page">
        <TopBar crumbs={["Admin", "Users", "sarah.k"]} />
        <div className="page-body">
          <div style={{ display: "flex", gap: 16, alignItems: "center", marginBottom: 20 }}>
            <div style={{ width: 56, height: 56, borderRadius: 8, background: "var(--bg-3)" }} />
            <div><h1 className="page-title" style={{ margin: 0 }}>Sarah Kowalski</h1></div>
          </div>
          <div className="row">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="stat-card col" style={{ padding: 14, height: 60 }} />
            ))}
          </div>
        </div>
      </div>
    </div>

    {/* Scrim */}
    <div style={{ position: "absolute", inset: 0, background: "color-mix(in oklab, var(--ink) 60%, transparent)", display: "grid", placeItems: "center", padding: 32 }}>
      {/* Modal */}
      <div role="dialog" aria-modal="true" aria-labelledby="del-dialog-title" aria-describedby="del-dialog-desc" className="card" style={{ width: 520, maxWidth: "100%", padding: 0, boxShadow: "0 24px 64px rgba(0,0,0,0.45)", border: "1px solid color-mix(in oklab, var(--bad) 40%, var(--hairline))" }}>
        <div style={{ padding: "18px 22px", borderBottom: "1px solid var(--hairline-2)", display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{ width: 40, height: 40, borderRadius: "50%", background: "color-mix(in oklab, var(--bad) 15%, transparent)", color: "var(--bad)", display: "grid", placeItems: "center", border: "1px solid color-mix(in oklab, var(--bad) 35%, transparent)", flexShrink: 0 }}>
            <Ic d={I.x} size={20} sw={2.2} />
          </div>
          <div style={{ flex: 1 }}>
            <Eyebrow style={{ color: "var(--bad)" }}>● IRREVERSIBLE</Eyebrow>
            <div id="del-dialog-title" style={{ fontSize: 18, fontWeight: 700, marginTop: 4 }}>Delete sarah.k?</div>
          </div>
        </div>

        <div style={{ padding: "18px 22px" }}>
          <div id="del-dialog-desc" style={{ fontSize: 13, color: "var(--fg-2)", lineHeight: 1.55 }}>
            This deletes Sarah Kowalski (<span className="mono" style={{ fontSize: 12 }}>user:2</span>) and every row tied to her across <b>25 scoped tables</b>. Shared catalogs (exercise inventory, equipment, modalities) are not touched.
          </div>

          <div style={{ display: "flex", gap: 0, marginTop: 16, marginBottom: 16, border: "1px solid var(--hairline-2)", borderRadius: 5, overflow: "hidden" }}>
            {[["Scoped rows", "46,540"], ["FIT files", "312"], ["Storage freed", "84 MB"]].map(([k, v], i) => (
              <div key={i} style={{ flex: 1, padding: "10px 12px", borderRight: i < 2 ? "1px solid var(--hairline-2)" : "none", textAlign: "center" }}>
                <div className="mono" style={{ fontSize: 8, letterSpacing: "0.16em", color: "var(--fg-3)", textTransform: "uppercase" }}>{k}</div>
                <div className="num" style={{ fontSize: 17, fontWeight: 700, marginTop: 3, color: "var(--bad)" }}>{v}</div>
              </div>
            ))}
          </div>

          <div className="mono" style={{ fontSize: 9, letterSpacing: "0.16em", color: "var(--fg-3)", textTransform: "uppercase", marginBottom: 8 }}>
            Type the username to confirm
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "11px 14px", border: "1px solid var(--hairline)", borderRadius: 5, background: "var(--bg-2)" }}>
            <span className="mono" style={{ fontSize: 14, color: "var(--fg)" }}>sarah.k</span>
            <span style={{ width: 1, height: 16, background: "var(--accent)", animation: "none" }} />
            <span style={{ flex: 1 }} />
            <Pill tone="good">✓ MATCH</Pill>
          </div>
        </div>

        <div style={{ padding: "14px 22px", borderTop: "1px solid var(--hairline-2)", display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <div className="btn btn-ghost">Cancel</div>
          <div className="btn" style={{ background: "var(--bad)", color: "white", padding: "10px 18px" }}>
            <Ic d={I.x} size={12} sw={2.2} /> Delete user &amp; all data
          </div>
        </div>
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// 19E. ADMIN · SYSTEM / TELEMETRY  (grounds the "Telemetry" CTA)
// ═══════════════════════════════════════════════════════════════════
const ScreenAdminSystem = () => {
  const Bars = ({ data, color = "var(--accent)" }) => {
    const max = Math.max(...data);
    return (
      <div style={{ display: "flex", alignItems: "flex-end", gap: 3, height: 48, marginTop: 10 }}>
        {data.map((v, i) => (
          <div key={i} style={{ flex: 1, height: `${(v / max) * 100}%`, background: color, opacity: 0.35 + (i / data.length) * 0.65, borderRadius: 1 }} />
        ))}
      </div>
    );
  };
  return (
    <div className="screen">
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <Sidebar active="athlete" />
        <div className="page">
          <TopBar crumbs={["Admin", "System"]} actions={
            <>
              <div className="btn btn-ghost btn-sm"><Ic d={I.clock} size={11} /> Live · 30s</div>
              <div className="btn btn-ghost btn-sm"><Ic d={I.download} size={11} /> Status page</div>
            </>
          } />
          <div className="page-body">
            <div style={{ marginBottom: 18 }}>
              <Eyebrow>Admin · service health + telemetry</Eyebrow>
              <h1 className="page-title" style={{ marginTop: 8 }}>System</h1>
              <div className="page-sub">Engine, queues, provider webhooks, and storage at a glance. All green right now.</div>
            </div>

            <AdminTabs active="health" />

            {/* Service status strip */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, marginBottom: 18 }}>
              {[
                ["Web / API", "operational", "99.98% · 30d"],
                ["Plan cascade", "operational", "p50 3m 41s"],
                ["Provider sync", "degraded", "Garmin API closed"],
                ["Database", "operational", "Neon · 2.4 GB"],
              ].map(([name, status, sub], i) => {
                const ok = status === "operational";
                return (
                  <div key={i} className="card" style={{ padding: 14 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <div style={{ width: 8, height: 8, borderRadius: "50%", background: ok ? "var(--good)" : "var(--warn)", boxShadow: `0 0 0 3px color-mix(in oklab, ${ok ? "var(--good)" : "var(--warn)"} 28%, transparent)` }} />
                      <span style={{ fontSize: 13, fontWeight: 600 }}>{name}</span>
                    </div>
                    <div className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: ok ? "var(--good)" : "var(--warn)", marginTop: 8, textTransform: "uppercase" }}>{status}</div>
                    <div className="mono" style={{ fontSize: 9, letterSpacing: "0.12em", color: "var(--fg-3)", marginTop: 3, textTransform: "uppercase" }}>{sub}</div>
                  </div>
                );
              })}
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}>
              {/* Charts */}
              <div className="card" style={{ padding: 18 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                  <Eyebrow>Plan generations · last 24h</Eyebrow>
                  <span className="num" style={{ fontSize: 18, fontWeight: 700 }}>312</span>
                </div>
                <Bars data={[4, 6, 3, 8, 12, 18, 22, 19, 14, 9, 7, 11, 16, 21, 24, 20, 15, 12, 10, 8, 6, 5, 7, 9]} />
                <div className="mono" style={{ fontSize: 9, letterSpacing: "0.12em", color: "var(--fg-3)", marginTop: 8, textTransform: "uppercase" }}>2 FAILED · INFEASIBLE SCHEDULE · 99.4% SUCCESS</div>
              </div>
              <div className="card" style={{ padding: 18 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                  <Eyebrow>Webhook events · last 24h</Eyebrow>
                  <span className="num" style={{ fontSize: 18, fontWeight: 700 }}>1,140</span>
                </div>
                <Bars data={[28, 34, 22, 41, 52, 38, 61, 48, 55, 44, 39, 47, 58, 62, 51, 43, 36, 40, 33, 29, 31, 27, 35, 42]} color="var(--good)" />
                <div className="mono" style={{ fontSize: 9, letterSpacing: "0.12em", color: "var(--fg-3)", marginTop: 8, textTransform: "uppercase" }}>STRAVA 812 · WAHOO 328 · 0 DROPPED</div>
              </div>
            </div>

            {/* Queues + deploys */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18, marginTop: 18 }}>
              <div className="card" style={{ padding: 0 }}>
                <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--hairline-2)" }}><Eyebrow>Queues</Eyebrow></div>
                {[
                  ["plan_cascade", "0 pending · 1 running", "ok"],
                  ["fit_ingest", "3 pending · 2 running", "ok"],
                  ["webhook_fanout", "0 pending", "ok"],
                  ["provider_pull", "1 pending · Garmin paused", "warn"],
                ].map(([q, s, tone], i, a) => (
                  <div key={i} style={{ padding: "11px 16px", borderBottom: i < a.length - 1 ? "1px solid var(--hairline-2)" : "none", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span className="mono" style={{ fontSize: 12, fontWeight: 600 }}>{q}</span>
                    <span className="mono" style={{ fontSize: 10, letterSpacing: "0.12em", color: tone === "warn" ? "var(--warn)" : "var(--fg-3)", textTransform: "uppercase" }}>{s}</span>
                  </div>
                ))}
              </div>
              <div className="card" style={{ padding: 0 }}>
                <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--hairline-2)" }}><Eyebrow>Recent deploys</Eyebrow></div>
                {[
                  ["engine v3.2", "May 24 · 09:12", "current"],
                  ["web v8.3.1", "May 27 · 14:40", "current"],
                  ["engine v3.1", "May 10 · 11:03", null],
                ].map(([n, when, tag], i, a) => (
                  <div key={i} style={{ padding: "11px 16px", borderBottom: i < a.length - 1 ? "1px solid var(--hairline-2)" : "none", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <div className="mono" style={{ fontSize: 12, fontWeight: 600 }}>{n}</div>
                      <div className="mono" style={{ fontSize: 9, letterSpacing: "0.12em", color: "var(--fg-3)", marginTop: 2, textTransform: "uppercase" }}>{when}</div>
                    </div>
                    {tag && <Pill tone="good">CURRENT</Pill>}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════
// 19. ADMIN · USERS  (override of the original — adds tab bar + drill-in)
// ═══════════════════════════════════════════════════════════════════
const ScreenAdmin = () => {
  const users = [
    { id: 1,  user: "ahorn",   display: "Andrew Horn",      email: "andrew@aidstation.run", strength: 412, cardio: 318, plans: 3, last: "today",   admin: true },
    { id: 2,  user: "sarah.k", display: "Sarah Kowalski",   email: "sarah@example.com",     strength: 218, cardio: 482, plans: 2, last: "today"   },
    { id: 3,  user: "marc.w",  display: "Marc Weber",       email: "marc@example.com",      strength:  88, cardio: 612, plans: 1, last: "2d ago"  },
    { id: 4,  user: "jenny.t", display: "Jenny Tran",       email: "jenny@example.com",     strength: 154, cardio: 240, plans: 4, last: "today"   },
    { id: 5,  user: "ramon.p", display: "Ramón Paredes",    email: "rp@example.com",        strength:  42, cardio: 188, plans: 1, last: "1w ago"  },
    { id: 6,  user: "lin.h",   display: "Lin Huang",        email: "lin@example.com",       strength: 312, cardio:  64, plans: 2, last: "today"   },
    { id: 7,  user: "darius.j", display: "Darius Jefferson", email: "djeff@example.com",    strength: 184, cardio: 396, plans: 1, last: "3d ago"  },
    { id: 8,  user: "anna.b",  display: "Anna Bergström",   email: "anna@example.com",      strength: 268, cardio: 412, plans: 3, last: "today"   },
    { id: 9,  user: "test.user", display: "(test)",         email: null,                    strength:   0, cardio:   0, plans: 0, last: "—"       },
  ];
  return (
    <div className="screen">
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <Sidebar active="athlete" />
        <div className="page">
          <TopBar crumbs={["Admin", "Users"]} actions={
            <>
              <div className="btn btn-ghost btn-sm"><Ic d={I.download} size={11} /> Audit log</div>
              <div className="btn btn-ghost btn-sm"><Ic d={I.bolt} size={11} /> System</div>
            </>
          } />
          <div className="page-body">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 18 }}>
              <div>
                <Eyebrow>Admin · user management</Eyebrow>
                <h1 className="page-title" style={{ marginTop: 8 }}>Users</h1>
                <div className="page-sub">Click a row to drill into a user. Deleting one removes their <code style={{ fontFamily: "var(--mono)", fontSize: 12 }}>users</code> row and every per-user row across the 25 scoped tables. Shared catalogs are untouched.</div>
              </div>
              <div style={{ display: "flex", gap: 14 }}>
                {[["Users", "9"], ["Pro", "6"], ["Active 7d", "5"], ["Plans active", "17"]].map(([k, v], i) => (
                  <div key={i} className="stat-card" style={{ minWidth: 96, padding: 14 }}>
                    <div className="k">{k}</div>
                    <div className="v num" style={{ fontSize: 22 }}>{v}</div>
                  </div>
                ))}
              </div>
            </div>

            <AdminTabs active="users" />

            <div className="card" style={{ padding: "10px 16px", marginBottom: 12, display: "flex", gap: 12, alignItems: "center" }}>
              <Ic d={I.search} size={14} />
              <span style={{ flex: 1, color: "var(--fg-3)", fontSize: 13 }}>Search by username, display name, or email…</span>
              {["All", "Pro", "Active", "Inactive"].map((f, i) => (
                <Pill key={i} tone={i === 0 ? "accent" : null}>{f.toUpperCase()}</Pill>
              ))}
            </div>

            <div className="card" style={{ padding: 0 }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr>
                    {["ID","Username","Display","Email","Strength","Cardio","Plans","Last login",""].map((h,i)=>(
                      <th key={i} className="mono" style={{ padding: "12px 16px", textAlign: i > 3 && i < 7 ? "right" : "left", fontSize: 9, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--fg-3)", fontWeight: 500, borderBottom: "1px solid var(--hairline-2)" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {users.map((u, i) => (
                    <tr key={u.id} style={{ borderBottom: i < users.length - 1 ? "1px solid var(--hairline-2)" : "none", background: u.user === "sarah.k" ? "color-mix(in oklab, var(--accent) 7%, transparent)" : "transparent", cursor: "pointer" }}>
                      <td className="mono num" style={{ padding: "12px 16px", color: "var(--fg-3)", width: 50 }}>{u.id}</td>
                      <td style={{ padding: "12px 16px", fontWeight: 600 }}>
                        {u.user}
                        {u.admin && <Pill tone="accent" style={{ marginLeft: 6 }}>ADMIN</Pill>}
                      </td>
                      <td style={{ padding: "12px 16px", color: u.display.startsWith("(") ? "var(--fg-4)" : "var(--fg-2)" }}>{u.display}</td>
                      <td style={{ padding: "12px 16px", color: "var(--fg-3)", fontSize: 12, fontFamily: "var(--mono)" }}>{u.email || "—"}</td>
                      <td className="num" style={{ padding: "12px 16px", textAlign: "right", fontFamily: "var(--mono)" }}>{u.strength}</td>
                      <td className="num" style={{ padding: "12px 16px", textAlign: "right", fontFamily: "var(--mono)" }}>{u.cardio}</td>
                      <td className="num" style={{ padding: "12px 16px", textAlign: "right", fontFamily: "var(--mono)" }}>{u.plans}</td>
                      <td className="mono" style={{ padding: "12px 16px", color: "var(--fg-3)", fontSize: 11 }}>{u.last}</td>
                      <td style={{ padding: "12px 16px", textAlign: "right" }}>
                        {u.admin
                          ? <span className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--fg-4)" }}>LOCKED</span>
                          : <Ic d={I.chevR} size={14} />}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

Object.assign(window, {
  ScreenAdmin,
  ScreenAdminAudit, ScreenAdminUser, ScreenAdminUserDelete, ScreenAdminSystem,
});
