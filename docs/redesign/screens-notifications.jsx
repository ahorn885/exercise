/* AIDSTATION redesign — Notifications / Activity feed
   Desktop full-page feed · Desktop dropdown panel (top-bar) · Mobile feed */

// ═══════════════════════════════════════════════════════════════════
// Shared notification items
// ═══════════════════════════════════════════════════════════════════
const NOTIFICATIONS = [
  // Today
  {
    when: "TODAY", time: "9:14 AM", tone: "accent", group: "Plan",
    title: "Plan v13 is ready to review",
    body: "Refresh completed — 4 sessions changed across the next 7 days. Hamstring + travel context applied.",
    action: "VIEW DIFF", actionTone: "primary", unread: true,
  },
  {
    when: "TODAY", time: "9:12 AM", tone: "info", group: "Provider",
    title: "Strava pulled 3 new sessions",
    body: "Yesterday's long run, Monday's strength session, and a Tuesday recovery spin.",
    action: "VIEW", unread: true,
  },
  {
    when: "TODAY", time: "8:42 AM", tone: "warn", group: "Sessions",
    title: "Conditions log missing",
    body: "Tuesday's long run is logged without conditions data. Worth a minute — clothing recs depend on this.",
    action: "LOG NOW", actionTone: "warn", unread: true,
  },
  {
    when: "TODAY", time: "6:30 AM", tone: "good", group: "Sessions",
    title: "PR — bench press 165 lb × 5",
    body: "Three weeks of progress on this lift. Next target: 170 × 5 in 2 weeks.",
    action: "VIEW HISTORY",
  },

  // Yesterday
  {
    when: "YESTERDAY", time: "8:14 PM", tone: "warn", group: "Plan",
    title: "Coach review · Tier 2 due",
    body: "9 days since your last weekly review. Recommended before Saturday's long run.",
    action: "REVIEW NOW",
  },
  {
    when: "YESTERDAY", time: "2:18 PM", tone: "warn", group: "Exercises",
    title: "Overhead press plateau",
    body: "6 sessions without progress at 110 lb. Consider a 10% deload to break through.",
    action: "DELOAD",
  },
  {
    when: "YESTERDAY", time: "10:42 AM", tone: "info", group: "Provider",
    title: "Wahoo synced · 86 sessions imported",
    body: "Backfill complete. Wahoo will pull new sessions automatically going forward.",
    action: null,
  },

  // This week
  {
    when: "THIS WEEK", time: "Mon · 6:08 AM", tone: "good", group: "Sessions",
    title: "Workout auto-completed",
    body: "Strava saw your Monday easy aerobic and matched it to the scheduled session.",
    action: null,
  },
  {
    when: "THIS WEEK", time: "Sun · 11:24 PM", tone: "info", group: "System",
    title: "Engine v3.2 deployed",
    body: "Updated periodization model. Your plan was diffed against v3.1 — no changes needed.",
    action: "SEE CHANGES",
  },
  {
    when: "THIS WEEK", time: "Fri · 3:14 PM", tone: "accent", group: "Plan",
    title: "Boston Marathon is 22 weeks out",
    body: "You're entering the Build phase. Expect threshold sessions to come up, intensity to climb 5–8%/week.",
    action: null,
  },
];

const FILTERS = ["All", "Plan", "Sessions", "Provider", "Exercises", "System"];

const ICON_FOR_TONE = (tone) => {
  switch (tone) {
    case "accent": return I.bolt;
    case "good":   return I.check;
    case "warn":   return I.bell;
    case "info":   return I.link;
    default:       return I.bell;
  }
};

// ═══════════════════════════════════════════════════════════════════
// 24. DESKTOP — Notifications full page
// ═══════════════════════════════════════════════════════════════════
const ScreenNotifications = () => {
  // Group by date label
  const byGroup = {};
  NOTIFICATIONS.forEach(n => {
    if (!byGroup[n.when]) byGroup[n.when] = [];
    byGroup[n.when].push(n);
  });
  const unreadCount = NOTIFICATIONS.filter(n => n.unread).length;

  return (
    <div className="screen">
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <Sidebar active="home" />
        <div className="page">
          <TopBar crumbs={["Notifications"]} actions={
            <>
              <div className="btn btn-ghost"><Ic d={I.check} size={12} sw={2.2} /> Mark all read</div>
              <div className="btn btn-ghost"><Ic d={I.gear} size={12} /> Settings</div>
            </>
          } />
          <div className="page-body">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 22 }}>
              <div>
                <Eyebrow>Activity feed · {NOTIFICATIONS.length} items</Eyebrow>
                <h1 className="page-title" style={{ marginTop: 8 }}>What's happened.</h1>
                <div className="page-sub">Plan updates, provider syncs, coach reminders, achievements. {unreadCount > 0 ? `${unreadCount} unread.` : "All caught up."}</div>
              </div>
              <Pill tone="accent">● {unreadCount} UNREAD</Pill>
            </div>

            {/* Filters */}
            <div style={{ display: "flex", gap: 6, marginBottom: 18 }}>
              {FILTERS.map((f, i) => (
                <Pill key={i} tone={i === 0 ? "accent" : null}>{f.toUpperCase()}{i === 0 ? ` · ${NOTIFICATIONS.length}` : ""}</Pill>
              ))}
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 22 }}>
              <div>
                {/* Feed */}
                {Object.entries(byGroup).map(([group, items]) => (
                  <div key={group} style={{ marginBottom: 22 }}>
                    <Eyebrow>{group}</Eyebrow>
                    <div className="card" style={{ marginTop: 10, padding: 0 }}>
                      {items.map((n, i, a) => {
                        const toneColor = n.tone === "accent" ? "var(--accent)"
                                      : n.tone === "good"   ? "var(--good)"
                                      : n.tone === "warn"   ? "var(--warn)"
                                      :                       "var(--info)";
                        return (
                          <div key={i} style={{
                            padding: "16px 18px",
                            borderBottom: i < a.length - 1 ? "1px solid var(--hairline-2)" : "none",
                            display: "grid", gridTemplateColumns: "36px 1fr auto", gap: 14,
                            alignItems: "flex-start",
                            background: n.unread ? "color-mix(in oklab, " + toneColor + " 5%, transparent)" : "transparent",
                            position: "relative",
                          }}>
                            {n.unread && <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 2, background: toneColor }} />}
                            <div style={{
                              width: 32, height: 32, borderRadius: "50%",
                              background: "color-mix(in oklab, " + toneColor + " 18%, transparent)",
                              color: toneColor, display: "grid", placeItems: "center",
                            }}>
                              <Ic d={ICON_FOR_TONE(n.tone)} size={14} />
                            </div>
                            <div style={{ minWidth: 0 }}>
                              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                                <span style={{ fontWeight: 600, fontSize: 14 }}>{n.title}</span>
                                <span className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--fg-4)", textTransform: "uppercase" }}>{n.group}</span>
                              </div>
                              <div style={{ fontSize: 13, color: "var(--fg-2)", marginTop: 6, lineHeight: 1.5 }}>{n.body}</div>
                              <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 10 }}>
                                {n.action && (
                                  <div className={"btn btn-sm " + (n.actionTone === "primary" ? "btn-primary" : n.actionTone === "warn" ? "btn-ghost" : "btn-ghost")}>
                                    {n.action} <Ic d={I.arrow} size={10} sw={2} />
                                  </div>
                                )}
                                <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em" }}>{n.time}</span>
                              </div>
                            </div>
                            <Ic d={I.more} size={14} />
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>

              {/* Right rail — settings shortcut */}
              <div className="stack">
                <div className="card" style={{ padding: 18 }}>
                  <Eyebrow>Notification settings</Eyebrow>
                  <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 10 }}>
                    {[
                      ["Plan refreshes", true],
                      ["Provider syncs", true],
                      ["Coach reminders", true],
                      ["Plateau alerts", true],
                      ["Achievements / PRs", true],
                      ["System updates", false],
                    ].map(([k, on], i) => (
                      <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <div style={{ fontSize: 13 }}>{k}</div>
                        <div style={{
                          width: 32, height: 18, borderRadius: 999,
                          background: on ? "var(--accent)" : "var(--bg-3)",
                          position: "relative", flexShrink: 0,
                        }}>
                          <div style={{
                            position: "absolute", top: 2, left: on ? 16 : 2,
                            width: 14, height: 14, borderRadius: "50%",
                            background: on ? "var(--ink)" : "var(--fg-3)",
                            transition: "left 0.15s ease",
                          }} />
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="btn btn-text btn-sm" style={{ marginTop: 14, padding: 0, color: "var(--accent)" }}>OPEN FULL SETTINGS →</div>
                </div>

                <div className="card" style={{ padding: 18 }}>
                  <Eyebrow>Delivery</Eyebrow>
                  <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 8, fontSize: 12, color: "var(--fg-2)" }}>
                    <div className="kv"><span className="k">In-app</span><span className="v">All</span></div>
                    <div className="kv"><span className="k">Email</span><span className="v">Daily digest</span></div>
                    <div className="kv"><span className="k">Push</span><span className="v">Plan + coach only</span></div>
                  </div>
                </div>

                <div className="card-flush" style={{ padding: 14 }}>
                  <Eyebrow>Quiet hours</Eyebrow>
                  <div style={{ display: "flex", alignItems: "baseline", gap: 6, marginTop: 6 }}>
                    <span className="num" style={{ fontSize: 18, fontWeight: 700 }}>10pm – 6am</span>
                  </div>
                  <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em", marginTop: 4, textTransform: "uppercase" }}>NO PUSH IN THIS WINDOW</div>
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
// 24b. DESKTOP — Notifications panel (top-bar dropdown)
// ═══════════════════════════════════════════════════════════════════
const ScreenNotificationsPanel = () => {
  const recent = NOTIFICATIONS.slice(0, 6);
  return (
    <div className="screen">
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <Sidebar active="home" />
        <div className="page">
          <TopBar crumbs={["Today", "Wed · May 27"]} actions={
            <>
              <div className="btn btn-icon" style={{ position: "relative" }}>
                <Ic d={I.bell} size={14} />
                <div style={{ position: "absolute", top: 4, right: 4, width: 8, height: 8, borderRadius: "50%", background: "var(--accent)" }} />
              </div>
            </>
          } />

          {/* Ghost body */}
          <div className="page-body" style={{ filter: "blur(1px)", opacity: 0.45, position: "relative" }}>
            <Eyebrow>Dashboard · Wed May 27</Eyebrow>
            <h1 className="page-title" style={{ marginTop: 8 }}>Morning, Andrew.</h1>
            <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 18, marginTop: 22 }}>
              <div className="card" style={{ height: 260 }} />
              <div className="stack">
                <div className="card" style={{ height: 120 }} />
                <div className="card" style={{ height: 120 }} />
              </div>
            </div>
          </div>

          {/* Floating panel */}
          <div style={{
            position: "absolute",
            top: 64,
            right: 28,
            width: 440,
            background: "var(--bg-2)",
            border: "1px solid var(--hairline)",
            borderRadius: 8,
            boxShadow: "0 24px 60px -8px rgba(0,0,0,0.5)",
            overflow: "hidden",
            zIndex: 20,
          }}>
            <div style={{ padding: "14px 18px", borderBottom: "1px solid var(--hairline-2)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <Eyebrow accent>● 3 UNREAD · 10 TOTAL</Eyebrow>
                <div style={{ fontSize: 16, fontWeight: 700, marginTop: 4 }}>Notifications</div>
              </div>
              <div style={{ display: "flex", gap: 6 }}>
                <div className="btn btn-text btn-sm" style={{ color: "var(--fg-3)", fontSize: 10 }}>MARK ALL READ</div>
              </div>
            </div>

            <div style={{ maxHeight: 460, overflow: "auto" }}>
              {recent.map((n, i, a) => {
                const toneColor = n.tone === "accent" ? "var(--accent)"
                              : n.tone === "good"   ? "var(--good)"
                              : n.tone === "warn"   ? "var(--warn)"
                              :                       "var(--info)";
                return (
                  <div key={i} style={{
                    padding: "12px 18px",
                    borderBottom: i < a.length - 1 ? "1px solid var(--hairline-2)" : "none",
                    display: "grid", gridTemplateColumns: "28px 1fr auto", gap: 12,
                    background: n.unread ? "color-mix(in oklab, " + toneColor + " 5%, transparent)" : "transparent",
                    position: "relative",
                  }}>
                    {n.unread && <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 2, background: toneColor }} />}
                    <div style={{
                      width: 26, height: 26, borderRadius: "50%",
                      background: "color-mix(in oklab, " + toneColor + " 18%, transparent)",
                      color: toneColor, display: "grid", placeItems: "center",
                    }}>
                      <Ic d={ICON_FOR_TONE(n.tone)} size={12} />
                    </div>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontWeight: 600, fontSize: 13, lineHeight: 1.3 }}>{n.title}</div>
                      <div style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 4, lineHeight: 1.45 }}>{n.body}</div>
                      {n.action && (
                        <div className="mono accent" style={{ marginTop: 6, fontSize: 10, color: "var(--accent)", letterSpacing: "0.14em", fontWeight: 600 }}>{n.action} →</div>
                      )}
                    </div>
                    <span className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.14em", whiteSpace: "nowrap" }}>{n.time.replace(" AM","A").replace(" PM","P")}</span>
                  </div>
                );
              })}
            </div>

            <div style={{ padding: "10px 18px", borderTop: "1px solid var(--hairline-2)", display: "flex", justifyContent: "center", background: "var(--bg)" }}>
              <span className="mono" style={{ fontSize: 10, color: "var(--accent)", letterSpacing: "0.18em" }}>VIEW ALL ACTIVITY →</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════
// M21. MOBILE — Notifications feed
// ═══════════════════════════════════════════════════════════════════
const MobileNotifications = () => {
  const byGroup = {};
  NOTIFICATIONS.forEach(n => {
    if (!byGroup[n.when]) byGroup[n.when] = [];
    byGroup[n.when].push(n);
  });
  return (
    <div className="screen">
      <StatusBar />
      <AppBar
        title="Notifications"
        left={<Ic d={I.chevL} size={22} />}
        right={<div className="mono" style={{ fontSize: 10, letterSpacing: "0.18em", color: "var(--accent)" }}>READ ALL</div>}
      />

      <div style={{ padding: "10px 16px", borderBottom: "1px solid var(--hairline-2)", display: "flex", gap: 6, overflowX: "auto" }}>
        {FILTERS.map((f, i) => (
          <Pill key={i} tone={i === 0 ? "accent" : null}>{f.toUpperCase()}</Pill>
        ))}
      </div>

      <div style={{ flex: 1, overflow: "auto" }}>
        {Object.entries(byGroup).map(([group, items]) => (
          <div key={group}>
            <div style={{ padding: "12px 16px 6px", background: "var(--bg)" }}>
              <Eyebrow>{group}</Eyebrow>
            </div>
            {items.map((n, i) => {
              const toneColor = n.tone === "accent" ? "var(--accent)"
                            : n.tone === "good"   ? "var(--good)"
                            : n.tone === "warn"   ? "var(--warn)"
                            :                       "var(--info)";
              return (
                <div key={i} style={{
                  padding: "14px 16px",
                  borderBottom: "1px solid var(--hairline-2)",
                  display: "grid", gridTemplateColumns: "28px 1fr", gap: 12,
                  alignItems: "flex-start",
                  background: n.unread ? "color-mix(in oklab, " + toneColor + " 5%, transparent)" : "transparent",
                  position: "relative",
                }}>
                  {n.unread && <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 2, background: toneColor }} />}
                  <div style={{
                    width: 26, height: 26, borderRadius: "50%",
                    background: "color-mix(in oklab, " + toneColor + " 18%, transparent)",
                    color: toneColor, display: "grid", placeItems: "center",
                  }}>
                    <Ic d={ICON_FOR_TONE(n.tone)} size={12} />
                  </div>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                      <span style={{ fontWeight: 600, fontSize: 13 }}>{n.title}</span>
                    </div>
                    <div style={{ fontSize: 12, color: "var(--fg-2)", marginTop: 4, lineHeight: 1.45 }}>{n.body}</div>
                    <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 8 }}>
                      {n.action && (
                        <span className="mono" style={{ fontSize: 10, color: toneColor, letterSpacing: "0.14em", fontWeight: 600 }}>{n.action} →</span>
                      )}
                      <span className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.14em", marginLeft: n.action ? "auto" : 0 }}>{n.time}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ))}
      </div>

      <TabBar active="home" />
    </div>
  );
};

Object.assign(window, {
  ScreenNotifications, ScreenNotificationsPanel, MobileNotifications,
});
