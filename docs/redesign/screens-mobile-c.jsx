/* AIDSTATION redesign — Mobile screens (part 3)
   Empty + error states + plan ops on mobile.
   Dashboard empty · Wellness empty · Connections empty
   · Auth failed · FIT parse error · Plan compare */

// ═══════════════════════════════════════════════════════════════════
// M11. MOBILE DASHBOARD — EMPTY (no plan yet)
// ═══════════════════════════════════════════════════════════════════
const MobileDashboardEmpty = () => (
  <div className="screen">
    <StatusBar />
    <div style={{ padding: "10px 18px 16px", display: "flex", justifyContent: "space-between", alignItems: "center", flexShrink: 0 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <AsMark size={22} />
        <Wordmark />
      </div>
      <div className="avatar" style={{ width: 32, height: 32, fontSize: 11 }}>AH</div>
    </div>

    <div style={{ flex: 1, overflow: "auto", padding: "0 18px 16px" }}>
      <Eyebrow accent>● WELCOME · NO PLAN YET</Eyebrow>
      <h1 style={{ fontSize: 28, fontWeight: 800, letterSpacing: "-0.025em", lineHeight: 1.05, margin: "8px 0 8px" }}>
        Build your first plan.
      </h1>
      <div style={{ color: "var(--fg-3)", fontSize: 14, lineHeight: 1.5 }}>
        Everything anchors to a race. Generate in 3–5 minutes — we pull from your providers + race target.
      </div>

      {/* Pre-flight readiness */}
      <Eyebrow style={{ marginTop: 22 }}>Pre-flight</Eyebrow>
      <div className="card" style={{ marginTop: 10, padding: 0 }}>
        {[
          ["Account",           true,  "Andrew Horn"],
          ["Provider",          true,  "Strava · 412 sessions"],
          ["Baselines",         false, "Set 4 of 6 — re-prefill"],
          ["Schedule",          true,  "6 days · 8.5 h/wk"],
          ["Skills",            true,  "5 of 12 checked"],
          ["Locations",         true,  "Home + 2 more"],
          ["Target race",       false, "Not set — required"],
        ].map(([k, done, v], i, a) => (
          <div key={i} style={{ display: "grid", gridTemplateColumns: "20px 1fr auto", gap: 10, alignItems: "center", padding: "12px 14px", borderBottom: i < a.length - 1 ? "1px solid var(--hairline-2)" : "none" }}>
            {done ? (
              <div style={{ width: 16, height: 16, borderRadius: "50%", background: "color-mix(in oklab, var(--good) 20%, transparent)", color: "var(--good)", display: "grid", placeItems: "center" }}>
                <Ic d={I.check} size={10} sw={2.5} />
              </div>
            ) : (
              <div style={{ width: 10, height: 10, borderRadius: "50%", background: "var(--warn)" }} />
            )}
            <div>
              <div style={{ fontWeight: 600, fontSize: 13 }}>{k}</div>
              <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.12em", marginTop: 2 }}>{v.toUpperCase()}</div>
            </div>
            {!done && <Pill tone="warn">FIX</Pill>}
          </div>
        ))}
      </div>

      <div style={{ marginTop: 22, display: "flex", flexDirection: "column", gap: 8 }}>
        <div className="btn btn-primary" style={{ width: "100%", justifyContent: "center", padding: "14px 16px" }}>
          <Ic d={I.bolt} size={13} /> SET RACE & GENERATE
        </div>
        <div className="btn btn-ghost" style={{ width: "100%", justifyContent: "center", padding: "12px 16px" }}>
          IMPORT EXISTING PLAN
        </div>
      </div>

      <div className="mono" style={{ marginTop: 18, fontSize: 10, letterSpacing: "0.18em", color: "var(--fg-4)", textAlign: "center", textTransform: "uppercase" }}>
        ⓘ NOTHING IS LOCKED IN · EDIT ANYTHING AFTER
      </div>
    </div>

    <TabBar active="home" />
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// M12. MOBILE WELLNESS — EMPTY
// ═══════════════════════════════════════════════════════════════════
const MobileWellnessEmpty = () => (
  <div className="screen">
    <StatusBar />
    <AppBar
      title="Wellness"
      left={<Ic d={I.menu} size={22} />}
      right={<div className="mono" style={{ fontSize: 10, letterSpacing: "0.18em", color: "var(--accent)" }}>30D ▾</div>}
    />

    <div style={{ flex: 1, overflow: "auto", padding: "20px 18px", display: "flex", flexDirection: "column", justifyContent: "center" }}>
      <div style={{ textAlign: "center" }}>
        <Eyebrow>● NO DATA YET</Eyebrow>
        <h2 style={{ fontSize: 24, fontWeight: 700, letterSpacing: "-0.02em", margin: "10px 0 8px" }}>
          Nothing to chart yet.
        </h2>
        <div style={{ color: "var(--fg-3)", fontSize: 13, lineHeight: 1.5, marginBottom: 22 }}>
          Log a self-report below, add body metrics, or connect a provider to pull sleep + HR automatically.
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {[
            ["Self-report", "Sleep · energy · mood", I.pulse, true],
            ["Body metrics", "Weight · BF · RHR", I.body],
            ["Connect provider", "Strava · Wahoo · …", I.link],
          ].map(([t, s, ic, primary], i) => (
            <div key={i} className="card" style={{ padding: 14, display: "flex", gap: 14, alignItems: "center", textAlign: "left", border: "1px solid " + (primary ? "var(--accent)" : "var(--hairline-2)") }}>
              <Ic d={ic} size={20} />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14, fontWeight: 600 }}>{t}</div>
                <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em", marginTop: 4, textTransform: "uppercase" }}>{s}</div>
              </div>
              <Ic d={I.chevR} size={16} />
            </div>
          ))}
        </div>
      </div>
    </div>

    <TabBar active="stats" />
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// M13. MOBILE CONNECTIONS — EMPTY
// ═══════════════════════════════════════════════════════════════════
const MobileConnectionsEmpty = () => (
  <div className="screen">
    <StatusBar />
    <AppBar title="Connections" left={<Ic d={I.menu} size={22} />} right={<Ic d={I.upload} size={20} />} />

    <div style={{ flex: 1, overflow: "auto", padding: "20px 18px" }}>
      <div style={{ textAlign: "center", paddingBottom: 12 }}>
        <Eyebrow>● ZERO CONNECTIONS</Eyebrow>
        <h2 style={{ fontSize: 22, fontWeight: 700, letterSpacing: "-0.02em", margin: "10px 0 8px" }}>
          No data flowing yet.
        </h2>
        <div style={{ color: "var(--fg-3)", fontSize: 13, lineHeight: 1.5 }}>
          Connect a provider to auto-sync, or upload .FIT files manually. Both feed the same engine.
        </div>
      </div>

      <Eyebrow accent style={{ marginTop: 14 }}>● RECOMMENDED · CONNECT A PROVIDER</Eyebrow>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 6, marginTop: 10, marginBottom: 18 }}>
        {[["Strava", "#FC4C02"], ["Wahoo", "#0093D0"], ["Whoop", "#000"]].map(([name, color], i) => (
          <div key={i} className="card" style={{ padding: 12, display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
            <div style={{ width: 32, height: 32, borderRadius: 4, background: color, display: "grid", placeItems: "center", color: "white", fontFamily: "var(--mono)", fontWeight: 700, fontSize: 14 }}>{name[0]}</div>
            <div style={{ fontSize: 12, fontWeight: 600 }}>{name}</div>
            <div className="btn btn-primary btn-sm" style={{ width: "100%", justifyContent: "center" }}>CONNECT</div>
          </div>
        ))}
      </div>
      <div className="btn btn-text" style={{ width: "100%", justifyContent: "center", color: "var(--fg-3)" }}>OR UPLOAD .FIT MANUALLY →</div>
    </div>

    <TabBar active="me" />
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// M14. MOBILE — PROVIDER AUTH FAILED
// ═══════════════════════════════════════════════════════════════════
const MobileAuthFailed = () => (
  <div className="screen">
    <StatusBar />
    <AppBar title="Connect Wahoo" left={<Ic d={I.chevL} size={22} />} right={null} />

    <div style={{ flex: 1, overflow: "auto", padding: "16px 18px" }}>
      <div style={{
        padding: 14,
        border: "1px solid color-mix(in oklab, var(--bad) 40%, transparent)",
        background: "color-mix(in oklab, var(--bad) 8%, transparent)",
        borderRadius: 6,
        display: "flex", gap: 12, alignItems: "flex-start",
        marginBottom: 18,
      }}>
        <div style={{ width: 28, height: 28, borderRadius: "50%", background: "color-mix(in oklab, var(--bad) 25%, transparent)", color: "var(--bad)", display: "grid", placeItems: "center", flexShrink: 0 }}>
          <Ic d={I.x} size={12} sw={2.5} />
        </div>
        <div>
          <Eyebrow style={{ color: "var(--bad)" }}>● AUTH FAILED</Eyebrow>
          <div style={{ fontSize: 16, fontWeight: 700, marginTop: 6 }}>Wahoo didn't connect.</div>
          <div style={{ fontSize: 12, color: "var(--fg-2)", marginTop: 4, lineHeight: 1.5 }}>
            OAuth handshake failed. Wahoo's auth surface may be down, or your account is missing scopes.
          </div>
        </div>
      </div>

      <Eyebrow>Diagnostic</Eyebrow>
      <div className="card-flush" style={{ marginTop: 8, padding: "12px 14px", fontFamily: "var(--mono)", fontSize: 11, color: "var(--fg-2)", lineHeight: 1.7, marginBottom: 18 }}>
        <div>request_id: <span style={{ color: "var(--accent)" }}>req_8x21abf9d</span></div>
        <div>provider: wahoo</div>
        <div>step: oauth_callback</div>
        <div>error: <span style={{ color: "var(--bad)" }}>invalid_grant</span></div>
      </div>

      <Eyebrow>Try this</Eyebrow>
      <div className="card" style={{ marginTop: 10, padding: 0, marginBottom: 18 }}>
        {[
          ["Try again",          "Auth codes expire after 60s."],
          ["Check Wahoo status", "status.wahoofitness.com"],
          ["Re-grant scopes",    "If you've revoked in Wahoo dashboard."],
          ["Contact support",    "Include the request_id above."],
        ].map(([k, v], i, a) => (
          <div key={i} style={{ padding: "12px 14px", borderBottom: i < a.length - 1 ? "1px solid var(--hairline-2)" : "none" }}>
            <div style={{ fontWeight: 600, fontSize: 13 }}>{k}</div>
            <div style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 3 }}>{v}</div>
          </div>
        ))}
      </div>

      <div className="btn btn-primary" style={{ width: "100%", justifyContent: "center", padding: "14px 16px" }}>
        <Ic d={I.link} size={13} /> TRY WAHOO AGAIN
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// M15. MOBILE — FIT PARSE ERROR
// ═══════════════════════════════════════════════════════════════════
const MobileFitError = () => (
  <div className="screen">
    <StatusBar />
    <AppBar title="Upload .FIT" left={<Ic d={I.chevL} size={22} />} right={null} />

    <div style={{ flex: 1, overflow: "auto", padding: "16px 18px" }}>
      <div style={{
        padding: 14,
        border: "1px solid color-mix(in oklab, var(--bad) 40%, transparent)",
        background: "color-mix(in oklab, var(--bad) 8%, transparent)",
        borderRadius: 6,
        marginBottom: 18,
      }}>
        <Eyebrow style={{ color: "var(--bad)" }}>● 2 OF 3 FAILED</Eyebrow>
        <div style={{ fontSize: 15, fontWeight: 700, marginTop: 6 }}>Couldn't read 2 files.</div>
        <div style={{ fontSize: 12, color: "var(--fg-2)", marginTop: 4, lineHeight: 1.5 }}>
          One imported cleanly. Re-export or upload different files for the others.
        </div>
      </div>

      <Eyebrow>Files</Eyebrow>
      <div className="card" style={{ marginTop: 8, padding: 0, marginBottom: 18 }}>
        {[
          { name: "activity_2026-05-27_0844.fit", status: "ok",    msg: "Imported · 1h 18m run" },
          { name: "activity_2026-05-26_corrupt.fit", status: "error", msg: "CRC mismatch — file truncated. Re-export from device." },
          { name: "swim_session.fit",             status: "error", msg: "Unknown sport ID (15). Convert format first." },
        ].map((f, i, a) => (
          <div key={i} style={{ padding: "12px 14px", borderBottom: i < a.length - 1 ? "1px solid var(--hairline-2)" : "none", display: "grid", gridTemplateColumns: "22px 1fr", gap: 10, alignItems: "flex-start" }}>
            {f.status === "ok" ? (
              <div style={{ width: 18, height: 18, borderRadius: "50%", background: "color-mix(in oklab, var(--good) 20%, transparent)", color: "var(--good)", display: "grid", placeItems: "center" }}>
                <Ic d={I.check} size={10} sw={2.5} />
              </div>
            ) : (
              <div style={{ width: 18, height: 18, borderRadius: "50%", background: "color-mix(in oklab, var(--bad) 20%, transparent)", color: "var(--bad)", display: "grid", placeItems: "center" }}>
                <Ic d={I.x} size={10} sw={2.5} />
              </div>
            )}
            <div>
              <div className="mono" style={{ fontSize: 11, fontWeight: 600, wordBreak: "break-all" }}>{f.name}</div>
              <div style={{ fontSize: 11, color: f.status === "ok" ? "var(--good)" : "var(--fg-3)", marginTop: 3 }}>{f.msg}</div>
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <div className="btn btn-primary" style={{ width: "100%", justifyContent: "center", padding: "12px 16px" }}>
          <Ic d={I.arrow} size={12} sw={2} /> CONTINUE WITH 1 FILE
        </div>
        <div className="btn btn-ghost" style={{ width: "100%", justifyContent: "center", padding: "12px 16px" }}>
          <Ic d={I.upload} size={12} /> UPLOAD MORE
        </div>
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// M16. MOBILE PLAN PROGRESS (cup pour, simplified for mobile)
// ═══════════════════════════════════════════════════════════════════
const MobilePlanProgress = () => (
  <div className="screen">
    <StatusBar />
    <AppBar title="Generating" left={<Ic d={I.chevL} size={22} />} right={null} />

    <div style={{ flex: 1, overflow: "hidden", padding: "12px 18px", display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center" }}>
      <Eyebrow accent>● BUILDING YOUR PLAN</Eyebrow>
      <h1 style={{ fontSize: 28, fontWeight: 800, letterSpacing: "-0.02em", lineHeight: 1.05, margin: "10px 0 8px" }}>
        Pouring you a plan.
      </h1>
      <div style={{ color: "var(--fg-3)", fontSize: 13, lineHeight: 1.5, maxWidth: 320, marginBottom: 8 }}>
        3–5 minutes. We're training your plan as hard as it'll train you.
      </div>

      {/* Scaled-down cup-pour using the same shared keyframes */}
      <div style={{ position: "relative", width: 340, height: 340, marginTop: 12, transform: "scale(0.78)", transformOrigin: "center top" }}>
        <div style={{
          position: "absolute",
          left: "50%",
          top: 60,
          width: 260,
          height: 260,
          transformOrigin: "75% 90%",
          animation: "cupTipping 12s ease-in-out infinite",
        }}>
          <CupOutline size={260} />
          {PLAN_LETTER_RENDER.map((l, i) => (
            <div key={i} style={{
              position: "absolute",
              left: "50%", top: 0,
              width: 14, height: 18, textAlign: "center",
              fontFamily: "var(--mono)", fontSize: 17, fontWeight: 800, lineHeight: 1,
              color: "var(--accent)", opacity: 0,
              "--px": `${l.px}px`, "--x": `${l.x}px`, "--y": `${l.y}px`, "--r": `${l.r}deg`,
              animation: `letterTumble 300s linear ${l.delay}s infinite`,
              pointerEvents: "none", willChange: "transform, opacity",
            }}>{l.ch}</div>
          ))}
        </div>
      </div>

      <div style={{ marginTop: -20 }}>
        <div className="mono" style={{ fontSize: 10, letterSpacing: "0.18em", color: "var(--fg-4)" }}>
          1M 32S ELAPSED · TYPICAL 3–5 MIN
        </div>
        <div style={{ marginTop: 12, fontSize: 12, color: "var(--fg-3)" }}>
          Close the app safely — we'll push when ready.
        </div>
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// M17. MOBILE PLAN COMPARE (vertical diff cards)
// ═══════════════════════════════════════════════════════════════════
const MobilePlanCompare = () => {
  const days = [
    { d: "TUE 27", before: { name: "Threshold intervals", sport: "Run", dur: "68'", z: "Z4" },     after: { name: "Easy aerobic", sport: "Run", dur: "55'", z: "Z2", note: "Moved to Sat" }, changed: true },
    { d: "WED 28", before: { name: "Easy aerobic",  sport: "Run", dur: "52'", z: "Z2" },           after: { name: "Easy aerobic", sport: "Run", dur: "52'", z: "Z2" } },
    { d: "THU 29", before: { name: "Lower strength", sport: "Strength", dur: "45'" },              after: { name: "Upper strength", sport: "Strength", dur: "45'", note: "Avoid hamstring" }, changed: true },
    { d: "FRI 30", before: { name: "VO2 short", sport: "Run", dur: "55'", z: "Z5" },               after: { name: "Easy aerobic", sport: "Run", dur: "40'", z: "Z2", note: "VO2 deferred" }, changed: true },
    { d: "SAT 31", before: { name: "Long run · fueling", sport: "Run", dur: "2h 10m", z: "Z2/Z3" }, after: { name: "Long + threshold", sport: "Run", dur: "2h 00m", z: "Z2/Z4", note: "Threshold in" }, changed: true },
    { d: "SUN 01", before: { name: "Recovery spin", sport: "Bike", dur: "60'" },                    after: { name: "Recovery spin", sport: "Bike", dur: "60'" } },
  ];
  return (
    <div className="screen">
      <StatusBar />
      <AppBar title="v12 → v13" left={<Ic d={I.chevL} size={22} />} right={<div className="mono" style={{ fontSize: 10, letterSpacing: "0.18em", color: "var(--accent)" }}>ACCEPT</div>} />

      {/* Summary */}
      <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--hairline-2)" }}>
        <Eyebrow accent>● PLAN REFRESH · 7-DAY · DIFF</Eyebrow>
        <div style={{ fontSize: 13, color: "var(--fg-2)", marginTop: 6, lineHeight: 1.5, fontStyle: "italic" }}>
          "Tweaked hamstring; travel Wed–Fri."
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 0, marginTop: 12, paddingTop: 12, borderTop: "1px solid var(--hairline-2)" }}>
          {[["CHANGED", "4 / 6"], ["VOLUME", "−18m"], ["INTENSITY", "Z4 −1d"]].map(([k, v], i) => (
            <div key={i} style={{ borderRight: i < 2 ? "1px solid var(--hairline-2)" : "none", padding: "0 6px", textAlign: "center" }}>
              <div className="eyebrow" style={{ fontSize: 8 }}>{k}</div>
              <div className="num" style={{ fontSize: 15, fontWeight: 700, marginTop: 3 }}>{v}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Day diff cards */}
      <div style={{ flex: 1, overflow: "auto", padding: "12px 16px" }}>
        {days.map((day, i) => (
          <div key={i} className="card" style={{
            padding: 12, marginBottom: 8,
            borderLeft: "3px solid " + (day.changed ? "var(--accent)" : "transparent"),
            background: day.changed ? "color-mix(in oklab, var(--accent) 5%, var(--bg-2))" : "var(--bg-2)",
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <span className="mono" style={{ fontSize: 10, letterSpacing: "0.16em", color: day.changed ? "var(--accent)" : "var(--fg-3)", fontWeight: 600 }}>{day.d}</span>
              {day.changed ? <Pill tone="accent">CHANGED</Pill> : <Pill>UNCHANGED</Pill>}
            </div>
            {day.changed ? (
              <>
                <div style={{ display: "flex", gap: 8, fontSize: 12, opacity: 0.55, marginBottom: 6 }}>
                  <span className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--fg-3)", flexShrink: 0, paddingTop: 1 }}>WAS</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ textDecoration: "line-through" }}>{day.before.name}</div>
                    <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.12em", marginTop: 2 }}>{day.before.sport.toUpperCase()} · {day.before.dur}</div>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8, fontSize: 13 }}>
                  <span className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--accent)", flexShrink: 0, paddingTop: 1 }}>NEW</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600 }}>{day.after.name}</div>
                    <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.12em", marginTop: 2 }}>{day.after.sport.toUpperCase()} · {day.after.dur} {day.after.z && `· ${day.after.z}`}</div>
                    {day.after.note && <div className="mono" style={{ fontSize: 9, color: "var(--accent)", letterSpacing: "0.12em", marginTop: 4 }}>● {day.after.note.toUpperCase()}</div>}
                  </div>
                </div>
              </>
            ) : (
              <div style={{ fontSize: 13 }}>
                <span style={{ fontWeight: 600 }}>{day.after.name}</span>
                <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.12em", marginLeft: 8 }}>{day.after.sport.toUpperCase()} · {day.after.dur}</span>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Bottom action bar */}
      <div style={{ padding: "10px 14px 22px", borderTop: "1px solid var(--hairline-2)", display: "flex", gap: 8, background: "var(--bg)", flexShrink: 0 }}>
        <div className="btn btn-ghost" style={{ flex: 1, justifyContent: "center", padding: "12px 16px" }}>DISCARD</div>
        <div className="btn btn-primary" style={{ flex: 2, justifyContent: "center", padding: "12px 16px" }}>
          <Ic d={I.check} size={13} sw={2.2} /> ACCEPT · ACTIVATE v13
        </div>
      </div>
    </div>
  );
};

Object.assign(window, {
  MobileDashboardEmpty, MobileWellnessEmpty, MobileConnectionsEmpty,
  MobileAuthFailed, MobileFitError, MobilePlanProgress, MobilePlanCompare,
});
