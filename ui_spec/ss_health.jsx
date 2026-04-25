// SaveSync — Health Check Modal

function HealthCheckModal({ onClose }) {
  const [phase, setPhase] = React.useState('idle'); // idle | scanning | done
  const [results, setResults] = React.useState([]);
  const [current, setCurrent] = React.useState('');

  const runCheck = () => {
    setPhase('scanning');
    setResults([]);

    const checks = SAMPLE_GAMES.map(g => ({
      name: g.name,
      savePath: g.savePath,
      drive: g.drive,
      lastSync: g.lastSync,
    }));

    // Simulate progressive scan
    let i = 0;
    const tick = setInterval(() => {
      if (i >= checks.length) {
        clearInterval(tick);
        setCurrent('');
        setPhase('done');
        const issues = checks.filter((_, idx) => idx === 2 || idx === 4).length;
        if (window.ssToast) {
          if (issues === 0) window.ssToast('Health check complete — all games OK', 'success');
          else window.ssToast(`Health check found ${issues} issue(s)`, 'warning');
        }
        return;
      }
      const g = checks[i];
      setCurrent(g.name);
      const hasSavePath = i !== 2; // Celeste: pretend path missing
      const driveOk = g.drive ? (i !== 4) : null; // Hades: pretend drive stale
      const syncFresh = (NOW - new Date(g.lastSync)) < 7 * 86400 * 1000;

      setResults(r => [...r, {
        name: g.name,
        savePath: hasSavePath,
        drive: driveOk,
        syncFresh,
        issues: (!hasSavePath ? 1 : 0) + (driveOk === false ? 1 : 0) + (!syncFresh ? 1 : 0),
      }]);
      i++;
    }, 400);
  };

  const statusDot = (ok) => (
    <span style={{ fontSize: 11, fontWeight: 600, fontFamily: 'Inter, sans-serif',
      color: ok ? '#3dd68c' : '#f05060' }}>
      {ok ? '✓' : '✕'}
    </span>
  );

  const totalIssues = results.reduce((sum, r) => sum + r.issues, 0);

  return (
    <div style={hcStyles.overlay} onClick={onClose}>
      <div style={hcStyles.modal} onClick={e => e.stopPropagation()}>

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <div>
            <div style={hcStyles.title}>Health Check</div>
            <div style={{ fontSize: 11, color: '#4a5278', fontFamily: 'Inter, sans-serif', marginTop: 2 }}>
              Verify save paths, Drive folders, and sync timestamps
            </div>
          </div>
          <button onClick={onClose} style={hcStyles.closeBtn}>✕</button>
        </div>

        {/* Idle state */}
        {phase === 'idle' && (
          <div style={{ textAlign: 'center', padding: '32px 0 24px' }}>
            <div style={{
              width: 64, height: 64, borderRadius: '50%',
              background: 'rgba(124,111,255,0.1)', border: '1.5px solid rgba(124,111,255,0.3)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              margin: '0 auto 16px', fontSize: 26,
            }}>🔍</div>
            <div style={{ fontSize: 13, color: '#8b93b3', fontFamily: 'Inter, sans-serif', maxWidth: 320, margin: '0 auto 24px', lineHeight: 1.5 }}>
              Scans all {SAMPLE_GAMES.length} games — checks save paths, Drive folders, and compares timestamps.
            </div>
            <button style={hcStyles.btnPrimary} onClick={runCheck}
              onMouseEnter={e => e.currentTarget.style.background = '#5249cc'}
              onMouseLeave={e => e.currentTarget.style.background = '#7c6fff'}>
              Run Health Check
            </button>
          </div>
        )}

        {/* Scanning */}
        {phase === 'scanning' && (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#7c6fff', animation: 'pulsering 1s ease-out infinite', position: 'relative' }} />
              <span style={{ fontSize: 12, color: '#8b93b3', fontFamily: 'Inter, sans-serif' }}>
                Scanning{current ? `: ${current}` : '…'}
              </span>
            </div>
            <div style={{ background: '#1c2540', borderRadius: 99, height: 3, overflow: 'hidden', marginBottom: 16 }}>
              <div style={{
                height: '100%', borderRadius: 99, background: '#7c6fff',
                width: `${(results.length / SAMPLE_GAMES.length) * 100}%`,
                transition: 'width 0.35s ease',
              }} />
            </div>
            <ResultsList results={results} statusDot={statusDot} />
          </div>
        )}

        {/* Done */}
        {phase === 'done' && (
          <div>
            {/* Summary */}
            <div style={{
              display: 'flex', gap: 10, marginBottom: 16,
              background: totalIssues === 0 ? 'rgba(61,214,140,0.07)' : 'rgba(240,168,48,0.07)',
              border: `1px solid ${totalIssues === 0 ? 'rgba(61,214,140,0.2)' : 'rgba(240,168,48,0.2)'}`,
              borderRadius: 10, padding: '12px 16px', alignItems: 'center',
            }}>
              <span style={{ fontSize: 20 }}>{totalIssues === 0 ? '✅' : '⚠️'}</span>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: '#e8eaf2', fontFamily: 'Inter, sans-serif' }}>
                  {totalIssues === 0 ? 'All games healthy' : `${totalIssues} issue${totalIssues > 1 ? 's' : ''} found`}
                </div>
                <div style={{ fontSize: 11, color: '#8b93b3', fontFamily: 'Inter, sans-serif', marginTop: 2 }}>
                  {results.length} games scanned · {results.filter(r => r.issues === 0).length} OK
                </div>
              </div>
              <button style={{ ...hcStyles.btnGhost, marginLeft: 'auto' }} onClick={runCheck}
                onMouseEnter={e => e.currentTarget.style.background = '#1c2848'}
                onMouseLeave={e => e.currentTarget.style.background = '#131c35'}>
                Re-scan
              </button>
            </div>
            <ResultsList results={results} statusDot={statusDot} />
            <div style={{ marginTop: 16, display: 'flex', justifyContent: 'flex-end' }}>
              <button style={hcStyles.btnPrimary} onClick={onClose}
                onMouseEnter={e => e.currentTarget.style.background = '#5249cc'}
                onMouseLeave={e => e.currentTarget.style.background = '#7c6fff'}>
                Close
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function ResultsList({ results, statusDot }) {
  if (!results.length) return null;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 320, overflowY: 'auto' }}>
      {results.map(r => (
        <div key={r.name} style={{
          background: r.issues > 0 ? 'rgba(240,168,48,0.05)' : '#0c1022',
          border: `1px solid ${r.issues > 0 ? 'rgba(240,168,48,0.2)' : '#1c2540'}`,
          borderRadius: 8, padding: '9px 14px',
          display: 'flex', alignItems: 'center', gap: 12,
        }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 12, fontWeight: 500, color: '#e8eaf2', fontFamily: 'Inter, sans-serif' }}>{r.name}</div>
            {r.issues > 0 && (
              <div style={{ display: 'flex', gap: 10, marginTop: 4, flexWrap: 'wrap' }}>
                {!r.savePath && <span style={hcStyles.issueBadge}>Save path missing</span>}
                {r.drive === false && <span style={hcStyles.issueBadge}>Drive out of sync</span>}
                {!r.syncFresh && r.issues === 1 && r.savePath && r.drive !== false && <span style={hcStyles.issueBadge}>Backup overdue</span>}
              </div>
            )}
          </div>
          {/* Check columns */}
          <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
            <div style={{ textAlign: 'center' }}>
              {statusDot(r.savePath)}
              <div style={{ fontSize: 9, color: '#4a5278', fontFamily: 'Inter, sans-serif' }}>Path</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              {r.drive === null
                ? <span style={{ fontSize: 11, color: '#4a5278' }}>—</span>
                : statusDot(r.drive)}
              <div style={{ fontSize: 9, color: '#4a5278', fontFamily: 'Inter, sans-serif' }}>Drive</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              {statusDot(r.syncFresh)}
              <div style={{ fontSize: 9, color: '#4a5278', fontFamily: 'Inter, sans-serif' }}>Sync</div>
            </div>
          </div>
          {r.issues > 0 && (
            <button style={hcStyles.fixBtn}
              onMouseEnter={e => e.currentTarget.style.background = '#1c2848'}
              onMouseLeave={e => e.currentTarget.style.background = '#131c35'}>
              Fix
            </button>
          )}
        </div>
      ))}
    </div>
  );
}

const hcStyles = {
  overlay: {
    position: 'fixed', inset: 0, background: 'rgba(7,9,26,0.85)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    zIndex: 1000, backdropFilter: 'blur(4px)',
  },
  modal: {
    background: '#0f1628', border: '1px solid #1c2540', borderRadius: 16,
    padding: '24px 28px', width: 560, maxHeight: '85vh', overflowY: 'auto',
    boxShadow: '0 24px 80px rgba(7,9,26,0.8)',
  },
  title: { fontSize: 16, fontWeight: 700, color: '#e8eaf2', fontFamily: 'Inter, sans-serif' },
  closeBtn: {
    background: 'none', border: 'none', color: '#4a5278', fontSize: 16,
    cursor: 'pointer', padding: '4px 8px', borderRadius: 6, fontFamily: 'Inter, sans-serif',
  },
  btnPrimary: {
    background: '#7c6fff', color: '#fff', border: 'none', borderRadius: 8,
    padding: '9px 20px', fontSize: 12, fontWeight: 600, cursor: 'pointer',
    fontFamily: 'Inter, sans-serif', transition: 'background 0.15s',
  },
  btnGhost: {
    background: '#131c35', color: '#8b93b3', border: '1px solid #1c2540',
    borderRadius: 8, padding: '7px 14px', fontSize: 11, cursor: 'pointer',
    fontFamily: 'Inter, sans-serif', transition: 'background 0.15s',
  },
  fixBtn: {
    background: '#131c35', color: '#8b93b3', border: '1px solid #1c2540',
    borderRadius: 6, padding: '5px 10px', fontSize: 10, cursor: 'pointer',
    fontFamily: 'Inter, sans-serif', transition: 'background 0.15s', flexShrink: 0,
  },
  issueBadge: {
    background: 'rgba(240,168,48,0.12)', color: '#f0a830',
    fontSize: 10, fontWeight: 500, padding: '2px 7px', borderRadius: 99,
    fontFamily: 'Inter, sans-serif',
  },
};

Object.assign(window, { HealthCheckModal });
