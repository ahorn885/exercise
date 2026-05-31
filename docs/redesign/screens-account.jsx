/* AIDSTATION redesign — Account settings (§12C)
   ───────────────────────────────────────────────────────────────
   Grounded ONLY in code that exists:
     · identity display — username · display name · email · last login
       (profile/edit.html › Account tab `user_row` fields)
     · change password — profile.change_password (current/new/confirm)
     · sign out — auth.logout · forgot password — auth.forgot
   Deliberately NO billing, NO 2FA, NO sessions list, NO self-serve
   delete (none exist in code yet). */

// ─── Local atoms (Field/Checkbox aren't exported from gaps file) ──
const AcctField = ({ label, value, type = "text", placeholder, hint, status }) => (
  <div>
    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
      <span className="mono" style={{ fontSize: 9, letterSpacing: "0.22em", textTransform: "uppercase", color: "var(--fg-3)" }}>● {label.toUpperCase()}</span>
      {status && <span className="mono" style={{ fontSize: 9, letterSpacing: "0.22em", textTransform: "uppercase", color: status[1] }}>{status[0]}</span>}
    </div>
    <div style={{ display: "flex", alignItems: "center", gap: 10, height: 40, padding: "0 12px", background: "var(--bg-2)", border: "1px solid var(--hairline-2)", borderRadius: 4 }}>
      <span style={{ flex: 1, fontSize: 14, color: value ? "var(--fg)" : "var(--fg-4)", fontFamily: type === "password" ? "var(--mono)" : "var(--sans)", letterSpacing: type === "password" && value ? "0.2em" : 0 }}>
        {type === "password" && value ? "•".repeat(value.length) : (value || placeholder)}
      </span>
      {type === "password" && <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.18em" }}>SHOW</span>}
    </div>
    {hint && <div style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 6 }}>{hint}</div>}
  </div>
);

// Reused password strength block (matches onboarding step 01 vocabulary;
// code rule is minlength=8).
const PwStrength = () => {
  const rules = [["≥ 8 characters", true], ["Mixed case", true], ["A number", true], ["A symbol (! @ # $ …)", false]];
  return (
    <div style={{ marginTop: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
        <span className="mono" style={{ fontSize: 9, letterSpacing: "0.22em", textTransform: "uppercase", color: "var(--fg-3)" }}>● STRENGTH</span>
        <span className="mono" style={{ fontSize: 9, letterSpacing: "0.22em", textTransform: "uppercase", color: "var(--warn)" }}>FAIR · ADD A SYMBOL</span>
      </div>
      <div style={{ display: "flex", gap: 4, height: 4 }}>
        {[0, 1, 2, 3].map((i) => (
          <div key={i} style={{ flex: 1, background: i < 3 ? "var(--warn)" : "var(--bg-3)" }} />
        ))}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px 14px", marginTop: 12 }}>
        {rules.map(([t, ok], i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: ok ? "var(--fg-2)" : "var(--fg-4)" }}>
            {ok ? <Ic d={I.check} size={12} sw={2.5} /> : <span style={{ width: 8, height: 8, borderRadius: "50%", border: "1px solid var(--fg-4)" }} />}
            {t}
          </div>
        ))}
      </div>
    </div>
  );
};

const IdentityRow = ({ k, v, action }) => (
  <div style={{ display: "grid", gridTemplateColumns: "180px 1fr auto", gap: 16, alignItems: "center", padding: "14px 0", borderBottom: "1px solid var(--hairline-2)" }}>
    <span className="mono" style={{ fontSize: 10, letterSpacing: "0.16em", color: "var(--fg-3)", textTransform: "uppercase" }}>{k}</span>
    <span style={{ color: "var(--fg)", fontFamily: k === "Email" || k === "Username" ? "var(--mono)" : "var(--sans)", fontSize: k === "Email" || k === "Username" ? 13 : 14 }}>{v}</span>
    {action || <span />}
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// 12C. ACCOUNT SETTINGS · desktop
// ═══════════════════════════════════════════════════════════════════
const ScreenAccount = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="athlete" />
      <div className="page">
        <TopBar crumbs={["Athlete", "Account"]} actions={
          <div className="btn btn-text btn-sm" style={{ color: "var(--fg-2)" }}>Sign out</div>
        } />
        <div className="page-body">
          <div style={{ marginBottom: 20 }}>
            <Eyebrow>Account · sign-in &amp; security</Eyebrow>
            <h1 className="page-title" style={{ marginTop: 8 }}>Account</h1>
            <div className="page-sub">Your login identity and password. Training data, baselines, schedule, and skills live on the <span style={{ color: "var(--fg-2)" }}>Athlete</span> tabs; connected services live in <span style={{ color: "var(--fg-2)" }}>Connections</span>.</div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1.1fr 1fr", gap: 22, alignItems: "start" }}>
            {/* LEFT — identity */}
            <div className="card" style={{ padding: 22 }}>
              <Eyebrow>Identity</Eyebrow>
              <div style={{ marginTop: 6 }}>
                <IdentityRow k="Username" v="ahorn" action={<span className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--fg-4)" }}>PERMANENT</span>} />
                <IdentityRow k="Display name" v="Andrew Horn" action={<div className="btn btn-ghost btn-sm">Edit</div>} />
                <IdentityRow k="Email" v={<>andrew@aidstation.run <Pill tone="good" style={{ marginLeft: 6 }}>✓ VERIFIED</Pill></>} action={<div className="btn btn-ghost btn-sm">Change</div>} />
                <div style={{ display: "grid", gridTemplateColumns: "180px 1fr auto", gap: 16, alignItems: "center", padding: "14px 0" }}>
                  <span className="mono" style={{ fontSize: 10, letterSpacing: "0.16em", color: "var(--fg-3)", textTransform: "uppercase" }}>Last login</span>
                  <span className="mono" style={{ fontSize: 13, color: "var(--fg-2)" }}>Today · 09:14 · Washington DC</span>
                  <span />
                </div>
              </div>
              <div className="mono" style={{ fontSize: 10, letterSpacing: "0.14em", color: "var(--fg-4)", marginTop: 8, textTransform: "uppercase", lineHeight: 1.6 }}>
                ⓘ EMAIL IS YOUR SIGN-IN. CHANGING IT SENDS A VERIFICATION LINK TO THE NEW ADDRESS BEFORE IT TAKES EFFECT.
              </div>
            </div>

            {/* RIGHT — change password + session */}
            <div className="stack">
              <div className="card" style={{ padding: 22 }}>
                <Eyebrow>Change password</Eyebrow>
                <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 12 }}>
                  <AcctField label="Current password" type="password" value="aidstationFTW21" />
                  <AcctField label="New password" type="password" value="trailrunner2026" />
                  <AcctField label="Confirm new password" type="password" value="trailrunner2026" status={["✓ MATCH", "var(--good)"]} />
                </div>
                <PwStrength />
                <div style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 18 }}>
                  <div className="btn btn-primary"><Ic d={I.check} size={12} sw={2.2} /> Change password</div>
                  <div className="btn btn-text btn-sm" style={{ color: "var(--fg-3)" }}>Forgot current?</div>
                </div>
              </div>

              <div className="card" style={{ padding: 22 }}>
                <Eyebrow>This session</Eyebrow>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 12 }}>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 600 }}>Signed in on this device</div>
                    <div className="mono" style={{ fontSize: 10, letterSpacing: "0.14em", color: "var(--fg-3)", marginTop: 3, textTransform: "uppercase" }}>
                      CHROME · MACOS · STARTED TODAY 09:14
                    </div>
                  </div>
                  <div className="btn btn-ghost btn-sm">Sign out</div>
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
// 12C. ACCOUNT SETTINGS · mobile
// ═══════════════════════════════════════════════════════════════════
const MobileAccount = () => (
  <div className="screen">
    <StatusBar />
    <AppBar title="Account" left={<Ic d={I.chevL} size={22} />} right={null} />

    <div style={{ flex: 1, overflow: "auto", padding: "16px 16px 28px" }}>
      <Eyebrow>Identity</Eyebrow>
      <div className="card" style={{ padding: "4px 14px", marginTop: 10, marginBottom: 18 }}>
        {[
          ["Username", "ahorn", "PERMANENT"],
          ["Display name", "Andrew Horn", "EDIT"],
          ["Email", "andrew@aidstation.run", "CHANGE"],
          ["Last login", "Today · 09:14", null],
        ].map(([k, v, act], i, a) => (
          <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 0", borderBottom: i < a.length - 1 ? "1px solid var(--hairline-2)" : "none", gap: 12 }}>
            <div style={{ minWidth: 0 }}>
              <div className="mono" style={{ fontSize: 9, letterSpacing: "0.16em", color: "var(--fg-3)", textTransform: "uppercase" }}>{k}</div>
              <div style={{ fontSize: 13, marginTop: 3, fontFamily: k === "Email" || k === "Username" ? "var(--mono)" : "var(--sans)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{v}</div>
            </div>
            {act === "PERMANENT"
              ? <span className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--fg-4)" }}>{act}</span>
              : act
                ? <span className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--accent)" }}>{act}</span>
                : null}
          </div>
        ))}
      </div>

      <Eyebrow>Change password</Eyebrow>
      <div className="card" style={{ padding: 16, marginTop: 10, marginBottom: 18 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <AcctField label="Current password" type="password" value="aidstationFTW21" />
          <AcctField label="New password" type="password" value="trailrunner2026" />
          <AcctField label="Confirm new" type="password" value="trailrunner2026" status={["✓ MATCH", "var(--good)"]} />
        </div>
        <PwStrength />
        <div className="btn btn-primary btn-sm" style={{ marginTop: 16, width: "100%", justifyContent: "center" }}>
          <Ic d={I.check} size={11} sw={2.2} /> Change password
        </div>
        <div className="btn btn-text btn-sm" style={{ marginTop: 6, width: "100%", justifyContent: "center", color: "var(--fg-3)" }}>Forgot current?</div>
      </div>

      <Eyebrow>Session</Eyebrow>
      <div className="card" style={{ padding: 16, marginTop: 10 }}>
        <div style={{ fontSize: 13, fontWeight: 600 }}>Signed in · this device</div>
        <div className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--fg-3)", marginTop: 3, textTransform: "uppercase" }}>SAFARI · iOS · STARTED TODAY 09:14</div>
        <div className="btn btn-ghost btn-sm" style={{ marginTop: 12, width: "100%", justifyContent: "center" }}>Sign out</div>
      </div>
    </div>

    <TabBar active="me" />
  </div>
);

Object.assign(window, { ScreenAccount, MobileAccount });
