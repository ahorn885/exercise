/* AIDSTATION redesign — coverage gaps (desktop)
   Onb step 01 · Profile empty · Wellness FIT import preview
   Notification settings · Command palette · Keyboard shortcuts
   Session expired · 404 · Permission denied · JSON import parse error
   Inline form validation errors. */

// ═══════════════════════════════════════════════════════════════════
// G1. ONBOARDING — STEP 01 · ACCOUNT CREATION
// ═══════════════════════════════════════════════════════════════════
const OnbAccount = () => {
  const pwRules = [
    ["≥ 10 characters",       true],
    ["Mixed case",            true],
    ["A number",              true],
    ["A symbol (! @ # $ …)",  false],
  ];
  return (
    <OnbShell step={1}>
      <div style={{ flex: 1, overflow: "hidden", display: "grid", gridTemplateColumns: "1.05fr 1fr", minHeight: 0 }}>
        {/* LEFT · form */}
        <div style={{ padding: "48px 56px 32px", overflow: "auto", borderRight: "1px solid var(--hairline-2)" }}>
          <div style={{ maxWidth: 460 }}>
            <Eyebrow accent>● STEP 01 · CREATE YOUR ACCOUNT</Eyebrow>
            <h1 style={{ fontSize: 40, fontWeight: 800, letterSpacing: "-0.025em", lineHeight: 1.06, margin: "12px 0 10px" }}>
              Start with <span style={{ color: "var(--accent)" }}>the basics.</span>
            </h1>
            <div style={{ fontSize: 15, color: "var(--fg-3)", lineHeight: 1.55 }}>
              Six more steps after this — they take about 4 minutes. You can edit anything later from Profile.
            </div>

            {/* Email + password */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 28 }}>
              <Field label="First name" value="Andrew" />
              <Field label="Last name"  value="Horn" />
            </div>
            <div style={{ marginTop: 12 }}>
              <Field label="Email" value="andrew@aidstation.run" valid />
            </div>
            <div style={{ marginTop: 12 }}>
              <Field label="Password" value="aidstationFTW21" type="password" hint="Used to sign back in." />
            </div>

            {/* Strength meter */}
            <div style={{ marginTop: 14 }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                <span className="mono" style={{ fontSize: 9, letterSpacing: "0.22em", textTransform: "uppercase", color: "var(--fg-3)" }}>● STRENGTH</span>
                <span className="mono" style={{ fontSize: 9, letterSpacing: "0.22em", textTransform: "uppercase", color: "var(--warn)" }}>FAIR · ADD A SYMBOL</span>
              </div>
              <div style={{ display: "flex", gap: 4, height: 4 }}>
                {[0,1,2,3].map(i => (
                  <div key={i} style={{ flex: 1, background: i < 3 ? "var(--warn)" : "var(--bg-3)" }} />
                ))}
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px 14px", marginTop: 12 }}>
                {pwRules.map(([t, ok], i) => (
                  <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: ok ? "var(--fg-2)" : "var(--fg-4)" }}>
                    {ok ? <Ic d={I.check} size={12} sw={2.5} /> : <span style={{ width: 8, height: 8, borderRadius: "50%", border: "1px solid var(--fg-4)" }} />}
                    {t}
                  </div>
                ))}
              </div>
            </div>

            {/* Consents */}
            <div style={{ marginTop: 22, padding: "14px 16px", border: "1px solid var(--hairline-2)", borderRadius: 6 }}>
              <Checkbox checked label="I'm 16 or older." />
              <div style={{ height: 8 }} />
              <Checkbox checked label={<>I agree to the <u>Terms of service</u> and <u>Privacy notice</u>.</>} />
              <div style={{ height: 8 }} />
              <Checkbox label="Email me product updates (1–2 / month, not training)." />
            </div>

            <div style={{ marginTop: 24, display: "flex", gap: 10, alignItems: "center" }}>
              <div className="btn btn-primary" style={{ padding: "12px 18px" }}>Create account <Ic d={I.arrow} size={12} sw={2} /></div>
              <div className="mono" style={{ fontSize: 10, letterSpacing: "0.18em", color: "var(--fg-4)" }}>· OR · <span style={{ color: "var(--fg-2)" }}>SIGN IN</span></div>
            </div>
          </div>
        </div>

        {/* RIGHT · marketing rail */}
        <div style={{ padding: "48px 48px", background: "var(--bg-2)", display: "flex", flexDirection: "column" }}>
          <Eyebrow>● WHAT YOU'RE SIGNING UP FOR</Eyebrow>
          <h2 style={{ fontSize: 24, fontWeight: 700, letterSpacing: "-0.015em", margin: "10px 0 22px" }}>
            One account · every device · all your providers.
          </h2>
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {[
              ["Adaptive plans",   "Sessions adjust to what you actually do — not what you remember to log."],
              ["Brand-neutral .FIT","Pull from Garmin, Wahoo, COROS, Polar, Suunto — or upload .FIT manually."],
              ["Plan versions",    "Every cascade run is a revertable version. Compare any two side-by-side."],
              ["Built for races",  "Plans anchor to a race date. Taper, peak, recovery — already in the math."],
            ].map(([k, v], i) => (
              <div key={i} style={{ display: "grid", gridTemplateColumns: "28px 1fr", gap: 14, padding: "12px 0", borderTop: i === 0 ? "none" : "1px solid var(--hairline-2)" }}>
                <div className="mono" style={{ fontSize: 11, color: "var(--accent)", letterSpacing: "0.16em" }}>0{i+1}</div>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>{k}</div>
                  <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 4, lineHeight: 1.5 }}>{v}</div>
                </div>
              </div>
            ))}
          </div>

          <div style={{ marginTop: "auto", paddingTop: 28, display: "flex", gap: 14, alignItems: "center" }}>
            <div className="avatar lg">JK</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13, lineHeight: 1.5 }}>
                "Three months in, fastest BQ-qualifier I've ever run. The plan reacts to my week, not the other way around."
              </div>
              <div className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.18em", marginTop: 8, textTransform: "uppercase" }}>● JESSICA K · BQ-QUALIFIED · Q1 2026</div>
            </div>
          </div>
        </div>
      </div>
    </OnbShell>
  );
};

// — small form atoms reused across this file —
const Field = ({ label, value, type = "text", hint, valid }) => (
  <div>
    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
      <span className="mono" style={{ fontSize: 9, letterSpacing: "0.22em", textTransform: "uppercase", color: "var(--fg-3)" }}>● {label.toUpperCase()}</span>
      {valid && <span className="mono" style={{ fontSize: 9, letterSpacing: "0.22em", textTransform: "uppercase", color: "var(--good)" }}>✓ AVAILABLE</span>}
    </div>
    <div style={{ display: "flex", alignItems: "center", gap: 10, height: 40, padding: "0 12px", background: "var(--bg-2)", border: "1px solid var(--hairline-2)", borderRadius: 4 }}>
      <span style={{ flex: 1, fontSize: 14, color: "var(--fg)", fontFamily: type === "password" ? "var(--mono)" : "var(--sans)", letterSpacing: type === "password" ? "0.2em" : 0 }}>
        {type === "password" ? "•".repeat(value.length) : value}
      </span>
      {type === "password" && <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.18em" }}>SHOW</span>}
    </div>
    {hint && <div style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 6 }}>{hint}</div>}
  </div>
);

const Checkbox = ({ checked, label }) => (
  <label style={{ display: "flex", gap: 10, alignItems: "flex-start", fontSize: 13, color: "var(--fg-2)", lineHeight: 1.5 }}>
    <span style={{ width: 16, height: 16, borderRadius: 3, border: "1px solid " + (checked ? "var(--accent)" : "var(--hairline)"), background: checked ? "var(--accent)" : "transparent", color: "var(--ink)", display: "grid", placeItems: "center", flexShrink: 0, marginTop: 1 }}>
      {checked && <Ic d={I.check} size={10} sw={3} />}
    </span>
    <span>{label}</span>
  </label>
);

// ═══════════════════════════════════════════════════════════════════
// G2. PROFILE — FIRST-RUN / EMPTY BASELINES
// ═══════════════════════════════════════════════════════════════════
const ScreenProfileEmpty = () => {
  const baselines = [
    ["FTP",          "—", "watts",  "From last 20-min cycling effort"],
    ["Threshold HR", "—", "bpm",    "From a lactate threshold test or 30-min TT"],
    ["VO₂ max",      "—", "ml/kg",  "From provider, or estimate from a 5K time"],
    ["Run pace · Z2","—", "/mi",    "From easy-effort runs · auto-derived"],
    ["1RM · Squat",  "—", "lb",     "Required for strength prescriptions"],
    ["1RM · Bench",  "—", "lb",     "Required for strength prescriptions"],
  ];
  return (
    <div className="screen">
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <Sidebar active="athlete" />
        <div className="page">
          <TopBar crumbs={["Athlete", "Profile"]} actions={<div className="btn btn-ghost">Edit identity</div>} />
          <div className="page-body">
            <Eyebrow>● PROFILE · DAY 1</Eyebrow>
            <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", marginTop: 8, marginBottom: 18 }}>
              <h1 className="page-title">Hi, Andrew. Let's fill this in.</h1>
              <div className="mono" style={{ fontSize: 10, letterSpacing: "0.18em", color: "var(--fg-3)" }}>4 / 11 FIELDS · 36% COMPLETE</div>
            </div>

            {/* progress bar */}
            <div style={{ height: 4, background: "var(--bg-3)", borderRadius: 2, overflow: "hidden", marginBottom: 28 }}>
              <div style={{ width: "36%", height: "100%", background: "var(--accent)" }} />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 24 }}>
              {/* LEFT — identity + baselines */}
              <div className="stack">
                <div className="card" style={{ padding: 22 }}>
                  <Eyebrow>Identity</Eyebrow>
                  <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: 18, alignItems: "center", marginTop: 14 }}>
                    <div className="avatar lg" style={{ width: 56, height: 56, fontSize: 18 }}>AH</div>
                    <div>
                      <div style={{ fontSize: 18, fontWeight: 700 }}>Andrew Horn</div>
                      <div className="mono" style={{ fontSize: 11, color: "var(--fg-3)", letterSpacing: "0.16em", marginTop: 4 }}>andrew@aidstation.run · PRO · MEMBER SINCE TODAY</div>
                    </div>
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginTop: 18, paddingTop: 18, borderTop: "1px solid var(--hairline-2)" }}>
                    {[["DOB","1988-04-12"],["Sex","M"],["Timezone","America/New_York"]].map(([k,v]) => (
                      <div key={k}>
                        <div className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.22em", textTransform: "uppercase" }}>● {k}</div>
                        <div style={{ fontSize: 13, fontWeight: 600, marginTop: 4 }}>{v}</div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="card" style={{ padding: 0 }}>
                  <div style={{ padding: "16px 22px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--hairline-2)" }}>
                    <Eyebrow>Performance baselines · 0 / 6</Eyebrow>
                    <div className="btn btn-ghost btn-sm">Pre-fill from Strava →</div>
                  </div>
                  {baselines.map(([k, v, u, hint], i, a) => (
                    <div key={k} style={{ padding: "14px 22px", display: "grid", gridTemplateColumns: "1.2fr auto 1fr", gap: 18, alignItems: "center", borderBottom: i < a.length - 1 ? "1px solid var(--hairline-2)" : "none" }}>
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 600 }}>{k}</div>
                        <div style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 3 }}>{hint}</div>
                      </div>
                      <div className="num" style={{ fontFamily: "var(--mono)", fontSize: 18, color: "var(--fg-4)", letterSpacing: "0.05em" }}>{v} <span style={{ fontSize: 10, color: "var(--fg-4)" }}>{u}</span></div>
                      <div style={{ justifySelf: "end" }}>
                        <div className="btn btn-ghost btn-sm"><Ic d={I.plus} size={10} sw={2.4} /> SET</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* RIGHT — next steps + zero state of plans/billing */}
              <div className="stack">
                <div className="card" style={{ padding: 22, background: "color-mix(in oklab, var(--accent) 8%, var(--bg-2))", borderColor: "color-mix(in oklab, var(--accent) 30%, transparent)" }}>
                  <Eyebrow accent>● NEXT BEST STEP</Eyebrow>
                  <div style={{ fontSize: 18, fontWeight: 700, letterSpacing: "-0.015em", marginTop: 8, lineHeight: 1.25 }}>
                    Set FTP &amp; threshold HR — they anchor every cardio session.
                  </div>
                  <div style={{ fontSize: 12, color: "var(--fg-2)", marginTop: 10, lineHeight: 1.55 }}>
                    Either run a 20-min cycling test (we'll guide you) or pull from your last 28 days of Strava data.
                  </div>
                  <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
                    <div className="btn btn-ghost btn-sm">PULL FROM STRAVA</div>
                    <div className="btn btn-primary btn-sm">START FTP TEST</div>
                  </div>
                </div>

                <div className="card" style={{ padding: 18 }}>
                  <Eyebrow>Plans</Eyebrow>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 12 }}>
                    <div>
                      <div style={{ fontSize: 14, fontWeight: 600 }}>No plan yet</div>
                      <div style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 3 }}>Set a race target to generate one.</div>
                    </div>
                    <div className="btn btn-ghost btn-sm">SET RACE →</div>
                  </div>
                </div>

                <div className="card" style={{ padding: 18 }}>
                  <Eyebrow>Billing</Eyebrow>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 12 }}>
                    <div>
                      <div style={{ fontSize: 14, fontWeight: 600 }}>Pro · 14-day trial</div>
                      <div style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 3 }}>Ends Jun 10 · $19/mo after.</div>
                    </div>
                    <Pill tone="accent">TRIAL</Pill>
                  </div>
                </div>

                <div className="card-flush" style={{ padding: 16 }}>
                  <Eyebrow>Tip</Eyebrow>
                  <div style={{ fontSize: 12, color: "var(--fg-2)", marginTop: 8, lineHeight: 1.55 }}>
                    Don't have FTP yet? It's fine — set Z2 pace and we'll backfill the rest after your first two structured cardio sessions.
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════
// G3. WELLNESS .FIT IMPORT PREVIEW (parallels FIT debug §18)
// ═══════════════════════════════════════════════════════════════════
const ScreenWellnessFitImport = () => {
  const days = [
    { d: "2026-05-26", hrv: 72, rhr: 47, sleep: "7h 34m", stress: 28, steps: 9421, ok: true },
    { d: "2026-05-25", hrv: 68, rhr: 49, sleep: "6h 51m", stress: 41, steps: 11_204, ok: true },
    { d: "2026-05-24", hrv: 81, rhr: 45, sleep: "8h 02m", stress: 22, steps: 6_318,  ok: true },
    { d: "2026-05-23", hrv: 70, rhr: 48, sleep: "7h 12m", stress: 33, steps: 8_847,  ok: true },
    { d: "2026-05-22", hrv: "—",rhr: "—",sleep: "—",      stress: "—",steps: "—",   ok: false, note: "Recovery field missing" },
    { d: "2026-05-21", hrv: 64, rhr: 51, sleep: "6h 28m", stress: 47, steps: 12_440, ok: true },
    { d: "2026-05-20", hrv: 76, rhr: 46, sleep: "7h 49m", stress: 26, steps: 7_932,  ok: true },
  ];
  return (
    <div className="screen">
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <Sidebar active="insights" />
        <div className="page">
          <TopBar crumbs={["Wellness", "Import preview"]} actions={
            <>
              <div className="btn btn-ghost"><Ic d={I.upload} size={12} /> Upload more</div>
              <div className="btn btn-primary"><Ic d={I.check} size={12} sw={2.4} /> Import 6 days</div>
            </>
          } />
          <div className="page-body">
            <Eyebrow>● WELLNESS · .FIT IMPORT · BRAND-NEUTRAL</Eyebrow>
            <h1 className="page-title" style={{ marginTop: 8 }}>Preview before import.</h1>
            <div className="page-sub">Inspect daily recovery exports before they overwrite anything. Sport-watch agnostic — works with any device that exports daily summary .FIT.</div>

            {/* upload meta */}
            <div className="card" style={{ marginTop: 22, padding: 16, display: "grid", gridTemplateColumns: "auto 1fr auto auto auto", gap: 22, alignItems: "center" }}>
              <div style={{ width: 38, height: 38, borderRadius: 6, background: "var(--bg-3)", display: "grid", placeItems: "center" }}>
                <Ic d={I.cloud} size={18} />
              </div>
              <div>
                <div className="mono" style={{ fontSize: 13, fontWeight: 600 }}>wellness_export_2026-05-27.zip</div>
                <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.16em", marginTop: 3 }}>● 7 DAYS · 412 KB · DEVICE WAHOO ELEMNT BOLT · NEUTRAL PARSE</div>
              </div>
              <div><StatLabel k="Parsed" v="6 / 7" tone="good" /></div>
              <div><StatLabel k="Field warns" v="1" tone="warn" /></div>
              <div><StatLabel k="Range" v="May 20–26" /></div>
            </div>

            {/* table */}
            <div className="card" style={{ marginTop: 18, padding: 0 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1.1fr 0.7fr 0.7fr 0.9fr 0.7fr 0.9fr 0.7fr", padding: "12px 18px", borderBottom: "1px solid var(--hairline-2)" }}>
                {["Day","HRV","RHR","Sleep","Stress","Steps","Status"].map(h => (
                  <div key={h} className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.22em", textTransform: "uppercase" }}>● {h}</div>
                ))}
              </div>
              {days.map((r, i) => (
                <div key={r.d} style={{ display: "grid", gridTemplateColumns: "1.1fr 0.7fr 0.7fr 0.9fr 0.7fr 0.9fr 0.7fr", padding: "14px 18px", borderBottom: i < days.length - 1 ? "1px solid var(--hairline-2)" : "none", alignItems: "center", opacity: r.ok ? 1 : 0.65 }}>
                  <div className="mono" style={{ fontSize: 13, fontWeight: 600 }}>{r.d}</div>
                  <div className="num" style={{ fontFamily: "var(--mono)", fontSize: 14, fontWeight: 600 }}>{r.hrv}</div>
                  <div className="num" style={{ fontFamily: "var(--mono)", fontSize: 14, fontWeight: 600 }}>{r.rhr}</div>
                  <div className="mono" style={{ fontSize: 13 }}>{r.sleep}</div>
                  <div className="num" style={{ fontFamily: "var(--mono)", fontSize: 14, fontWeight: 600 }}>{r.stress}</div>
                  <div className="num" style={{ fontFamily: "var(--mono)", fontSize: 13 }}>{r.steps}</div>
                  <div>{r.ok ? <Pill tone="good">OK</Pill> : <Pill tone="warn">WARN</Pill>}</div>
                  {r.note && <div style={{ gridColumn: "1 / -1", fontSize: 11, color: "var(--warn)", marginTop: 6 }}>⚠ {r.note} · day will be skipped on import.</div>}
                </div>
              ))}
            </div>

            {/* footer disclosure */}
            <div className="card-flush" style={{ marginTop: 18, padding: "14px 18px", display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 22 }}>
              {[
                ["Will overwrite",     "2 existing entries · May 24 + 25"],
                ["Maps to",            "wellness_log table · 5 fields"],
                ["Parser version",     "fit-sdk 21.115 · neutral profile"],
              ].map(([k,v]) => (
                <div key={k}>
                  <div className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.22em", textTransform: "uppercase" }}>● {k}</div>
                  <div style={{ fontSize: 12, marginTop: 4 }}>{v}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const StatLabel = ({ k, v, tone }) => (
  <div>
    <div className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.22em", textTransform: "uppercase" }}>● {k}</div>
    <div className="num" style={{ fontFamily: "var(--mono)", fontSize: 16, fontWeight: 700, marginTop: 3, color: tone === "good" ? "var(--good)" : tone === "warn" ? "var(--warn)" : "var(--fg)" }}>{v}</div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// G4. NOTIFICATION SETTINGS · FULL PAGE
// ═══════════════════════════════════════════════════════════════════
const ScreenNotifSettings = () => {
  const cats = [
    ["Plan changes",   "Version writes · scope shifts · cap-exceeded.", { app: true,  email: true,  push: true  }],
    ["Sessions",       "Tomorrow's prescription · same-day rescheduling.", { app: true, email: false, push: true }],
    ["Coach reminders","Log adherence nudges · weekly check-ins.", { app: true, email: true, push: false }],
    ["Plateau alerts", "Detected stalls in any baseline · auto-deload offers.", { app: true, email: true, push: true }],
    ["Achievements",   "PRs · streak milestones · race countdowns.", { app: true, email: false, push: false }],
    ["System",         "Provider sync failures · billing · security.", { app: true, email: true, push: false }],
  ];
  return (
    <div className="screen">
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <Sidebar active="athlete" />
        <div className="page">
          <TopBar crumbs={["Athlete", "Notifications"]} actions={<><div className="btn btn-ghost">Reset to default</div><div className="btn btn-primary">Save</div></>} />
          <div className="page-body">
            <Eyebrow>● NOTIFICATIONS · CHANNELS × CATEGORIES</Eyebrow>
            <h1 className="page-title" style={{ marginTop: 8 }}>Tell us what to bother you about.</h1>
            <div className="page-sub">Each category sends to up to three channels. Silenced channels still log into the in-app feed.</div>

            {/* Quiet hours strip */}
            <div className="card" style={{ marginTop: 22, padding: 16, display: "grid", gridTemplateColumns: "auto 1fr auto auto auto", gap: 22, alignItems: "center" }}>
              <div style={{ width: 38, height: 38, borderRadius: 6, background: "var(--bg-3)", display: "grid", placeItems: "center" }}>
                <Ic d={I.clock} size={18} />
              </div>
              <div>
                <div style={{ fontWeight: 600 }}>Quiet hours</div>
                <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 3 }}>Push + email are held back; the in-app feed still updates.</div>
              </div>
              <div><StatLabel k="From" v="22:00" /></div>
              <div><StatLabel k="To"   v="07:00" /></div>
              <Toggle on />
            </div>

            {/* Matrix */}
            <div className="card" style={{ marginTop: 18, padding: 0 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1.6fr 110px 110px 110px", padding: "14px 22px", borderBottom: "1px solid var(--hairline-2)", alignItems: "center" }}>
                <div className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.22em", textTransform: "uppercase" }}>● Category</div>
                {["In-app","Email","Push"].map(c => (
                  <div key={c} className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.22em", textTransform: "uppercase", textAlign: "center" }}>{c}</div>
                ))}
              </div>
              {cats.map(([name, desc, ch], i) => (
                <div key={name} style={{ display: "grid", gridTemplateColumns: "1.6fr 110px 110px 110px", padding: "16px 22px", borderBottom: i < cats.length - 1 ? "1px solid var(--hairline-2)" : "none", alignItems: "center" }}>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 14 }}>{name}</div>
                    <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 3 }}>{desc}</div>
                  </div>
                  <div style={{ display: "grid", placeItems: "center" }}><Toggle on={ch.app}   /></div>
                  <div style={{ display: "grid", placeItems: "center" }}><Toggle on={ch.email} /></div>
                  <div style={{ display: "grid", placeItems: "center" }}><Toggle on={ch.push}  /></div>
                </div>
              ))}
            </div>

            {/* Device row */}
            <div style={{ marginTop: 22, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}>
              <div className="card" style={{ padding: 18 }}>
                <Eyebrow>Push devices</Eyebrow>
                {[
                  ["iPhone 15 · Andrew", "Last active 4 min ago", true],
                  ["MacBook Air · Safari", "Last active 2 days ago", true],
                  ["Old iPad",         "Last active 47 days ago", false],
                ].map(([d, t, on], i) => (
                  <div key={i} style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 0", borderTop: i === 0 ? "1px solid var(--hairline-2)" : "1px solid var(--hairline-2)", marginTop: i === 0 ? 14 : 0 }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 13, fontWeight: 600 }}>{d}</div>
                      <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em", marginTop: 3 }}>{t}</div>
                    </div>
                    <Toggle on={on} />
                  </div>
                ))}
              </div>
              <div className="card" style={{ padding: 18 }}>
                <Eyebrow>Email digest</Eyebrow>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginTop: 14 }}>
                  {[["Off",false],["Daily",false],["Weekly",true]].map(([l, on]) => (
                    <div key={l} className="card" style={{ padding: "10px 12px", textAlign: "center", borderColor: on ? "var(--accent)" : undefined, background: on ? "color-mix(in oklab, var(--accent) 12%, transparent)" : undefined, color: on ? "var(--accent)" : undefined }}>
                      <div className="mono" style={{ fontSize: 10, letterSpacing: "0.18em", fontWeight: 600 }}>{l.toUpperCase()}</div>
                    </div>
                  ))}
                </div>
                <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 14, lineHeight: 1.55 }}>
                  Sent Monday 06:00 local · summarizes last week + previews the upcoming block.
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const Toggle = ({ on }) => (
  <div style={{ width: 36, height: 20, borderRadius: 999, padding: 2, background: on ? "var(--accent)" : "var(--bg-3)", display: "flex", alignItems: "center", justifyContent: on ? "flex-end" : "flex-start" }}>
    <div style={{ width: 16, height: 16, borderRadius: "50%", background: on ? "var(--ink)" : "var(--fg-3)" }} />
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// G5. COMMAND PALETTE · ⌘K
// ═══════════════════════════════════════════════════════════════════
const ScreenSearchOverlay = () => {
  const groups = [
    ["Suggested", [
      ["Tomorrow's session", "12 mi · MP-effort long run", I.workout, "↵"],
      ["Refresh plan", "Re-run cascade against current inputs", I.bolt, "R"],
      ["Log a wellness check", "Sleep · energy · soreness", I.pulse, "L W"],
    ]],
    ["Navigate", [
      ["Today",          "/dashboard", I.home,    "G T"],
      ["Plan · week",    "/plan", I.plan,         "G P"],
      ["Workouts",       "/workouts", I.workout, "G W"],
      ["Exercises",      "/exercises", I.library, "G E"],
      ["Locations",      "/locations", I.pin,    "G L"],
      ["Connections",    "/connections", I.link, "G C"],
      ["Wellness",       "/wellness", I.pulse,   "G I"],
    ]],
    ["Workouts (12)", [
      ["Tue · 8 × 800 m @ 5K",   "Week 9 · interval", I.workout, "↵"],
      ["Wed · 60 min Z2 ride",   "Week 9 · aerobic",  I.workout, "↵"],
      ["Thu · Heavy lower",      "Week 9 · strength", I.weight,  "↵"],
    ]],
  ];
  return (
    <div className="screen">
      <div style={{ display: "flex", flex: 1, minHeight: 0, position: "relative" }}>
        <Sidebar active="home" />
        <div className="page" style={{ filter: "blur(2px)", opacity: 0.4 }}>
          <TopBar crumbs={["Today"]} />
          <div className="page-body">
            <h1 className="page-title">Today</h1>
            <div className="card" style={{ marginTop: 22, height: 220 }} />
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, marginTop: 16 }}>
              <div className="card" style={{ height: 200 }} />
              <div className="card" style={{ height: 200 }} />
              <div className="card" style={{ height: 200 }} />
            </div>
          </div>
        </div>
        <div style={{ position: "absolute", inset: 0, background: "color-mix(in oklab, var(--ink) 60%, transparent)" }} />

        {/* Palette */}
        <div style={{
          position: "absolute", top: 110, left: "50%", transform: "translateX(-50%)",
          width: 680, maxHeight: 540, background: "var(--bg-2)", border: "1px solid var(--hairline)", borderRadius: 10,
          boxShadow: "0 24px 80px -10px rgba(0,0,0,0.7)", overflow: "hidden",
          display: "flex", flexDirection: "column",
        }}>
          {/* input */}
          <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--hairline-2)", display: "flex", alignItems: "center", gap: 14 }}>
            <Ic d={I.search} size={16} />
            <span style={{ flex: 1, fontSize: 17, color: "var(--fg)" }}>refresh<span style={{ color: "var(--accent)", animation: "blink 1s steps(1) infinite" }}>│</span></span>
            <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.18em" }}>ESC TO CLOSE</span>
          </div>
          {/* results */}
          <div style={{ overflow: "auto", flex: 1 }}>
            {groups.map(([title, rows], gi) => (
              <div key={title}>
                <div className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.22em", textTransform: "uppercase", padding: "12px 20px 6px" }}>● {title}</div>
                {rows.map(([k, sub, icon, kbd], i) => (
                  <div key={i} style={{
                    display: "grid", gridTemplateColumns: "26px 1fr auto", gap: 14, alignItems: "center",
                    padding: "10px 20px",
                    background: gi === 0 && i === 1 ? "color-mix(in oklab, var(--accent) 15%, transparent)" : "transparent",
                  }}>
                    <div style={{ width: 26, height: 26, borderRadius: 4, background: "var(--bg-3)", display: "grid", placeItems: "center" }}>
                      <Ic d={icon} size={13} />
                    </div>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: 14, fontWeight: 600 }}>{k}</div>
                      <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em", marginTop: 2 }}>{sub}</div>
                    </div>
                    <div style={{ display: "flex", gap: 4 }}>
                      {kbd.split(" ").map((part, j) => (
                        <kbd key={j} className="mono" style={{ fontSize: 10, padding: "3px 6px", background: "var(--bg-3)", borderRadius: 3, color: "var(--fg-2)" }}>{part}</kbd>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ))}
          </div>
          {/* footer */}
          <div style={{ padding: "10px 20px", borderTop: "1px solid var(--hairline-2)", display: "flex", gap: 18, alignItems: "center", fontSize: 10 }}>
            <span className="mono" style={{ color: "var(--fg-3)", letterSpacing: "0.18em" }}><kbd style={{ background: "var(--bg-3)", padding: "2px 5px", borderRadius: 2, marginRight: 4 }}>↑↓</kbd> NAVIGATE</span>
            <span className="mono" style={{ color: "var(--fg-3)", letterSpacing: "0.18em" }}><kbd style={{ background: "var(--bg-3)", padding: "2px 5px", borderRadius: 2, marginRight: 4 }}>↵</kbd> OPEN</span>
            <span className="mono" style={{ color: "var(--fg-3)", letterSpacing: "0.18em" }}><kbd style={{ background: "var(--bg-3)", padding: "2px 5px", borderRadius: 2, marginRight: 4 }}>?</kbd> SHORTCUTS</span>
            <span style={{ flex: 1 }} />
            <span className="mono" style={{ color: "var(--fg-3)", letterSpacing: "0.18em" }}>3 GROUPS · 13 MATCHES</span>
          </div>
        </div>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════
// G6. KEYBOARD SHORTCUTS · CHEAT SHEET
// ═══════════════════════════════════════════════════════════════════
const ScreenShortcuts = () => {
  const sections = [
    ["Anywhere", [
      ["⌘ K",   "Open command palette"],
      ["?",     "Show this cheat sheet"],
      ["⌘ /",   "Toggle quick-log sheet"],
      ["⌘ N",   "New manual log"],
      ["⌘ ⇧ R", "Refresh current plan"],
      ["G then T", "Go to Today"],
      ["G then P", "Go to Plan"],
      ["G then W", "Go to Workouts"],
      ["G then E", "Go to Exercises"],
      ["G then I", "Go to Wellness (insights)"],
    ]],
    ["In a workout", [
      ["J / K",   "Next / previous exercise"],
      ["Space",   "Start/pause set timer"],
      ["U",       "Upload completed .FIT"],
      ["S",       "Mark session done"],
      ["E",       "Edit prescription"],
      ["R",       "Redo as next session"],
    ]],
    ["Plan week", [
      ["← / →",   "Previous / next week"],
      ["D",       "Toggle density (sparse / dense)"],
      ["C",       "Compare to last version"],
      ["⌘ ⇧ V",   "Plan version history"],
    ]],
    ["Editing", [
      ["⌘ S",     "Save current form"],
      ["⌘ Z",     "Undo last edit"],
      ["Esc",     "Close modal / palette / sheet"],
      ["Tab",     "Next field"],
    ]],
  ];
  return (
    <div className="screen">
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <Sidebar active="home" />
        <div className="page">
          <TopBar crumbs={["Help", "Keyboard shortcuts"]} actions={<div className="btn btn-ghost">Print cheat sheet</div>} />
          <div className="page-body">
            <Eyebrow>● KEYBOARD SHORTCUTS · CHEAT SHEET</Eyebrow>
            <h1 className="page-title" style={{ marginTop: 8 }}>Move faster.</h1>
            <div className="page-sub">Press <kbd className="mono" style={{ background: "var(--bg-2)", padding: "2px 5px", borderRadius: 2, border: "1px solid var(--hairline-2)" }}>?</kbd> anywhere to bring up this sheet.</div>

            <div style={{ marginTop: 24, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}>
              {sections.map(([title, rows]) => (
                <div key={title} className="card" style={{ padding: 0 }}>
                  <div style={{ padding: "14px 20px", borderBottom: "1px solid var(--hairline-2)" }}>
                    <Eyebrow accent>● {title.toUpperCase()}</Eyebrow>
                  </div>
                  {rows.map(([k, v], i, a) => (
                    <div key={i} style={{ display: "grid", gridTemplateColumns: "1.3fr 1fr", padding: "11px 20px", borderBottom: i < a.length - 1 ? "1px solid var(--hairline-2)" : "none", alignItems: "center" }}>
                      <div style={{ fontSize: 13 }}>{v}</div>
                      <div style={{ display: "flex", gap: 5, justifyContent: "flex-end" }}>
                        {k.split(" ").map((part, j) => (
                          <kbd key={j} className="mono" style={{ fontSize: part.length > 4 ? 10 : 11, padding: "3px 7px", background: "var(--bg-3)", borderRadius: 3, color: "var(--fg)", border: "1px solid var(--hairline-2)" }}>{part}</kbd>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              ))}
            </div>

            <div className="card-flush" style={{ marginTop: 22, padding: "14px 18px", fontSize: 12, color: "var(--fg-3)" }}>
              ⓘ G-sequences (G then T, G then P …) work anywhere except when you're typing in an input. Click into an empty area first to release focus.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════
// G7. SESSION EXPIRED — appears in place of the page after token expiry
// ═══════════════════════════════════════════════════════════════════
const ScreenSessionExpired = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0, position: "relative" }}>
      <Sidebar active="home" />
      <div className="page" style={{ filter: "blur(2px)", opacity: 0.35 }}>
        <TopBar crumbs={["Plan", "Week 09"]} />
        <div className="page-body">
          <div className="card" style={{ height: 180, marginTop: 22 }} />
          <div className="card" style={{ height: 260, marginTop: 18 }} />
        </div>
      </div>
      <div style={{ position: "absolute", inset: 0, background: "color-mix(in oklab, var(--ink) 50%, transparent)" }} />

      <div style={{
        position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)",
        width: 460, background: "var(--bg-2)", border: "1px solid var(--hairline)", borderRadius: 8,
        boxShadow: "0 24px 60px -8px rgba(0,0,0,0.5)", overflow: "hidden",
      }}>
        <div style={{ padding: "18px 22px", borderBottom: "1px solid var(--hairline-2)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <Eyebrow>● SESSION EXPIRED</Eyebrow>
          <Pill tone="warn">401</Pill>
        </div>
        <div style={{ padding: "22px" }}>
          <div style={{ fontSize: 22, fontWeight: 700, letterSpacing: "-0.015em" }}>Sign back in.</div>
          <div style={{ fontSize: 13, color: "var(--fg-2)", marginTop: 8, lineHeight: 1.55 }}>
            Your session lapsed after 30 days of inactivity. Any unsaved form is held in this tab — you'll land back here after sign-in.
          </div>
          <div style={{ marginTop: 18, padding: "12px 14px", background: "var(--bg-3)", borderRadius: 4 }}>
            <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.18em", textTransform: "uppercase" }}>● ACCOUNT</div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 8 }}>
              <div className="avatar">AH</div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600 }}>Andrew Horn</div>
                <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em" }}>andrew@aidstation.run</div>
              </div>
            </div>
          </div>
          <div style={{ marginTop: 16, display: "flex", gap: 8 }}>
            <div className="btn btn-ghost btn-sm" style={{ flex: 1, justifyContent: "center" }}>Not me · sign out</div>
            <div className="btn btn-primary btn-sm" style={{ flex: 2, justifyContent: "center" }}>Sign in as Andrew →</div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// G8. 404 · NOT FOUND
// ═══════════════════════════════════════════════════════════════════
const Screen404 = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="home" />
      <div className="page">
        <TopBar crumbs={["?", "Not found"]} />
        <div className="page-body" style={{ display: "grid", placeItems: "center" }}>
          <div style={{ maxWidth: 560, textAlign: "center" }}>
            <div className="mono" style={{ fontSize: 96, fontWeight: 800, letterSpacing: "-0.04em", lineHeight: 1, color: "var(--accent)" }}>4·0·4</div>
            <Eyebrow style={{ marginTop: 18 }}>● NO SUCH ROUTE</Eyebrow>
            <h1 style={{ fontSize: 32, fontWeight: 700, letterSpacing: "-0.02em", margin: "10px 0 12px" }}>
              That URL doesn't go anywhere.
            </h1>
            <div style={{ color: "var(--fg-3)", fontSize: 14, lineHeight: 1.55, maxWidth: 440, margin: "0 auto 24px" }}>
              You followed an old link, or a plan version was deleted. Nothing's broken — try one of these instead.
            </div>

            <div className="card-flush" style={{ padding: "12px 16px", textAlign: "left", marginBottom: 20 }}>
              <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.18em", textTransform: "uppercase" }}>● ATTEMPTED PATH</div>
              <div className="mono" style={{ fontSize: 13, marginTop: 6, color: "var(--fg)", wordBreak: "break-all" }}>/plans/v12/sessions/9c4-archive-2025</div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, maxWidth: 460, margin: "0 auto" }}>
              {[["Today", I.home], ["Plan", I.plan], ["Workouts", I.workout]].map(([l, ic]) => (
                <div key={l} className="card" style={{ padding: "14px 12px", display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
                  <Ic d={ic} size={18} />
                  <div style={{ fontSize: 12, fontWeight: 600 }}>{l}</div>
                </div>
              ))}
            </div>
            <div className="btn btn-text" style={{ marginTop: 18, color: "var(--fg-3)" }}>Or search — ⌘ K</div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// G9. PERMISSION DENIED — non-admin hitting an admin route
// ═══════════════════════════════════════════════════════════════════
const ScreenPermissionDenied = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="home" />
      <div className="page">
        <TopBar crumbs={["Admin", "Telemetry"]} />
        <div className="page-body" style={{ display: "grid", placeItems: "center" }}>
          <div style={{ maxWidth: 560, width: "100%" }}>
            <div style={{ textAlign: "center", marginBottom: 24 }}>
              <div style={{ width: 80, height: 80, margin: "0 auto 18px", borderRadius: "50%", background: "color-mix(in oklab, var(--warn) 15%, transparent)", color: "var(--warn)", display: "grid", placeItems: "center", border: "1px solid color-mix(in oklab, var(--warn) 40%, transparent)" }}>
                <Ic d={I.gear} size={36} />
              </div>
              <Eyebrow style={{ color: "var(--warn)" }}>● PERMISSION DENIED · 403</Eyebrow>
              <h1 style={{ fontSize: 32, fontWeight: 700, letterSpacing: "-0.02em", margin: "10px 0 10px" }}>
                That page needs the admin role.
              </h1>
              <div style={{ color: "var(--fg-3)", fontSize: 14, lineHeight: 1.55, maxWidth: 440, margin: "0 auto" }}>
                Your account has the <b>Athlete · Pro</b> role. Admin telemetry, audit log, and user management aren't included.
              </div>
            </div>

            <div className="card" style={{ padding: 18 }}>
              <Eyebrow>What you can do</Eyebrow>
              <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 12 }}>
                {[
                  ["Request access",   "Reach your workspace admin. If you don't know who that is, support can route it.", "Ask admin"],
                  ["Switch workspaces", "You belong to 2 workspaces — try the other one if it has admin access.", "Switch"],
                  ["Head back",        "Return to your last page or the Today view.", "Go to Today"],
                ].map(([k, v, cta], i) => (
                  <div key={i} style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 14, alignItems: "center", paddingTop: i > 0 ? 12 : 0, borderTop: i > 0 ? "1px solid var(--hairline-2)" : "none" }}>
                    <div>
                      <div style={{ fontSize: 14, fontWeight: 600 }}>{k}</div>
                      <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 4 }}>{v}</div>
                    </div>
                    <div className="btn btn-ghost btn-sm">{cta} →</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="card-flush" style={{ marginTop: 18, padding: "14px 18px", fontFamily: "var(--mono)", fontSize: 11, color: "var(--fg-2)", lineHeight: 1.7 }}>
              <div>attempted_route: <span style={{ color: "var(--accent)" }}>/admin/telemetry_refresh</span></div>
              <div>required_role: admin</div>
              <div>your_roles: athlete, athlete_pro</div>
              <div>request_id: req_5b91c2d4</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// G10. PLAN IMPORT · JSON PARSE ERROR
// ═══════════════════════════════════════════════════════════════════
const ScreenPlanImportError = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="plan" />
      <div className="page">
        <TopBar crumbs={["Plan", "Import", "Validation failed"]} actions={<div className="btn btn-ghost">Reset · paste again</div>} />
        <div className="page-body">
          <Eyebrow style={{ color: "var(--bad)" }}>● JSON PARSE FAILED · LINE 47</Eyebrow>
          <h1 className="page-title" style={{ marginTop: 8 }}>Almost — 2 issues to fix.</h1>
          <div className="page-sub">We paused at the first parse error. Fix it and we'll re-validate the rest. Schema reference is open on the right.</div>

          <div style={{ marginTop: 22, display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 18 }}>
            {/* CODE GUTTER */}
            <div className="card" style={{ padding: 0, overflow: "hidden" }}>
              <div style={{ padding: "12px 18px", display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: "1px solid var(--hairline-2)" }}>
                <Eyebrow>● paste.json · 132 lines</Eyebrow>
                <div style={{ display: "flex", gap: 6 }}>
                  <Pill tone="bad">2 ERRORS</Pill>
                  <Pill tone="warn">1 WARN</Pill>
                </div>
              </div>
              <div style={{ fontFamily: "var(--mono)", fontSize: 12, lineHeight: 1.65, padding: "10px 0" }}>
                {[
                  [44, "    {", null],
                  [45, "      \"day\": \"Mon\",", null],
                  [46, "      \"type\": \"interval\",", null],
                  [47, "      \"target_pace\": \"5:14/mi\"", "error"],
                  [48, "      \"target_hr\": [165, 175]", null],
                  [49, "    },", null],
                  [50, "", null],
                  [51, "    {", null],
                  [52, "      \"day\": \"Wed\",", null],
                  [53, "      \"discipline\": \"swim\",", "warn"],
                  [54, "      \"distance_m\": 2400", null],
                  [55, "    }", null],
                ].map(([n, code, tone]) => (
                  <div key={n} style={{
                    display: "grid", gridTemplateColumns: "44px 1fr", padding: "1px 0",
                    background: tone === "error" ? "color-mix(in oklab, var(--bad) 12%, transparent)" : tone === "warn" ? "color-mix(in oklab, var(--warn) 8%, transparent)" : "transparent",
                    borderLeft: "3px solid " + (tone === "error" ? "var(--bad)" : tone === "warn" ? "var(--warn)" : "transparent"),
                  }}>
                    <div style={{ textAlign: "right", paddingRight: 12, color: "var(--fg-4)" }}>{n}</div>
                    <div style={{ paddingRight: 14, color: tone === "error" ? "var(--bad)" : tone === "warn" ? "var(--warn)" : "var(--fg-2)", whiteSpace: "pre" }}>{code}</div>
                  </div>
                ))}
                <div style={{ padding: "8px 14px 8px 58px", color: "var(--fg-4)", fontSize: 11 }}>… 120 more lines</div>
              </div>
            </div>

            {/* RIGHT — issues + schema */}
            <div className="stack">
              <div className="card" style={{ padding: 0 }}>
                <div style={{ padding: "12px 18px", borderBottom: "1px solid var(--hairline-2)" }}>
                  <Eyebrow style={{ color: "var(--bad)" }}>● ISSUES · 3</Eyebrow>
                </div>
                {[
                  ["error", "L47 · Missing comma", "Properties separated by comma. Add `,` after `target_pace`."],
                  ["error", "L96 · Unknown enum value", "`discipline: \"hike\"` isn't supported. Valid: run · ride · swim · strength · mobility."],
                  ["warn",  "L53 · Discipline shadowed", "`type` is preferred over `discipline` (v3 schema). Will be coerced."],
                ].map(([t, k, v], i, a) => (
                  <div key={i} style={{ padding: "12px 18px", borderBottom: i < a.length - 1 ? "1px solid var(--hairline-2)" : "none", display: "grid", gridTemplateColumns: "16px 1fr", gap: 10 }}>
                    <div style={{ width: 8, height: 8, borderRadius: 999, background: t === "error" ? "var(--bad)" : "var(--warn)", marginTop: 6 }} />
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600 }}>{k}</div>
                      <div style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 3, lineHeight: 1.5 }}>{v}</div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="card-flush" style={{ padding: "14px 18px" }}>
                <Eyebrow>Schema · session entry</Eyebrow>
                <div className="mono" style={{ fontSize: 11, lineHeight: 1.65, color: "var(--fg-2)", marginTop: 8 }}>
                  {`{
  day:         "Mon"…"Sun",
  type:        "easy" | "interval" | …,
  target_pace: "m:ss/mi",
  target_hr:   [low, high],
  duration_m:  number,
  notes?:      string
}`}
                </div>
              </div>

              <div style={{ display: "flex", gap: 8 }}>
                <div className="btn btn-ghost" style={{ flex: 1, justifyContent: "center" }}>Download schema</div>
                <div className="btn btn-primary" style={{ flex: 1, justifyContent: "center" }}><Ic d={I.check} size={12} sw={2.4} /> Re-validate</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// G11. INLINE FORM VALIDATION — race form with multiple bad fields
// ═══════════════════════════════════════════════════════════════════
const ScreenFormErrors = () => {
  const FieldErr = ({ label, value, error }) => (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
        <span className="mono" style={{ fontSize: 9, letterSpacing: "0.22em", textTransform: "uppercase", color: "var(--fg-3)" }}>● {label.toUpperCase()}</span>
        {error && <span className="mono" style={{ fontSize: 9, letterSpacing: "0.22em", textTransform: "uppercase", color: "var(--bad)" }}>✕ INVALID</span>}
      </div>
      <div style={{ display: "flex", alignItems: "center", height: 40, padding: "0 12px", background: "var(--bg-2)", border: "1px solid " + (error ? "var(--bad)" : "var(--hairline-2)"), borderRadius: 4 }}>
        <span style={{ flex: 1, fontSize: 14, color: error ? "var(--bad)" : "var(--fg)" }}>{value}</span>
      </div>
      {error && <div style={{ fontSize: 12, color: "var(--bad)", marginTop: 6, display: "flex", alignItems: "center", gap: 6 }}><span style={{ width: 12, height: 12, borderRadius: "50%", background: "var(--bad)", color: "var(--ink)", display: "grid", placeItems: "center", fontSize: 9, fontWeight: 700 }}>!</span>{error}</div>}
    </div>
  );
  return (
    <div className="screen">
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <Sidebar active="plan" />
        <div className="page">
          <TopBar crumbs={["Profile", "Edit target race"]} />
          <div className="page-body" style={{ display: "grid", placeItems: "start center" }}>
            <div style={{ maxWidth: 640, width: "100%" }}>
              {/* error summary */}
              <div style={{ padding: 18, border: "1px solid color-mix(in oklab, var(--bad) 40%, transparent)", background: "color-mix(in oklab, var(--bad) 8%, transparent)", borderRadius: 6, marginBottom: 24, display: "flex", gap: 14, alignItems: "flex-start" }}>
                <div style={{ width: 32, height: 32, borderRadius: "50%", background: "color-mix(in oklab, var(--bad) 25%, transparent)", color: "var(--bad)", display: "grid", placeItems: "center", flexShrink: 0 }}>
                  <Ic d={I.x} size={14} sw={2.5} />
                </div>
                <div style={{ flex: 1 }}>
                  <Eyebrow style={{ color: "var(--bad)" }}>● 3 FIELDS NEED ATTENTION</Eyebrow>
                  <div style={{ fontSize: 16, fontWeight: 700, marginTop: 6 }}>Fix these before saving.</div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 10 }}>
                    {["Race date","Goal time","Distance"].map(t => (
                      <Pill tone="bad" key={t}>↑ {t}</Pill>
                    ))}
                  </div>
                </div>
              </div>

              <Eyebrow>● TARGET RACE</Eyebrow>
              <h2 style={{ fontSize: 24, fontWeight: 700, letterSpacing: "-0.015em", margin: "8px 0 22px" }}>Boston Marathon 2026</h2>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
                <FieldErr label="Race name" value="Boston Marathon 2026" />
                <FieldErr label="Distance" value="42.4 km" error="Must be a supported distance — 5K, 10K, half, marathon, ultra." />
                <FieldErr label="Race date" value="2025-04-20" error="Date is in the past. Target races must be ≥ 4 weeks ahead." />
                <FieldErr label="Goal time" value="2:48" error="Format is hh:mm:ss (e.g. 02:48:00). Just two parts isn't valid." />
                <FieldErr label="Course profile" value="Hilly · rolling" />
                <FieldErr label="Priority" value="A-race" />
              </div>

              <div style={{ marginTop: 26, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div className="mono" style={{ fontSize: 10, letterSpacing: "0.18em", color: "var(--fg-3)" }}>AUTO-SAVED · LAST 14:22</div>
                <div style={{ display: "flex", gap: 8 }}>
                  <div className="btn btn-ghost">Discard changes</div>
                  <div className="btn btn-primary" style={{ opacity: 0.55 }}>Save · 3 errors</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════
// G12. ERROR SHELL — shared layout for all error pages
//   Pattern: icon · code · title · message · diagnostic · retry + support CTAs
//   Used by 404, plan-gen error, and generic error.
// ═══════════════════════════════════════════════════════════════════
const ErrorShell = ({
  active = "home",
  crumbs = ["Error"],
  tone = "bad",                  // bad | warn
  code,                          // "404", "500", "PLAN-GEN-FAILED" …
  glyph = I.x,
  glyphSw = 2,
  title,
  message,
  diag = [],                     // [["request_id", "req_…"], …]
  retryLabel = "Try again",
  retryIcon = I.bolt,
  showRetry = true,
  supportSubject,                // pre-fills mailto subject
  children,                      // optional extra block above the CTAs
}) => {
  const toneVar = tone === "warn" ? "var(--warn)" : "var(--bad)";
  return (
    <div className="screen">
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <Sidebar active={active} />
        <div className="page">
          <TopBar crumbs={crumbs} />
          <div className="page-body" style={{ display: "grid", placeItems: "center", padding: "32px 28px" }}>
            <div style={{ maxWidth: 560, width: "100%", textAlign: "center" }}>
              <div style={{
                width: 80, height: 80, margin: "0 auto 18px", borderRadius: "50%",
                background: `color-mix(in oklab, ${toneVar} 15%, transparent)`,
                color: toneVar, display: "grid", placeItems: "center",
                border: `1px solid color-mix(in oklab, ${toneVar} 35%, transparent)`,
              }}>
                <Ic d={glyph} size={36} sw={glyphSw} />
              </div>
              <Eyebrow style={{ color: toneVar }}>● {code}</Eyebrow>
              <h1 style={{ fontSize: 32, fontWeight: 700, letterSpacing: "-0.02em", margin: "10px 0 12px" }}>
                {title}
              </h1>
              <div style={{ color: "var(--fg-3)", fontSize: 14, lineHeight: 1.55, maxWidth: 460, margin: "0 auto 22px" }}>
                {message}
              </div>

              {children}

              {diag.length > 0 && (
                <div className="card-flush" style={{ padding: "12px 16px", textAlign: "left", marginTop: 18, marginBottom: 22, fontFamily: "var(--mono)", fontSize: 11, color: "var(--fg-2)", lineHeight: 1.7 }}>
                  <div className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.22em", textTransform: "uppercase", marginBottom: 6 }}>● DIAGNOSTIC · INCLUDED IF YOU EMAIL US</div>
                  {diag.map(([k, v], i) => (
                    <div key={i}>{k}: <span style={{ color: i === 0 ? "var(--accent)" : "var(--fg-2)" }}>{v}</span></div>
                  ))}
                </div>
              )}

              <div style={{ display: "flex", gap: 10, justifyContent: "center", flexWrap: "wrap" }}>
                <div className="btn btn-ghost">
                  <Ic d={I.bell} size={12} /> Email help@aidstation.pro
                </div>
                {showRetry && (
                  <div className="btn btn-primary">
                    <Ic d={retryIcon} size={12} sw={2} /> {retryLabel}
                  </div>
                )}
              </div>
              <div className="mono" style={{ marginTop: 16, fontSize: 10, letterSpacing: "0.18em", color: "var(--fg-4)" }}>
                ⓘ MAILTO INCLUDES THE DIAGNOSTIC ABOVE · NO ACTION REQUIRED FROM YOU
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// — 404 (replaces previous Screen404 with the shell version) —
const Screen404v2 = () => (
  <ErrorShell
    code="404 · NO SUCH ROUTE"
    tone="bad"
    glyph={I.x}
    title="You're off trail."
    message="This route isn't on the map — an old link, or a plan version that's since been archived. No harm done. Here's the way back."
    showRetry={false}
    crumbs={["?", "Not found"]}
    diag={[
      ["attempted_path", "/plans/v12/sessions/9c4-archive-2025"],
      ["referrer",       "/notifications"],
      ["request_id",     "req_4b9e2a7c"],
    ]}
  >
    <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, maxWidth: 440, margin: "0 auto" }}>
      {[["Today", I.home], ["Plan", I.plan], ["Workouts", I.workout]].map(([l, ic]) => (
        <div key={l} className="card" style={{ padding: "14px 12px", display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
          <Ic d={ic} size={18} />
          <div style={{ fontSize: 12, fontWeight: 600 }}>{l}</div>
        </div>
      ))}
    </div>
  </ErrorShell>
);

// — Plan generation failed (replaces previous ScreenPlanGenFailed in states.jsx) —
const ScreenPlanGenFailedV2 = () => (
  <ErrorShell
    active="plan"
    crumbs={["Plan", "Generation failed"]}
    tone="bad"
    code="PLAN-GEN-FAILED · STEP 4 OF 6"
    glyph={I.x}
    title="The build stalled."
    message="We made it through base and build, then hit the wall on the peak block — your weekly long session won't fit the windows you gave us. Your inputs are saved; tweak one thing and run it again."
    retryLabel="Retry generation"
    retryIcon={I.bolt}
    diag={[
      ["generation_id",          "gen_9c40e2a1"],
      ["last_completed_phase",   "build_synthesis"],
      ["failed_phase",           "peak_block_synthesis"],
      ["error",                  "InfeasibleScheduleConstraint"],
    ]}
  >
    <div className="card" style={{ textAlign: "left", padding: 0, maxWidth: 480, margin: "0 auto" }}>
      <div style={{ padding: "12px 18px", borderBottom: "1px solid var(--hairline-2)" }}>
        <Eyebrow>Suggested fixes · pick one, then retry</Eyebrow>
      </div>
      {[
        ["Extend Saturday window to 3 h",  "The peak block needs the weekly long session."],
        ["Move long session to Sunday",     "If Sunday is rest, enable it for the peak block."],
        ["Drop goal one tier",              "Sub-3:00 → BQ qualifying. Peak block becomes feasible."],
      ].map(([k, v], i, a) => (
        <div key={i} style={{ padding: "12px 18px", borderBottom: i < a.length - 1 ? "1px solid var(--hairline-2)" : "none", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
          <div>
            <div style={{ fontWeight: 600, fontSize: 13 }}>{k}</div>
            <div style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 3 }}>{v}</div>
          </div>
          <div className="btn btn-ghost btn-sm">FIX →</div>
        </div>
      ))}
    </div>
  </ErrorShell>
);

// — Generic error (the catch-all: parse failures, OAuth, permission, server 500, …) —
const ScreenErrorGeneric = () => (
  <ErrorShell
    active="link"
    crumbs={["Connections", "Sync"]}
    tone="bad"
    code="500 · SOMETHING BROKE"
    glyph={I.x}
    title="Something seized up."
    message="Whatever you just tried — a provider sync, a file upload, a save — cramped up on our end. Your data's safe; nothing was committed. Catch your breath and try again."
    retryLabel="Try again"
    retryIcon={I.bolt}
    diag={[
      ["request_id",  "req_a72e9f04"],
      ["action",      "POST /connections/wahoo/refresh"],
      ["status",      "500 internal_error"],
      ["timestamp",   "2026-05-27T14:24:07Z"],
    ]}
  />
);

Object.assign(window, {
  OnbAccount,
  ScreenProfileEmpty,
  ScreenWellnessFitImport,
  ScreenNotifSettings,
  ScreenSearchOverlay,
  ScreenShortcuts,
  ErrorShell,
  Screen404v2, ScreenPlanGenFailedV2, ScreenErrorGeneric,
});
