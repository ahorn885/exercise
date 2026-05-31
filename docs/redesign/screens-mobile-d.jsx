/* AIDSTATION redesign — Mobile screens (part 4)
   Plan list · Plan empty · Exercises empty (mobile) */

// ═══════════════════════════════════════════════════════════════════
// M18. MOBILE PLAN LIST (history)
// ═══════════════════════════════════════════════════════════════════
const MobilePlanList = () => (
  <div className="screen">
    <StatusBar />
    <AppBar title="Plans" left={<Ic d={I.menu} size={22} />} right={<div className="mono" style={{ fontSize: 10, letterSpacing: "0.18em", color: "var(--accent)" }}>+ NEW</div>} />

    <div style={{ flex: 1, overflow: "auto", padding: "12px 16px" }}>
      {/* Active plan hero */}
      <div className="card" style={{ padding: 14, border: "1px solid color-mix(in oklab, var(--accent) 35%, var(--hairline-2))", position: "relative", overflow: "hidden", marginBottom: 18 }}>
        <div style={{ position: "absolute", top: 0, left: 0, bottom: 0, width: 3, background: "var(--accent)" }} />
        <Eyebrow accent>● ACTIVE · BUILD WK 8 / 22</Eyebrow>
        <div style={{ fontSize: 18, fontWeight: 800, letterSpacing: "-0.02em", marginTop: 6 }}>Boston Marathon 2026</div>
        <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em", marginTop: 4, textTransform: "uppercase" }}>
          APR 20 · 14W 6D OUT · SUB-3:00
        </div>

        {/* Phase strip */}
        <div style={{ display: "flex", height: 18, borderRadius: 3, overflow: "hidden", marginTop: 12 }}>
          <div style={{ flex: 4, background: "var(--ink-3)" }} />
          <div style={{ flex: 8, background: "var(--accent)" }} />
          <div style={{ flex: 6, background: "var(--bg-3)" }} />
          <div style={{ flex: 4, background: "var(--bg-3)" }} />
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4, fontFamily: "var(--mono)", fontSize: 8, color: "var(--fg-3)", letterSpacing: "0.12em" }}>
          <span>BASE</span><span style={{ color: "var(--accent)" }}>BUILD ●</span><span>PEAK</span><span>TAPER</span>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 0, marginTop: 14, paddingTop: 12, borderTop: "1px solid var(--hairline-2)" }}>
          {[["VERSIONS", "13"], ["PATTERN", "B"], ["BUILT", "MAY 21"]].map(([k, v], i) => (
            <div key={i} style={{ borderRight: i < 2 ? "1px solid var(--hairline-2)" : "none", padding: "0 6px", textAlign: "center" }}>
              <div className="eyebrow" style={{ fontSize: 8 }}>{k}</div>
              <div className="num" style={{ fontSize: 14, fontWeight: 700, marginTop: 3 }}>{v}</div>
            </div>
          ))}
        </div>
        <div className="btn btn-primary btn-sm" style={{ width: "100%", justifyContent: "center", marginTop: 12, padding: "10px 14px" }}>
          <Ic d={I.arrow} size={11} sw={2} /> OPEN PLAN
        </div>
      </div>

      {/* Version history */}
      <Eyebrow>Versions · 13</Eyebrow>
      <div className="card" style={{ marginTop: 8, padding: 0, marginBottom: 18 }}>
        {[
          { v: "13", date: "May 27 · 09:14", via: "Refresh T2", changes: "4 sessions · −18m", active: true },
          { v: "12", date: "May 21 · 14:42", via: "Generate",    changes: "—" },
          { v: "11", date: "May 18 · 21:30", via: "Refresh T1",  changes: "2 sessions" },
          { v: "10", date: "May 13 · 10:08", via: "Refresh T3",  changes: "23 sess · +8%" },
          { v: "9",  date: "May 06 · 18:22", via: "Refresh T2",  changes: "3 sessions" },
        ].map((r, i, a) => (
          <div key={i} style={{
            padding: "12px 14px",
            borderBottom: i < a.length - 1 ? "1px solid var(--hairline-2)" : "none",
            background: r.active ? "color-mix(in oklab, var(--accent) 5%, transparent)" : "transparent",
            display: "grid", gridTemplateColumns: "44px 1fr auto", gap: 10, alignItems: "center",
          }}>
            <div>
              <span className="num mono" style={{ fontWeight: 700, fontSize: 14 }}>v{r.v}</span>
              {r.active && <div className="mono" style={{ fontSize: 8, letterSpacing: "0.14em", color: "var(--accent)", marginTop: 2 }}>● ACTIVE</div>}
            </div>
            <div>
              <div style={{ fontSize: 13, fontWeight: 500 }}>{r.via}</div>
              <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.12em", marginTop: 2 }}>{r.date.toUpperCase()} · {r.changes}</div>
            </div>
            <Ic d={I.chevR} size={14} />
          </div>
        ))}
        <div style={{ padding: "10px 14px", borderTop: "1px solid var(--hairline-2)", textAlign: "center", background: "var(--bg)" }}>
          <span className="mono" style={{ fontSize: 10, color: "var(--accent)", letterSpacing: "0.16em" }}>SHOW 8 EARLIER VERSIONS →</span>
        </div>
      </div>

      {/* Archived */}
      <Eyebrow>Archived · past races</Eyebrow>
      <div className="card" style={{ marginTop: 8, padding: 0 }}>
        {[
          { name: "NYC Marathon 2025",      meta: "Nov 02 · 3:08:42" },
          { name: "Bay to Breakers · 2025", meta: "May 18 · 42:18" },
          { name: "Boston Marathon 2025",   meta: "Apr 21 · 3:04:15" },
        ].map((p, i, a) => (
          <div key={i} style={{ padding: "12px 14px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: i < a.length - 1 ? "1px solid var(--hairline-2)" : "none" }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600 }}>{p.name}</div>
              <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em", marginTop: 3, textTransform: "uppercase" }}>{p.meta}</div>
            </div>
            <Pill tone="good">✓ DONE</Pill>
          </div>
        ))}
      </div>
      <div style={{ height: 12 }} />
    </div>

    <TabBar active="plan" />
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// M19. MOBILE PLAN — empty
// ═══════════════════════════════════════════════════════════════════
const MobilePlanEmpty = () => (
  <div className="screen">
    <StatusBar />
    <AppBar title="Plan" left={<Ic d={I.menu} size={22} />} right={null} />

    <div style={{ flex: 1, overflow: "auto", padding: "20px 18px", display: "flex", flexDirection: "column", justifyContent: "center" }}>
      <div style={{ textAlign: "center" }}>
        <Eyebrow>● NO ACTIVE PLAN</Eyebrow>
        <h1 style={{ fontSize: 26, fontWeight: 800, letterSpacing: "-0.025em", lineHeight: 1.05, margin: "10px 0 10px" }}>
          You don't have a plan yet.
        </h1>
        <div style={{ color: "var(--fg-3)", fontSize: 13, lineHeight: 1.5, marginBottom: 22 }}>
          Plans anchor your training to a race. Generate one in 3–5 minutes, or import an existing JSON plan.
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <div className="card" style={{ padding: 14, border: "1px solid color-mix(in oklab, var(--accent) 40%, var(--hairline-2))" }}>
          <Eyebrow accent>● RECOMMENDED</Eyebrow>
          <div style={{ fontSize: 15, fontWeight: 700, marginTop: 6 }}>Generate from your profile</div>
          <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 4, lineHeight: 1.45 }}>
            We run your profile + race target through the full cascade.
          </div>
          <div className="btn btn-primary btn-sm" style={{ marginTop: 12, width: "100%", justifyContent: "center" }}>
            <Ic d={I.bolt} size={11} /> GENERATE PLAN
          </div>
        </div>
        <div className="card" style={{ padding: 14 }}>
          <Eyebrow>● POWER USER</Eyebrow>
          <div style={{ fontSize: 15, fontWeight: 700, marginTop: 6 }}>Import existing JSON</div>
          <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 4, lineHeight: 1.45 }}>
            Paste a JSON plan from anywhere.
          </div>
          <div className="btn btn-ghost btn-sm" style={{ marginTop: 12, width: "100%", justifyContent: "center" }}>
            <Ic d={I.upload} size={11} /> IMPORT
          </div>
        </div>
      </div>

      <div style={{ marginTop: 22, textAlign: "center" }}>
        <span className="mono" style={{ fontSize: 10, color: "var(--accent)", letterSpacing: "0.16em" }}>BROWSE PAST PLANS →</span>
      </div>
    </div>

    <TabBar active="plan" />
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// M20. MOBILE EXERCISES — empty
// ═══════════════════════════════════════════════════════════════════
const MobileExercisesEmpty = () => (
  <div className="screen">
    <StatusBar />
    <AppBar
      title="Exercises"
      left={<Ic d={I.menu} size={22} />}
      right={<div className="mono" style={{ fontSize: 10, letterSpacing: "0.18em", color: "var(--accent)" }}>+ ADD</div>}
    />

    <div style={{ flex: 1, overflow: "auto", padding: "20px 18px", display: "flex", flexDirection: "column", justifyContent: "center" }}>
      <div style={{ textAlign: "center" }}>
        <Eyebrow>● NO PRESCRIBED EXERCISES</Eyebrow>
        <h1 style={{ fontSize: 24, fontWeight: 700, letterSpacing: "-0.02em", margin: "10px 0 10px" }}>
          No Rx yet.
        </h1>
        <div style={{ color: "var(--fg-3)", fontSize: 13, lineHeight: 1.5, marginBottom: 22 }}>
          The exercise library tracks what you're prescribed — sets, reps, weights, plateau watch. Generate a plan or add manually.
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <div className="card" style={{ padding: 14, border: "1px solid color-mix(in oklab, var(--accent) 40%, var(--hairline-2))" }}>
          <Eyebrow accent>● RECOMMENDED</Eyebrow>
          <div style={{ fontSize: 15, fontWeight: 700, marginTop: 6 }}>Generate from a plan</div>
          <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 4, lineHeight: 1.45 }}>
            Plan synthesis populates strength + interval Rx from your skills, locations, and goals.
          </div>
          <div className="btn btn-primary btn-sm" style={{ marginTop: 12, width: "100%", justifyContent: "center" }}>GENERATE PLAN</div>
        </div>
        <div className="card" style={{ padding: 14 }}>
          <Eyebrow>● MANUAL</Eyebrow>
          <div style={{ fontSize: 15, fontWeight: 700, marginTop: 6 }}>Browse catalog</div>
          <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 4, lineHeight: 1.45 }}>
            Pick from 312 exercises. Set starting weights, we track from there.
          </div>
          <div className="btn btn-ghost btn-sm" style={{ marginTop: 12, width: "100%", justifyContent: "center" }}>BROWSE</div>
        </div>
      </div>

      <div style={{ marginTop: 22, textAlign: "center" }}>
        <span className="mono" style={{ fontSize: 10, color: "var(--fg-4)", letterSpacing: "0.14em", textTransform: "uppercase" }}>
          ⓘ 312 IN CATALOG · 0 IN YOUR ACTIVE RX
        </span>
      </div>
    </div>

    <TabBar active="me" />
  </div>
);

Object.assign(window, { MobilePlanList, MobilePlanEmpty, MobileExercisesEmpty });
