/* AIDSTATION redesign — Mobile screens
   Dashboard · Workout · Quick log sheet · Plan */

// ═══════════════════════════════════════════════════════════════════
// M1. MOBILE DASHBOARD
// ═══════════════════════════════════════════════════════════════════
const MobileDashboard = () => (
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
      <Eyebrow>Wed · May 27 · WK 8 · Build</Eyebrow>
      <h1 style={{ fontSize: 24, fontWeight: 700, letterSpacing: "-0.02em", lineHeight: 1.1, margin: "8px 0 4px" }}>
        Morning, Andrew.
      </h1>
      <div style={{ color: "var(--fg-3)", fontSize: 14 }}>Time to move.</div>

      {/* Readiness chip strip */}
      <div style={{ display: "flex", gap: 8, marginTop: 14, overflowX: "auto" }}>
        <Pill tone="accent">● READINESS 84</Pill>
        <Pill tone="good">▲ LOAD 612</Pill>
        <Pill>HRV 62</Pill>
        <Pill>RHR 48</Pill>
      </div>

      {/* Today's workout hero */}
      <div className="card" style={{ marginTop: 18, padding: 16, position: "relative", overflow: "hidden" }}>
        <div style={{ position: "absolute", top: 0, left: 0, bottom: 0, width: 3, background: "var(--accent)" }} />
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <Eyebrow accent>● TODAY · PRIMARY</Eyebrow>
            <div style={{ fontSize: 19, fontWeight: 700, letterSpacing: "-0.01em", marginTop: 6 }}>Threshold intervals</div>
            <div style={{ color: "var(--fg-3)", fontSize: 13, marginTop: 2 }}>6 × 5min @ FTHR · Run · 68 min</div>
          </div>
        </div>

        {/* Mini interval chart */}
        <svg viewBox="0 0 280 36" style={{ width: "100%", height: 36, marginTop: 14 }}>
          <rect x="0" y="22" width="22" height="14" fill="var(--ink-3)" />
          {[0,1,2,3,4,5].map(i => (
            <g key={i} transform={`translate(${26 + i * 38}, 0)`}>
              <rect x="0" y="4" width="24" height="32" fill="var(--accent)" />
              <rect x="26" y="22" width="8" height="14" fill="var(--ink-3)" />
            </g>
          ))}
          <rect x="258" y="22" width="22" height="14" fill="var(--ink-3)" />
        </svg>

        {/* Targets */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 0, marginTop: 14, borderTop: "1px solid var(--hairline-2)", paddingTop: 12 }}>
          {[["Pace","6:42","/mi"],["HR","168","bpm"],["Fuel","60","g/hr"]].map(([k,v,u],i)=>(
            <div key={i} style={{ textAlign: i === 0 ? "left" : i === 1 ? "center" : "right" }}>
              <div className="eyebrow" style={{ fontSize: 9 }}>{k}</div>
              <div style={{ marginTop: 4 }}>
                <span className="num" style={{ fontSize: 17, fontWeight: 700 }}>{v}</span>
                <span style={{ fontSize: 10, color: "var(--fg-3)", marginLeft: 3 }}>{u}</span>
              </div>
            </div>
          ))}
        </div>

        <div style={{ display: "flex", gap: 6, marginTop: 14 }}>
          <div className="btn btn-primary btn-sm" style={{ flex: 1, justifyContent: "center" }}>OPEN WORKOUT</div>
          <div className="btn btn-icon"><Ic d={I.download} size={13} /></div>
          <div className="btn btn-icon"><Ic d={I.check} size={13} sw={2.2} /></div>
        </div>
      </div>

      {/* Weather card */}
      <div className="card" style={{ marginTop: 12, padding: 14, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <Eyebrow>Weather · 7am</Eyebrow>
          <div style={{ display: "flex", alignItems: "baseline", gap: 6, marginTop: 4 }}>
            <span className="num" style={{ fontSize: 22, fontWeight: 700 }}>64°</span>
            <span style={{ fontSize: 12, color: "var(--fg-3)" }}>partly cloudy</span>
          </div>
        </div>
        <Pill tone="good">OPTIMAL</Pill>
      </div>

      {/* Up next */}
      <div style={{ marginTop: 22 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <Eyebrow>Up next · this week</Eyebrow>
          <span className="mono" style={{ fontSize: 9, letterSpacing: "0.18em", color: "var(--accent)" }}>VIEW PLAN →</span>
        </div>
        <div className="card" style={{ marginTop: 10, padding: 0 }}>
          {[
            ["THU","Easy aerobic","52'","Z2"],
            ["FRI","Lower strength","45'","RPE 7"],
            ["SAT","Long run · fueling","2h 10m","KEY"],
          ].map((r,i)=>(
            <div key={i} style={{ display: "grid", gridTemplateColumns: "44px 1fr auto", gap: 10, alignItems: "center", padding: "12px 14px", borderBottom: i < 2 ? "1px solid var(--hairline-2)" : "none" }}>
              <span className="mono" style={{ fontSize: 10, letterSpacing: "0.18em", color: "var(--fg-3)" }}>{r[0]}</span>
              <div>
                <div style={{ fontSize: 14, fontWeight: 500 }}>{r[1]}</div>
                <div className="num" style={{ fontSize: 11, color: "var(--fg-3)" }}>{r[2]}</div>
              </div>
              {r[3] === "KEY" ? <Pill tone="accent">★ KEY</Pill> : <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>{r[3]}</span>}
            </div>
          ))}
        </div>
      </div>

      {/* Stats row */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginTop: 22 }}>
        <div className="stat-card hi" style={{ padding: 14 }}>
          <div className="k">7-day load</div>
          <div className="v num" style={{ fontSize: 24 }}>612<span className="u">tss</span></div>
          <div className="delta">▲ 18%</div>
        </div>
        <div className="stat-card" style={{ padding: 14 }}>
          <div className="k">Miles · wk</div>
          <div className="v num" style={{ fontSize: 24 }}>48.2</div>
          <div className="delta">▲ 4.1</div>
        </div>
      </div>

      <div style={{ height: 12 }} />
    </div>

    <TabBar active="home" />
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// M2. MOBILE WORKOUT DETAIL
// ═══════════════════════════════════════════════════════════════════
const MobileWorkout = () => (
  <div className="screen">
    <StatusBar />
    <AppBar
      title="Threshold intervals"
      left={<Ic d={I.chevL} size={22} />}
      right={<Ic d={I.more} size={20} />}
    />

    <div style={{ flex: 1, overflow: "auto" }}>
      {/* Hero */}
      <div style={{ padding: "16px 18px 20px", borderBottom: "1px solid var(--hairline-2)" }}>
        <Eyebrow accent>● TODAY · MAY 27 · KEY SESSION</Eyebrow>
        <div style={{ fontSize: 13, color: "var(--fg-3)", marginTop: 8 }}>
          Six 5-minute blocks at lactate threshold with 2-min easy returns. Owns the line where lactate clears as fast as you make it.
        </div>
      </div>

      {/* Targets grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", borderBottom: "1px solid var(--hairline-2)" }}>
        {[
          ["Time","68","min"],
          ["Dist","9.4","mi"],
          ["TSS","82",""],
        ].map(([k,v,u],i)=>(
          <div key={i} style={{ padding: "14px 16px", borderRight: i < 2 ? "1px solid var(--hairline-2)" : "none" }}>
            <div className="eyebrow" style={{ fontSize: 9 }}>{k}</div>
            <div style={{ marginTop: 4 }}>
              <span className="num" style={{ fontSize: 19, fontWeight: 700 }}>{v}</span>
              <span style={{ fontSize: 10, color: "var(--fg-3)", marginLeft: 2 }}>{u}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Structure visualization */}
      <div style={{ padding: "18px" }}>
        <Eyebrow>Structure</Eyebrow>
        <svg viewBox="0 0 320 80" style={{ width: "100%", height: 80, marginTop: 10 }}>
          <rect x="0"   y="48" width="28" height="28" fill="var(--ink-3)" />
          <text x="14" y="68" fontFamily="var(--mono)" fontSize="8" textAnchor="middle" fill="var(--fg-3)">WU</text>
          {[0,1,2,3,4,5].map(i => (
            <g key={i} transform={`translate(${34 + i * 44}, 0)`}>
              <rect x="0" y="8" width="28" height="68" fill="var(--accent)" />
              <text x="14" y="44" fontFamily="var(--mono)" fontSize="9" fontWeight="600" textAnchor="middle" fill="var(--ink)">5'</text>
              <rect x="30" y="48" width="10" height="28" fill="var(--ink-3)" />
            </g>
          ))}
          <rect x="298" y="48" width="22" height="28" fill="var(--ink-3)" />
          <text x="309" y="68" fontFamily="var(--mono)" fontSize="8" textAnchor="middle" fill="var(--fg-3)">CD</text>
        </svg>
      </div>

      {/* Coach notes */}
      <div style={{ padding: "0 18px 18px" }}>
        <Eyebrow>Coaching notes</Eyebrow>
        <div style={{ marginTop: 10, padding: "14px 16px", background: "var(--bg-2)", borderLeft: "2px solid var(--accent)", borderRadius: "0 4px 4px 0", fontSize: 13, lineHeight: 1.55 }}>
          Same effort, not same pace — fade is OK if it stays Z4. If HR drifts above 172 by rep 4, hold remaining to 4 minutes. Fuel 30g carb at minute 30.
        </div>
      </div>

      {/* Blocks list */}
      <div style={{ padding: "0 18px 18px" }}>
        <Eyebrow>Blocks · 9</Eyebrow>
        <div style={{ marginTop: 10 }}>
          {[
            ["WU","Easy + 4× strides","10:00","8:30"],
            ["1","Threshold","5:00","6:42"],
            ["—","Recovery","2:00","8:30"],
            ["2","Threshold","5:00","6:42"],
            ["—","Recovery","2:00","8:30"],
            ["3","Threshold","5:00","6:42"],
          ].map((r,i)=>(
            <div key={i} style={{ display: "grid", gridTemplateColumns: "40px 1fr 60px 60px", alignItems: "center", padding: "10px 0", borderBottom: i < 5 ? "1px solid var(--hairline-2)" : "none", fontSize: 13 }}>
              <span className="mono" style={{ fontSize: 11, letterSpacing: "0.12em", color: r[0] === "—" ? "var(--fg-4)" : r[0] === "WU" ? "var(--fg-3)" : "var(--accent)" }}>{r[0]}</span>
              <span style={{ color: "var(--fg-2)" }}>{r[1]}</span>
              <span className="num" style={{ fontWeight: 600 }}>{r[2]}</span>
              <span className="num" style={{ color: "var(--fg-3)" }}>{r[3]}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Locale */}
      <div className="card" style={{ margin: "0 18px 18px", padding: 14 }}>
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <Eyebrow>Location</Eyebrow>
          <Pill tone="good">OPTIMAL</Pill>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 10 }}>
          <div>
            <div style={{ fontWeight: 600, fontSize: 14 }}>Rock Creek loop</div>
            <div style={{ fontSize: 11, color: "var(--fg-3)" }}>4.2 mi · rolling · 64°F</div>
          </div>
          <Ic d={I.pin} size={20} />
        </div>
      </div>
    </div>

    {/* Bottom action bar */}
    <div style={{ padding: "10px 14px 22px", borderTop: "1px solid var(--hairline-2)", display: "flex", gap: 8, background: "var(--bg)", flexShrink: 0 }}>
      <div className="btn btn-ghost btn-icon" style={{ width: 44, height: 44 }}><Ic d={I.x} size={14} /></div>
      <div className="btn btn-ghost btn-icon" style={{ width: 44, height: 44 }}><Ic d={I.download} size={14} /></div>
      <div className="btn btn-primary" style={{ flex: 1, justifyContent: "center", padding: "12px 16px" }}>
        <Ic d={I.check} size={14} sw={2.2} /> MARK COMPLETE
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// M3. MOBILE QUICK LOG — Bottom sheet
// ═══════════════════════════════════════════════════════════════════
const MobileQuickLog = () => (
  <div className="screen">
    <StatusBar />

    {/* Dimmed background — dashboard ghost */}
    <div style={{ flex: 1, position: "relative", overflow: "hidden" }}>
      <div style={{ position: "absolute", inset: 0, padding: 18, opacity: 0.25, pointerEvents: "none" }}>
        <Eyebrow>WED · MAY 27</Eyebrow>
        <div style={{ fontSize: 24, fontWeight: 700, marginTop: 8 }}>Morning, Andrew.</div>
        <div className="card" style={{ marginTop: 24, padding: 16, height: 200 }} />
        <div className="card" style={{ marginTop: 12, padding: 16, height: 100 }} />
      </div>
      <div style={{ position: "absolute", inset: 0, background: "color-mix(in oklab, var(--ink) 60%, transparent)" }} />

      {/* Sheet */}
      <div style={{
        position: "absolute", left: 0, right: 0, bottom: 0,
        background: "var(--bg)",
        borderTop: "1px solid var(--hairline)",
        borderRadius: "16px 16px 0 0",
        padding: "10px 0 28px",
        maxHeight: "82%", display: "flex", flexDirection: "column",
      }}>
        <div style={{ width: 40, height: 4, background: "var(--hairline)", borderRadius: 2, margin: "0 auto 14px" }} />
        <div style={{ padding: "0 18px 14px", borderBottom: "1px solid var(--hairline-2)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <Eyebrow accent>● QUICK LOG</Eyebrow>
            <div style={{ fontSize: 18, fontWeight: 700, marginTop: 4 }}>What did you do?</div>
          </div>
          <Ic d={I.x} size={20} />
        </div>

        <div style={{ flex: 1, overflow: "auto", padding: "16px 18px" }}>
          {/* Activity */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
            {[
              ["Run", I.workout, true],
              ["Bike", I.workout, false],
              ["Strength", I.weight, false],
              ["Swim", I.workout, false],
              ["Body", I.weight, false],
              ["Other", I.plus, false],
            ].map(([label, icon, active], i) => (
              <div key={i} style={{
                padding: "14px 8px", textAlign: "center", borderRadius: 4,
                border: "1px solid " + (active ? "var(--accent)" : "var(--hairline)"),
                background: active ? "color-mix(in oklab, var(--accent) 12%, transparent)" : "transparent",
                color: active ? "var(--fg)" : "var(--fg-2)",
              }}>
                <Ic d={icon} size={20} />
                <div style={{ fontSize: 12, fontWeight: 500, marginTop: 4 }}>{label}</div>
              </div>
            ))}
          </div>

          {/* Inline fields */}
          <div className="card-flush" style={{ marginTop: 18, padding: 0 }}>
            {[
              ["Duration", "1h 08m"],
              ["Distance", "9.42 mi"],
              ["Avg pace", "7:14 /mi"],
              ["Avg HR",   "152 bpm"],
            ].map(([k, v], i) => (
              <div key={i} style={{ padding: "14px 16px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: i < 3 ? "1px solid var(--hairline-2)" : "none" }}>
                <div className="eyebrow">{k}</div>
                <div className="num" style={{ fontSize: 15, fontWeight: 600 }}>{v}</div>
              </div>
            ))}
          </div>

          {/* RPE */}
          <div style={{ marginTop: 18 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <Eyebrow>RPE</Eyebrow>
              <span className="mono" style={{ fontSize: 10, color: "var(--accent)" }}>7 · COMFORTABLY HARD</span>
            </div>
            <div style={{ marginTop: 10, display: "flex", gap: 3 }}>
              {[1,2,3,4,5,6,7,8,9,10].map(n => (
                <div key={n} style={{
                  flex: 1, aspectRatio: 1, display: "grid", placeItems: "center",
                  border: "1px solid " + (n === 7 ? "var(--accent)" : "var(--hairline)"),
                  background: n === 7 ? "color-mix(in oklab, var(--accent) 14%, transparent)" : "transparent",
                  color: n <= 7 ? "var(--fg)" : "var(--fg-3)",
                  fontFamily: "var(--mono)", fontSize: 11, fontWeight: 500, borderRadius: 3,
                }}>{n}</div>
              ))}
            </div>
          </div>

          {/* Plan match */}
          <div style={{ marginTop: 18, padding: "12px 14px", background: "color-mix(in oklab, var(--accent) 10%, transparent)", borderRadius: 4, border: "1px solid color-mix(in oklab, var(--accent) 40%, transparent)" }}>
            <div className="eyebrow accent">✓ MATCHED TO PLAN</div>
            <div style={{ fontSize: 13, fontWeight: 500, marginTop: 4 }}>Threshold intervals · today</div>
            <div style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 2 }}>We'll mark this workout complete on save.</div>
          </div>

          <div className="btn btn-text" style={{ marginTop: 14, justifyContent: "center", color: "var(--fg-3)", fontSize: 10 }}>
            OR LOG VIA TEXT: "60 MIN EASY, FELT GREAT" →
          </div>
        </div>

        <div style={{ padding: "12px 18px 0", borderTop: "1px solid var(--hairline-2)", display: "flex", gap: 8 }}>
          <div className="btn btn-ghost" style={{ flex: 1, justifyContent: "center", padding: "12px 16px" }}>SAVE</div>
          <div className="btn btn-primary" style={{ flex: 2, justifyContent: "center", padding: "12px 16px" }}>
            <Ic d={I.check} size={13} sw={2.2} /> SAVE & COMPLETE
          </div>
        </div>
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// M4. MOBILE PLAN
// ═══════════════════════════════════════════════════════════════════
const MobilePlan = () => (
  <div className="screen">
    <StatusBar />
    <AppBar
      title="Plan"
      left={<Ic d={I.menu} size={22} />}
      right={<div className="mono" style={{ fontSize: 10, letterSpacing: "0.18em", color: "var(--accent)" }}>REFRESH</div>}
    />

    {/* Phase header */}
    <div style={{ padding: "14px 18px 16px", borderBottom: "1px solid var(--hairline-2)" }}>
      <Eyebrow>BUILD · WEEK 8 of 22 · 14 weeks out</Eyebrow>
      <div style={{ marginTop: 8, fontSize: 18, fontWeight: 700, letterSpacing: "-0.01em" }}>Boston Marathon ’26</div>
      <div style={{ marginTop: 12, display: "flex", height: 8, borderRadius: 2, overflow: "hidden" }}>
        <div style={{ flex: 4, background: "var(--ink-3)" }} />
        <div style={{ flex: 8, background: "var(--accent)" }} />
        <div style={{ flex: 6, background: "var(--bg-3)" }} />
        <div style={{ flex: 4, background: "var(--bg-3)" }} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6, fontFamily: "var(--mono)", fontSize: 9, letterSpacing: "0.12em", color: "var(--fg-3)" }}>
        <span>BASE</span><span style={{ color: "var(--accent)" }}>BUILD ●</span><span>PEAK</span><span>TAPER</span>
      </div>
    </div>

    {/* Week picker */}
    <div style={{ padding: "12px 18px", display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: "1px solid var(--hairline-2)" }}>
      <Ic d={I.chevL} size={18} />
      <div className="mono" style={{ fontSize: 11, letterSpacing: "0.2em", fontWeight: 600 }}>WEEK 8 · MAY 26 – JUN 01</div>
      <Ic d={I.chevR} size={18} />
    </div>

    {/* Day list */}
    <div style={{ flex: 1, overflow: "auto" }}>
      {[
        { d: "MON", date: "26", items: [{ name: "Easy aerobic", sport: "Run", dur: "45'", done: true }] },
        { d: "TUE", date: "27", today: true, items: [
          { name: "Threshold intervals", sport: "Run", dur: "68'", key: true, today: true },
          { name: "Upper push", sport: "Strength", dur: "40'" },
        ] },
        { d: "WED", date: "28", items: [{ name: "Easy aerobic", sport: "Run", dur: "52'" }] },
        { d: "THU", date: "29", items: [
          { name: "Lower strength", sport: "Strength", dur: "45'" },
          { name: "Mobility", sport: "Recovery", dur: "20'" },
        ] },
        { d: "FRI", date: "30", items: [{ name: "VO2 short", sport: "Run", dur: "55'", key: true }] },
        { d: "SAT", date: "31", items: [{ name: "Long run · fueling", sport: "Run", dur: "2h 10m", key: true }] },
        { d: "SUN", date: "01", items: [{ name: "Recovery spin", sport: "Bike", dur: "60'" }] },
      ].map((day, i) => (
        <div key={i} style={{
          display: "grid", gridTemplateColumns: "56px 1fr",
          borderBottom: "1px solid var(--hairline-2)",
          background: day.today ? "color-mix(in oklab, var(--accent) 6%, transparent)" : "transparent",
        }}>
          <div style={{ padding: "14px 0 14px 18px", borderRight: "1px solid var(--hairline-2)" }}>
            <div className="mono" style={{ fontSize: 9, letterSpacing: "0.18em", color: day.today ? "var(--accent)" : "var(--fg-3)" }}>{day.d}</div>
            <div className="num" style={{ fontSize: 22, fontWeight: 700, lineHeight: 1, marginTop: 4, color: day.today ? "var(--accent)" : "var(--fg)" }}>{day.date}</div>
          </div>
          <div style={{ padding: "12px 16px", display: "flex", flexDirection: "column", gap: 6 }}>
            {day.items.map((it, ii) => (
              <div key={ii} style={{
                display: "flex", justifyContent: "space-between", alignItems: "center",
                padding: "8px 10px",
                background: it.key ? "var(--accent)" : "var(--bg-2)",
                color: it.key ? "var(--ink)" : "var(--fg)",
                borderRadius: 4,
                opacity: it.done ? 0.5 : 1,
              }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>
                    {it.done && "✓ "}{it.name}
                  </div>
                  <div className="mono" style={{ fontSize: 9, letterSpacing: "0.16em", opacity: 0.7, marginTop: 2, textTransform: "uppercase" }}>{it.sport}</div>
                </div>
                <div className="num" style={{ fontSize: 12, fontWeight: 600, opacity: 0.85 }}>{it.dur}</div>
              </div>
            ))}
          </div>
        </div>
      ))}

      <div style={{ padding: "16px 18px", display: "flex", justifyContent: "space-between", fontSize: 12, color: "var(--fg-3)" }}>
        <span className="mono" style={{ letterSpacing: "0.16em" }}>WK TOTAL</span>
        <span className="num">8h 35m · 48.2 mi · 612 tss</span>
      </div>
    </div>

    <TabBar active="plan" />
  </div>
);

Object.assign(window, { MobileDashboard, MobileWorkout, MobileQuickLog, MobilePlan });
