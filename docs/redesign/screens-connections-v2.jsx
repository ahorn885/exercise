/* AIDSTATION redesign — Connections v2 (unified hub)
   Consolidates: sidebar Connections + FIT debug (formerly "Garmin dashboard")
   + Wellness FIT import + Profile › Connections tab.

   One page, three tabs: Sources · Files · Preferences.
   The "FIT debug" inspector becomes a side panel inside the Files tab
   instead of a standalone destination. Single .FIT drop zone sniffs sport;
   no more separate activity vs wellness uploads. */

// ─── Shared bits ─────────────────────────────────────────────────
const HubTabs = ({ active }) => (
  <div role="tablist" aria-label="Connections sections" style={{ display: "flex", gap: 0, marginBottom: 22, borderBottom: "1px solid var(--hairline-2)" }}>
    {[
      ["sources", "Sources",     "providers + upload"],
      ["files",   "Files",       "import history"],
      ["prefs",   "Preferences", "rules + windows"],
    ].map(([key, label, sub]) => {
      const on = key === active;
      return (
        <div key={key} role="tab" aria-selected={on ? "true" : "false"} tabIndex={on ? 0 : -1} style={{
          padding: "10px 18px",
          borderBottom: "2px solid " + (on ? "var(--accent)" : "transparent"),
          marginBottom: -1,
          cursor: "pointer",
          display: "flex",
          alignItems: "baseline",
          gap: 10,
        }}>
          <span style={{ fontSize: 14, fontWeight: on ? 600 : 500, color: on ? "var(--fg)" : "var(--fg-3)" }}>{label}</span>
          <span className="mono" style={{ fontSize: 9, letterSpacing: "0.16em", color: "var(--fg-4)", textTransform: "uppercase" }}>{sub}</span>
        </div>
      );
    })}
    <div style={{ flex: 1 }} />
    <div className="mono" style={{ fontSize: 10, letterSpacing: "0.16em", color: "var(--fg-3)", padding: "12px 0", textTransform: "uppercase" }}>
      Last sync · 6 min ago
    </div>
  </div>
);

const HubHeader = ({ sub, title, lede }) => (
  <div style={{ marginBottom: 18 }}>
    <Eyebrow>{sub}</Eyebrow>
    <h1 className="page-title" style={{ marginTop: 8 }}>{title}</h1>
    <div className="page-sub">{lede}</div>
  </div>
);

const PROVIDERS = [
  { name: "Strava",        connected: true,  since: "May 12, 2026", lastSync: "6 min ago",  scopes: ["activity", "wellness"],   pulls: "412 sessions",     priority: 1 },
  { name: "Wahoo",         connected: true,  since: "May 18, 2026", lastSync: "2 hr ago",   scopes: ["activity", "body", "sleep"], pulls: "86 sessions",   priority: 2 },
  { name: "Whoop",         scopes: ["workouts", "sleep", "recovery"] },
  { name: "TrainingPeaks", scopes: ["workouts", "planned"] },
  { name: "Zwift",         scopes: ["indoor activities"] },
  { name: "Ride With GPS", scopes: ["routes"] },
  { name: "Garmin",        paused: true, reason: "Garmin Connect API access closed — upload .FIT files manually instead" },
];

const FILES = [
  { id: 1, name: "activity_2026-05-22T1844.fit", sport: "running",   src: "manual",      device: "Wahoo ELEMNT Roam 2", when: "6 min ago",  dur: "1:18:42", dist: "9.42 mi",  hr: "152 / 178", warn: 1,  status: "ready",     selected: true  },
  { id: 2, name: "activity_2026-05-22T0612.fit", sport: "cycling",   src: "Strava sync", device: "Wahoo BOLT 2",        when: "yesterday",  dur: "0:52:11", dist: "18.6 mi",  hr: "141 / 168", warn: 0,  status: "imported" },
  { id: 3, name: "wellness_2026-05-21.fit",      sport: "wellness",  src: "manual",      device: "COROS APEX 2 Pro",    when: "yesterday",  dur: "24 hr",   dist: "—",        hr: "rest 48",   warn: 0,  status: "imported" },
  { id: 4, name: "activity_2026-05-20T1530.fit", sport: "strength",  src: "manual",      device: "Apple Watch S10",     when: "2 days ago", dur: "0:44:08", dist: "—",        hr: "118 / 152", warn: 2,  status: "imported" },
  { id: 5, name: "activity_2026-05-19T0700.fit", sport: "running",   src: "Strava sync", device: "iPhone 16 Pro",       when: "3 days ago", dur: "0:38:24", dist: "4.41 mi",  hr: "148 / 161", warn: 0,  status: "imported" },
  { id: 6, name: "wellness_2026-05-19.fit",      sport: "wellness",  src: "manual",      device: "Wahoo TICKR FIT",     when: "3 days ago", dur: "24 hr",   dist: "—",        hr: "rest 50",   warn: 0,  status: "imported" },
  { id: 7, name: "activity_2026-05-17T1730.fit", sport: "cycling",   src: "manual",      device: "Wahoo BOLT 2",        when: "5 days ago", dur: "1:42:08", dist: "26.1 mi",  hr: "138 / 172", warn: 0,  status: "imported" },
  { id: 8, name: "activity_2026-05-16T0830.fit", sport: "running",   src: "Strava sync", device: "Garmin Forerunner 965", when: "6 days ago", dur: "1:02:14", dist: "7.8 mi", hr: "146 / 176", warn: 0,  status: "imported" },
];

const SportGlyph = ({ sport, size = 14 }) => {
  const map = {
    running:  "R",
    cycling:  "C",
    strength: "S",
    wellness: "W",
  };
  return (
    <div style={{
      width: size + 8, height: size + 8, borderRadius: 3,
      background: sport === "wellness" ? "color-mix(in oklab, var(--accent) 24%, var(--bg-2))" : "var(--bg-3)",
      color: sport === "wellness" ? "var(--accent)" : "var(--fg-2)",
      display: "grid", placeItems: "center",
      fontFamily: "var(--mono)", fontWeight: 700, fontSize: size - 3,
      flexShrink: 0,
    }}>{map[sport] || "·"}</div>
  );
};

const ProviderRow = ({ p }) => (
  <div className="card" style={{ padding: 14, display: "flex", gap: 14, alignItems: "center", opacity: p.paused ? 0.6 : 1 }}>
    <div style={{ width: 40, height: 40, borderRadius: 4, background: p.connected ? "var(--accent)" : "var(--bg-3)", color: p.connected ? "var(--ink)" : "var(--fg-2)", display: "grid", placeItems: "center", flexShrink: 0, fontFamily: "var(--mono)", fontWeight: 700, fontSize: 14 }}>
      {p.name[0]}
    </div>
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <span style={{ fontWeight: 600, fontSize: 14 }}>{p.name}</span>
        {p.connected && <Pill tone="good">✓ CONNECTED</Pill>}
        {p.paused && <Pill tone="warn">PAUSED</Pill>}
        {p.connected && p.priority === 1 && <Pill>PRIMARY</Pill>}
      </div>
      {p.connected ? (
        <div className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--fg-3)", marginTop: 5, textTransform: "uppercase" }}>
          {p.scopes.join(" · ")} · synced {p.lastSync.toUpperCase()} · {p.pulls.toUpperCase()}
        </div>
      ) : p.paused ? (
        <div style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 5 }}>{p.reason}</div>
      ) : (
        <div className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--fg-3)", marginTop: 5, textTransform: "uppercase" }}>
          Scopes · {p.scopes.join(" · ")}
        </div>
      )}
    </div>
    <div style={{ display: "flex", gap: 6 }}>
      {p.connected ? (
        <>
          <div className="btn btn-ghost btn-sm">Settings</div>
          <div className="btn btn-text btn-sm" style={{ color: "var(--bad)" }}>REVOKE</div>
        </>
      ) : p.paused ? (
        <div className="btn btn-ghost btn-sm">View status</div>
      ) : (
        <div className="btn btn-primary btn-sm">CONNECT</div>
      )}
    </div>
  </div>
);

// ─── Shared drop zone ─────────────────────────────────────────────
const DropZone = ({ compact }) => (
  <div style={{
    padding: compact ? 20 : 28,
    border: "1px dashed color-mix(in oklab, var(--accent) 55%, var(--hairline))",
    borderRadius: 6,
    background: "color-mix(in oklab, var(--accent) 5%, transparent)",
    textAlign: "center",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 8,
  }}>
    <div style={{ width: 40, height: 40, borderRadius: 999, background: "color-mix(in oklab, var(--accent) 18%, transparent)", display: "grid", placeItems: "center" }}>
      <Ic d={I.upload} size={18} />
    </div>
    <div style={{ fontSize: 15, fontWeight: 600 }}>Drop .FIT files here</div>
    <div style={{ fontSize: 12, color: "var(--fg-3)", maxWidth: 380, lineHeight: 1.45 }}>
      Any device that exports .FIT — Garmin, Wahoo, COROS, Polar, Suunto, Apple Watch.
      We sniff sport &amp; type automatically; nothing else to pick.
    </div>
    <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
      <div className="btn btn-primary btn-sm"><Ic d={I.upload} size={11} /> Browse files</div>
      <div className="btn btn-ghost btn-sm">Paste JSON instead</div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// 10B-A. CONNECTIONS · SOURCES tab (default)
// ═══════════════════════════════════════════════════════════════════
const ScreenConnHubSources = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="link" />
      <div className="page">
        <TopBar crumbs={["Connections"]} actions={
          <>
            <div className="btn btn-ghost btn-sm"><Ic d={I.bolt} size={11} /> Sync all</div>
            <div className="btn btn-primary"><Ic d={I.upload} size={12} /> Upload .FIT</div>
          </>
        } />
        <div className="page-body">
          <HubHeader
            sub="Connections · everything that feeds the app"
            title="Bring data in."
            lede="One place for every source — auto-sync providers, manual .FIT uploads, and the rules that decide which wins when they overlap."
          />

          <HubTabs active="sources" />

          {/* Drop zone — first because manual is the most-used path */}
          <div style={{ marginBottom: 22 }}>
            <DropZone />
          </div>

          {/* Providers */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 10 }}>
            <Eyebrow>Auto-sync providers · 2 of 7 connected</Eyebrow>
            <span className="mono" style={{ fontSize: 9, letterSpacing: "0.16em", color: "var(--fg-3)", textTransform: "uppercase" }}>
              Strava is primary · drag to reorder
            </span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 22 }}>
            {PROVIDERS.map((p, i) => <ProviderRow key={i} p={p} />)}
          </div>

          {/* Bottom: at-a-glance stats — replaces the awkward 7-day mini list */}
          <Eyebrow>Last 30 days · all sources combined</Eyebrow>
          <div className="row" style={{ marginTop: 12 }}>
            {[
              ["Sessions in",      "47"],
              ["Auto · via providers", "31"],
              ["Manual · uploads", "12"],
              ["Duplicates merged", "4"],
              ["Rejected · parse fail", "0"],
            ].map(([k, v], i) => (
              <div key={i} className="stat-card col" style={{ padding: 14 }}>
                <div className="k" style={{ fontSize: 9 }}>{k}</div>
                <div className="v num" style={{ fontSize: 22 }}>{v}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// 10B-B. CONNECTIONS · FILES tab (with inline inspector)
// Replaces standalone FIT debug — no separate destination.
// ═══════════════════════════════════════════════════════════════════
const ScreenConnHubFiles = () => {
  const sel = FILES.find((f) => f.selected);
  return (
    <div className="screen">
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <Sidebar active="link" />
        <div className="page">
          <TopBar crumbs={["Connections", "Files"]} actions={
            <>
              <div className="btn btn-ghost btn-sm"><Ic d={I.download} size={11} /> Export CSV</div>
              <div className="btn btn-primary"><Ic d={I.upload} size={12} /> Upload .FIT</div>
            </>
          } />
          <div className="page-body">
            <HubHeader
              sub="Connections · file history + inspector"
              title="Files we've seen."
              lede="Every .FIT we've ingested — manual or via a provider. Click any row to inspect what we parsed before it lands in your log."
            />

            <HubTabs active="files" />

            {/* Toolbar + selection-aware split */}
            <div className="card" style={{ padding: "10px 14px", marginBottom: 14, display: "flex", gap: 12, alignItems: "center" }}>
              <Ic d={I.search} size={14} />
              <span style={{ flex: 1, color: "var(--fg-3)", fontSize: 13 }}>Filter by filename, sport, device…</span>
              {["All", "Running", "Cycling", "Strength", "Wellness", "Manual", "Auto"].map((f, i) => (
                <Pill key={i} tone={i === 0 ? "accent" : null}>{f.toUpperCase()}</Pill>
              ))}
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1.15fr 1fr", gap: 14 }}>
              {/* LEFT — file list */}
              <div className="card" style={{ padding: 0 }}>
                <div style={{ padding: "10px 14px", borderBottom: "1px solid var(--hairline-2)", display: "flex", justifyContent: "space-between" }}>
                  <Eyebrow>Files · 312 total</Eyebrow>
                  <span className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--fg-3)" }}>NEWEST FIRST</span>
                </div>
                <div>
                  {FILES.map((f, i) => (
                    <div key={f.id} style={{
                      display: "grid",
                      gridTemplateColumns: "auto 1fr auto",
                      gap: 12,
                      alignItems: "center",
                      padding: "12px 14px",
                      borderBottom: i < FILES.length - 1 ? "1px solid var(--hairline-2)" : "none",
                      background: f.selected ? "color-mix(in oklab, var(--accent) 10%, transparent)" : "transparent",
                      borderLeft: f.selected ? "2px solid var(--accent)" : "2px solid transparent",
                      cursor: "pointer",
                    }}>
                      <SportGlyph sport={f.sport} />
                      <div style={{ minWidth: 0 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <span className="mono" style={{ fontSize: 11, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{f.name}</span>
                          {f.status === "ready" && <Pill tone="accent">REVIEW</Pill>}
                          {f.warn > 0 && <Pill tone="warn">{f.warn} ⚠</Pill>}
                        </div>
                        <div className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--fg-3)", marginTop: 4, textTransform: "uppercase" }}>
                          {f.src} · {f.device} · {f.dur} · {f.dist !== "—" ? f.dist : f.hr}
                        </div>
                      </div>
                      <div className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--fg-3)", textAlign: "right", whiteSpace: "nowrap", textTransform: "uppercase" }}>
                        {f.when}
                      </div>
                    </div>
                  ))}
                </div>
                <div style={{ padding: "10px 14px", borderTop: "1px solid var(--hairline-2)", display: "flex", justifyContent: "space-between" }}>
                  <span className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--fg-3)" }}>SHOWING 8 OF 312</span>
                  <span className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--accent)" }}>LOAD MORE →</span>
                </div>
              </div>

              {/* RIGHT — inspector panel for selected file */}
              <div className="card" style={{ padding: 0, alignSelf: "start", position: "sticky", top: 0 }}>
                <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--hairline-2)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <Eyebrow accent>● INSPECTOR · NEEDS REVIEW</Eyebrow>
                    <div className="mono" style={{ fontSize: 12, fontWeight: 600, marginTop: 4 }}>{sel.name}</div>
                  </div>
                  <div style={{ display: "flex", gap: 6 }}>
                    <div className="btn btn-ghost btn-sm">Discard</div>
                    <div className="btn btn-primary btn-sm"><Ic d={I.check} size={11} sw={2.2} /> Import</div>
                  </div>
                </div>

                {/* Top stats */}
                <div style={{ padding: 14, borderBottom: "1px solid var(--hairline-2)" }}>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8 }}>
                    {[
                      ["Sport",    "trail run"],
                      ["Duration", "1:18:42"],
                      ["Distance", "9.42 mi"],
                      ["Calories", "924"],
                      ["Avg HR",   "152 bpm"],
                      ["Max HR",   "178 bpm"],
                      ["Elev",     "412 ft"],
                      ["Cadence",  "168 spm"],
                    ].map(([k, v], i) => (
                      <div key={i} style={{ padding: 8, background: "var(--bg-2)", borderRadius: 3 }}>
                        <div className="mono" style={{ fontSize: 8, letterSpacing: "0.18em", color: "var(--fg-3)", textTransform: "uppercase" }}>{k}</div>
                        <div className="num" style={{ fontWeight: 600, fontSize: 14, marginTop: 2 }}>{v}</div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Record stream sample */}
                <div style={{ padding: "10px 16px", borderBottom: "1px solid var(--hairline-2)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <Eyebrow>Record stream · 4,725 rows</Eyebrow>
                    <span className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--fg-3)" }}>SAMPLED EVERY 5S</span>
                  </div>
                </div>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11, fontFamily: "var(--mono)" }}>
                  <thead>
                    <tr>
                      {["t", "hr", "cad", "m/s", "alt"].map((h, i) => (
                        <th key={i} style={{ padding: "6px 14px", textAlign: i === 0 ? "left" : "right", fontSize: 8, letterSpacing: "0.16em", textTransform: "uppercase", color: "var(--fg-3)", fontWeight: 500, borderBottom: "1px solid var(--hairline-2)" }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {Array.from({ length: 8 }).map((_, i) => {
                      const ts = `18:44:${(i * 5).toString().padStart(2, "0")}`;
                      const hr = 122 + Math.floor(Math.sin(i * 0.5) * 12 + i * 1.2);
                      const cad = 168 + Math.floor(Math.cos(i * 0.4) * 4);
                      const spd = (3.42 + Math.sin(i * 0.3) * 0.18).toFixed(2);
                      const alt = (124.5 + Math.sin(i * 0.6) * 3).toFixed(1);
                      return (
                        <tr key={i} style={{ borderBottom: i < 7 ? "1px solid var(--hairline-2)" : "none" }}>
                          <td style={{ padding: "5px 14px", color: "var(--fg-3)" }}>{ts}</td>
                          <td style={{ padding: "5px 14px", textAlign: "right" }}>{hr}</td>
                          <td style={{ padding: "5px 14px", textAlign: "right" }}>{cad}</td>
                          <td style={{ padding: "5px 14px", textAlign: "right" }}>{spd}</td>
                          <td style={{ padding: "5px 14px", textAlign: "right" }}>{alt}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>

                {/* Footer · file meta + warnings */}
                <div style={{ padding: 14, borderTop: "1px solid var(--hairline-2)", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  <div>
                    <Eyebrow>Device</Eyebrow>
                    <div className="mono" style={{ fontSize: 10, color: "var(--fg-2)", lineHeight: 1.75, marginTop: 6 }}>
                      <div>wahoo · elemnt_roam_2</div>
                      <div>sw v14.2 · crc <span style={{ color: "var(--good)" }}>valid</span></div>
                      <div>487,294 bytes · 4,725 records</div>
                    </div>
                  </div>
                  <div style={{ padding: 10, background: "color-mix(in oklab, var(--warn) 10%, transparent)", border: "1px solid color-mix(in oklab, var(--warn) 30%, transparent)", borderRadius: 4 }}>
                    <Eyebrow>1 warning</Eyebrow>
                    <div style={{ fontSize: 11, color: "var(--fg-2)", lineHeight: 1.45, marginTop: 5 }}>
                      <b>Power data missing.</b> Source had no power_w field — pace/HR-only. Fine for trail running.
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
};

// ═══════════════════════════════════════════════════════════════════
// 10B-C. CONNECTIONS · PREFERENCES tab
// Replaces profile › connections tab (deep-links into here).
// ═══════════════════════════════════════════════════════════════════
const ConnToggle = ({ on }) => (
  <div style={{ width: 30, height: 16, borderRadius: 999, background: on ? "var(--accent)" : "var(--bg-3)", position: "relative", flexShrink: 0 }}>
    <div style={{ width: 12, height: 12, borderRadius: 999, background: "var(--paper)", position: "absolute", top: 2, left: on ? 16 : 2 }}></div>
  </div>
);

const PrefRow = ({ label, sub, control }) => (
  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 0", borderBottom: "1px solid var(--hairline-2)", gap: 20 }}>
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{ fontSize: 14, fontWeight: 500 }}>{label}</div>
      <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 3, lineHeight: 1.4 }}>{sub}</div>
    </div>
    <div>{control}</div>
  </div>
);

const ScreenConnHubPrefs = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="link" />
      <div className="page">
        <TopBar crumbs={["Connections", "Preferences"]} actions={
          <div className="btn btn-primary btn-sm"><Ic d={I.check} size={11} sw={2.2} /> Save changes</div>
        } />
        <div className="page-body">
          <HubHeader
            sub="Connections · sync rules"
            title="How data gets in."
            lede="Tie-breakers, time windows, and what to do when the same workout shows up twice. These rules used to live on the profile page."
          />

          <HubTabs active="prefs" />

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 22 }}>
            {/* LEFT column */}
            <div className="stack">
              <div className="card" style={{ padding: 22 }}>
                <Eyebrow>Tie-breakers · when two sources have the same workout</Eyebrow>
                <div style={{ marginTop: 4 }}>
                  <PrefRow
                    label="Trust order"
                    sub="Same workout from multiple sources? Higher in list wins."
                    control={
                      <div style={{ display: "flex", flexDirection: "column", gap: 4, fontFamily: "var(--mono)", fontSize: 10, color: "var(--fg-2)", textAlign: "right", letterSpacing: "0.14em" }}>
                        <div>1 · MANUAL UPLOAD</div>
                        <div>2 · STRAVA <span style={{ color: "var(--fg-3)" }}>(primary)</span></div>
                        <div>3 · WAHOO</div>
                      </div>
                    }
                  />
                  <PrefRow
                    label="Dedupe window"
                    sub="Treat two activities as the same if they start within this window."
                    control={<Pill tone="solid">±3 min</Pill>}
                  />
                  <PrefRow
                    label="Auto-merge on match"
                    sub="Keep the highest-fidelity stream, discard the rest."
                    control={<ConnToggle on />}
                  />
                  <PrefRow
                    label="Notify on merge"
                    sub="Drop a note in the activity feed when we collapse duplicates."
                    control={<ConnToggle on={false} />}
                  />
                </div>
              </div>

              <div className="card" style={{ padding: 22 }}>
                <Eyebrow>Manual upload defaults</Eyebrow>
                <div style={{ marginTop: 4 }}>
                  <PrefRow
                    label="Sport detection"
                    sub="Use the .FIT sport field when present; fall back to file naming."
                    control={<ConnToggle on />}
                  />
                  <PrefRow
                    label="Time zone"
                    sub="What to apply when the file has no zone."
                    control={<Pill tone="solid">America/Denver</Pill>}
                  />
                  <PrefRow
                    label="Overwrite existing logs"
                    sub="If a manual upload conflicts with an existing entry."
                    control={<Pill tone="solid">Always ask</Pill>}
                  />
                  <PrefRow
                    label="Auto-import on drop"
                    sub="Skip the inspector for files with zero warnings."
                    control={<ConnToggle on={false} />}
                  />
                </div>
              </div>
            </div>

            {/* RIGHT column */}
            <div className="stack">
              <div className="card" style={{ padding: 22 }}>
                <Eyebrow>Pull windows · per provider</Eyebrow>
                <div style={{ marginTop: 10 }}>
                  {[
                    { p: "Strava", on: true,  win: "every 5 min · last 30 days", scopes: "activity · wellness" },
                    { p: "Wahoo",  on: true,  win: "every 30 min · last 14 days", scopes: "activity · body · sleep" },
                    { p: "Garmin", on: false, win: "paused — API access closed", scopes: "—" },
                  ].map((s, i) => (
                    <div key={i} style={{ padding: "14px 0", borderBottom: i < 2 ? "1px solid var(--hairline-2)" : "none", display: "flex", alignItems: "center", gap: 14 }}>
                      <div style={{ width: 32, height: 32, borderRadius: 4, background: s.on ? "var(--accent)" : "var(--bg-3)", color: s.on ? "var(--ink)" : "var(--fg-3)", display: "grid", placeItems: "center", fontFamily: "var(--mono)", fontWeight: 700, fontSize: 12 }}>
                        {s.p[0]}
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 14, fontWeight: 500 }}>{s.p}</div>
                        <div className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--fg-3)", marginTop: 3, textTransform: "uppercase" }}>{s.win}</div>
                      </div>
                      <ConnToggle on={s.on} />
                    </div>
                  ))}
                </div>
              </div>

              <div className="card" style={{ padding: 22 }}>
                <Eyebrow>Privacy &amp; retention</Eyebrow>
                <div style={{ marginTop: 4 }}>
                  <PrefRow
                    label="Keep raw .FIT files"
                    sub="On = we store the originals so you can re-parse later."
                    control={<ConnToggle on />}
                  />
                  <PrefRow
                    label="Share aggregate metrics with coaches"
                    sub="Coaches assigned to you see weekly load summaries only."
                    control={<ConnToggle on />}
                  />
                  <PrefRow
                    label="Retention"
                    sub="Auto-delete raw files older than this."
                    control={<Pill tone="solid">365 days</Pill>}
                  />
                </div>
              </div>

              <div style={{ padding: 14, border: "1px solid color-mix(in oklab, var(--bad) 30%, transparent)", borderRadius: 4, background: "color-mix(in oklab, var(--bad) 6%, transparent)" }}>
                <Eyebrow>Danger zone</Eyebrow>
                <div style={{ fontSize: 12, color: "var(--fg-2)", marginTop: 8, lineHeight: 1.5 }}>
                  Revoke every provider and delete all imported files. Your logs stay; only the source connections and raw files are removed.
                </div>
                <div className="btn btn-ghost btn-sm" style={{ marginTop: 12, color: "var(--bad)", borderColor: "color-mix(in oklab, var(--bad) 40%, transparent)" }}>
                  Reset all sources
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
// M10B. MOBILE · CONNECTIONS HUB (single screen, segmented tabs)
// ═══════════════════════════════════════════════════════════════════
const MobileConnHub = ({ tab = "sources" }) => (
  <div className="screen">
    <StatusBar />
    <AppBar
      title="Connections"
      left={<Ic d={I.menu} size={22} />}
      right={<Ic d={I.upload} size={20} />}
    />

    <div style={{ padding: "10px 16px 0", borderBottom: "1px solid var(--hairline-2)" }}>
      <div style={{ display: "flex", background: "var(--bg-2)", borderRadius: 999, padding: 3, marginBottom: 12 }}>
        {[["sources", "Sources"], ["files", "Files"], ["prefs", "Prefs"]].map(([k, label]) => (
          <div key={k} style={{
            flex: 1,
            textAlign: "center",
            padding: "8px 0",
            borderRadius: 999,
            background: tab === k ? "var(--bg)" : "transparent",
            fontSize: 12,
            fontWeight: tab === k ? 600 : 500,
            color: tab === k ? "var(--fg)" : "var(--fg-3)",
          }}>{label}</div>
        ))}
      </div>
    </div>

    <div style={{ flex: 1, overflow: "auto", padding: "14px 16px 84px" }}>
      {tab === "sources" && (
        <>
          {/* Drop zone */}
          <div style={{ padding: 18, border: "1px dashed color-mix(in oklab, var(--accent) 55%, var(--hairline))", borderRadius: 6, background: "color-mix(in oklab, var(--accent) 5%, transparent)", textAlign: "center", marginBottom: 18 }}>
            <Ic d={I.upload} size={18} />
            <div style={{ fontSize: 13, fontWeight: 600, marginTop: 6 }}>Drop or browse .FIT</div>
            <div style={{ fontSize: 10, color: "var(--fg-3)", marginTop: 4 }}>Any device · sport detected automatically</div>
            <div className="btn btn-primary btn-sm" style={{ marginTop: 10, display: "inline-flex" }}>Choose file</div>
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
            <Eyebrow>Auto-sync · 2 of 7</Eyebrow>
            <span className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--fg-3)" }}>STRAVA PRIMARY</span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {PROVIDERS.map((p, i) => (
              <div key={i} className="card" style={{ padding: 12, display: "flex", gap: 12, alignItems: "center", opacity: p.paused ? 0.6 : 1 }}>
                <div style={{ width: 36, height: 36, borderRadius: 4, background: p.connected ? "var(--accent)" : "var(--bg-3)", color: p.connected ? "var(--ink)" : "var(--fg-2)", display: "grid", placeItems: "center", flexShrink: 0, fontFamily: "var(--mono)", fontWeight: 700, fontSize: 14 }}>
                  {p.name[0]}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span style={{ fontWeight: 600, fontSize: 13 }}>{p.name}</span>
                    {p.connected && <Pill tone="good">✓</Pill>}
                    {p.paused && <Pill tone="warn">PAUSED</Pill>}
                  </div>
                  <div className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.14em", marginTop: 3, textTransform: "uppercase" }}>
                    {p.connected ? `synced ${p.lastSync}` : p.paused ? "api access closed" : p.scopes.join(" · ")}
                  </div>
                </div>
                {!p.connected && !p.paused && <div className="btn btn-primary btn-sm">CONNECT</div>}
                {p.connected && <Ic d={I.gear} size={14} />}
              </div>
            ))}
          </div>
        </>
      )}

      {tab === "files" && (
        <>
          <Eyebrow>Recent files · 312 total</Eyebrow>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 10 }}>
            {FILES.slice(0, 6).map((f) => (
              <div key={f.id} className="card" style={{
                padding: 12,
                display: "flex",
                gap: 10,
                alignItems: "center",
                borderLeft: f.selected ? "2px solid var(--accent)" : "2px solid transparent",
                background: f.selected ? "color-mix(in oklab, var(--accent) 8%, transparent)" : undefined,
              }}>
                <SportGlyph sport={f.sport} size={12} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span className="mono" style={{ fontSize: 11, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{f.name.replace("activity_", "").replace("wellness_", "well_")}</span>
                    {f.status === "ready" && <Pill tone="accent">REVIEW</Pill>}
                  </div>
                  <div className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--fg-3)", marginTop: 3, textTransform: "uppercase" }}>
                    {f.src} · {f.when} · {f.dur}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Inline inspector sheet for the selected file */}
          <div className="card" style={{ marginTop: 16, padding: 14, border: "1px solid color-mix(in oklab, var(--accent) 40%, transparent)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <Eyebrow accent>● INSPECTOR · NEEDS REVIEW</Eyebrow>
              <Pill tone="warn">1 ⚠</Pill>
            </div>
            <div className="mono" style={{ fontSize: 11, fontWeight: 600, marginTop: 6 }}>activity_2026-05-22T1844.fit</div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 6, marginTop: 10 }}>
              {[["DUR", "1:18:42"], ["DIST", "9.42 mi"], ["HR", "152"], ["EL", "412"]].map(([k, v], i) => (
                <div key={i} style={{ padding: 6, background: "var(--bg-2)", borderRadius: 3, textAlign: "center" }}>
                  <div className="mono" style={{ fontSize: 8, letterSpacing: "0.16em", color: "var(--fg-3)" }}>{k}</div>
                  <div className="num" style={{ fontSize: 12, fontWeight: 600, marginTop: 2 }}>{v}</div>
                </div>
              ))}
            </div>
            <div style={{ marginTop: 10, padding: 8, background: "color-mix(in oklab, var(--warn) 10%, transparent)", borderRadius: 3, fontSize: 11, color: "var(--fg-2)" }}>
              Power data missing — pace/HR-only.
            </div>
            <div style={{ display: "flex", gap: 6, marginTop: 12 }}>
              <div className="btn btn-ghost btn-sm" style={{ flex: 1, justifyContent: "center" }}>Discard</div>
              <div className="btn btn-primary btn-sm" style={{ flex: 2, justifyContent: "center" }}><Ic d={I.check} size={11} sw={2.2} /> Import</div>
            </div>
          </div>
        </>
      )}

      {tab === "prefs" && (
        <>
          <Eyebrow>Tie-breakers</Eyebrow>
          <div className="card" style={{ padding: "0 14px", marginTop: 10, marginBottom: 16 }}>
            <PrefRow label="Trust order" sub="Manual › Strava › Wahoo" control={<Ic d={I.chev_right} size={14} />} />
            <PrefRow label="Dedupe window" sub="Same activity if within ±N min." control={<Pill tone="solid">±3 min</Pill>} />
            <PrefRow label="Auto-merge" sub="Collapse duplicates automatically." control={<ConnToggle on />} />
          </div>

          <Eyebrow>Manual upload defaults</Eyebrow>
          <div className="card" style={{ padding: "0 14px", marginTop: 10, marginBottom: 16 }}>
            <PrefRow label="Time zone" sub="Applied when .FIT has none." control={<Pill tone="solid">Denver</Pill>} />
            <PrefRow label="Auto-import" sub="Skip inspector if no warnings." control={<ConnToggle on={false} />} />
          </div>

          <Eyebrow>Privacy &amp; retention</Eyebrow>
          <div className="card" style={{ padding: "0 14px", marginTop: 10 }}>
            <PrefRow label="Keep raw .FIT" sub="365 days, then auto-purge." control={<ConnToggle on />} />
            <PrefRow label="Share with coach" sub="Aggregate metrics only." control={<ConnToggle on />} />
          </div>
        </>
      )}
    </div>

    <TabBar active="me" />
  </div>
);

// Convenience wrappers for the canvas
const MobileConnHubSources = () => <MobileConnHub tab="sources" />;
const MobileConnHubFiles   = () => <MobileConnHub tab="files" />;
const MobileConnHubPrefs   = () => <MobileConnHub tab="prefs" />;

// ═══════════════════════════════════════════════════════════════════
// 10C. CONNECTIONS · EMPTY (zero providers, zero files)
// Folds in the former standalone "Connections · zero providers" empty
// state — it's just the hub's Sources tab before anything is connected.
// ═══════════════════════════════════════════════════════════════════
const ScreenConnHubEmpty = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="link" />
      <div className="page">
        <TopBar crumbs={["Connections"]} actions={
          <div className="btn btn-primary"><Ic d={I.upload} size={12} /> Upload .FIT</div>
        } />
        <div className="page-body">
          <HubHeader
            sub="Connections · nothing flowing yet"
            title="Bring data in."
            lede="No sources connected and no files uploaded. Hook up a provider to auto-sync, or drop a .FIT — both feed the same engine, and your plan adapts either way."
          />

          <HubTabs active="sources" />

          {/* Drop zone — leads, since manual works before any OAuth */}
          <div style={{ marginBottom: 22 }}>
            <DropZone />
          </div>

          {/* Providers — all disconnected (Garmin still shows paused) */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 10 }}>
            <Eyebrow accent>● RECOMMENDED · CONNECT A PROVIDER</Eyebrow>
            <span className="mono" style={{ fontSize: 9, letterSpacing: "0.16em", color: "var(--fg-3)", textTransform: "uppercase" }}>
              0 of 7 connected
            </span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 22 }}>
            {PROVIDERS.map((p, i) => (
              <ProviderRow key={i} p={p.paused ? p : { name: p.name, scopes: p.scopes }} />
            ))}
          </div>

          {/* Zero-state stat strip */}
          <Eyebrow>Last 30 days · all sources combined</Eyebrow>
          <div className="row" style={{ marginTop: 12 }}>
            {[
              ["Sessions in",      "0"],
              ["Auto · via providers", "0"],
              ["Manual · uploads", "0"],
              ["Duplicates merged", "0"],
              ["Rejected · parse fail", "0"],
            ].map(([k, v], i) => (
              <div key={i} className="stat-card col" style={{ padding: 14, opacity: 0.55 }}>
                <div className="k" style={{ fontSize: 9 }}>{k}</div>
                <div className="v num" style={{ fontSize: 22 }}>{v}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  </div>
);

const MobileConnHubEmpty = () => (
  <div className="screen">
    <StatusBar />
    <AppBar title="Connections" left={<Ic d={I.menu} size={22} />} right={<Ic d={I.upload} size={20} />} />

    <div style={{ padding: "10px 16px 0", borderBottom: "1px solid var(--hairline-2)" }}>
      <div style={{ display: "flex", background: "var(--bg-2)", borderRadius: 999, padding: 3, marginBottom: 12 }}>
        {[["sources", "Sources"], ["files", "Files"], ["prefs", "Prefs"]].map(([k, label], i) => (
          <div key={k} style={{
            flex: 1, textAlign: "center", padding: "8px 0", borderRadius: 999,
            background: i === 0 ? "var(--bg)" : "transparent",
            fontSize: 12, fontWeight: i === 0 ? 600 : 500,
            color: i === 0 ? "var(--fg)" : "var(--fg-3)",
          }}>{label}</div>
        ))}
      </div>
    </div>

    <div style={{ flex: 1, overflow: "auto", padding: "14px 16px 84px" }}>
      <div style={{ textAlign: "center", marginBottom: 16 }}>
        <Eyebrow>● NOTHING FLOWING YET</Eyebrow>
        <h2 style={{ fontSize: 21, fontWeight: 700, letterSpacing: "-0.02em", margin: "8px 0 6px" }}>Bring data in.</h2>
        <div style={{ color: "var(--fg-3)", fontSize: 12, lineHeight: 1.5 }}>
          Connect a provider or drop a .FIT. Both feed the same engine.
        </div>
      </div>

      <div style={{ padding: 18, border: "1px dashed color-mix(in oklab, var(--accent) 55%, var(--hairline))", borderRadius: 6, background: "color-mix(in oklab, var(--accent) 5%, transparent)", textAlign: "center", marginBottom: 18 }}>
        <Ic d={I.upload} size={18} />
        <div style={{ fontSize: 13, fontWeight: 600, marginTop: 6 }}>Drop or browse .FIT</div>
        <div style={{ fontSize: 10, color: "var(--fg-3)", marginTop: 4 }}>Any device · sport detected automatically</div>
        <div className="btn btn-primary btn-sm" style={{ marginTop: 10, display: "inline-flex" }}>Choose file</div>
      </div>

      <Eyebrow accent>● RECOMMENDED · CONNECT A PROVIDER</Eyebrow>
      <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 10 }}>
        {PROVIDERS.map((p, i) => (
          <div key={i} className="card" style={{ padding: 12, display: "flex", gap: 12, alignItems: "center", opacity: p.paused ? 0.6 : 1 }}>
            <div style={{ width: 36, height: 36, borderRadius: 4, background: "var(--bg-3)", color: "var(--fg-2)", display: "grid", placeItems: "center", flexShrink: 0, fontFamily: "var(--mono)", fontWeight: 700, fontSize: 14 }}>
              {p.name[0]}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ fontWeight: 600, fontSize: 13 }}>{p.name}</span>
                {p.paused && <Pill tone="warn">PAUSED</Pill>}
              </div>
              <div className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.14em", marginTop: 3, textTransform: "uppercase" }}>
                {p.paused ? "api access closed" : p.scopes.join(" · ")}
              </div>
            </div>
            {!p.paused && <div className="btn btn-primary btn-sm">CONNECT</div>}
          </div>
        ))}
      </div>
    </div>

    <TabBar active="me" />
  </div>
);

// ─── Stack helper if not already available ────────────────────────
// (relies on .stack class from existing styles; no-op fallback)

Object.assign(window, {
  ScreenConnHubSources, ScreenConnHubFiles, ScreenConnHubPrefs, ScreenConnHubEmpty,
  MobileConnHubSources, MobileConnHubFiles, MobileConnHubPrefs, MobileConnHubEmpty,
});
