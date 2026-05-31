/* AIDSTATION redesign — Shared "no plan" empty state
   ───────────────────────────────────────────────────────────────
   Consolidates THREE previously-divergent screens into one design:
     · Dashboard · no plan   (was "You haven't built a plan.")
     · Plan page · no plan   (was "You don't have a plan yet.")
     · Plans list · no plan  (was "You haven't made a plan.")
   One headline, one layout, reused across all three surfaces.
   Loaded LAST so its window exports override the originals. */

// ─── Shared body (desktop) ────────────────────────────────────────
const NoPlanBody = () => (
  <div style={{ maxWidth: 600, width: "100%", textAlign: "center" }}>
    <Eyebrow accent>● NO ACTIVE PLAN</Eyebrow>
    <h1 style={{ fontSize: 44, fontWeight: 800, letterSpacing: "-0.025em", lineHeight: 1.04, margin: "12px 0 14px" }}>
      You're at the start line.
    </h1>
    <div style={{ color: "var(--fg-3)", fontSize: 15, lineHeight: 1.55, maxWidth: 470, margin: "0 auto 26px" }}>
      Every session you'll run anchors to a race. Generate your first plan in 3–5 minutes — built from your profile, your schedule, and your target — or import one you already have.
    </div>

    {/* Pre-flight readiness — the single most useful thing to show here */}
    <div className="card" style={{ padding: 18, textAlign: "left", marginBottom: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <Eyebrow>Pre-flight · what the cascade has</Eyebrow>
        <span className="mono" style={{ fontSize: 9, letterSpacing: "0.16em", color: "var(--fg-3)", textTransform: "uppercase" }}>1 thing left</span>
      </div>
      <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 8 }}>
        {[
          ["Account",               true,  "Andrew Horn · andrew@aidstation.run"],
          ["Connected source",      true,  "Strava · 412 sessions"],
          ["Performance baselines", true,  "6 of 6 set"],
          ["Schedule",              true,  "6 days · 8.5 h/wk"],
          ["Skills",                true,  "5 of 12 checked"],
          ["Locations",             true,  "Home garage + 2 more"],
          ["Target race",           false, "Not set — required to generate"],
        ].map(([k, ok, v], i) => (
          <div key={i} style={{ display: "grid", gridTemplateColumns: "20px 1fr auto", gap: 12, alignItems: "center" }}>
            {ok ? (
              <div style={{ width: 16, height: 16, borderRadius: "50%", background: "color-mix(in oklab, var(--good) 20%, transparent)", color: "var(--good)", display: "grid", placeItems: "center" }}>
                <Ic d={I.check} size={10} sw={2.5} />
              </div>
            ) : (
              <div style={{ width: 10, height: 10, borderRadius: "50%", background: "var(--warn)", boxShadow: "0 0 0 4px color-mix(in oklab, var(--warn) 30%, transparent)", margin: "0 3px" }} />
            )}
            <div>
              <div style={{ fontWeight: 600, fontSize: 13 }}>{k}</div>
              <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em", marginTop: 2, textTransform: "uppercase" }}>{v}</div>
            </div>
            {!ok && <Pill tone="warn">FIX →</Pill>}
          </div>
        ))}
      </div>
    </div>

    {/* The two ways in */}
    <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 12, marginBottom: 16 }}>
      <div className="card" style={{ padding: 18, textAlign: "left", border: "1px solid color-mix(in oklab, var(--accent) 35%, var(--hairline-2))" }}>
        <Eyebrow accent>● START HERE</Eyebrow>
        <div style={{ fontSize: 17, fontWeight: 700, marginTop: 6 }}>Generate from your profile</div>
        <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 5, lineHeight: 1.5 }}>
          We periodize back from your race date — Base → Build → Peak → Taper.
        </div>
        <div className="btn btn-primary" style={{ marginTop: 13, width: "100%", justifyContent: "center", padding: "12px 14px" }}>
          <Ic d={I.bolt} size={12} /> SET RACE &amp; GENERATE
        </div>
      </div>
      <div className="card" style={{ padding: 18, textAlign: "left" }}>
        <Eyebrow>● POWER USER</Eyebrow>
        <div style={{ fontSize: 17, fontWeight: 700, marginTop: 6 }}>Import a plan</div>
        <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 5, lineHeight: 1.5 }}>
          Paste JSON from a coach, another tool, or hand-built.
        </div>
        <div className="btn btn-ghost" style={{ marginTop: 13, width: "100%", justifyContent: "center", padding: "12px 14px" }}>
          <Ic d={I.upload} size={12} /> IMPORT
        </div>
      </div>
    </div>

    {/* Past races — only meaningful for returning athletes; harmless otherwise */}
    <div className="card-flush" style={{ padding: 16, textAlign: "left" }}>
      <Eyebrow>Or revisit a past race</Eyebrow>
      <div style={{ display: "flex", gap: 10, marginTop: 10 }}>
        {[
          "NYC Marathon 2025",
          "Boston Marathon 2025",
          "Bay to Breakers 2025",
        ].map((name, i) => (
          <div key={i} style={{ padding: "8px 12px", border: "1px solid var(--hairline-2)", borderRadius: 4, flex: 1, fontSize: 12 }}>
            <div style={{ fontWeight: 600 }}>{name}</div>
            <Pill tone="good" style={{ marginTop: 6 }}>✓ ARCHIVED</Pill>
          </div>
        ))}
      </div>
    </div>

    <div className="mono" style={{ marginTop: 18, fontSize: 10, letterSpacing: "0.18em", color: "var(--fg-4)", textTransform: "uppercase" }}>
      ⓘ NOTHING IS LOCKED IN · EDIT ANYTHING AFTER GENERATION
    </div>
  </div>
);

// Desktop surface wrapper — same body, contextual sidebar + crumbs
const NoPlanScreen = ({ active, crumbs }) => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active={active} />
      <div className="page">
        <TopBar crumbs={crumbs} actions={null} />
        <div className="page-body" style={{ display: "grid", placeItems: "center", padding: "32px 28px" }}>
          <NoPlanBody />
        </div>
      </div>
    </div>
  </div>
);

const ScreenDashboardEmpty = () => <NoPlanScreen active="home" crumbs={["Today"]} />;
const ScreenPlanEmpty       = () => <NoPlanScreen active="plan" crumbs={["Plan"]} />;
const ScreenPlanListEmpty   = () => <NoPlanScreen active="plan" crumbs={["Plan", "All plans"]} />;

// ─── Shared body (mobile) ─────────────────────────────────────────
const MobileNoPlanBody = () => (
  <>
    <div style={{ textAlign: "center", marginBottom: 18 }}>
      <Eyebrow accent>● NO ACTIVE PLAN</Eyebrow>
      <h1 style={{ fontSize: 27, fontWeight: 800, letterSpacing: "-0.025em", lineHeight: 1.05, margin: "10px 0 8px" }}>
        You're at the start line.
      </h1>
      <div style={{ color: "var(--fg-3)", fontSize: 13, lineHeight: 1.5 }}>
        Every session anchors to a race. Build your first plan in 3–5 minutes, or import one you already have.
      </div>
    </div>

    {/* Pre-flight readiness */}
    <div className="card" style={{ padding: 14, marginBottom: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <Eyebrow>Pre-flight</Eyebrow>
        <span className="mono" style={{ fontSize: 9, letterSpacing: "0.16em", color: "var(--warn)", textTransform: "uppercase" }}>1 left</span>
      </div>
      <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 7 }}>
        {[
          ["Source connected", true,  "Strava · 412"],
          ["Baselines",        true,  "6 of 6"],
          ["Schedule",         true,  "6 days · 8.5h"],
          ["Locations",        true,  "3 saved"],
          ["Target race",      false, "Not set"],
        ].map(([k, ok, v], i) => (
          <div key={i} style={{ display: "grid", gridTemplateColumns: "16px 1fr auto", gap: 10, alignItems: "center" }}>
            {ok ? (
              <div style={{ width: 14, height: 14, borderRadius: "50%", background: "color-mix(in oklab, var(--good) 20%, transparent)", color: "var(--good)", display: "grid", placeItems: "center" }}>
                <Ic d={I.check} size={9} sw={2.5} />
              </div>
            ) : (
              <div style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--warn)", boxShadow: "0 0 0 3px color-mix(in oklab, var(--warn) 30%, transparent)", margin: "0 3px" }} />
            )}
            <div style={{ fontSize: 12, fontWeight: 600 }}>{k}</div>
            <span className="mono" style={{ fontSize: 9, letterSpacing: "0.12em", color: ok ? "var(--fg-3)" : "var(--warn)", textTransform: "uppercase" }}>{v}</span>
          </div>
        ))}
      </div>
    </div>

    <div className="card" style={{ padding: 14, border: "1px solid color-mix(in oklab, var(--accent) 40%, var(--hairline-2))", marginBottom: 10 }}>
      <Eyebrow accent>● START HERE</Eyebrow>
      <div style={{ fontSize: 15, fontWeight: 700, marginTop: 6 }}>Generate from your profile</div>
      <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 4, lineHeight: 1.45 }}>
        Periodized Base → Build → Peak → Taper from your race date.
      </div>
      <div className="btn btn-primary btn-sm" style={{ marginTop: 12, width: "100%", justifyContent: "center" }}>
        <Ic d={I.bolt} size={11} /> SET RACE &amp; GENERATE
      </div>
    </div>
    <div className="btn btn-ghost btn-sm" style={{ width: "100%", justifyContent: "center" }}>
      <Ic d={I.upload} size={11} /> IMPORT A JSON PLAN
    </div>

    <div className="mono" style={{ marginTop: 16, fontSize: 9, letterSpacing: "0.16em", color: "var(--fg-4)", textAlign: "center", textTransform: "uppercase" }}>
      ⓘ NOTHING IS LOCKED IN · EDIT ANYTHING AFTER
    </div>
  </>
);

const MobileNoPlanScreen = ({ tab, appbar, right = null }) => (
  <div className="screen">
    <StatusBar />
    <AppBar title={appbar} left={<Ic d={I.menu} size={22} />} right={right} />
    <div style={{ flex: 1, overflow: "auto", padding: "18px 18px 24px" }}>
      <MobileNoPlanBody />
    </div>
    <TabBar active={tab} />
  </div>
);

const MobileDashboardEmpty = () => <MobileNoPlanScreen tab="home" appbar="Today" right={<Ic d={I.bell} size={20} />} />;
const MobilePlanEmpty      = () => <MobileNoPlanScreen tab="plan" appbar="Plan" />;
const MobilePlanListEmpty  = () => <MobileNoPlanScreen tab="plan" appbar="Plans" />;

// Override the originals (load order guarantees this file wins)
Object.assign(window, {
  ScreenDashboardEmpty, ScreenPlanEmpty, ScreenPlanListEmpty,
  MobileDashboardEmpty, MobilePlanEmpty, MobilePlanListEmpty,
  NoPlanBody, MobileNoPlanBody,
});
