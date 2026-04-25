// SaveSync — Settings + Restore Panels

function SettingsPanel() {
  const [driveConnected, setDriveConnected] = React.useState(true);
  const [dbStatus] = React.useState({ version: '2024-03-15', games: 89241, updateAvailable: true });
  const [notifs, setNotifs] = React.useState({ backup: true, sync: true, health: true });
  const [startWithWindows, setStartWithWindows] = React.useState(true);
  const [searchQuery, setSearchQuery] = React.useState('');
  const [searchResults, setSearchResults] = React.useState(null);
  const [searching, setSearching] = React.useState(false);

  const fakeSearch = () => {
    if (!searchQuery) return;
    setSearching(true);
    setTimeout(() => {
      setSearchResults([
        { game: searchQuery, path: `C:/Users/User/AppData/Roaming/${searchQuery.replace(/ /g,'')}` },
        { game: searchQuery, path: `C:/Users/User/AppData/LocalLow/${searchQuery.replace(/ /g,'')}` },
      ]);
      setSearching(false);
    }, 700);
  };

  const Section = ({ title, children }) => (
    <div style={{ marginBottom: 24 }}>
      <div style={settingsStyles.sectionTitle}>{title}</div>
      <div style={settingsStyles.card}>{children}</div>
    </div>
  );

  const Row = ({ label, sub, children }) => (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 0', borderBottom: '1px solid #111827' }}>
      <div>
        <div style={{ fontSize: 13, color: '#e8eaf2', fontFamily: 'Inter, sans-serif', fontWeight: 500 }}>{label}</div>
        {sub && <div style={{ fontSize: 11, color: '#4a5278', fontFamily: 'Inter, sans-serif', marginTop: 2 }}>{sub}</div>}
      </div>
      {children}
    </div>
  );

  const Toggle = ({ value, onChange }) => (
    <div onClick={() => onChange(!value)} style={{
      width: 36, height: 20, borderRadius: 99, cursor: 'pointer',
      background: value ? '#7c6fff' : '#1c2540',
      position: 'relative', transition: 'background 0.2s',
    }}>
      <div style={{
        position: 'absolute', top: 3, left: value ? 18 : 3,
        width: 14, height: 14, borderRadius: '50%', background: '#fff',
        transition: 'left 0.2s', boxShadow: '0 1px 4px rgba(0,0,0,0.4)',
      }} />
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div style={{ padding: '18px 24px 0', flexShrink: 0 }}>
        <div style={{ fontSize: 17, fontWeight: 700, color: '#e8eaf2', fontFamily: 'Inter, sans-serif', letterSpacing: '-0.3px' }}>
          Settings
        </div>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 24px 32px' }}>

        {/* Google Drive */}
        <Section title="Google Drive">
          <Row label="Account" sub={driveConnected ? 'user@gmail.com' : 'Not connected'}>
            <button
              onClick={() => setDriveConnected(c => !c)}
              style={{
                ...settingsStyles.btn,
                background: driveConnected ? 'rgba(240,80,96,0.12)' : 'rgba(124,111,255,0.12)',
                color: driveConnected ? '#f05060' : '#7c6fff',
                borderColor: driveConnected ? 'rgba(240,80,96,0.3)' : 'rgba(124,111,255,0.3)',
              }}
              onMouseEnter={e => e.currentTarget.style.opacity = '0.8'}
              onMouseLeave={e => e.currentTarget.style.opacity = '1'}
            >{driveConnected ? 'Disconnect' : 'Connect'}</button>
          </Row>
          <Row label="Root folder" sub="All game backups are stored under this folder on Drive">
            <input defaultValue="SaveSync" style={settingsStyles.inlineInput} />
          </Row>
          <div style={{ padding: '12px 0', borderBottom: '1px solid #111827' }}>
            <div style={{ fontSize: 11, color: '#4a5278', fontFamily: 'Inter, sans-serif', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Status</div>
            <div style={{ display: 'flex', gap: 16 }}>
              {[['Space used', '2.3 GB'], ['Space free', '12.1 GB'], ['Games backed up', '5']].map(([k,v]) => (
                <div key={k}>
                  <div style={{ fontSize: 14, fontWeight: 600, color: '#e8eaf2', fontFamily: 'Inter, sans-serif' }}>{v}</div>
                  <div style={{ fontSize: 10, color: '#4a5278', fontFamily: 'Inter, sans-serif' }}>{k}</div>
                </div>
              ))}
            </div>
          </div>
        </Section>

        {/* Notifications */}
        <Section title="Notifications">
          {[
            ['backup', 'Backup complete', 'Toast when a backup finishes'],
            ['sync', 'Sync events', 'Toast when Drive sync runs'],
            ['health', 'Startup health check', 'Notification on Windows login'],
          ].map(([key, label, sub]) => (
            <Row key={key} label={label} sub={sub}>
              <Toggle value={notifs[key]} onChange={v => setNotifs(n => ({ ...n, [key]: v }))} />
            </Row>
          ))}
        </Section>

        {/* Startup */}
        <Section title="Startup">
          <Row label="Start with Windows" sub="Launches minimized to tray with watcher running">
            <Toggle value={startWithWindows} onChange={setStartWithWindows} />
          </Row>
          <Row label="Windows Startup folder" sub="C:/Users/User/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup">
            <button style={settingsStyles.btn}
              onMouseEnter={e => e.currentTarget.style.background = '#1c2848'}
              onMouseLeave={e => e.currentTarget.style.background = '#131c35'}>
              Open
            </button>
          </Row>
        </Section>

        {/* Database */}
        <Section title="Ludusavi Database">
          <Row label="Database version" sub={`${dbStatus.games.toLocaleString()} games indexed`}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <span style={{ fontSize: 11, color: '#4a5278', fontFamily: 'Inter, sans-serif' }}>{dbStatus.version}</span>
              {dbStatus.updateAvailable && (
                <span style={{ background: 'rgba(240,168,48,0.15)', color: '#f0a830', fontSize: 10, fontWeight: 600, padding: '2px 7px', borderRadius: 99, fontFamily: 'Inter, sans-serif' }}>
                  Update
                </span>
              )}
            </div>
          </Row>
          <div style={{ padding: '12px 0', borderBottom: '1px solid #111827' }}>
            <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
              <input
                style={{ ...settingsStyles.inlineInput, flex: 1, fontFamily: 'Inter, sans-serif' }}
                placeholder="Search save location database…"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && fakeSearch()}
              />
              <button style={{ ...settingsStyles.btn, padding: '7px 14px' }} onClick={fakeSearch}
                onMouseEnter={e => e.currentTarget.style.background = '#1c2848'}
                onMouseLeave={e => e.currentTarget.style.background = '#131c35'}>
                {searching ? '…' : 'Search'}
              </button>
            </div>
            {searchResults && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {searchResults.map((r,i) => (
                  <div key={i} style={{ background: '#0c1022', border: '1px solid #1c2540', borderRadius: 8, padding: '8px 12px' }}>
                    <div style={{ fontSize: 11, fontWeight: 500, color: '#e8eaf2', fontFamily: 'Inter, sans-serif' }}>{r.game}</div>
                    <div style={{ fontSize: 10, color: '#6aacf5', fontFamily: 'JetBrains Mono, monospace', marginTop: 2 }}>{r.path}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div style={{ padding: '12px 0', display: 'flex', gap: 8 }}>
            <button style={settingsStyles.btn}
              onMouseEnter={e => e.currentTarget.style.background = '#1c2848'}
              onMouseLeave={e => e.currentTarget.style.background = '#131c35'}>
              Download / Update
            </button>
            <button style={settingsStyles.btn}
              onMouseEnter={e => e.currentTarget.style.background = '#1c2848'}
              onMouseLeave={e => e.currentTarget.style.background = '#131c35'}>
              Rebuild Index
            </button>
          </div>
        </Section>

        {/* Danger zone */}
        <Section title="Reset">
          <div style={{ padding: '12px 0', display: 'flex', gap: 8 }}>
            <button style={{ ...settingsStyles.btn, color: '#f05060', borderColor: 'rgba(240,80,96,0.3)', background: 'rgba(240,80,96,0.06)' }}
              onMouseEnter={e => e.currentTarget.style.opacity = '0.8'}
              onMouseLeave={e => e.currentTarget.style.opacity = '1'}>
              Clear Config
            </button>
            <button style={{ ...settingsStyles.btn, color: '#f05060', borderColor: 'rgba(240,80,96,0.3)', background: 'rgba(240,80,96,0.06)' }}
              onMouseEnter={e => e.currentTarget.style.opacity = '0.8'}
              onMouseLeave={e => e.currentTarget.style.opacity = '1'}>
              Clear Thumbnail Cache
            </button>
          </div>
        </Section>

      </div>
    </div>
  );
}

// ── Restore Panel ─────────────────────────────────────────────
function RestorePanel() {
  const [driveGames] = React.useState([
    { name: 'Elden Ring',       files: 8,  lastUpdate: new Date(NOW - 2*3600*1000).toISOString(),  inLocal: true  },
    { name: 'Hollow Knight',    files: 4,  lastUpdate: new Date(NOW - 30*3600*1000).toISOString(), inLocal: true  },
    { name: 'Stardew Valley',   files: 12, lastUpdate: new Date(NOW - 15*60*1000).toISOString(),   inLocal: true  },
    { name: "Baldur's Gate 3",  files: 22, lastUpdate: new Date(NOW - 1*3600*1000).toISOString(),  inLocal: true  },
    { name: 'Hades',            files: 3,  lastUpdate: new Date(NOW - 5*86400*1000).toISOString(), inLocal: true  },
    { name: 'Dead Cells',       files: 2,  lastUpdate: new Date(NOW - 2*86400*1000).toISOString(), inLocal: false },
    { name: 'Ori and the Blind Forest', files: 5, lastUpdate: new Date(NOW - 7*86400*1000).toISOString(), inLocal: false },
  ]);
  const [restoring, setRestoring] = React.useState(null);
  const [restored, setRestored] = React.useState([]);

  const handleRestore = (game) => {
    setRestoring(game.name);
    setTimeout(() => {
      setRestoring(null);
      setRestored(r => [...r, game.name]);
    }, 1800);
  };

  const notInLocal = driveGames.filter(g => !g.inLocal);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div style={{ padding: '18px 24px 0', flexShrink: 0, display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{ fontSize: 17, fontWeight: 700, color: '#e8eaf2', fontFamily: 'Inter, sans-serif', letterSpacing: '-0.3px' }}>
          Restore from Drive
        </div>
        {notInLocal.length > 0 && (
          <button style={{
            marginLeft: 'auto', background: 'rgba(124,111,255,0.12)', color: '#7c6fff',
            border: '1px solid rgba(124,111,255,0.3)', borderRadius: 8, padding: '7px 14px',
            fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'Inter, sans-serif',
          }}
          onMouseEnter={e => e.currentTarget.style.opacity = '0.8'}
          onMouseLeave={e => e.currentTarget.style.opacity = '1'}>
            Add All Missing ({notInLocal.length})
          </button>
        )}
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 24px 24px' }}>
        {notInLocal.length > 0 && (
          <div style={{ marginBottom: 20 }}>
            <div style={settingsStyles.sectionTitle}>Not in local list</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {notInLocal.map(game => (
                <RestoreRow key={game.name} game={game} restoring={restoring === game.name} restored={restored.includes(game.name)} onRestore={handleRestore} />
              ))}
            </div>
          </div>
        )}

        <div>
          <div style={settingsStyles.sectionTitle}>All Drive games</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {driveGames.map(game => (
              <RestoreRow key={game.name} game={game} restoring={restoring === game.name} restored={restored.includes(game.name)} onRestore={handleRestore} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function RestoreRow({ game, restoring, restored, onRestore }) {
  return (
    <div style={{
      background: '#0f1628', border: '1px solid #1c2540', borderRadius: 10,
      padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 14,
    }}>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: '#e8eaf2', fontFamily: 'Inter, sans-serif' }}>{game.name}</div>
        <div style={{ display: 'flex', gap: 12, marginTop: 3 }}>
          <span style={{ fontSize: 11, color: '#4a5278', fontFamily: 'Inter, sans-serif' }}>{game.files} files</span>
          <span style={{ fontSize: 11, color: '#4a5278', fontFamily: 'Inter, sans-serif' }}>Updated {relTime(game.lastUpdate)}</span>
        </div>
      </div>
      {!game.inLocal && (
        <span style={{ background: 'rgba(240,168,48,0.1)', color: '#f0a830', fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 99, fontFamily: 'Inter, sans-serif' }}>
          Not local
        </span>
      )}
      {restored ? (
        <span style={{ fontSize: 11, color: '#3dd68c', fontFamily: 'Inter, sans-serif', fontWeight: 600 }}>✓ Restored</span>
      ) : restoring ? (
        <span style={{ fontSize: 11, color: '#8b93b3', fontFamily: 'Inter, sans-serif' }}>Restoring…</span>
      ) : (
        <button style={{
          background: '#131c35', border: '1px solid #1c2540', color: '#8b93b3',
          borderRadius: 8, padding: '7px 14px', fontSize: 11, cursor: 'pointer', fontFamily: 'Inter, sans-serif',
        }}
        onClick={() => onRestore(game)}
        onMouseEnter={e => e.currentTarget.style.background = '#1c2848'}
        onMouseLeave={e => e.currentTarget.style.background = '#131c35'}>
          ↓ Restore
        </button>
      )}
    </div>
  );
}

const settingsStyles = {
  sectionTitle: {
    fontSize: 11, color: '#4a5278', fontFamily: 'Inter, sans-serif',
    textTransform: 'uppercase', letterSpacing: '0.8px', fontWeight: 600,
    marginBottom: 8,
  },
  card: {
    background: '#0f1628', border: '1px solid #1c2540', borderRadius: 12,
    padding: '0 16px',
  },
  btn: {
    background: '#131c35', color: '#8b93b3', border: '1px solid #1c2540',
    borderRadius: 8, padding: '7px 12px', fontSize: 11, cursor: 'pointer',
    fontFamily: 'Inter, sans-serif', transition: 'background 0.15s, opacity 0.15s',
  },
  inlineInput: {
    background: '#0c1022', border: '1px solid #1c2540', borderRadius: 7,
    padding: '6px 10px', fontSize: 12, color: '#e8eaf2',
    fontFamily: 'JetBrains Mono, monospace', outline: 'none',
  },
};

Object.assign(window, { SettingsPanel, RestorePanel });
