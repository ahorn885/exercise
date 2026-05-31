/* AIDSTATION redesign — Empty and error states
   Dashboard empty · Plan empty · Wellness empty
   Provider auth failed · FIT parse error · Plan-gen failed
   Refresh cap-exceeded modal */

// ═══════════════════════════════════════════════════════════════════
// E1. DASHBOARD — NO PLAN YET (first-run, after signup before plan gen)
// ═══════════════════════════════════════════════════════════════════
const ScreenDashboardEmpty = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="home" />
      <div className="page">
        <TopBar crumbs={["Today"]} actions={null} />
        <div className="page-body" style={{ display: "grid", placeItems: "center", padding: "32px 28px" }}>
          <div style={{ maxWidth: 580, width: "100%", textAlign: "center" }}>
            <Eyebrow accent>● WELCOME · NO PLAN YET</Eyebrow>
            <h1 style={{ fontSize: 44, fontWeight: 800, letterSpacing: "-0.025em", lineHeight: 1.05, margin: "12px 0 14px" }}>
              You haven't built a plan.
            </h1>
            <div style={{ color: "var(--fg-3)", fontSize: 15, lineHeight: 1.55, maxWidth: 460, margin: "0 auto 28px" }}>
              Everything in AIDSTATION anchors to a race. Generate your first plan in 3–5 minutes — we pull from your providers and your race target.
            </div>

            {/* Pre-flight readiness card */}
            <div className="card" style={{ padding: 18, textAlign: "left", marginBottom: 18 }}>
              <Eyebrow>Pre-flight · what we have</Eyebrow>
              <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 8 }}>
                {[
                  ["Account",           true,  "Andrew Horn · andrew@aidstation.run"],
                  ["Connected provider", true,  "Strava · 412 sessions"],
                  ["Performance baselines", false, "Set 4 of 6 — re-prefill from Strava"],
                  ["Schedule",          true,  "6 days · 8.5 h/wk"],
                  ["Skills",            true,  "5 of 12 checked"],
                  ["Locations",         true,  "Home garage + 2 more"],
                  ["Target race",       false, "Not set — required for plan generation"],
                ].map(([k, done, v], i) => (
                  <div key={i} style={{ display: "grid", gridTemplateColumns: "20px 1fr auto", gap: 12, alignItems: "center" }}>
                    {done ? (
                      <div style={{ width: 16, height: 16, borderRadius: "50%", background: "color-mix(in oklab, var(--good) 20%, transparent)", color: "var(--good)", display: "grid", placeItems: "center" }}>
                        <Ic d={I.check} size={10} sw={2.5} />
                      </div>
                    ) : (
                      <div style={{ width: 10, height: 10, borderRadius: "50%", background: "var(--warn)", boxShadow: "0 0 0 4px color-mix(in oklab, var(--warn) 30%, transparent)" }} />
                    )}
                    <div>
                      <div style={{ fontWeight: 600, fontSize: 13 }}>{k}</div>
                      <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em", marginTop: 2, textTransform: "uppercase" }}>{v}</div>
                    </div>
                    {!done && <Pill tone="warn">FIX →</Pill>}
                  </div>
                ))}
              </div>
            </div>

            <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
              <div className="btn btn-ghost" style={{ padding: "14px 18px" }}>Set target race first</div>
              <div className="btn btn-primary" style={{ padding: "14px 22px" }}><Ic d={I.bolt} size={13} /> Generate plan</div>
            </div>
            <div className="mono" style={{ marginTop: 18, fontSize: 10, letterSpacing: "0.18em", color: "var(--fg-4)" }}>
              ⓘ NOTHING IS LOCKED IN · YOU CAN EDIT ANYTHING AFTER
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// E2. WELLNESS — EMPTY (no data in range)
// ═══════════════════════════════════════════════════════════════════
const ScreenWellnessEmpty = () => (
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
        <div className="page-body" style={{ display: "grid", placeItems: "center" }}>
          <div style={{ maxWidth: 560, textAlign: "center" }}>
            <Eyebrow>● NO DATA YET · LAST 30 DAYS</Eyebrow>
            <h2 style={{ fontSize: 30, fontWeight: 700, letterSpacing: "-0.02em", margin: "10px 0 8px" }}>
              Nothing to chart yet.
            </h2>
            <div style={{ color: "var(--fg-3)", fontSize: 14, lineHeight: 1.55, maxWidth: 440, margin: "0 auto 24px" }}>
              Log a wellness self-report below, add body metrics, or connect a provider to pull sleep + HR automatically. We'll start charting as data arrives.
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, maxWidth: 440, margin: "0 auto" }}>
              {[
                ["Self-report", "Sleep · energy · mood", I.pulse],
                ["Body metrics", "Weight · BF · RHR", I.body],
                ["Connect", "Strava · Wahoo · …", I.link],
              ].map(([t, s, ic], i) => (
                <div key={i} className="card" style={{ padding: 14, textAlign: "center" }}>
                  <Ic d={ic} size={18} />
                  <div style={{ fontSize: 13, fontWeight: 600, marginTop: 8 }}>{t}</div>
                  <div className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.14em", marginTop: 4, textTransform: "uppercase" }}>{s}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// E3. CONNECTIONS — NO PROVIDERS YET
// ═══════════════════════════════════════════════════════════════════
const ScreenConnectionsEmpty = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="link" />
      <div className="page">
        <TopBar crumbs={["Connections"]} actions={
          <div className="btn btn-primary"><Ic d={I.upload} size={12} /> Upload .FIT</div>
        } />
        <div className="page-body" style={{ display: "grid", placeItems: "center", padding: "32px 28px" }}>
          <div style={{ maxWidth: 580, textAlign: "center" }}>
            <Eyebrow>● ZERO CONNECTIONS · ZERO IMPORTS</Eyebrow>
            <h1 style={{ fontSize: 36, fontWeight: 700, letterSpacing: "-0.02em", margin: "10px 0 10px" }}>
              No data flowing yet.
            </h1>
            <div style={{ color: "var(--fg-3)", fontSize: 14, lineHeight: 1.55, maxWidth: 440, margin: "0 auto 28px" }}>
              Connect a service to auto-sync, or upload .FIT files manually. Either path feeds the same engine — plans will adapt to whichever you choose.
            </div>
            <div className="card" style={{ padding: 24, marginBottom: 14 }}>
              <Eyebrow accent>● RECOMMENDED · CONNECT A PROVIDER</Eyebrow>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8, marginTop: 14 }}>
                {[["Strava", "#FC4C02"], ["Wahoo", "#0093D0"], ["Whoop", "#000"]].map(([name, color], i) => (
                  <div key={i} className="card" style={{ padding: 14, display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
                    <div style={{ width: 32, height: 32, borderRadius: 4, background: color, display: "grid", placeItems: "center", color: "white", fontFamily: "var(--mono)", fontWeight: 700, fontSize: 14 }}>
                      {name[0]}
                    </div>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{name}</div>
                    <div className="btn btn-primary btn-sm">CONNECT</div>
                  </div>
                ))}
              </div>
            </div>
            <div className="btn btn-text" style={{ color: "var(--fg-3)" }}>Or skip and upload .FIT manually →</div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// E4. PROVIDER AUTH FAILED (OAuth handshake error)
// ═══════════════════════════════════════════════════════════════════
const ScreenAuthFailed = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="link" />
      <div className="page">
        <TopBar crumbs={["Connections", "Connect Wahoo"]} />
        <div className="page-body" style={{ display: "grid", placeItems: "center", padding: "32px 28px" }}>
          <div style={{ maxWidth: 580, width: "100%" }}>
            <div style={{
              padding: 18,
              border: "1px solid color-mix(in oklab, var(--bad) 40%, transparent)",
              background: "color-mix(in oklab, var(--bad) 8%, transparent)",
              borderRadius: 6,
              marginBottom: 24,
              display: "flex", gap: 14, alignItems: "flex-start",
            }}>
              <div style={{ width: 32, height: 32, borderRadius: "50%", background: "color-mix(in oklab, var(--bad) 25%, transparent)", color: "var(--bad)", display: "grid", placeItems: "center", flexShrink: 0 }}>
                <Ic d={I.x} size={14} sw={2.5} />
              </div>
              <div>
                <Eyebrow style={{ color: "var(--bad)" }}>● AUTH FAILED</Eyebrow>
                <div style={{ fontSize: 17, fontWeight: 700, marginTop: 6 }}>Wahoo didn't connect.</div>
                <div style={{ fontSize: 13, color: "var(--fg-2)", marginTop: 6, lineHeight: 1.55 }}>
                  The OAuth handshake or partner-user registration failed. This usually means Wahoo's auth surface is briefly down, or your account doesn't have the required scopes enabled.
                </div>
              </div>
            </div>

            <Eyebrow>Diagnostic</Eyebrow>
            <div className="card-flush" style={{ marginTop: 10, padding: "14px 16px", fontFamily: "var(--mono)", fontSize: 12, color: "var(--fg-2)", lineHeight: 1.7 }}>
              <div>request_id: <span style={{ color: "var(--accent)" }}>req_8x21abf9d</span></div>
              <div>provider: wahoo</div>
              <div>step: oauth_callback</div>
              <div>error_code: <span style={{ color: "var(--bad)" }}>invalid_grant</span></div>
              <div>error_description: authorization code expired</div>
              <div>timestamp: 2026-05-27T14:24:07Z</div>
            </div>

            <Eyebrow style={{ marginTop: 22 }}>Try this</Eyebrow>
            <div className="card" style={{ marginTop: 10, padding: 0 }}>
              {[
                ["Try again",                "Auth codes expire after 60s — the most common cause."],
                ["Check Wahoo status",       "status.wahoofitness.com — green check means it's up."],
                ["Re-grant scopes",          "If you've revoked AIDSTATION in Wahoo's dashboard, you'll need to re-add."],
                ["Contact support",          "Email support@aidstation.run — include the request_id above."],
              ].map(([k, v], i, a) => (
                <div key={i} style={{ padding: "14px 18px", borderBottom: i < a.length - 1 ? "1px solid var(--hairline-2)" : "none" }}>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>{k}</div>
                  <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 4 }}>{v}</div>
                </div>
              ))}
            </div>

            <div style={{ display: "flex", gap: 10, marginTop: 24 }}>
              <div className="btn btn-ghost" style={{ flex: 1, justifyContent: "center" }}>Cancel</div>
              <div className="btn btn-primary" style={{ flex: 2, justifyContent: "center" }}><Ic d={I.link} size={12} /> Try Wahoo again</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// E5. FIT PARSE ERROR (uploaded file rejected)
// ═══════════════════════════════════════════════════════════════════
const ScreenFitError = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="link" />
      <div className="page">
        <TopBar crumbs={["Connections", "Upload .FIT"]} />
        <div className="page-body" style={{ display: "grid", placeItems: "center", padding: "32px 28px" }}>
          <div style={{ maxWidth: 640, width: "100%" }}>
            <div style={{
              padding: 18,
              border: "1px solid color-mix(in oklab, var(--bad) 40%, transparent)",
              background: "color-mix(in oklab, var(--bad) 8%, transparent)",
              borderRadius: 6,
              marginBottom: 24,
              display: "flex", gap: 14, alignItems: "flex-start",
            }}>
              <div style={{ width: 32, height: 32, borderRadius: "50%", background: "color-mix(in oklab, var(--bad) 25%, transparent)", color: "var(--bad)", display: "grid", placeItems: "center", flexShrink: 0 }}>
                <Ic d={I.x} size={14} sw={2.5} />
              </div>
              <div>
                <Eyebrow style={{ color: "var(--bad)" }}>● PARSE FAILED · 2 OF 3 FILES</Eyebrow>
                <div style={{ fontSize: 17, fontWeight: 700, marginTop: 6 }}>Couldn't read 2 .FIT files.</div>
                <div style={{ fontSize: 13, color: "var(--fg-2)", marginTop: 6, lineHeight: 1.55 }}>
                  One imported cleanly; two were rejected. Re-export from your device or upload a different file.
                </div>
              </div>
            </div>

            <Eyebrow>Files</Eyebrow>
            <div className="card" style={{ marginTop: 10, padding: 0 }}>
              {[
                { name: "activity_2026-05-27_0844.fit",    size: "487 KB", status: "ok",     msg: "Imported · 1h 18m run" },
                { name: "activity_2026-05-26_corrupt.fit", size: "12 KB",  status: "error",  msg: "CRC mismatch — file appears truncated. Re-export from device." },
                { name: "swim_session.fit",                 size: "284 KB", status: "error",  msg: "Unknown sport ID (15). Convert to a supported format first." },
              ].map((f, i, a) => (
                <div key={i} style={{ padding: "14px 18px", borderBottom: i < a.length - 1 ? "1px solid var(--hairline-2)" : "none", display: "grid", gridTemplateColumns: "32px 1fr auto", gap: 14, alignItems: "center" }}>
                  {f.status === "ok" ? (
                    <div style={{ width: 24, height: 24, borderRadius: "50%", background: "color-mix(in oklab, var(--good) 20%, transparent)", color: "var(--good)", display: "grid", placeItems: "center" }}>
                      <Ic d={I.check} size={12} sw={2.5} />
                    </div>
                  ) : (
                    <div style={{ width: 24, height: 24, borderRadius: "50%", background: "color-mix(in oklab, var(--bad) 20%, transparent)", color: "var(--bad)", display: "grid", placeItems: "center" }}>
                      <Ic d={I.x} size={12} sw={2.5} />
                    </div>
                  )}
                  <div style={{ minWidth: 0 }}>
                    <div className="mono" style={{ fontSize: 13, fontWeight: 600 }}>{f.name}</div>
                    <div style={{ fontSize: 12, color: f.status === "ok" ? "var(--good)" : "var(--fg-3)", marginTop: 4 }}>{f.msg}</div>
                  </div>
                  <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.14em" }}>{f.size}</span>
                </div>
              ))}
            </div>

            <div style={{ marginTop: 24, display: "flex", gap: 10 }}>
              <div className="btn btn-ghost" style={{ flex: 1, justifyContent: "center" }}><Ic d={I.upload} size={12} /> Upload more</div>
              <div className="btn btn-primary" style={{ flex: 1, justifyContent: "center" }}><Ic d={I.arrow} size={12} sw={2} /> Continue with 1 file</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// E6. PLAN GENERATION FAILED
// ═══════════════════════════════════════════════════════════════════
const ScreenPlanGenFailed = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="plan" />
      <div className="page">
        <TopBar crumbs={["Plan", "Generation failed"]} />
        <div className="page-body" style={{ display: "grid", placeItems: "center", padding: "32px 28px" }}>
          <div style={{ maxWidth: 580, width: "100%", textAlign: "center" }}>
            <div style={{ width: 80, height: 80, margin: "0 auto 18px", borderRadius: "50%", background: "color-mix(in oklab, var(--bad) 15%, transparent)", color: "var(--bad)", display: "grid", placeItems: "center" }}>
              <Ic d={I.x} size={36} sw={2} />
            </div>
            <Eyebrow style={{ color: "var(--bad)" }}>● GENERATION FAILED · STEP 4 OF 6</Eyebrow>
            <h1 style={{ fontSize: 36, fontWeight: 700, letterSpacing: "-0.02em", margin: "12px 0 12px" }}>
              Plan didn't finish.
            </h1>
            <div style={{ color: "var(--fg-3)", fontSize: 14, lineHeight: 1.55, maxWidth: 440, margin: "0 auto 24px" }}>
              We got partway through the cascade — base + build phases were synthesized — but the peak block hit a constraint conflict it couldn't resolve. Your inputs are saved; you can retry with a tweak.
            </div>

            <div className="card-flush" style={{ padding: "14px 18px", textAlign: "left", marginBottom: 18 }}>
              <Eyebrow>Diagnostic</Eyebrow>
              <div style={{ marginTop: 8, fontFamily: "var(--mono)", fontSize: 12, lineHeight: 1.7, color: "var(--fg-2)" }}>
                <div>generation_id: <span style={{ color: "var(--accent)" }}>gen_9c40e2a1</span></div>
                <div>last_completed_phase: build_synthesis</div>
                <div>failed_phase: peak_block_synthesis</div>
                <div>error: <span style={{ color: "var(--bad)" }}>InfeasibleScheduleConstraint</span></div>
                <div style={{ marginTop: 6, padding: "8px 10px", background: "var(--bg-2)", borderRadius: 3, fontSize: 11 }}>
                  Weekly long session ({"≥"}2h 30m) doesn't fit any of your enabled day windows during the 4-week peak block. Longest window is Sat 2h 30m — borderline.
                </div>
              </div>
            </div>

            <Eyebrow>Suggested fixes</Eyebrow>
            <div className="card" style={{ marginTop: 10, padding: 0, textAlign: "left", marginBottom: 24 }}>
              {[
                ["Extend Saturday window to 3 h",  "Most direct fix — the peak block needs the long session."],
                ["Move long session to Sunday",     "If Sunday's currently rest day, enable it for the peak block."],
                ["Drop goal one tier",              "Sub-3:00 → BQ qualifying time — peak block becomes feasible."],
              ].map(([k, v], i, a) => (
                <div key={i} style={{ padding: "14px 18px", borderBottom: i < a.length - 1 ? "1px solid var(--hairline-2)" : "none", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 14 }}>{k}</div>
                    <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 4 }}>{v}</div>
                  </div>
                  <div className="btn btn-ghost btn-sm">FIX →</div>
                </div>
              ))}
            </div>

            <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
              <div className="btn btn-ghost">Edit inputs</div>
              <div className="btn btn-primary"><Ic d={I.bolt} size={12} /> Retry generation</div>
            </div>
            <div className="mono" style={{ marginTop: 14, fontSize: 10, letterSpacing: "0.18em", color: "var(--fg-4)" }}>
              ⓘ NO CHARGE FOR FAILED GENERATIONS · CACHED PHASES REUSE ON RETRY
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// E7. REFRESH CAP-EXCEEDED MODAL
// ═══════════════════════════════════════════════════════════════════
const ScreenRefreshCapped = () => (
  <div className="screen">
    {/* Ghost background — refresh form behind */}
    <div style={{ display: "flex", flex: 1, minHeight: 0, position: "relative" }}>
      <Sidebar active="plan" />
      <div className="page" style={{ filter: "blur(2px)", opacity: 0.4 }}>
        <TopBar crumbs={["Plan", "Refresh"]} />
        <div className="page-body">
          <Eyebrow>Plan refresh · re-run the cascade</Eyebrow>
          <h1 className="page-title" style={{ marginTop: 8 }}>Update your plan.</h1>
          <div className="card" style={{ marginTop: 20, padding: 18, height: 100 }} />
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginTop: 18 }}>
            <div className="card" style={{ height: 140 }} />
            <div className="card" style={{ height: 140 }} />
            <div className="card" style={{ height: 140 }} />
          </div>
        </div>
      </div>

      {/* Dim overlay */}
      <div style={{ position: "absolute", inset: 0, background: "color-mix(in oklab, var(--ink) 50%, transparent)" }} />

      {/* Modal */}
      <div style={{
        position: "absolute", top: "50%", left: "50%",
        transform: "translate(-50%, -50%)",
        width: 480,
        background: "var(--bg-2)",
        border: "1px solid var(--hairline)",
        borderRadius: 8,
        boxShadow: "0 24px 60px -8px rgba(0,0,0,0.5)",
        overflow: "hidden",
      }}>
        <div style={{ padding: "18px 22px 16px", borderBottom: "1px solid var(--hairline-2)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <Eyebrow>● FREQUENCY CAP</Eyebrow>
          <Ic d={I.x} size={16} />
        </div>
        <div style={{ padding: "20px 22px" }}>
          <h3 style={{ fontSize: 22, fontWeight: 700, letterSpacing: "-0.015em", margin: 0 }}>Refresh again?</h3>
          <div style={{ fontSize: 14, color: "var(--fg-2)", marginTop: 10, lineHeight: 1.55 }}>
            You've already refreshed <b>4 times</b> in the last 24 hours. Each refresh re-runs the cascade and costs compute. Continue if this signal is worth it.
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 0, marginTop: 16, padding: "12px 0", borderTop: "1px solid var(--hairline-2)", borderBottom: "1px solid var(--hairline-2)" }}>
            {[
              ["T2 today",    "4"],
              ["Soft cap",    "3 / 24h"],
              ["Last refresh", "32 min ago"],
            ].map(([k, v], i) => (
              <div key={i} style={{ borderRight: i < 2 ? "1px solid var(--hairline-2)" : "none", padding: "0 14px", textAlign: i === 1 ? "center" : i === 2 ? "right" : "left" }}>
                <div className="eyebrow" style={{ fontSize: 9 }}>{k}</div>
                <div className="num" style={{ fontSize: 16, fontWeight: 700, marginTop: 4 }}>{v}</div>
              </div>
            ))}
          </div>

          <div className="mono" style={{ fontSize: 10, letterSpacing: "0.14em", color: "var(--fg-3)", marginTop: 14, textTransform: "uppercase" }}>
            ⓘ THE CAP RESETS AT MIDNIGHT LOCAL · YOUR PLAN VERSIONS ARE FREE TO REVERT
          </div>
        </div>
        <div style={{ padding: "14px 22px", borderTop: "1px solid var(--hairline-2)", display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <div className="btn btn-ghost btn-sm">Cancel</div>
          <div className="btn btn-primary btn-sm"><Ic d={I.bolt} size={11} /> Refresh anyway · T2</div>
        </div>
      </div>
    </div>
  </div>
);

Object.assign(window, {
  ScreenDashboardEmpty, ScreenWellnessEmpty, ScreenConnectionsEmpty,
  ScreenAuthFailed, ScreenFitError, ScreenPlanGenFailed, ScreenRefreshCapped,
});
