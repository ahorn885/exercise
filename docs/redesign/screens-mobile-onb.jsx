/* AIDSTATION redesign — Mobile onboarding parity (7 steps)
   Mirrors the desktop onb flow (screens-desktop-b.jsx) in portrait.
   One focused decision per scroll-screen; same content, restructured. */

// ─── Mobile onboarding shell ────────────────────────────────────
const MobileOnbShell = ({ step, title, sub, children, nextLabel = "Continue", backLabel = "Back" }) => (
  <div className="screen">
    <StatusBar />
    {/* Brand + skip + progress */}
    <div style={{ padding: "8px 16px 6px", display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <AsMark size={22} />
        <Wordmark />
      </div>
      <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.18em" }}>SKIP →</span>
    </div>
    {/* Progress dots */}
    <div style={{ padding: "8px 16px 10px", display: "flex", gap: 6, alignItems: "center", flexShrink: 0 }}>
      {[1,2,3,4,5,6,7].map(n => (
        <div key={n} style={{
          flex: 1, height: 3, borderRadius: 999,
          background: n < step ? "var(--fg-3)" : n === step ? "var(--accent)" : "var(--bg-3)",
        }} />
      ))}
      <span className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.18em", marginLeft: 8 }}>{step}/7</span>
    </div>
    {/* Body */}
    <div style={{ flex: 1, overflow: "auto", padding: "10px 16px 16px" }}>
      <Eyebrow accent>● STEP 0{step} · {sub.toUpperCase()}</Eyebrow>
      <div style={{ fontSize: 26, fontWeight: 800, letterSpacing: "-0.025em", lineHeight: 1.1, margin: "8px 0 14px" }}>{title}</div>
      {children}
    </div>
    {/* Footer */}
    <div style={{ padding: "12px 16px 22px", borderTop: "1px solid var(--hairline-2)", display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
      {step > 1 && <div className="btn btn-text" style={{ color: "var(--fg-3)" }}><Ic d={I.chevL} size={12} /> {backLabel}</div>}
      <div style={{ flex: 1 }} />
      <div className="btn btn-primary" style={{ padding: "11px 16px" }}>{nextLabel} <Ic d={I.arrow} size={12} sw={2} /></div>
    </div>
  </div>
);

// — small atoms reused inline —
const MobField = ({ label, value, type = "text", hint, valid, error }) => (
  <div>
    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
      <span className="mono" style={{ fontSize: 9, letterSpacing: "0.22em", textTransform: "uppercase", color: "var(--fg-3)" }}>● {label.toUpperCase()}</span>
      {valid && <span className="mono" style={{ fontSize: 9, letterSpacing: "0.22em", textTransform: "uppercase", color: "var(--good)" }}>✓ OK</span>}
      {error && <span className="mono" style={{ fontSize: 9, letterSpacing: "0.22em", textTransform: "uppercase", color: "var(--bad)" }}>✕ INVALID</span>}
    </div>
    <div style={{ display: "flex", alignItems: "center", gap: 10, height: 44, padding: "0 12px", background: "var(--bg-2)", border: "1px solid " + (error ? "var(--bad)" : "var(--hairline-2)"), borderRadius: 4 }}>
      <span style={{ flex: 1, fontSize: 15, color: "var(--fg)", fontFamily: type === "password" ? "var(--mono)" : "var(--sans)", letterSpacing: type === "password" ? "0.2em" : 0 }}>
        {type === "password" ? "•".repeat(value.length) : value}
      </span>
      {type === "password" && <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.18em" }}>SHOW</span>}
    </div>
    {hint && <div style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 5 }}>{hint}</div>}
    {error && <div style={{ fontSize: 11, color: "var(--bad)", marginTop: 5 }}>{error}</div>}
  </div>
);

const MobCheck = ({ checked, label }) => (
  <label style={{ display: "flex", gap: 10, alignItems: "flex-start", fontSize: 12, color: "var(--fg-2)", lineHeight: 1.45 }}>
    <span style={{ width: 16, height: 16, borderRadius: 3, border: "1px solid " + (checked ? "var(--accent)" : "var(--hairline)"), background: checked ? "var(--accent)" : "transparent", color: "var(--ink)", display: "grid", placeItems: "center", flexShrink: 0, marginTop: 1 }}>
      {checked && <Ic d={I.check} size={10} sw={3} />}
    </span>
    <span>{label}</span>
  </label>
);

// ═══════════════════════════════════════════════════════════════════
// STEP 01 · ACCOUNT CREATION
// ═══════════════════════════════════════════════════════════════════
const MobileOnbAccount = () => {
  const pwRules = [["≥ 10 chars", true], ["Mixed case", true], ["A number", true], ["A symbol", false]];
  return (
    <MobileOnbShell step={1} sub="Create your account" title="Start with the basics." nextLabel="Create account">
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 12 }}>
        <MobField label="First name" value="Andrew" />
        <MobField label="Last name"  value="Horn" />
      </div>
      <div style={{ marginBottom: 12 }}>
        <MobField label="Email" value="andrew@aidstation.run" valid />
      </div>
      <div>
        <MobField label="Password" value="aidstationFTW21" type="password" />
      </div>
      <div style={{ marginTop: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
          <span className="mono" style={{ fontSize: 9, letterSpacing: "0.22em", textTransform: "uppercase", color: "var(--fg-3)" }}>● STRENGTH</span>
          <span className="mono" style={{ fontSize: 9, letterSpacing: "0.22em", textTransform: "uppercase", color: "var(--warn)" }}>FAIR · ADD SYMBOL</span>
        </div>
        <div style={{ display: "flex", gap: 4, height: 4 }}>
          {[0,1,2,3].map(i => <div key={i} style={{ flex: 1, background: i < 3 ? "var(--warn)" : "var(--bg-3)" }} />)}
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px 14px", marginTop: 10 }}>
          {pwRules.map(([t, ok], i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: ok ? "var(--fg-2)" : "var(--fg-4)" }}>
              {ok ? <Ic d={I.check} size={12} sw={2.5} /> : <span style={{ width: 8, height: 8, borderRadius: "50%", border: "1px solid var(--fg-4)" }} />}
              {t}
            </div>
          ))}
        </div>
      </div>

      <div style={{ marginTop: 20, padding: 14, border: "1px solid var(--hairline-2)", borderRadius: 6, display: "flex", flexDirection: "column", gap: 10 }}>
        <MobCheck checked label="I'm 16 or older." />
        <MobCheck checked label={<>I agree to the <u>Terms</u> and <u>Privacy notice</u>.</>} />
        <MobCheck label="Email me product updates (1–2 / month)." />
      </div>

      <div style={{ marginTop: 16, fontSize: 12, color: "var(--fg-3)", textAlign: "center" }}>
        Already have an account? <span style={{ color: "var(--fg)", fontWeight: 600 }}>Sign in →</span>
      </div>
    </MobileOnbShell>
  );
};

// ═══════════════════════════════════════════════════════════════════
// STEP 02 · CONNECT PROVIDERS
// ═══════════════════════════════════════════════════════════════════
const MobileOnbConnect = () => (
  <MobileOnbShell step={2} sub="Connect your providers" title={<>Bring in what you <span style={{ color: "var(--accent)" }}>already track.</span></>}>
    <div style={{ fontSize: 13, color: "var(--fg-3)", lineHeight: 1.5, marginBottom: 16 }}>
      Pull activity, sleep, and heart-rate data so your plan reacts to what you actually do — not what you remember to log.
    </div>

    {[
      ["Strava",  "#FC4C02", "Activity · Routes · HR · Power",    "popular"],
      ["Wahoo",   "#0093D0", "Activity · HR · Power · Recovery",  null],
      ["Whoop",   "#000000", "Recovery · Sleep · Strain",          null],
      ["Garmin",  "#000000", "Activity · Wellness · Sleep",        "paused"],
      ["COROS",   "#FF6B00", "Activity · HR · Power",              null],
    ].map(([name, color, desc, state], i) => (
      <div key={name} className="card" style={{ padding: 14, marginBottom: 8, display: "grid", gridTemplateColumns: "40px 1fr auto", gap: 12, alignItems: "center", opacity: state === "paused" ? 0.6 : 1 }}>
        <div style={{ width: 40, height: 40, borderRadius: 6, background: color, color: "white", display: "grid", placeItems: "center", fontFamily: "var(--mono)", fontWeight: 800, fontSize: 18 }}>
          {name[0]}
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 600 }}>{name}</div>
          <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em", marginTop: 3 }}>{desc}</div>
        </div>
        {state === "popular" ? <div className="btn btn-primary btn-sm">CONNECT</div>
          : state === "paused" ? <Pill tone="warn">PAUSED</Pill>
          : <div className="btn btn-ghost btn-sm">CONNECT</div>}
      </div>
    ))}

    <div className="card-flush" style={{ padding: 12, marginTop: 10 }}>
      <Eyebrow>What you're consenting to</Eyebrow>
      <div style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 6, lineHeight: 1.5 }}>
        Activity (workouts, HR, pace, power) · Wellness (weight, RHR, recovery) · Sleep summaries · Profile (name + user ID).
      </div>
    </div>

    <div className="btn btn-text" style={{ marginTop: 14, justifyContent: "center", color: "var(--fg-3)", display: "flex" }}>
      Or skip — upload .FIT manually later →
    </div>
  </MobileOnbShell>
);

// ═══════════════════════════════════════════════════════════════════
// STEP 03 · PREFILL REVIEW
// ═══════════════════════════════════════════════════════════════════
const MobileOnbPrefill = () => {
  const fields = [
    { label: "Resting HR",      unit: "bpm",      current: "48", curSrc: "STRAVA · 2D AGO",  suggested: "47",   sugProv: "Wahoo",  sugDays: "today" },
    { label: "VO₂ max",         unit: "ml/kg",    current: "62", curSrc: "SELF-REPORTED",    suggested: "63",   sugProv: "Strava", sugDays: "May 18" },
    { label: "Body weight",     unit: "lb",       current: "162", curSrc: "MANUAL",          suggested: "162.4",sugProv: "Wahoo",  sugDays: "today" },
    { label: "Threshold pace",  unit: "/mi",      current: "6:42", curSrc: "TEST · MAY 4",   suggested: "6:38", sugProv: "Strava", sugDays: "May 22" },
    { label: "FTP",             unit: "watts",    current: null, missing: true },
  ];
  return (
    <MobileOnbShell step={3} sub="Review your data" title={<>We pulled <span style={{ color: "var(--accent)" }}>4 of 5</span> baselines.</>}>
      <div style={{ fontSize: 13, color: "var(--fg-3)", lineHeight: 1.5, marginBottom: 14 }}>
        Tap the value to use for each — we'll keep prefilling automatically as new data arrives.
      </div>

      {fields.map((f, i) => (
        <div key={i} className="card" style={{ padding: 14, marginBottom: 8 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <div style={{ fontSize: 14, fontWeight: 600 }}>{f.label}</div>
              <div className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--fg-3)", textTransform: "uppercase", marginTop: 2 }}>{f.unit}</div>
            </div>
            {f.missing && <Pill tone="warn">NO DATA</Pill>}
          </div>

          {!f.missing ? (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 10 }}>
              <div style={{ padding: "10px 12px", border: "1px solid var(--hairline-2)", borderRadius: 4 }}>
                <div className="eyebrow" style={{ fontSize: 8 }}>Current</div>
                <div className="num" style={{ fontFamily: "var(--mono)", fontSize: 18, fontWeight: 700, marginTop: 3 }}>{f.current}</div>
                <div className="mono" style={{ fontSize: 8, letterSpacing: "0.14em", color: "var(--fg-4)", marginTop: 3 }}>{f.curSrc}</div>
              </div>
              <div style={{ padding: "10px 12px", border: "1px solid color-mix(in oklab, var(--accent) 40%, transparent)", background: "color-mix(in oklab, var(--accent) 8%, transparent)", borderRadius: 4 }}>
                <div className="eyebrow accent" style={{ fontSize: 8 }}>{f.sugProv} suggests</div>
                <div className="num" style={{ fontFamily: "var(--mono)", fontSize: 18, fontWeight: 700, marginTop: 3, color: "var(--accent)" }}>{f.suggested}</div>
                <div className="mono" style={{ fontSize: 8, letterSpacing: "0.14em", color: "var(--fg-4)", marginTop: 3 }}>AS OF {f.sugDays.toUpperCase()}</div>
              </div>
            </div>
          ) : (
            <div className="btn btn-ghost btn-sm" style={{ marginTop: 10, width: "100%", justifyContent: "center" }}>ENTER MANUALLY</div>
          )}
        </div>
      ))}
    </MobileOnbShell>
  );
};

// ═══════════════════════════════════════════════════════════════════
// STEP 04 · SCHEDULE
// ═══════════════════════════════════════════════════════════════════
const MobileOnbSchedule = () => {
  const days = [
    { d: "Mon", on: true,  start: "06:00", dur: 60 },
    { d: "Tue", on: true,  start: "06:00", dur: 75 },
    { d: "Wed", on: true,  start: "06:00", dur: 60 },
    { d: "Thu", on: false, start: "—",     dur: 0 },
    { d: "Fri", on: true,  start: "06:00", dur: 60 },
    { d: "Sat", on: true,  start: "07:30", dur: 150 },
    { d: "Sun", on: true,  start: "08:00", dur: 90 },
  ];
  const totalH = days.reduce((s, d) => s + d.dur, 0) / 60;
  return (
    <MobileOnbShell step={4} sub="Schedule & availability" title={<>When can you <span style={{ color: "var(--accent)" }}>actually train?</span></>}>
      <div className="card" style={{ padding: 14, marginBottom: 12, display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
        {[["Days","6 / 7"],["H/wk", totalH.toFixed(1)],["Longest","Sat · 2.5h"]].map(([k,v]) => (
          <div key={k}>
            <div className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.18em", textTransform: "uppercase" }}>● {k}</div>
            <div className="num" style={{ fontFamily: "var(--mono)", fontSize: 16, fontWeight: 700, marginTop: 4 }}>{v}</div>
          </div>
        ))}
      </div>

      {days.map((d, i) => (
        <div key={i} className="card" style={{ padding: 12, marginBottom: 6, display: "grid", gridTemplateColumns: "auto 1fr auto auto", gap: 12, alignItems: "center", opacity: d.on ? 1 : 0.55 }}>
          <div className="mono" style={{ fontSize: 12, fontWeight: 700, width: 36 }}>{d.d.toUpperCase()}</div>
          <div className="mono" style={{ fontSize: 11, color: "var(--fg-3)", letterSpacing: "0.14em" }}>
            {d.on ? `${d.start} · ${d.dur} min` : "Rest day"}
          </div>
          <Toggle on={d.on} />
        </div>
      ))}

      <div className="card-flush" style={{ padding: 12, marginTop: 12, fontSize: 12, color: "var(--fg-3)", lineHeight: 1.5 }}>
        Plan auto-respects these windows. Tap a day to set a second slot (AM + PM) or change duration.
      </div>
    </MobileOnbShell>
  );
};

// ═══════════════════════════════════════════════════════════════════
// STEP 05 · SKILLS
// ═══════════════════════════════════════════════════════════════════
const MobileOnbSkills = () => {
  const skills = [
    { name: "Swim freestyle",        desc: "200m+ continuous, no stops.",          checked: true },
    { name: "Open-water swimming",   desc: "Wetsuit, sighting, course nav.",       checked: false },
    { name: "Road cycling",          desc: "2+ hr on a road bike.",                checked: true },
    { name: "Mountain biking",       desc: "Technical singletrack & drops.",       checked: false },
    { name: "Power meter (bike)",    desc: "Calibrated bike power.",               checked: true },
    { name: "Running power",         desc: "Stryd / watch power data.",            checked: false },
    { name: "Trail running",         desc: "Rocky / rooted technical trail.",      checked: true },
    { name: "Strength · free weight", desc: "Squat / DL / bench / OHP solid form.", checked: true },
    { name: "Yoga / mobility",       desc: "Regular dedicated practice.",          checked: false },
    { name: "Climbing 5.10+",        desc: "Outdoor sport / trad / boulder.",      checked: false },
    { name: "Paddling",              desc: "Kayak / SUP — flat or whitewater.",    checked: false },
    { name: "Backcountry skiing",    desc: "Skinning · AT setup · basics.",        checked: false },
  ];
  const count = skills.filter(s => s.checked).length;
  return (
    <MobileOnbShell step={5} sub="Skills & capabilities" title={<>What can you <span style={{ color: "var(--accent)" }}>already do?</span></>}>
      <div style={{ fontSize: 13, color: "var(--fg-3)", lineHeight: 1.5, marginBottom: 14 }}>
        Check what's true today — we use this to filter which kinds of sessions show up. Editable later.
      </div>

      {skills.map((s, i) => (
        <div key={i} style={{
          padding: "12px 14px", marginBottom: 6, borderRadius: 6,
          background: s.checked ? "color-mix(in oklab, var(--accent) 6%, var(--bg-2))" : "var(--bg-2)",
          border: "1px solid " + (s.checked ? "color-mix(in oklab, var(--accent) 30%, var(--hairline-2))" : "var(--hairline-2)"),
          display: "grid", gridTemplateColumns: "20px 1fr", gap: 12, alignItems: "flex-start",
        }}>
          <div style={{
            width: 18, height: 18, borderRadius: 3, marginTop: 1,
            border: "1px solid " + (s.checked ? "var(--accent)" : "var(--hairline)"),
            background: s.checked ? "var(--accent)" : "transparent",
            color: "var(--ink)", display: "grid", placeItems: "center",
          }}>{s.checked && <Ic d={I.check} size={11} sw={2.5} />}</div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600 }}>{s.name}</div>
            <div style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 2, lineHeight: 1.4 }}>{s.desc}</div>
          </div>
        </div>
      ))}

      <div className="mono" style={{ marginTop: 10, fontSize: 10, letterSpacing: "0.18em", color: "var(--fg-3)" }}>● {count} OF 12 CHECKED</div>
    </MobileOnbShell>
  );
};

// ═══════════════════════════════════════════════════════════════════
// STEP 06 · LOCATIONS
// ═══════════════════════════════════════════════════════════════════
const MobileOnbLocations = () => {
  const locs = [
    { name: "Home garage", addr: "Washington, DC", tags: ["Barbell","Squat rack","DBs to 50lb","Plates 405lb"], primary: true },
    { name: "Equinox Capitol Hill", addr: "320 Pennsylvania Ave SE", tags: ["Olympic platform","DBs to 150lb","Concept2","Sauna"], chain: "EQX" },
    { name: "Rock Creek loop", addr: "Beach Dr NW · 4.2 mi", tags: ["Rolling","Aid water MP2"], route: true },
  ];
  return (
    <MobileOnbShell step={6} sub="Your locations" title={<>Where do you <span style={{ color: "var(--accent)" }}>train?</span></>}>
      <div style={{ fontSize: 13, color: "var(--fg-3)", lineHeight: 1.5, marginBottom: 14 }}>
        Each location has an equipment profile — we filter exercises to what's actually available.
      </div>

      {/* Add row */}
      <div className="card" style={{ padding: 12, marginBottom: 12, display: "flex", alignItems: "center", gap: 10 }}>
        <Ic d={I.search} size={16} />
        <span style={{ flex: 1, fontSize: 13, color: "var(--fg-3)" }}>Search a gym, park, or address…</span>
        <div className="btn btn-primary btn-sm"><Ic d={I.plus} size={10} sw={2.4} /> ADD</div>
      </div>

      <Eyebrow style={{ display: "block", marginBottom: 8 }}>● 3 SAVED</Eyebrow>
      {locs.map((loc, i) => (
        <div key={i} className="card" style={{ padding: 14, marginBottom: 8 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <span style={{ fontWeight: 700, fontSize: 15 }}>{loc.name}</span>
            {loc.primary && <Pill tone="accent">PRIMARY</Pill>}
            {loc.chain && <Pill tone="solid">{loc.chain}</Pill>}
            {loc.route && <Pill tone="solid">ROUTE</Pill>}
          </div>
          <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em", marginTop: 6, textTransform: "uppercase" }}>△ {loc.addr}</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 10 }}>
            {loc.tags.map((t, j) => <Pill tone="solid" key={j}>{t}</Pill>)}
          </div>
        </div>
      ))}
    </MobileOnbShell>
  );
};

// ═══════════════════════════════════════════════════════════════════
// STEP 07 · TARGET RACE
// ═══════════════════════════════════════════════════════════════════
const MobileOnbRace = () => (
  <MobileOnbShell step={7} sub="Target race · anchor your plan" title={<>What are you <span style={{ color: "var(--accent)" }}>training for?</span></>} nextLabel="Generate plan">
    <div style={{ fontSize: 13, color: "var(--fg-3)", lineHeight: 1.5, marginBottom: 16 }}>
      The race date anchors taper, peak, and recovery. Editable later.
    </div>

    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <MobField label="Race name" value="Boston Marathon 2026" valid />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <MobField label="Distance" value="Marathon" />
        <MobField label="Course" value="Hilly · rolling" />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <MobField label="Race date" value="2026-04-20" />
        <MobField label="Priority" value="A-race" />
      </div>
      <MobField label="Goal time" value="02:48:00" hint="hh:mm:ss · 6:24/mi avg" />
    </div>

    {/* Computed preview */}
    <div className="card" style={{ marginTop: 18, padding: 14, background: "color-mix(in oklab, var(--accent) 8%, var(--bg-2))", borderColor: "color-mix(in oklab, var(--accent) 30%, transparent)" }}>
      <Eyebrow accent>● PLAN WINDOW</Eyebrow>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, marginTop: 10 }}>
        {[["Today","May 27"],["Race","Apr 20"],["Weeks","47"]].map(([k,v]) => (
          <div key={k}>
            <div className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.18em", textTransform: "uppercase" }}>{k}</div>
            <div className="num" style={{ fontFamily: "var(--mono)", fontSize: 16, fontWeight: 700, marginTop: 3 }}>{v}</div>
          </div>
        ))}
      </div>
      <div style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 10, lineHeight: 1.5 }}>
        Base 12wk · Build 16wk · Peak 12wk · Taper 3wk · Race 1wk · Recovery 3wk
      </div>
    </div>
  </MobileOnbShell>
);

Object.assign(window, {
  MobileOnbShell,
  MobileOnbAccount, MobileOnbConnect, MobileOnbPrefill, MobileOnbSchedule,
  MobileOnbSkills, MobileOnbLocations, MobileOnbRace,
});
