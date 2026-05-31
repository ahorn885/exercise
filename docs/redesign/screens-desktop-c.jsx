/* AIDSTATION redesign — Desktop screens (part 3)
   Exercises library · Locations · Wellness · Garmin connections · Plan refresh · Profile */

// ═══════════════════════════════════════════════════════════════════
// 7. EXERCISES LIBRARY (replaces rx/list.html)
// ═══════════════════════════════════════════════════════════════════
const ScreenExercises = () => {
  const exercises = [
    { ex: "Back squat",        disc: "Foot",  type: "Compound",   pattern: "Squat",       sets: "3", reps: "5",  wt: "225 lb", last: "May 25", out: "↑ progress", fails: 0, since: 0 },
    { ex: "Front squat",       disc: "Foot",  type: "Compound",   pattern: "Squat",       sets: "3", reps: "5",  wt: "185 lb", last: "May 21", out: "→ hold",     fails: 0, since: 4 },
    { ex: "Romanian deadlift", disc: "Foot",  type: "Compound",   pattern: "Hinge",       sets: "3", reps: "8",  wt: "185 lb", last: "May 25", out: "→ hold",     fails: 1, since: 2 },
    { ex: "Bench press",       disc: "Cross", type: "Compound",   pattern: "Push horiz",  sets: "4", reps: "5",  wt: "165 lb", last: "May 23", out: "↑ progress", fails: 0, since: 0 },
    { ex: "Overhead press",    disc: "Cross", type: "Compound",   pattern: "Push vert",   sets: "4", reps: "5",  wt: "110 lb", last: "May 23", out: "↓ reduce",   fails: 3, since: 6, deload: true },
    { ex: "Pull-up",           disc: "Cross", type: "Compound",   pattern: "Pull vert",   sets: "4", reps: "6",  wt: "BW+25",  last: "May 23", out: "↑ progress", fails: 0, since: 0 },
    { ex: "Bent-over row",     disc: "Cross", type: "Compound",   pattern: "Pull horiz",  sets: "4", reps: "8",  wt: "155 lb", last: "May 21", out: "→ hold",     fails: 0, since: 3 },
    { ex: "Hip thrust",        disc: "Foot",  type: "Assist.",    pattern: "Hinge",       sets: "3", reps: "10", wt: "225 lb", last: "May 22", out: "↑ progress", fails: 0, since: 0 },
    { ex: "Single-leg Roman.", disc: "Foot",  type: "Unilateral", pattern: "Hinge",       sets: "3", reps: "8",  wt: "85 lb",  last: "May 21", out: "↑ progress", fails: 0, since: 1 },
    { ex: "Bike — VO2",        disc: "Bike",  type: "Cardio",     pattern: "Z5 interval", sets: "5", reps: "3'", wt: "—",      last: "May 22", out: "↑ progress", fails: 0, since: 0 },
  ];

  return (
    <div className="screen">
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <Sidebar active="library" />
        <div className="page">
          <TopBar crumbs={["Exercises"]} actions={
            <>
              <div className="btn btn-ghost"><Ic d={I.upload} size={12} /> Import</div>
              <div className="btn btn-primary"><Ic d={I.plus} size={12} sw={2.2} /> Add exercise</div>
            </>
          } />
          <div className="page-body">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 18 }}>
              <div>
                <Eyebrow>Library · current Rx</Eyebrow>
                <h1 className="page-title" style={{ marginTop: 8 }}>Exercises</h1>
                <div className="page-sub">Your prescribed lifts and intervals. Outcomes flow back from your set logs to set the next target.</div>
              </div>
              <div style={{ display: "flex", gap: 6 }}>
                {["All disciplines","Bike","Foot","Water","Cross"].map((d, i) => (
                  <Pill key={i} tone={i === 0 ? "accent" : null}>{d.toUpperCase()}</Pill>
                ))}
              </div>
            </div>

            {/* Plateau alert */}
            <div style={{
              marginBottom: 18, padding: "14px 18px",
              background: "color-mix(in oklab, var(--warn) 8%, transparent)",
              border: "1px solid color-mix(in oklab, var(--warn) 30%, transparent)",
              borderRadius: 4, display: "flex", justifyContent: "space-between", alignItems: "center",
            }}>
              <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
                <Pill tone="warn">! PLATEAU CHECK</Pill>
                <span style={{ fontSize: 13 }}>
                  <b>1 exercise</b> has stalled ≥6 sessions without progress \u2014 consider a 10% deload.
                </span>
              </div>
              <div className="btn btn-ghost btn-sm">REVIEW</div>
            </div>

            {/* Filters */}
            <div className="card" style={{ padding: "12px 16px", marginBottom: 14, display: "flex", gap: 10, alignItems: "center" }}>
              <Eyebrow>Filter</Eyebrow>
              <div style={{ display: "flex", gap: 8, marginLeft: 16 }}>
                {["Discipline · all","Status · all","Location · all","Pattern · all"].map((f,i)=>(
                  <div key={i} className="chip" style={{ padding: "5px 10px" }}>{f.toUpperCase()} <Ic d={I.chevD} size={10} /></div>
                ))}
              </div>
              <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
                <Ic d={I.search} size={14} />
                <span style={{ color: "var(--fg-3)", fontSize: 12 }}>Search exercises…</span>
              </div>
            </div>

            {/* Table */}
            <div className="card" style={{ padding: 0 }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr>
                    {["Exercise","Disc.","Type","Pattern","Sets","Reps","Weight","Last done","Outcome",""].map((h, i) => (
                      <th key={i} className="mono" style={{ padding: "12px 14px", textAlign: "left", fontSize: 9, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--fg-3)", fontWeight: 500, borderBottom: "1px solid var(--hairline-2)", whiteSpace: "nowrap" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {exercises.map((e, i) => {
                    const isUp = e.out.includes("↑");
                    const isHold = e.out.includes("→");
                    const isDown = e.out.includes("↓");
                    return (
                      <tr key={i} style={{ borderBottom: i < exercises.length - 1 ? "1px solid var(--hairline-2)" : "none" }}>
                        <td style={{ padding: "12px 14px", fontWeight: 600 }}>{e.ex}</td>
                        <td style={{ padding: "12px 14px" }}><Pill tone="solid">{e.disc}</Pill></td>
                        <td style={{ padding: "12px 14px", color: "var(--fg-3)", fontSize: 12 }}>{e.type}</td>
                        <td style={{ padding: "12px 14px", color: "var(--fg-3)", fontSize: 12 }}>{e.pattern}</td>
                        <td className="num" style={{ padding: "12px 14px" }}>{e.sets}</td>
                        <td className="num" style={{ padding: "12px 14px" }}>{e.reps}</td>
                        <td className="num" style={{ padding: "12px 14px", fontWeight: 600 }}>{e.wt}</td>
                        <td className="mono num" style={{ padding: "12px 14px", fontSize: 11, color: "var(--fg-3)" }}>{e.last}</td>
                        <td style={{ padding: "12px 14px" }}>
                          <Pill tone={isUp ? "good" : isHold ? "warn" : "bad"}>{e.out.toUpperCase()}</Pill>
                          {e.deload && <Pill tone="bad" style={{ marginLeft: 4 }}>DELOAD</Pill>}
                          {e.fails > 0 && <span className="mono" style={{ marginLeft: 6, fontSize: 10, color: "var(--bad)" }}>{e.fails}/3</span>}
                        </td>
                        <td style={{ padding: "12px 14px", textAlign: "right" }}>
                          {e.deload ? (
                            <div className="btn btn-ghost btn-sm" style={{ color: "var(--warn)" }}>−10%</div>
                          ) : (
                            <Ic d={I.more} size={14} />
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div style={{ marginTop: 12, fontSize: 12, color: "var(--fg-3)", display: "flex", justifyContent: "space-between" }}>
              <span className="mono" style={{ letterSpacing: "0.18em" }}>SHOWING 10 OF 42 \u00b7 32 WITHOUT CURRENT RX</span>
              <span className="mono" style={{ letterSpacing: "0.18em", color: "var(--accent)" }}>VIEW ALL EXERCISES \u2192</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════
// 8. LOCATIONS (replaces locales/list.html)
// ═══════════════════════════════════════════════════════════════════
const ScreenLocations = () => {
  const locs = [
    {
      name: "Home garage", category: "MANUAL",
      addr: "Washington, DC", items: 18, updated: "May 14, 2026", primary: true,
      tags: ["Barbell", "Squat rack", "Bench", "Pull-up bar", "Kettlebells 12-32kg", "DBs to 50lb", "Plates to 405lb", "Foam roller", "Bands"],
      notes: "Garage at 65°F year-round. No platform — caution on heavy drops.",
    },
    {
      name: "Equinox Capitol Hill", chain: "Equinox",
      addr: "320 Pennsylvania Ave SE, Washington DC 20003",
      items: 42, updated: "Apr 22, 2026", coords: "38.8869, -76.9989",
      tags: ["Olympic platform", "Power racks ×4", "DBs to 150lb", "Cable stack", "Concept2 row", "Watt bike", "Sled track", "Sauna", "Cold plunge"],
      notes: "Open 5a-11p weekdays. Member, no extra fee for guests.",
    },
    {
      name: "Rock Creek loop", category: "ROUTE",
      addr: "Beach Dr NW, Washington DC", items: 0, updated: "May 02, 2026", route: true,
      tags: ["4.2 mi loop", "Rolling", "Paved", "Closed to cars weekends", "Aid water at MP2"],
    },
    {
      name: "Marriott Marquis DC", chain: "Marriott", category: "HOTEL",
      addr: "901 Massachusetts Ave NW, Washington DC", items: 8, updated: "Mar 14, 2026",
      tags: ["Treadmills ×4", "DBs to 50lb", "Cable", "Mat"],
      notes: "Travel default for east-coast work trips.",
    },
  ];
  return (
    <div className="screen">
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <Sidebar active="locations" />
        <div className="page">
          <TopBar crumbs={["Locations"]} actions={
            <>
              <div className="btn btn-ghost"><Ic d={I.search} size={12} /> Find nearby</div>
              <div className="btn btn-primary"><Ic d={I.plus} size={12} sw={2.2} /> Add location</div>
            </>
          } />
          <div className="page-body">
            <div style={{ marginBottom: 22 }}>
              <Eyebrow>Locations · equipment profiles</Eyebrow>
              <h1 className="page-title" style={{ marginTop: 8 }}>Where you train</h1>
              <div className="page-sub">Each location has an equipment profile. Selecting one filters exercises so you only see what's actually available.</div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
              {locs.map((loc, i) => (
                <div key={i} className="card" style={{ padding: 0, overflow: "hidden" }}>
                  <div style={{ padding: "16px 18px", borderBottom: "1px solid var(--hairline-2)", display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                        <span style={{ fontSize: 17, fontWeight: 700, letterSpacing: "-0.01em" }}>{loc.name}</span>
                        {loc.primary && <Pill tone="accent">★ PRIMARY</Pill>}
                        {loc.chain && <Pill tone="solid">{loc.chain.toUpperCase()}</Pill>}
                        {loc.category && <Pill>{loc.category}</Pill>}
                      </div>
                      <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", marginTop: 6, letterSpacing: "0.14em", textTransform: "uppercase" }}>
                        \u25b3 {loc.addr}
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: 4 }}>
                      <div className="btn btn-icon"><Ic d={I.bolt} size={12} /></div>
                      <div className="btn btn-icon"><Ic d={I.more} size={12} /></div>
                    </div>
                  </div>
                  <div style={{ padding: "16px 18px" }}>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                      {loc.tags.map((t, j) => (
                        <Pill key={j} tone="solid">{t}</Pill>
                      ))}
                    </div>
                    {loc.notes && (
                      <div style={{ marginTop: 12, padding: "10px 12px", background: "var(--bg)", borderRadius: 4, fontSize: 12, color: "var(--fg-3)", fontStyle: "italic" }}>
                        {loc.notes}
                      </div>
                    )}
                  </div>
                  <div style={{ padding: "10px 18px", borderTop: "1px solid var(--hairline-2)", background: "var(--bg)", display: "flex", justifyContent: "space-between" }}>
                    <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.16em" }}>
                      {loc.items} ITEMS \u00b7 UPDATED {loc.updated.toUpperCase()}
                    </span>
                    <div style={{ display: "flex", gap: 8 }}>
                      <span className="mono" style={{ fontSize: 10, color: "var(--accent)", letterSpacing: "0.16em" }}>EDIT \u2192</span>
                    </div>
                  </div>
                </div>
              ))}

              {/* Add tile */}
              <div className="card" style={{ padding: 18, border: "1px dashed var(--hairline)", background: "transparent", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: 200, textAlign: "center", color: "var(--fg-3)" }}>
                <Ic d={I.plus} size={20} />
                <div style={{ fontWeight: 500, fontSize: 14, marginTop: 8 }}>Add another location</div>
                <div className="mono" style={{ fontSize: 10, letterSpacing: "0.14em", marginTop: 4 }}>HOME \u00b7 GYM \u00b7 ROUTE \u00b7 HOTEL</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════
// 9. WELLNESS (replaces wellness/index.html)
// ═══════════════════════════════════════════════════════════════════
const ScreenWellness = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="insights" />
      <div className="page">
        <TopBar crumbs={["Wellness", "Last 30 days"]} actions={
          <>
            <div className="btn btn-ghost">Range · 30 days <Ic d={I.chevD} size={12} /></div>
            <div className="btn btn-primary"><Ic d={I.plus} size={12} sw={2.2} /> Log today</div>
          </>
        } />
        <div className="page-body">
          <div style={{ marginBottom: 22 }}>
            <Eyebrow>Wellness · self-report + provider telemetry</Eyebrow>
            <h1 className="page-title" style={{ marginTop: 8 }}>How you've been showing up.</h1>
            <div className="page-sub">Daily self-report (sleep / energy / soreness / mood), body comp, training load, and provider aggregates \u2014 30 days.</div>
          </div>

          {/* Self-report strip */}
          <div className="card" style={{ marginBottom: 14, padding: 18 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 14 }}>
              <Eyebrow>Self-report · today</Eyebrow>
              <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.18em" }}>1 = WORST \u00b7 5 = BEST</span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr 1fr", gap: 18 }}>
              {[
                ["Sleep", "7.4", "h"],
                ["Quality", "4", "/5"],
                ["Energy", "4", "/5"],
                ["Soreness", "3", "/5"],
                ["Mood", "5", "/5"],
              ].map(([k, v, u], i) => (
                <div key={i}>
                  <div className="eyebrow">{k}</div>
                  <div style={{ marginTop: 6 }}>
                    <span className="num" style={{ fontSize: 30, fontWeight: 700 }}>{v}</span>
                    <span style={{ fontSize: 12, color: "var(--fg-3)", marginLeft: 4 }}>{u}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Charts grid */}
          <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 14, marginBottom: 14 }}>
            <div className="card" style={{ padding: 18 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <Eyebrow>Sleep \u00b7 hours · 30 days</Eyebrow>
                <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>AVG <b style={{ color: "var(--fg)" }}>7.3</b> H</span>
              </div>
              <svg viewBox="0 0 600 140" style={{ width: "100%", height: 140, marginTop: 12 }}>
                {[6, 7, 8, 9].map((v, i) => (
                  <g key={v}>
                    <line x1="30" x2="600" y1={130 - (v - 5) * 26} y2={130 - (v - 5) * 26} stroke="var(--hairline-2)" />
                    <text x="0" y={134 - (v - 5) * 26} fontFamily="var(--mono)" fontSize="9" fill="var(--fg-4)">{v}h</text>
                  </g>
                ))}
                {Array.from({ length: 30 }).map((_, i) => {
                  const v = 6.5 + Math.sin(i * 0.7) * 0.8 + Math.cos(i * 0.4) * 0.6 + (i / 30) * 0.4;
                  return <rect key={i} x={32 + i * 19} y={130 - (v - 5) * 26} width="14" height={(v - 5) * 26} fill={i === 29 ? "var(--accent)" : "var(--ink-3)"} />;
                })}
              </svg>
            </div>
            <div className="card" style={{ padding: 18 }}>
              <Eyebrow>Ratings · trends</Eyebrow>
              <svg viewBox="0 0 280 140" style={{ width: "100%", height: 140, marginTop: 12 }}>
                {["energy", "mood", "soreness"].map((label, j) => {
                  const color = ["var(--accent)", "var(--good)", "var(--warn)"][j];
                  const pts = Array.from({ length: 30 }).map((_, i) => {
                    const v = 3.4 + Math.sin(i * 0.4 + j) * 0.6 + j * 0.3;
                    return `${i * 9 + 6},${135 - v * 20}`;
                  }).join(" ");
                  return <polyline key={label} points={pts} fill="none" stroke={color} strokeWidth="1.5" opacity="0.85" />;
                })}
              </svg>
              <div style={{ display: "flex", gap: 12, marginTop: 8, flexWrap: "wrap" }}>
                {[["Energy","var(--accent)"],["Mood","var(--good)"],["Soreness","var(--warn)"]].map(([l,c],i)=>(
                  <div key={i} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                    <div style={{ width: 8, height: 2, background: c }} />
                    <span className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--fg-3)" }}>{l.toUpperCase()}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Body comp + training load */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14, marginBottom: 14 }}>
            {[
              { k: "Weight", v: "162.4", u: "lb", trend: [165, 164.5, 164, 163.5, 163, 163.2, 162.8, 162.4], color: "var(--paper)" },
              { k: "Body fat", v: "12.8", u: "%", trend: [13.6, 13.5, 13.3, 13.2, 13.1, 13.0, 12.9, 12.8], color: "var(--accent)" },
              { k: "Resting HR", v: "48", u: "bpm", trend: [52, 51, 50, 49, 48, 48, 47, 48], color: "var(--info)" },
            ].map((m, i) => (
              <div key={i} className="card" style={{ padding: 18 }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <Eyebrow>{m.k}</Eyebrow>
                  <Pill tone="good">▼ 1.6%</Pill>
                </div>
                <div style={{ display: "flex", alignItems: "baseline", gap: 6, marginTop: 8 }}>
                  <span className="num" style={{ fontSize: 30, fontWeight: 700 }}>{m.v}</span>
                  <span style={{ fontSize: 12, color: "var(--fg-3)" }}>{m.u}</span>
                </div>
                <svg viewBox="0 0 200 50" style={{ width: "100%", height: 50, marginTop: 10 }}>
                  <polyline
                    points={m.trend.map((v, i) => {
                      const min = Math.min(...m.trend); const max = Math.max(...m.trend);
                      const y = 45 - ((v - min) / (max - min || 1)) * 40;
                      return `${i * 28 + 4},${y}`;
                    }).join(" ")}
                    fill="none" stroke={m.color} strokeWidth="1.5"
                  />
                  {m.trend.map((v, i) => {
                    const min = Math.min(...m.trend); const max = Math.max(...m.trend);
                    const y = 45 - ((v - min) / (max - min || 1)) * 40;
                    return <circle key={i} cx={i * 28 + 4} cy={y} r={i === m.trend.length - 1 ? 3 : 1.5} fill={m.color} />;
                  })}
                </svg>
              </div>
            ))}
          </div>

          <div className="card" style={{ padding: 18 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <Eyebrow>Training load · minutes / day</Eyebrow>
              <div style={{ display: "flex", gap: 12 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 4 }}><div style={{ width: 10, height: 10, background: "var(--paper)" }} /><span className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--fg-3)" }}>CARDIO</span></div>
                <div style={{ display: "flex", alignItems: "center", gap: 4 }}><div style={{ width: 10, height: 10, background: "var(--accent)" }} /><span className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--fg-3)" }}>STRENGTH</span></div>
              </div>
            </div>
            <svg viewBox="0 0 600 120" style={{ width: "100%", height: 120, marginTop: 12 }}>
              {Array.from({ length: 30 }).map((_, i) => {
                const cardio = i % 7 === 6 ? 0 : 30 + Math.sin(i * 0.5) * 25 + (i % 7 === 5 ? 80 : 0);
                const strength = i % 7 === 1 || i % 7 === 3 ? 45 : 0;
                return (
                  <g key={i} transform={`translate(${i * 19 + 4}, 0)`}>
                    <rect x="0" y={115 - cardio * 0.5} width="14" height={cardio * 0.5} fill="var(--paper)" />
                    <rect x="0" y={115 - cardio * 0.5 - strength * 0.5} width="14" height={strength * 0.5} fill="var(--accent)" />
                  </g>
                );
              })}
              <line x1="0" x2="600" y1="115" y2="115" stroke="var(--hairline)" />
            </svg>
          </div>
        </div>
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// 10. GARMIN / CONNECTIONS (replaces garmin/dashboard.html)
// ═══════════════════════════════════════════════════════════════════
const ScreenConnections = () => {
  const providers = [
    { name: "Strava",        connected: true,  since: "May 12, 2026", lastSync: "6 min ago", scopes: ["activity", "wellness"], pulls: "412 sessions" },
    { name: "Wahoo",         connected: true,  since: "May 18, 2026", lastSync: "2 hr ago",  scopes: ["activity", "body", "sleep"], pulls: "86 sessions" },
    { name: "Whoop",         connected: false, scopes: ["workouts", "sleep", "recovery"] },
    { name: "TrainingPeaks", connected: false, scopes: ["workouts", "planned"] },
    { name: "Zwift",         connected: false, scopes: ["indoor activities"] },
    { name: "Ride With GPS", connected: false, scopes: ["routes"] },
    { name: "Garmin",        connected: false, paused: true, reason: "Garmin API access closed \u2014 use FIT upload below" },
  ];
  return (
    <div className="screen">
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <Sidebar active="link" />
        <div className="page">
          <TopBar crumbs={["Connections"]} actions={
            <div className="btn btn-primary"><Ic d={I.upload} size={12} /> Upload .FIT</div>
          } />
          <div className="page-body">
            <div style={{ marginBottom: 22 }}>
              <Eyebrow>Connections · providers + FIT files</Eyebrow>
              <h1 className="page-title" style={{ marginTop: 8 }}>Bring data in.</h1>
              <div className="page-sub">Connect a service to auto-sync, or upload .FIT files manually \u2014 your training adapts the same way either route.</div>
            </div>

            {/* Manual upload row */}
            <div className="row" style={{ marginBottom: 18 }}>
              <div className="card col" style={{ padding: 18 }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <Eyebrow accent>\u25cf MANUAL FIT \u00b7 ACTIVITY</Eyebrow>
                  <Pill tone="solid">.FIT</Pill>
                </div>
                <div style={{ fontWeight: 600, fontSize: 16, marginTop: 8 }}>Upload activity .FIT</div>
                <div style={{ fontSize: 13, color: "var(--fg-3)", marginTop: 4 }}>Drop a workout .FIT from any device that exports the format — Garmin, Wahoo, COROS, Polar, Suunto, etc. — to auto-populate the cardio log.</div>
                <div style={{ marginTop: 14, padding: "20px", border: "1px dashed var(--hairline)", borderRadius: 4, textAlign: "center" }}>
                  <Ic d={I.upload} size={20} />
                  <div style={{ fontSize: 13, marginTop: 6 }}>Drop .FIT here or <span style={{ color: "var(--accent)" }}>browse</span></div>
                </div>
              </div>
              <div className="card col" style={{ padding: 18 }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <Eyebrow accent>\u25cf MANUAL FIT \u00b7 WELLNESS</Eyebrow>
                  <Pill tone="solid">.FIT</Pill>
                </div>
                <div style={{ fontWeight: 600, fontSize: 16, marginTop: 8 }}>Upload wellness .FIT</div>
                <div style={{ fontSize: 13, color: "var(--fg-3)", marginTop: 4 }}>HR, stress, recovery scores, and step data from any vendor's daily wellness .FIT export.</div>
                <div style={{ marginTop: 14, padding: "20px", border: "1px dashed var(--hairline)", borderRadius: 4, textAlign: "center" }}>
                  <Ic d={I.upload} size={20} />
                  <div style={{ fontSize: 13, marginTop: 6 }}>Drop .FIT here or <span style={{ color: "var(--accent)" }}>browse</span></div>
                </div>
              </div>
              <div className="card col" style={{ padding: 18, display: "flex", flexDirection: "column" }}>
                <Eyebrow>Last 7 days · imports</Eyebrow>
                <div style={{ marginTop: 14, flex: 1 }}>
                  {[
                    ["May 27","Threshold intervals","auto · Strava","6 min ago"],
                    ["May 26","Easy 45'","auto · Strava","yesterday"],
                    ["May 25","Bench + pull","manual","2 days ago"],
                    ["May 23","Long run 1:48","auto · Strava","3 days ago"],
                  ].map((r, i) => (
                    <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: i < 3 ? "1px solid var(--hairline-2)" : "none", fontSize: 12 }}>
                      <div>
                        <span className="mono num" style={{ fontSize: 10, color: "var(--fg-3)", marginRight: 8 }}>{r[0]}</span>
                        <span>{r[1]}</span>
                      </div>
                      <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em" }}>{r[2].toUpperCase()}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Providers */}
            <Eyebrow>Provider integrations · 2 connected</Eyebrow>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 12 }}>
              {providers.map((p, i) => (
                <div key={i} className="card" style={{ padding: 16, display: "flex", gap: 14, opacity: p.paused ? 0.55 : 1 }}>
                  <div style={{ width: 44, height: 44, borderRadius: 4, background: p.connected ? "var(--accent)" : "var(--bg-3)", color: p.connected ? "var(--ink)" : "var(--fg-2)", display: "grid", placeItems: "center", flexShrink: 0, fontFamily: "var(--mono)", fontWeight: 700, fontSize: 16 }}>
                    {p.name[0]}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                      <span style={{ fontWeight: 600, fontSize: 15 }}>{p.name}</span>
                      {p.connected && <Pill tone="good">\u2713 CONNECTED</Pill>}
                      {p.paused && <Pill tone="warn">PAUSED</Pill>}
                    </div>
                    {p.connected ? (
                      <div className="mono" style={{ fontSize: 10, letterSpacing: "0.14em", color: "var(--fg-3)", marginTop: 6, textTransform: "uppercase" }}>
                        SINCE {p.since.toUpperCase()} \u00b7 SYNCED {p.lastSync.toUpperCase()} \u00b7 {p.pulls.toUpperCase()}
                      </div>
                    ) : p.paused ? (
                      <div style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 6 }}>{p.reason}</div>
                    ) : (
                      <div className="mono" style={{ fontSize: 10, letterSpacing: "0.14em", color: "var(--fg-3)", marginTop: 6, textTransform: "uppercase" }}>
                        SCOPES \u00b7 {p.scopes.join(" \u00b7 ")}
                      </div>
                    )}
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 4, justifyContent: "center" }}>
                    {p.connected ? (
                      <>
                        <div className="btn btn-ghost btn-sm">RE-AUTH</div>
                        <div className="btn btn-text btn-sm" style={{ color: "var(--bad)", justifyContent: "flex-end" }}>REVOKE</div>
                      </>
                    ) : p.paused ? (
                      <div className="btn btn-ghost btn-sm" style={{ opacity: 0.5 }}>—</div>
                    ) : (
                      <div className="btn btn-primary btn-sm">CONNECT</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════
// 11. PLAN REFRESH (consolidated — replaces plans/v2/refresh.html
// AND coaching/review.html; the two route together do the same job
// with overlapping fields. See section 17 "Code cleanup" callout.)
// ═══════════════════════════════════════════════════════════════════
const ScreenPlanRefresh = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="plan" />
      <div className="page">
        <TopBar crumbs={["Plan", "Refresh"]} actions={
          <div className="btn btn-primary"><Ic d={I.bolt} size={12} /> Run refresh</div>
        } />
        <div className="page-body">
          <div style={{ maxWidth: 1100 }}>
            <div style={{ marginBottom: 22 }}>
              <Eyebrow>Plan refresh · re-run the cascade</Eyebrow>
              <h1 className="page-title" style={{ marginTop: 8 }}>Update your plan.</h1>
              <div className="page-sub">Pick a horizon and (optionally) tell us what changed. We'll re-run the cascade for that window, write a new plan version, and show a diff before activating.</div>
            </div>

            {/* Current version + horizon selection — top row */}
            <div className="card" style={{ padding: 18, marginBottom: 18 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <Eyebrow>Current plan version</Eyebrow>
                <Pill tone="solid">PATTERN B · v12</Pill>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 0, marginTop: 14, borderTop: "1px solid var(--hairline-2)", paddingTop: 14 }}>
                {[
                  ["Built", "May 21, 2026"],
                  ["Via", "Manual generate"],
                  ["Scope start", "May 22, 2026"],
                  ["Scope end", "Apr 26, 2027"],
                ].map(([k, v], i) => (
                  <div key={i} style={{ borderRight: i < 3 ? "1px solid var(--hairline-2)" : "none", padding: "0 16px", textAlign: i === 0 ? "left" : i === 3 ? "right" : "center" }}>
                    <div className="eyebrow" style={{ fontSize: 9 }}>{k}</div>
                    <div className="num" style={{ fontWeight: 600, marginTop: 4, fontSize: 14 }}>{v}</div>
                  </div>
                ))}
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 360px", gap: 22 }}>
              <div>
                {/* Horizon picker */}
                <Eyebrow>Pick a horizon</Eyebrow>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginTop: 12, marginBottom: 22 }}>
                  {[
                    { tier: "T1", days: "2 days", title: "Quick fix", desc: "Energy, equipment-of-the-moment, a tweak that needs to land now.", time: "~30s" },
                    { tier: "T2", days: "7 days", title: "Weekly check-in", desc: "Re-balance this week's load against how you're showing up.", time: "~2 min", recommended: true },
                    { tier: "T3", days: "28 days", title: "Big update", desc: "Fitness signal shift, race-block re-eval, life change.", time: "~6 min" },
                  ].map((h, i) => (
                    <div key={i} style={{
                      padding: 14,
                      borderRadius: 4,
                      border: "1px solid " + (h.recommended ? "var(--accent)" : "var(--hairline)"),
                      background: h.recommended ? "color-mix(in oklab, var(--accent) 8%, transparent)" : "transparent",
                      position: "relative",
                    }}>
                      {h.recommended && <div style={{ position: "absolute", top: -9, left: 12, padding: "2px 8px", background: "var(--accent)", color: "var(--ink)", fontFamily: "var(--mono)", fontSize: 9, letterSpacing: "0.18em", borderRadius: 2 }}>★ SUGGESTED</div>}
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                        <Eyebrow accent>{h.tier} · {h.days.toUpperCase()}</Eyebrow>
                        <span className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.16em" }}>{h.time}</span>
                      </div>
                      <div style={{ fontSize: 15, fontWeight: 700, letterSpacing: "-0.01em", marginTop: 6 }}>{h.title}</div>
                      <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 6, lineHeight: 1.4 }}>{h.desc}</div>
                    </div>
                  ))}
                </div>

                {/* How is the plan feeling? (from coaching/review) */}
                <Eyebrow>How is the plan feeling?</Eyebrow>
                <div className="card" style={{ marginTop: 12, padding: 16, marginBottom: 18 }}>
                  <div style={{ display: "flex", gap: 8 }}>
                    {[["Just right", true], ["Too hard", false], ["Too easy", false]].map(([l, active], i) => (
                      <div key={i} style={{ flex: 1, padding: "12px 14px", textAlign: "center", borderRadius: 4, border: "1px solid " + (active ? "var(--accent)" : "var(--hairline)"), background: active ? "color-mix(in oklab, var(--accent) 10%, transparent)" : "transparent", fontWeight: 500, fontSize: 13 }}>{l}</div>
                    ))}
                  </div>
                </div>

                {/* Current location */}
                <Eyebrow>Current location</Eyebrow>
                <div className="card" style={{ marginTop: 12, padding: "14px 16px", marginBottom: 18, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <span style={{ fontWeight: 600, fontSize: 15 }}>Home garage</span>
                    <Pill tone="solid" style={{ marginLeft: 8 }}>PRIMARY</Pill>
                  </div>
                  <Ic d={I.chevD} size={14} />
                </div>

                {/* Location changes adder */}
                <div style={{ marginBottom: 18 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <Eyebrow>Upcoming location changes · optional</Eyebrow>
                    <div className="btn btn-ghost btn-sm"><Ic d={I.plus} size={11} sw={2} /> ADD</div>
                  </div>
                  <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 4 }}>
                    Date ranges where your training environment changes — travel, events, restricted access. We'll factor them in.
                  </div>
                  <div className="card" style={{ marginTop: 12, padding: "14px 16px", display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr 28px", gap: 10, alignItems: "end" }}>
                    {[["From", "May 29"], ["To", "May 31"], ["Location type", "Hotel"], ["City", "Boston, MA"]].map(([k, v], i) => (
                      <div key={i}>
                        <div className="eyebrow" style={{ fontSize: 9, marginBottom: 4 }}>{k}</div>
                        <div className="num" style={{ fontSize: 13, fontWeight: 500, padding: "8px 10px", border: "1px solid var(--hairline-2)", borderRadius: 3 }}>{v}</div>
                      </div>
                    ))}
                    <div style={{ display: "grid", placeItems: "center", paddingBottom: 8 }}><Ic d={I.x} size={14} /></div>
                  </div>
                </div>

                {/* Race goals changed */}
                <div style={{ marginBottom: 18 }}>
                  <Eyebrow>Race goals changed?</Eyebrow>
                  <div className="card" style={{ marginTop: 12, padding: "14px 16px", display: "flex", alignItems: "center", gap: 10 }}>
                    <div style={{ width: 16, height: 16, borderRadius: 3, border: "1px solid var(--hairline)", background: "transparent" }} />
                    <span style={{ fontSize: 13 }}>My event goals have changed</span>
                    <span className="mono" style={{ marginLeft: "auto", fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.16em" }}>CURRENT: SUB-3:00 · BQ</span>
                  </div>
                </div>

                {/* What changed / coach notes */}
                <Eyebrow>What changed? · plain English</Eyebrow>
                <div className="card-flush" style={{ marginTop: 10, padding: "14px 16px", minHeight: 100, fontSize: 14, color: "var(--fg-2)" }}>
                  Tweaked my left hamstring on yesterday's long run — nothing acute but feels tight. Travel to Boston Wed-Fri so the threshold workout needs to move. Recovered well from Saturday's long otherwise.<span style={{ background: "var(--fg)", width: 1, height: 16, display: "inline-block", marginLeft: 2, verticalAlign: "middle", opacity: 0.5 }} />
                </div>
                <div className="mono" style={{ fontSize: 10, color: "var(--fg-4)", marginTop: 6, letterSpacing: "0.14em", textTransform: "uppercase" }}>
                  ~217 / 2000 CHARS · WE MAY ASK CLARIFYING QUESTIONS BEFORE RUNNING
                </div>
              </div>

              {/* Right rail: recent + upcoming context */}
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

                <div className="card-flush" style={{ padding: 14, fontSize: 12, color: "var(--fg-3)", lineHeight: 1.5 }}>
                  <Eyebrow>What happens next</Eyebrow>
                  <div style={{ marginTop: 8 }}>
                    Refresh writes plan version <span className="mono">v13</span>. You'll get a side-by-side diff before it activates — accept or discard. <span className="mono accent" style={{ color: "var(--accent)" }}>SEE PLAN COMPARE →</span>
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

// ═══════════════════════════════════════════════════════════════════
// 12. PROFILE (replaces profile/edit.html)
// ═══════════════════════════════════════════════════════════════════
const ScreenProfile = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="athlete" />
      <div className="page">
        <TopBar crumbs={["Athlete", "Andrew Horn"]} actions={
          <div className="btn btn-primary"><Ic d={I.check} size={12} sw={2.2} /> Save changes</div>
        } />
        <div className="page-body" style={{ padding: 0 }}>
          {/* Hero */}
          <div style={{ padding: "28px 32px 0", borderBottom: "1px solid var(--hairline-2)" }}>
            <div style={{ display: "flex", gap: 22, alignItems: "center", marginBottom: 24 }}>
              <div className="avatar lg" style={{ width: 72, height: 72, fontSize: 26 }}>AH</div>
              <div style={{ flex: 1 }}>
                <Eyebrow>Athlete</Eyebrow>
                <h1 style={{ fontSize: 32, fontWeight: 700, letterSpacing: "-0.02em", margin: "4px 0 4px" }}>Andrew Horn</h1>
                <div className="mono" style={{ fontSize: 11, letterSpacing: "0.18em", color: "var(--fg-3)", textTransform: "uppercase" }}>
                  ANDREW@AIDSTATION.RUN \u00b7 PRO \u00b7 MEMBER SINCE JAN 2026
                </div>
              </div>
              <div style={{ display: "flex", gap: 14, paddingLeft: 22, borderLeft: "1px solid var(--hairline)" }}>
                {[["Plans","3"],["Sessions","412"],["Streak","18 d"]].map(([k,v],i)=>(
                  <div key={i} style={{ minWidth: 70 }}>
                    <div className="eyebrow" style={{ fontSize: 9 }}>{k}</div>
                    <div className="num" style={{ fontSize: 24, fontWeight: 700, marginTop: 4 }}>{v}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Tabs */}
            <div style={{ display: "flex", gap: 0 }}>
              {[
                ["Athlete", true],
                ["Race events", false],
                ["Schedule", false],
                ["Skills", false],
                ["Notifications", false],
                ["Privacy", false],
              ].map(([l, active], i) => (
                <div key={i} style={{
                  padding: "12px 18px",
                  borderBottom: "2px solid " + (active ? "var(--accent)" : "transparent"),
                  color: active ? "var(--fg)" : "var(--fg-3)",
                  fontWeight: 500, fontSize: 13,
                }}>{l}</div>
              ))}
            </div>
          </div>

          {/* Body */}
          <div style={{ padding: "28px 32px" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 28 }}>
              <div>
                {/* Identity */}
                <Eyebrow>Identity</Eyebrow>
                <div className="card" style={{ marginTop: 12, padding: 0 }}>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr" }}>
                    {[
                      ["Display name", "Andrew Horn"],
                      ["Username", "ahorn"],
                      ["Email", "andrew@aidstation.run", "Verified"],
                      ["Time zone", "America/New_York"],
                      ["Pronouns", "he/him"],
                      ["DOB", "Aug 12, 1988"],
                    ].map(([k, v, badge], i) => (
                      <div key={i} style={{
                        padding: "16px 18px",
                        borderRight: i % 2 === 0 ? "1px solid var(--hairline-2)" : "none",
                        borderBottom: i < 4 ? "1px solid var(--hairline-2)" : "none",
                      }}>
                        <div className="eyebrow" style={{ fontSize: 9 }}>{k}</div>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6 }}>
                          <span style={{ fontWeight: 600 }}>{v}</span>
                          {badge && <Pill tone="good">{badge.toUpperCase()}</Pill>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Performance baselines */}
                <div style={{ marginTop: 24 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                    <Eyebrow>Performance baselines</Eyebrow>
                    <span className="mono" style={{ fontSize: 10, letterSpacing: "0.18em", color: "var(--accent)" }}>RE-PREFILL FROM PROVIDERS \u2192</span>
                  </div>
                  <div className="card" style={{ marginTop: 12, padding: 0 }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                      <thead>
                        <tr>
                          {["Field","Value","Unit","Source","Updated"].map((h,i)=>(
                            <th key={i} className="mono" style={{ padding: "12px 18px", textAlign: "left", fontSize: 9, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--fg-3)", fontWeight: 500, borderBottom: "1px solid var(--hairline-2)" }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {[
                          ["Threshold pace","6:42","/mi","Test on May 4","May 4"],
                          ["Threshold HR","168","bpm","From Wahoo","2 days ago"],
                          ["FTP","—","watts","Not set","\u2014"],
                          ["VO2 max","62","ml/kg/min","Self-reported","Apr 18"],
                          ["Resting HR","48","bpm","From Wahoo","today"],
                          ["Body weight","162.4","lb","From Wahoo","today"],
                        ].map((r, i) => (
                          <tr key={i} style={{ borderBottom: i < 5 ? "1px solid var(--hairline-2)" : "none" }}>
                            <td style={{ padding: "12px 18px", fontWeight: 500 }}>{r[0]}</td>
                            <td className="num" style={{ padding: "12px 18px", fontWeight: 700 }}>{r[1]}</td>
                            <td style={{ padding: "12px 18px", color: "var(--fg-3)" }}>{r[2]}</td>
                            <td style={{ padding: "12px 18px", color: "var(--fg-3)", fontSize: 12 }}>{r[3]}</td>
                            <td className="mono" style={{ padding: "12px 18px", color: "var(--fg-3)", fontSize: 11 }}>{r[4]}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Active plans */}
                <div style={{ marginTop: 24 }}>
                  <Eyebrow>Active plans</Eyebrow>
                  <div className="card" style={{ marginTop: 12, padding: 18, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <div style={{ fontSize: 16, fontWeight: 700 }}>Boston Marathon 2026</div>
                      <div className="mono" style={{ fontSize: 10, letterSpacing: "0.14em", color: "var(--fg-3)", marginTop: 4, textTransform: "uppercase" }}>
                        APR 20 \u00b7 22-WEEK BUILD \u00b7 WEEK 8 \u00b7 PATTERN B v12
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: 6 }}>
                      <div className="btn btn-ghost btn-sm">VIEW</div>
                      <div className="btn btn-ghost btn-sm">REFRESH</div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Right rail */}
              <div className="stack">
                <div className="card" style={{ padding: 18 }}>
                  <Eyebrow>Account</Eyebrow>
                  <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 8 }}>
                    <div className="btn btn-ghost btn-sm" style={{ justifyContent: "space-between" }}>Account settings <Ic d={I.chevR} size={12} /></div>
                    <div className="btn btn-ghost btn-sm" style={{ justifyContent: "space-between" }}>Change password <Ic d={I.chevR} size={12} /></div>
                    <div className="btn btn-text btn-sm" style={{ justifyContent: "flex-start", color: "var(--fg-2)", padding: "8px 0" }}>Sign out</div>
                  </div>
                </div>

                <div className="card-flush" style={{ padding: 14 }}>
                  <Eyebrow>Engine version</Eyebrow>
                  <div className="mono" style={{ fontSize: 12, marginTop: 6 }}>v3.2 \u00b7 deployed May 24</div>
                  <div style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 6 }}>
                    Your plans regenerate against v3.2. Next engine bump rolls automatically; we'll diff your plan before applying.
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
  ScreenExercises, ScreenLocations, ScreenWellness, ScreenConnections, ScreenPlanRefresh, ScreenProfile,
});
