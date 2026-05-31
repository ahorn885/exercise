/* AIDSTATION redesign — Desktop screens (part 5)
   Plan list / history · Plan view empty · Exercises empty */

// ═══════════════════════════════════════════════════════════════════
// 23. PLAN LIST — versions + history
// ═══════════════════════════════════════════════════════════════════
const ScreenPlanList = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="plan" />
      <div className="page">
        <TopBar crumbs={["Plan", "All plans"]} actions={
          <>
            <div className="btn btn-ghost"><Ic d={I.upload} size={12} /> Import</div>
            <div className="btn btn-primary"><Ic d={I.plus} size={12} sw={2.2} /> New plan</div>
          </>
        } />
        <div className="page-body">
          <div style={{ marginBottom: 22 }}>
            <Eyebrow>Plan history · 2 plans · 14 versions</Eyebrow>
            <h1 className="page-title" style={{ marginTop: 8 }}>Your plans.</h1>
            <div className="page-sub">Every refresh writes a new version. Past plans stay viewable — revert any version, fork into a new plan, or archive.</div>
          </div>

          {/* Active plan hero */}
          <div className="card" style={{ padding: 22, marginBottom: 22, position: "relative", overflow: "hidden", border: "1px solid color-mix(in oklab, var(--accent) 35%, var(--hairline-2))" }}>
            <div style={{ position: "absolute", top: 0, left: 0, bottom: 0, width: 3, background: "var(--accent)" }} />
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 18 }}>
              <div>
                <Eyebrow accent>● ACTIVE PLAN · BUILD WK 8 OF 22</Eyebrow>
                <div style={{ fontSize: 26, fontWeight: 800, letterSpacing: "-0.02em", lineHeight: 1.1, marginTop: 8 }}>Boston Marathon 2026</div>
                <div className="mono" style={{ fontSize: 11, letterSpacing: "0.16em", color: "var(--fg-3)", marginTop: 4, textTransform: "uppercase" }}>
                  APR 20, 2026 · 14W 6D OUT · GOAL SUB-3:00
                </div>
              </div>
              <div style={{ display: "flex", gap: 6 }}>
                <div className="btn btn-ghost btn-sm"><Ic d={I.bolt} size={11} /> REFRESH</div>
                <div className="btn btn-primary btn-sm"><Ic d={I.arrow} size={11} sw={2} /> OPEN</div>
              </div>
            </div>

            {/* Phase strip */}
            <div style={{ display: "flex", height: 28, borderRadius: 4, overflow: "hidden", marginBottom: 14 }}>
              <div style={{ flex: 4, background: "var(--ink-3)", display: "grid", placeItems: "center", fontFamily: "var(--mono)", fontSize: 9, letterSpacing: "0.16em", color: "var(--fg-2)" }}>BASE · 4W</div>
              <div style={{ flex: 8, background: "var(--accent)", display: "grid", placeItems: "center", fontFamily: "var(--mono)", fontSize: 9, letterSpacing: "0.16em", color: "var(--ink)", fontWeight: 600 }}>BUILD · WK 8 ●</div>
              <div style={{ flex: 6, background: "var(--bg-3)", display: "grid", placeItems: "center", fontFamily: "var(--mono)", fontSize: 9, letterSpacing: "0.16em", color: "var(--fg-4)" }}>PEAK · 6W</div>
              <div style={{ flex: 4, background: "var(--bg-3)", display: "grid", placeItems: "center", fontFamily: "var(--mono)", fontSize: 9, letterSpacing: "0.16em", color: "var(--fg-4)" }}>TAPER · 4W</div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", borderTop: "1px solid var(--hairline-2)", paddingTop: 14 }}>
              {[
                ["Pattern",      "B · v13"],
                ["Sessions",     "132"],
                ["Versions",     "13"],
                ["Built",        "May 21, 2026"],
                ["Last refresh", "11 hr ago"],
              ].map(([k, v], i) => (
                <div key={i} style={{ borderRight: i < 4 ? "1px solid var(--hairline-2)" : "none", padding: "0 16px" }}>
                  <div className="eyebrow" style={{ fontSize: 9 }}>{k}</div>
                  <div className="num" style={{ fontSize: 15, fontWeight: 700, marginTop: 4 }}>{v}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Version history */}
          <div style={{ marginBottom: 22 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 12 }}>
              <Eyebrow>Version history · Boston Marathon 2026</Eyebrow>
              <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.16em" }}>13 VERSIONS</span>
            </div>
            <div className="card" style={{ padding: 0 }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr>
                    {["v", "Built", "Via", "Scope", "Changes", "Pattern", ""].map((h, i) => (
                      <th key={i} className="mono" style={{ padding: "12px 16px", textAlign: "left", fontSize: 9, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--fg-3)", fontWeight: 500, borderBottom: "1px solid var(--hairline-2)" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[
                    { v: "13", date: "May 27, 2026 · 09:14", via: "Refresh · T2",  scope: "7 days",   changes: "4 sessions · −18m vol",  pattern: "B", active: true },
                    { v: "12", date: "May 21, 2026 · 14:42", via: "Manual generate", scope: "Full plan", changes: "—",                         pattern: "B" },
                    { v: "11", date: "May 18, 2026 · 21:30", via: "Refresh · T1",  scope: "2 days",   changes: "2 sessions",                pattern: "A" },
                    { v: "10", date: "May 13, 2026 · 10:08", via: "Refresh · T3",  scope: "28 days",  changes: "23 sessions · +8% vol",     pattern: "A" },
                    { v: "9",  date: "May 06, 2026 · 18:22", via: "Refresh · T2",  scope: "7 days",   changes: "3 sessions",                pattern: "A" },
                    { v: "8",  date: "Apr 29, 2026 · 07:55", via: "Refresh · T2",  scope: "7 days",   changes: "5 sessions",                pattern: "A" },
                    { v: "7",  date: "Apr 22, 2026 · 17:14", via: "Refresh · T2",  scope: "7 days",   changes: "2 sessions",                pattern: "A" },
                    { v: "6",  date: "Apr 15, 2026 · 09:01", via: "Manual generate", scope: "Full plan", changes: "—",                         pattern: "A" },
                  ].map((r, i, a) => (
                    <tr key={i} style={{
                      borderBottom: i < a.length - 1 ? "1px solid var(--hairline-2)" : "none",
                      background: r.active ? "color-mix(in oklab, var(--accent) 5%, transparent)" : "transparent",
                    }}>
                      <td style={{ padding: "14px 16px", width: 60 }}>
                        <span className="num mono" style={{ fontWeight: 700, fontSize: 14 }}>v{r.v}</span>
                        {r.active && <Pill tone="accent" style={{ marginLeft: 6 }}>● ACTIVE</Pill>}
                      </td>
                      <td className="mono num" style={{ padding: "14px 16px", fontSize: 11, color: "var(--fg-3)" }}>{r.date}</td>
                      <td style={{ padding: "14px 16px", fontWeight: 500 }}>{r.via}</td>
                      <td style={{ padding: "14px 16px", color: "var(--fg-2)" }}>{r.scope}</td>
                      <td style={{ padding: "14px 16px", color: "var(--fg-2)", fontSize: 12 }}>{r.changes}</td>
                      <td style={{ padding: "14px 16px" }}><Pill tone="solid">Pattern {r.pattern}</Pill></td>
                      <td style={{ padding: "14px 16px", textAlign: "right" }}>
                        <div style={{ display: "flex", gap: 4, justifyContent: "flex-end" }}>
                          {!r.active && <div className="btn btn-ghost btn-sm">VIEW</div>}
                          <div className="btn btn-text btn-sm" style={{ color: "var(--fg-3)" }}>···</div>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div style={{ padding: "10px 16px", borderTop: "1px solid var(--hairline-2)", display: "flex", justifyContent: "space-between", background: "var(--bg)" }}>
                <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.16em" }}>SHOWING 8 OF 13 · v5 \u2192 v13</span>
                <span className="mono" style={{ fontSize: 10, color: "var(--accent)", letterSpacing: "0.16em" }}>SHOW EARLIER VERSIONS →</span>
              </div>
            </div>
          </div>

          {/* Archived plans */}
          <div>
            <Eyebrow>Archived plans · past races</Eyebrow>
            <div className="card" style={{ marginTop: 12, padding: 0 }}>
              {[
                { name: "NYC Marathon 2025", date: "Nov 02, 2025", goal: "Sub-3:10 · finished 3:08:42", versions: 12, sessions: 124, status: "completed" },
                { name: "Bay to Breakers 12K · 2025", date: "May 18, 2025", goal: "PR · finished 42:18", versions: 6, sessions: 32, status: "completed" },
                { name: "Boston Marathon 2025", date: "Apr 21, 2025", goal: "Sub-3:00 · finished 3:04:15", versions: 18, sessions: 132, status: "completed" },
              ].map((p, i, a) => (
                <div key={i} style={{ display: "grid", gridTemplateColumns: "1fr 180px 100px auto", gap: 18, padding: "16px 18px", borderBottom: i < a.length - 1 ? "1px solid var(--hairline-2)" : "none", alignItems: "center" }}>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 14 }}>{p.name}</div>
                    <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em", marginTop: 4, textTransform: "uppercase" }}>{p.date} · {p.goal}</div>
                  </div>
                  <div className="mono" style={{ fontSize: 11, color: "var(--fg-3)" }}>{p.versions} VERSIONS</div>
                  <div className="mono" style={{ fontSize: 11, color: "var(--fg-3)" }}>{p.sessions} SESSIONS</div>
                  <div style={{ display: "flex", gap: 6 }}>
                    <Pill tone="good">✓ {p.status.toUpperCase()}</Pill>
                    <div className="btn btn-ghost btn-sm">VIEW</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// E8. PLAN VIEW — empty (no active plan)
// ═══════════════════════════════════════════════════════════════════
const ScreenPlanEmpty = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="plan" />
      <div className="page">
        <TopBar crumbs={["Plan"]} actions={null} />
        <div className="page-body" style={{ display: "grid", placeItems: "center", padding: "32px 28px" }}>
          <div style={{ maxWidth: 620, width: "100%", textAlign: "center" }}>
            <Eyebrow>● NO ACTIVE PLAN</Eyebrow>
            <h1 style={{ fontSize: 42, fontWeight: 800, letterSpacing: "-0.025em", lineHeight: 1.05, margin: "12px 0 12px" }}>
              You don't have a plan yet.
            </h1>
            <div style={{ color: "var(--fg-3)", fontSize: 15, lineHeight: 1.55, maxWidth: 480, margin: "0 auto 28px" }}>
              Plans anchor every session of your training to a race. Generate one in 3–5 minutes from your profile, or import an existing plan as JSON.
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 18 }}>
              <div className="card" style={{ padding: 22, textAlign: "left" }}>
                <Eyebrow accent>● RECOMMENDED</Eyebrow>
                <div style={{ fontSize: 18, fontWeight: 700, marginTop: 8 }}>Generate from your profile</div>
                <div style={{ fontSize: 13, color: "var(--fg-3)", marginTop: 6, lineHeight: 1.5 }}>
                  We run your profile + race target through the full cascade. Base → Build → Peak → Taper, periodized.
                </div>
                <div className="btn btn-primary" style={{ marginTop: 14, width: "100%", justifyContent: "center", padding: "12px 14px" }}>
                  <Ic d={I.bolt} size={12} /> GENERATE
                </div>
              </div>
              <div className="card" style={{ padding: 22, textAlign: "left" }}>
                <Eyebrow>● POWER USER</Eyebrow>
                <div style={{ fontSize: 18, fontWeight: 700, marginTop: 8 }}>Import existing plan</div>
                <div style={{ fontSize: 13, color: "var(--fg-3)", marginTop: 6, lineHeight: 1.5 }}>
                  Paste a JSON plan from anywhere — your old coach, another tool, or a hand-built one.
                </div>
                <div className="btn btn-ghost" style={{ marginTop: 14, width: "100%", justifyContent: "center", padding: "12px 14px" }}>
                  <Ic d={I.upload} size={12} /> IMPORT
                </div>
              </div>
            </div>

            <div className="card-flush" style={{ padding: 16, textAlign: "left" }}>
              <Eyebrow>Or browse past plans</Eyebrow>
              <div style={{ display: "flex", gap: 12, marginTop: 10 }}>
                {[
                  ["NYC Marathon 2025",     "completed"],
                  ["Boston Marathon 2025",  "completed"],
                  ["Bay to Breakers · 2025","completed"],
                ].map(([name, status], i) => (
                  <div key={i} style={{ padding: "8px 12px", border: "1px solid var(--hairline-2)", borderRadius: 4, flex: 1, fontSize: 12 }}>
                    <div style={{ fontWeight: 600 }}>{name}</div>
                    <Pill tone="good" style={{ marginTop: 6 }}>✓ ARCHIVED</Pill>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// E9. EXERCISES — empty (no Rx yet)
// ═══════════════════════════════════════════════════════════════════
const ScreenExercisesEmpty = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="library" />
      <div className="page">
        <TopBar crumbs={["Exercises"]} actions={
          <div className="btn btn-primary"><Ic d={I.plus} size={12} sw={2.2} /> Add exercise</div>
        } />
        <div className="page-body" style={{ display: "grid", placeItems: "center", padding: "32px 28px" }}>
          <div style={{ maxWidth: 580, textAlign: "center" }}>
            <Eyebrow>● NO PRESCRIBED EXERCISES YET</Eyebrow>
            <h1 style={{ fontSize: 36, fontWeight: 700, letterSpacing: "-0.02em", margin: "12px 0 10px" }}>
              No Rx yet.
            </h1>
            <div style={{ color: "var(--fg-3)", fontSize: 14, lineHeight: 1.55, maxWidth: 460, margin: "0 auto 24px" }}>
              The exercise library tracks what you're currently prescribed — sets, reps, weights, plateau watch. Generate a plan to populate it, or add exercises manually.
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 18 }}>
              <div className="card" style={{ padding: 18, textAlign: "left" }}>
                <Eyebrow accent>● RECOMMENDED</Eyebrow>
                <div style={{ fontSize: 16, fontWeight: 700, marginTop: 6 }}>Generate from a plan</div>
                <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 4, lineHeight: 1.45 }}>
                  Plan synthesis populates strength + interval Rx from your skills, locations, and goals.
                </div>
                <div className="btn btn-primary btn-sm" style={{ marginTop: 12, width: "100%", justifyContent: "center" }}>GENERATE PLAN</div>
              </div>
              <div className="card" style={{ padding: 18, textAlign: "left" }}>
                <Eyebrow>● MANUAL</Eyebrow>
                <div style={{ fontSize: 16, fontWeight: 700, marginTop: 6 }}>Add exercises</div>
                <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 4, lineHeight: 1.45 }}>
                  Pick from the catalog of 312 exercises. Set your starting weights, we track from there.
                </div>
                <div className="btn btn-ghost btn-sm" style={{ marginTop: 12, width: "100%", justifyContent: "center" }}>BROWSE CATALOG</div>
              </div>
            </div>

            <div className="mono" style={{ fontSize: 10, letterSpacing: "0.16em", color: "var(--fg-4)", textTransform: "uppercase" }}>
              ⓘ 312 EXERCISES IN THE CATALOG · 0 IN YOUR ACTIVE RX
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

Object.assign(window, { ScreenPlanList, ScreenPlanEmpty, ScreenExercisesEmpty });
