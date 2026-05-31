/* AIDSTATION redesign — Desktop screens (part 2)
   Log (adaptive · type picker drives right pane) · Onboarding (6 steps) · Login */

// ═══════════════════════════════════════════════════════════════════
// 4. LOG — single landing, type picker, adaptive right pane
// ═══════════════════════════════════════════════════════════════════
const LOG_TYPES = [
  { key: "cardio",     label: "Cardio",      sub: "Run · bike · swim · row", icon: I.workout },
  { key: "strength",   label: "Strength",    sub: "Set-by-set logging",      icon: I.weight },
  { key: "body",       label: "Body",        sub: "Weight · BF% · RHR · VO2max", icon: I.body },
  { key: "wellness",   label: "Wellness",    sub: "Sleep · energy · mood",   icon: I.pulse },
  { key: "conditions", label: "Conditions",  sub: "Weather · clothing · comfort", icon: I.cloud },
  { key: "injury",     label: "Injury",      sub: "Body part · severity",    icon: I.bandage },
];

// — Type picker (left column) ————————————————————————————————
const LogTypePicker = ({ active }) => (
  <div>
    <Eyebrow>Log type</Eyebrow>
    <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 12 }}>
      {LOG_TYPES.map((t) => {
        const isActive = t.key === active;
        return (
          <div key={t.key} style={{
            padding: "14px 16px",
            border: "1px solid " + (isActive ? "var(--accent)" : "var(--hairline)"),
            background: isActive ? "color-mix(in oklab, var(--accent) 10%, transparent)" : "transparent",
            borderRadius: 4,
            display: "flex", alignItems: "center", gap: 12,
            position: "relative",
          }}>
            {isActive && <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 2, background: "var(--accent)" }} />}
            <div style={{ width: 32, height: 32, borderRadius: 4, background: isActive ? "var(--accent)" : "var(--bg-3)", color: isActive ? "var(--ink)" : "var(--fg-2)", display: "grid", placeItems: "center", flexShrink: 0 }}>
              <Ic d={t.icon} size={16} />
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 14, fontWeight: 600 }}>{t.label}</div>
              <div className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--fg-3)", marginTop: 2 }}>{t.sub}</div>
            </div>
            {isActive && <Ic d={I.chevR} size={14} />}
          </div>
        );
      })}
    </div>

    <div style={{ marginTop: 22, padding: "14px 16px", border: "1px dashed var(--hairline)", borderRadius: 4 }}>
      <Eyebrow>Or · log via text</Eyebrow>
      <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 6 }}>"60 min easy run, felt great"</div>
      <div className="mono" style={{ fontSize: 10, color: "var(--fg-4)", marginTop: 8, letterSpacing: "0.14em", textTransform: "uppercase" }}>WE PARSE IT \u00b7 ANY TYPE \u2192</div>
    </div>
  </div>
);

// — Cardio form ————————————————————————————————————————————
const LogCardioForm = () => (
  <>
    <div className="card-flush" style={{ padding: 0 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr" }}>
        {[
          ["Activity", "Run", true],
          ["Date · time", "Tue May 27 · 06:48", false],
          ["Location", "Rock Creek loop", false],
          ["Duration", "1h 08m", false, "min \u00b7 auto-split"],
          ["Distance", "9.42 mi", false, "GPS \u00b7 editable"],
          ["Avg pace", "7:14 /mi", false, "derived"],
        ].map(([label, value, primary, helper], i) => (
          <div key={i} style={{
            padding: "18px 20px",
            borderRight: i % 3 < 2 ? "1px solid var(--hairline)" : "none",
            borderBottom: i < 3 ? "1px solid var(--hairline)" : "none",
          }}>
            <div className="eyebrow" style={{ fontSize: 9 }}>{label}</div>
            <div className="num" style={{ fontSize: 18, fontWeight: 600, marginTop: 6 }}>{value}</div>
            {helper && <div className="mono" style={{ fontSize: 10, color: "var(--fg-4)", marginTop: 4, letterSpacing: "0.1em", textTransform: "uppercase" }}>{helper}</div>}
          </div>
        ))}
      </div>
    </div>

    {/* HR + zones */}
    <div style={{ marginTop: 24 }}>
      <Eyebrow>Heart rate · zones</Eyebrow>
      <div className="card" style={{ marginTop: 10, padding: 18 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 12 }}>
          <div className="num" style={{ fontSize: 20, fontWeight: 700 }}>152 <span style={{ color: "var(--fg-3)", fontWeight: 400 }}>/ 178</span> <span style={{ fontSize: 11, color: "var(--fg-3)", fontWeight: 400 }}>bpm avg/max</span></div>
          <div className="mono" style={{ fontSize: 10, letterSpacing: "0.18em", color: "var(--fg-3)" }}>Z2 PRIMARY \u00b7 Z4 SPIKE</div>
        </div>
        <div style={{ display: "flex", height: 10, borderRadius: 2, overflow: "hidden", marginBottom: 6 }}>
          <div style={{ flex: 8, background: "var(--ink-3)" }} />
          <div style={{ flex: 38, background: "var(--good)" }} />
          <div style={{ flex: 28, background: "var(--warn)" }} />
          <div style={{ flex: 18, background: "var(--orange)" }} />
          <div style={{ flex: 8, background: "var(--bad)" }} />
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 8, fontFamily: "var(--mono)", fontSize: 10, color: "var(--fg-3)" }}>
          {[["Z1","8%"],["Z2","38%"],["Z3","28%"],["Z4","18%"],["Z5","8%"]].map(([z,p],i)=>(
            <div key={i}><span style={{ letterSpacing: "0.18em", color: "var(--fg)" }}>{z}</span><span className="num" style={{ marginLeft: 6 }}>{p}</span></div>
          ))}
        </div>
      </div>
    </div>

    {/* RPE + Comfort */}
    <div style={{ marginTop: 24, display: "grid", gridTemplateColumns: "2fr 1fr", gap: 16 }}>
      <div>
        <Eyebrow>RPE \u00b7 Perceived effort</Eyebrow>
        <div style={{ marginTop: 10, display: "flex", gap: 4 }}>
          {[1,2,3,4,5,6,7,8,9,10].map(n => (
            <div key={n} style={{
              flex: 1, aspectRatio: 1, display: "grid", placeItems: "center",
              border: "1px solid " + (n === 7 ? "var(--accent)" : "var(--hairline)"),
              background: n === 7 ? "color-mix(in oklab, var(--accent) 14%, transparent)" : "transparent",
              color: n === 7 ? "var(--fg)" : "var(--fg-3)",
              fontFamily: "var(--mono)", fontSize: 12, fontWeight: 500, borderRadius: 4,
            }}>{n}</div>
          ))}
        </div>
      </div>
      <div>
        <Eyebrow>Mark complete</Eyebrow>
        <div style={{ marginTop: 10, padding: "10px 12px", border: "1px solid color-mix(in oklab, var(--accent) 40%, transparent)", background: "color-mix(in oklab, var(--accent) 8%, transparent)", borderRadius: 4 }}>
          <div className="eyebrow accent" style={{ fontSize: 9 }}>\u25cf MATCHED \u00b7 PLAN ITEM</div>
          <div style={{ fontSize: 12, fontWeight: 500, marginTop: 4 }}>Threshold intervals \u00b7 Today</div>
        </div>
      </div>
    </div>

    {/* Notes */}
    <div style={{ marginTop: 24 }}>
      <Eyebrow>Session notes</Eyebrow>
      <div className="card-flush" style={{ marginTop: 10, padding: "14px 16px", fontSize: 14, minHeight: 70, color: "var(--fg-2)" }}>
        Held pace cleanly through mile 6, hamstring twinge at mile 8 \u2014 eased into Z2 to finish.
      </div>
    </div>
  </>
);

// — Strength form ——————————————————————————————————————————
const LogStrengthForm = () => (
  <>
    <div className="card-flush" style={{ padding: 0 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr" }}>
        <div style={{ padding: "18px 20px", borderRight: "1px solid var(--hairline)" }}>
          <div className="eyebrow" style={{ fontSize: 9 }}>Date</div>
          <div className="num" style={{ fontSize: 18, fontWeight: 600, marginTop: 6 }}>Tue May 27, 2026</div>
        </div>
        <div style={{ padding: "18px 20px", borderRight: "1px solid var(--hairline)" }}>
          <div className="eyebrow" style={{ fontSize: 9 }}>Link to plan</div>
          <div style={{ fontSize: 14, fontWeight: 500, marginTop: 6, color: "var(--accent)" }}>Upper push \u00b7 today</div>
        </div>
        <div style={{ padding: "18px 20px" }}>
          <div className="eyebrow" style={{ fontSize: 9 }}>Location</div>
          <div style={{ fontSize: 14, fontWeight: 500, marginTop: 6 }}>Home garage</div>
        </div>
      </div>
    </div>

    {/* Exercise groups */}
    <div style={{ marginTop: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 10 }}>
        <Eyebrow>Set log \u00b7 add as you go</Eyebrow>
        <div className="btn btn-ghost btn-sm"><Ic d={I.plus} size={11} sw={2} /> ADD EXERCISE</div>
      </div>

      {/* Exercise 1: Bench press */}
      <div className="card" style={{ padding: 0, marginBottom: 12 }}>
        <div style={{ padding: "12px 18px", borderBottom: "1px solid var(--hairline-2)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <span style={{ fontWeight: 600, fontSize: 15 }}>Bench press</span>
            <span className="mono" style={{ fontSize: 10, letterSpacing: "0.16em", color: "var(--fg-3)", marginLeft: 10 }}>3 SETS \u00b7 TARGET 4\u00d75 @ 165LB</span>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>RPE</span>
            <div className="num" style={{ width: 38, padding: "4px 8px", textAlign: "center", border: "1px solid var(--hairline)", borderRadius: 3, fontWeight: 600 }}>8</div>
          </div>
        </div>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr>
              {["#","Reps","Weight","Duration",""].map((h,i)=>(
                <th key={i} className="mono" style={{ padding: "10px 14px", textAlign: "left", fontSize: 9, letterSpacing: "0.18em", textTransform: "uppercase", fontWeight: 500, color: "var(--fg-3)", borderBottom: "1px solid var(--hairline-2)" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[["1","5","165 lb","\u2014"],["2","5","165 lb","\u2014"],["3","4","165 lb","\u2014"]].map((r,i)=>(
              <tr key={i} style={{ borderBottom: "1px solid var(--hairline-2)" }}>
                <td className="mono" style={{ padding: "10px 14px", width: 30, color: "var(--fg-3)" }}>{r[0]}</td>
                <td className="num" style={{ padding: "10px 14px", fontWeight: 600 }}>{r[1]}</td>
                <td className="num" style={{ padding: "10px 14px" }}>{r[2]}</td>
                <td className="num" style={{ padding: "10px 14px", color: "var(--fg-3)" }}>{r[3]}</td>
                <td style={{ padding: "10px 14px", textAlign: "right" }}><Ic d={I.x} size={12} /></td>
              </tr>
            ))}
          </tbody>
        </table>
        <div style={{ padding: "10px 18px", display: "flex", justifyContent: "space-between" }}>
          <div className="btn btn-text btn-sm" style={{ color: "var(--accent)" }}><Ic d={I.plus} size={11} sw={2} /> ADD SET</div>
          <Pill tone="good">\u2191 PROGRESS</Pill>
        </div>
      </div>

      {/* Exercise 2: Pull-up */}
      <div className="card" style={{ padding: 0, marginBottom: 12 }}>
        <div style={{ padding: "12px 18px", borderBottom: "1px solid var(--hairline-2)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <span style={{ fontWeight: 600, fontSize: 15 }}>Pull-up</span>
            <span className="mono" style={{ fontSize: 10, letterSpacing: "0.16em", color: "var(--fg-3)", marginLeft: 10 }}>4 SETS \u00b7 TARGET 4\u00d76 @ BW+25LB</span>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>RPE</span>
            <div className="num" style={{ width: 38, padding: "4px 8px", textAlign: "center", border: "1px solid var(--hairline)", borderRadius: 3, fontWeight: 600 }}>7.5</div>
          </div>
        </div>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <tbody>
            {[["1","6","BW+25","\u2014"],["2","6","BW+25","\u2014"],["3","5","BW+25","\u2014"],["4","5","BW+25","\u2014"]].map((r,i)=>(
              <tr key={i} style={{ borderBottom: i < 3 ? "1px solid var(--hairline-2)" : "none" }}>
                <td className="mono" style={{ padding: "10px 14px", width: 30, color: "var(--fg-3)" }}>{r[0]}</td>
                <td className="num" style={{ padding: "10px 14px", fontWeight: 600 }}>{r[1]}</td>
                <td className="num" style={{ padding: "10px 14px" }}>{r[2]}</td>
                <td className="num" style={{ padding: "10px 14px", color: "var(--fg-3)" }}>{r[3]}</td>
                <td style={{ padding: "10px 14px", textAlign: "right" }}><Ic d={I.x} size={12} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="btn btn-ghost" style={{ width: "100%", justifyContent: "center", padding: "14px 16px" }}>
        <Ic d={I.plus} size={12} sw={2} /> ADD EXERCISE
      </div>
    </div>
  </>
);

// — Body form ——————————————————————————————————————————————
const LogBodyForm = () => (
  <>
    <div className="card-flush" style={{ padding: 0 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr" }}>
        {[
          ["Date", "Tue May 27, 2026", "today"],
          ["Time", "06:24 AM", "before breakfast"],
          ["Source", "Manual", "or import from provider"],
        ].map(([k,v,h],i)=>(
          <div key={i} style={{ padding: "18px 20px", borderRight: i < 2 ? "1px solid var(--hairline)" : "none" }}>
            <div className="eyebrow" style={{ fontSize: 9 }}>{k}</div>
            <div className="num" style={{ fontSize: 16, fontWeight: 600, marginTop: 6 }}>{v}</div>
            <div className="mono" style={{ fontSize: 10, color: "var(--fg-4)", marginTop: 4, letterSpacing: "0.1em", textTransform: "uppercase" }}>{h}</div>
          </div>
        ))}
      </div>
    </div>

    {/* Body metric cards */}
    <div style={{ marginTop: 24 }}>
      <Eyebrow>Metrics \u00b7 fill what you measured today</Eyebrow>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 12, marginTop: 12 }}>
        {[
          { label: "Weight",   value: "162.4", unit: "lb",  prev: "162.8 yesterday",  delta: "\u25bc 0.4", trend: [161, 162, 163, 162, 162.5, 162.8, 162.4] },
          { label: "Body fat", value: "12.8",  unit: "%",   prev: "13.0 last week",   delta: "\u25bc 0.2", trend: [13.4, 13.2, 13.1, 13.0, 13.0, 12.9, 12.8] },
          { label: "Resting HR", value: "48",  unit: "bpm", prev: "47 last week",     delta: "\u25b2 1",   trend: [50, 49, 48, 47, 48, 47, 48] },
          { label: "VO2 max",  value: "62",    unit: "ml",  prev: "61 last test",     delta: "\u25b2 1",   trend: [58, 59, 60, 60, 61, 61, 62] },
        ].map((m, i) => (
          <div key={i} className="card" style={{ padding: 18 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div>
                <Eyebrow>{m.label}</Eyebrow>
                <div style={{ marginTop: 8 }}>
                  <span className="num" style={{ fontSize: 32, fontWeight: 700, letterSpacing: "-0.02em" }}>{m.value}</span>
                  <span style={{ fontSize: 12, color: "var(--fg-3)", marginLeft: 4 }}>{m.unit}</span>
                </div>
                <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", marginTop: 4, letterSpacing: "0.12em" }}>{m.prev} \u00b7 {m.delta}</div>
              </div>
              <svg viewBox="0 0 100 36" style={{ width: 100, height: 36 }}>
                <polyline
                  points={m.trend.map((v, i) => `${i * 16},${36 - ((v - Math.min(...m.trend)) / (Math.max(...m.trend) - Math.min(...m.trend) || 1)) * 28 - 4}`).join(" ")}
                  fill="none" stroke="var(--accent)" strokeWidth="1.5"
                />
              </svg>
            </div>
          </div>
        ))}
      </div>
    </div>

    <div style={{ marginTop: 24 }}>
      <Eyebrow>Notes</Eyebrow>
      <div className="card-flush" style={{ marginTop: 10, padding: "14px 16px", fontSize: 14, minHeight: 60, color: "var(--fg-3)" }}>
        Add notes \u2014 illness, travel, big meal yesterday...
      </div>
    </div>
  </>
);

// — Wellness form ——————————————————————————————————————————
const LogWellnessForm = () => (
  <>
    <div className="card-flush" style={{ padding: 0 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr" }}>
        <div style={{ padding: "18px 20px", borderRight: "1px solid var(--hairline)" }}>
          <div className="eyebrow" style={{ fontSize: 9 }}>Date</div>
          <div className="num" style={{ fontSize: 16, fontWeight: 600, marginTop: 6 }}>Tue May 27, 2026</div>
        </div>
        <div style={{ padding: "18px 20px", borderRight: "1px solid var(--hairline)" }}>
          <div className="eyebrow" style={{ fontSize: 9 }}>Sleep \u00b7 hours</div>
          <div className="num" style={{ fontSize: 22, fontWeight: 700, marginTop: 6 }}>7.4 <span style={{ fontSize: 12, color: "var(--fg-3)", fontWeight: 400 }}>h</span></div>
        </div>
        <div style={{ padding: "18px 20px" }}>
          <div className="eyebrow" style={{ fontSize: 9 }}>Logged at</div>
          <div className="num" style={{ fontSize: 16, fontWeight: 600, marginTop: 6 }}>06:32 AM</div>
        </div>
      </div>
    </div>

    {/* 1-5 scales */}
    <div style={{ marginTop: 24 }}>
      <Eyebrow>Self-report \u00b7 1\u20135 \u00b7 1 = worst \u00b7 5 = best</Eyebrow>
      <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 14, marginTop: 12 }}>
        {[
          { label: "Sleep quality", selected: 4 },
          { label: "Energy",        selected: 4 },
          { label: "Soreness",      selected: 3, hint: "(1 = sore everywhere \u00b7 5 = fresh)" },
          { label: "Mood",          selected: 5 },
        ].map((r, ri) => (
          <div key={ri} style={{ display: "grid", gridTemplateColumns: "160px 1fr", gap: 16, alignItems: "center" }}>
            <div>
              <div style={{ fontSize: 14, fontWeight: 500 }}>{r.label}</div>
              {r.hint && <div className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--fg-4)", marginTop: 2 }}>{r.hint}</div>}
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              {[1,2,3,4,5].map(n => (
                <div key={n} style={{
                  flex: 1, padding: "16px 0", textAlign: "center",
                  border: "1px solid " + (n === r.selected ? "var(--accent)" : "var(--hairline)"),
                  background: n === r.selected ? "color-mix(in oklab, var(--accent) 14%, transparent)" : "transparent",
                  color: n === r.selected ? "var(--fg)" : "var(--fg-3)",
                  fontFamily: "var(--mono)", fontSize: 13, fontWeight: 600, borderRadius: 4,
                }}>{n}</div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>

    {/* Notes */}
    <div style={{ marginTop: 24 }}>
      <Eyebrow>Notes \u00b7 optional</Eyebrow>
      <div className="card-flush" style={{ marginTop: 10, padding: "14px 16px", fontSize: 14, minHeight: 60, color: "var(--fg-3)" }}>
        Anything worth noting \u2014 illness, travel, big workout yesterday\u2026
      </div>
    </div>
  </>
);

// — Conditions form ——————————————————————————————————————
const LogConditionsForm = () => (
  <>
    <div className="card-flush" style={{ padding: 0 }}>
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr" }}>
        <div style={{ padding: "18px 20px", borderRight: "1px solid var(--hairline)" }}>
          <div className="eyebrow" style={{ fontSize: 9 }}>Link to cardio session · optional</div>
          <div style={{ fontSize: 14, fontWeight: 600, marginTop: 6, color: "var(--accent)" }}>May 27 · Threshold intervals</div>
          <div className="mono" style={{ fontSize: 10, color: "var(--fg-4)", marginTop: 4, letterSpacing: "0.12em", textTransform: "uppercase" }}>AUTO-FILLS DATE · ACTIVITY</div>
        </div>
        <div style={{ padding: "18px 20px", borderRight: "1px solid var(--hairline)" }}>
          <div className="eyebrow" style={{ fontSize: 9 }}>Date</div>
          <div className="num" style={{ fontSize: 16, fontWeight: 600, marginTop: 6 }}>May 27, 2026</div>
        </div>
        <div style={{ padding: "18px 20px", borderRight: "1px solid var(--hairline)" }}>
          <div className="eyebrow" style={{ fontSize: 9 }}>Activity</div>
          <div style={{ fontSize: 16, fontWeight: 600, marginTop: 6 }}>Run</div>
        </div>
        <div style={{ padding: "18px 20px" }}>
          <div className="eyebrow" style={{ fontSize: 9 }}>Setting</div>
          <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
            <Pill tone="accent">OUTDOOR</Pill>
            <Pill>INDOOR</Pill>
          </div>
        </div>
      </div>
    </div>

    <div style={{ marginTop: 24 }}>
      <Eyebrow>Weather</Eyebrow>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 10, marginTop: 12 }}>
        {[
          ["Temp",       "64",  "°F"],
          ["Feels like", "63",  "°F"],
          ["Wind",       "6",   "mph"],
          ["Wind dir",   "NW",  ""],
          ["Humidity",   "58",  "%"],
        ].map(([k, v, u], i) => (
          <div key={i} className="card" style={{ padding: 14 }}>
            <div className="eyebrow" style={{ fontSize: 9 }}>{k}</div>
            <div className="num" style={{ fontSize: 22, fontWeight: 700, marginTop: 6 }}>{v}<span style={{ fontSize: 11, color: "var(--fg-3)", fontWeight: 400, marginLeft: 2 }}>{u}</span></div>
          </div>
        ))}
      </div>
      <div style={{ marginTop: 14 }}>
        <Eyebrow>Conditions</Eyebrow>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 10 }}>
          {["Partly cloudy", "Clear", "Overcast", "Light rain", "Heavy rain", "Snow", "Sleet", "Fog"].map((c, i) => (
            <div key={i} style={{
              padding: "7px 12px", borderRadius: 4,
              border: "1px solid " + (i === 0 ? "var(--accent)" : "var(--hairline)"),
              background: i === 0 ? "color-mix(in oklab, var(--accent) 10%, transparent)" : "transparent",
              fontSize: 12, color: i === 0 ? "var(--fg)" : "var(--fg-2)",
            }}>{c}</div>
          ))}
        </div>
      </div>
    </div>

    <div style={{ marginTop: 28 }}>
      <Eyebrow>What you wore</Eyebrow>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, marginTop: 12 }}>
        {[
          ["Upper base",  "Tech tee"],
          ["Upper mid",   "—"],
          ["Shell",       "—"],
          ["Lower",       "Split shorts"],
          ["Headwear",    "Visor"],
          ["Gloves",      "—"],
          ["Footwear",    "Endorphins Pro 4"],
          ["Socks",       "Crew"],
        ].map(([k, v], i) => (
          <div key={i} style={{ padding: "12px 14px", border: "1px solid var(--hairline-2)", borderRadius: 4 }}>
            <div className="eyebrow" style={{ fontSize: 9 }}>{k}</div>
            <div style={{ fontSize: 13, fontWeight: 500, marginTop: 4, color: v === "—" ? "var(--fg-4)" : "var(--fg)" }}>{v}</div>
          </div>
        ))}
      </div>
    </div>

    <div style={{ marginTop: 24 }}>
      <Eyebrow>Comfort · 1–5</Eyebrow>
      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        {[["1","Very cold"],["2","Cold"],["3","Comfortable"],["4","Warm"],["5","Very hot"]].map(([n, l], i) => (
          <div key={i} style={{
            flex: 1, padding: "14px 0", textAlign: "center", borderRadius: 4,
            border: "1px solid " + (i === 2 ? "var(--accent)" : "var(--hairline)"),
            background: i === 2 ? "color-mix(in oklab, var(--accent) 14%, transparent)" : "transparent",
            color: i === 2 ? "var(--fg)" : "var(--fg-3)",
          }}>
            <div className="num mono" style={{ fontSize: 18, fontWeight: 700 }}>{n}</div>
            <div className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", marginTop: 4, textTransform: "uppercase" }}>{l}</div>
          </div>
        ))}
      </div>
      <div className="card-flush" style={{ marginTop: 12, padding: "12px 14px", fontSize: 13, color: "var(--fg-3)" }}>
        Comfort notes — toes cold the first 10 minutes, then fine…
      </div>
    </div>
  </>
);

// — Injury form ————————————————————————————————————————————
const LogInjuryForm = () => (
  <>
    <div className="card-flush" style={{ padding: 0 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr" }}>
        {[
          ["Start date", "May 26, 2026"],
          ["Status",     "Active"],
          ["Resolved",   "—"],
          ["Days open",  "1"],
        ].map(([k, v], i) => (
          <div key={i} style={{ padding: "18px 20px", borderRight: i < 3 ? "1px solid var(--hairline)" : "none" }}>
            <div className="eyebrow" style={{ fontSize: 9 }}>{k}</div>
            <div className="num" style={{ fontSize: 17, fontWeight: 600, marginTop: 6 }}>{v}</div>
          </div>
        ))}
      </div>
    </div>

    <div style={{ marginTop: 24 }}>
      <Eyebrow>Body part</Eyebrow>
      <div style={{ marginTop: 12, display: "grid", gridTemplateColumns: "260px 1fr", gap: 18 }}>
        <div className="card" style={{ padding: 18, display: "grid", placeItems: "center" }}>
          <svg viewBox="0 0 120 220" style={{ width: 180, height: 200 }}>
            <circle cx="60" cy="18" r="14" fill="var(--bg-3)" stroke="var(--hairline)" strokeWidth="1" />
            <path d="M40 36 L80 36 L82 90 L78 130 L42 130 L38 90 Z" fill="var(--bg-3)" stroke="var(--hairline)" strokeWidth="1" />
            <path d="M40 38 L24 90 L26 130 L34 130 L38 92 Z" fill="var(--bg-3)" stroke="var(--hairline)" strokeWidth="1" />
            <path d="M80 38 L96 90 L94 130 L86 130 L82 92 Z" fill="var(--bg-3)" stroke="var(--hairline)" strokeWidth="1" />
            <path d="M42 130 L40 200 L52 200 L56 130 Z" fill="var(--bg-3)" stroke="var(--hairline)" strokeWidth="1" />
            <path d="M78 130 L80 200 L68 200 L64 130 Z" fill="var(--bg-3)" stroke="var(--hairline)" strokeWidth="1" />
            <ellipse cx="48" cy="160" rx="8" ry="14" fill="var(--accent)" opacity="0.85" />
            <text x="60" y="218" fontFamily="var(--mono)" fontSize="7" letterSpacing="1" textAnchor="middle" fill="var(--fg-3)">SELECTED: LEFT HAMSTRING</text>
          </svg>
        </div>
        <div>
          <div className="eyebrow" style={{ fontSize: 9 }}>Selected body part</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
            {["Left hamstring", "Right hamstring", "Left calf", "Right calf", "Left knee", "Right knee", "Left ankle", "Right ankle", "Lower back", "Hip flexor", "IT band", "Achilles", "Plantar fascia", "Shoulder", "Wrist"].map((b, i) => (
              <div key={i} style={{
                padding: "7px 12px", borderRadius: 4,
                border: "1px solid " + (i === 0 ? "var(--accent)" : "var(--hairline)"),
                background: i === 0 ? "color-mix(in oklab, var(--accent) 10%, transparent)" : "transparent",
                fontSize: 12, color: i === 0 ? "var(--fg)" : "var(--fg-2)",
              }}>{b}</div>
            ))}
          </div>

          <div style={{ marginTop: 20 }}>
            <Eyebrow>Injury type</Eyebrow>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
              {["Strain", "Sprain", "Tendinopathy", "Stress fracture", "Contusion", "Overuse", "Other"].map((t, i) => (
                <Pill key={i} tone={i === 0 ? "accent" : "solid"}>{t.toUpperCase()}</Pill>
              ))}
            </div>
          </div>

          <div style={{ marginTop: 20 }}>
            <Eyebrow>Severity stage</Eyebrow>
            <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
              {[["1", "Twinge"], ["2", "Manageable", true], ["3", "Modify"], ["4", "Significant"], ["5", "Acute"]].map(([n, l, a], i) => (
                <div key={i} style={{
                  flex: 1, padding: "12px 8px", textAlign: "center", borderRadius: 4,
                  border: "1px solid " + (a ? "var(--accent)" : "var(--hairline)"),
                  background: a ? "color-mix(in oklab, var(--accent) 14%, transparent)" : "transparent",
                }}>
                  <div className="num" style={{ fontSize: 18, fontWeight: 700 }}>{n}</div>
                  <div className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", marginTop: 2, color: "var(--fg-3)", textTransform: "uppercase" }}>{l}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>

    <div style={{ marginTop: 24 }}>
      <Eyebrow>Movement constraints</Eyebrow>
      <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 4 }}>We'll auto-modify exercises around these constraints in your plan.</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8, marginTop: 12 }}>
        {[
          ["No hip extension under load", true],
          ["No deep knee flexion", false],
          ["No max-effort sprinting", true],
          ["No plyometrics", true],
          ["No deadlift pattern", false],
          ["No single-leg max effort", true],
        ].map(([l, on], i) => (
          <div key={i} style={{ display: "flex", gap: 10, padding: "10px 12px", border: "1px solid var(--hairline-2)", borderRadius: 4, alignItems: "center" }}>
            <div style={{ width: 16, height: 16, borderRadius: 3, border: "1px solid " + (on ? "var(--accent)" : "var(--hairline)"), background: on ? "var(--accent)" : "transparent", color: "var(--ink)", display: "grid", placeItems: "center" }}>
              {on && <Ic d={I.check} size={11} sw={2.5} />}
            </div>
            <span style={{ fontSize: 12, fontWeight: 500 }}>{l}</span>
          </div>
        ))}
      </div>
    </div>

    <div style={{ marginTop: 24, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
      <div>
        <Eyebrow>Description</Eyebrow>
        <div className="card-flush" style={{ marginTop: 10, padding: "12px 14px", minHeight: 80, fontSize: 13, color: "var(--fg-2)" }}>
          Felt a twinge during mile 8 of yesterday's long run — deep cramping rather than sharp pain. Loosened with walking. Tight this morning but no swelling.
        </div>
      </div>
      <div>
        <Eyebrow>Modifications needed</Eyebrow>
        <div className="card-flush" style={{ marginTop: 10, padding: "12px 14px", minHeight: 80, fontSize: 13, color: "var(--fg-2)" }}>
          Skip threshold intervals for 5–7 days. Replace with Z2 only, max 60 min. No hip thrust or RDL. Light stretching + foam roll.
        </div>
      </div>
    </div>
  </>
);

// — The Log screen ——————————————————————————————————————————
const ScreenLog = ({ type = "cardio" }) => {
  const active = LOG_TYPES.find(t => t.key === type) || LOG_TYPES[0];
  const FormCmp = {
    cardio:     LogCardioForm,
    strength:   LogStrengthForm,
    body:       LogBodyForm,
    wellness:   LogWellnessForm,
    conditions: LogConditionsForm,
    injury:     LogInjuryForm,
  }[type] || LogCardioForm;

  return (
    <div className="screen">
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <Sidebar active="log" />
        <div className="page">
          <TopBar crumbs={["Log", active.label]} actions={
            <>
              <div className="btn btn-ghost">Cancel</div>
              <div className="btn btn-primary"><Ic d={I.check} size={12} sw={2.2} />Save {active.label.toLowerCase()}</div>
            </>
          } />
          <div className="page-body">
            <div style={{ marginBottom: 22 }}>
              <Eyebrow>Quick log</Eyebrow>
              <h1 className="page-title" style={{ marginTop: 8 }}>What did you do today?</h1>
              <div className="page-sub">Pick a type \u2014 the form adapts. Sessions auto-match to scheduled plan items.</div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "260px 1fr", gap: 28 }}>
              <LogTypePicker active={type} />
              <div>
                <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 14 }}>
                  <Eyebrow accent>\u25cf {active.label.toUpperCase()}</Eyebrow>
                  <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.18em" }}>\u00b7 {active.sub.toUpperCase()}</span>
                </div>
                <FormCmp />
                <div style={{ height: 40 }} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════
// 5. ONBOARDING — 7-step flow with 6 step screens (skip step 1, signup)
// ═══════════════════════════════════════════════════════════════════
const ONB_STEPS = [
  ["1", "Account"],
  ["2", "Connect"],
  ["3", "Prefill"],
  ["4", "Schedule"],
  ["5", "Skills"],
  ["6", "Locations"],
  ["7", "Race"],
];

const OnbShell = ({ step, children }) => (
  <div className="screen">
    <div style={{ height: 60, padding: "0 32px", display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: "1px solid var(--hairline-2)", flexShrink: 0 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <AsMark size={24} />
        <Wordmark />
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        {ONB_STEPS.map(([n, l], i) => {
          const done = parseInt(n) < step;
          const current = parseInt(n) === step;
          return (
            <div key={n} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <div style={{
                width: 20, height: 20, borderRadius: "50%",
                background: current ? "var(--accent)" : done ? "var(--ink-3)" : "transparent",
                border: "1px solid " + (current ? "var(--accent)" : done ? "var(--hairline)" : "var(--hairline)"),
                display: "grid", placeItems: "center",
                fontFamily: "var(--mono)", fontSize: 9, fontWeight: 600,
                color: current ? "var(--ink)" : done ? "var(--fg)" : "var(--fg-3)",
              }}>{done ? "\u2713" : n}</div>
              <span className="mono" style={{ fontSize: 9, letterSpacing: "0.18em", textTransform: "uppercase", color: current ? "var(--fg)" : "var(--fg-3)" }}>{l}</span>
            </div>
          );
        })}
      </div>
      <div className="mono" style={{ fontSize: 10, letterSpacing: "0.18em", color: "var(--fg-3)" }}>SKIP \u2192</div>
    </div>
    {children}
  </div>
);

const OnbFooter = ({ step, backLabel, nextLabel }) => (
  <div style={{ marginTop: 40, paddingTop: 22, borderTop: "1px solid var(--hairline-2)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
    <div className="btn btn-text" style={{ color: "var(--fg-3)" }}><Ic d={I.chevL} size={12} /> {backLabel}</div>
    <div className="mono" style={{ fontSize: 10, letterSpacing: "0.18em", color: "var(--fg-3)" }}>STEP 0{step} OF 07</div>
    <div className="btn btn-primary">{nextLabel} <Ic d={I.arrow} size={12} sw={2} /></div>
  </div>
);

// — Step 2: Connect providers ————————————————————————————————
const OnbConnect = () => (
  <OnbShell step={2}>
    <div style={{ flex: 1, overflow: "auto", padding: "40px 32px 48px" }}>
      <div style={{ maxWidth: 1000, margin: "0 auto" }}>
        <Eyebrow accent>\u25cf STEP 02 \u00b7 CONNECT YOUR PROVIDERS</Eyebrow>
        <h1 style={{ fontSize: 44, fontWeight: 800, letterSpacing: "-0.025em", lineHeight: 1.05, margin: "12px 0 12px", maxWidth: 700 }}>
          Bring in what you <span style={{ color: "var(--accent)" }}>already track.</span>
        </h1>
        <div style={{ fontSize: 16, color: "var(--fg-3)", maxWidth: 600, lineHeight: 1.5 }}>
          AIDSTATION pulls activity, sleep, and heart-rate data so your training plan reacts to what you actually do \u2014 not what you remember to log.
        </div>

        {/* Consent disclosure */}
        <div className="card" style={{ marginTop: 24, padding: 18 }}>
          <Eyebrow>What you're consenting to</Eyebrow>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 18, marginTop: 14 }}>
            {[
              ["Activity",  "Workouts, durations, distance, heart rate, pace, power, elevation."],
              ["Wellness",  "Body weight, resting heart rate, recovery scores."],
              ["Sleep",     "Nightly duration and sleep-quality summaries."],
              ["Profile",   "Name + provider user ID, used to map webhooks to you."],
            ].map(([k, v], i) => (
              <div key={i}>
                <div className="mono accent" style={{ fontSize: 10, letterSpacing: "0.18em", color: "var(--accent)" }}>\u25cf {k.toUpperCase()}</div>
                <div style={{ fontSize: 12, color: "var(--fg-2)", marginTop: 6, lineHeight: 1.45 }}>{v}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Provider list */}
        <div style={{ marginTop: 28 }}>
          <Eyebrow>Available providers</Eyebrow>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 12, marginTop: 12 }}>
            {[
              { name: "Strava",        status: "connected",    since: "May 12, 2026",  color: "#FC4C02" },
              { name: "Wahoo",         status: "connected",    since: "May 18, 2026",  color: "#0093D0" },
              { name: "Whoop",         status: "available",    scopes: "Workouts \u00b7 sleep \u00b7 recovery", color: "#000000" },
              { name: "TrainingPeaks", status: "available",    scopes: "Workouts \u00b7 planned sessions",     color: "#E32B17" },
              { name: "Zwift",         status: "available",    scopes: "Indoor activities",                    color: "#FC6719" },
              { name: "Ride With GPS", status: "available",    scopes: "Route-based activities",               color: "#E94B4F" },
              { name: "Garmin",        status: "paused",       reason: "Garmin API access closed",             color: "#000000" },
            ].map((p, i) => {
              const isConnected = p.status === "connected";
              const isPaused = p.status === "paused";
              return (
                <div key={i} className="card" style={{ padding: 16, display: "flex", gap: 14, alignItems: "center", opacity: isPaused ? 0.55 : 1 }}>
                  <div style={{ width: 40, height: 40, borderRadius: 4, background: p.color, display: "grid", placeItems: "center", flexShrink: 0, color: "white", fontFamily: "var(--mono)", fontWeight: 700, fontSize: 14 }}>
                    {p.name[0]}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontWeight: 600, fontSize: 14 }}>{p.name}</span>
                      {isConnected && <Pill tone="good">\u2713 CONNECTED</Pill>}
                      {isPaused && <Pill tone="warn">PAUSED</Pill>}
                    </div>
                    <div className="mono" style={{ fontSize: 10, letterSpacing: "0.14em", color: "var(--fg-3)", marginTop: 4, textTransform: "uppercase" }}>
                      {isConnected ? `SINCE ${p.since}` : isPaused ? p.reason : p.scopes}
                    </div>
                  </div>
                  {isConnected ? (
                    <div className="btn btn-ghost btn-sm">RE-AUTH</div>
                  ) : isPaused ? (
                    <div className="btn btn-ghost btn-sm" style={{ opacity: 0.5 }}>UNAVAILABLE</div>
                  ) : (
                    <div className="btn btn-primary btn-sm">CONNECT \u2192</div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        <OnbFooter step={2} backLabel="Back \u00b7 Account" nextLabel="Continue \u00b7 2 connected" />
      </div>
    </div>
  </OnbShell>
);

// — Step 3: Prefill review ————————————————————————————————————
const OnbPrefill = () => (
  <OnbShell step={3}>
    <div style={{ flex: 1, overflow: "auto", padding: "40px 32px 48px" }}>
      <div style={{ maxWidth: 1000, margin: "0 auto" }}>
        <Eyebrow accent>\u25cf STEP 03 \u00b7 REVIEW YOUR DATA</Eyebrow>
        <h1 style={{ fontSize: 44, fontWeight: 800, letterSpacing: "-0.025em", lineHeight: 1.05, margin: "12px 0 12px", maxWidth: 700 }}>
          We pulled <span style={{ color: "var(--accent)" }}>4 of 5</span> baselines.
        </h1>
        <div style={{ fontSize: 16, color: "var(--fg-3)", maxWidth: 600, lineHeight: 1.5 }}>
          Pick the value to use for each performance baseline. We'll keep prefilling from your providers automatically as new data arrives.
        </div>

        <div style={{ marginTop: 28, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          {[
            { label: "Resting heart rate", unit: "bpm",
              current: { value: "48",  source: "From Strava", days: "2 days ago" },
              suggested: { provider: "Wahoo", value: "47", days: "today" },
              hasSuggestion: true,
            },
            { label: "VO2 max", unit: "ml/kg/min",
              current: { value: "62",  source: "Self-reported" },
              suggested: { provider: "Strava", value: "63", days: "May 18" },
              hasSuggestion: true,
            },
            { label: "Body weight", unit: "lb",
              current: { value: "162", source: "Manually set" },
              suggested: { provider: "Wahoo", value: "162.4", days: "today" },
              hasSuggestion: true,
              isManual: true,
            },
            { label: "Threshold pace", unit: "/mi",
              current: { value: "6:42", source: "Test on May 4" },
              suggested: { provider: "Strava", value: "6:38", days: "May 22" },
              hasSuggestion: true,
            },
            { label: "FTP", unit: "watts",
              current: { value: null },
              hasSuggestion: false,
            },
          ].map((f, i) => (
            <div key={i} className="card" style={{ padding: 18 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 15 }}>{f.label}</div>
                  <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em", textTransform: "uppercase", marginTop: 2 }}>{f.unit}</div>
                </div>
                {!f.hasSuggestion && <Pill>NO DATA YET</Pill>}
              </div>
              <div style={{ display: "grid", gridTemplateColumns: f.hasSuggestion ? "1fr 1fr" : "1fr", gap: 0, borderTop: "1px solid var(--hairline-2)", paddingTop: 12 }}>
                <div style={{ paddingRight: f.hasSuggestion ? 12 : 0, borderRight: f.hasSuggestion ? "1px solid var(--hairline-2)" : "none" }}>
                  <div className="eyebrow" style={{ fontSize: 9 }}>Current</div>
                  {f.current.value ? (
                    <>
                      <div className="num" style={{ fontSize: 22, fontWeight: 700, marginTop: 4 }}>{f.current.value}</div>
                      <div className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--fg-3)", marginTop: 4, textTransform: "uppercase" }}>{f.current.source}{f.current.days ? ` \u00b7 ${f.current.days}` : ""}</div>
                    </>
                  ) : (
                    <div style={{ fontSize: 12, color: "var(--fg-3)", fontStyle: "italic", marginTop: 8 }}>Not set</div>
                  )}
                </div>
                {f.hasSuggestion && (
                  <div style={{ paddingLeft: 12 }}>
                    <div className="eyebrow accent" style={{ fontSize: 9 }}>{f.suggested.provider} suggests</div>
                    <div className="num" style={{ fontSize: 22, fontWeight: 700, marginTop: 4, color: "var(--accent)" }}>{f.suggested.value}</div>
                    <div className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--fg-3)", marginTop: 4, textTransform: "uppercase" }}>As of {f.suggested.days}</div>
                  </div>
                )}
              </div>
              {f.hasSuggestion && (
                <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
                  <div className="btn btn-primary btn-sm" style={{ flex: 1, justifyContent: "center" }}>USE {f.suggested.provider.toUpperCase()}</div>
                  {f.current.value && <div className="btn btn-ghost btn-sm" style={{ flex: 1, justifyContent: "center" }}>KEEP CURRENT</div>}
                </div>
              )}
              {!f.hasSuggestion && (
                <div className="btn btn-ghost btn-sm" style={{ marginTop: 12, width: "100%", justifyContent: "center" }}>ENTER MANUALLY</div>
              )}
            </div>
          ))}
        </div>

        <OnbFooter step={3} backLabel="Back \u00b7 Connect" nextLabel="Continue \u00b7 Schedule" />
      </div>
    </div>
  </OnbShell>
);

// — Step 4: Schedule ————————————————————————————————————————
const OnbSchedule = () => {
  const days = [
    { d: "Monday",    enabled: true,  start: "06:00", dur: 60,  hasSecond: false },
    { d: "Tuesday",   enabled: true,  start: "06:00", dur: 75,  hasSecond: false, key: true },
    { d: "Wednesday", enabled: true,  start: "06:00", dur: 55,  hasSecond: false },
    { d: "Thursday",  enabled: true,  start: "06:00", dur: 60,  hasSecond: true, start2: "17:30", dur2: 30 },
    { d: "Friday",    enabled: true,  start: "06:00", dur: 55,  hasSecond: false },
    { d: "Saturday",  enabled: true,  start: "07:00", dur: 150, hasSecond: false, key: true },
    { d: "Sunday",    enabled: false },
  ];
  const total = days.reduce((s, d) => s + (d.enabled ? d.dur + (d.hasSecond ? d.dur2 : 0) : 0), 0);
  return (
    <OnbShell step={4}>
      <div style={{ flex: 1, overflow: "auto", padding: "40px 32px 48px" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto" }}>
          <Eyebrow accent>\u25cf STEP 04 \u00b7 SCHEDULE & AVAILABILITY</Eyebrow>
          <h1 style={{ fontSize: 44, fontWeight: 800, letterSpacing: "-0.025em", lineHeight: 1.05, margin: "12px 0 12px", maxWidth: 700 }}>
            When can you <span style={{ color: "var(--accent)" }}>actually train?</span>
          </h1>
          <div style={{ fontSize: 16, color: "var(--fg-3)", maxWidth: 620, lineHeight: 1.5 }}>
            Start time is the earliest you can begin (not fixed). Duration is the window length. Unchecked days are rest days; longest enabled window becomes your weekly long session.
          </div>

          {/* Doubles question */}
          <div className="card" style={{ marginTop: 28, padding: 18 }}>
            <Eyebrow>Doubles feasible?</Eyebrow>
            <div style={{ fontSize: 13, color: "var(--fg-3)", marginTop: 6 }}>Are second sessions on the same day realistic?</div>
            <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
              {[["No", false], ["Occasionally", true], ["Regularly", false]].map(([l, active], i) => (
                <div key={i} style={{
                  padding: "10px 18px", borderRadius: 4,
                  border: "1px solid " + (active ? "var(--accent)" : "var(--hairline)"),
                  background: active ? "color-mix(in oklab, var(--accent) 10%, transparent)" : "transparent",
                  fontWeight: 500, fontSize: 13,
                  color: active ? "var(--fg)" : "var(--fg-2)",
                }}>{l}</div>
              ))}
            </div>
          </div>

          {/* Schedule grid */}
          <div className="card" style={{ marginTop: 18, padding: 0, overflow: "hidden" }}>
            <div style={{ display: "grid", gridTemplateColumns: "150px 1fr 1fr 1fr 1fr", padding: "12px 0", borderBottom: "1px solid var(--hairline-2)", background: "var(--bg)" }}>
              {["Day","Earliest start","Duration","Second start","Second duration"].map((h,i)=>(
                <div key={i} className="mono" style={{ padding: "0 18px", fontSize: 9, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--fg-3)", fontWeight: 500 }}>{h}</div>
              ))}
            </div>
            {days.map((day, i) => (
              <div key={i} style={{
                display: "grid", gridTemplateColumns: "150px 1fr 1fr 1fr 1fr", alignItems: "center", padding: "14px 0",
                borderBottom: i < days.length - 1 ? "1px solid var(--hairline-2)" : "none",
                opacity: day.enabled ? 1 : 0.4,
              }}>
                <div style={{ padding: "0 18px", display: "flex", alignItems: "center", gap: 10 }}>
                  <div style={{ width: 16, height: 16, border: "1px solid " + (day.enabled ? "var(--accent)" : "var(--hairline)"), background: day.enabled ? "var(--accent)" : "transparent", color: "var(--ink)", borderRadius: 2, display: "grid", placeItems: "center" }}>
                    {day.enabled && <Ic d={I.check} size={11} sw={2.5} />}
                  </div>
                  <span style={{ fontWeight: 500, fontSize: 14 }}>{day.d}</span>
                  {day.key && <Pill tone="accent">KEY</Pill>}
                </div>
                <div style={{ padding: "0 18px" }} className="num">{day.enabled ? day.start : "\u2014"}</div>
                <div style={{ padding: "0 18px" }} className="num">{day.enabled ? `${day.dur} min` : "\u2014"}</div>
                <div style={{ padding: "0 18px" }} className="num">{day.hasSecond ? day.start2 : "\u2014"}</div>
                <div style={{ padding: "0 18px" }} className="num">{day.hasSecond ? `${day.dur2} min` : "\u2014"}</div>
              </div>
            ))}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "14px 18px", borderTop: "1px solid var(--hairline)", background: "var(--bg-2)" }}>
              <Eyebrow>Weekly total \u00b7 derived</Eyebrow>
              <div className="num" style={{ fontSize: 22, fontWeight: 700 }}>{(total / 60).toFixed(1)} <span style={{ fontSize: 12, color: "var(--fg-3)", fontWeight: 400 }}>h / week</span></div>
            </div>
          </div>

          <OnbFooter step={4} backLabel="Back \u00b7 Prefill" nextLabel="Continue \u00b7 Skills" />
        </div>
      </div>
    </OnbShell>
  );
};

// — Step 5: Skills ——————————————————————————————————————————
const OnbSkills = () => {
  const skills = [
    { name: "Swim freestyle (front crawl)", desc: "I can swim 200m+ continuous freestyle without stopping.", checked: true },
    { name: "Open-water swimming",          desc: "Comfortable in open water with wetsuit, sighting, navigating a course.", checked: false },
    { name: "Road cycling (drop bars)",     desc: "I can ride 2+ hours on a road bike in a paceline or solo.", checked: true },
    { name: "Mountain biking",              desc: "Technical singletrack, descending, drops, technical climbs.", checked: false },
    { name: "Power meter (bike)",           desc: "I train and race with a calibrated bike power meter.", checked: true },
    { name: "Running power (Stryd / watch)", desc: "I have access to running power data.", checked: false },
    { name: "Trail running (technical)",    desc: "Comfortable on rocky, rooted, exposed singletrack.", checked: true },
    { name: "Strength training (free weights)", desc: "Squat, deadlift, bench, OHP with free weights in good form.", checked: true },
    { name: "Yoga / mobility",              desc: "Regular mobility practice (Pilates, yoga, dedicated mobility).", checked: false },
    { name: "Climbing (5.10+ outdoor)",     desc: "Outdoor sport/trad/boulder at a moderate grade or above.", checked: false },
    { name: "Paddling (kayak / SUP)",       desc: "Flatwater or whitewater paddle craft.", checked: false },
    { name: "Skiing (skinning / touring)",  desc: "Backcountry skinning, AT setup, ski mountaineering basics.", checked: false },
  ];
  return (
    <OnbShell step={5}>
      <div style={{ flex: 1, overflow: "auto", padding: "40px 32px 48px" }}>
        <div style={{ maxWidth: 1000, margin: "0 auto" }}>
          <Eyebrow accent>\u25cf STEP 05 \u00b7 SKILLS & CAPABILITIES</Eyebrow>
          <h1 style={{ fontSize: 44, fontWeight: 800, letterSpacing: "-0.025em", lineHeight: 1.05, margin: "12px 0 12px", maxWidth: 720 }}>
            What can you <span style={{ color: "var(--accent)" }}>already do?</span>
          </h1>
          <div style={{ fontSize: 16, color: "var(--fg-3)", maxWidth: 600, lineHeight: 1.5 }}>
            Check what's true today \u2014 we use this to filter which kinds of sessions show up in your plan. Everything is editable later.
          </div>

          <div style={{ marginTop: 28, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            {skills.map((s, i) => (
              <div key={i} className="card" style={{
                padding: "14px 16px", display: "flex", gap: 12, alignItems: "flex-start",
                background: s.checked ? "color-mix(in oklab, var(--accent) 6%, transparent)" : "var(--bg-2)",
                borderColor: s.checked ? "color-mix(in oklab, var(--accent) 30%, var(--hairline-2))" : "var(--hairline-2)",
              }}>
                <div style={{
                  width: 18, height: 18, borderRadius: 3, marginTop: 2, flexShrink: 0,
                  border: "1px solid " + (s.checked ? "var(--accent)" : "var(--hairline)"),
                  background: s.checked ? "var(--accent)" : "transparent",
                  color: "var(--ink)", display: "grid", placeItems: "center",
                }}>{s.checked && <Ic d={I.check} size={12} sw={2.5} />}</div>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>{s.name}</div>
                  <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 3, lineHeight: 1.4 }}>{s.desc}</div>
                </div>
              </div>
            ))}
          </div>

          <div style={{ marginTop: 18, fontSize: 12, color: "var(--fg-3)" }}>
            <span className="mono" style={{ letterSpacing: "0.18em" }}>5 OF 12 CHECKED</span>
          </div>

          <OnbFooter step={5} backLabel="Back \u00b7 Schedule" nextLabel="Continue \u00b7 Locations" />
        </div>
      </div>
    </OnbShell>
  );
};

// — Step 6: Locations ——————————————————————————————————————
const OnbLocations = () => (
  <OnbShell step={6}>
    <div style={{ flex: 1, overflow: "auto", padding: "40px 32px 48px" }}>
      <div style={{ maxWidth: 1000, margin: "0 auto" }}>
        <Eyebrow accent>\u25cf STEP 06 \u00b7 YOUR LOCATIONS</Eyebrow>
        <h1 style={{ fontSize: 44, fontWeight: 800, letterSpacing: "-0.025em", lineHeight: 1.05, margin: "12px 0 12px", maxWidth: 720 }}>
          Where do you <span style={{ color: "var(--accent)" }}>train?</span>
        </h1>
        <div style={{ fontSize: 16, color: "var(--fg-3)", maxWidth: 620, lineHeight: 1.5 }}>
          Each location has its own equipment profile. We use this to filter which exercises show up when you log strength at that place \u2014 no point seeing barbell squats if the location is a hotel gym.
        </div>

        {/* Add via search */}
        <div className="card" style={{ marginTop: 28, padding: 16, display: "flex", alignItems: "center", gap: 12 }}>
          <Ic d={I.search} size={16} />
          <span style={{ flex: 1, color: "var(--fg-3)" }}>Search "Equinox", "Planet Fitness", a park, or any address\u2026</span>
          <div className="btn btn-primary btn-sm"><Ic d={I.plus} size={11} sw={2} /> ADD MANUAL</div>
        </div>

        {/* Saved locations */}
        <div style={{ marginTop: 20 }}>
          <Eyebrow>3 saved \u00b7 active</Eyebrow>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 12 }}>
            {[
              {
                name: "Home garage", category: "manual",
                addr: "Washington, DC", items: 18, updated: "May 14, 2026", primary: true,
                tags: ["Barbell", "Squat rack", "Bench", "Pull-up bar", "Kettlebells", "DBs to 50lb", "Plates to 405lb", "Foam roller"],
              },
              {
                name: "Equinox Capitol Hill", chain: "Equinox",
                addr: "320 Pennsylvania Ave SE, Washington DC", items: 42, updated: "Apr 22, 2026",
                tags: ["Olympic platform", "Power racks", "DBs to 150lb", "Cable stack", "Concept2 row", "Watt bike", "Sauna"],
              },
              {
                name: "Rock Creek loop", category: "outdoor route",
                addr: "Beach Dr NW, Washington DC", items: 0, updated: "May 02, 2026", route: true,
                tags: ["4.2 mi loop", "Rolling", "Aid water at MP2"],
              },
            ].map((loc, i) => (
              <div key={i} className="card" style={{ padding: 18 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontWeight: 600, fontSize: 16 }}>{loc.name}</span>
                      {loc.primary && <Pill tone="accent">PRIMARY</Pill>}
                      {loc.chain && <Pill tone="solid">{loc.chain.toUpperCase()}</Pill>}
                      {loc.route && <Pill tone="solid">ROUTE</Pill>}
                    </div>
                    <div className="mono" style={{ fontSize: 10, letterSpacing: "0.14em", color: "var(--fg-3)", marginTop: 6, textTransform: "uppercase" }}>
                      \u25b3 {loc.addr}
                    </div>
                  </div>
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 14 }}>
                  {loc.tags.slice(0, 6).map((t, j) => (
                    <Pill key={j} tone="solid">{t}</Pill>
                  ))}
                  {loc.tags.length > 6 && (
                    <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)", padding: "4px 6px" }}>+{loc.tags.length - 6} more</span>
                  )}
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginTop: 14, paddingTop: 12, borderTop: "1px solid var(--hairline-2)" }}>
                  <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.16em" }}>{loc.items} ITEMS \u00b7 UPDATED {loc.updated}</span>
                  <div style={{ display: "flex", gap: 6 }}>
                    <div className="btn btn-ghost btn-sm">EDIT</div>
                  </div>
                </div>
              </div>
            ))}

            <div className="card" style={{ padding: 18, border: "1px dashed var(--hairline)", background: "transparent", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center", color: "var(--fg-3)" }}>
              <Ic d={I.plus} size={20} />
              <div style={{ fontWeight: 500, fontSize: 14, marginTop: 8 }}>Add another location</div>
              <div className="mono" style={{ fontSize: 10, letterSpacing: "0.14em", marginTop: 4 }}>HOME \u00b7 GYM \u00b7 ROUTE \u00b7 TRAVEL</div>
            </div>
          </div>
        </div>

        <OnbFooter step={6} backLabel="Back \u00b7 Skills" nextLabel="Continue \u00b7 Target race" />
      </div>
    </div>
  </OnbShell>
);

// — Step 7: Target race (rich, matches real template) ——————————
const OnbRace = () => (
  <OnbShell step={7}>
    <div style={{ flex: 1, overflow: "auto", padding: "40px 32px 48px" }}>
      <div style={{ maxWidth: 1100, margin: "0 auto" }}>
        <Eyebrow accent>\u25cf STEP 07 \u00b7 TARGET RACE</Eyebrow>
        <h1 style={{ fontSize: 44, fontWeight: 800, letterSpacing: "-0.025em", lineHeight: 1.05, margin: "12px 0 12px", maxWidth: 720 }}>
          What are you training <span style={{ color: "var(--accent)" }}>for?</span>
        </h1>
        <div style={{ fontSize: 16, color: "var(--fg-3)", maxWidth: 600, lineHeight: 1.5 }}>
          Anchor everything to a race. We periodize back from this date \u2014 base, build, peak, taper.
        </div>

        {/* Name + date row */}
        <div className="card" style={{ marginTop: 28, padding: 0 }}>
          <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr" }}>
            <div style={{ padding: "18px 20px", borderRight: "1px solid var(--hairline-2)" }}>
              <div className="eyebrow" style={{ fontSize: 9 }}>Race name</div>
              <div style={{ fontSize: 17, fontWeight: 600, marginTop: 6 }}>Boston Marathon 2026</div>
            </div>
            <div style={{ padding: "18px 20px", borderRight: "1px solid var(--hairline-2)" }}>
              <div className="eyebrow" style={{ fontSize: 9 }}>Race date</div>
              <div className="num" style={{ fontSize: 17, fontWeight: 600, marginTop: 6 }}>Apr 20, 2026</div>
              <div className="mono accent" style={{ fontSize: 10, letterSpacing: "0.16em", color: "var(--accent)", marginTop: 4 }}>22W 6D OUT</div>
            </div>
            <div style={{ padding: "18px 20px" }}>
              <div className="eyebrow" style={{ fontSize: 9 }}>Race URL (optional)</div>
              <div style={{ fontSize: 13, marginTop: 6, color: "var(--fg-3)", fontFamily: "var(--mono)" }}>baa.org/races/boston</div>
            </div>
          </div>
        </div>

        {/* Race format */}
        <div style={{ marginTop: 22 }}>
          <Eyebrow>Race format</Eyebrow>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 8, marginTop: 12 }}>
            {[
              ["Road run","5K \u2192 Marathon", true],
              ["Trail / Ultra","50K \u2192 200M", false],
              ["Triathlon","Sprint \u2192 140.6", false],
              ["Cycling","Crit \u00b7 GF \u00b7 Stage", false],
              ["Adventure","Multi-discipline", false],
            ].map(([n, s, active], i) => (
              <div key={i} style={{
                padding: "16px 14px",
                border: "1px solid " + (active ? "var(--accent)" : "var(--hairline)"),
                background: active ? "color-mix(in oklab, var(--accent) 10%, transparent)" : "transparent",
                borderRadius: 4,
              }}>
                <div style={{ fontWeight: 600, fontSize: 14 }}>{n}</div>
                <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", marginTop: 4, letterSpacing: "0.12em" }}>{s}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Primary metric + distance + elevation */}
        <div style={{ marginTop: 22, display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
          <div className="card" style={{ padding: 18 }}>
            <Eyebrow>Primary metric</Eyebrow>
            <div style={{ display: "flex", gap: 6, marginTop: 12 }}>
              {[["Distance", true], ["Duration", false]].map(([l, a], i) => (
                <div key={i} style={{
                  flex: 1, padding: "10px 14px", textAlign: "center", borderRadius: 4,
                  border: "1px solid " + (a ? "var(--accent)" : "var(--hairline)"),
                  background: a ? "color-mix(in oklab, var(--accent) 10%, transparent)" : "transparent",
                  fontSize: 13, fontWeight: 500,
                }}>{l}</div>
              ))}
            </div>
          </div>
          <div className="card" style={{ padding: 18 }}>
            <Eyebrow>Distance (km)</Eyebrow>
            <div className="num" style={{ fontSize: 32, fontWeight: 700, marginTop: 6 }}>42.20</div>
            <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em" }}>= 26.2 MI</div>
          </div>
          <div className="card" style={{ padding: 18 }}>
            <Eyebrow>Elevation gain (m)</Eyebrow>
            <div className="num" style={{ fontSize: 32, fontWeight: 700, marginTop: 6 }}>248</div>
            <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em" }}>= 813 FT</div>
          </div>
        </div>

        {/* Goal + first-time + pack */}
        <div style={{ marginTop: 22 }}>
          <Eyebrow>Goal</Eyebrow>
          <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 6 }}>What you're chasing. Feeds our goal-viability check.</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 8, marginTop: 12 }}>
            {[
              ["Finish",   "Just complete"],
              ["Time goal","Sub-3:00", true],
              ["Place",    "Top 10 AG"],
              ["PR",       "Beat 3:04:15"],
            ].map(([l, s, active], i) => (
              <div key={i} style={{
                padding: "14px 16px", borderRadius: 4,
                border: "1px solid " + (active ? "var(--accent)" : "var(--hairline)"),
                background: active ? "color-mix(in oklab, var(--accent) 10%, transparent)" : "transparent",
              }}>
                <div style={{ fontWeight: 600, fontSize: 14 }}>{l}</div>
                <div className="mono num" style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 4, letterSpacing: "0.12em" }}>{s}</div>
              </div>
            ))}
          </div>
        </div>

        <div style={{ marginTop: 22, display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
          <div className="card" style={{ padding: 16 }}>
            <Eyebrow>First time at distance?</Eyebrow>
            <div style={{ display: "flex", gap: 6, marginTop: 10 }}>
              {[["Yes", false], ["No", true]].map(([l, a], i) => (
                <div key={i} style={{ flex: 1, padding: "8px 12px", textAlign: "center", borderRadius: 4, border: "1px solid " + (a ? "var(--accent)" : "var(--hairline)"), background: a ? "color-mix(in oklab, var(--accent) 10%, transparent)" : "transparent", fontSize: 12 }}>{l}</div>
              ))}
            </div>
          </div>
          <div className="card" style={{ padding: 16 }}>
            <Eyebrow>Time goal (free text)</Eyebrow>
            <div className="num" style={{ fontSize: 17, fontWeight: 600, marginTop: 8 }}>sub-3:00</div>
          </div>
          <div className="card" style={{ padding: 16 }}>
            <Eyebrow>Pack weight (kg)</Eyebrow>
            <div className="num" style={{ fontSize: 17, fontWeight: 600, marginTop: 8 }}>\u2014 <span style={{ fontSize: 11, color: "var(--fg-3)", fontWeight: 400 }}>(not required)</span></div>
          </div>
        </div>

        {/* Rules + mandatory gear */}
        <div style={{ marginTop: 22, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <div className="card" style={{ padding: 16 }}>
            <Eyebrow>Race rules summary</Eyebrow>
            <div style={{ fontSize: 13, color: "var(--fg-2)", marginTop: 8, lineHeight: 1.5 }}>
              Wave start by qualifying time. 6h cutoff. No pacers after Hopkinton wave gun. Headphones discouraged. Bib transfer prohibited\u2026
            </div>
            <div className="mono" style={{ fontSize: 10, color: "var(--fg-4)", marginTop: 8, letterSpacing: "0.14em" }}>247 / 4000 CHARS</div>
          </div>
          <div className="card" style={{ padding: 16 }}>
            <Eyebrow>Mandatory gear</Eyebrow>
            <div style={{ fontSize: 13, color: "var(--fg-3)", marginTop: 8, fontStyle: "italic" }}>
              None required for road marathon. We'll skip kit-manifest tracking.
            </div>
            <div className="mono" style={{ fontSize: 10, color: "var(--fg-4)", marginTop: 8, letterSpacing: "0.14em" }}>0 / 4000 CHARS</div>
          </div>
        </div>

        <OnbFooter step={7} backLabel="Back \u00b7 Locations" nextLabel="Finish \u00b7 Generate plan" />
      </div>
    </div>
  </OnbShell>
);

// ═══════════════════════════════════════════════════════════════════
// 6. LOGIN — Split layout (unchanged)
// ═══════════════════════════════════════════════════════════════════
const ScreenLogin = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <div style={{
        flex: 1, padding: "48px 56px", display: "flex", flexDirection: "column", justifyContent: "space-between",
        borderRight: "1px solid var(--hairline-2)",
        background: "radial-gradient(circle at 20% 80%, color-mix(in oklab, var(--accent) 10%, transparent), transparent 60%)",
        position: "relative", overflow: "hidden",
      }}>
        <svg style={{ position: "absolute", inset: 0, width: "100%", height: "100%", opacity: 0.18 }} viewBox="0 0 700 900" preserveAspectRatio="xMidYMid slice">
          {[0,1,2,3,4,5,6,7,8,9,10,11,12].map(i => (
            <path key={i}
              d={`M -50 ${100 + i * 60} Q 200 ${50 + i * 60} 350 ${120 + i * 50} T 750 ${80 + i * 55}`}
              stroke="var(--fg)" strokeWidth="0.6" fill="none"
            />
          ))}
        </svg>

        <div style={{ display: "flex", alignItems: "center", gap: 10, position: "relative" }}>
          <AsMark size={26} />
          <Wordmark />
        </div>

        <div style={{ position: "relative" }}>
          <Eyebrow accent>\u25cf AI TRAINING \u00b7 FOR THE DATA-OBSESSED</Eyebrow>
          <h1 style={{ fontSize: 56, fontWeight: 800, letterSpacing: "-0.03em", lineHeight: 1, margin: "18px 0 18px", maxWidth: 480 }}>
            Every workout, <span style={{ color: "var(--accent)" }}>periodized.</span><br />
            Every session, <span style={{ color: "var(--fg-3)", fontWeight: 300 }}>logged.</span>
          </h1>
          <div style={{ fontSize: 16, color: "var(--fg-2)", maxWidth: 440, lineHeight: 1.5 }}>
            Race-anchored plans, fueled by your provider data and tuned daily to how you're actually showing up.
          </div>
        </div>

        <div style={{ display: "flex", gap: 0, borderTop: "1px solid var(--hairline-2)", paddingTop: 18, position: "relative" }}>
          {[["2,840+","Athletes"],["62%","BQ rate"],["v3.2","Engine"]].map(([v,l],i)=>(
            <div key={i} style={{ flex: 1, paddingRight: 18, borderRight: i < 2 ? "1px solid var(--hairline-2)" : "none", paddingLeft: i > 0 ? 18 : 0 }}>
              <div className="num" style={{ fontSize: 22, fontWeight: 700 }}>{v}</div>
              <div className="eyebrow" style={{ fontSize: 9, marginTop: 4 }}>{l}</div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ width: 460, padding: "48px 48px", display: "flex", flexDirection: "column", justifyContent: "center" }}>
        <Eyebrow>Sign in</Eyebrow>
        <h2 style={{ fontSize: 32, fontWeight: 700, letterSpacing: "-0.02em", margin: "10px 0 8px" }}>Welcome back.</h2>
        <div style={{ color: "var(--fg-3)", fontSize: 14 }}>New here? <span style={{ color: "var(--accent)", borderBottom: "1px solid var(--accent)" }}>Create an account</span></div>

        <div style={{ marginTop: 32, display: "flex", flexDirection: "column", gap: 14 }}>
          <div>
            <div className="eyebrow" style={{ fontSize: 9, marginBottom: 6 }}>EMAIL</div>
            <div style={{ padding: "12px 14px", border: "1px solid var(--hairline)", borderRadius: 4, fontSize: 15, fontFamily: "var(--mono)" }}>
              andrew@aidstation.run
            </div>
          </div>
          <div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <div className="eyebrow" style={{ fontSize: 9, marginBottom: 6 }}>PASSWORD</div>
              <div className="mono" style={{ fontSize: 9, letterSpacing: "0.18em", color: "var(--fg-3)" }}>FORGOT?</div>
            </div>
            <div style={{ padding: "12px 14px", border: "1px solid var(--accent)", borderRadius: 4, fontSize: 15, fontFamily: "var(--mono)", letterSpacing: "0.2em" }}>
              \u25cf\u25cf\u25cf\u25cf\u25cf\u25cf\u25cf\u25cf\u25cf\u25cf\u25cf\u25cf
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 4 }}>
            <div style={{ width: 16, height: 16, border: "1px solid var(--accent)", background: "var(--accent)", borderRadius: 2, display: "grid", placeItems: "center", color: "var(--ink)" }}>
              <Ic d={I.check} size={11} sw={2.5} />
            </div>
            <span style={{ fontSize: 12, color: "var(--fg-2)" }}>Keep me signed in on this device</span>
          </div>
          <div className="btn btn-primary" style={{ justifyContent: "center", padding: "14px 16px", fontSize: 12, marginTop: 8 }}>
            Sign in <Ic d={I.arrow} size={12} sw={2} />
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12, margin: "24px 0", color: "var(--fg-4)" }}>
          <div style={{ flex: 1, height: 1, background: "var(--hairline)" }} />
          <span className="mono" style={{ fontSize: 9, letterSpacing: "0.22em" }}>OR</span>
          <div style={{ flex: 1, height: 1, background: "var(--hairline)" }} />
        </div>

        <div className="btn btn-ghost" style={{ justifyContent: "center", padding: "12px 16px" }}>
          <Ic d={I.link} size={13} /> Continue with Strava
        </div>

        <div className="mono" style={{ marginTop: 40, fontSize: 9, letterSpacing: "0.22em", color: "var(--fg-4)", textTransform: "uppercase" }}>
          By signing in you agree to \u00b7 TERMS \u00b7 PRIVACY
        </div>
      </div>
    </div>
  </div>
);

Object.assign(window, {
  ScreenLog,
  OnbConnect, OnbPrefill, OnbSchedule, OnbSkills, OnbLocations, OnbRace,
  ScreenLogin,
});
