/* AIDSTATION redesign — shell components
   Sidebar nav (desktop) · top bar · mobile statusbar/appbar/tabbar
   Reusable icons, the brand mark, and small atoms. */

// ─── Brand mark + wordmark ───────────────────────────────────────
const AsMark = ({ size = 26, chip = "#E8893A" }) => (
  <svg width={size} height={size} viewBox="0 0 100 100" aria-hidden="true">
    <path d="M26 30 L74 30 L67 84 Q 50 92, 33 84 Z" fill="none" stroke="currentColor" strokeWidth="6" strokeLinejoin="round" />
    <line x1="26" y1="30" x2="74" y2="30" stroke="currentColor" strokeWidth="6" strokeLinecap="round" />
    <path d="M40 54 L48 60 L40 66" stroke="currentColor" strokeWidth="5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    <rect x="53" y="55" width="9" height="10" fill={chip} />
  </svg>
);

const Wordmark = ({ children = ["AID", "STATION"] }) => (
  <span className="wordmark">
    <span className="b">{children[0]}</span><span className="r">{children[1]}</span>
  </span>
);

// ─── Icon set (mono line, 16px viewBox 24) ───────────────────────
const I = {
  // navigation icons
  home: <path d="M3 11l9-8 9 8v10a1 1 0 0 1-1 1h-5v-7h-6v7H4a1 1 0 0 1-1-1V11z" />,
  plan: <path d="M4 6h16M4 12h16M4 18h10" />,
  workout: <path d="M2 12h2m16 0h2M6 8v8m12-8v8M9 6v12m6-12v12" />,
  log: <path d="M5 4h11l3 3v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1zM9 11h6M9 15h6M9 7h4" />,
  library: <path d="M4 5h6v14H4zM10 5h4v14h-4zM14 6l4 1-3 13-4-1z" />,
  gear: <path d="M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zm9 4l-2-1 1-2-2-2-2 1-1-2h-3l-1 2-2-1-2 2 1 2-2 1v3l2 1-1 2 2 2 2-1 1 2h3l1-2 2 1 2-2-1-2 2-1z" />,
  link: <path d="M10 14a4 4 0 0 0 5.66 0l3-3a4 4 0 0 0-5.66-5.66l-1 1M14 10a4 4 0 0 0-5.66 0l-3 3a4 4 0 0 0 5.66 5.66l1-1" />,
  athlete: <path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 20a8 8 0 0 1 16 0" />,
  insights: <path d="M4 19V5M4 19h16M8 15l3-5 3 3 4-7" />,
  // utility
  bell: <path d="M6 18V11a6 6 0 1 1 12 0v7M3 18h18M10 21h4" />,
  search: <path d="M11 4a7 7 0 1 1 0 14 7 7 0 0 1 0-14zm9 16l-4-4" />,
  plus: <path d="M12 5v14M5 12h14" />,
  check: <path d="M5 13l4 4 10-10" />,
  x: <path d="M6 6l12 12M18 6L6 18" />,
  arrow: <path d="M5 12h14m-5-5l5 5-5 5" />,
  download: <path d="M12 4v12m-5-5l5 5 5-5M4 20h16" />,
  chevR: <path d="M9 6l6 6-6 6" />,
  chevL: <path d="M15 6l-6 6 6 6" />,
  chevD: <path d="M6 9l6 6 6-6" />,
  clock: <path d="M12 4a8 8 0 1 1 0 16 8 8 0 0 1 0-16zM12 8v4l3 2" />,
  flame: <path d="M12 3c1 4 5 5 5 10a5 5 0 0 1-10 0c0-2 1-3 2-4-1 3 1 4 2 4 0-3-1-5 1-10z" />,
  heart: <path d="M12 20s-7-4-7-10a4 4 0 0 1 7-3 4 4 0 0 1 7 3c0 6-7 10-7 10z" />,
  pin: <path d="M12 21s-7-7-7-12a7 7 0 0 1 14 0c0 5-7 12-7 12zM12 11a2 2 0 1 0 0-4 2 2 0 0 0 0 4z" />,
  cloud: <path d="M7 18a5 5 0 1 1 1-9.9A6 6 0 0 1 19 11a4 4 0 0 1-1 7z" />,
  weight: <path d="M5 7h14l-1 13H6L5 7zM9 7V5a3 3 0 0 1 6 0v2" />,
  shoe: <path d="M3 14c0-3 2-3 4-5l3-4 3 1 1 4 6 2v4c0 1-1 2-2 2H5a2 2 0 0 1-2-2v-2z" />,
  menu: <path d="M4 6h16M4 12h16M4 18h16" />,
  more: <path d="M5 12h.01M12 12h.01M19 12h.01" />,
  bolt: <path d="M13 3L4 14h7l-1 7 9-11h-7z" />,
  upload: <path d="M12 16V4m-5 5l5-5 5 5M4 20h16" />,
  body: <path d="M12 6a2 2 0 1 0 0-4 2 2 0 0 0 0 4zm-3 3l3-1 3 1 2 7-2 1-1-4v9h-2v-5h-2v5h-2v-9l-1 4-2-1z" />,
  pulse: <path d="M3 12h4l2-6 4 12 2-6h6" />,
  bandage: <path d="M5 14L14 5a3.5 3.5 0 0 1 5 5l-9 9a3.5 3.5 0 0 1-5-5zM9 9l6 6" />,
  sun: <path d="M12 5V3m0 18v-2m7-7h2M3 12h2m13.5-6.5l1.4-1.4M4.1 19.9l1.4-1.4m13 0l1.4 1.4M4.1 4.1l1.4 1.4M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z" />,
};
const Ic = ({ d, size = 16, sw = 1.6 }) => (
  <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">
    {d}
  </svg>
);

// ─── Desktop sidebar ─────────────────────────────────────────────
const NAV = [
  {
    section: "Train",
    items: [
      { key: "home",    label: "Today",      icon: I.home },
      { key: "plan",    label: "Plan",       icon: I.plan },
      { key: "workout", label: "Workouts",   icon: I.workout, badge: "12" },
      { key: "library", label: "Exercises",  icon: I.library },
    ],
  },
  {
    section: "Log",
    items: [
      { key: "log",      label: "Quick log",  icon: I.log },
      { key: "insights", label: "Wellness",   icon: I.pulse },
    ],
  },
  {
    section: "Account",
    items: [
      { key: "athlete",  label: "Athlete",     icon: I.athlete },
      { key: "locations", label: "Locations",  icon: I.pin },
      { key: "link",     label: "Connections", icon: I.link },
    ],
  },
];

const Sidebar = ({ active = "home" }) => (
  <aside className="sidebar">
    <div className="sidebar-brand">
      <AsMark size={24} />
      <Wordmark />
    </div>
    {NAV.map((sec) => (
      <div key={sec.section}>
        <div className="sidebar-section">{sec.section}</div>
        {sec.items.map((it) => (
          <div key={it.key} className={"sidebar-item" + (it.key === active ? " active" : "")}>
            <Ic d={it.icon} />
            <span>{it.label}</span>
            {it.badge && <span className="badge">{it.badge}</span>}
          </div>
        ))}
      </div>
    ))}
    <div className="sidebar-foot">
      <div className="avatar">AH</div>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ fontSize: 12, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>Andrew Horn</div>
        <div className="mono" style={{ fontSize: 9, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--fg-3)" }}>Pro · WK 8</div>
      </div>
      <Ic d={I.more} />
    </div>
  </aside>
);

// ─── Top bar (breadcrumb + search + actions) ─────────────────────
const TopBar = ({ crumbs = [], actions = null, search = true }) => (
  <div className="topbar">
    <div className="crumbs">
      {crumbs.map((c, i) => (
        <React.Fragment key={i}>
          {i > 0 && <span style={{ opacity: 0.5 }}>/</span>}
          {i === crumbs.length - 1 ? <b>{c}</b> : <span>{c}</span>}
        </React.Fragment>
      ))}
    </div>
    <div className="spacer" />
    {search && (
      <div className="search">
        <Ic d={I.search} size={13} />
        <span>Search workouts, exercises…</span>
        <kbd>⌘K</kbd>
      </div>
    )}
    <div className="btn btn-icon"><Ic d={I.bell} size={14} /></div>
    {actions}
  </div>
);

// ─── Mobile chrome ───────────────────────────────────────────────
const StatusBar = ({ light = false }) => (
  <div className="statusbar" style={light ? { color: "var(--ink)" } : null}>
    <span>9:41</span>
    <div className="right">
      <svg width="16" height="11" viewBox="0 0 16 11" fill="currentColor"><path d="M0 8h2v3H0zM4 6h2v5H4zM8 4h2v7H8zM12 1h2v10h-2z" /></svg>
      <svg width="14" height="10" viewBox="0 0 14 10" fill="none" stroke="currentColor" strokeWidth="1.2"><path d="M1 4a8 8 0 0 1 12 0M3 6.5a5 5 0 0 1 8 0M6 9h2" /></svg>
      <svg width="22" height="10" viewBox="0 0 22 10" fill="none" stroke="currentColor" strokeWidth="1"><rect x="0.5" y="0.5" width="18" height="9" rx="2" /><rect x="2" y="2" width="13" height="6" fill="currentColor" /><path d="M20 3v4" strokeWidth="1.2" /></svg>
    </div>
  </div>
);

const AppBar = ({ title, left, right }) => (
  <div className="appbar">
    {left || <Ic d={I.menu} size={22} />}
    <div className="title" style={{ flex: 1 }}>{title}</div>
    {right || <Ic d={I.bell} size={20} />}
  </div>
);

const TabBar = ({ active = "home" }) => {
  const tabs = [
    { key: "home",  label: "Today",   icon: I.home },
    { key: "plan",  label: "Plan",    icon: I.plan },
    { key: "log",   label: "Log",     fab: true, icon: I.plus },
    { key: "stats", label: "Stats",   icon: I.insights },
    { key: "me",    label: "Athlete", icon: I.athlete },
  ];
  return (
    <div className="tabbar">
      {tabs.map((t) => (
        <div key={t.key} className={"tab" + (t.key === active ? " active" : "") + (t.fab ? " fab" : "")}>
          {t.fab ? (
            <>
              <div className="fab-btn"><Ic d={t.icon} size={22} sw={2} /></div>
              <span style={{ marginTop: 2 }}>{t.label}</span>
            </>
          ) : (
            <>
              <Ic d={t.icon} size={22} sw={1.6} />
              <span>{t.label}</span>
            </>
          )}
        </div>
      ))}
    </div>
  );
};

// ─── Tiny utility components ─────────────────────────────────────
const Eyebrow = ({ children, accent = false }) => (
  <span className={"eyebrow" + (accent ? " accent" : "")}>{children}</span>
);

const Pill = ({ children, tone }) => (
  <span className={"chip" + (tone ? " " + tone : "")}>{children}</span>
);

// expose
Object.assign(window, {
  AsMark, Wordmark, Ic, I,
  Sidebar, TopBar,
  StatusBar, AppBar, TabBar,
  Eyebrow, Pill,
});
