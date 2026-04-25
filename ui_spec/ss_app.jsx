// SaveSync — App Shell + Tweaks

function App() {
  const [panel, setPanel] = React.useState(() => localStorage.getItem('ss_panel') || 'games');
  const [prevPanel, setPrevPanel] = React.useState(null);
  const [transitioning, setTransitioning] = React.useState(false);
  const [watcherRunning, setWatcherRunning] = React.useState(true);
  const [tweaksVisible, setTweaksVisible] = React.useState(false);
  const [tweaks, setTweaks] = React.useState(() => {
    try { return JSON.parse(localStorage.getItem('ss_tweaks') || 'null') || TWEAK_DEFAULTS; }
    catch { return TWEAK_DEFAULTS; }
  });

  // Panel transition
  const navigateTo = (next) => {
    if (next === panel || transitioning) return;
    setTransitioning(true);
    setTimeout(() => {
      setPrevPanel(panel);
      setPanel(next);
      localStorage.setItem('ss_panel', next);
      setTransitioning(false);
    }, 180);
  };

  const setTweak = (k, v) => {
    setTweaks(t => {
      const next = { ...t, [k]: v };
      localStorage.setItem('ss_tweaks', JSON.stringify(next));
      window.parent.postMessage({ type: '__edit_mode_set_keys', edits: next }, '*');
      return next;
    });
  };

  // Tweaks toggle from host
  React.useEffect(() => {
    const handler = (e) => {
      if (e.data?.type === '__activate_edit_mode') setTweaksVisible(true);
      if (e.data?.type === '__deactivate_edit_mode') setTweaksVisible(false);
    };
    window.addEventListener('message', handler);
    window.parent.postMessage({ type: '__edit_mode_available' }, '*');
    return () => window.removeEventListener('message', handler);
  }, []);

  const renderPanel = () => {
    switch (panel) {
      case 'games':    return <GamesPanel tweaks={tweaks} />;
      case 'watcher':  return <WatcherPanel watcherRunning={watcherRunning} onToggle={() => setWatcherRunning(r => !r)} />;
      case 'restore':  return <RestorePanel />;
      case 'settings': return <SettingsPanel />;
      default:         return null;
    }
  };

  // Status bar last backup
  const lastBackup = SAMPLE_GAMES.reduce((a, g) => g.lastSync > a ? g.lastSync : a, '');
  const lastRel = relTime(lastBackup);

  return (
    <div style={{ ...appStyles.root, '--accent': tweaks.accent || '#7c6fff', fontFamily: 'Inter, sans-serif' }}>
      <Sidebar
        active={panel}
        onNav={navigateTo}
        watcherRunning={watcherRunning}
        gameCount={SAMPLE_GAMES.length}
      />

      {/* Main column */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
        {/* Content area */}
        <div style={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
          <div style={{
            ...appStyles.panelWrap,
            opacity: transitioning ? 0 : 1,
            transform: transitioning ? 'translateY(10px)' : 'translateY(0)',
            transition: 'opacity 0.18s ease, transform 0.18s ease',
          }}>
            {renderPanel()}
          </div>
        </div>

        {/* Status bar */}
        <div style={appStyles.statusBar}>
          <span style={appStyles.statusText}>Last backup: {lastRel}</span>
          <span style={{ ...appStyles.statusText, marginLeft: 'auto', marginRight: 12 }}>
            {watcherRunning
              ? <span style={{ color: '#3dd68c' }}>● Watcher running</span>
              : <span style={{ color: '#4a5278' }}>● Watcher stopped</span>}
          </span>
        </div>
      </div>

      <ToastContainer />

      {/* Tweaks panel */}
      {tweaksVisible && (
        <div style={appStyles.tweaksPanel}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#e8eaf2', marginBottom: 16, fontFamily: 'Inter, sans-serif' }}>Tweaks</div>

          <TweakSection title="Card Layout">
            <TweakLabel label="Card width">
              <input type="range" min="180" max="280" step="10"
                value={tweaks.cardWidth}
                onChange={e => setTweak('cardWidth', +e.target.value)}
                style={appStyles.range}
              />
              <span style={appStyles.tweakVal}>{tweaks.cardWidth}px</span>
            </TweakLabel>
          </TweakSection>

          <TweakSection title="Accent Color">
            {['#7c6fff','#4f9eff','#3dd68c','#f0a830','#f05060','#e86aff'].map(c => (
              <button key={c} onClick={() => setTweak('accent', c)} style={{
                width: 26, height: 26, borderRadius: '50%', background: c, border: tweaks.accent === c ? '2px solid #fff' : '2px solid transparent',
                cursor: 'pointer', marginRight: 6, marginBottom: 4,
              }} />
            ))}
          </TweakSection>

          <TweakSection title="Watcher Animation">
            <TweakLabel label="Radar rings">
              <input type="checkbox" checked={tweaks.radarRings}
                onChange={e => setTweak('radarRings', e.target.checked)} />
            </TweakLabel>
            <TweakLabel label="Pulse dots">
              <input type="checkbox" checked={tweaks.pulseDots}
                onChange={e => setTweak('pulseDots', e.target.checked)} />
            </TweakLabel>
          </TweakSection>
        </div>
      )}
    </div>
  );
}

function TweakSection({ title, children }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ fontSize: 10, color: '#4a5278', textTransform: 'uppercase', letterSpacing: '0.8px', fontWeight: 600, marginBottom: 10, fontFamily: 'Inter, sans-serif' }}>{title}</div>
      {children}
    </div>
  );
}

function TweakLabel({ label, children }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
      <span style={{ fontSize: 11, color: '#8b93b3', fontFamily: 'Inter, sans-serif' }}>{label}</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>{children}</div>
    </div>
  );
}

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "cardWidth": 220,
  "accent": "#7c6fff",
  "radarRings": true,
  "pulseDots": true
}/*EDITMODE-END*/;

const appStyles = {
  root: {
    display: 'flex', width: '100vw', height: '100vh',
    background: '#07091a', overflow: 'hidden',
  },
  panelWrap: {
    position: 'absolute', inset: 0,
    display: 'flex', flexDirection: 'column',
  },
  statusBar: {
    height: 30, background: '#0c1022', borderTop: '1px solid #1c2540',
    display: 'flex', alignItems: 'center', paddingLeft: 20, flexShrink: 0,
  },
  statusText: { fontSize: 11, color: '#4a5278', fontFamily: 'Inter, sans-serif' },
  tweaksPanel: {
    width: 220, background: '#0c1022', borderLeft: '1px solid #1c2540',
    padding: '18px 16px', overflowY: 'auto', flexShrink: 0,
  },
  range: { width: 90, accentColor: '#7c6fff' },
  tweakVal: { fontSize: 11, color: '#8b93b3', fontFamily: 'Inter, sans-serif', minWidth: 36 },
};

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
