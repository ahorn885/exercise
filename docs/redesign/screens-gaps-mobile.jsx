/* AIDSTATION redesign — coverage gaps · MOBILE parity
   Profile empty · Wellness FIT import · Notification settings
   Session expired · 404 · Permission denied
   Plus inline form errors and command palette for mobile (search sheet). */

const _phone = (kids) => (
  <div className="screen">
    <StatusBar />
    {kids}
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// M-G1. MOBILE PROFILE — FIRST-RUN
// ═══════════════════════════════════════════════════════════════════
const MobileProfileEmpty = () => (
  <div className="screen">
    <StatusBar />
    <AppBar title="Profile" right={<span className="mono" style={{ fontSize: 10, letterSpacing: "0.18em", color: "var(--fg-3)" }}>EDIT</span>} />
    <div style={{ flex: 1, overflow: "auto", padding: "8px 16px 16px" }}>
      <Eyebrow>● DAY 1 · 4 / 11 FIELDS</Eyebrow>
      <div style={{ fontSize: 26, fontWeight: 700, letterSpacing: "-0.02em", marginTop: 6, lineHeight: 1.15 }}>
        Hi, Andrew. Let's fill this in.
      </div>
      <div style={{ height: 4, background: "var(--bg-3)", borderRadius: 2, overflow: "hidden", marginTop: 14 }}>
        <div style={{ width: "36%", height: "100%", background: "var(--accent)" }} />
      </div>

      {/* identity */}
      <div className="card" style={{ padding: 14, marginTop: 18, display: "flex", alignItems: "center", gap: 12 }}>
        <div className="avatar lg" style={{ width: 44, height: 44 }}>AH</div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ fontSize: 15, fontWeight: 700 }}>Andrew Horn</div>
          <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.16em", marginTop: 3, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>andrew@aidstation.run · PRO · TRIAL</div>
        </div>
      </div>

      {/* next-step */}
      <div className="card" style={{ padding: 14, marginTop: 12, background: "color-mix(in oklab, var(--accent) 8%, var(--bg-2))", borderColor: "color-mix(in oklab, var(--accent) 30%, transparent)" }}>
        <Eyebrow accent>● NEXT</Eyebrow>
        <div style={{ fontSize: 15, fontWeight: 700, marginTop: 6, lineHeight: 1.25 }}>Set FTP &amp; threshold HR.</div>
        <div style={{ fontSize: 12, color: "var(--fg-2)", marginTop: 6, lineHeight: 1.5 }}>
          Anchor every cardio prescription — pull from Strava or run a 20-min test.
        </div>
        <div style={{ display: "flex", gap: 6, marginTop: 12 }}>
          <div className="btn btn-ghost btn-sm" style={{ flex: 1, justifyContent: "center" }}>PULL FROM STRAVA</div>
          <div className="btn btn-primary btn-sm" style={{ flex: 1, justifyContent: "center" }}>START TEST</div>
        </div>
      </div>

      {/* baselines */}
      <div className="card" style={{ padding: 0, marginTop: 12 }}>
        <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--hairline-2)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <Eyebrow>Baselines · 0 / 6</Eyebrow>
          <span className="mono" style={{ fontSize: 10, color: "var(--accent)", letterSpacing: "0.16em" }}>PREFILL →</span>
        </div>
        {[
          ["FTP",          "watts",  "From cycling effort"],
          ["Threshold HR", "bpm",    "From LT test"],
          ["VO₂ max",      "ml/kg",  "From provider"],
          ["Z2 pace",      "/mi",    "Auto-derived"],
          ["1RM · Squat",  "lb",     "Required for strength"],
          ["1RM · Bench",  "lb",     "Required for strength"],
        ].map(([k, u, h], i, a) => (
          <div key={k} style={{ padding: "12px 16px", borderBottom: i < a.length - 1 ? "1px solid var(--hairline-2)" : "none", display: "grid", gridTemplateColumns: "1fr auto", gap: 12, alignItems: "center" }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600 }}>{k}</div>
              <div style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 3 }}>{h}</div>
            </div>
            <div className="btn btn-ghost btn-sm"><Ic d={I.plus} size={10} sw={2.4} /> SET <span className="mono" style={{ color: "var(--fg-4)", marginLeft: 4 }}>{u}</span></div>
          </div>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 12 }}>
        <div className="card" style={{ padding: 12 }}>
          <Eyebrow>Plan</Eyebrow>
          <div style={{ fontSize: 13, fontWeight: 600, marginTop: 6 }}>No plan yet</div>
          <div className="mono" style={{ fontSize: 10, color: "var(--accent)", letterSpacing: "0.16em", marginTop: 8 }}>SET RACE →</div>
        </div>
        <div className="card" style={{ padding: 12 }}>
          <Eyebrow>Billing</Eyebrow>
          <div style={{ fontSize: 13, fontWeight: 600, marginTop: 6 }}>Trial · ends Jun 10</div>
          <div className="mono" style={{ fontSize: 10, color: "var(--accent)", letterSpacing: "0.16em", marginTop: 8 }}>MANAGE →</div>
        </div>
      </div>
    </div>
    <TabBar active="me" />
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// M-G2. MOBILE WELLNESS FIT IMPORT PREVIEW
// ═══════════════════════════════════════════════════════════════════
const MobileWellnessFitImport = () => {
  const days = [
    { d: "May 26", hrv: 72, rhr: 47, sleep: "7h 34m", ok: true },
    { d: "May 25", hrv: 68, rhr: 49, sleep: "6h 51m", ok: true },
    { d: "May 24", hrv: 81, rhr: 45, sleep: "8h 02m", ok: true },
    { d: "May 23", hrv: 70, rhr: 48, sleep: "7h 12m", ok: true },
    { d: "May 22", hrv: "—",rhr: "—",sleep: "—",      ok: false, note: "Recovery field missing — will be skipped." },
    { d: "May 21", hrv: 64, rhr: 51, sleep: "6h 28m", ok: true },
    { d: "May 20", hrv: 76, rhr: 46, sleep: "7h 49m", ok: true },
  ];
  return (
    <div className="screen">
      <StatusBar />
      <AppBar title="Import preview" left={<Ic d={I.chevL} size={22} />} right={<span className="mono" style={{ fontSize: 10, letterSpacing: "0.18em", color: "var(--accent)" }}>IMPORT</span>} />
      <div style={{ flex: 1, overflow: "auto", padding: "8px 16px 16px" }}>
        <Eyebrow>● WELLNESS · .FIT · BRAND-NEUTRAL</Eyebrow>
        <div style={{ fontSize: 22, fontWeight: 700, letterSpacing: "-0.015em", marginTop: 6, lineHeight: 1.2 }}>
          7 days · 6 parsed cleanly.
        </div>

        {/* file meta */}
        <div className="card" style={{ padding: 12, marginTop: 14, display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ width: 32, height: 32, borderRadius: 5, background: "var(--bg-3)", display: "grid", placeItems: "center" }}>
            <Ic d={I.cloud} size={16} />
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div className="mono" style={{ fontSize: 11, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>wellness_export_2026-05-27.zip</div>
            <div className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.16em", marginTop: 3 }}>● 412 KB · WAHOO BOLT</div>
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginTop: 10 }}>
          {[["Parsed","6 / 7","good"],["Warns","1","warn"],["Days","7","fg"]].map(([k,v,t]) => (
            <div key={k} className="card-flush" style={{ padding: 10, textAlign: "center" }}>
              <div className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.18em" }}>● {k.toUpperCase()}</div>
              <div className="num" style={{ fontFamily: "var(--mono)", fontSize: 16, fontWeight: 700, marginTop: 4, color: t === "good" ? "var(--good)" : t === "warn" ? "var(--warn)" : "var(--fg)" }}>{v}</div>
            </div>
          ))}
        </div>

        <Eyebrow style={{ display: "block", marginTop: 18 }}>● DAYS</Eyebrow>
        <div className="card" style={{ padding: 0, marginTop: 8 }}>
          {days.map((r, i) => (
            <div key={r.d} style={{ padding: "12px 14px", borderBottom: i < days.length - 1 ? "1px solid var(--hairline-2)" : "none", opacity: r.ok ? 1 : 0.75 }}>
              <div style={{ display: "grid", gridTemplateColumns: "auto 1fr auto", alignItems: "center", gap: 10 }}>
                <div className="mono" style={{ fontSize: 13, fontWeight: 700 }}>{r.d}</div>
                <div className="mono" style={{ fontSize: 11, color: "var(--fg-3)", letterSpacing: "0.14em" }}>HRV {r.hrv} · RHR {r.rhr} · SLP {r.sleep}</div>
                {r.ok ? <Pill tone="good">OK</Pill> : <Pill tone="warn">WARN</Pill>}
              </div>
              {r.note && <div style={{ fontSize: 11, color: "var(--warn)", marginTop: 6 }}>⚠ {r.note}</div>}
            </div>
          ))}
        </div>

        <div style={{ marginTop: 16, display: "flex", gap: 8 }}>
          <div className="btn btn-ghost" style={{ flex: 1, justifyContent: "center" }}><Ic d={I.upload} size={12} /> More</div>
          <div className="btn btn-primary" style={{ flex: 2, justifyContent: "center" }}><Ic d={I.check} size={12} sw={2.4} /> Import 6 days</div>
        </div>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════
// M-G3. MOBILE NOTIFICATION SETTINGS
// ═══════════════════════════════════════════════════════════════════
const MobileNotifSettings = () => {
  const cats = [
    ["Plan changes",    "Version writes · scope shifts.",       { app: true,  email: true,  push: true  }],
    ["Sessions",        "Tomorrow's prescription, reschedules.", { app: true, email: false, push: true }],
    ["Coach reminders", "Log nudges · weekly check-ins.",        { app: true, email: true, push: false }],
    ["Plateau alerts",  "Stalls · auto-deload offers.",          { app: true, email: true, push: true }],
    ["Achievements",    "PRs · streaks · race countdowns.",      { app: true, email: false, push: false }],
    ["System",          "Sync failures · billing · security.",   { app: true, email: true, push: false }],
  ];
  return (
    <div className="screen">
      <StatusBar />
      <AppBar title="Notifications" left={<Ic d={I.chevL} size={22} />} right={<span className="mono" style={{ fontSize: 10, letterSpacing: "0.18em", color: "var(--accent)" }}>SAVE</span>} />
      <div style={{ flex: 1, overflow: "auto", padding: "8px 16px 16px" }}>
        <Eyebrow>● CHANNELS × CATEGORIES</Eyebrow>
        <div style={{ fontSize: 22, fontWeight: 700, letterSpacing: "-0.015em", marginTop: 6, lineHeight: 1.2 }}>
          Tell us what to bother you about.
        </div>

        {/* quiet hours */}
        <div className="card" style={{ padding: 14, marginTop: 14 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Ic d={I.clock} size={16} />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 600 }}>Quiet hours</div>
              <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em", marginTop: 2 }}>22:00 → 07:00 · LOCAL</div>
            </div>
            <Toggle on />
          </div>
        </div>

        {/* categories */}
        <Eyebrow style={{ display: "block", marginTop: 18 }}>● CATEGORIES · TAP ROW TO EXPAND</Eyebrow>
        <div className="card" style={{ padding: 0, marginTop: 8 }}>
          {cats.map(([name, desc, ch], i) => (
            <div key={name} style={{ padding: "14px 14px", borderBottom: i < cats.length - 1 ? "1px solid var(--hairline-2)" : "none" }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>{name}</div>
                <div style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 3 }}>{desc}</div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginTop: 10 }}>
                {[["In-app",ch.app],["Email",ch.email],["Push",ch.push]].map(([l,on]) => (
                  <div key={l} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 10px", border: "1px solid var(--hairline-2)", borderRadius: 4, background: on ? "color-mix(in oklab, var(--accent) 10%, transparent)" : "transparent" }}>
                    <span className="mono" style={{ fontSize: 9, letterSpacing: "0.18em", textTransform: "uppercase", color: on ? "var(--accent)" : "var(--fg-3)" }}>{l}</span>
                    <Toggle on={on} />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* email digest */}
        <Eyebrow style={{ display: "block", marginTop: 18 }}>● EMAIL DIGEST</Eyebrow>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginTop: 8 }}>
          {[["Off",false],["Daily",false],["Weekly",true]].map(([l, on]) => (
            <div key={l} className="card" style={{ padding: "12px", textAlign: "center", borderColor: on ? "var(--accent)" : undefined, background: on ? "color-mix(in oklab, var(--accent) 12%, transparent)" : undefined, color: on ? "var(--accent)" : undefined }}>
              <div className="mono" style={{ fontSize: 11, letterSpacing: "0.18em", fontWeight: 600 }}>{l.toUpperCase()}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════
// M-G4. MOBILE SESSION EXPIRED
// ═══════════════════════════════════════════════════════════════════
const MobileSessionExpired = () => (
  <div className="screen">
    <StatusBar />
    <div style={{ flex: 1, padding: "60px 24px 24px", display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 36 }}>
        <AsMark size={26} />
        <Wordmark />
      </div>
      <Eyebrow>● SESSION EXPIRED · 401</Eyebrow>
      <div style={{ fontSize: 28, fontWeight: 700, letterSpacing: "-0.02em", marginTop: 8, lineHeight: 1.15 }}>
        Sign back in.
      </div>
      <div style={{ fontSize: 14, color: "var(--fg-3)", marginTop: 12, lineHeight: 1.55 }}>
        Your session lapsed. Anything in flight is held — you'll land back here after sign-in.
      </div>

      <div className="card" style={{ padding: 14, marginTop: 22, display: "flex", alignItems: "center", gap: 10 }}>
        <div className="avatar lg" style={{ width: 40, height: 40 }}>AH</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 14, fontWeight: 600 }}>Andrew Horn</div>
          <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em", marginTop: 2 }}>andrew@aidstation.run</div>
        </div>
      </div>

      <div style={{ marginTop: 18 }}>
        <span className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.22em", textTransform: "uppercase" }}>● PASSWORD</span>
        <div style={{ display: "flex", alignItems: "center", gap: 10, height: 44, padding: "0 14px", background: "var(--bg-2)", border: "1px solid var(--hairline-2)", borderRadius: 4, marginTop: 6 }}>
          <span style={{ flex: 1, fontSize: 16, fontFamily: "var(--mono)", letterSpacing: "0.2em" }}>••••••••••</span>
          <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.18em" }}>SHOW</span>
        </div>
      </div>

      <div style={{ marginTop: "auto", display: "flex", flexDirection: "column", gap: 10, paddingTop: 24 }}>
        <div className="btn btn-primary" style={{ justifyContent: "center", padding: "14px 18px" }}>Sign in as Andrew</div>
        <div className="btn btn-text" style={{ justifyContent: "center", color: "var(--fg-3)" }}>Not me · sign out</div>
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// M-G5. MOBILE 404
// ═══════════════════════════════════════════════════════════════════
const Mobile404 = () => (
  <div className="screen">
    <StatusBar />
    <AppBar title="Not found" left={<Ic d={I.chevL} size={22} />} right={<Ic d={I.search} size={20} />} />
    <div style={{ flex: 1, overflow: "auto", padding: "16px 24px 16px", display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", justifyContent: "center" }}>
      <div className="mono" style={{ fontSize: 84, fontWeight: 800, letterSpacing: "-0.04em", lineHeight: 1, color: "var(--accent)" }}>4·0·4</div>
      <Eyebrow style={{ marginTop: 14 }}>● NO SUCH ROUTE</Eyebrow>
      <div style={{ fontSize: 22, fontWeight: 700, letterSpacing: "-0.015em", margin: "8px 0 10px", lineHeight: 1.2 }}>
        That URL doesn't go anywhere.
      </div>
      <div style={{ fontSize: 13, color: "var(--fg-3)", lineHeight: 1.55, marginBottom: 18 }}>
        You followed an old link, or that plan version is gone. Nothing's broken — try something below.
      </div>

      <div className="card-flush" style={{ padding: "10px 14px", width: "100%", textAlign: "left", marginBottom: 18 }}>
        <div className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.22em", textTransform: "uppercase" }}>● PATH</div>
        <div className="mono" style={{ fontSize: 12, marginTop: 4, color: "var(--fg)", wordBreak: "break-all" }}>/plans/v12/sessions/9c4-archive</div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, width: "100%" }}>
        {[["Today", I.home],["Plan", I.plan],["Workouts", I.workout]].map(([l, ic]) => (
          <div key={l} className="card" style={{ padding: 12, display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
            <Ic d={ic} size={18} />
            <div style={{ fontSize: 12, fontWeight: 600 }}>{l}</div>
          </div>
        ))}
      </div>
    </div>
    <TabBar active="home" />
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// M-G6. MOBILE PERMISSION DENIED
// ═══════════════════════════════════════════════════════════════════
const MobilePermissionDenied = () => (
  <div className="screen">
    <StatusBar />
    <AppBar title="Admin" left={<Ic d={I.chevL} size={22} />} />
    <div style={{ flex: 1, overflow: "auto", padding: "20px 20px 20px", display: "flex", flexDirection: "column" }}>
      <div style={{ width: 64, height: 64, borderRadius: "50%", background: "color-mix(in oklab, var(--warn) 15%, transparent)", color: "var(--warn)", display: "grid", placeItems: "center", border: "1px solid color-mix(in oklab, var(--warn) 40%, transparent)", margin: "8px auto 14px" }}>
        <Ic d={I.gear} size={28} />
      </div>
      <Eyebrow style={{ color: "var(--warn)", textAlign: "center" }}>● 403 · PERMISSION DENIED</Eyebrow>
      <div style={{ fontSize: 24, fontWeight: 700, letterSpacing: "-0.02em", textAlign: "center", marginTop: 8, lineHeight: 1.15 }}>
        This page needs the admin role.
      </div>
      <div style={{ fontSize: 13, color: "var(--fg-3)", lineHeight: 1.55, marginTop: 10, textAlign: "center" }}>
        Your account is <b>Athlete · Pro</b> — telemetry and audit log aren't included.
      </div>

      <div className="card" style={{ padding: 0, marginTop: 22 }}>
        {[
          ["Ask your admin",    "We can route a request if you don't know who that is."],
          ["Switch workspace",  "You belong to 2 — the other one may have admin."],
          ["Go to Today",       "Return to your last working page."],
        ].map(([k, v], i, a) => (
          <div key={i} style={{ padding: "14px 16px", borderBottom: i < a.length - 1 ? "1px solid var(--hairline-2)" : "none", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ minWidth: 0, paddingRight: 12 }}>
              <div style={{ fontSize: 13, fontWeight: 600 }}>{k}</div>
              <div style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 3 }}>{v}</div>
            </div>
            <Ic d={I.chevR} size={14} />
          </div>
        ))}
      </div>

      <div className="card-flush" style={{ marginTop: 14, padding: "12px 14px", fontFamily: "var(--mono)", fontSize: 10, color: "var(--fg-2)", lineHeight: 1.7 }}>
        <div>route: <span style={{ color: "var(--accent)" }}>/admin/telemetry_refresh</span></div>
        <div>required_role: admin</div>
        <div>request_id: req_5b91c2d4</div>
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// M-ERROR. Shared mobile error shell — used by 404, plan-gen, generic
// ═══════════════════════════════════════════════════════════════════
const MobileErrorShell = ({
  title,
  code,
  message,
  tone = "bad",
  glyph = I.x,
  retryLabel = "Try again",
  retryIcon = I.bolt,
  showRetry = true,
  diag = [],
  children,
  tab = "home",
  appbar = "Error",
}) => {
  const toneVar = tone === "warn" ? "var(--warn)" : "var(--bad)";
  return (
    <div className="screen">
      <StatusBar />
      <AppBar title={appbar} left={<Ic d={I.chevL} size={22} />} />
      <div style={{ flex: 1, overflow: "auto", padding: "24px 20px 16px", display: "flex", flexDirection: "column" }}>
        <div style={{
          width: 64, height: 64, borderRadius: "50%",
          background: `color-mix(in oklab, ${toneVar} 15%, transparent)`,
          color: toneVar, display: "grid", placeItems: "center",
          border: `1px solid color-mix(in oklab, ${toneVar} 35%, transparent)`,
          margin: "8px auto 14px",
        }}>
          <Ic d={glyph} size={28} sw={2} />
        </div>
        <div style={{ textAlign: "center" }}>
          <Eyebrow style={{ color: toneVar }}>● {code}</Eyebrow>
          <div style={{ fontSize: 22, fontWeight: 700, letterSpacing: "-0.02em", marginTop: 8, lineHeight: 1.2 }}>{title}</div>
          <div style={{ fontSize: 13, color: "var(--fg-3)", lineHeight: 1.55, marginTop: 10 }}>{message}</div>
        </div>

        {children && <div style={{ marginTop: 18 }}>{children}</div>}

        {diag.length > 0 && (
          <div className="card-flush" style={{ marginTop: 18, padding: "12px 14px", fontFamily: "var(--mono)", fontSize: 10, color: "var(--fg-2)", lineHeight: 1.7 }}>
            <div className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.22em", textTransform: "uppercase", marginBottom: 6 }}>● DIAGNOSTIC</div>
            {diag.map(([k, v], i) => (
              <div key={i}>{k}: <span style={{ color: i === 0 ? "var(--accent)" : "var(--fg-2)" }}>{v}</span></div>
            ))}
          </div>
        )}

        <div style={{ marginTop: "auto", paddingTop: 20, display: "flex", flexDirection: "column", gap: 8 }}>
          {showRetry && (
            <div className="btn btn-primary" style={{ justifyContent: "center", padding: "13px 18px" }}>
              <Ic d={retryIcon} size={12} sw={2} /> {retryLabel}
            </div>
          )}
          <div className="btn btn-ghost" style={{ justifyContent: "center", padding: "13px 18px" }}>
            <Ic d={I.bell} size={12} /> Email help@aidstation.pro
          </div>
          <div className="mono" style={{ textAlign: "center", marginTop: 4, fontSize: 9, letterSpacing: "0.18em", color: "var(--fg-4)" }}>
            ⓘ MAILTO INCLUDES THE DIAGNOSTIC ABOVE
          </div>
        </div>
      </div>
      <TabBar active={tab} />
    </div>
  );
};

const Mobile404v2 = () => (
  <MobileErrorShell
    appbar="Not found"
    code="404 · NO SUCH ROUTE"
    title="You're off trail."
    message="This route isn't on the map — an old link, or a plan version that's been archived. Here's the way back."
    showRetry={false}
    diag={[
      ["attempted_path", "/plans/v12/sessions/9c4"],
      ["request_id",     "req_4b9e2a7c"],
    ]}
  >
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
      {[["Today", I.home],["Plan", I.plan],["Workouts", I.workout]].map(([l, ic]) => (
        <div key={l} className="card" style={{ padding: 12, display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
          <Ic d={ic} size={18} />
          <div style={{ fontSize: 12, fontWeight: 600 }}>{l}</div>
        </div>
      ))}
    </div>
  </MobileErrorShell>
);

const MobilePlanGenFailedV2 = () => (
  <MobileErrorShell
    appbar="Plan generation"
    tab="plan"
    code="PLAN-GEN-FAILED · STEP 4/6"
    title="The build stalled."
    message="Base and build came together — then we hit the wall on the peak block. Inputs are saved; tweak one thing and run it again."
    retryLabel="Retry generation"
    diag={[
      ["generation_id", "gen_9c40e2a1"],
      ["failed_phase",  "peak_block_synthesis"],
      ["error",         "InfeasibleScheduleConstraint"],
    ]}
  >
    <Eyebrow style={{ display: "block", marginBottom: 6 }}>● TRY ONE</Eyebrow>
    <div className="card" style={{ padding: 0 }}>
      {[
        "Extend Saturday window to 3 h",
        "Move long session to Sunday",
        "Drop goal one tier (sub-3:00 → BQ)",
      ].map((l, i, a) => (
        <div key={i} style={{ padding: "12px 14px", borderBottom: i < a.length - 1 ? "1px solid var(--hairline-2)" : "none", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontSize: 13, fontWeight: 600 }}>{l}</div>
          <Ic d={I.chevR} size={14} />
        </div>
      ))}
    </div>
  </MobileErrorShell>
);

const MobileErrorGeneric = () => (
  <MobileErrorShell
    appbar="Sync"
    tab="home"
    code="500 · SOMETHING BROKE"
    title="Something seized up."
    message="Whatever you just tried cramped up on our end. Your data's safe — nothing was committed. Catch your breath and try again."
    diag={[
      ["request_id", "req_a72e9f04"],
      ["action",     "POST /connections/wahoo/refresh"],
      ["status",     "500 internal_error"],
    ]}
  />
);

Object.assign(window, {
  MobileProfileEmpty,
  MobileWellnessFitImport,
  MobileNotifSettings,
  MobileErrorShell,
  Mobile404v2, MobilePlanGenFailedV2, MobileErrorGeneric,
});
