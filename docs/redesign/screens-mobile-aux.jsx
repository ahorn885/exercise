/* AIDSTATION redesign — Mobile parity for misc desktop-only screens
   Mobile sign-in · Mobile plan generate (preflight) · Mobile plan import
   Mobile command palette (fullscreen search sheet) */

// ═══════════════════════════════════════════════════════════════════
// MA1. MOBILE SIGN-IN
// ═══════════════════════════════════════════════════════════════════
const MobileLogin = () => (
  <div className="screen">
    <StatusBar />
    <div style={{ flex: 1, padding: "40px 24px 24px", display: "flex", flexDirection: "column" }}>
      {/* Brand */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 40 }}>
        <AsMark size={28} />
        <Wordmark />
      </div>

      <Eyebrow accent>● WELCOME BACK</Eyebrow>
      <div style={{ fontSize: 30, fontWeight: 800, letterSpacing: "-0.02em", marginTop: 8, lineHeight: 1.1 }}>
        Sign in.
      </div>
      <div style={{ fontSize: 14, color: "var(--fg-3)", marginTop: 10, lineHeight: 1.55, marginBottom: 28 }}>
        Race-day's not getting any further away.
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <div>
          <span className="mono" style={{ fontSize: 9, letterSpacing: "0.22em", textTransform: "uppercase", color: "var(--fg-3)" }}>● EMAIL</span>
          <div style={{ display: "flex", alignItems: "center", gap: 10, height: 46, padding: "0 14px", background: "var(--bg-2)", border: "1px solid var(--hairline-2)", borderRadius: 4, marginTop: 6 }}>
            <span style={{ flex: 1, fontSize: 15 }}>andrew@aidstation.run</span>
          </div>
        </div>
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
            <span className="mono" style={{ fontSize: 9, letterSpacing: "0.22em", textTransform: "uppercase", color: "var(--fg-3)" }}>● PASSWORD</span>
            <span className="mono" style={{ fontSize: 9, letterSpacing: "0.22em", textTransform: "uppercase", color: "var(--accent)" }}>FORGOT?</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, height: 46, padding: "0 14px", background: "var(--bg-2)", border: "1px solid var(--hairline-2)", borderRadius: 4 }}>
            <span style={{ flex: 1, fontSize: 16, fontFamily: "var(--mono)", letterSpacing: "0.2em" }}>•••••••••••</span>
            <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.18em" }}>SHOW</span>
          </div>
        </div>

        <label style={{ display: "flex", gap: 10, alignItems: "center", fontSize: 13, color: "var(--fg-2)", marginTop: 4 }}>
          <span style={{ width: 16, height: 16, borderRadius: 3, border: "1px solid var(--accent)", background: "var(--accent)", color: "var(--ink)", display: "grid", placeItems: "center" }}>
            <Ic d={I.check} size={10} sw={3} />
          </span>
          Keep me signed in on this device
        </label>
      </div>

      <div className="btn btn-primary" style={{ marginTop: 20, justifyContent: "center", padding: "14px 18px" }}>Sign in <Ic d={I.arrow} size={12} sw={2} /></div>

      <div style={{ marginTop: "auto", paddingTop: 28, textAlign: "center", fontSize: 13, color: "var(--fg-3)" }}>
        New here? <span style={{ color: "var(--fg)", fontWeight: 600 }}>Create an account →</span>
      </div>
      <div className="mono" style={{ fontSize: 9, letterSpacing: "0.22em", textTransform: "uppercase", color: "var(--fg-4)", textAlign: "center", marginTop: 16 }}>
        ● V8.3 · BUILD 2026.05.27 · ANDROID + iOS
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// MA2. MOBILE PLAN GENERATE · PRE-FLIGHT
// ═══════════════════════════════════════════════════════════════════
const MobilePlanGenerate = () => {
  const checks = [
    ["Race target",        true,  "Boston Marathon · Apr 20, 2026"],
    ["Performance baselines", true, "5 of 5 set · last refreshed today"],
    ["Schedule",           true,  "6 days · 8.5 h/wk"],
    ["Skills",             true,  "5 of 12 checked"],
    ["Locations",          true,  "Home garage + 2 more"],
    ["Provider sync",      false, "Strava 3 days stale — refresh recommended"],
  ];
  return (
    <div className="screen">
      <StatusBar />
      <AppBar title="Generate plan" left={<Ic d={I.chevL} size={22} />} />
      <div style={{ flex: 1, overflow: "auto", padding: "8px 16px 16px" }}>
        <Eyebrow accent>● PRE-FLIGHT</Eyebrow>
        <div style={{ fontSize: 26, fontWeight: 800, letterSpacing: "-0.02em", marginTop: 6, lineHeight: 1.1 }}>
          Ready to brew a plan.
        </div>
        <div style={{ fontSize: 13, color: "var(--fg-3)", marginTop: 8, lineHeight: 1.55 }}>
          Cascade runs in ~5 min on average. Inputs locked at start — refresh anytime after.
        </div>

        {/* meta cards */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginTop: 18 }}>
          <div className="card" style={{ padding: 12 }}>
            <div className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.18em" }}>● RACE</div>
            <div style={{ fontSize: 14, fontWeight: 700, marginTop: 4, lineHeight: 1.3 }}>Boston Marathon</div>
            <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em", marginTop: 4 }}>APR 20 · 47W AWAY</div>
          </div>
          <div className="card" style={{ padding: 12 }}>
            <div className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.18em" }}>● GOAL</div>
            <div className="num" style={{ fontFamily: "var(--mono)", fontSize: 18, fontWeight: 700, marginTop: 4 }}>02:48:00</div>
            <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em", marginTop: 4 }}>6:24/MI · BQ-QUALIFIER</div>
          </div>
        </div>

        <Eyebrow style={{ display: "block", marginTop: 18, marginBottom: 8 }}>● READINESS · {checks.filter(c => c[1]).length} / {checks.length}</Eyebrow>
        <div className="card" style={{ padding: 0 }}>
          {checks.map(([k, ok, v], i) => (
            <div key={k} style={{ padding: "12px 14px", borderBottom: i < checks.length - 1 ? "1px solid var(--hairline-2)" : "none", display: "grid", gridTemplateColumns: "20px 1fr auto", gap: 12, alignItems: "center" }}>
              {ok ? (
                <div style={{ width: 18, height: 18, borderRadius: "50%", background: "color-mix(in oklab, var(--good) 20%, transparent)", color: "var(--good)", display: "grid", placeItems: "center" }}>
                  <Ic d={I.check} size={11} sw={2.5} />
                </div>
              ) : (
                <div style={{ width: 10, height: 10, borderRadius: "50%", background: "var(--warn)", boxShadow: "0 0 0 4px color-mix(in oklab, var(--warn) 30%, transparent)", margin: "0 auto" }} />
              )}
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 600 }}>{k}</div>
                <div className="mono" style={{ fontSize: 10, color: ok ? "var(--fg-3)" : "var(--warn)", letterSpacing: "0.12em", marginTop: 3 }}>{v}</div>
              </div>
              {!ok && <Pill tone="warn">FIX</Pill>}
            </div>
          ))}
        </div>

        <div className="card-flush" style={{ marginTop: 14, padding: 12, fontSize: 12, color: "var(--fg-3)", lineHeight: 1.55 }}>
          Phases: <b>Base 12w · Build 16w · Peak 12w · Taper 3w</b>. Each phase emits a versioned plan you can compare or revert.
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 16 }}>
          <div className="btn btn-primary" style={{ justifyContent: "center", padding: "14px 18px" }}>
            <Ic d={I.bolt} size={13} /> Generate plan · ~5 min
          </div>
          <div className="btn btn-ghost" style={{ justifyContent: "center" }}>Edit inputs first</div>
        </div>
        <div className="mono" style={{ marginTop: 12, fontSize: 9, letterSpacing: "0.18em", color: "var(--fg-4)", textAlign: "center" }}>
          ⓘ FAILED RUNS COST NOTHING · CACHED PHASES REUSE ON RETRY
        </div>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════
// MA3. MOBILE PLAN IMPORT · JSON PASTE
// ═══════════════════════════════════════════════════════════════════
const MobilePlanImport = () => (
  <div className="screen">
    <StatusBar />
    <AppBar title="Import plan" left={<Ic d={I.chevL} size={22} />} right={<span className="mono" style={{ fontSize: 10, letterSpacing: "0.18em", color: "var(--fg-3)" }}>HELP</span>} />
    <div style={{ flex: 1, overflow: "auto", padding: "8px 16px 16px" }}>
      <Eyebrow>● IMPORT · JSON PASTE</Eyebrow>
      <div style={{ fontSize: 22, fontWeight: 700, letterSpacing: "-0.015em", marginTop: 6, lineHeight: 1.2 }}>
        Paste a plan as JSON.
      </div>
      <div style={{ fontSize: 13, color: "var(--fg-3)", marginTop: 8, lineHeight: 1.5 }}>
        Coach-exported or hand-authored. We validate before anything writes.
      </div>

      <div className="card-flush" style={{ marginTop: 14, padding: 12, fontSize: 12, lineHeight: 1.5, color: "var(--fg-2)" }}>
        ⓘ Importing on mobile is fine for short plans. For long plans (200+ sessions), use desktop — easier to scroll the validation results.
      </div>

      {/* paste area */}
      <Eyebrow style={{ display: "block", marginTop: 18 }}>● PASTE · 132 LINES</Eyebrow>
      <div className="card" style={{ marginTop: 8, padding: 0, fontFamily: "var(--mono)", fontSize: 11, lineHeight: 1.6, color: "var(--fg-2)", overflow: "hidden" }}>
        {[
          `{`,
          `  "schema": "v3",`,
          `  "race": {`,
          `    "name": "Boston 2026",`,
          `    "distance": "marathon",`,
          `    "date": "2026-04-20"`,
          `  },`,
          `  "phases": [`,
          `    {`,
          `      "name": "Base",`,
          `      "weeks": 12,`,
          `      "sessions": [...]`,
          `    },`,
          `    ...`,
        ].map((l, i) => (
          <div key={i} style={{ display: "grid", gridTemplateColumns: "32px 1fr", padding: "1px 0" }}>
            <div style={{ textAlign: "right", paddingRight: 8, color: "var(--fg-4)" }}>{i + 1}</div>
            <div style={{ paddingRight: 10, whiteSpace: "pre" }}>{l}</div>
          </div>
        ))}
        <div style={{ padding: "8px 10px 8px 40px", color: "var(--fg-4)", fontSize: 11 }}>… 118 more lines</div>
      </div>

      {/* validation */}
      <Eyebrow style={{ display: "block", marginTop: 18 }}>● VALIDATION</Eyebrow>
      <div className="card" style={{ marginTop: 8, padding: 0 }}>
        {[
          ["good", "Schema v3", "Recognized."],
          ["good", "Race target", "Marathon · Apr 20, 2026 (parsed OK)."],
          ["good", "4 phases · 158 sessions", "All required fields present."],
          ["warn", "L53 · 'discipline' shadowed", "v3 prefers 'type'. Will be coerced on import."],
        ].map(([t, k, v], i, a) => (
          <div key={i} style={{ padding: "12px 14px", borderBottom: i < a.length - 1 ? "1px solid var(--hairline-2)" : "none", display: "grid", gridTemplateColumns: "16px 1fr", gap: 10 }}>
            <div style={{ width: 8, height: 8, borderRadius: 999, background: t === "warn" ? "var(--warn)" : "var(--good)", marginTop: 6 }} />
            <div>
              <div style={{ fontSize: 13, fontWeight: 600 }}>{k}</div>
              <div style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 3, lineHeight: 1.5 }}>{v}</div>
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 16 }}>
        <div className="btn btn-primary" style={{ justifyContent: "center", padding: "13px 18px" }}>
          <Ic d={I.check} size={12} sw={2.4} /> Import as new plan
        </div>
        <div className="btn btn-ghost" style={{ justifyContent: "center" }}>Re-paste · clear</div>
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// MA4. MOBILE COMMAND PALETTE — fullscreen search sheet
// ═══════════════════════════════════════════════════════════════════
const MobileSearchOverlay = () => {
  const recent = [
    ["Tomorrow's session", "12 mi · MP-effort long run", I.workout],
    ["Wahoo connection",   "/connections/wahoo",          I.link],
    ["Plan compare v12→v13","Last opened 2h ago",         I.plan],
  ];
  const results = [
    { group: "Workouts (3)", rows: [
      ["Tue · 8 × 800 m @ 5K",  "Week 9 · interval", I.workout],
      ["Wed · 60 min Z2 ride",  "Week 9 · aerobic",  I.workout],
      ["Thu · Heavy lower",     "Week 9 · strength", I.weight],
    ]},
    { group: "Pages", rows: [
      ["Refresh plan", "/refresh",            I.bolt],
      ["Wellness",     "/wellness",           I.pulse],
      ["Connections",  "/connections",        I.link],
    ]},
  ];
  return (
    <div className="screen">
      <StatusBar />
      {/* search header */}
      <div style={{ padding: "10px 14px 12px", display: "flex", alignItems: "center", gap: 10, borderBottom: "1px solid var(--hairline-2)", flexShrink: 0 }}>
        <Ic d={I.search} size={18} />
        <div style={{ flex: 1, fontSize: 16, color: "var(--fg)" }}>refresh<span style={{ color: "var(--accent)" }}>│</span></div>
        <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.18em" }}>CANCEL</span>
      </div>

      <div style={{ flex: 1, overflow: "auto" }}>
        {/* Quick actions row */}
        <div style={{ padding: "12px 14px", display: "flex", gap: 8, overflow: "auto" }}>
          {[["Today", I.home], ["Plan", I.plan], ["Workouts", I.workout], ["Log", I.log], ["Athlete", I.athlete]].map(([l, ic]) => (
            <div key={l} style={{ flexShrink: 0, padding: "10px 14px", border: "1px solid var(--hairline-2)", borderRadius: 999, display: "flex", alignItems: "center", gap: 6 }}>
              <Ic d={ic} size={12} />
              <span className="mono" style={{ fontSize: 10, letterSpacing: "0.16em", textTransform: "uppercase" }}>{l}</span>
            </div>
          ))}
        </div>

        {/* Recent */}
        <Eyebrow style={{ display: "block", padding: "10px 14px 6px" }}>● RECENT</Eyebrow>
        {recent.map(([k, sub, ic], i) => (
          <div key={i} style={{ padding: "10px 14px", display: "grid", gridTemplateColumns: "32px 1fr auto", gap: 12, alignItems: "center", borderBottom: i === recent.length - 1 ? "8px solid transparent" : "1px solid var(--hairline-2)" }}>
            <div style={{ width: 32, height: 32, borderRadius: 4, background: "var(--bg-3)", display: "grid", placeItems: "center" }}>
              <Ic d={ic} size={14} />
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 14, fontWeight: 600 }}>{k}</div>
              <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em", marginTop: 2 }}>{sub}</div>
            </div>
            <Ic d={I.arrow} size={14} sw={2} />
          </div>
        ))}

        {/* Results */}
        {results.map((g, gi) => (
          <div key={gi}>
            <Eyebrow style={{ display: "block", padding: "16px 14px 6px" }}>● {g.group.toUpperCase()}</Eyebrow>
            {g.rows.map(([k, sub, ic], i) => (
              <div key={i} style={{
                padding: "12px 14px", display: "grid", gridTemplateColumns: "32px 1fr auto", gap: 12, alignItems: "center",
                background: gi === 0 && i === 0 ? "color-mix(in oklab, var(--accent) 12%, transparent)" : "transparent",
                borderBottom: i < g.rows.length - 1 ? "1px solid var(--hairline-2)" : "none",
              }}>
                <div style={{ width: 32, height: 32, borderRadius: 4, background: "var(--bg-3)", display: "grid", placeItems: "center" }}>
                  <Ic d={ic} size={14} />
                </div>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 14, fontWeight: 600 }}>{k}</div>
                  <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em", marginTop: 2 }}>{sub}</div>
                </div>
                <Ic d={I.arrow} size={14} sw={2} />
              </div>
            ))}
          </div>
        ))}

        <div className="mono" style={{ padding: "20px 14px 12px", fontSize: 9, color: "var(--fg-4)", letterSpacing: "0.22em", textAlign: "center" }}>● 2 GROUPS · 6 MATCHES</div>
      </div>
    </div>
  );
};

Object.assign(window, {
  MobileLogin,
  MobilePlanGenerate,
  MobilePlanImport,
  MobileSearchOverlay,
});
