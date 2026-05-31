/* AIDSTATION redesign — Coach memory (§12D)
   ───────────────────────────────────────────────────────────────
   The profile/edit.html › "Coach memory" tab. Durable preferences the
   AI coach reads on every plan generation, review, and chat. Auto-
   captured from chat / plan reviews / natural-log entries / workout
   notes (fb_source), or added manually. Each is deletable; some are
   marked permanent. Backed by: profile.add_preference /
   profile.delete_preference / profile.view_feedback. */

// fb_source → friendly label
const SOURCE_LABEL = {
  chat: "chat",
  plan_review: "plan review",
  natural_log: "natural log",
  workout_note: "workout note",
  manual: "added manually",
};

const MEMORY = [
  { id: 1, cat: "exercise_exclusion", perm: true,  content: "No burpees — excluded at user request after knee irritation.", src: "chat",         date: "May 18", fb: true },
  { id: 2, cat: "fueling",            perm: true,  content: "Targets 60 g carb/hr on long runs; prefers gels over chews.",   src: "workout_note", date: "May 20", fb: true },
  { id: 3, cat: "intensity",          perm: false, content: "Responds poorly to back-to-back hard days — wants 48 h between Z4+ sessions.", src: "plan_review", date: "May 21", fb: true },
  { id: 4, cat: "equipment",          perm: false, content: "Home gym tops out at 50 lb dumbbells; program strength around it.", src: "natural_log", date: "May 12", fb: true },
  { id: 5, cat: "recovery",           perm: true,  content: "Sleeps ~7 h; flag any week where load jumps more than 15%.",    src: "plan_review", date: "May 22", fb: true },
  { id: 6, cat: "scheduling",         perm: false, content: "Thursdays are tight — keep that session at or under 45 min.",   src: "manual",       date: "May 14", fb: false },
  { id: 7, cat: "communication",      perm: false, content: "Wants terse coaching notes — skip the pep talk.",              src: "manual",       date: "May 09", fb: false },
  { id: 8, cat: "terrain",            perm: false, content: "Trains on rolling trail; bias long runs to trail-specific terrain.", src: "chat",   date: "May 16", fb: true },
];

const CATS = ["exercise_exclusion", "fueling", "intensity", "equipment", "recovery", "scheduling", "communication", "terrain", "nutrition", "general"];

const fmtCat = (c) => c.replace(/_/g, " ");

const SourceTag = ({ src, date, fb }) => (
  <span className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--fg-3)", textTransform: "uppercase" }}>
    {src === "manual" ? "ADDED MANUALLY" : `CAPTURED FROM ${SOURCE_LABEL[src].toUpperCase()}`} · {date.toUpperCase()}
    {fb && <span style={{ color: "var(--accent)" }}> · VIEW ORIGINAL →</span>}
  </span>
);

const MemoryItem = ({ m, compact }) => (
  <div style={{ display: "flex", gap: 14, padding: compact ? "12px 0" : "14px 0", borderBottom: "1px solid var(--hairline-2)", alignItems: "flex-start" }}>
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 6 }}>
        <Pill tone="solid">{fmtCat(m.cat)}</Pill>
        {m.perm && <Pill tone="warn">PERMANENT</Pill>}
      </div>
      <div style={{ fontSize: compact ? 13 : 14, fontWeight: 600, lineHeight: 1.45, color: "var(--fg)" }}>{m.content}</div>
      <div style={{ marginTop: 5 }}><SourceTag src={m.src} date={m.date} fb={m.fb} /></div>
    </div>
    <div className="btn btn-ghost btn-sm" style={{ color: "var(--bad)", borderColor: "color-mix(in oklab, var(--bad) 25%, transparent)", flexShrink: 0 }}>
      <Ic d={I.x} size={11} sw={2.2} />
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// 12D. COACH MEMORY · desktop
// ═══════════════════════════════════════════════════════════════════
const ScreenCoachMemory = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="athlete" />
      <div className="page">
        <TopBar crumbs={["Athlete", "Coach memory"]} actions={
          <div className="btn btn-ghost btn-sm"><Ic d={I.bolt} size={11} /> How the coach uses this</div>
        } />
        <div className="page-body">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 18 }}>
            <div style={{ maxWidth: 620 }}>
              <Eyebrow>Athlete · what the coach remembers</Eyebrow>
              <h1 className="page-title" style={{ marginTop: 8 }}>Coach memory</h1>
              <div className="page-sub">Durable preferences your AI coach reads on every plan generation, review, and chat. Most are captured automatically from your conversations, plan-review feedback, and logs — edit or remove any of them, or add your own.</div>
            </div>
            <div style={{ display: "flex", gap: 14 }}>
              {[["Preferences", "8"], ["Permanent", "3"], ["Auto-captured", "6"]].map(([k, v], i) => (
                <div key={i} className="stat-card" style={{ minWidth: 100, padding: 14 }}>
                  <div className="k">{k}</div>
                  <div className="v num" style={{ fontSize: 22 }}>{v}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Filters */}
          <div className="card" style={{ padding: "10px 16px", marginBottom: 14, display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <Ic d={I.search} size={14} />
            <span style={{ flex: 1, color: "var(--fg-3)", fontSize: 13, minWidth: 160 }}>Filter preferences…</span>
            {["All", "Permanent", "From chat", "From reviews", "Manual"].map((f, i) => (
              <Pill key={i} tone={i === 0 ? "accent" : null}>{f.toUpperCase()}</Pill>
            ))}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr", gap: 18, alignItems: "start" }}>
            {/* LEFT — memory list */}
            <div className="card" style={{ padding: "4px 18px 14px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 0 4px" }}>
                <Eyebrow>Active preferences · 8</Eyebrow>
                <span className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--fg-3)" }}>NEWEST FIRST</span>
              </div>
              {MEMORY.map((m) => <MemoryItem key={m.id} m={m} />)}
              <div className="mono" style={{ fontSize: 10, letterSpacing: "0.14em", color: "var(--fg-4)", marginTop: 14, textTransform: "uppercase", lineHeight: 1.6 }}>
                ⓘ DELETING A PREFERENCE STOPS THE COACH USING IT ON THE NEXT RUN. AUTO-CAPTURED ONES CAN RE-APPEAR IF YOU RAISE THEM AGAIN IN CHAT.
              </div>
            </div>

            {/* RIGHT — add + how it works */}
            <div className="stack">
              <div className="card" style={{ padding: 20, border: "1px solid color-mix(in oklab, var(--accent) 30%, var(--hairline-2))" }}>
                <Eyebrow accent>● ADD A PREFERENCE</Eyebrow>
                <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 12 }}>
                  <div>
                    <div className="mono" style={{ fontSize: 9, letterSpacing: "0.22em", textTransform: "uppercase", color: "var(--fg-3)", marginBottom: 6 }}>● CATEGORY</div>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", height: 40, padding: "0 12px", background: "var(--bg-2)", border: "1px solid var(--hairline-2)", borderRadius: 4 }}>
                      <span style={{ fontSize: 14 }}>exercise exclusion</span>
                      <Ic d={I.chevD} size={14} />
                    </div>
                  </div>
                  <div>
                    <div className="mono" style={{ fontSize: 9, letterSpacing: "0.22em", textTransform: "uppercase", color: "var(--fg-3)", marginBottom: 6 }}>● PREFERENCE</div>
                    <div style={{ minHeight: 64, padding: "10px 12px", background: "var(--bg-2)", border: "1px solid var(--hairline-2)", borderRadius: 4, fontSize: 14, color: "var(--fg-4)", lineHeight: 1.5 }}>
                      e.g. No box jumps — bad ankle. Keep plyometrics low-impact.
                    </div>
                  </div>
                  <label style={{ display: "flex", gap: 10, alignItems: "center", fontSize: 13, color: "var(--fg-2)" }}>
                    <span style={{ width: 16, height: 16, borderRadius: 3, border: "1px solid var(--accent)", background: "var(--accent)", color: "var(--ink)", display: "grid", placeItems: "center", flexShrink: 0 }}>
                      <Ic d={I.check} size={10} sw={3} />
                    </span>
                    Treat as a permanent rule
                  </label>
                  <div className="btn btn-primary" style={{ width: "100%", justifyContent: "center", padding: "11px 14px" }}>
                    <Ic d={I.plus} size={12} sw={2.2} /> Add preference
                  </div>
                </div>
              </div>

              <div className="card-flush" style={{ padding: 16 }}>
                <Eyebrow>Where these come from</Eyebrow>
                <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 10 }}>
                  {[
                    ["Chat", "Things you tell the coach in conversation."],
                    ["Plan reviews", "Feedback you give when reviewing a generated plan."],
                    ["Natural log", "Free-text entries we parse into structured prefs."],
                    ["Workout notes", "Notes attached to a logged session."],
                  ].map(([k, v], i) => (
                    <div key={i} style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: 10, alignItems: "baseline" }}>
                      <span className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--accent)", textTransform: "uppercase", whiteSpace: "nowrap" }}>{k}</span>
                      <span style={{ fontSize: 12, color: "var(--fg-3)", lineHeight: 1.45 }}>{v}</span>
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

// ═══════════════════════════════════════════════════════════════════
// 12D. COACH MEMORY · mobile
// ═══════════════════════════════════════════════════════════════════
const MobileCoachMemory = () => (
  <div className="screen">
    <StatusBar />
    <AppBar title="Coach memory" left={<Ic d={I.chevL} size={22} />} right={<Ic d={I.search} size={20} />} />

    <div style={{ flex: 1, overflow: "auto", padding: "14px 16px 28px" }}>
      <div style={{ marginBottom: 14 }}>
        <div style={{ color: "var(--fg-3)", fontSize: 13, lineHeight: 1.5 }}>
          What your AI coach remembers across plans, reviews, and chats. Auto-captured or add your own.
        </div>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        {[["Prefs", "8"], ["Permanent", "3"], ["Auto", "6"]].map(([k, v], i) => (
          <div key={i} className="stat-card col" style={{ flex: 1, padding: 12 }}>
            <div className="k" style={{ fontSize: 9 }}>{k}</div>
            <div className="v num" style={{ fontSize: 20 }}>{v}</div>
          </div>
        ))}
      </div>

      <div style={{ display: "flex", gap: 6, marginBottom: 14, overflowX: "auto" }}>
        {["All", "Permanent", "Chat", "Reviews", "Manual"].map((f, i) => (
          <Pill key={i} tone={i === 0 ? "accent" : null}>{f.toUpperCase()}</Pill>
        ))}
      </div>

      <Eyebrow>Active preferences · 8</Eyebrow>
      <div className="card" style={{ padding: "2px 14px", marginTop: 10, marginBottom: 16 }}>
        {MEMORY.map((m) => <MemoryItem key={m.id} m={m} compact />)}
      </div>

      <div className="card" style={{ padding: 16, border: "1px solid color-mix(in oklab, var(--accent) 30%, var(--hairline-2))" }}>
        <Eyebrow accent>● ADD A PREFERENCE</Eyebrow>
        <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", height: 38, padding: "0 12px", background: "var(--bg-2)", border: "1px solid var(--hairline-2)", borderRadius: 4 }}>
            <span style={{ fontSize: 13 }}>exercise exclusion</span>
            <Ic d={I.chevD} size={14} />
          </div>
          <div style={{ minHeight: 54, padding: "9px 12px", background: "var(--bg-2)", border: "1px solid var(--hairline-2)", borderRadius: 4, fontSize: 13, color: "var(--fg-4)", lineHeight: 1.45 }}>
            e.g. No box jumps — bad ankle.
          </div>
          <label style={{ display: "flex", gap: 10, alignItems: "center", fontSize: 13, color: "var(--fg-2)" }}>
            <span style={{ width: 16, height: 16, borderRadius: 3, border: "1px solid var(--accent)", background: "var(--accent)", color: "var(--ink)", display: "grid", placeItems: "center", flexShrink: 0 }}>
              <Ic d={I.check} size={10} sw={3} />
            </span>
            Permanent rule
          </label>
          <div className="btn btn-primary btn-sm" style={{ width: "100%", justifyContent: "center" }}>
            <Ic d={I.plus} size={11} sw={2.2} /> Add preference
          </div>
        </div>
      </div>
    </div>

    <TabBar active="me" />
  </div>
);

Object.assign(window, { ScreenCoachMemory, MobileCoachMemory });
