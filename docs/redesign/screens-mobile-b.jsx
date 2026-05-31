/* AIDSTATION redesign — Mobile screens (part 2)
   Exercises · Locations · Wellness · Connections · Profile · Plan refresh */

// ═══════════════════════════════════════════════════════════════════
// M5. MOBILE EXERCISES LIBRARY
// ═══════════════════════════════════════════════════════════════════
const MobileExercises = () => (
  <div className="screen">
    <StatusBar />
    <AppBar
      title="Exercises"
      left={<Ic d={I.menu} size={22} />}
      right={<Ic d={I.search} size={20} />}
    />

    {/* Plateau alert */}
    <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--hairline-2)", background: "color-mix(in oklab, var(--warn) 8%, transparent)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
        <Pill tone="warn">! PLATEAU</Pill>
        <span style={{ fontSize: 12, flex: 1, color: "var(--fg-2)" }}>1 exercise stalled ≥6 sessions</span>
        <span className="mono" style={{ fontSize: 10, color: "var(--accent)", letterSpacing: "0.14em" }}>REVIEW →</span>
      </div>
    </div>

    {/* Filter pills */}
    <div style={{ padding: "10px 16px", borderBottom: "1px solid var(--hairline-2)", display: "flex", gap: 6, overflowX: "auto" }}>
      {[["All", true], ["Bike", false], ["Foot", false], ["Water", false], ["Cross", false]].map(([l, active], i) => (
        <Pill key={i} tone={active ? "accent" : null}>{l.toString().toUpperCase()}</Pill>
      ))}
    </div>

    {/* Exercises list */}
    <div style={{ flex: 1, overflow: "auto" }}>
      {[
        { ex: "Back squat",        disc: "Foot",  reps: "3 × 5",  wt: "225 lb", out: "↑ progress" },
        { ex: "Romanian deadlift", disc: "Foot",  reps: "3 × 8",  wt: "185 lb", out: "→ hold" },
        { ex: "Bench press",       disc: "Cross", reps: "4 × 5",  wt: "165 lb", out: "↑ progress" },
        { ex: "Overhead press",    disc: "Cross", reps: "4 × 5",  wt: "110 lb", out: "↓ reduce", deload: true },
        { ex: "Pull-up",           disc: "Cross", reps: "4 × 6",  wt: "BW+25",  out: "↑ progress" },
        { ex: "Bent-over row",     disc: "Cross", reps: "4 × 8",  wt: "155 lb", out: "→ hold" },
        { ex: "Hip thrust",        disc: "Foot",  reps: "3 × 10", wt: "225 lb", out: "↑ progress" },
        { ex: "Front squat",       disc: "Foot",  reps: "3 × 5",  wt: "185 lb", out: "→ hold" },
      ].map((e, i) => {
        const up = e.out.includes("↑"), hold = e.out.includes("→"), down = e.out.includes("↓");
        return (
          <div key={i} style={{ padding: "14px 16px", borderBottom: "1px solid var(--hairline-2)", display: "flex", gap: 12, alignItems: "center" }}>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontWeight: 600, fontSize: 14 }}>{e.ex}</span>
                <Pill tone="solid">{e.disc}</Pill>
              </div>
              <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em", marginTop: 4 }}>
                {e.reps.toUpperCase()} · {e.wt.toUpperCase()}
              </div>
            </div>
            <div style={{ textAlign: "right", display: "flex", flexDirection: "column", gap: 4, alignItems: "flex-end" }}>
              <Pill tone={up ? "good" : hold ? "warn" : "bad"}>{e.out.toUpperCase()}</Pill>
              {e.deload && <span className="mono" style={{ fontSize: 9, color: "var(--bad)", letterSpacing: "0.12em" }}>DELOAD −10%</span>}
            </div>
          </div>
        );
      })}
      <div style={{ padding: 14, textAlign: "center", fontSize: 11, color: "var(--fg-3)" }} className="mono">
        SHOWING 8 OF 42 · 32 WITHOUT CURRENT RX
      </div>
    </div>

    <TabBar active="me" />
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// M6. MOBILE LOCATIONS
// ═══════════════════════════════════════════════════════════════════
const MobileLocations = () => (
  <div className="screen">
    <StatusBar />
    <AppBar
      title="Locations"
      left={<Ic d={I.menu} size={22} />}
      right={<div className="mono" style={{ fontSize: 10, letterSpacing: "0.18em", color: "var(--accent)" }}>+ ADD</div>}
    />

    {/* Search bar */}
    <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--hairline-2)", display: "flex", alignItems: "center", gap: 10, background: "var(--bg-2)" }}>
      <Ic d={I.search} size={14} />
      <span style={{ flex: 1, fontSize: 12, color: "var(--fg-3)" }}>Equinox, Planet Fitness, address…</span>
    </div>

    <div style={{ flex: 1, overflow: "auto", padding: "14px 16px" }}>
      <Eyebrow>3 saved · active</Eyebrow>
      <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 12 }}>
        {[
          { name: "Home garage", category: "MANUAL", items: 18, primary: true, tags: ["Barbell", "Squat rack", "Bench", "Pull-up bar", "DBs to 50lb"] },
          { name: "Equinox Capitol Hill", chain: "EQUINOX", items: 42, tags: ["Olympic platform", "Power racks", "DBs to 150lb", "Cable", "Sauna"] },
          { name: "Rock Creek loop", category: "ROUTE", items: 0, route: true, tags: ["4.2 mi loop", "Rolling", "Aid at MP2"] },
        ].map((loc, i) => (
          <div key={i} className="card" style={{ padding: 14 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                  <span style={{ fontWeight: 600, fontSize: 15 }}>{loc.name}</span>
                  {loc.primary && <Pill tone="accent">★</Pill>}
                  {loc.chain && <Pill tone="solid">{loc.chain}</Pill>}
                  {loc.category && <Pill>{loc.category}</Pill>}
                </div>
              </div>
              <Ic d={I.more} size={16} />
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 10 }}>
              {loc.tags.slice(0, 4).map((t, j) => <Pill key={j} tone="solid">{t}</Pill>)}
              {loc.tags.length > 4 && <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)", padding: "4px 4px" }}>+{loc.tags.length - 4}</span>}
            </div>
            <div className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.16em", marginTop: 10 }}>
              {loc.items} ITEMS
            </div>
          </div>
        ))}

        <div className="card" style={{ padding: 18, border: "1px dashed var(--hairline)", background: "transparent", textAlign: "center", color: "var(--fg-3)" }}>
          <Ic d={I.plus} size={16} />
          <div style={{ fontSize: 13, fontWeight: 500, marginTop: 6 }}>Add another location</div>
        </div>
      </div>
    </div>

    <TabBar active="me" />
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// M7. MOBILE WELLNESS
// ═══════════════════════════════════════════════════════════════════
const MobileWellness = () => (
  <div className="screen">
    <StatusBar />
    <AppBar
      title="Wellness"
      left={<Ic d={I.menu} size={22} />}
      right={<div className="mono" style={{ fontSize: 10, letterSpacing: "0.18em", color: "var(--accent)" }}>30D ▾</div>}
    />

    <div style={{ flex: 1, overflow: "auto", padding: "14px 16px" }}>
      {/* Self-report */}
      <div className="card" style={{ padding: 14, marginBottom: 14 }}>
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <Eyebrow>Self-report · today</Eyebrow>
          <span className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.16em" }}>1 = WORST · 5 = BEST</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 8, marginTop: 12 }}>
          {[["SLEEP", "7.4", "h"], ["QUAL", "4", ""], ["NRG", "4", ""], ["SORE", "3", ""], ["MOOD", "5", ""]].map(([k, v, u], i) => (
            <div key={i} style={{ textAlign: "center" }}>
              <div className="eyebrow" style={{ fontSize: 9 }}>{k}</div>
              <div className="num" style={{ fontSize: 20, fontWeight: 700, marginTop: 4 }}>{v}<span style={{ fontSize: 10, color: "var(--fg-3)", fontWeight: 400 }}>{u}</span></div>
            </div>
          ))}
        </div>
      </div>

      {/* Sleep chart */}
      <div className="card" style={{ padding: 14, marginBottom: 14 }}>
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <Eyebrow>Sleep · 30 days</Eyebrow>
          <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>AVG <b style={{ color: "var(--fg)" }}>7.3</b>H</span>
        </div>
        <svg viewBox="0 0 320 100" style={{ width: "100%", height: 100, marginTop: 8 }}>
          {[7, 8].map((v) => (
            <line key={v} x1="0" x2="320" y1={92 - (v - 5) * 20} y2={92 - (v - 5) * 20} stroke="var(--hairline-2)" />
          ))}
          {Array.from({ length: 30 }).map((_, i) => {
            const v = 6.5 + Math.sin(i * 0.7) * 0.8 + Math.cos(i * 0.4) * 0.6;
            return <rect key={i} x={i * 10 + 4} y={92 - (v - 5) * 20} width="8" height={(v - 5) * 20} fill={i === 29 ? "var(--accent)" : "var(--ink-3)"} />;
          })}
        </svg>
      </div>

      {/* Body stats grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 14 }}>
        {[
          { k: "Weight", v: "162.4", u: "lb", delta: "▼ 1.6%" },
          { k: "Body fat", v: "12.8", u: "%", delta: "▼ 0.6" },
          { k: "Resting HR", v: "48", u: "bpm", delta: "→ ±0" },
          { k: "VO2 max", v: "62", u: "ml", delta: "▲ 1" },
        ].map((m, i) => (
          <div key={i} className="card" style={{ padding: 12 }}>
            <Eyebrow>{m.k}</Eyebrow>
            <div style={{ display: "flex", alignItems: "baseline", gap: 4, marginTop: 6 }}>
              <span className="num" style={{ fontSize: 22, fontWeight: 700 }}>{m.v}</span>
              <span style={{ fontSize: 11, color: "var(--fg-3)" }}>{m.u}</span>
            </div>
            <div className="mono" style={{ fontSize: 9, color: m.delta.includes("▼") ? "var(--good)" : "var(--fg-3)", letterSpacing: "0.14em", marginTop: 4 }}>{m.delta}</div>
          </div>
        ))}
      </div>

      {/* Training load */}
      <div className="card" style={{ padding: 14, marginBottom: 14 }}>
        <Eyebrow>Training load · 14 days</Eyebrow>
        <svg viewBox="0 0 320 80" style={{ width: "100%", height: 80, marginTop: 8 }}>
          {Array.from({ length: 14 }).map((_, i) => {
            const cardio = i % 7 === 6 ? 0 : 30 + Math.sin(i * 0.5) * 25 + (i % 7 === 5 ? 80 : 0);
            const strength = i % 7 === 1 || i % 7 === 3 ? 45 : 0;
            return (
              <g key={i} transform={`translate(${i * 22 + 4}, 0)`}>
                <rect x="0" y={75 - cardio * 0.4} width="16" height={cardio * 0.4} fill="var(--paper)" />
                <rect x="0" y={75 - cardio * 0.4 - strength * 0.4} width="16" height={strength * 0.4} fill="var(--accent)" />
              </g>
            );
          })}
        </svg>
        <div style={{ display: "flex", gap: 12, marginTop: 6, fontFamily: "var(--mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.12em" }}>
          <span>■ CARDIO</span>
          <span style={{ color: "var(--accent)" }}>■ STRENGTH</span>
        </div>
      </div>

      <div style={{ height: 12 }} />
    </div>

    <TabBar active="stats" />
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// M8. MOBILE CONNECTIONS
// ═══════════════════════════════════════════════════════════════════
const MobileConnections = () => (
  <div className="screen">
    <StatusBar />
    <AppBar
      title="Connections"
      left={<Ic d={I.menu} size={22} />}
      right={<Ic d={I.upload} size={20} />}
    />

    <div style={{ flex: 1, overflow: "auto", padding: "14px 16px" }}>
      <Eyebrow>Manual import</Eyebrow>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 10, marginBottom: 18 }}>
        {[
          ["Activity .FIT", "Workouts from your device"],
          ["Wellness .FIT", "HR, stress, body battery"],
        ].map(([label, sub], i) => (
          <div key={i} className="card" style={{ padding: 14, textAlign: "center" }}>
            <Ic d={I.upload} size={18} />
            <div style={{ fontSize: 12, fontWeight: 600, marginTop: 8 }}>{label}</div>
            <div style={{ fontSize: 10, color: "var(--fg-3)", marginTop: 4 }}>{sub}</div>
          </div>
        ))}
      </div>

      <Eyebrow>Providers · 2 connected</Eyebrow>
      <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 10 }}>
        {[
          { name: "Strava",        connected: true,  since: "May 12", last: "6 min ago" },
          { name: "Wahoo",         connected: true,  since: "May 18", last: "2 hr ago" },
          { name: "Whoop",         scopes: "Workouts · sleep" },
          { name: "TrainingPeaks", scopes: "Workouts · planned" },
          { name: "Zwift",         scopes: "Indoor activities" },
          { name: "Ride With GPS", scopes: "Route activities" },
          { name: "Garmin",        paused: true, reason: "API access closed" },
        ].map((p, i) => (
          <div key={i} className="card" style={{ padding: 12, display: "flex", gap: 12, alignItems: "center", opacity: p.paused ? 0.55 : 1 }}>
            <div style={{ width: 36, height: 36, borderRadius: 4, background: p.connected ? "var(--accent)" : "var(--bg-3)", color: p.connected ? "var(--ink)" : "var(--fg-2)", display: "grid", placeItems: "center", flexShrink: 0, fontFamily: "var(--mono)", fontWeight: 700, fontSize: 14 }}>
              {p.name[0]}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ fontWeight: 600, fontSize: 13 }}>{p.name}</span>
                {p.connected && <Pill tone="good">✓</Pill>}
                {p.paused && <Pill tone="warn">PAUSED</Pill>}
              </div>
              <div className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.14em", marginTop: 3 }}>
                {p.connected ? `${p.since.toUpperCase()} · ${p.last.toUpperCase()}` : p.paused ? p.reason.toUpperCase() : p.scopes.toUpperCase()}
              </div>
            </div>
            {p.connected ? (
              <div className="btn btn-ghost btn-sm">···</div>
            ) : p.paused ? null : (
              <div className="btn btn-primary btn-sm">CONNECT</div>
            )}
          </div>
        ))}
      </div>
      <div style={{ height: 16 }} />
    </div>

    <TabBar active="me" />
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// M9. MOBILE PROFILE
// ═══════════════════════════════════════════════════════════════════
const MobileProfile = () => (
  <div className="screen">
    <StatusBar />
    <AppBar
      title="Athlete"
      left={<Ic d={I.menu} size={22} />}
      right={<Ic d={I.gear} size={20} />}
    />

    <div style={{ flex: 1, overflow: "auto" }}>
      {/* Hero */}
      <div style={{ padding: "18px 16px 16px", borderBottom: "1px solid var(--hairline-2)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div className="avatar" style={{ width: 56, height: 56, fontSize: 20 }}>AH</div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontWeight: 700, fontSize: 18 }}>Andrew Horn</div>
            <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em", marginTop: 2 }}>
              ANDREW@AIDSTATION.RUN
            </div>
            <Pill tone="accent" style={{ marginTop: 8 }}>PRO · MEMBER SINCE JAN 2026</Pill>
          </div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 6, marginTop: 16, paddingTop: 16, borderTop: "1px solid var(--hairline-2)" }}>
          {[["Plans", "3"], ["Sessions", "412"], ["Streak", "18 d"]].map(([k, v], i) => (
            <div key={i} style={{ textAlign: "center" }}>
              <div className="eyebrow" style={{ fontSize: 9 }}>{k}</div>
              <div className="num" style={{ fontSize: 20, fontWeight: 700, marginTop: 4 }}>{v}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Tab strip */}
      <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--hairline-2)", display: "flex", gap: 6, overflowX: "auto" }}>
        {[["Profile", true], ["Race events", false], ["Schedule", false], ["Skills", false], ["Privacy", false]].map(([l, a], i) => (
          <Pill key={i} tone={a ? "accent" : null}>{l.toString().toUpperCase()}</Pill>
        ))}
      </div>

      {/* Identity card */}
      <div style={{ padding: 16 }}>
        <Eyebrow>Identity</Eyebrow>
        <div className="card" style={{ marginTop: 10, padding: 0 }}>
          {[
            ["Display name", "Andrew Horn"],
            ["Username", "ahorn"],
            ["Time zone", "America/New_York"],
            ["Pronouns", "he/him"],
            ["DOB", "Aug 12, 1988"],
          ].map(([k, v], i, a) => (
            <div key={i} style={{ padding: "12px 14px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: i < a.length - 1 ? "1px solid var(--hairline-2)" : "none" }}>
              <div className="eyebrow" style={{ fontSize: 9 }}>{k}</div>
              <div style={{ fontWeight: 600, fontSize: 13 }}>{v}</div>
            </div>
          ))}
        </div>

        <Eyebrow style={{ marginTop: 20 }}>Performance baselines</Eyebrow>
        <div className="card" style={{ marginTop: 10, padding: 0 }}>
          {[
            ["Threshold pace", "6:42 /mi"],
            ["Threshold HR", "168 bpm"],
            ["FTP", "—"],
            ["VO2 max", "62"],
            ["Resting HR", "48 bpm"],
            ["Body weight", "162.4 lb"],
          ].map(([k, v], i, a) => (
            <div key={i} style={{ padding: "12px 14px", display: "flex", justifyContent: "space-between", borderBottom: i < a.length - 1 ? "1px solid var(--hairline-2)" : "none" }}>
              <div className="eyebrow" style={{ fontSize: 9 }}>{k}</div>
              <div className="num" style={{ fontWeight: 700, fontSize: 13, color: v === "—" ? "var(--fg-3)" : "var(--fg)" }}>{v}</div>
            </div>
          ))}
        </div>

        <Eyebrow style={{ marginTop: 20 }}>Subscription</Eyebrow>
        <div className="card" style={{ marginTop: 10, padding: 14 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 15 }}>AIDSTATION Pro</div>
              <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em", marginTop: 4 }}>$24/MO · NEXT JUN 12</div>
            </div>
            <div className="btn btn-ghost btn-sm">MANAGE</div>
          </div>
        </div>

        <div style={{ marginTop: 24, paddingBottom: 14 }}>
          <div className="btn btn-ghost" style={{ width: "100%", justifyContent: "center", padding: "12px 14px" }}>Sign out</div>
        </div>
      </div>
    </div>

    <TabBar active="me" />
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// M10. MOBILE PLAN REFRESH
// ═══════════════════════════════════════════════════════════════════
const MobilePlanRefresh = () => (
  <div className="screen">
    <StatusBar />
    <AppBar
      title="Refresh plan"
      left={<Ic d={I.chevL} size={22} />}
      right={<div className="mono" style={{ fontSize: 10, letterSpacing: "0.18em", color: "var(--accent)" }}>RUN</div>}
    />

    <div style={{ flex: 1, overflow: "auto", padding: "14px 16px" }}>
      <Eyebrow>Current · v12 · Pattern B</Eyebrow>
      <div className="card" style={{ marginTop: 8, padding: 12, marginBottom: 18 }}>
        <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em" }}>BUILT MAY 21 · MANUAL GENERATE</div>
        <div className="num" style={{ fontSize: 13, marginTop: 4 }}>May 22, 2026 → Apr 26, 2027</div>
      </div>

      {/* Horizon picker */}
      <Eyebrow>Pick a horizon</Eyebrow>
      <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 10, marginBottom: 18 }}>
        {[
          { tier: "T1", days: "2 days", title: "Quick fix", time: "~30s" },
          { tier: "T2", days: "7 days", title: "Weekly check-in", time: "~2 min", recommended: true },
          { tier: "T3", days: "28 days", title: "Big update", time: "~6 min" },
        ].map((h, i) => (
          <div key={i} style={{
            padding: "12px 14px",
            borderRadius: 4,
            border: "1px solid " + (h.recommended ? "var(--accent)" : "var(--hairline)"),
            background: h.recommended ? "color-mix(in oklab, var(--accent) 8%, transparent)" : "transparent",
            display: "flex", alignItems: "center", gap: 12,
          }}>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <Eyebrow accent={h.recommended}>{h.tier} · {h.days.toUpperCase()}</Eyebrow>
                {h.recommended && <Pill tone="accent">★ SUGGESTED</Pill>}
              </div>
              <div style={{ fontWeight: 600, fontSize: 14, marginTop: 4 }}>{h.title}</div>
            </div>
            <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em" }}>{h.time}</span>
          </div>
        ))}
      </div>

      {/* Feeling */}
      <Eyebrow>How is the plan feeling?</Eyebrow>
      <div style={{ display: "flex", gap: 6, marginTop: 10, marginBottom: 18 }}>
        {[["Just right", true], ["Too hard", false], ["Too easy", false]].map(([l, a], i) => (
          <div key={i} style={{
            flex: 1, padding: "10px 8px", textAlign: "center", borderRadius: 4,
            border: "1px solid " + (a ? "var(--accent)" : "var(--hairline)"),
            background: a ? "color-mix(in oklab, var(--accent) 10%, transparent)" : "transparent",
            fontSize: 12, fontWeight: 500,
          }}>{l}</div>
        ))}
      </div>

      {/* Location */}
      <Eyebrow>Current location</Eyebrow>
      <div className="card" style={{ marginTop: 10, padding: "12px 14px", marginBottom: 18, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: 14 }}>Home garage</div>
          <Pill tone="solid" style={{ marginTop: 4 }}>PRIMARY</Pill>
        </div>
        <Ic d={I.chevD} size={14} />
      </div>

      {/* Location changes */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <Eyebrow>Upcoming location changes</Eyebrow>
        <div className="btn btn-ghost btn-sm"><Ic d={I.plus} size={11} sw={2} /> ADD</div>
      </div>
      <div className="card" style={{ padding: "10px 12px", marginBottom: 18, display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 12 }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: 13 }}>Boston, MA · Hotel</div>
          <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em", marginTop: 2 }}>MAY 29 → MAY 31</div>
        </div>
        <Ic d={I.x} size={14} />
      </div>

      {/* What changed */}
      <Eyebrow>What changed? · plain English</Eyebrow>
      <div className="card-flush" style={{ marginTop: 10, padding: "12px 14px", minHeight: 100, fontSize: 13, color: "var(--fg-2)", marginBottom: 18 }}>
        Tweaked my left hamstring on yesterday's long run. Travel to Boston Wed-Fri so the threshold workout needs to move.<span style={{ background: "var(--fg)", width: 1, height: 14, display: "inline-block", marginLeft: 2, verticalAlign: "middle", opacity: 0.5 }} />
      </div>

      <div style={{ paddingBottom: 12 }}>
        <div className="btn btn-primary" style={{ width: "100%", justifyContent: "center", padding: "14px 16px" }}>
          <Ic d={I.bolt} size={13} /> RUN REFRESH · T2
        </div>
      </div>
    </div>
  </div>
);

Object.assign(window, {
  MobileExercises, MobileLocations, MobileWellness,
  MobileConnections, MobileProfile, MobilePlanRefresh,
});
