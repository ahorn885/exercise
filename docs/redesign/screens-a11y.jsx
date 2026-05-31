/* AIDSTATION redesign — Keyboard & screen-reader spec (§29 expansion)
   The behavioral accessibility layer that a static mockup can't embody:
   tab-order, landmarks, focus management, and the ARIA contract per
   component. Engineering implements against these when building.

   These are annotated SPEC diagrams (wireframes I control), not live
   overlays — so the numbered tab-stops sit exactly where intended. */

const A11Y_ACCENT = "var(--accent)";

// Numbered tab-stop badge (absolutely positioned on a diagram)
const Stop = ({ n, style, ghost }) => (
  <div style={{
    position: "absolute", width: 22, height: 22, borderRadius: "50%",
    background: ghost ? "var(--bg-3)" : A11Y_ACCENT,
    color: ghost ? "var(--fg-2)" : "var(--ink)",
    display: "grid", placeItems: "center",
    fontFamily: "var(--mono)", fontWeight: 800, fontSize: 11,
    boxShadow: ghost ? "none" : "0 0 0 3px color-mix(in oklab, var(--accent) 22%, transparent)",
    zIndex: 5, ...style,
  }}>{n}</div>
);

// Wireframe region box
const Region = ({ label, role, style, children }) => (
  <div style={{
    position: "absolute", border: "1px dashed var(--hairline)", borderRadius: 5,
    background: "color-mix(in oklab, var(--fg) 3%, transparent)", ...style,
  }}>
    <div className="mono" style={{ position: "absolute", top: 6, left: 8, fontSize: 8, letterSpacing: "0.14em", color: "var(--fg-4)", textTransform: "uppercase" }}>
      {label}{role && <span style={{ color: "var(--accent)" }}> · {role}</span>}
    </div>
    {children}
  </div>
);

// Ladder row — one tab stop in sequence
const Rung = ({ n, name, role, label, note }) => (
  <div style={{ display: "grid", gridTemplateColumns: "24px 1fr", gap: 12, padding: "9px 0", borderBottom: "1px solid var(--hairline-2)", alignItems: "start" }}>
    <div style={{ width: 22, height: 22, borderRadius: "50%", background: A11Y_ACCENT, color: "var(--ink)", display: "grid", placeItems: "center", fontFamily: "var(--mono)", fontWeight: 800, fontSize: 11 }}>{n}</div>
    <div>
      <div style={{ display: "flex", gap: 8, alignItems: "baseline", flexWrap: "wrap" }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>{name}</span>
        <span className="mono" style={{ fontSize: 9, letterSpacing: "0.12em", color: "var(--accent)", textTransform: "uppercase" }}>{role}</span>
      </div>
      {label && <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", marginTop: 2 }}>aria-label "{label}"</div>}
      {note && <div style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 3, lineHeight: 1.4 }}>{note}</div>}
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// Desktop shell — landmarks + tab order
// ═══════════════════════════════════════════════════════════════════
const ScreenTabDesktop = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="home" />
      <div className="page">
        <TopBar crumbs={["Accessibility", "Keyboard · desktop shell"]} actions={
          <div className="btn btn-ghost btn-sm">Tab ⇥ walks this order</div>
        } />
        <div className="page-body">
          <div style={{ maxWidth: 720, marginBottom: 18 }}>
            <Eyebrow>Keyboard · the order Tab walks</Eyebrow>
            <h1 className="page-title" style={{ marginTop: 8 }}>Landmarks &amp; tab-order.</h1>
            <div className="page-sub">Five ARIA landmarks; Tab moves through them in DOM = reading order. A skip-link jumps straight to <span className="mono" style={{ color: "var(--fg-2)" }}>&lt;main&gt;</span>. Shift+Tab reverses; arrow keys move within composite widgets (nav, tablists, tables).</div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1.25fr 1fr", gap: 22, alignItems: "start" }}>
            {/* Wireframe diagram */}
            <div className="card" style={{ padding: 16 }}>
              <Eyebrow>Region map</Eyebrow>
              <div style={{ position: "relative", height: 420, marginTop: 12, border: "1px solid var(--hairline-2)", borderRadius: 6, background: "var(--bg)" }}>
                {/* skip link */}
                <div style={{ position: "absolute", top: 10, left: 12, padding: "5px 10px", border: "1px solid var(--accent)", borderRadius: 4, fontSize: 11, fontWeight: 600, color: "var(--accent)", background: "color-mix(in oklab, var(--accent) 10%, var(--bg))", zIndex: 6 }}>
                  Skip to content
                </div>
                <Stop n={1} style={{ top: 4, left: 116 }} />

                {/* sidebar */}
                <Region label="nav" role="banner+nav" style={{ top: 44, left: 12, width: 150, bottom: 12 }}>
                  <Stop n={2} style={{ top: 30, left: 12 }} />
                  <div style={{ position: "absolute", top: 30, left: 42, fontSize: 11, color: "var(--fg-2)", fontWeight: 600 }}>Brand → Today</div>
                  <Stop n={3} style={{ top: 70, left: 12 }} />
                  <div style={{ position: "absolute", top: 72, left: 42, fontSize: 11, color: "var(--fg-3)" }}>nav items…</div>
                  <div className="mono" style={{ position: "absolute", top: 96, left: 42, fontSize: 9, color: "var(--fg-4)" }}>↑↓ ARROWS WITHIN</div>
                  <Stop n={4} style={{ bottom: 16, left: 12 }} />
                  <div style={{ position: "absolute", bottom: 18, left: 42, fontSize: 11, color: "var(--fg-3)" }}>Account</div>
                </Region>

                {/* topbar */}
                <Region label="search + actions" role="banner" style={{ top: 44, left: 174, right: 12, height: 52 }}>
                  <Stop n={5} style={{ top: 15, left: 90 }} />
                  <div style={{ position: "absolute", top: 18, left: 118, fontSize: 11, color: "var(--fg-3)" }}>Search ⌘K</div>
                  <Stop n={6} style={{ top: 15, right: 56 }} />
                  <Stop n={7} style={{ top: 15, right: 16 }} />
                </Region>

                {/* main */}
                <Region label="main" role="main" style={{ top: 108, left: 174, right: 12, bottom: 12 }}>
                  <Stop n={8} style={{ top: 30, right: 18 }} />
                  <div style={{ position: "absolute", top: 33, right: 46, fontSize: 11, color: "var(--fg-3)" }}>Primary action</div>
                  <div style={{ position: "absolute", top: 64, left: 16, right: 16, fontSize: 12, fontWeight: 700, color: "var(--fg)" }}>h1 · page title <span className="mono" style={{ fontSize: 9, color: "var(--fg-4)", fontWeight: 400 }}>(focus target of skip-link)</span></div>
                  <Stop n={9} style={{ top: 110, left: 16 }} />
                  <Stop n={10} style={{ top: 110, left: 56 }} />
                  <Stop n={11} style={{ top: 110, left: 96 }} />
                  <div style={{ position: "absolute", top: 112, left: 130, fontSize: 11, color: "var(--fg-3)" }}>interactive content · DOM order</div>
                  <div className="mono" style={{ position: "absolute", bottom: 14, left: 16, fontSize: 9, color: "var(--fg-4)", letterSpacing: "0.12em" }}>CARDS &amp; ROWS FOLLOW IN READING ORDER →</div>
                </Region>
              </div>
            </div>

            {/* Ladder */}
            <div className="card" style={{ padding: "4px 18px 14px" }}>
              <div style={{ padding: "12px 0 2px" }}><Eyebrow>Sequence</Eyebrow></div>
              <Rung n={1} name="Skip to content" role="link" note="Visually hidden until focused; jumps focus to <main> and the h1." />
              <Rung n={2} name="Brand / Today" role="link" label="AIDSTATION — go to Today" />
              <Rung n={3} name="Nav items" role="navigation" note="Single tab stop into the list; ↑/↓ arrows move between items, aria-current=page on active." />
              <Rung n={4} name="Account" role="button" label="Account menu" note="Opens menu; focus moves into it, Esc returns here." />
              <Rung n={5} name="Search" role="combobox" label="Search — Command-K" />
              <Rung n={6} name="Topbar action A" role="button" note="Left-to-right." />
              <Rung n={7} name="Topbar action B" role="button" />
              <Rung n={8} name="Primary page action" role="button" note="First main action — e.g. Upload .FIT." />
              <Rung n={9} name="Content controls" role="varies" note="Cards, rows, toggles, links — in DOM = reading order, top-to-bottom, left-to-right." />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// Form — labels, errors, fieldsets (Account · change password)
// ═══════════════════════════════════════════════════════════════════
const ScreenTabForm = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="athlete" />
      <div className="page">
        <TopBar crumbs={["Accessibility", "Keyboard · forms"]} />
        <div className="page-body">
          <div style={{ maxWidth: 720, marginBottom: 18 }}>
            <Eyebrow>Keyboard · forms &amp; inputs</Eyebrow>
            <h1 className="page-title" style={{ marginTop: 8 }}>Every field speaks.</h1>
            <div className="page-sub">Each input has a programmatic label, hints wired via <span className="mono" style={{ color: "var(--fg-2)" }}>aria-describedby</span>, and errors via <span className="mono" style={{ color: "var(--fg-2)" }}>aria-invalid</span> + a live region. Grouped controls sit in a <span className="mono" style={{ color: "var(--fg-2)" }}>&lt;fieldset&gt;</span> with a <span className="mono" style={{ color: "var(--fg-2)" }}>&lt;legend&gt;</span>.</div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 22, alignItems: "start" }}>
            <div className="card" style={{ padding: 20, position: "relative" }}>
              <Eyebrow>Annotated · change password</Eyebrow>
              <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 14 }}>
                {[
                  ["Current password", "1", "label for=cur · type=password"],
                  ["New password", "2", "aria-describedby=pw-rules"],
                  ["Confirm new password", "3", "aria-describedby=pw-match"],
                ].map(([lbl, n, meta], i) => (
                  <div key={i} style={{ position: "relative" }}>
                    <div className="mono" style={{ fontSize: 9, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--fg-3)", marginBottom: 6 }}>● {lbl}</div>
                    <div style={{ display: "flex", alignItems: "center", gap: 10, height: 38, padding: "0 12px", background: "var(--bg-2)", border: "1px solid var(--hairline-2)", borderRadius: 4 }}>
                      <span className="mono" style={{ flex: 1, color: "var(--fg-3)", letterSpacing: "0.2em" }}>••••••••</span>
                      <Stop n={n} style={{ position: "static" }} />
                    </div>
                    <div className="mono" style={{ fontSize: 9, color: "var(--accent)", marginTop: 4 }}>{meta}</div>
                  </div>
                ))}
                <div style={{ padding: 10, background: "color-mix(in oklab, var(--accent) 7%, transparent)", borderRadius: 4 }}>
                  <div className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--accent)" }}>id=pw-rules · role=status · aria-live=polite</div>
                  <div style={{ fontSize: 11, color: "var(--fg-2)", marginTop: 4 }}>Strength + rules announce as you type.</div>
                </div>
                <div style={{ display: "flex", gap: 10, alignItems: "center", position: "relative" }}>
                  <div className="btn btn-primary" style={{ position: "relative" }}>Change password<Stop n="4" style={{ top: -10, right: -10 }} /></div>
                  <div className="btn btn-text btn-sm" style={{ color: "var(--fg-3)", position: "relative" }}>Forgot?<Stop n="5" style={{ top: -10, right: -10 }} ghost /></div>
                </div>
              </div>
            </div>

            <div className="card" style={{ padding: "4px 18px 14px" }}>
              <div style={{ padding: "12px 0 2px" }}><Eyebrow>Rules</Eyebrow></div>
              <Rung n="L" name="Label association" role="label/for" note="Every field has a <label for> or aria-label — never placeholder-as-label." />
              <Rung n="H" name="Hints" role="aria-describedby" note="Helper text + format hints linked to the field so SRs read them after the label." />
              <Rung n="E" name="Errors" role="aria-invalid + alert" note="On submit, invalid fields get aria-invalid=true; the message is an inline role=alert and focus moves to the first error." />
              <Rung n="G" name="Groups" role="fieldset/legend" note="Radio/checkbox sets and segmented toggles are grouped; the legend names the group." />
              <Rung n="S" name="Switches" role="switch" note="Toggles expose aria-checked; space/enter flips them." />
              <Rung n="R" name="Required" role="aria-required" note="Required fields marked programmatically, not just with a visual asterisk." />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// Modal — focus trap (Admin · delete user)
// ═══════════════════════════════════════════════════════════════════
const ScreenTabModal = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="athlete" />
      <div className="page">
        <TopBar crumbs={["Accessibility", "Keyboard · modal focus trap"]} />
        <div className="page-body">
          <div style={{ maxWidth: 720, marginBottom: 18 }}>
            <Eyebrow>Keyboard · dialogs</Eyebrow>
            <h1 className="page-title" style={{ marginTop: 8 }}>Focus stays in the room.</h1>
            <div className="page-sub">A dialog traps focus: Tab cycles only inside it, the background is <span className="mono" style={{ color: "var(--fg-2)" }}>inert</span>, Esc closes, and focus returns to the element that opened it.</div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1.1fr 1fr", gap: 22, alignItems: "start" }}>
            <div className="card" style={{ padding: 16 }}>
              <Eyebrow>role=dialog · aria-modal=true</Eyebrow>
              <div style={{ position: "relative", marginTop: 12, border: "1px solid var(--hairline-2)", borderRadius: 6, padding: 18, background: "var(--bg)" }}>
                <div className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--fg-4)", textTransform: "uppercase" }}>aria-labelledby ↓</div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 6 }}>
                  <div style={{ fontSize: 17, fontWeight: 700 }}>Delete sarah.k?</div>
                  <div className="btn btn-icon" style={{ position: "relative" }}><Ic d={I.x} size={14} /><Stop n={1} style={{ top: -10, right: -10 }} /></div>
                </div>
                <div style={{ fontSize: 12, color: "var(--fg-3)", marginTop: 8, lineHeight: 1.5 }}>Type-to-confirm field, then the two actions.</div>
                <div style={{ display: "flex", alignItems: "center", gap: 10, height: 38, padding: "0 12px", background: "var(--bg-2)", border: "1px solid var(--hairline-2)", borderRadius: 4, marginTop: 12, position: "relative" }}>
                  <span className="mono" style={{ flex: 1, color: "var(--fg)" }}>sarah.k</span>
                  <Stop n={2} style={{ position: "static" }} />
                </div>
                <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 16 }}>
                  <div className="btn btn-ghost" style={{ position: "relative" }}>Cancel<Stop n={3} style={{ top: -10, right: -10 }} /></div>
                  <div className="btn" style={{ background: "var(--bad)", color: "#fff", position: "relative" }}>Delete<Stop n={4} style={{ top: -10, right: -10 }} /></div>
                </div>
                <div className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--accent)", textTransform: "uppercase", marginTop: 14, textAlign: "center" }}>
                  ⤺ TAB AFTER 4 LOOPS BACK TO 1
                </div>
              </div>
            </div>

            <div className="card" style={{ padding: "4px 18px 14px" }}>
              <div style={{ padding: "12px 0 2px" }}><Eyebrow>Behavior</Eyebrow></div>
              <Rung n="①" name="On open" role="focus move" note="Focus moves to the dialog (the close button or first field), not left behind on the trigger." />
              <Rung n="②" name="Trap" role="focus trap" note="Tab / Shift+Tab cycle only through 1→4; they never reach the dimmed page behind." />
              <Rung n="③" name="Background" role="inert + aria-hidden" note="Everything outside the dialog is inert and hidden from the SR." />
              <Rung n="④" name="Esc" role="dismiss" note="Esc cancels (same as Cancel); never the destructive action." />
              <Rung n="⑤" name="On close" role="focus restore" note="Focus returns to the row's Delete button that opened the dialog." />
              <Rung n="⑥" name="Naming" role="labelledby/describedby" note="aria-labelledby = the title; aria-describedby = the body warning." />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// Mobile — tab-order, tabbar, FAB, gestures
// ═══════════════════════════════════════════════════════════════════
const ScreenTabMobile = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="home" />
      <div className="page">
        <TopBar crumbs={["Accessibility", "Keyboard · mobile + touch"]} />
        <div className="page-body">
          <div style={{ maxWidth: 720, marginBottom: 18 }}>
            <Eyebrow>Mobile · focus + assistive touch</Eyebrow>
            <h1 className="page-title" style={{ marginTop: 8 }}>Same order, thumb-first.</h1>
            <div className="page-sub">VoiceOver / TalkBack swipe order = DOM order: app bar → content → bottom tab bar. The tab bar is a <span className="mono" style={{ color: "var(--fg-2)" }}>nav</span> with <span className="mono" style={{ color: "var(--fg-2)" }}>aria-current</span>; the FAB is a labelled button. Targets ≥ 44px.</div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: 28, alignItems: "start" }}>
            {/* phone wireframe */}
            <div style={{ position: "relative", width: 230, height: 420, border: "1px solid var(--hairline)", borderRadius: 20, background: "var(--bg)", padding: 10 }}>
              <Region label="app bar" role="banner" style={{ top: 32, left: 10, right: 10, height: 44 }}>
                <Stop n={1} style={{ top: 11, left: 10 }} />
                <div style={{ position: "absolute", top: 14, left: 38, fontSize: 11, color: "var(--fg-3)" }}>Back</div>
                <Stop n={2} style={{ top: 11, right: 10 }} />
              </Region>
              <Region label="main" role="main" style={{ top: 84, left: 10, right: 10, bottom: 78 }}>
                <Stop n={3} style={{ top: 14, left: 12 }} />
                <Stop n={4} style={{ top: 50, left: 12 }} />
                <div style={{ position: "absolute", top: 16, left: 42, fontSize: 11, color: "var(--fg-3)" }}>content rows…</div>
              </Region>
              <Region label="tab bar" role="navigation" style={{ bottom: 10, left: 10, right: 10, height: 58 }}>
                {[5, 6, 7, 8, 9].map((n, i) => (
                  <Stop key={n} n={n} style={{ bottom: 18, left: 10 + i * 40, transform: i === 2 ? "translateY(-8px)" : "none", background: i === 2 ? A11Y_ACCENT : "var(--bg-3)", color: i === 2 ? "var(--ink)" : "var(--fg-2)", boxShadow: i === 2 ? "0 0 0 3px color-mix(in oklab, var(--accent) 22%, transparent)" : "none" }} />
                ))}
                <div className="mono" style={{ position: "absolute", top: 4, left: 90, fontSize: 8, color: "var(--accent)" }}>7 = FAB</div>
              </Region>
            </div>

            <div className="card" style={{ padding: "4px 18px 14px" }}>
              <div style={{ padding: "12px 0 2px" }}><Eyebrow>Sequence &amp; rules</Eyebrow></div>
              <Rung n={1} name="Back" role="button" label="Back" note="Top of swipe order; mirrors the OS back gesture." />
              <Rung n={2} name="App-bar action" role="button" label="e.g. Upload" />
              <Rung n={3} name="Content" role="main" note="Headings + rows in reading order; each row is one swipe stop." />
              <Rung n="●" name="Tab bar" role="navigation" note="A nav landmark; the active tab carries aria-current=page." />
              <Rung n="●" name="FAB (Quick log)" role="button" label="Quick log" note="Center action; visually raised but mid-sequence in the bar." />
              <Rung n="●" name="Targets" role="44px min" note="Every tab + the FAB meet the 44×44 minimum; spacing prevents mis-taps." />
              <Rung n="●" name="Gestures" role="non-exclusive" note="Swipe actions (e.g. on list rows) always have a visible button equivalent — never gesture-only." />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════
// ARIA component reference — the contract, per component
// ═══════════════════════════════════════════════════════════════════
const ARIA = [
  ["Sidebar", "nav", "<nav aria-label='Primary'>", "aria-current=page on active item", "↑/↓ between items, Enter activates"],
  ["Nav item", "link", "text content", "aria-current=page", "Enter / click"],
  ["Top bar", "banner", "—", "—", "—"],
  ["Search", "combobox", "aria-label='Search'", "aria-expanded, aria-controls=listbox", "⌘K opens · ↑/↓ · Enter · Esc"],
  ["Button (text)", "button", "visible text", "aria-disabled when off", "Enter / Space"],
  ["Button (icon)", "button", "aria-label (required)", "aria-pressed if toggle", "Enter / Space"],
  ["Chip / Pill", "status / text", "text; aria-label if glyph-only", "—", "— (non-interactive)"],
  ["Stat card", "group", "aria-label='<metric> <value>'", "—", "—"],
  ["Card (action)", "button / link", "heading text", "—", "Enter"],
  ["Tabs", "tablist / tab / tabpanel", "tab text", "aria-selected, tabpanel aria-labelledby", "←/→ between tabs, Enter selects"],
  ["Table", "table", "caption / aria-label", "th scope=col/row; aria-sort", "Tab to row, Enter opens"],
  ["Selectable row", "row", "row content", "aria-selected=true", "Enter / Space"],
  ["Text input", "textbox", "<label for>", "aria-describedby, aria-invalid, aria-required", "type"],
  ["Toggle", "switch", "label", "aria-checked", "Space / Enter"],
  ["Select", "combobox / listbox", "label", "aria-expanded, option aria-selected", "↑/↓ · Enter · Esc"],
  ["Drop zone", "button", "aria-label='Upload .FIT'", "aria-describedby formats", "Enter opens picker; drop also works"],
  ["Modal", "dialog", "aria-labelledby title", "aria-modal=true; bg inert", "Tab traps · Esc closes"],
  ["Notification feed", "feed / list", "aria-label='Activity'", "new items via aria-live=polite", "Tab through items"],
  ["Progress (plan gen)", "progressbar / status", "aria-label='Generating plan'", "aria-valuenow OR aria-live text", "—"],
  ["Chart / sparkline", "img", "aria-label='<summary>'", "decorative dups aria-hidden", "—"],
  ["Toast / alert", "alert / status", "message text", "aria-live=assertive (errors) / polite", "auto-announced"],
];

const ScreenAriaRef = () => (
  <div className="screen">
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      <Sidebar active="home" />
      <div className="page">
        <TopBar crumbs={["Accessibility", "ARIA reference"]} actions={
          <div className="btn btn-ghost btn-sm"><Ic d={I.download} size={11} /> Hand to engineering</div>
        } />
        <div className="page-body">
          <div style={{ maxWidth: 760, marginBottom: 18 }}>
            <Eyebrow>Screen reader · the contract</Eyebrow>
            <h1 className="page-title" style={{ marginTop: 8 }}>ARIA per component.</h1>
            <div className="page-sub">One row per reusable component — role, accessible name, the states it must expose, and its keyboard model. Build against this and every screen inherits correct semantics.</div>
          </div>

          <div className="card" style={{ padding: 0 }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
              <thead>
                <tr>
                  {["Component", "role", "Accessible name", "States / properties", "Keyboard"].map((h, i) => (
                    <th key={i} className="mono" style={{ padding: "11px 16px", textAlign: "left", fontSize: 9, letterSpacing: "0.16em", textTransform: "uppercase", color: "var(--fg-3)", fontWeight: 500, borderBottom: "1px solid var(--hairline-2)", position: "sticky", top: 0, background: "var(--bg-2)" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ARIA.map((r, i) => (
                  <tr key={i} style={{ borderBottom: i < ARIA.length - 1 ? "1px solid var(--hairline-2)" : "none" }}>
                    <td style={{ padding: "10px 16px", fontWeight: 600, whiteSpace: "nowrap" }}>{r[0]}</td>
                    <td className="mono" style={{ padding: "10px 16px", color: "var(--accent)", fontSize: 11, whiteSpace: "nowrap" }}>{r[1]}</td>
                    <td className="mono" style={{ padding: "10px 16px", color: "var(--fg-2)", fontSize: 11 }}>{r[2]}</td>
                    <td className="mono" style={{ padding: "10px 16px", color: "var(--fg-3)", fontSize: 11 }}>{r[3]}</td>
                    <td className="mono" style={{ padding: "10px 16px", color: "var(--fg-3)", fontSize: 11 }}>{r[4]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mono" style={{ fontSize: 10, letterSpacing: "0.14em", color: "var(--fg-4)", marginTop: 14, textTransform: "uppercase", lineHeight: 1.7 }}>
            ⓘ NAMES ARE EXAMPLES — USE THE VISIBLE TEXT WHERE ONE EXISTS. ICON-ONLY CONTROLS ALWAYS NEED AN EXPLICIT ARIA-LABEL.
          </div>
        </div>
      </div>
    </div>
  </div>
);

Object.assign(window, {
  ScreenTabDesktop, ScreenTabForm, ScreenTabModal, ScreenTabMobile, ScreenAriaRef,
});
