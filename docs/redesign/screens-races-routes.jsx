/* AIDSTATION redesign — Race events + Notification deep-links (§13, §22C)
   ───────────────────────────────────────────────────────────────
   §13  Race events manager — the race_events tab. A race is the anchor
        every plan periodizes back from (Base→Build→Peak→Taper). CRUD
        over goal races: A/B/C priority, date, distance, location.
        Editing a date/distance triggers the existing plan-refresh flow.
   §22C Notification deep-links — audits every notification type and
        maps it to the real destination screen it routes to, plus the
        tap affordance on a feed row. */

// ═══════════════════════════════════════════════════════════════════
// §13. RACE EVENTS MANAGER
// ═══════════════════════════════════════════════════════════════════
const RACES = [
  {
    id: 1, name: "Boston Marathon", date: "Apr 20, 2026", dist: "Marathon · 26.2 mi",
    loc: "Boston, MA", prio: "A", status: "active", weeksOut: 22, phase: "Build",
    note: "Goal race. Plan v13 periodizes to this date.", terrain: "Road · point-to-point · net downhill",
  },
  {
    id: 2, name: "Cherry Blossom Ten Miler", date: "Mar 8, 2026", dist: "10 mi",
    loc: "Washington, DC", prio: "B", status: "active", weeksOut: 14, phase: "—",
    note: "Tune-up / fitness test. Slots into Build as a hard effort.", terrain: "Road · flat",
  },
  {
    id: 3, name: "Rock Creek Trail Half", date: "Feb 14, 2026", dist: "Half · 13.1 mi",
    loc: "Washington, DC", prio: "C", status: "active", weeksOut: 11, phase: "—",
    note: "Optional. Counts as a long run if legs are good.", terrain: "Trail · rolling",
  },
  {
    id: 4, name: "NYC Marathon", date: "Nov 2, 2025", dist: "Marathon · 26.2 mi",
    loc: "New York, NY", prio: "A", status: "past", result: "3:14:22 · PR", terrain: "Road",
  },
  {
    id: 5, name: "Bay to Breakers 12K", date: "May 18, 2025", dist: "12K",
    loc: "San Francisco, CA", prio: "C", status: "past", result: "48:51", terrain: "Road · hilly",
  },
];

const PRIO_TONE = { A: "accent", B: "info", C: null };

const PrioBadge = ({ p }) => (
  <div style={{
    width: 26, height: 26, borderRadius: 5, flexShrink: 0,
    background: p === "A" ? "var(--accent)" : p === "B" ? "color-mix(in oklab, var(--accent) 22%, var(--bg-3))" : "var(--bg-3)",
    color: p === "A" ? "var(--ink)" : "var(--fg-2)",
    display: "grid", placeItems: "center", fontFamily: "var(--mono)", fontWeight: 800, fontSize: 13,
  }}>{p}</div>
);

const RaceRow = ({ r }) => (
  <div className="card" style={{ padding: 16, display: "flex", gap: 16, alignItems: "center", opacity: r.status === "past" ? 0.72 : 1 }}>
    <PrioBadge p={r.prio} />
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <span style={{ fontWeight: 700, fontSize: 16 }}>{r.name}</span>
        {r.status === "active" && r.prio === "A" && <Pill tone="accent">GOAL RACE</Pill>}
        {r.status === "active" && r.phase !== "—" && <Pill tone="solid">{r.phase.toUpperCase()} PHASE</Pill>}
        {r.status === "past" && <Pill tone="good">✓ {r.result}</Pill>}
      </div>
      <div className="mono" style={{ fontSize: 10, letterSpacing: "0.14em", color: "var(--fg-3)", marginTop: 6, textTransform: "uppercase" }}>
        {r.date} · {r.dist} · {r.loc}{r.status === "active" ? ` · ${r.weeksOut} WK OUT` : ""}
      </div>
      {r.note && <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 6, lineHeight: 1.4 }}>{r.note}</div>}
    </div>
    {r.status === "active" ? (
      <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
        <div className="btn btn-ghost btn-sm">Edit</div>
        <div className="btn btn-ghost btn-sm"><Ic d={I.more} size={14} /></div>
      </div>
    ) : (
      <div className="btn btn-ghost btn-sm" style={{ flexShrink: 0 }}>View recap</div>
    )}
  </div>
);

const ScreenRaceEvents = () => {
  const active = RACES.filter((r) => r.status === "active");
  const past = RACES.filter((r) => r.status === "past");
  return (
    <div className="screen">
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <Sidebar active="plan" />
        <div className="page">
          <TopBar crumbs={["Plan", "Races"]} actions={
            <div className="btn btn-primary"><Ic d={I.plus} size={12} sw={2.2} /> Add a race</div>
          } />
          <div className="page-body">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 20 }}>
              <div style={{ maxWidth: 620 }}>
                <Eyebrow>Plan · the dates everything points at</Eyebrow>
                <h1 className="page-title" style={{ marginTop: 8 }}>Races</h1>
                <div className="page-sub">Your goal race anchors the whole plan — we periodize backward from it through Base, Build, Peak, and Taper. B and C races slot in as tune-ups. Change a date or distance and the plan re-cascades.</div>
              </div>
              <div style={{ display: "flex", gap: 14 }}>
                {[["Upcoming", "3"], ["Goal (A)", "1"], ["Weeks to A", "22"]].map(([k, v], i) => (
                  <div key={i} className="stat-card" style={{ minWidth: 100, padding: 14 }}>
                    <div className="k">{k}</div>
                    <div className="v num" style={{ fontSize: 22 }}>{v}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Goal race spotlight */}
            <div className="card" style={{ padding: 0, marginBottom: 22, overflow: "hidden", border: "1px solid color-mix(in oklab, var(--accent) 35%, var(--hairline-2))" }}>
              <div style={{ display: "flex" }}>
                <div style={{ width: 6, background: "var(--accent)" }} />
                <div style={{ flex: 1, padding: 20 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                    <div>
                      <Eyebrow accent>● GOAL RACE · A PRIORITY</Eyebrow>
                      <div style={{ fontSize: 26, fontWeight: 800, letterSpacing: "-0.02em", marginTop: 8 }}>Boston Marathon</div>
                      <div className="mono" style={{ fontSize: 11, letterSpacing: "0.14em", color: "var(--fg-3)", marginTop: 6, textTransform: "uppercase" }}>
                        APR 20, 2026 · MARATHON 26.2 MI · BOSTON, MA · ROAD · NET DOWNHILL
                      </div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <div className="num" style={{ fontSize: 40, fontWeight: 800, lineHeight: 1, color: "var(--accent)" }}>22</div>
                      <div className="mono" style={{ fontSize: 9, letterSpacing: "0.18em", color: "var(--fg-3)", marginTop: 2 }}>WEEKS OUT</div>
                    </div>
                  </div>

                  {/* Periodization track */}
                  <div style={{ marginTop: 18 }}>
                    <div style={{ display: "flex", height: 8, borderRadius: 4, overflow: "hidden", gap: 2 }}>
                      {[["Base", 8, "var(--bg-3)"], ["Build", 8, "var(--accent)"], ["Peak", 4, "color-mix(in oklab, var(--accent) 45%, var(--bg-3))"], ["Taper", 2, "color-mix(in oklab, var(--accent) 22%, var(--bg-3))"]].map(([ph, w, c], i) => (
                        <div key={i} style={{ flex: w, background: c }} />
                      ))}
                    </div>
                    <div style={{ display: "flex", marginTop: 8 }}>
                      {[["Base", 8], ["Build ◀ now", 8], ["Peak", 4], ["Taper", 2]].map(([ph, w], i) => (
                        <div key={i} style={{ flex: w }}>
                          <span className="mono" style={{ fontSize: 9, letterSpacing: "0.12em", color: i === 1 ? "var(--accent)" : "var(--fg-3)", textTransform: "uppercase", fontWeight: i === 1 ? 700 : 400 }}>{ph}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div style={{ display: "flex", gap: 8, marginTop: 18 }}>
                    <div className="btn btn-ghost btn-sm">Edit race</div>
                    <div className="btn btn-ghost btn-sm">View plan</div>
                    <div className="btn btn-text btn-sm" style={{ color: "var(--fg-3)" }}>Change goal race</div>
                  </div>
                </div>
              </div>
            </div>

            {/* Upcoming list */}
            <Eyebrow>Upcoming · {active.length}</Eyebrow>
            <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 12, marginBottom: 24 }}>
              {active.map((r) => <RaceRow key={r.id} r={r} />)}
            </div>

            {/* Past list */}
            <Eyebrow>Past · {past.length}</Eyebrow>
            <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 12 }}>
              {past.map((r) => <RaceRow key={r.id} r={r} />)}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// ── Mobile race events ────────────────────────────────────────────
const MobileRaceEvents = () => {
  const active = RACES.filter((r) => r.status === "active");
  const past = RACES.filter((r) => r.status === "past");
  return (
    <div className="screen">
      <StatusBar />
      <AppBar title="Races" left={<Ic d={I.chevL} size={22} />} right={<Ic d={I.plus} size={22} />} />
      <div style={{ flex: 1, overflow: "auto", padding: "14px 16px 28px" }}>
        {/* Goal spotlight */}
        <div className="card" style={{ padding: 0, marginBottom: 18, overflow: "hidden", border: "1px solid color-mix(in oklab, var(--accent) 35%, var(--hairline-2))" }}>
          <div style={{ display: "flex" }}>
            <div style={{ width: 5, background: "var(--accent)" }} />
            <div style={{ flex: 1, padding: 16 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <div style={{ minWidth: 0 }}>
                  <Eyebrow accent>● GOAL · A</Eyebrow>
                  <div style={{ fontSize: 19, fontWeight: 800, letterSpacing: "-0.02em", marginTop: 6 }}>Boston Marathon</div>
                  <div className="mono" style={{ fontSize: 9, letterSpacing: "0.12em", color: "var(--fg-3)", marginTop: 4, textTransform: "uppercase" }}>APR 20 · 26.2 MI · BOSTON</div>
                </div>
                <div style={{ textAlign: "right", flexShrink: 0 }}>
                  <div className="num" style={{ fontSize: 28, fontWeight: 800, lineHeight: 1, color: "var(--accent)" }}>22</div>
                  <div className="mono" style={{ fontSize: 8, letterSpacing: "0.16em", color: "var(--fg-3)" }}>WK OUT</div>
                </div>
              </div>
              <div style={{ display: "flex", height: 6, borderRadius: 3, overflow: "hidden", gap: 2, marginTop: 14 }}>
                {[8, 8, 4, 2].map((w, i) => (
                  <div key={i} style={{ flex: w, background: i === 1 ? "var(--accent)" : i === 0 ? "var(--bg-3)" : "color-mix(in oklab, var(--accent) 35%, var(--bg-3))" }} />
                ))}
              </div>
              <div className="mono" style={{ fontSize: 8, letterSpacing: "0.12em", color: "var(--accent)", marginTop: 6, textTransform: "uppercase" }}>◀ BUILD PHASE</div>
            </div>
          </div>
        </div>

        <Eyebrow>Upcoming · {active.length}</Eyebrow>
        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 10, marginBottom: 20 }}>
          {active.map((r) => (
            <div key={r.id} className="card" style={{ padding: 12, display: "flex", gap: 12, alignItems: "center" }}>
              <PrioBadge p={r.prio} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 700, fontSize: 14 }}>{r.name}</div>
                <div className="mono" style={{ fontSize: 9, letterSpacing: "0.12em", color: "var(--fg-3)", marginTop: 3, textTransform: "uppercase" }}>{r.date} · {r.dist.split(" · ")[0]} · {r.weeksOut} WK</div>
              </div>
              <Ic d={I.chevR} size={14} />
            </div>
          ))}
        </div>

        <Eyebrow>Past · {past.length}</Eyebrow>
        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 10 }}>
          {past.map((r) => (
            <div key={r.id} className="card" style={{ padding: 12, display: "flex", gap: 12, alignItems: "center", opacity: 0.75 }}>
              <PrioBadge p={r.prio} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 700, fontSize: 14 }}>{r.name}</div>
                <div className="mono" style={{ fontSize: 9, letterSpacing: "0.12em", color: "var(--fg-3)", marginTop: 3, textTransform: "uppercase" }}>{r.date} · {r.dist.split(" · ")[0]}</div>
              </div>
              <Pill tone="good">✓ {r.result}</Pill>
            </div>
          ))}
        </div>

        <div className="btn btn-primary" style={{ marginTop: 20, width: "100%", justifyContent: "center" }}>
          <Ic d={I.plus} size={12} sw={2.2} /> Add a race
        </div>
      </div>
      <TabBar active="plan" />
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════
// §22C. NOTIFICATION DEEP-LINKS
// Every notification group → the real screen it routes to.
// ═══════════════════════════════════════════════════════════════════
const ROUTES = [
  { group: "Plan", tone: "accent", example: "Plan v13 is ready to review", action: "VIEW DIFF",
    dest: "Plan · compare / diff view", crumb: "Plan › v12 ↔ v13", note: "Opens the version compare with the 4 changed sessions pre-expanded." },
  { group: "Plan", tone: "accent", example: "Boston is 22 weeks out", action: "—",
    dest: "Plan · current week", crumb: "Plan › Build › Wk 1", note: "Scrolls the plan to the phase boundary it's announcing." },
  { group: "Provider", tone: "info", example: "Strava pulled 3 new sessions", action: "VIEW",
    dest: "Connections › Files (filtered: auto · today)", crumb: "Connections › Files", note: "Files tab pre-filtered to the new imports." },
  { group: "Sessions", tone: "warn", example: "Conditions log missing", action: "LOG NOW",
    dest: "Quick log › Conditions (that session)", crumb: "Log › Conditions", note: "Opens the conditions form bound to the flagged session." },
  { group: "Sessions", tone: "good", example: "PR — bench press 165×5", action: "VIEW HISTORY",
    dest: "Exercise detail › Bench press › history", crumb: "Exercises › Bench press", note: "Lands on the lift's progression chart." },
  { group: "Sessions", tone: "good", example: "Workout auto-completed", action: "—",
    dest: "Workout detail (the matched session)", crumb: "Workouts › Mon easy", note: "Read-only completed view with the matched FIT attached." },
  { group: "Exercises", tone: "warn", example: "Overhead press plateau", action: "DELOAD",
    dest: "Exercise detail › deload action sheet", crumb: "Exercises › OHP", note: "Opens the exercise with the 10% deload pre-staged." },
  { group: "Plan", tone: "warn", example: "Coach review · Tier 2 due", action: "REVIEW NOW",
    dest: "Coaching review flow", crumb: "Plan › Weekly review", note: "Starts the Tier-2 weekly review." },
  { group: "System", tone: "info", example: "Engine v3.2 deployed", action: "SEE CHANGES",
    dest: "Plan · engine diff (v3.1 ↔ v3.2)", crumb: "Plan › Engine diff", note: "Shows what the engine bump changed (or didn't)." },
];

const TONE_DOT = { accent: "var(--accent)", info: "var(--fg-2)", warn: "var(--warn)", good: "var(--good)" };

const ScreenNotifRoutes = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="home" />
      <div className="page">
        <TopBar crumbs={["Notifications", "Deep-links"]} actions={
          <div className="btn btn-ghost btn-sm"><Ic d={I.gear} size={11} /> Notification settings</div>
        } />
        <div className="page-body">
          <div style={{ marginBottom: 18, maxWidth: 680 }}>
            <Eyebrow>Notifications · routing map</Eyebrow>
            <h1 className="page-title" style={{ marginTop: 8 }}>Where each tap lands.</h1>
            <div className="page-sub">Every notification is a doorway. This maps each type to the exact screen + state it opens — no dead ends. Tapping a feed row (right) routes here; tapping its action button jumps straight to the deep state.</div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr", gap: 20, alignItems: "start" }}>
            {/* LEFT — the routing table */}
            <div className="card" style={{ padding: 0 }}>
              <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--hairline-2)", display: "flex", justifyContent: "space-between" }}>
                <Eyebrow>Type → destination · 9 mapped</Eyebrow>
                <span className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--good)" }}>0 DEAD ENDS</span>
              </div>
              {ROUTES.map((r, i) => (
                <div key={i} style={{ padding: "14px 16px", borderBottom: i < ROUTES.length - 1 ? "1px solid var(--hairline-2)" : "none" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                    <span style={{ width: 7, height: 7, borderRadius: "50%", background: TONE_DOT[r.tone], flexShrink: 0 }} />
                    <Pill tone="solid">{r.group.toUpperCase()}</Pill>
                    <span style={{ fontSize: 13, color: "var(--fg-2)", fontWeight: 500 }}>"{r.example}"</span>
                    {r.action !== "—" && <Pill tone="accent">{r.action}</Pill>}
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: 10, alignItems: "center", paddingLeft: 17 }}>
                    <Ic d={I.arrow} size={14} />
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                        <span style={{ fontSize: 13, fontWeight: 600 }}>{r.dest}</span>
                        <span className="mono" style={{ fontSize: 9, letterSpacing: "0.12em", color: "var(--accent)", textTransform: "uppercase" }}>{r.crumb}</span>
                      </div>
                      <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 3, lineHeight: 1.4 }}>{r.note}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* RIGHT — the tap affordance on a real feed row */}
            <div className="stack">
              <div className="card-flush" style={{ padding: 16 }}>
                <Eyebrow>The affordance</Eyebrow>
                <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 8, lineHeight: 1.5 }}>
                  The whole row is tappable → routes to the destination. The action button is a shortcut to the <i>deep</i> state. Both resolve; neither dead-ends.
                </div>

                {/* Demo feed row with hover/tap state */}
                <div style={{ marginTop: 14, border: "1px solid color-mix(in oklab, var(--accent) 40%, var(--hairline))", borderRadius: 6, padding: 14, background: "color-mix(in oklab, var(--accent) 6%, transparent)", cursor: "pointer" }}>
                  <div style={{ display: "flex", gap: 12 }}>
                    <div style={{ width: 30, height: 30, borderRadius: 6, background: "var(--accent)", color: "var(--ink)", display: "grid", placeItems: "center", flexShrink: 0 }}>
                      <Ic d={I.bolt} size={14} />
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 600 }}>Plan v13 is ready to review</div>
                      <div style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 3, lineHeight: 1.4 }}>4 sessions changed across the next 7 days.</div>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 10 }}>
                        <div className="btn btn-primary btn-sm">VIEW DIFF</div>
                        <span className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--fg-3)", textTransform: "uppercase" }}>TAP ROW → PLAN</span>
                      </div>
                    </div>
                  </div>
                  <div style={{ marginTop: 12, paddingTop: 10, borderTop: "1px dashed color-mix(in oklab, var(--accent) 30%, var(--hairline))", display: "flex", alignItems: "center", gap: 8 }}>
                    <Ic d={I.arrow} size={13} />
                    <span className="mono" style={{ fontSize: 10, letterSpacing: "0.12em", color: "var(--accent)", textTransform: "uppercase" }}>ROUTES TO · PLAN › V12 ↔ V13</span>
                  </div>
                </div>
              </div>

              <div className="card-flush" style={{ padding: 16 }}>
                <Eyebrow>Rules</Eyebrow>
                <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 9 }}>
                  {[
                    "Every type has a destination — a notification with no route is a bug, not a feature.",
                    "Deleted/stale target (e.g. a removed plan version) → falls back to the section index, never a 404.",
                    "Tapping marks the item read; the action button does too.",
                    "Deep-links survive cold start — opening from a push lands on the same state.",
                  ].map((t, i) => (
                    <div key={i} style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: 9, alignItems: "baseline" }}>
                      <Ic d={I.check} size={13} sw={2.4} />
                      <span style={{ fontSize: 12, color: "var(--fg-2)", lineHeight: 1.45 }}>{t}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

Object.assign(window, { ScreenRaceEvents, MobileRaceEvents, ScreenNotifRoutes });
