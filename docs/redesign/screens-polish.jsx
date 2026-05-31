/* AIDSTATION redesign — Polish: light mode + accessibility spec (§28–29)
   Light variants reuse the exact same screen components, wrapped in
   `.light` so the token swap does all the work — proof the palette is
   theme-ready, not a reskin. The A11y card documents the focus / motion
   / contrast / hit-target rules shipped in polish.css. */

const Light = ({ children }) => (
  <div className="light" style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", background: "var(--bg)" }}>
    {children}
  </div>
);

// Light-wrapped representatives (reuse real components)
const LightDashboard   = () => <Light><ScreenDashboard /></Light>;
const LightPlan        = () => <Light><ScreenPlan /></Light>;
const LightWorkout     = () => <Light><ScreenWorkout /></Light>;
const LightConnections = () => <Light><ScreenConnHubSources /></Light>;
const LightMobileDash  = () => <Light><MobileDashboard /></Light>;
const LightMobilePlan  = () => <Light><MobilePlan /></Light>;
// archetype coverage: form, list/table, feed, profile, admin, races, logging
const LightLogging     = () => <Light><ScreenLog type="cardio" /></Light>;
const LightExercises   = () => <Light><ScreenExercises /></Light>;
const LightWellness    = () => <Light><ScreenWellness /></Light>;
const LightRaces       = () => <Light><ScreenRaceEvents /></Light>;
const LightProfile     = () => <Light><ScreenProfile /></Light>;
const LightAccount     = () => <Light><ScreenAccount /></Light>;
const LightNotifs      = () => <Light><ScreenNotifications /></Light>;
const LightAdmin       = () => <Light><ScreenAdmin /></Light>;
const LightMobileLog   = () => <Light><MobileQuickLog /></Light>;
const LightMobileConn  = () => <Light><MobileConnHubSources /></Light>;

// ── Accessibility & motion spec note ──────────────────────────────
const SpecRow = ({ k, children }) => (
  <div style={{ display: "grid", gridTemplateColumns: "128px 1fr", gap: 16, padding: "14px 0", borderBottom: "1px solid var(--hairline-2)", alignItems: "start" }}>
    <span className="mono" style={{ fontSize: 10, letterSpacing: "0.16em", color: "var(--fg-3)", textTransform: "uppercase", paddingTop: 2 }}>{k}</span>
    <div style={{ fontSize: 13, color: "var(--fg-2)", lineHeight: 1.55 }}>{children}</div>
  </div>
);

const ScreenA11ySpec = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="home" />
      <div className="page">
        <TopBar crumbs={["Polish", "Accessibility & motion"]} actions={
          <div className="btn btn-ghost btn-sm"><Ic d={I.check} size={11} sw={2.2} /> Shipped in polish.css</div>
        } />
        <div className="page-body">
          <div style={{ maxWidth: 720, marginBottom: 22 }}>
            <Eyebrow>Polish · the rules behind the pixels</Eyebrow>
            <h1 className="page-title" style={{ marginTop: 8 }}>Accessibility &amp; motion.</h1>
            <div className="page-sub">Focus, contrast, hit targets, reduced motion, and print — all live in <span className="mono" style={{ color: "var(--fg-2)" }}>polish.css</span> so the built components inherit them for free.</div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1.1fr 1fr", gap: 22, alignItems: "start" }}>
            {/* LEFT — the spec */}
            <div className="card" style={{ padding: "4px 20px 16px" }}>
              <SpecRow k="Focus">
                Every interactive element gets a <b>2px accent ring</b> at 2px offset on <span className="mono" style={{ fontSize: 12 }}>:focus-visible</span> — keyboard only, never on mouse click. On orange fills the ring flips to ink for contrast.
              </SpecRow>
              <SpecRow k="Contrast">
                Body text <b>≥ 4.5:1</b>, large text + UI <b>≥ 3:1</b>. <span className="mono" style={{ fontSize: 12 }}>--fg</span> on <span className="mono" style={{ fontSize: 12 }}>--bg</span> ≈ 15:1; the muted <span className="mono" style={{ fontSize: 12 }}>--fg-3</span> is reserved for labels, never body copy.
              </SpecRow>
              <SpecRow k="Hit targets">
                Mobile tap targets <b>≥ 44×44px</b> (tab bar, FAB, list rows). Desktop click targets ≥ 32px. Icon-only buttons pad to a full square.
              </SpecRow>
              <SpecRow k="Motion">
                <span className="mono" style={{ fontSize: 12 }}>prefers-reduced-motion</span> kills the plan-gen letter-tumble + every transition. Letters settle legibly in the cup instead of spilling.
              </SpecRow>
              <SpecRow k="Print">
                Any screen prints ink-on-paper: forced light palette, exact color for accent fills + charts, transient chrome hidden, scroll regions un-clipped, rows kept off page breaks.
              </SpecRow>
              <SpecRow k="Forced colors">
                Windows high-contrast mode keeps hairlines + accents visible via system color keywords.
              </SpecRow>
            </div>

            {/* RIGHT — live focus demo + motion */}
            <div className="stack">
              <div className="card" style={{ padding: 20 }}>
                <Eyebrow>Focus ring · live</Eyebrow>
                <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 8, marginBottom: 14, lineHeight: 1.5 }}>
                  How the <span className="mono" style={{ fontSize: 12 }}>:focus-visible</span> treatment renders on each button type.
                </div>
                <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
                  <div className="btn btn-primary focus-demo on-accent">Primary</div>
                  <div className="btn btn-ghost focus-demo">Ghost</div>
                  <div className="btn btn-icon focus-demo"><Ic d={I.gear} size={14} /></div>
                  <span className="focus-demo" style={{ display: "inline-flex" }}><Pill tone="accent">CHIP</Pill></span>
                </div>
              </div>

              <div className="card" style={{ padding: 20 }}>
                <Eyebrow>Hit targets</Eyebrow>
                <div style={{ display: "flex", gap: 14, marginTop: 14, alignItems: "flex-end" }}>
                  <div style={{ textAlign: "center" }}>
                    <div style={{ width: 44, height: 44, borderRadius: 8, border: "1px dashed color-mix(in oklab, var(--accent) 55%, var(--hairline))", display: "grid", placeItems: "center", color: "var(--accent)" }}>
                      <Ic d={I.plus} size={18} />
                    </div>
                    <div className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--fg-3)", marginTop: 6 }}>44²·MIN</div>
                  </div>
                  <div style={{ textAlign: "center" }}>
                    <div style={{ width: 32, height: 32, borderRadius: 6, border: "1px dashed var(--hairline)", display: "grid", placeItems: "center", color: "var(--fg-3)" }}>
                      <Ic d={I.gear} size={14} />
                    </div>
                    <div className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--fg-3)", marginTop: 6 }}>32²·DESK</div>
                  </div>
                  <div style={{ flex: 1, fontSize: 12, color: "var(--fg-3)", lineHeight: 1.5 }}>
                    Dashed = minimum touch/click bounds. Visual icon can be smaller; the target can't.
                  </div>
                </div>
              </div>

              <div className="card-flush" style={{ padding: 16 }}>
                <Eyebrow>Reduced motion</Eyebrow>
                <div style={{ display: "flex", gap: 16, marginTop: 12 }}>
                  <div style={{ flex: 1 }}>
                    <div className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--fg-3)", textTransform: "uppercase" }}>DEFAULT</div>
                    <div style={{ fontSize: 12, color: "var(--fg-2)", marginTop: 4, lineHeight: 1.45 }}>Letters scatter into the cup, then spill out as the plan finishes.</div>
                  </div>
                  <div style={{ width: 1, background: "var(--hairline-2)" }} />
                  <div style={{ flex: 1 }}>
                    <div className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--accent)", textTransform: "uppercase" }}>REDUCED</div>
                    <div style={{ fontSize: 12, color: "var(--fg-2)", marginTop: 4, lineHeight: 1.45 }}>Phrase appears, holds, swaps. No tumble, no transitions.</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

Object.assign(window, {
  LightDashboard, LightPlan, LightWorkout, LightConnections, LightMobileDash, LightMobilePlan,
  LightLogging, LightExercises, LightWellness, LightRaces, LightProfile, LightAccount,
  LightNotifs, LightAdmin, LightMobileLog, LightMobileConn,
  ScreenA11ySpec,
});
