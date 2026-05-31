/* AIDSTATION redesign — Desktop screens (part 4)
   Plan generation · Plan generation progress · Plan compare · Plan import
   · Coaching review · FIT debug · Admin dashboard */

// ═══════════════════════════════════════════════════════════════════
// 13. PLAN GENERATION — Start form
// ═══════════════════════════════════════════════════════════════════
const ScreenPlanGenerate = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="plan" />
      <div className="page">
        <TopBar crumbs={["Plan", "Generate"]} />
        <div className="page-body">
          <div style={{ maxWidth: 920 }}>
            <Eyebrow>Plan generate · Pattern A synthesis</Eyebrow>
            <h1 className="page-title" style={{ marginTop: 8 }}>Build me a plan.</h1>
            <div className="page-sub">Runs the full coaching cascade against your profile + current state + target race. Typically 3–4 phases — Base → Build → Peak → Taper — with seam reviews between each.</div>

            {/* Pre-flight checklist */}
            <div style={{ marginTop: 24 }}>
              <Eyebrow>Pre-flight · inputs to the cascade</Eyebrow>
              <div className="card" style={{ marginTop: 12, padding: 0 }}>
                {[
                  { label: "Connected providers",  status: "ok",   v: "Strava · Wahoo",            sub: "Activity, sleep, body comp pulling on schedule" },
                  { label: "Performance baselines", status: "ok",  v: "6 of 6 set",                sub: "Threshold pace, HR, FTP, VO2, RHR, body weight" },
                  { label: "Schedule windows",     status: "ok",   v: "6 days · 8.5h / wk",        sub: "Mon–Sat enabled, Sun rest, one double on Thursday" },
                  { label: "Skills",               status: "ok",   v: "5 of 12 checked",           sub: "Road run, road bike, strength, trail, power meter" },
                  { label: "Locations",            status: "ok",   v: "3 saved",                   sub: "Home garage (primary), Equinox Cap Hill, Rock Creek" },
                  { label: "Target race",          status: "ok",   v: "Boston Marathon · Apr 20",  sub: "22 weeks 6 days out · Sub-3:00 goal · 26.2 mi / 248m" },
                  { label: "Recent training",      status: "warn", v: "Last 12 weeks present",     sub: "Some gaps before Mar 14 — we'll treat as untracked" },
                ].map((row, i, a) => (
                  <div key={i} style={{ display: "grid", gridTemplateColumns: "200px 1fr auto", alignItems: "center", padding: "14px 18px", borderBottom: i < a.length - 1 ? "1px solid var(--hairline-2)" : "none" }}>
                    <div className="eyebrow" style={{ fontSize: 9 }}>{row.label}</div>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: 14 }}>{row.v}</div>
                      <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 2 }}>{row.sub}</div>
                    </div>
                    <Pill tone={row.status === "ok" ? "good" : "warn"}>{row.status === "ok" ? "✓ READY" : "⚠ PARTIAL"}</Pill>
                  </div>
                ))}
              </div>
            </div>

            {/* Start date */}
            <div style={{ marginTop: 24, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
              <div className="card" style={{ padding: 18 }}>
                <Eyebrow>Plan start date</Eyebrow>
                <div className="num" style={{ fontSize: 28, fontWeight: 700, marginTop: 8 }}>May 27, 2026</div>
                <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", marginTop: 6, letterSpacing: "0.14em", textTransform: "uppercase" }}>TODAY · OR PICK A FUTURE DATE</div>
              </div>
              <div className="card" style={{ padding: 18, background: "color-mix(in oklab, var(--accent) 6%, var(--bg-2))" }}>
                <Eyebrow accent>● ANCHOR · TARGET RACE</Eyebrow>
                <div style={{ fontSize: 18, fontWeight: 700, marginTop: 8 }}>Boston Marathon 2026</div>
                <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", marginTop: 6, letterSpacing: "0.14em", textTransform: "uppercase" }}>APR 20, 2026 · 22W 6D OUT</div>
              </div>
            </div>

            {/* Expectations + button */}
            <div style={{ marginTop: 24 }}>
              <Eyebrow>What you'll get</Eyebrow>
              <div className="card" style={{ marginTop: 12, padding: 18 }}>
                <div style={{ display: "flex", height: 36, borderRadius: 4, overflow: "hidden", marginBottom: 12 }}>
                  <div style={{ flex: 4, background: "var(--ink-3)", display: "grid", placeItems: "center", fontFamily: "var(--mono)", fontSize: 10, letterSpacing: "0.18em", color: "var(--fg-2)" }}>BASE · 4W</div>
                  <div style={{ flex: 8, background: "color-mix(in oklab, var(--accent) 60%, var(--ink-3))", display: "grid", placeItems: "center", fontFamily: "var(--mono)", fontSize: 10, letterSpacing: "0.18em", color: "var(--ink)" }}>BUILD · 8W</div>
                  <div style={{ flex: 6, background: "var(--accent)", display: "grid", placeItems: "center", fontFamily: "var(--mono)", fontSize: 10, letterSpacing: "0.18em", color: "var(--ink)", fontWeight: 600 }}>PEAK · 6W</div>
                  <div style={{ flex: 4, background: "var(--ink-3)", display: "grid", placeItems: "center", fontFamily: "var(--mono)", fontSize: 10, letterSpacing: "0.18em", color: "var(--fg-2)" }}>TAPER · 4W</div>
                </div>
                <div style={{ fontSize: 13, color: "var(--fg-2)", lineHeight: 1.5 }}>
                  ~22 weeks · 132 sessions · 6 per week (one double). Seam reviews at week 4, 12, 18.
                  Each session is shaped by your locations + skills + injury constraints. Editable per-day after generation.
                </div>
              </div>
            </div>

            <div style={{ marginTop: 24, display: "flex", gap: 10 }}>
              <div className="btn btn-primary" style={{ padding: "14px 22px" }}><Ic d={I.bolt} size={13} /> Generate plan</div>
              <div className="btn btn-ghost" style={{ padding: "14px 22px" }}><Ic d={I.upload} size={13} /> Import plan from JSON</div>
              <div className="btn btn-text" style={{ color: "var(--fg-3)", padding: "14px 0", marginLeft: "auto" }}>Cancel</div>
            </div>

            <div className="mono" style={{ fontSize: 10, color: "var(--fg-4)", marginTop: 16, letterSpacing: "0.14em", textTransform: "uppercase" }}>
              ⓘ GENERATION TYPICALLY TAKES 2–5 MIN · WE'LL SHOW LIVE PROGRESS
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// 14. PLAN GENERATION — Progress (cup-pour, monotonic, brand-led)
// ═══════════════════════════════════════════════════════════════════
// Why this design: source template cycles MESSAGES every 6s on the
// client because the server can't report sub-step progress, so the
// progress feels deceptive (Finishing up → Evaluating…). This
// redesign drops step-by-step timing entirely and goes graphic: the
// brand cup fills with the current generation step, drains, the next
// step pours in. Calm, evocative, never lies.
//
// 25 steps × 12s = 300s loop = 5 min — past the typical envelope
// before any repeat. If generation outruns that, the long-run
// variant takes over with steady (non-cycling) messaging.

const PLAN_STEPS = [
  "Reading your training history",
  "Mapping your goal viability",
  "Sketching the phase shape",
  "Choosing your periodization",
  "Sequencing the build phase",
  "Placing key sessions",
  "Balancing weekly load",
  "Distributing intensity",
  "Slotting long sessions",
  "Honoring your schedule",
  "Filtering for skills",
  "Adjusting for injuries",
  "Calibrating recovery",
  "Tuning week-to-week ramp",
  "Designing the taper",
  "Writing session details",
  "Adding fueling notes",
  "Cross-checking constraints",
  "Pacing the peak block",
  "Routing through your locations",
  "Anchoring to race day",
  "Drafting the first cut",
  "Polishing transitions",
  "Reviewing the whole plan",
  "Finalizing",
];

// Cup outline only — no fill animation. The letters are the contents,
// they tumble in individually and spill out under their own animation.
const CupOutline = ({ size = 260 }) => (
  <svg width={size} height={size} viewBox="0 0 300 300" style={{ overflow: "visible", display: "block" }} aria-hidden="true">
    {/* Inside shadow */}
    <path d="M78 90 L222 90 L201 252 Q 150 277, 99 252 Z"
      fill="color-mix(in oklab, var(--ink) 60%, transparent)" />
    {/* Cup outline */}
    <path d="M78 90 L222 90 L201 252 Q 150 277, 99 252 Z"
      fill="none" stroke="var(--paper)" strokeWidth="6" strokeLinejoin="round" />
    {/* Top rim */}
    <line x1="78" y1="90" x2="222" y2="90" stroke="var(--paper)" strokeWidth="6" strokeLinecap="round" />
  </svg>
);

// Cup interior slots — bottom-up tetris-style stack. Coordinates are in
// screen px relative to the 260×260 cup container's top-left. The cup
// outline narrows toward the bottom; slot widths reflect that so letters
// never cross the cup edge.
const CUP_LETTER_SLOTS = (() => {
  const rows = [
    { y: 202, xs: [-32, -16, 0, 16, 32] },            // bottom row, narrowest
    { y: 186, xs: [-35, -18, 0, 18, 35] },
    { y: 170, xs: [-38, -23, -8, 8, 23, 38] },
    { y: 154, xs: [-40, -24, -8, 8, 24, 40] },
    { y: 138, xs: [-44, -29, -14, 0, 14, 29, 44] },
    { y: 122, xs: [-44, -29, -14, 0, 14, 29, 44] },   // top row, near rim
  ];
  const out = [];
  rows.forEach(({ y, xs }) => xs.forEach((x) => out.push({ x, y })));
  return out;
})();

// Build a deterministic, per-letter render plan across all 25 steps.
// Each letter knows two horizontal positions: --px (its readable
// place in the phrase preview above the cup) and --x (its scattered
// landing slot inside the cup). Spaces are skipped from the render
// but their indices still affect --px so words read with proper gaps.
const PLAN_LETTER_RENDER = (() => {
  const out = [];
  const LETTER_PITCH = 12; // px between adjacent characters in the phrase
  PLAN_STEPS.forEach((step, si) => {
    const chars = step.toUpperCase().split("");
    const centerCi = (chars.length - 1) / 2;
    let slotIdx = 0;
    chars.forEach((ch, ci) => {
      if (ch === " ") return; // skip spaces — gaps emerge from --px math
      if (slotIdx >= CUP_LETTER_SLOTS.length) return;
      const slot = CUP_LETTER_SLOTS[slotIdx];
      const seed = (si * 11 + ci * 13 + ch.charCodeAt(0)) % 23;
      const xJitter = ((seed % 7) - 3) * 1.2;
      const yJitter = ((seed % 5) - 2) * 1.5;
      const rJitter = ((seed % 13) - 6) * 5;
      out.push({
        ch,
        px: (ci - centerCi) * LETTER_PITCH, // phrase preview position
        x: slot.x + xJitter,                // scattered settle position
        y: slot.y + yJitter,
        r: rJitter,
        // ~25 ms stagger per character produces a left-to-right
        // "typewriter reveal → wave-scatter" rather than a sync drop.
        delay: si * 12 + ci * 0.025,
      });
      slotIdx++;
    });
  });
  return out;
})();

const ScreenPlanProgress = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="plan" />
      <div className="page">
        <TopBar crumbs={["Plan", "Generating"]} />
        <div className="page-body" style={{ display: "grid", placeItems: "center", padding: "32px 28px" }}>
          <div style={{ maxWidth: 680, width: "100%", textAlign: "center" }}>

            <Eyebrow accent>● BUILDING YOUR PLAN</Eyebrow>
            <h1 style={{ fontSize: 44, fontWeight: 800, letterSpacing: "-0.025em", lineHeight: 1.05, margin: "12px 0 12px" }}>
              Pouring you a plan.
            </h1>
            <div style={{ color: "var(--fg-3)", fontSize: 15, lineHeight: 1.55, maxWidth: 480, margin: "0 auto 24px" }}>
              Takes 3–5 minutes. We're training your plan as hard as it'll train you — every session shaped by your full profile.
            </div>

            {/* The cup + tumbling letters. Letters live INSIDE the
                rotating container so they ride with the cup when it
                tips, and their local upward translate during spill
                exits through the mouth in world space. */}
            <div style={{ position: "relative", width: 360, height: 380, margin: "8px auto 0" }}>
              <div style={{
                position: "absolute",
                left: "50%",
                top: 90,
                width: 260,
                height: 260,
                transformOrigin: "75% 90%",
                animation: "cupTipping 12s ease-in-out infinite",
                willChange: "transform",
              }}>
                <CupOutline size={260} />

                {/* Letters — children of the cup container */}
                {PLAN_LETTER_RENDER.map((l, i) => (
                  <div key={i} style={{
                    position: "absolute",
                    left: "50%",
                    top: 0,
                    width: 14,
                    height: 18,
                    textAlign: "center",
                    fontFamily: "var(--mono)",
                    fontSize: 17,
                    fontWeight: 800,
                    lineHeight: 1,
                    color: "var(--accent)",
                    opacity: 0,
                    "--px": `${l.px}px`,
                    "--x": `${l.x}px`,
                    "--y": `${l.y}px`,
                    "--r": `${l.r}deg`,
                    animation: `letterTumble 300s linear ${l.delay}s infinite`,
                    pointerEvents: "none",
                    willChange: "transform, opacity",
                  }}>
                    {l.ch}
                  </div>
                ))}
              </div>
            </div>

            <div style={{ marginTop: 4, fontSize: 13, color: "var(--fg-3)" }}>
              You can close this tab — we'll email you when it's ready.
            </div>
            <div className="mono" style={{ marginTop: 6, fontSize: 10, letterSpacing: "0.18em", color: "var(--fg-4)" }}>
              1M 32S ELAPSED · TYPICAL 3–5 MIN
            </div>

            <div style={{ marginTop: 22 }}>
              <div className="btn btn-text" style={{ color: "var(--fg-3)", fontSize: 10 }}>CANCEL GENERATION</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

// Long-run variant — same cup, slower tipping, calmer copy. Just a
// few letters tumbling to keep the page alive without lying about
// progress.
const LONG_RUN_LETTERS = "STILLWORKING".split("").map((ch, i) => ({
  ch,
  x: ((i % 5) - 2) * 18,
  y: 140 + Math.floor(i / 5) * 18,
  r: ((i % 7) - 3) * 6,
  delay: i * 4,
}));

const ScreenPlanProgressLong = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="plan" />
      <div className="page">
        <TopBar crumbs={["Plan", "Generating"]} />
        <div className="page-body" style={{ display: "grid", placeItems: "center", padding: "32px 28px" }}>
          <div style={{ maxWidth: 640, width: "100%", textAlign: "center" }}>

            <Eyebrow>● STILL POURING · TAKING LONGER THAN USUAL</Eyebrow>
            <h1 style={{ fontSize: 44, fontWeight: 800, letterSpacing: "-0.025em", lineHeight: 1.05, margin: "12px 0 12px" }}>
              Patience. <span style={{ color: "var(--fg-3)", fontWeight: 300 }}>Almost there.</span>
            </h1>
            <div style={{ color: "var(--fg-3)", fontSize: 15, lineHeight: 1.55, maxWidth: 500, margin: "0 auto 24px" }}>
              You're past the typical 5-minute envelope. Sometimes synthesis takes longer when the race date is far out, the schedule is complex, or the engine is under load. No action needed — we'll finish.
            </div>

            <div style={{ position: "relative", width: 360, height: 380, margin: "0 auto" }}>
              <div style={{
                position: "absolute",
                left: "50%",
                top: 60,
                width: 240,
                height: 240,
                transformOrigin: "75% 90%",
                animation: "cupTipping 18s ease-in-out infinite",
              }}>
                <CupOutline size={240} />
                {LONG_RUN_LETTERS.map((l, i) => (
                  <div key={i} style={{
                    position: "absolute",
                    left: "50%",
                    top: 0,
                    width: 14,
                    height: 18,
                    textAlign: "center",
                    fontFamily: "var(--mono)",
                    fontSize: 17,
                    fontWeight: 800,
                    color: "var(--warn)",
                    lineHeight: 1,
                    opacity: 0,
                    "--x": `${l.x}px`,
                    "--y": `${l.y}px`,
                    "--r": `${l.r}deg`,
                    animation: `letterTumble 72s linear ${l.delay}s infinite`,
                    pointerEvents: "none",
                  }}>
                    {l.ch}
                  </div>
                ))}
              </div>
            </div>

            <div className="card" style={{ marginTop: 16, padding: 18, textAlign: "left", display: "flex", gap: 16, alignItems: "center" }}>
              <Ic d={I.bell} size={20} />
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: 14 }}>Get notified when it's done</div>
                <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 2 }}>Close this tab safely — we'll email + push when your plan is ready.</div>
              </div>
              <div className="btn btn-primary btn-sm">EMAIL + PUSH</div>
            </div>

            <div className="mono" style={{ marginTop: 16, fontSize: 10, letterSpacing: "0.18em", color: "var(--fg-4)" }}>
              7M 04S ELAPSED · ENGINE STILL RUNNING
            </div>

            <div style={{ marginTop: 14 }}>
              <div className="btn btn-text" style={{ color: "var(--bad)", fontSize: 10 }}>CANCEL GENERATION</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// 15. PLAN COMPARE — After refresh, side-by-side
// ═══════════════════════════════════════════════════════════════════
const ScreenPlanCompare = () => {
  const days = [
    { d: "TUE 27", before: { name: "Threshold intervals", sport: "Run", dur: "68'", z: "Z4" }, after: { name: "Easy aerobic", sport: "Run", dur: "55'", z: "Z2", note: "Move threshold → Sat" }, changed: true },
    { d: "WED 28", before: { name: "Easy aerobic", sport: "Run", dur: "52'", z: "Z2" }, after: { name: "Easy aerobic", sport: "Run", dur: "52'", z: "Z2" } },
    { d: "THU 29", before: { name: "Lower strength", sport: "Strength", dur: "45'" }, after: { name: "Upper strength", sport: "Strength", dur: "45'", note: "Avoid hamstring" }, changed: true },
    { d: "FRI 30", before: { name: "VO2 short", sport: "Run", dur: "55'", z: "Z5" }, after: { name: "Easy aerobic", sport: "Run", dur: "40'", z: "Z2", note: "Defer VO2" }, changed: true },
    { d: "SAT 31", before: { name: "Long run · fueling", sport: "Run", dur: "2h 10m", z: "Z2/Z3" }, after: { name: "Long run + threshold", sport: "Run", dur: "2h 00m", z: "Z2/Z4", note: "Threshold moved in" }, changed: true },
    { d: "SUN 01", before: { name: "Recovery spin", sport: "Bike", dur: "60'" }, after: { name: "Recovery spin", sport: "Bike", dur: "60'" } },
  ];
  return (
    <div className="screen">
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <Sidebar active="plan" />
        <div className="page">
          <TopBar crumbs={["Plan", "Compare", "v12 → v13"]} actions={
            <>
              <div className="btn btn-ghost"><Ic d={I.x} size={12} /> Discard new version</div>
              <div className="btn btn-primary"><Ic d={I.check} size={12} sw={2.2} /> Accept · activate v13</div>
            </>
          } />
          <div className="page-body">
            <div style={{ marginBottom: 22 }}>
              <Eyebrow>Plan refresh · v12 vs v13</Eyebrow>
              <h1 className="page-title" style={{ marginTop: 8 }}>Diff of your plan.</h1>
              <div className="page-sub">7-day refresh. Reason given: <em>"Tweaked left hamstring on long run; travel to Boston Wed–Fri."</em> Hit Accept to make v13 active, or Discard to keep v12.</div>
            </div>

            {/* Summary */}
            <div className="row" style={{ marginBottom: 18 }}>
              {[
                ["Sessions changed",     "4 / 6"],
                ["Volume (this week)",   "−18 min"],
                ["Intensity",            "Z4 deferred · −1 day"],
                ["Phase position",       "Build · WK 8 (same)"],
              ].map(([k, v], i) => (
                <div key={i} className="stat-card col" style={{ padding: 16 }}>
                  <div className="k">{k}</div>
                  <div className="v num" style={{ fontSize: 20 }}>{v}</div>
                </div>
              ))}
            </div>

            {/* Diff table */}
            <div className="card" style={{ padding: 0 }}>
              <div style={{ display: "grid", gridTemplateColumns: "100px 1fr 1fr", padding: "12px 0", borderBottom: "1px solid var(--hairline)", background: "var(--bg)" }}>
                <div className="mono" style={{ padding: "0 18px", fontSize: 9, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--fg-3)" }}>Day</div>
                <div className="mono" style={{ padding: "0 18px", fontSize: 9, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--fg-3)" }}>Before · v12</div>
                <div className="mono" style={{ padding: "0 18px", fontSize: 9, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--accent)" }}>After · v13</div>
              </div>
              {days.map((day, i) => (
                <div key={i} style={{
                  display: "grid", gridTemplateColumns: "100px 1fr 1fr",
                  borderBottom: i < days.length - 1 ? "1px solid var(--hairline-2)" : "none",
                  background: day.changed ? "color-mix(in oklab, var(--accent) 4%, transparent)" : "transparent",
                }}>
                  <div style={{ padding: "16px 18px", display: "flex", alignItems: "center" }}>
                    <span className="mono" style={{ fontSize: 11, letterSpacing: "0.16em", color: day.changed ? "var(--accent)" : "var(--fg-3)", fontWeight: day.changed ? 600 : 400 }}>{day.d}</span>
                  </div>
                  <div style={{ padding: "12px 18px", borderRight: "1px solid var(--hairline-2)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                      <span style={{ fontWeight: 600, color: day.changed ? "var(--fg-3)" : "var(--fg)", textDecoration: day.changed ? "line-through" : "none" }}>{day.before.name}</span>
                      <span className="num" style={{ fontSize: 12, color: "var(--fg-3)" }}>{day.before.dur}</span>
                    </div>
                    <div className="mono" style={{ fontSize: 10, letterSpacing: "0.14em", color: "var(--fg-3)", marginTop: 4, textTransform: "uppercase" }}>{day.before.sport} {day.before.z && `· ${day.before.z}`}</div>
                  </div>
                  <div style={{ padding: "12px 18px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                      <span style={{ fontWeight: 600 }}>{day.after.name}</span>
                      <span className="num" style={{ fontSize: 12, color: "var(--fg-3)" }}>{day.after.dur}</span>
                    </div>
                    <div className="mono" style={{ fontSize: 10, letterSpacing: "0.14em", color: "var(--fg-3)", marginTop: 4, textTransform: "uppercase" }}>{day.after.sport} {day.after.z && `· ${day.after.z}`}</div>
                    {day.after.note && <Pill tone="accent" style={{ marginTop: 6 }}>● {day.after.note.toUpperCase()}</Pill>}
                  </div>
                </div>
              ))}
            </div>

            <div className="card-flush" style={{ marginTop: 18, padding: 16 }}>
              <Eyebrow>Engine notes</Eyebrow>
              <div style={{ fontSize: 13, color: "var(--fg-2)", marginTop: 8, lineHeight: 1.55 }}>
                Hamstring strain (severity 2) flags 5–7 days of Z2 only and no posterior-chain strength. Threshold + VO2 deferred, swapped strength split to upper. To preserve weekly stimulus, threshold moved into Saturday's long run as a 3×8' fast-finish. Phase position unchanged — Build week 8 still tracks.
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════
// 16. PLAN IMPORT — Paste JSON
// ═══════════════════════════════════════════════════════════════════
const ScreenPlanImport = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="plan" />
      <div className="page">
        <TopBar crumbs={["Plan", "Import"]} actions={
          <>
            <div className="btn btn-ghost">Cancel</div>
            <div className="btn btn-primary"><Ic d={I.upload} size={12} /> Import plan</div>
          </>
        } />
        <div className="page-body">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 380px", gap: 24 }}>
            <div>
              <Eyebrow>Plan · external import</Eyebrow>
              <h1 className="page-title" style={{ marginTop: 8 }}>Import a plan.</h1>
              <div className="page-sub">Paste a JSON plan (Claude-generated, or built by any tool that follows the schema on the right). Imports become a new plan version; existing plans stay intact.</div>

              <div style={{ marginTop: 24 }}>
                <Eyebrow>Plan JSON</Eyebrow>
                <div className="card-flush" style={{ marginTop: 10, padding: "18px 20px", fontFamily: "var(--mono)", fontSize: 12, lineHeight: 1.55, color: "var(--fg-2)", minHeight: 380, overflow: "auto", whiteSpace: "pre" }}>
{`{
  "name": "4-Week Peak Cycling Block",
  "description": "Build threshold power ahead of target event",
  "sport_focus": "cycling",
  "start_date": "2026-04-14",
  "end_date": "2026-05-11",
  "workouts": [
    {
      "date": "2026-04-14",
      "sport_type": "cycling",
      "workout_name": "5x8min Threshold",
      "description": "WU 15min, 5x8min at FTP (3min rest), CD 10min",
      "target_duration_min": 90,
      "target_distance_mi": null,
      "intensity": "threshold",
      "garmin_workout_json": {}
    }
  ]
}`}
                </div>
                <div className="mono" style={{ fontSize: 10, color: "var(--fg-4)", marginTop: 6, letterSpacing: "0.14em", textTransform: "uppercase" }}>
                  847 / 100KB · VALID JSON · 28 WORKOUTS DETECTED
                </div>
              </div>

              <div style={{ marginTop: 16, padding: "12px 14px", background: "color-mix(in oklab, var(--good) 10%, transparent)", border: "1px solid color-mix(in oklab, var(--good) 30%, transparent)", borderRadius: 4 }}>
                <Pill tone="good">✓ SCHEMA VALID</Pill>
                <span style={{ marginLeft: 10, fontSize: 13, color: "var(--fg-2)" }}>28 workouts across 4 weeks · all required fields present · 0 warnings.</span>
              </div>
            </div>

            {/* Right rail: schema reference */}
            <div className="stack">
              <div className="card" style={{ padding: 18 }}>
                <Eyebrow>Schema · top-level</Eyebrow>
                <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 8 }}>
                  {[
                    ["name",          "string · required"],
                    ["description",   "string"],
                    ["sport_focus",   "running | cycling | …"],
                    ["start_date",    "YYYY-MM-DD · required"],
                    ["end_date",      "YYYY-MM-DD · required"],
                    ["workouts",      "array · required"],
                  ].map(([k, t], i) => (
                    <div key={i} style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
                      <span className="mono">{k}</span>
                      <span className="mono" style={{ color: "var(--fg-3)" }}>{t}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="card" style={{ padding: 18 }}>
                <Eyebrow>Workout entry</Eyebrow>
                <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 8 }}>
                  {[
                    ["date",                "YYYY-MM-DD"],
                    ["sport_type",          "running, cycling, …"],
                    ["workout_name",        "string"],
                    ["description",         "string"],
                    ["target_duration_min", "int | null"],
                    ["target_distance_mi",  "float | null"],
                    ["intensity",           "easy | moderate | …"],
                    ["garmin_workout_json", "object"],
                  ].map(([k, t], i) => (
                    <div key={i} style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
                      <span className="mono">{k}</span>
                      <span className="mono" style={{ color: "var(--fg-3)" }}>{t}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="card-flush" style={{ padding: 14 }}>
                <Eyebrow>FIT sport IDs · standard</Eyebrow>
                <div style={{ marginTop: 8, fontFamily: "var(--mono)", fontSize: 11, color: "var(--fg-3)", lineHeight: 1.7 }}>
                  running · 1<br />cycling · 2<br />strength_training · 4<br />pool_swimming · 5<br />walking · 11<br />hiking · 17
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
// 17. COACHING REVIEW — Tier 1/2/3 with context cards
// ═══════════════════════════════════════════════════════════════════
const ScreenCoachingReview = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="plan" />
      <div className="page">
        <TopBar crumbs={["Plan", "AI review"]} actions={
          <div className="btn btn-primary"><Ic d={I.bolt} size={12} /> Run review</div>
        } />
        <div className="page-body">
          <div style={{ marginBottom: 22 }}>
            <Eyebrow>AI plan review · three tiers</Eyebrow>
            <h1 className="page-title" style={{ marginTop: 8 }}>Coach me through it.</h1>
            <div className="page-sub">Different scopes of review for different signals. Tier 1 is a session-level patch; Tier 3 generates a brand-new 4-week block.</div>
          </div>

          {/* Tier status cards */}
          <div className="row" style={{ marginBottom: 22 }}>
            {[
              { tier: "Tier 1", scope: "Session", status: "due", desc: "Adjust the next 1–2 sessions based on RPE, fatigue, or a miss.", meta: "3 sessions since last review", color: "var(--warn)" },
              { tier: "Tier 2", scope: "Weekly",  status: "due", desc: "Patch the next 1–2 weeks. Reads planned vs actual delta.", meta: "9 days since weekly review", color: "var(--warn)" },
              { tier: "Tier 3", scope: "Block",   status: "ok",  desc: "Generate a brand-new 4-week block starting after the current plan ends.", meta: "32 scheduled sessions remaining", color: "var(--good)" },
            ].map((t, i) => (
              <div key={i} className="card col" style={{ padding: 18, border: "1px solid " + (t.status === "due" ? "color-mix(in oklab, " + t.color + " 50%, transparent)" : "var(--hairline-2)") }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <Eyebrow>{t.tier} · {t.scope}</Eyebrow>
                  {t.status === "due" ? <Pill tone="warn">! DUE</Pill> : <Pill tone="good">✓ OK</Pill>}
                </div>
                <div style={{ fontSize: 13, color: "var(--fg-2)", marginTop: 10, lineHeight: 1.45, minHeight: 56 }}>{t.desc}</div>
                <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em", marginTop: 12, textTransform: "uppercase" }}>{t.meta}</div>
              </div>
            ))}
          </div>

          {/* Form */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 360px", gap: 24 }}>
            <div>
              <div className="card" style={{ padding: 18, marginBottom: 14 }}>
                <Eyebrow>Review tier</Eyebrow>
                <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                  {[
                    ["Tier 1 · Session",  false],
                    ["Tier 2 · Weekly",   true],
                    ["Tier 3 · New block", false],
                  ].map(([l, active], i) => (
                    <div key={i} style={{ flex: 1, padding: "14px 16px", textAlign: "center", borderRadius: 4, border: "1px solid " + (active ? "var(--accent)" : "var(--hairline)"), background: active ? "color-mix(in oklab, var(--accent) 10%, transparent)" : "transparent", fontWeight: 500, fontSize: 13 }}>{l}</div>
                  ))}
                </div>
                <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", marginTop: 12, letterSpacing: "0.14em", textTransform: "uppercase", lineHeight: 1.5 }}>
                  ⓘ TIER 2 · READS 90 DAYS OF HISTORY + PLANNED-VS-ACTUAL DELTA · PATCHES NEXT 1–2 WEEKS · INCLUDES CLOTHING RECOMMENDATIONS FOR NEXT 7 DAYS
                </div>
              </div>

              <div className="card" style={{ padding: 18, marginBottom: 14 }}>
                <Eyebrow>How is the plan feeling?</Eyebrow>
                <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                  {[["Just right", true], ["Too hard", false], ["Too easy", false]].map(([l, active], i) => (
                    <div key={i} style={{ flex: 1, padding: "12px 14px", textAlign: "center", borderRadius: 4, border: "1px solid " + (active ? "var(--accent)" : "var(--hairline)"), background: active ? "color-mix(in oklab, var(--accent) 10%, transparent)" : "transparent" }}>{l}</div>
                  ))}
                </div>
              </div>

              <div className="card" style={{ padding: 18, marginBottom: 14 }}>
                <Eyebrow>Current location</Eyebrow>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 10 }}>
                  <div style={{ fontWeight: 600, fontSize: 15 }}>Home garage <Pill tone="solid">PRIMARY</Pill></div>
                  <Ic d={I.chevD} size={14} />
                </div>
              </div>

              <div className="card" style={{ padding: 18, marginBottom: 14 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <Eyebrow>Upcoming location changes</Eyebrow>
                  <div className="btn btn-ghost btn-sm"><Ic d={I.plus} size={11} sw={2} /> ADD</div>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr auto", gap: 8, marginTop: 12 }}>
                  {[["From", "May 29"], ["To", "May 31"], ["Location", "Hotel"], ["City", "Boston, MA"]].map(([k, v], i) => (
                    <div key={i} style={{ padding: "10px 12px", border: "1px solid var(--hairline-2)", borderRadius: 4 }}>
                      <div className="eyebrow" style={{ fontSize: 9 }}>{k}</div>
                      <div className="num" style={{ fontSize: 13, fontWeight: 500, marginTop: 4 }}>{v}</div>
                    </div>
                  ))}
                  <div style={{ display: "grid", placeItems: "center" }}><Ic d={I.x} size={14} /></div>
                </div>
                <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", marginTop: 10, letterSpacing: "0.14em" }}>1 LOCATION CHANGE PLANNED · WE'LL FACTOR IT IN</div>
              </div>

              <div className="card" style={{ padding: 18, marginBottom: 14 }}>
                <Eyebrow>Coach notes · optional</Eyebrow>
                <div className="card-flush" style={{ marginTop: 10, padding: "12px 14px", minHeight: 100, fontSize: 13, color: "var(--fg-2)" }}>
                  Feeling pretty good week 8 — recovered well from Saturday's long. Hamstring tightness from Mon is gone. Boston trip Wed–Fri means I have a small hotel gym only; can run outside.<span style={{ background: "var(--fg)", width: 1, height: 16, display: "inline-block", marginLeft: 2, verticalAlign: "middle", opacity: 0.5 }} />
                </div>
              </div>
            </div>

            <div className="stack">
              <div className="card" style={{ padding: 0 }}>
                <div style={{ padding: "12px 18px", borderBottom: "1px solid var(--hairline-2)" }}>
                  <Eyebrow>Recent sessions · 5</Eyebrow>
                </div>
                {[
                  ["May 26", "Easy aerobic", "completed"],
                  ["May 25", "Bench + pull", "completed"],
                  ["May 24", "Long run · fueling", "completed"],
                  ["May 23", "Easy aerobic", "skipped"],
                  ["May 22", "Threshold intervals", "completed"],
                ].map((r, i) => (
                  <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "10px 18px", borderBottom: i < 4 ? "1px solid var(--hairline-2)" : "none", fontSize: 12 }}>
                    <div>
                      <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)", marginRight: 8 }}>{r[0]}</span>
                      <span>{r[1]}</span>
                    </div>
                    <Pill tone={r[2] === "completed" ? "good" : "warn"}>{r[2].toUpperCase()}</Pill>
                  </div>
                ))}
              </div>

              <div className="card" style={{ padding: 0 }}>
                <div style={{ padding: "12px 18px", borderBottom: "1px solid var(--hairline-2)" }}>
                  <Eyebrow>Upcoming · next 5</Eyebrow>
                </div>
                {[
                  ["May 27", "Threshold intervals", "Z4"],
                  ["May 28", "Easy aerobic", "Z2"],
                  ["May 29", "Lower strength", "RPE 7"],
                  ["May 30", "VO2 short", "Z5"],
                  ["May 31", "Long run · fueling", "Z2/Z3"],
                ].map((r, i) => (
                  <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "10px 18px", borderBottom: i < 4 ? "1px solid var(--hairline-2)" : "none", fontSize: 12 }}>
                    <div>
                      <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)", marginRight: 8 }}>{r[0]}</span>
                      <span style={{ fontWeight: 500 }}>{r[1]}</span>
                    </div>
                    <span className="mono" style={{ fontSize: 10, color: "var(--accent)", letterSpacing: "0.14em" }}>{r[2]}</span>
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
// 18. FIT DEBUG — Utility view for inspecting a parsed FIT
// ═══════════════════════════════════════════════════════════════════
const ScreenFitDebug = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="link" />
      <div className="page">
        <TopBar crumbs={["Connections", "Debug · .FIT"]} actions={
          <>
            <div className="btn btn-ghost"><Ic d={I.upload} size={12} /> Upload another</div>
            <div className="btn btn-primary"><Ic d={I.check} size={12} sw={2.2} /> Import this session</div>
          </>
        } />
        <div className="page-body">
          <div style={{ marginBottom: 18 }}>
            <Eyebrow>Debug · activity_2026-05-22T1844.fit · from Wahoo ELEMNT Roam 2</Eyebrow>
            <h1 className="page-title" style={{ marginTop: 8 }}>Parsed FIT file.</h1>
            <div className="page-sub">Shows the raw records we extracted before they're written to your cardio log. Confirm everything looks right and import.</div>
          </div>

          {/* Top stats */}
          <div className="row" style={{ marginBottom: 14 }}>
            {[
              ["Sport",       "running"],
              ["Sub-sport",   "trail"],
              ["Duration",    "1:18:42"],
              ["Distance",    "9.42 mi"],
              ["Avg HR",      "152 bpm"],
              ["Max HR",      "178 bpm"],
              ["Elev gain",   "412 ft"],
              ["Calories",    "924"],
            ].map(([k, v], i) => (
              <div key={i} className="stat-card col" style={{ padding: 12 }}>
                <div className="k" style={{ fontSize: 9 }}>{k}</div>
                <div className="v num" style={{ fontSize: 17 }}>{v}</div>
              </div>
            ))}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 360px", gap: 14 }}>
            {/* Record stream */}
            <div className="card" style={{ padding: 0 }}>
              <div style={{ padding: "12px 18px", borderBottom: "1px solid var(--hairline-2)", display: "flex", justifyContent: "space-between" }}>
                <Eyebrow>Record stream · sample · 4,725 rows</Eyebrow>
                <div style={{ display: "flex", gap: 6 }}>
                  <Pill tone="solid">RECORDS</Pill>
                  <Pill>LAPS</Pill>
                  <Pill>SESSIONS</Pill>
                  <Pill>EVENTS</Pill>
                </div>
              </div>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, fontFamily: "var(--mono)" }}>
                <thead>
                  <tr>
                    {["timestamp","heart_rate","cadence","speed_mps","distance_m","altitude_m","power_w"].map((h,i)=>(
                      <th key={i} style={{ padding: "10px 14px", textAlign: "left", fontSize: 9, letterSpacing: "0.16em", textTransform: "uppercase", color: "var(--fg-3)", fontWeight: 500, borderBottom: "1px solid var(--hairline-2)" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {Array.from({ length: 12 }).map((_, i) => {
                    const ts = `18:44:${(i * 5).toString().padStart(2, "0")}`;
                    const hr = 122 + Math.floor(Math.sin(i * 0.5) * 12 + i * 1.2);
                    const cad = 168 + Math.floor(Math.cos(i * 0.4) * 4);
                    const spd = (3.42 + Math.sin(i * 0.3) * 0.18).toFixed(2);
                    const dist = (i * 17.5).toFixed(1);
                    const alt = (124.5 + Math.sin(i * 0.6) * 3).toFixed(1);
                    return (
                      <tr key={i} style={{ borderBottom: i < 11 ? "1px solid var(--hairline-2)" : "none" }}>
                        <td style={{ padding: "8px 14px", color: "var(--fg-3)" }}>{ts}</td>
                        <td style={{ padding: "8px 14px" }}>{hr}</td>
                        <td style={{ padding: "8px 14px" }}>{cad}</td>
                        <td style={{ padding: "8px 14px" }}>{spd}</td>
                        <td style={{ padding: "8px 14px" }}>{dist}</td>
                        <td style={{ padding: "8px 14px" }}>{alt}</td>
                        <td style={{ padding: "8px 14px", color: "var(--fg-4)" }}>—</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <div style={{ padding: "10px 18px", borderTop: "1px solid var(--hairline-2)", background: "var(--bg)", display: "flex", justifyContent: "space-between" }}>
                <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.16em" }}>SHOWING 12 OF 4,725 ROWS · SAMPLED EVERY 5S</span>
                <span className="mono" style={{ fontSize: 10, color: "var(--accent)", letterSpacing: "0.16em" }}>VIEW ALL · EXPORT CSV →</span>
              </div>
            </div>

            {/* Right rail */}
            <div className="stack">
              <div className="card" style={{ padding: 18 }}>
                <Eyebrow>File header</Eyebrow>
                <div style={{ marginTop: 10, fontFamily: "var(--mono)", fontSize: 11, color: "var(--fg-2)", lineHeight: 1.85 }}>
                  <div>protocol_version: 2.0</div>
                  <div>profile_version: 21.40</div>
                  <div>data_size: 487,294 bytes</div>
                  <div>data_type: <span style={{ color: "var(--accent)" }}>".FIT"</span></div>
                  <div>crc: <span style={{ color: "var(--good)" }}>valid</span></div>
                </div>
              </div>

              <div className="card" style={{ padding: 18 }}>
                <Eyebrow>Device</Eyebrow>
                <div style={{ marginTop: 10, fontFamily: "var(--mono)", fontSize: 11, color: "var(--fg-2)", lineHeight: 1.85 }}>
                  <div>manufacturer: wahoo</div>
                  <div>product: elemnt_roam_2</div>
                  <div>serial_number: ****redacted</div>
                  <div>software_version: 14.2</div>
                </div>
              </div>

              <div className="card" style={{ padding: 18 }}>
                <Eyebrow>Warnings · 1</Eyebrow>
                <div style={{ marginTop: 10, padding: "10px 12px", background: "color-mix(in oklab, var(--warn) 10%, transparent)", border: "1px solid color-mix(in oklab, var(--warn) 30%, transparent)", borderRadius: 4, fontSize: 12, color: "var(--fg-2)" }}>
                  <b>Power data missing.</b> Source had no power_w field — pace/HR-only import. This is fine for trail running.
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
// 19. ADMIN DASHBOARD
// ═══════════════════════════════════════════════════════════════════
const ScreenAdmin = () => {
  const users = [
    { id: 1,  user: "ahorn",        display: "Andrew Horn",      email: "andrew@aidstation.run",   strength: 412, cardio: 318, plans: 3, last: "today",   admin: true },
    { id: 2,  user: "sarah.k",      display: "Sarah Kowalski",   email: "sarah@example.com",       strength: 218, cardio: 482, plans: 2, last: "today"   },
    { id: 3,  user: "marc.w",       display: "Marc Weber",       email: "marc@example.com",        strength:  88, cardio: 612, plans: 1, last: "2d ago"  },
    { id: 4,  user: "jenny.t",      display: "Jenny Tran",       email: "jenny@example.com",       strength: 154, cardio: 240, plans: 4, last: "today"   },
    { id: 5,  user: "ramon.p",      display: "Ramón Paredes",    email: "rp@example.com",          strength:  42, cardio: 188, plans: 1, last: "1w ago"  },
    { id: 6,  user: "lin.h",        display: "Lin Huang",        email: "lin@example.com",         strength: 312, cardio:  64, plans: 2, last: "today"   },
    { id: 7,  user: "darius.j",     display: "Darius Jefferson", email: "djeff@example.com",       strength: 184, cardio: 396, plans: 1, last: "3d ago"  },
    { id: 8,  user: "anna.b",       display: "Anna Bergström",   email: "anna@example.com",        strength: 268, cardio: 412, plans: 3, last: "today"   },
    { id: 9,  user: "test.user",    display: "(test)",           email: null,                      strength:   0, cardio:   0, plans: 0, last: "—"       },
  ];
  return (
    <div className="screen">
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <Sidebar active="athlete" />
        <div className="page">
          <TopBar crumbs={["Admin", "Users"]} actions={
            <>
              <div className="btn btn-ghost"><Ic d={I.download} size={12} /> Audit log</div>
              <div className="btn btn-ghost"><Ic d={I.bolt} size={12} /> Telemetry</div>
            </>
          } />
          <div className="page-body">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 22 }}>
              <div>
                <Eyebrow>Admin · user management</Eyebrow>
                <h1 className="page-title" style={{ marginTop: 8 }}>Users</h1>
                <div className="page-sub">Deleting a user removes their row in <code style={{ fontFamily: "var(--mono)", fontSize: 12 }}>users</code> and every per-user row across the 25 scoped tables. Shared catalogs are untouched.</div>
              </div>
              <div style={{ display: "flex", gap: 14 }}>
                {[["Users", "9"], ["Pro", "6"], ["Active 7d", "5"], ["Plans active", "17"]].map(([k, v], i) => (
                  <div key={i} className="stat-card" style={{ minWidth: 100, padding: 14 }}>
                    <div className="k">{k}</div>
                    <div className="v num" style={{ fontSize: 22 }}>{v}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Search + filters */}
            <div className="card" style={{ padding: "10px 16px", marginBottom: 12, display: "flex", gap: 12, alignItems: "center" }}>
              <Ic d={I.search} size={14} />
              <span style={{ flex: 1, color: "var(--fg-3)", fontSize: 13 }}>Search by username, display name, or email…</span>
              {["All", "Pro", "Active", "Inactive"].map((f, i) => (
                <Pill key={i} tone={i === 0 ? "accent" : null}>{f.toUpperCase()}</Pill>
              ))}
            </div>

            {/* Users table */}
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
                    <tr key={u.id} style={{ borderBottom: i < users.length - 1 ? "1px solid var(--hairline-2)" : "none" }}>
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
                        {!u.admin && <div className="btn btn-ghost btn-sm" style={{ color: "var(--bad)", borderColor: "color-mix(in oklab, var(--bad) 30%, transparent)" }}>DELETE</div>}
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
  ScreenPlanGenerate, ScreenPlanProgress, ScreenPlanProgressLong, ScreenPlanCompare, ScreenPlanImport,
  ScreenCoachingReview, ScreenFitDebug, ScreenAdmin,
});
