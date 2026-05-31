/* AIDSTATION redesign — Empty + error states (part 2)
   Plan list empty · Locations empty · Workout empty (rest day)
   Mobile: plan-gen failed · refresh cap modal · offline state */

// ═══════════════════════════════════════════════════════════════════
// E10. PLAN LIST — empty (brand-new user, no plans yet)
// ═══════════════════════════════════════════════════════════════════
const ScreenPlanListEmpty = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="plan" />
      <div className="page">
        <TopBar crumbs={["Plan", "All plans"]} actions={null} />
        <div className="page-body" style={{ display: "grid", placeItems: "center", padding: "32px 28px" }}>
          <div style={{ maxWidth: 580, width: "100%", textAlign: "center" }}>
            <Eyebrow>● ZERO PLANS · BRAND NEW</Eyebrow>
            <h1 style={{ fontSize: 42, fontWeight: 800, letterSpacing: "-0.025em", lineHeight: 1.05, margin: "12px 0 10px" }}>
              You haven't made a plan.
            </h1>
            <div style={{ color: "var(--fg-3)", fontSize: 14, lineHeight: 1.55, maxWidth: 460, margin: "0 auto 28px" }}>
              Plans are how everything connects — your race target, your schedule, your sessions all anchor here. Build your first one in 3–5 minutes.
            </div>

            <div className="card" style={{ padding: 22, marginBottom: 14, textAlign: "left", border: "1px solid color-mix(in oklab, var(--accent) 35%, var(--hairline-2))" }}>
              <Eyebrow accent>● START HERE</Eyebrow>
              <div style={{ fontSize: 18, fontWeight: 700, marginTop: 6 }}>Generate from your profile</div>
              <div style={{ fontSize: 13, color: "var(--fg-3)", marginTop: 6, lineHeight: 1.5 }}>
                We periodize back from your race date — Base → Build → Peak → Taper — using your connected providers, skills, schedule, and locations.
              </div>
              <div className="btn btn-primary" style={{ marginTop: 14, padding: "12px 16px" }}>
                <Ic d={I.bolt} size={12} /> GENERATE YOUR FIRST PLAN
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 18 }}>
              <div className="card" style={{ padding: 16, textAlign: "left" }}>
                <Eyebrow>● IMPORT</Eyebrow>
                <div style={{ fontSize: 14, fontWeight: 700, marginTop: 6 }}>Have a JSON plan?</div>
                <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 4, lineHeight: 1.45 }}>
                  Paste the JSON — from another tool, a coach, or hand-built.
                </div>
                <div className="btn btn-ghost btn-sm" style={{ marginTop: 12, width: "100%", justifyContent: "center" }}>IMPORT PLAN</div>
              </div>
              <div className="card" style={{ padding: 16, textAlign: "left" }}>
                <Eyebrow>● TEMPLATE</Eyebrow>
                <div style={{ fontSize: 14, fontWeight: 700, marginTop: 6 }}>Start from a template</div>
                <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 4, lineHeight: 1.45 }}>
                  Marathon · 50K · 70.3 · Olympic Tri · skeleton plans.
                </div>
                <div className="btn btn-ghost btn-sm" style={{ marginTop: 12, width: "100%", justifyContent: "center" }}>BROWSE</div>
              </div>
            </div>

            <div className="mono" style={{ fontSize: 10, letterSpacing: "0.18em", color: "var(--fg-4)", textTransform: "uppercase" }}>
              ⓘ NEED A RACE TARGET FIRST? <span style={{ color: "var(--accent)" }}>SET ONE →</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

const MobilePlanListEmpty = () => (
  <div className="screen">
    <StatusBar />
    <AppBar title="Plans" left={<Ic d={I.menu} size={22} />} right={null} />

    <div style={{ flex: 1, overflow: "auto", padding: "20px 18px", display: "flex", flexDirection: "column", justifyContent: "center" }}>
      <div style={{ textAlign: "center" }}>
        <Eyebrow>● ZERO PLANS · BRAND NEW</Eyebrow>
        <h1 style={{ fontSize: 26, fontWeight: 800, letterSpacing: "-0.025em", lineHeight: 1.05, margin: "10px 0 8px" }}>
          You haven't made a plan.
        </h1>
        <div style={{ color: "var(--fg-3)", fontSize: 13, lineHeight: 1.5, marginBottom: 18 }}>
          Build your first one in 3–5 minutes.
        </div>
      </div>

      <div className="card" style={{ padding: 14, border: "1px solid color-mix(in oklab, var(--accent) 40%, var(--hairline-2))", marginBottom: 10 }}>
        <Eyebrow accent>● START HERE</Eyebrow>
        <div style={{ fontSize: 15, fontWeight: 700, marginTop: 6 }}>Generate from your profile</div>
        <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 4, lineHeight: 1.45 }}>
          Periodized Base → Build → Peak → Taper from your race date.
        </div>
        <div className="btn btn-primary btn-sm" style={{ marginTop: 12, width: "100%", justifyContent: "center" }}>
          <Ic d={I.bolt} size={11} /> GENERATE FIRST PLAN
        </div>
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <div className="card" style={{ padding: 12, flex: 1 }}>
          <Eyebrow>IMPORT</Eyebrow>
          <div style={{ fontSize: 13, fontWeight: 600, marginTop: 4 }}>JSON plan</div>
          <div className="btn btn-ghost btn-sm" style={{ marginTop: 8, width: "100%", justifyContent: "center" }}>OPEN</div>
        </div>
        <div className="card" style={{ padding: 12, flex: 1 }}>
          <Eyebrow>TEMPLATE</Eyebrow>
          <div style={{ fontSize: 13, fontWeight: 600, marginTop: 4 }}>Marathon · 50K · …</div>
          <div className="btn btn-ghost btn-sm" style={{ marginTop: 8, width: "100%", justifyContent: "center" }}>BROWSE</div>
        </div>
      </div>

      <div style={{ marginTop: 18, textAlign: "center" }}>
        <span className="mono" style={{ fontSize: 10, letterSpacing: "0.16em", color: "var(--accent)" }}>SET RACE TARGET FIRST →</span>
      </div>
    </div>

    <TabBar active="plan" />
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// E11. LOCATIONS — empty
// ═══════════════════════════════════════════════════════════════════
const ScreenLocationsEmpty = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="locations" />
      <div className="page">
        <TopBar crumbs={["Locations"]} actions={
          <div className="btn btn-primary"><Ic d={I.plus} size={12} sw={2.2} /> Add location</div>
        } />
        <div className="page-body" style={{ display: "grid", placeItems: "center", padding: "32px 28px" }}>
          <div style={{ maxWidth: 580, textAlign: "center" }}>
            <Eyebrow>● NO LOCATIONS SAVED</Eyebrow>
            <h1 style={{ fontSize: 36, fontWeight: 700, letterSpacing: "-0.02em", margin: "10px 0 10px" }}>
              Where do you train?
            </h1>
            <div style={{ color: "var(--fg-3)", fontSize: 14, lineHeight: 1.55, maxWidth: 460, margin: "0 auto 24px" }}>
              Each location has its own equipment profile — barbell at home vs cable stack at the gym vs treadmill at the hotel. We filter exercises to what's actually available.
            </div>

            {/* Quick-add cards */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, marginBottom: 18 }}>
              {[
                ["Home",    "Your default training spot"],
                ["Gym",     "Chain or independent"],
                ["Route",   "Outdoor run / ride loop"],
                ["Hotel",   "Travel default"],
              ].map(([t, s], i) => (
                <div key={i} className="card" style={{ padding: 16, textAlign: "left" }}>
                  <div className="eyebrow accent" style={{ fontSize: 9 }}>● {t.toUpperCase()}</div>
                  <div style={{ fontSize: 14, fontWeight: 700, marginTop: 8 }}>Add {t.toLowerCase()}</div>
                  <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em", marginTop: 6, textTransform: "uppercase" }}>{s}</div>
                  <div className="btn btn-ghost btn-sm" style={{ marginTop: 12, width: "100%", justifyContent: "center" }}><Ic d={I.plus} size={10} sw={2} /> ADD</div>
                </div>
              ))}
            </div>

            <div className="card-flush" style={{ padding: "14px 16px", textAlign: "left" }}>
              <Eyebrow>Or search by address</Eyebrow>
              <div style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 10 }}>
                <Ic d={I.search} size={14} />
                <span style={{ flex: 1, color: "var(--fg-3)", fontSize: 13 }}>Equinox, Planet Fitness, an address…</span>
                <div className="btn btn-primary btn-sm">SEARCH</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

const MobileLocationsEmpty = () => (
  <div className="screen">
    <StatusBar />
    <AppBar
      title="Locations"
      left={<Ic d={I.menu} size={22} />}
      right={<div className="mono" style={{ fontSize: 10, letterSpacing: "0.18em", color: "var(--accent)" }}>+ ADD</div>}
    />

    <div style={{ flex: 1, overflow: "auto", padding: "20px 18px" }}>
      <div style={{ textAlign: "center", marginBottom: 22 }}>
        <Eyebrow>● NO LOCATIONS SAVED</Eyebrow>
        <h1 style={{ fontSize: 24, fontWeight: 700, letterSpacing: "-0.02em", margin: "10px 0 8px" }}>
          Where do you train?
        </h1>
        <div style={{ color: "var(--fg-3)", fontSize: 13, lineHeight: 1.5 }}>
          Each spot has its own equipment profile. We filter exercises to what's actually available.
        </div>
      </div>

      {/* Search bar */}
      <div style={{ padding: "12px 14px", border: "1px solid var(--hairline)", borderRadius: 4, display: "flex", alignItems: "center", gap: 10, marginBottom: 18 }}>
        <Ic d={I.search} size={14} />
        <span style={{ flex: 1, fontSize: 13, color: "var(--fg-3)" }}>Equinox, an address…</span>
      </div>

      <Eyebrow>Or pick a type</Eyebrow>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 10 }}>
        {[
          ["Home",  "Default training spot"],
          ["Gym",   "Chain or independent"],
          ["Route", "Outdoor loop"],
          ["Hotel", "Travel default"],
        ].map(([t, s], i) => (
          <div key={i} className="card" style={{ padding: 12 }}>
            <div className="eyebrow accent" style={{ fontSize: 9 }}>● {t.toUpperCase()}</div>
            <div style={{ fontSize: 13, fontWeight: 700, marginTop: 6 }}>Add {t.toLowerCase()}</div>
            <div className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.14em", marginTop: 4, textTransform: "uppercase" }}>{s}</div>
            <div className="btn btn-ghost btn-sm" style={{ marginTop: 10, width: "100%", justifyContent: "center" }}><Ic d={I.plus} size={10} sw={2} /> ADD</div>
          </div>
        ))}
      </div>
    </div>

    <TabBar active="me" />
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// E12. WORKOUT — empty (rest day / no workout today)
// ═══════════════════════════════════════════════════════════════════
const ScreenWorkoutEmpty = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="workout" />
      <div className="page">
        <TopBar crumbs={["Today", "May 27"]} actions={null} />
        <div className="page-body" style={{ display: "grid", placeItems: "center", padding: "32px 28px" }}>
          <div style={{ maxWidth: 580, textAlign: "center" }}>
            <Eyebrow>● REST DAY · BY DESIGN</Eyebrow>
            <h1 style={{ fontSize: 42, fontWeight: 800, letterSpacing: "-0.025em", lineHeight: 1.05, margin: "12px 0 12px" }}>
              Nothing today. <span style={{ color: "var(--fg-3)", fontWeight: 300 }}>By design.</span>
            </h1>
            <div style={{ color: "var(--fg-3)", fontSize: 15, lineHeight: 1.55, maxWidth: 480, margin: "0 auto 28px" }}>
              Your plan has Wednesday penciled as a recovery day. Move easy, sleep well, eat. Tomorrow's threshold session needs you ready.
            </div>

            {/* Up next */}
            <div className="card" style={{ padding: 18, marginBottom: 14, textAlign: "left" }}>
              <Eyebrow accent>● TOMORROW · KEY SESSION</Eyebrow>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 12 }}>
                <div>
                  <div style={{ fontSize: 17, fontWeight: 700 }}>Threshold intervals</div>
                  <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em", marginTop: 4, textTransform: "uppercase" }}>
                    THU MAY 28 · RUN · 68 MIN · 6×5' @ FTHR
                  </div>
                </div>
                <div className="btn btn-ghost btn-sm"><Ic d={I.arrow} size={11} sw={2} /> PREVIEW</div>
              </div>
            </div>

            {/* Optional add-on */}
            <div className="card-flush" style={{ padding: 16, textAlign: "left" }}>
              <Eyebrow>Feel like moving anyway?</Eyebrow>
              <div style={{ fontSize: 13, color: "var(--fg-2)", marginTop: 8, lineHeight: 1.5 }}>
                Rest doesn't mean nothing. Try 15–20 min of mobility, a walk, or some easy spinning at Z1. Want a suggestion?
              </div>
              <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                <div className="btn btn-ghost btn-sm"><Ic d={I.bolt} size={11} /> SUGGEST EASY SESSION</div>
                <div className="btn btn-text btn-sm" style={{ color: "var(--fg-3)" }}>LOG A SESSION</div>
              </div>
            </div>

            <div className="mono" style={{ marginTop: 22, fontSize: 10, letterSpacing: "0.18em", color: "var(--fg-4)", textTransform: "uppercase" }}>
              ⓘ RECOVERY DAYS ARE WHEN ADAPTATIONS HAPPEN · TRUST THE PLAN
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

const MobileWorkoutEmpty = () => (
  <div className="screen">
    <StatusBar />
    <AppBar
      title="Today"
      left={<Ic d={I.menu} size={22} />}
      right={<Ic d={I.bell} size={20} />}
    />

    <div style={{ flex: 1, overflow: "auto", padding: "20px 18px" }}>
      <div style={{ textAlign: "center", marginBottom: 22 }}>
        <Eyebrow>● REST DAY · BY DESIGN</Eyebrow>
        <h1 style={{ fontSize: 26, fontWeight: 800, letterSpacing: "-0.025em", lineHeight: 1.05, margin: "10px 0 8px" }}>
          Nothing today. <span style={{ color: "var(--fg-3)", fontWeight: 300 }}>By design.</span>
        </h1>
        <div style={{ color: "var(--fg-3)", fontSize: 13, lineHeight: 1.5 }}>
          Your plan has Wednesday penciled for recovery. Move easy, sleep well, eat. Tomorrow needs you ready.
        </div>
      </div>

      <div className="card" style={{ padding: 14, marginBottom: 10 }}>
        <Eyebrow accent>● TOMORROW · KEY</Eyebrow>
        <div style={{ fontSize: 15, fontWeight: 700, marginTop: 6 }}>Threshold intervals</div>
        <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em", marginTop: 4, textTransform: "uppercase" }}>
          THU MAY 28 · RUN · 68 MIN · 6×5' @ FTHR
        </div>
        <div className="btn btn-ghost btn-sm" style={{ marginTop: 12, width: "100%", justifyContent: "center" }}><Ic d={I.arrow} size={11} sw={2} /> PREVIEW</div>
      </div>

      <div className="card-flush" style={{ padding: 14 }}>
        <Eyebrow>Feel like moving?</Eyebrow>
        <div style={{ fontSize: 12, color: "var(--fg-2)", marginTop: 6, lineHeight: 1.5 }}>
          Try 15–20 min mobility, a walk, or easy Z1 spinning.
        </div>
        <div className="btn btn-ghost btn-sm" style={{ marginTop: 12, width: "100%", justifyContent: "center" }}><Ic d={I.bolt} size={11} /> SUGGEST EASY SESSION</div>
      </div>

      <div className="mono" style={{ marginTop: 20, fontSize: 10, letterSpacing: "0.16em", color: "var(--fg-4)", textAlign: "center", textTransform: "uppercase" }}>
        ⓘ RECOVERY IS WHEN ADAPTATIONS HAPPEN
      </div>
    </div>

    <TabBar active="home" />
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// E13. MOBILE — PLAN GEN FAILED
// ═══════════════════════════════════════════════════════════════════
const MobilePlanGenFailed = () => (
  <div className="screen">
    <StatusBar />
    <AppBar title="Generation failed" left={<Ic d={I.chevL} size={22} />} right={null} />

    <div style={{ flex: 1, overflow: "auto", padding: "16px 18px", textAlign: "center" }}>
      <div style={{ width: 60, height: 60, margin: "0 auto 14px", borderRadius: "50%", background: "color-mix(in oklab, var(--bad) 15%, transparent)", color: "var(--bad)", display: "grid", placeItems: "center" }}>
        <Ic d={I.x} size={28} sw={2} />
      </div>
      <Eyebrow style={{ color: "var(--bad)" }}>● FAILED · STEP 4 OF 6</Eyebrow>
      <h1 style={{ fontSize: 24, fontWeight: 700, letterSpacing: "-0.02em", margin: "10px 0 8px" }}>Plan didn't finish.</h1>
      <div style={{ color: "var(--fg-3)", fontSize: 13, lineHeight: 1.5, marginBottom: 18 }}>
        We got partway through. Peak block hit a constraint conflict. Your inputs are saved.
      </div>

      <div className="card-flush" style={{ padding: "12px 14px", textAlign: "left", marginBottom: 16 }}>
        <Eyebrow>Diagnostic</Eyebrow>
        <div style={{ marginTop: 6, fontFamily: "var(--mono)", fontSize: 11, lineHeight: 1.7, color: "var(--fg-2)" }}>
          <div>gen_id: <span style={{ color: "var(--accent)" }}>gen_9c40e2a1</span></div>
          <div>failed_phase: peak_block</div>
          <div>error: <span style={{ color: "var(--bad)" }}>InfeasibleSchedule</span></div>
        </div>
        <div style={{ marginTop: 8, fontSize: 11, color: "var(--fg-3)", lineHeight: 1.5 }}>
          Weekly long session (≥2h 30m) doesn't fit any enabled day window during peak.
        </div>
      </div>

      <Eyebrow style={{ textAlign: "left" }}>Suggested fixes</Eyebrow>
      <div className="card" style={{ padding: 0, marginTop: 8, marginBottom: 18, textAlign: "left" }}>
        {[
          ["Extend Saturday to 3 h",   "Most direct fix"],
          ["Move long to Sunday",       "Enable Sunday for peak"],
          ["Drop goal one tier",        "Sub-3:00 → BQ"],
        ].map(([k, v], i, a) => (
          <div key={i} style={{ padding: "12px 14px", borderBottom: i < a.length - 1 ? "1px solid var(--hairline-2)" : "none", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
            <div>
              <div style={{ fontWeight: 600, fontSize: 13 }}>{k}</div>
              <div style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 2 }}>{v}</div>
            </div>
            <Ic d={I.chevR} size={14} />
          </div>
        ))}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <div className="btn btn-primary" style={{ width: "100%", justifyContent: "center", padding: "12px 16px" }}>
          <Ic d={I.bolt} size={12} /> RETRY GENERATION
        </div>
        <div className="btn btn-ghost" style={{ width: "100%", justifyContent: "center", padding: "10px 16px" }}>
          EDIT INPUTS
        </div>
      </div>

      <div className="mono" style={{ marginTop: 16, fontSize: 9, letterSpacing: "0.16em", color: "var(--fg-4)", textTransform: "uppercase" }}>
        ⓘ NO CHARGE · CACHED PHASES REUSE ON RETRY
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// E14. MOBILE — REFRESH CAP-EXCEEDED MODAL
// ═══════════════════════════════════════════════════════════════════
const MobileRefreshCapped = () => (
  <div className="screen">
    <StatusBar />

    <div style={{ flex: 1, position: "relative", overflow: "hidden" }}>
      {/* Ghost background */}
      <div style={{ position: "absolute", inset: 0, padding: 18, opacity: 0.2, pointerEvents: "none" }}>
        <Eyebrow>Plan refresh</Eyebrow>
        <h1 style={{ fontSize: 22, fontWeight: 700, marginTop: 8 }}>Update your plan.</h1>
        <div className="card" style={{ marginTop: 16, padding: 14, height: 80 }} />
        <div className="card" style={{ marginTop: 10, padding: 14, height: 60 }} />
      </div>
      <div style={{ position: "absolute", inset: 0, background: "color-mix(in oklab, var(--ink) 70%, transparent)" }} />

      {/* Sheet */}
      <div style={{
        position: "absolute", left: 0, right: 0, bottom: 0,
        background: "var(--bg-2)",
        borderTop: "1px solid var(--hairline)",
        borderRadius: "16px 16px 0 0",
        padding: "10px 0 28px",
      }}>
        <div style={{ width: 40, height: 4, background: "var(--hairline)", borderRadius: 2, margin: "0 auto 14px" }} />
        <div style={{ padding: "0 22px 14px", borderBottom: "1px solid var(--hairline-2)" }}>
          <Eyebrow>● FREQUENCY CAP</Eyebrow>
          <div style={{ fontSize: 20, fontWeight: 700, letterSpacing: "-0.015em", marginTop: 6 }}>Refresh again?</div>
        </div>

        <div style={{ padding: "16px 22px" }}>
          <div style={{ fontSize: 14, color: "var(--fg-2)", lineHeight: 1.55 }}>
            You've refreshed <b>4 times</b> in the last 24 hours. Each refresh re-runs the cascade and costs compute. Continue if the signal is worth it.
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 0, marginTop: 14, padding: "12px 0", borderTop: "1px solid var(--hairline-2)", borderBottom: "1px solid var(--hairline-2)" }}>
            {[["T2 TODAY","4"], ["SOFT CAP","3/24h"], ["LAST","32m ago"]].map(([k, v], i) => (
              <div key={i} style={{ borderRight: i < 2 ? "1px solid var(--hairline-2)" : "none", padding: "0 6px", textAlign: "center" }}>
                <div className="eyebrow" style={{ fontSize: 8 }}>{k}</div>
                <div className="num" style={{ fontSize: 15, fontWeight: 700, marginTop: 3 }}>{v}</div>
              </div>
            ))}
          </div>

          <div className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--fg-3)", marginTop: 14, textTransform: "uppercase" }}>
            ⓘ CAP RESETS AT MIDNIGHT LOCAL · VERSIONS ARE FREE TO REVERT
          </div>

          <div style={{ display: "flex", gap: 8, marginTop: 18 }}>
            <div className="btn btn-ghost" style={{ flex: 1, justifyContent: "center", padding: "12px 16px" }}>CANCEL</div>
            <div className="btn btn-primary" style={{ flex: 2, justifyContent: "center", padding: "12px 16px" }}>
              <Ic d={I.bolt} size={11} /> REFRESH ANYWAY
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// E15. OFFLINE / NETWORK DROP (desktop + mobile)
// ═══════════════════════════════════════════════════════════════════
const ScreenOffline = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="home" />
      <div className="page">
        {/* Top banner */}
        <div style={{
          padding: "12px 28px",
          borderBottom: "1px solid color-mix(in oklab, var(--warn) 40%, transparent)",
          background: "color-mix(in oklab, var(--warn) 10%, transparent)",
          display: "flex", alignItems: "center", gap: 14,
        }}>
          <div style={{ width: 24, height: 24, borderRadius: "50%", background: "color-mix(in oklab, var(--warn) 25%, transparent)", color: "var(--warn)", display: "grid", placeItems: "center", flexShrink: 0 }}>
            <Ic d={I.x} size={12} sw={2.5} />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13, fontWeight: 600 }}>You're offline · retrying every 30s</div>
            <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em", marginTop: 2 }}>LAST SYNC 2 MIN 14 SEC AGO · 3 LOCAL CHANGES WILL UPLOAD WHEN CONNECTED</div>
          </div>
          <div className="btn btn-ghost btn-sm">RETRY NOW</div>
        </div>

        <div className="page-body" style={{ display: "grid", placeItems: "center", padding: "32px 28px" }}>
          <div style={{ maxWidth: 540, textAlign: "center" }}>
            <Eyebrow>● OFFLINE · CACHED VIEW</Eyebrow>
            <h1 style={{ fontSize: 36, fontWeight: 700, letterSpacing: "-0.02em", margin: "10px 0 10px" }}>
              You can still work.
            </h1>
            <div style={{ color: "var(--fg-3)", fontSize: 14, lineHeight: 1.55, maxWidth: 460, margin: "0 auto 22px" }}>
              We've cached your active plan, today's workout, and the last 30 days of data. Log sessions, mark complete, check intervals — everything queues locally and syncs when you reconnect.
            </div>

            <div className="card" style={{ padding: 0, textAlign: "left", marginBottom: 14 }}>
              <div style={{ padding: "14px 18px", borderBottom: "1px solid var(--hairline-2)" }}>
                <Eyebrow>What works offline</Eyebrow>
              </div>
              {[
                ["✓ View today's workout",       "Full structure, intervals, coaching notes"],
                ["✓ Log strength sessions",     "Sets queue locally, sync later"],
                ["✓ Log cardio (manual)",       "Or import .FIT when back online"],
                ["✓ Self-report wellness",      "Sleep, energy, soreness, mood"],
                ["✗ Generate or refresh plan",  "Requires the cascade — back online first"],
                ["✗ Provider sync",             "Strava/Wahoo pull resumes on reconnect"],
              ].map(([k, v], i, a) => (
                <div key={i} style={{ padding: "12px 18px", borderBottom: i < a.length - 1 ? "1px solid var(--hairline-2)" : "none", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <div style={{ fontWeight: 500, fontSize: 13, color: k.startsWith("✓") ? "var(--fg)" : "var(--fg-3)" }}>{k}</div>
                    <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em", marginTop: 2, textTransform: "uppercase" }}>{v}</div>
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

const MobileOffline = () => (
  <div className="screen">
    <StatusBar />
    <AppBar title="Today" left={<Ic d={I.menu} size={22} />} right={null} />

    <div style={{
      padding: "10px 16px",
      borderBottom: "1px solid color-mix(in oklab, var(--warn) 40%, transparent)",
      background: "color-mix(in oklab, var(--warn) 10%, transparent)",
      display: "flex", alignItems: "center", gap: 10,
    }}>
      <div style={{ width: 20, height: 20, borderRadius: "50%", background: "color-mix(in oklab, var(--warn) 25%, transparent)", color: "var(--warn)", display: "grid", placeItems: "center", flexShrink: 0 }}>
        <Ic d={I.x} size={10} sw={2.5} />
      </div>
      <div style={{ flex: 1, fontSize: 12, fontWeight: 600 }}>Offline · retrying every 30s</div>
      <span className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.14em" }}>2M 14S</span>
    </div>

    <div style={{ flex: 1, overflow: "auto", padding: "20px 18px" }}>
      <div style={{ textAlign: "center", marginBottom: 22 }}>
        <Eyebrow>● CACHED VIEW</Eyebrow>
        <h1 style={{ fontSize: 24, fontWeight: 700, letterSpacing: "-0.02em", margin: "10px 0 8px" }}>You can still work.</h1>
        <div style={{ color: "var(--fg-3)", fontSize: 13, lineHeight: 1.5 }}>
          Active plan, today's workout, and 30 days of data are cached. Sessions queue locally, sync on reconnect.
        </div>
      </div>

      <Eyebrow>What works offline</Eyebrow>
      <div className="card" style={{ padding: 0, marginTop: 8 }}>
        {[
          ["✓ Today's workout",     "Full structure"],
          ["✓ Log strength",         "Sets queue locally"],
          ["✓ Log cardio (manual)", ".FIT later"],
          ["✓ Self-report",          "Sleep · energy · mood"],
          ["✗ Generate or refresh", "Needs network"],
          ["✗ Provider sync",        "Resumes on reconnect"],
        ].map(([k, v], i, a) => (
          <div key={i} style={{ padding: "10px 14px", borderBottom: i < a.length - 1 ? "1px solid var(--hairline-2)" : "none", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <div style={{ fontWeight: 500, fontSize: 12, color: k.startsWith("✓") ? "var(--fg)" : "var(--fg-3)" }}>{k}</div>
              <div className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.14em", marginTop: 2 }}>{v.toUpperCase()}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="btn btn-ghost" style={{ marginTop: 18, width: "100%", justifyContent: "center", padding: "12px 16px" }}>
        RETRY CONNECTION
      </div>
    </div>

    <TabBar active="home" />
  </div>
);

Object.assign(window, {
  ScreenPlanListEmpty, MobilePlanListEmpty,
  ScreenLocationsEmpty, MobileLocationsEmpty,
  ScreenWorkoutEmpty, MobileWorkoutEmpty,
  MobilePlanGenFailed, MobileRefreshCapped,
  ScreenOffline, MobileOffline,
});
