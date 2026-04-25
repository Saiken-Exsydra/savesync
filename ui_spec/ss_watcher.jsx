// SaveSync — Watcher Panel

function WatcherPanel({ watcherRunning, onToggle }) {
  const [log] = React.useState(WATCHER_LOG);
  const [showHealth, setShowHealth] = React.useState(false);
  const [processes] = React.useState([
    { name: 'eldenring.exe',         game: 'Elden Ring',       status: 'active',   pid: 14208, lastBackup: SAMPLE_GAMES[0].lastSync },
    { name: 'StardewModdingAPI.exe', game: 'Stardew Valley',   status: 'watching', pid: null,  lastBackup: SAMPLE_GAMES[3].lastSync },
    { name: 'hollow_knight.exe',     game: 'Hollow Knight',    status: 'watching', pid: null,  lastBackup: SAMPLE_GAMES[1].lastSync },
    { name: 'Hades.exe',             game: 'Hades',            status: 'watching', pid: null,  lastBackup: SAMPLE_GAMES[4].lastSync },
    { name: 'Cyberpunk2077.exe',     game: 'Cyberpunk 2077',   status: 'watching', pid: null,  lastBackup: SAMPLE_GAMES[5].lastSync },
    { name: 'bg3.exe',               game: "Baldur's Gate 3",  status: 'watching', pid: null,  lastBackup: SAMPLE_GAMES[6].lastSync },
    { name: 'Terraria.exe',          game: 'Terraria',         status: 'watching', pid: null,  lastBackup: SAMPLE_GAMES[7].lastSync },
  ]);
  const [backingUp, setBackingUp] = React.useState(null);
  const [tick, setTick] = React.useState(0);

  React.useEffect(() => {
    if (!watcherRunning) return;
    const t = setInterval(() => setTick(n => n + 1), 1000);
    return () => clearInterval(t);
  }, [watcherRunning]);

  const handleBackupNow = (proc) => {
    setBackingUp(proc.name);
    setTimeout(() => {
      setBackingUp(null);
      if (window.ssToast) window.ssToast(`${proc.game} backed up`, 'success');
    }, 1800);
  };

  const logColors = { backup: '#3dd68c', detect: '#6aacf5', interval: '#f0a830', sync: '#a89fff' };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Top bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '18px 24px 0', flexShrink: 0 }}>
        <div style={{ fontSize: 17, fontWeight: 700, color: '#e8eaf2', fontFamily: 'Inter, sans-serif', letterSpacing: '-0.3px' }}>
          Watcher
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 10, alignItems: 'center' }}>
          {watcherRunning && (
            <div style={{ fontSize: 11, color: '#4a5278', fontFamily: 'Inter, sans-serif' }}>
              Uptime: {Math.floor(tick / 60)}m {tick % 60}s
            </div>
          )}
          <button
            onClick={onToggle}
            style={{
              ...watcherStyles.toggleBtn,
              background: watcherRunning ? 'rgba(240,80,96,0.12)' : 'rgba(61,214,140,0.12)',
              color: watcherRunning ? '#f05060' : '#3dd68c',
              borderColor: watcherRunning ? 'rgba(240,80,96,0.3)' : 'rgba(61,214,140,0.3)',
            }}
            onMouseEnter={e => e.currentTarget.style.opacity = '0.8'}
            onMouseLeave={e => e.currentTarget.style.opacity = '1'}
          >
            {watcherRunning ? '⏹ Stop Watcher' : '▶ Start Watcher'}
          </button>
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 24px 24px', display: 'flex', flexDirection: 'column', gap: 16 }}>
        {/* Status hero card */}
        <div style={{
          background: '#0f1628', border: `1px solid ${watcherRunning ? 'rgba(61,214,140,0.2)' : '#1c2540'}`,
          borderRadius: 14, padding: '20px 24px',
          display: 'flex', alignItems: 'center', gap: 24,
          boxShadow: watcherRunning ? '0 0 40px rgba(61,214,140,0.04)' : 'none',
          transition: 'border-color 0.4s, box-shadow 0.4s',
        }}>
          {/* Radar ring */}
          <div style={{ position: 'relative', width: 72, height: 72, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            {watcherRunning && [1,2,3].map(i => (
              <div key={i} style={{
                position: 'absolute', borderRadius: '50%',
                border: '1px solid rgba(61,214,140,0.3)',
                animation: `radar ${1.8 + i * 0.4}s ease-out infinite`,
                animationDelay: `${i * 0.5}s`,
                width: 72, height: 72,
              }} />
            ))}
            <div style={{
              width: 48, height: 48, borderRadius: '50%',
              background: watcherRunning ? 'rgba(61,214,140,0.12)' : 'rgba(74,82,120,0.2)',
              border: `2px solid ${watcherRunning ? '#3dd68c' : '#4a5278'}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              transition: 'all 0.4s', zIndex: 1,
            }}>
              <div style={{ width: 12, height: 12, borderRadius: '50%', background: watcherRunning ? '#3dd68c' : '#4a5278', transition: 'background 0.4s' }} />
            </div>
          </div>

          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: '#e8eaf2', fontFamily: 'Inter, sans-serif' }}>
              {watcherRunning ? 'Watcher is running' : 'Watcher is stopped'}
            </div>
            <div style={{ fontSize: 12, color: '#8b93b3', marginTop: 4, fontFamily: 'Inter, sans-serif' }}>
              {watcherRunning
                ? `Monitoring ${processes.length} processes — 1 active (eldenring.exe)`
                : 'Start the watcher to enable automatic backups'}
            </div>
            {watcherRunning && (
              <div style={{ display: 'flex', gap: 16, marginTop: 12 }}>
                {[['Watching', processes.length], ['Active', 1], ['Backups today', 4]].map(([label, val]) => (
                  <div key={label}>
                    <div style={{ fontSize: 18, fontWeight: 700, color: '#e8eaf2', fontFamily: 'Inter, sans-serif' }}>{val}</div>
                    <div style={{ fontSize: 10, color: '#4a5278', fontFamily: 'Inter, sans-serif', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{label}</div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'flex-end' }}>
            <button style={watcherStyles.actionBtn}
              onMouseEnter={e => e.currentTarget.style.background = '#1c2848'}
              onMouseLeave={e => e.currentTarget.style.background = '#131c35'}>
              Add to Startup
            </button>
            <button style={watcherStyles.actionBtn} onClick={() => setShowHealth(true)}
              onMouseEnter={e => e.currentTarget.style.background = '#1c2848'}
              onMouseLeave={e => e.currentTarget.style.background = '#131c35'}>
              Health Check
            </button>
          </div>
        </div>

        {/* Process list */}
        <div>
          <div style={watcherStyles.sectionTitle}>Watched Processes</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {processes.map(proc => {
              const isActive = watcherRunning && proc.status === 'active';
              const isBacking = backingUp === proc.name;
              return (
                <div key={proc.name} style={{
                  background: '#0f1628', border: `1px solid ${isActive ? 'rgba(61,214,140,0.2)' : '#1c2540'}`,
                  borderRadius: 10, padding: '10px 14px',
                  display: 'flex', alignItems: 'center', gap: 12,
                  transition: 'border-color 0.3s',
                }}>
                  <div style={{ position: 'relative', width: 8, height: 8, flexShrink: 0 }}>
                    <div style={{ width: 8, height: 8, borderRadius: '50%', background: isActive ? '#3dd68c' : watcherRunning ? '#2a3a5a' : '#1c2540' }} />
                    {isActive && <div style={{ position: 'absolute', inset: -3, borderRadius: '50%', border: '1.5px solid #3dd68c', animation: 'pulsering 1.6s ease-out infinite' }} />}
                  </div>

                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12, fontWeight: 500, color: '#e8eaf2', fontFamily: 'Inter, sans-serif' }}>{proc.game}</div>
                    <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginTop: 2 }}>
                      <span style={{ fontSize: 10, color: '#4a5278', fontFamily: 'JetBrains Mono, monospace' }}>{proc.name}</span>
                      {proc.lastBackup && (
                        <span style={{ fontSize: 10, color: '#4a5278', fontFamily: 'Inter, sans-serif' }}>
                          · last backup {relTime(proc.lastBackup)}
                        </span>
                      )}
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0 }}>
                    {isActive && (
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        <div style={{ fontSize: 10, color: '#4a5278', fontFamily: 'JetBrains Mono, monospace' }}>PID {proc.pid}</div>
                        <span style={{ background: 'rgba(61,214,140,0.12)', color: '#3dd68c', fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 99, fontFamily: 'Inter, sans-serif' }}>RUNNING</span>
                      </div>
                    )}
                    {!isActive && watcherRunning && (
                      <span style={{ color: '#4a5278', fontSize: 10, fontFamily: 'Inter, sans-serif' }}>watching…</span>
                    )}
                    {/* Inline backup button */}
                    <button
                      onClick={() => handleBackupNow(proc)}
                      disabled={isBacking}
                      style={{
                        background: '#131c35', border: '1px solid #1c2540', color: isBacking ? '#4a5278' : '#8b93b3',
                        borderRadius: 6, padding: '4px 10px', fontSize: 10, cursor: isBacking ? 'default' : 'pointer',
                        fontFamily: 'Inter, sans-serif', transition: 'background 0.15s',
                      }}
                      onMouseEnter={e => { if (!isBacking) e.currentTarget.style.background = '#1c2848'; }}
                      onMouseLeave={e => e.currentTarget.style.background = '#131c35'}
                    >
                      {isBacking ? 'Backing up…' : 'Backup now'}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Activity log */}
        <div>
          <div style={watcherStyles.sectionTitle}>Activity Log</div>
          <div style={{ background: '#0c1022', border: '1px solid #1c2540', borderRadius: 10, overflow: 'hidden' }}>
            {log.map((entry, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'flex-start', gap: 12, padding: '10px 16px',
                borderBottom: i < log.length - 1 ? '1px solid #111827' : 'none',
              }}>
                <span style={{ fontSize: 10, color: '#4a5278', fontFamily: 'JetBrains Mono, monospace', flexShrink: 0, marginTop: 1 }}>{entry.time}</span>
                <div style={{ width: 4, height: 4, borderRadius: '50%', background: logColors[entry.type] || '#4a5278', flexShrink: 0, marginTop: 5 }} />
                <span style={{ fontSize: 12, color: '#8b93b3', fontFamily: 'Inter, sans-serif', lineHeight: 1.4 }}>{entry.msg}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {showHealth && <HealthCheckModal onClose={() => setShowHealth(false)} />}
    </div>
  );
}

const watcherStyles = {
  toggleBtn: {
    border: '1px solid', borderRadius: 8, padding: '8px 16px',
    fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'Inter, sans-serif',
    transition: 'opacity 0.15s',
  },
  actionBtn: {
    background: '#131c35', border: '1px solid #1c2540', color: '#8b93b3',
    borderRadius: 8, padding: '7px 14px', fontSize: 11, cursor: 'pointer',
    fontFamily: 'Inter, sans-serif', transition: 'background 0.15s',
  },
  sectionTitle: {
    fontSize: 11, color: '#4a5278', fontFamily: 'Inter, sans-serif',
    textTransform: 'uppercase', letterSpacing: '0.8px', fontWeight: 600,
    marginBottom: 10,
  },
};

Object.assign(window, { WatcherPanel });
