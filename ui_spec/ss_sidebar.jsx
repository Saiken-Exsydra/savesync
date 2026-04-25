// SaveSync Sidebar component

function Sidebar({ active, onNav, watcherRunning, gameCount }) {
  const navItems = [
    { key: 'games',    label: 'Games',    icon: '⊞' },
    { key: 'watcher',  label: 'Watcher',  icon: '◉' },
    { key: 'restore',  label: 'Restore',  icon: '↓' },
    { key: 'settings', label: 'Settings', icon: '⚙' },
  ];

  return (
    <div style={sidebarStyles.root}>
      {/* Logo */}
      <div style={sidebarStyles.logo}>
        <div style={sidebarStyles.logoMark}>
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <circle cx="14" cy="14" r="13" fill="rgba(124,111,255,0.15)" stroke="#7c6fff" strokeWidth="1.5"/>
            <path d="M9 10.5 C9 8.5 10.5 7 12.5 7 C14.5 7 16 8.5 16 10.5 C16 11.8 15.3 13 14.2 13.7"
              stroke="#7c6fff" strokeWidth="2" strokeLinecap="round" fill="none"/>
            <path d="M19 17.5 C19 19.5 17.5 21 15.5 21 C13.5 21 12 19.5 12 17.5 C12 16.2 12.7 15 13.8 14.3"
              stroke="#a89fff" strokeWidth="2" strokeLinecap="round" fill="none"/>
            <circle cx="14" cy="14" r="2" fill="#7c6fff"/>
          </svg>
        </div>
        <div>
          <div style={sidebarStyles.logoText}>SaveSync</div>
          <div style={sidebarStyles.logoSub}>Save Manager</div>
        </div>
      </div>

      {/* Divider */}
      <div style={sidebarStyles.divider} />

      {/* Nav */}
      <nav style={{ flex: 1, padding: '8px 0' }}>
        {navItems.map(({ key, label, icon }) => {
          const isActive = active === key;
          return (
            <button
              key={key}
              onClick={() => onNav(key)}
              style={{
                ...sidebarStyles.navBtn,
                ...(isActive ? sidebarStyles.navBtnActive : {}),
              }}
              onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = 'rgba(124,111,255,0.08)'; }}
              onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'transparent'; }}
            >
              {isActive && <div style={sidebarStyles.navIndicator} />}
              <span style={{ ...sidebarStyles.navIcon, color: isActive ? '#7c6fff' : '#4a5278' }}>
                {icon}
              </span>
              <span style={{ color: isActive ? '#e8eaf2' : '#8b93b3', fontWeight: isActive ? 600 : 400 }}>
                {label}
              </span>
              {key === 'games' && gameCount > 0 && (
                <span style={{
                  ...sidebarStyles.badge,
                  background: isActive ? 'rgba(124,111,255,0.25)' : 'rgba(124,111,255,0.12)',
                  color: isActive ? '#a89fff' : '#5249cc',
                }}>{gameCount}</span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Watcher status chip */}
      <div style={sidebarStyles.watcherChip}>
        <div style={{ position: 'relative', width: 8, height: 8 }}>
          <div style={{
            width: 8, height: 8, borderRadius: '50%',
            background: watcherRunning ? '#3dd68c' : '#4a5278',
          }} />
          {watcherRunning && (
            <div style={sidebarStyles.pulse} />
          )}
        </div>
        <span style={{ color: watcherRunning ? '#3dd68c' : '#4a5278', fontSize: 11, fontWeight: 500 }}>
          Watcher {watcherRunning ? 'running' : 'stopped'}
        </span>
      </div>
    </div>
  );
}

const sidebarStyles = {
  root: {
    width: 210, minWidth: 210,
    background: '#0c1022',
    borderRight: '1px solid #1c2540',
    display: 'flex', flexDirection: 'column',
    height: '100%',
    userSelect: 'none',
  },
  logo: {
    display: 'flex', alignItems: 'center', gap: 10,
    padding: '22px 18px 18px',
  },
  logoMark: { flexShrink: 0 },
  logoText: {
    fontSize: 15, fontWeight: 700, color: '#e8eaf2', letterSpacing: '-0.3px',
  },
  logoSub: { fontSize: 10, color: '#4a5278', marginTop: 1, letterSpacing: '0.3px', textTransform: 'uppercase' },
  divider: { height: 1, background: '#1c2540', margin: '0 18px 8px' },
  navBtn: {
    display: 'flex', alignItems: 'center', gap: 10,
    width: '100%', padding: '11px 18px', border: 'none', cursor: 'pointer',
    background: 'transparent', textAlign: 'left', position: 'relative',
    fontSize: 13, fontFamily: 'Inter, sans-serif',
    transition: 'background 0.15s',
    borderRadius: 0,
  },
  navBtnActive: {
    background: 'rgba(124,111,255,0.1)',
  },
  navIndicator: {
    position: 'absolute', left: 0, top: '50%', transform: 'translateY(-50%)',
    width: 3, height: 20, borderRadius: '0 3px 3px 0',
    background: '#7c6fff',
    boxShadow: '0 0 8px rgba(124,111,255,0.6)',
  },
  navIcon: { fontSize: 14, width: 18, textAlign: 'center', flexShrink: 0 },
  badge: {
    marginLeft: 'auto', fontSize: 10, fontWeight: 600,
    padding: '2px 6px', borderRadius: 99,
  },
  watcherChip: {
    display: 'flex', alignItems: 'center', gap: 8,
    padding: '14px 18px',
    borderTop: '1px solid #1c2540',
    marginTop: 8,
  },
  pulse: {
    position: 'absolute', top: -3, left: -3,
    width: 14, height: 14, borderRadius: '50%',
    border: '1.5px solid #3dd68c',
    animation: 'pulsering 1.6s ease-out infinite',
  },
};

Object.assign(window, { Sidebar });
