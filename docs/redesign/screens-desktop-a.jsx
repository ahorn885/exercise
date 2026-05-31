/* AIDSTATION redesign — Desktop screens (part 1)
   Dashboard · Training Plan · Today's Workout */

// ═══════════════════════════════════════════════════════════════════
// 1. DASHBOARD — Today
// ═══════════════════════════════════════════════════════════════════
const ScreenDashboard = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="home" />
      <div className="page">
        <TopBar crumbs={["Today", "Wed · May 27"]} actions={
          <div className="btn btn-primary"><Ic d={I.plus} size={12} sw={2.2} />Log session</div>
        } />
        <div className="page-body">
          {/* Greeting */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 24 }}>
            <div>
              <Eyebrow>Week 8 · Build phase · 14 weeks to race</Eyebrow>
              <h1 className="page-title" style={{ marginTop: 8, fontSize: 36 }}>
                Morning, Andrew. <span style={{ color: "var(--fg-3)", fontWeight: 400 }}>Time to move.</span>
              </h1>
            </div>
            <div style={{ display: "flex", gap: 10 }}>
              <Pill tone="good">▲ Load 612 TSS</Pill>
              <Pill tone="accent">● Readiness 84</Pill>
            </div>
          </div>

          {/* Top: today's session hero + readiness */}
          <div className="row" style={{ marginBottom: 16 }}>
            {/* Today's primary workout */}
            <div className="card col" style={{ padding: 22, display: "flex", flexDirection: "column" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 18 }}>
                <div>
                  <Eyebrow accent>● Today · Primary</Eyebrow>
                  <div style={{ fontSize: 22, fontWeight: 700, letterSpacing: "-0.015em", marginTop: 6 }}>
                    Threshold intervals · 6 × 5min @ FTHR
                  </div>
                  <div style={{ color: "var(--fg-3)", marginTop: 4, fontSize: 13 }}>
                    Run · 68 min · Z4 ceilings, easy returns to Z2
                  </div>
                </div>
                <div style={{ display: "flex", gap: 6 }}>
                  <div className="btn btn-ghost btn-sm"><Ic d={I.x} size={11} /> Skip</div>
                  <div className="btn btn-ghost btn-sm"><Ic d={I.download} size={11} /> .FIT</div>
                  <div className="btn btn-primary btn-sm"><Ic d={I.check} size={11} sw={2.2} /> Complete</div>
                </div>
              </div>

              {/* Interval visualization */}
              <div style={{ background: "var(--bg)", border: "1px solid var(--hairline-2)", borderRadius: 4, padding: "16px 18px" }}>
                <svg viewBox="0 0 600 84" style={{ width: "100%", height: 84 }}>
                  {/* baseline grid */}
                  {[0, 21, 42, 63].map((y) => (
                    <line key={y} x1="0" x2="600" y1={y + 4} y2={y + 4} stroke="var(--hairline-2)" />
                  ))}
                  {/* warmup */}
                  <rect x="0"   y="48" width="60"  height="28" fill="var(--ink-3)" />
                  {/* 6× threshold blocks + recoveries */}
                  {[0, 1, 2, 3, 4, 5].map((i) => (
                    <g key={i} transform={`translate(${70 + i * 80}, 0)`}>
                      <rect x="0"  y="6"  width="48" height="70" fill="var(--orange)" />
                      <rect x="50" y="48" width="22" height="28" fill="var(--ink-3)" />
                    </g>
                  ))}
                  {/* cooldown */}
                  <rect x="555" y="48" width="42" height="28" fill="var(--ink-3)" />
                </svg>
                <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6, fontFamily: "var(--mono)", fontSize: 9, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--fg-4)" }}>
                  <span>WU · 10'</span><span>6 × 5' / 2'</span><span>CD · 7'</span>
                </div>
              </div>

              {/* Targets */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 0, marginTop: 18, borderTop: "1px solid var(--hairline)", borderBottom: "1px solid var(--hairline)" }}>
                {[
                  ["Pace target",  "6:42", "/mi"],
                  ["HR ceiling",   "168",  "bpm"],
                  ["RPE",          "7.5",  "/10"],
                  ["Fueling",      "60",   "g/hr"],
                ].map(([k, v, u], i) => (
                  <div key={i} style={{ padding: "12px 16px", borderRight: i < 3 ? "1px solid var(--hairline)" : "none" }}>
                    <div className="eyebrow" style={{ fontSize: 9 }}>{k}</div>
                    <div style={{ fontSize: 20, fontWeight: 700, marginTop: 4 }} className="num">{v}<span style={{ fontSize: 11, fontWeight: 400, color: "var(--fg-3)", marginLeft: 4 }}>{u}</span></div>
                  </div>
                ))}
              </div>

              <div style={{ display: "flex", gap: 14, marginTop: 16, fontSize: 12, color: "var(--fg-3)" }}>
                <div><Ic d={I.pin} size={11} /> Rock Creek loop · 4.2 mi</div>
                <div><Ic d={I.cloud} size={11} /> 64°F · light NW wind</div>
                <div><Ic d={I.shoe} size={11} /> Endorphins Pro 4 · 142mi</div>
              </div>
            </div>

            {/* Right column — readiness + weather */}
            <div className="stack" style={{ width: 320, flexShrink: 0 }}>
              <div className="card" style={{ padding: 18 }}>
                <Eyebrow>Readiness · this morning</Eyebrow>
                <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginTop: 8 }}>
                  <div style={{ fontSize: 44, fontWeight: 800, letterSpacing: "-0.03em", color: "var(--accent)" }} className="num">84</div>
                  <div style={{ fontSize: 12, color: "var(--fg-3)" }}>/ 100 · primed</div>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginTop: 14, paddingTop: 14, borderTop: "1px solid var(--hairline-2)" }}>
                  {[["HRV","62","ms"],["RHR","48","bpm"],["Sleep","7.4","h"],["Strain","412","TSS"]].map(([k,v,u],i)=>(
                    <div key={i} style={{ textAlign: "center" }}>
                      <div className="eyebrow" style={{ fontSize: 9 }}>{k}</div>
                      <div className="num" style={{ fontSize: 16, fontWeight: 700, marginTop: 4 }}>{v}</div>
                      <div style={{ fontSize: 10, color: "var(--fg-4)" }}>{u}</div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="card" style={{ padding: 18 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <Eyebrow>Weather · Washington DC</Eyebrow>
                  <Pill tone="good">Optimal</Pill>
                </div>
                <div style={{ display: "flex", alignItems: "baseline", gap: 6, marginTop: 10 }}>
                  <div style={{ fontSize: 38, fontWeight: 700, letterSpacing: "-0.02em" }} className="num">64°</div>
                  <div style={{ fontSize: 12, color: "var(--fg-3)" }}>feels 63° · partly cloudy</div>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 4, marginTop: 14 }}>
                  {[6,7,8,9,10,11,12].map((h, i) => (
                    <div key={i} style={{ textAlign: "center", fontSize: 10, color: "var(--fg-3)" }}>
                      <div className="mono" style={{ fontSize: 9, opacity: 0.7 }}>{h}AM</div>
                      <div style={{ height: 28 + i * 2, background: i < 3 ? "var(--ink-3)" : i < 5 ? "var(--accent)" : "var(--orange-deep)", marginTop: 6, borderRadius: 2 }} />
                      <div className="num" style={{ marginTop: 4, fontWeight: 600 }}>{58 + i * 2}°</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Tomorrow + upcoming + nudges */}
          <div className="row" style={{ marginBottom: 16 }}>
            <div className="card col" style={{ padding: 0 }}>
              <div style={{ display: "flex", justifyContent: "space-between", padding: "14px 18px", borderBottom: "1px solid var(--hairline-2)" }}>
                <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
                  <Eyebrow>Up next · 4 days</Eyebrow>
                </div>
                <div className="mono" style={{ fontSize: 10, letterSpacing: "0.18em", color: "var(--fg-3)" }}>VIEW PLAN →</div>
              </div>
              <div>
                {[
                  ["THU 28","Easy aerobic","Run","52 min","Z2","scheduled"],
                  ["FRI 29","Lower body strength","Strength","45 min","RPE 7","scheduled"],
                  ["SAT 30","Long run · fueling drill","Run","2h 10m","Z2/Z3","key"],
                  ["SUN 31","Recovery spin","Bike","60 min","Z1","optional"],
                ].map(([d, name, sport, dur, int, tag], i) => (
                  <div key={i} style={{ display: "grid", gridTemplateColumns: "70px 1fr 100px 90px 80px 110px", alignItems: "center", padding: "12px 18px", borderBottom: i < 3 ? "1px solid var(--hairline-2)" : "none", fontSize: 13 }}>
                    <span className="mono" style={{ fontSize: 10, letterSpacing: "0.18em", color: "var(--fg-3)" }}>{d}</span>
                    <span style={{ fontWeight: 600 }}>{name}</span>
                    <span style={{ color: "var(--fg-3)", fontSize: 12 }}>{sport}</span>
                    <span className="num" style={{ color: "var(--fg-2)", fontSize: 12 }}>{dur}</span>
                    <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>{int}</span>
                    <span style={{ justifySelf: "end" }}>
                      {tag === "key" ? <Pill tone="accent">★ KEY</Pill> : tag === "optional" ? <Pill>OPTIONAL</Pill> : <Pill>SCHED</Pill>}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Bottom row: stats strip + recent activity */}
          <div className="row" style={{ marginBottom: 16 }}>
            <div className="stat-card hi col"><div className="k">7-day load</div><div className="v num">612<span className="u">tss</span></div><div className="delta">▲ 18% vs last wk</div></div>
            <div className="stat-card col"><div className="k">Weekly miles</div><div className="v num">48.2<span className="u">mi</span></div><div className="delta">▲ 4.1</div></div>
            <div className="stat-card col"><div className="k">Sleep avg</div><div className="v num">7.4<span className="u">h</span></div><div className="delta">→ steady</div></div>
            <div className="stat-card col"><div className="k">Body weight</div><div className="v num">162<span className="u">lb</span></div><div className="delta" style={{ color: "var(--fg-3)" }}>—</div></div>
            <div className="stat-card col"><div className="k">Active injuries</div><div className="v num" style={{ color: "var(--good)" }}>0</div><div className="delta">clean</div></div>
          </div>

          {/* Recent strength + cardio */}
          <div className="row">
            <div className="card col" style={{ padding: 0 }}>
              <div style={{ display: "flex", justifyContent: "space-between", padding: "14px 18px", borderBottom: "1px solid var(--hairline-2)" }}>
                <Eyebrow>Recent strength · 5 sessions</Eyebrow>
                <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>VIEW ALL →</span>
              </div>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr style={{ color: "var(--fg-3)" }}>
                    {["Date","Exercise","Sets×Reps","Load","Outcome"].map((h,i)=>(
                      <th key={i} className="mono" style={{ textAlign: "left", padding: "10px 18px", fontSize: 9, letterSpacing: "0.18em", textTransform: "uppercase", fontWeight: 500, borderBottom: "1px solid var(--hairline-2)" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[
                    ["May 25","Back squat","3 × 5","225 lb","↑ progress"],
                    ["May 25","Romanian DL","3 × 8","185 lb","→ hold"],
                    ["May 23","Bench press","4 × 5","165 lb","↑ progress"],
                    ["May 23","Pull-up","4 × 6","BW+25","↑ progress"],
                    ["May 21","Front squat","3 × 5","185 lb","→ hold"],
                  ].map((r,i)=>(
                    <tr key={i} style={{ borderBottom: i < 4 ? "1px solid var(--hairline-2)" : "none" }}>
                      <td className="mono num" style={{ padding: "10px 18px", color: "var(--fg-3)", fontSize: 11 }}>{r[0]}</td>
                      <td style={{ padding: "10px 18px", fontWeight: 500 }}>{r[1]}</td>
                      <td className="num" style={{ padding: "10px 18px" }}>{r[2]}</td>
                      <td className="num" style={{ padding: "10px 18px" }}>{r[3]}</td>
                      <td style={{ padding: "10px 18px" }}>
                        <Pill tone={r[4].includes("↑") ? "good" : "warn"}>{r[4]}</Pill>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="card" style={{ padding: 18, width: 320, flexShrink: 0 }}>
              <Eyebrow>Training load · 4 weeks</Eyebrow>
              <div style={{ display: "flex", alignItems: "baseline", gap: 6, marginTop: 8 }}>
                <div className="num" style={{ fontSize: 32, fontWeight: 700 }}>612</div>
                <div style={{ fontSize: 12, color: "var(--fg-3)" }}>TSS this week</div>
              </div>
              <svg viewBox="0 0 280 100" style={{ width: "100%", height: 100, marginTop: 12 }}>
                {/* baseline */}
                <line x1="0" x2="280" y1="80" y2="80" stroke="var(--hairline)" />
                {/* ramp line */}
                <path d="M0 75 L40 70 L80 60 L120 55 L160 42 L200 36 L240 30 L280 25" stroke="var(--accent)" strokeWidth="2" fill="none" />
                {/* bars */}
                {[420, 460, 510, 540, 575, 595, 612].map((v, i) => (
                  <rect key={i} x={i * 40 + 4} y={90 - v * 0.1} width="28" height={v * 0.1} fill={i === 6 ? "var(--accent)" : "var(--ink-3)"} />
                ))}
              </svg>
              <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4, fontFamily: "var(--mono)", fontSize: 9, color: "var(--fg-4)" }}>
                {["W2","W3","W4","W5","W6","W7","W8"].map(w => <span key={w}>{w}</span>)}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// 2. TRAINING PLAN — Week view
// ═══════════════════════════════════════════════════════════════════
const ScreenPlan = () => {
  const days = [
    { d: "MON 26", date: "May 26", items: [
      { name: "Easy aerobic", sport: "Run", dur: "45 min", z: "Z2", done: true },
    ]},
    { d: "TUE 27", date: "May 27", items: [
      { name: "Threshold intervals", sport: "Run", dur: "68 min", z: "Z4", key: true, today: true },
      { name: "Upper push", sport: "Strength", dur: "40 min", z: "RPE 7" },
    ]},
    { d: "WED 28", date: "May 28", items: [
      { name: "Easy aerobic", sport: "Run", dur: "52 min", z: "Z2" },
    ]},
    { d: "THU 29", date: "May 29", items: [
      { name: "Lower strength", sport: "Strength", dur: "45 min", z: "RPE 7" },
      { name: "Mobility", sport: "Recovery", dur: "20 min", z: "—" },
    ]},
    { d: "FRI 30", date: "May 30", items: [
      { name: "VO2 short", sport: "Run", dur: "55 min", z: "Z5", key: true },
    ]},
    { d: "SAT 31", date: "May 31", items: [
      { name: "Long run · fueling", sport: "Run", dur: "2h 10m", z: "Z2/Z3", key: true },
    ]},
    { d: "SUN 01", date: "Jun 01", items: [
      { name: "Recovery spin", sport: "Bike", dur: "60 min", z: "Z1" },
    ]},
  ];
  return (
    <div className="screen">
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <Sidebar active="plan" />
        <div className="page">
          <TopBar crumbs={["Plan", "Boston Marathon ’26", "Week 8"]} actions={
            <div className="btn btn-primary"><Ic d={I.bolt} size={12} />Refresh plan</div>
          } />
          <div className="page-body">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 18 }}>
              <div>
                <Eyebrow>Build phase · Week 8 of 22 · 14 weeks to race</Eyebrow>
                <h1 className="page-title" style={{ marginTop: 8 }}>Threshold consolidation</h1>
                <div className="page-sub">Six structured sessions, one long run with fueling drill, ramp +5% vs last week.</div>
              </div>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <div className="btn btn-icon"><Ic d={I.chevL} size={14} /></div>
                <div className="mono" style={{ fontSize: 11, letterSpacing: "0.18em", padding: "0 12px" }}>WEEK 8</div>
                <div className="btn btn-icon"><Ic d={I.chevR} size={14} /></div>
              </div>
            </div>

            {/* Week grid */}
            <div className="card" style={{ padding: 0, marginBottom: 16, overflow: "hidden" }}>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)" }}>
                {days.map((day, di) => (
                  <div key={di} style={{ borderRight: di < 6 ? "1px solid var(--hairline-2)" : "none", padding: "16px 14px", minHeight: 280, background: day.items[0]?.today ? "color-mix(in oklab, var(--accent) 6%, transparent)" : "transparent" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 14 }}>
                      <span className="mono" style={{ fontSize: 10, letterSpacing: "0.18em", color: day.items[0]?.today ? "var(--accent)" : "var(--fg-3)" }}>{day.d}</span>
                      {day.items[0]?.today && <span className="pulse-dot" />}
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                      {day.items.map((it, ii) => (
                        <div key={ii} style={{
                          background: it.key ? "var(--accent)" : "var(--bg-3)",
                          color: it.key ? "var(--ink)" : "var(--fg)",
                          padding: "10px 12px",
                          borderRadius: 4,
                          opacity: it.done ? 0.5 : 1,
                          position: "relative",
                        }}>
                          {it.done && (
                            <div className="mono" style={{ position: "absolute", top: 6, right: 8, fontSize: 9, letterSpacing: "0.18em", opacity: 0.7 }}>✓ DONE</div>
                          )}
                          {it.key && !it.done && (
                            <div className="mono" style={{ fontSize: 9, letterSpacing: "0.18em", opacity: 0.7, marginBottom: 4 }}>★ KEY · {it.z}</div>
                          )}
                          {!it.key && !it.done && (
                            <div className="mono" style={{ fontSize: 9, letterSpacing: "0.18em", opacity: 0.6, marginBottom: 4, color: "var(--fg-3)" }}>{it.sport.toUpperCase()} · {it.z}</div>
                          )}
                          <div style={{ fontSize: 13, fontWeight: 600, lineHeight: 1.25 }}>{it.name}</div>
                          <div className="num" style={{ fontSize: 11, marginTop: 4, opacity: 0.8 }}>{it.dur}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              {/* Day-of-week labels */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", borderTop: "1px solid var(--hairline-2)", background: "var(--bg)" }}>
                {["Mon","Tue","Wed","Thu","Fri","Sat","Sun"].map((dn, i) => (
                  <div key={i} className="mono" style={{ padding: "10px 14px", fontSize: 9, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--fg-4)", borderRight: i < 6 ? "1px solid var(--hairline-2)" : "none" }}>{dn}</div>
                ))}
              </div>
            </div>

            {/* Bottom: phase progress + week totals */}
            <div className="row">
              <div className="card col" style={{ padding: 18 }}>
                <Eyebrow>Phase progress</Eyebrow>
                <div style={{ marginTop: 14 }}>
                  <div style={{ display: "flex", height: 32, borderRadius: 4, overflow: "hidden" }}>
                    <div style={{ flex: 4, background: "var(--ink-3)", display: "grid", placeItems: "center", fontSize: 10, fontFamily: "var(--mono)", letterSpacing: "0.18em", color: "var(--fg-3)" }}>BASE · 4w</div>
                    <div style={{ flex: 8, background: "var(--accent)", color: "var(--ink)", display: "grid", placeItems: "center", fontSize: 10, fontFamily: "var(--mono)", letterSpacing: "0.18em", fontWeight: 600 }}>BUILD · 8w</div>
                    <div style={{ flex: 6, background: "var(--bg-3)", display: "grid", placeItems: "center", fontSize: 10, fontFamily: "var(--mono)", letterSpacing: "0.18em", color: "var(--fg-4)" }}>PEAK · 6w</div>
                    <div style={{ flex: 4, background: "var(--bg-3)", display: "grid", placeItems: "center", fontSize: 10, fontFamily: "var(--mono)", letterSpacing: "0.18em", color: "var(--fg-4)" }}>TAPER · 4w</div>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8, fontFamily: "var(--mono)", fontSize: 9, color: "var(--fg-4)" }}>
                    <span>W1</span><span>W4</span><span style={{ color: "var(--accent)", fontWeight: 600 }}>W8 · YOU</span><span>W16</span><span>W22</span>
                  </div>
                </div>
                <div style={{ marginTop: 18, paddingTop: 14, borderTop: "1px solid var(--hairline-2)" }}>
                  <div className="kv"><span className="k">Target race</span><span className="v">Boston Marathon · Apr 20</span></div>
                  <div className="kv" style={{ marginTop: 8 }}><span className="k">Goal time</span><span className="v num">2:58:00</span></div>
                  <div className="kv" style={{ marginTop: 8 }}><span className="k">Predicted</span><span className="v num" style={{ color: "var(--accent)" }}>2:57:42</span></div>
                </div>
              </div>
              <div className="card" style={{ padding: 18, width: 360, flexShrink: 0 }}>
                <Eyebrow>Week 8 · totals</Eyebrow>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginTop: 14 }}>
                  {[["Duration","8h 35m"],["Distance","48.2 mi"],["TSS","612"],["Strength","1h 25m"]].map(([k,v],i)=>(
                    <div key={i}>
                      <div className="eyebrow" style={{ fontSize: 9 }}>{k}</div>
                      <div className="num" style={{ fontSize: 22, fontWeight: 700, marginTop: 4 }}>{v}</div>
                    </div>
                  ))}
                </div>
                <div style={{ marginTop: 18, paddingTop: 14, borderTop: "1px solid var(--hairline-2)" }}>
                  <div className="eyebrow" style={{ marginBottom: 8 }}>Intensity mix</div>
                  <div style={{ display: "flex", height: 10, borderRadius: 2, overflow: "hidden" }}>
                    <div style={{ flex: 62, background: "var(--good)" }} />
                    <div style={{ flex: 18, background: "var(--warn)" }} />
                    <div style={{ flex: 14, background: "var(--orange)" }} />
                    <div style={{ flex: 6, background: "var(--bad)" }} />
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6, fontFamily: "var(--mono)", fontSize: 9, color: "var(--fg-3)" }}>
                    <span>Z1-2 · 62%</span><span>Z3 · 18%</span><span>Z4 · 14%</span><span>Z5 · 6%</span>
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
// 3. TODAY'S WORKOUT — Detail view
// ═══════════════════════════════════════════════════════════════════
const ScreenWorkout = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="workout" />
      <div className="page">
        <TopBar crumbs={["Plan", "Week 8", "Threshold intervals"]} actions={null} />
        <div className="page-body" style={{ padding: 0 }}>
          <div style={{ padding: "28px 32px 0", display: "grid", gridTemplateColumns: "1fr 360px", gap: 24 }}>
            {/* LEFT — workout body */}
            <div>
              <Eyebrow accent>● Today · May 27 · Primary key session</Eyebrow>
              <h1 style={{ fontSize: 40, fontWeight: 800, letterSpacing: "-0.025em", lineHeight: 1.05, margin: "10px 0 8px" }}>
                Threshold intervals
              </h1>
              <div style={{ color: "var(--fg-3)", fontSize: 16, maxWidth: 580 }}>
                Six 5-minute blocks at lactate threshold, with two-minute easy returns. Owns the line where lactate clears as fast as you produce it.
              </div>

              {/* Targets strip */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", borderTop: "1px solid var(--hairline)", borderBottom: "1px solid var(--hairline)", marginTop: 28 }}>
                {[
                  ["Duration","68","min"],
                  ["Distance","9.4","mi"],
                  ["TSS","82",""],
                  ["IF","0.92",""],
                  ["Fueling","60","g/hr"],
                ].map(([k,v,u],i)=>(
                  <div key={i} style={{ padding: "16px 18px", borderRight: i < 4 ? "1px solid var(--hairline)" : "none" }}>
                    <div className="eyebrow">{k}</div>
                    <div style={{ marginTop: 6 }}>
                      <span className="num" style={{ fontSize: 26, fontWeight: 700 }}>{v}</span>
                      <span style={{ fontSize: 12, color: "var(--fg-3)", marginLeft: 4 }}>{u}</span>
                    </div>
                  </div>
                ))}
              </div>

              {/* Interval blocks */}
              <div style={{ marginTop: 28 }}>
                <Eyebrow>Structure</Eyebrow>
                <div className="card-flush" style={{ marginTop: 10, padding: 20 }}>
                  <svg viewBox="0 0 700 110" style={{ width: "100%", height: 110 }}>
                    <line x1="0" x2="700" y1="100" y2="100" stroke="var(--hairline)" />
                    <rect x="0"   y="60" width="70"  height="40" fill="var(--ink-3)" />
                    <text x="35" y="92" fontFamily="var(--mono)" fontSize="9" letterSpacing="2" textAnchor="middle" fill="var(--fg-3)">WU</text>
                    {[0,1,2,3,4,5].map(i => (
                      <g key={i} transform={`translate(${80 + i * 95}, 0)`}>
                        <rect x="0" y="10" width="60" height="90" fill="var(--orange)" />
                        <text x="30" y="60" fontFamily="var(--mono)" fontSize="10" fontWeight="600" textAnchor="middle" fill="var(--ink)">5'</text>
                        <text x="30" y="74" fontFamily="var(--mono)" fontSize="8" letterSpacing="1.5" textAnchor="middle" fill="var(--ink)" opacity="0.8">Z4</text>
                        <rect x="62" y="60" width="28" height="40" fill="var(--ink-3)" />
                        <text x="76" y="84" fontFamily="var(--mono)" fontSize="8" textAnchor="middle" fill="var(--fg-3)">2'</text>
                      </g>
                    ))}
                    <rect x="650" y="60" width="50" height="40" fill="var(--ink-3)" />
                    <text x="675" y="84" fontFamily="var(--mono)" fontSize="9" textAnchor="middle" fill="var(--fg-3)">CD</text>
                  </svg>
                </div>
              </div>

              {/* Coaching notes */}
              <div style={{ marginTop: 28 }}>
                <Eyebrow>Coaching notes</Eyebrow>
                <div style={{ marginTop: 12, padding: "20px 22px", background: "var(--bg-2)", borderLeft: "2px solid var(--accent)", borderRadius: "0 4px 4px 0", fontSize: 15, lineHeight: 1.6 }}>
                  Treat each rep as the same effort, not the same pace — fade is fine if it stays in Z4. <b>If HR drifts above 172 by rep 4</b>, hold the remaining reps to 4 minutes and bank the work. Fuel 30g carb at minute 30; rehearse race-day flask handling.
                </div>
              </div>

              {/* Block details */}
              <div style={{ marginTop: 28 }}>
                <Eyebrow>Block-by-block</Eyebrow>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, marginTop: 12 }}>
                  <thead>
                    <tr style={{ color: "var(--fg-3)" }}>
                      {["#","Block","Duration","Pace","HR","RPE"].map((h,i)=>(
                        <th key={i} className="mono" style={{ textAlign: "left", padding: "8px 12px", fontSize: 9, letterSpacing: "0.18em", textTransform: "uppercase", fontWeight: 500, borderBottom: "1px solid var(--hairline)" }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      ["1","Warm-up · easy with 4×30s strides","10:00","8:30","< 145","3"],
                      ["2","Threshold #1","5:00","6:42","165-168","7.5"],
                      ["3","Recovery","2:00","8:30","< 150","3"],
                      ["4","Threshold #2","5:00","6:42","165-168","7.5"],
                      ["5","Recovery","2:00","8:30","< 150","3"],
                      ["6","Threshold #3 · fuel at end","5:00","6:42","165-168","7.5"],
                      ["7","Recovery","2:00","8:30","< 150","3"],
                      ["8","Threshold #4-6 · repeat","21:00","6:42","165-172","8"],
                      ["9","Cool-down","7:00","9:00","< 140","2"],
                    ].map((r,i)=>(
                      <tr key={i} style={{ borderBottom: "1px solid var(--hairline-2)" }}>
                        <td className="mono" style={{ padding: "10px 12px", color: "var(--fg-4)", width: 30 }}>{r[0]}</td>
                        <td style={{ padding: "10px 12px", fontWeight: 500 }}>{r[1]}</td>
                        <td className="num" style={{ padding: "10px 12px", width: 80 }}>{r[2]}</td>
                        <td className="num" style={{ padding: "10px 12px", width: 70, color: "var(--fg-2)" }}>{r[3]}</td>
                        <td className="num" style={{ padding: "10px 12px", width: 80, color: "var(--fg-2)" }}>{r[4]}</td>
                        <td className="num" style={{ padding: "10px 12px", width: 50, color: "var(--fg-2)" }}>{r[5]}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div style={{ height: 40 }} />
            </div>

            {/* RIGHT — context rail */}
            <div className="stack" style={{ position: "sticky", top: 0, alignSelf: "start" }}>
              <div className="card" style={{ padding: 18 }}>
                <Eyebrow>Send to device</Eyebrow>
                <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 12 }}>
                  <div className="btn btn-primary" style={{ justifyContent: "center" }}>
                    <Ic d={I.check} size={12} sw={2.2} /> Mark complete
                  </div>
                  <div className="btn btn-ghost" style={{ justifyContent: "center" }}>
                    <Ic d={I.download} size={12} /> Download .FIT
                  </div>
                  <div className="btn btn-ghost" style={{ justifyContent: "center" }}>
                    <Ic d={I.upload} size={12} /> Upload completed .FIT
                  </div>
                  <div className="btn btn-text" style={{ justifyContent: "center", color: "var(--fg-3)" }}>
                    <Ic d={I.x} size={11} /> Skip today
                  </div>
                </div>
              </div>

              <div className="card" style={{ padding: 18 }}>
                <Eyebrow>Location · today</Eyebrow>
                <div style={{ marginTop: 12, fontWeight: 600 }}>Rock Creek loop</div>
                <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 2 }}>Washington DC · 4.2 mi · rolling</div>
                <div style={{ marginTop: 14, paddingTop: 14, borderTop: "1px solid var(--hairline-2)", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  <div><div className="eyebrow" style={{ fontSize: 9 }}>Temp</div><div className="num" style={{ fontWeight: 600, marginTop: 2 }}>64°F</div></div>
                  <div><div className="eyebrow" style={{ fontSize: 9 }}>Feels</div><div className="num" style={{ fontWeight: 600, marginTop: 2 }}>63°F</div></div>
                  <div><div className="eyebrow" style={{ fontSize: 9 }}>Wind</div><div className="num" style={{ fontWeight: 600, marginTop: 2 }}>6 mph NW</div></div>
                  <div><div className="eyebrow" style={{ fontSize: 9 }}>Humidity</div><div className="num" style={{ fontWeight: 600, marginTop: 2 }}>58%</div></div>
                </div>
              </div>

              <div className="card" style={{ padding: 18 }}>
                <Eyebrow>Kit recommendation</Eyebrow>
                <div style={{ marginTop: 10, fontSize: 12, color: "var(--fg-3)", marginBottom: 10 }}>From 14 sessions logged at 60-68°F partly cloudy</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {["Singlet","Split shorts","Crew socks","Endorphins Pro 4","Visor","Handheld 500ml"].map((k,i)=>(
                    <Pill key={i} tone="solid">{k}</Pill>
                  ))}
                </div>
              </div>

              <div className="card-flush" style={{ padding: 14, fontSize: 12, color: "var(--fg-3)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                  <Eyebrow>Generated</Eyebrow>
                  <span className="mono" style={{ fontSize: 10 }}>v3.2</span>
                </div>
                Built from your Garmin history (last 84 days), threshold test on May 4, and Boston goal pace. Refresh anytime.
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

Object.assign(window, { ScreenDashboard, ScreenPlan, ScreenWorkout });
