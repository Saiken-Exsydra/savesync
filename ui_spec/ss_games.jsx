// SaveSync — Games Panel + Add Game Wizard

// ── Badge ────────────────────────────────────────────────────
function Badge({ label, bg, fg }) {
  return (
    <span style={{ background: bg, color: fg, fontSize: 10, fontWeight: 600,
      padding: '3px 7px', borderRadius: 99, letterSpacing: '0.2px' }}>
      {label}
    </span>
  );
}

// ── Thumbnail placeholder (shown before real image loads) ─────
function ThumbPlaceholder({ game, colors, height }) {
  return (
    <div style={{
      width: '100%', height: height,
      background: `linear-gradient(135deg, ${colors.from}, oklch(0.10 0.04 ${strHue(game.name)}) 100%)`,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      position: 'relative', overflow: 'hidden',
    }}>
      {/* Subtle grid */}
      <svg style={{ position: 'absolute', inset: 0, opacity: 0.10 }} width="100%" height="100%">
        <defs>
          <pattern id={`g${game.id}`} width="24" height="24" patternUnits="userSpaceOnUse">
            <path d="M 24 0 L 0 0 0 24" fill="none" stroke={colors.text} strokeWidth="0.5"/>
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill={`url(#g${game.id})`}/>
      </svg>
      <span style={{ fontSize: 38, fontWeight: 800, color: colors.text, opacity: 0.7,
        letterSpacing: '-2px', zIndex: 1, fontFamily: 'Inter, sans-serif' }}>
        {initials(game.name)}
      </span>
    </div>
  );
}

// ── Game Card ─────────────────────────────────────────────────
function GameCard({ game, onSync, onBackup, onEdit, onRemove, cardWidth, thumbData }) {
  const [hovered, setHovered] = React.useState(false);
  const [menuOpen, setMenuOpen] = React.useState(false);
  const [imgLoaded, setImgLoaded] = React.useState(false);
  const colors = gameColor(game.name);
  const rel = relTime(game.lastSync);
  const isRecent = (NOW - new Date(game.lastSync)) < 3600000;

  return (
    <div
      style={{
        width: cardWidth, borderRadius: 14,
        background: `linear-gradient(160deg, ${colors.from} 0%, ${colors.to} 100%)`,
        border: `1px solid ${hovered ? '#3a4d8a' : '#1c2540'}`,
        boxShadow: hovered ? '0 0 0 1px rgba(124,111,255,0.3), 0 8px 32px rgba(7,9,26,0.6)' : '0 2px 12px rgba(7,9,26,0.4)',
        transition: 'border-color 0.2s, box-shadow 0.2s',
        overflow: 'hidden', cursor: 'default', position: 'relative',
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => { setHovered(false); setMenuOpen(false); }}
    >
      {/* Thumbnail area — natural aspect ratio, no forced crop */}
      <div style={{ position: 'relative', width: '100%', lineHeight: 0 }}>
        {thumbData ? (
          <>
            {/* Placeholder shown until image loads */}
            {!imgLoaded && <ThumbPlaceholder game={game} colors={colors} height={Math.round(cardWidth * (thumbData.height / thumbData.width))} />}
            <img
              src={thumbData.url}
              alt={game.name}
              onLoad={() => setImgLoaded(true)}
              onError={() => setImgLoaded(false)}
              style={{
                width: '100%', height: 'auto', display: imgLoaded ? 'block' : 'none',
                borderRadius: 0,
              }}
            />
          </>
        ) : (
          <ThumbPlaceholder game={game} colors={colors} height={Math.round(cardWidth * 1.5)} />
        )}
        {/* Exe badge overlay */}
        {game.exe && (
          <div style={{ position: 'absolute', top: 8, right: 8,
            background: 'rgba(7,9,26,0.72)', backdropFilter: 'blur(4px)',
            borderRadius: 6, padding: '3px 7px',
            fontSize: 10, color: '#4a5278', fontFamily: 'Inter, sans-serif' }}>
            {game.exe.split('.')[0]}
          </div>
        )}
      </div>

      {/* Info section */}
      <div style={{ padding: '12px 14px 14px' }}>
        {/* Name */}
        <div style={{ fontSize: 14, fontWeight: 600, color: '#e8eaf2',
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          fontFamily: 'Inter, sans-serif', letterSpacing: '-0.2px' }}>
          {game.name}
        </div>

        {/* Last sync */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 4 }}>
          <span style={{ fontSize: 11, color: '#4a5278', fontFamily: 'Inter, sans-serif' }}>Last sync</span>
          <span style={{ fontSize: 11, fontWeight: 500, fontFamily: 'Inter, sans-serif',
            color: isRecent ? '#3dd68c' : '#8b93b3' }}>{rel}</span>
          <span style={{ marginLeft: 'auto', fontSize: 10, color: '#4a5278', fontFamily: 'Inter, sans-serif' }}>
            {fmtSize(game.sizeKB)}
          </span>
        </div>

        {/* Badges */}
        <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginTop: 9 }}>
          {game.drive && <Badge label="Drive" bg="#0d1c3e" fg="#6aacf5" />}
          {game.archive && <Badge label=".7z" bg="#1e1500" fg="#f0c040" />}
          {game.interval > 0
            ? <Badge label={`${game.interval} min`} bg="#091a10" fg="#3dd68c" />
            : game.trigger === 'close'
              ? <Badge label="on close" bg="#091a10" fg="#3dd68c" />
              : game.trigger === 'launch'
                ? <Badge label="on launch" bg="#091a10" fg="#3dd68c" />
                : null}
        </div>

        {/* Action buttons */}
        <div style={{ display: 'flex', gap: 6, marginTop: 12 }}>
          {game.drive ? (
            <button
              onClick={() => onSync(game)}
              style={{ ...gamesStyles.btnPrimary, flex: 1 }}
              onMouseEnter={e => e.currentTarget.style.background = '#5249cc'}
              onMouseLeave={e => e.currentTarget.style.background = '#7c6fff'}
            >Sync</button>
          ) : (
            <button
              onClick={() => onBackup(game)}
              style={{ ...gamesStyles.btnGhost, flex: 1 }}
              onMouseEnter={e => e.currentTarget.style.background = '#1c2848'}
              onMouseLeave={e => e.currentTarget.style.background = '#131c35'}
            >Backup</button>
          )}
          {/* More menu */}
          <div style={{ position: 'relative' }}>
            <button
              onClick={() => setMenuOpen(m => !m)}
              style={{ ...gamesStyles.btnGhost, width: 34, padding: 0, letterSpacing: 2 }}
              onMouseEnter={e => e.currentTarget.style.background = '#1c2848'}
              onMouseLeave={e => e.currentTarget.style.background = '#131c35'}
            >···</button>
            {menuOpen && (
              <div style={gamesStyles.dropMenu}>
                <button style={gamesStyles.dropItem} onClick={() => { setMenuOpen(false); onBackup(game); }}
                  onMouseEnter={e => e.currentTarget.style.background = 'rgba(124,111,255,0.12)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                  Backup now
                </button>
                <button style={gamesStyles.dropItem} onClick={() => { setMenuOpen(false); onEdit(game); }}
                  onMouseEnter={e => e.currentTarget.style.background = 'rgba(124,111,255,0.12)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                  Edit
                </button>
                <div style={{ height: 1, background: '#1c2540', margin: '4px 0' }}/>
                <button style={{ ...gamesStyles.dropItem, color: '#f05060' }}
                  onClick={() => { setMenuOpen(false); onRemove(game); }}
                  onMouseEnter={e => e.currentTarget.style.background = 'rgba(240,80,96,0.1)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                  Remove
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Sync Dialog ──────────────────────────────────────────────
function SyncDialog({ game, onClose }) {
  const [phase, setPhase] = React.useState('compare'); // compare | syncing | done
  const [direction, setDirection] = React.useState(null); // 'upload' | 'download' | 'equal'
  const [log, setLog] = React.useState([]);
  const [progress, setProgress] = React.useState(0);

  React.useEffect(() => {
    // Simulate timestamp comparison
    setTimeout(() => {
      const diff = (NOW - new Date(game.lastSync)) / 1000;
      const dir = diff < 3600 ? 'equal' : diff < 86400 ? 'upload' : 'download';
      setDirection(dir);
    }, 800);
  }, []);

  const runSync = () => {
    setPhase('syncing');
    const steps = direction === 'upload' ? [
      'Creating local .7z snapshot…',
      `Connecting to Google Drive…`,
      `Uploading ${game.saveCount} save file(s) to ${game.drive}…`,
      'Updating backup timestamp…',
      '✓ Local → Drive sync complete',
    ] : [
      'Snapshot of local saves created…',
      `Connecting to Google Drive…`,
      `Downloading ${game.driveFiles} file(s) from ${game.drive}…`,
      'Overwriting local saves…',
      '✓ Drive → Local sync complete',
    ];
    let i = 0;
    const iv = setInterval(() => {
      setLog(l => [...l, steps[i]]);
      setProgress(Math.round(((i+1)/steps.length)*100));
      i++;
      if (i >= steps.length) {
        clearInterval(iv);
        setPhase('done');
        if (window.ssToast) window.ssToast(`${game.name} synced successfully`, 'success');
      }
    }, 500);
  };

  const dirLabels = {
    upload:   { icon: '↑', label: 'Local is newer — upload to Drive', color: '#6aacf5' },
    download: { icon: '↓', label: 'Drive is newer — download to local', color: '#a89fff' },
    equal:    { icon: '=', label: 'Already in sync', color: '#3dd68c' },
  };

  return (
    <div style={gamesStyles.overlay}>
      <div style={{ ...gamesStyles.modal, maxWidth: 480 }} onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: '#e8eaf2', fontFamily: 'Inter, sans-serif' }}>
            Sync — {game.name}
          </div>
          <button onClick={onClose} style={gamesStyles.closeBtn}>✕</button>
        </div>

        {phase === 'compare' && (
          <div>
            {/* Timestamp comparison */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 16 }}>
              {[['Local', relTime(game.lastSync)], ['Drive', relTime(game.lastSync ? new Date(new Date(game.lastSync) - 3600000*12).toISOString() : null)]].map(([label, val]) => (
                <div key={label} style={{ background: '#0c1022', border: '1px solid #1c2540', borderRadius: 8, padding: '10px 14px' }}>
                  <div style={{ fontSize: 10, color: '#4a5278', fontFamily: 'Inter, sans-serif', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{label}</div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: '#e8eaf2', fontFamily: 'Inter, sans-serif', marginTop: 4 }}>{val}</div>
                </div>
              ))}
            </div>

            {!direction ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#8b93b3', fontSize: 12, fontFamily: 'Inter, sans-serif', padding: '8px 0' }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#7c6fff', animation: 'pulsering 1s ease-out infinite' }} />
                Comparing timestamps…
              </div>
            ) : (
              <div style={{
                display: 'flex', alignItems: 'center', gap: 12,
                background: direction === 'equal' ? 'rgba(61,214,140,0.08)' : 'rgba(124,111,255,0.08)',
                border: `1px solid ${direction === 'equal' ? 'rgba(61,214,140,0.2)' : 'rgba(124,111,255,0.2)'}`,
                borderRadius: 10, padding: '12px 16px', marginBottom: 16,
              }}>
                <span style={{ fontSize: 22, color: dirLabels[direction].color }}>{dirLabels[direction].icon}</span>
                <span style={{ fontSize: 12, color: '#e8eaf2', fontFamily: 'Inter, sans-serif' }}>{dirLabels[direction].label}</span>
              </div>
            )}

            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <button style={gamesStyles.btnGhost} onClick={onClose}
                onMouseEnter={e => e.currentTarget.style.background = '#1c2848'}
                onMouseLeave={e => e.currentTarget.style.background = '#131c35'}>
                Cancel
              </button>
              {direction && direction !== 'equal' && (
                <button style={{ ...gamesStyles.btnPrimary, flex: 1 }} onClick={runSync}
                  onMouseEnter={e => e.currentTarget.style.background = '#5249cc'}
                  onMouseLeave={e => e.currentTarget.style.background = '#7c6fff'}>
                  {direction === 'upload' ? '↑ Sync to Drive' : '↓ Sync from Drive'}
                </button>
              )}
              {direction === 'equal' && (
                <button style={{ ...gamesStyles.btnPrimary, flex: 1 }} onClick={onClose}
                  onMouseEnter={e => e.currentTarget.style.background = '#5249cc'}
                  onMouseLeave={e => e.currentTarget.style.background = '#7c6fff'}>
                  Done
                </button>
              )}
            </div>
          </div>
        )}

        {(phase === 'syncing' || phase === 'done') && (
          <div>
            <div style={{ background: '#0c1022', borderRadius: 8, padding: '12px 14px', border: '1px solid #1c2540', fontFamily: 'JetBrains Mono, monospace', fontSize: 11, marginBottom: 12, minHeight: 110 }}>
              {log.map((l, i) => (
                <div key={i} style={{ color: l.startsWith('✓') ? '#3dd68c' : '#8b93b3', padding: '2px 0' }}>{l}</div>
              ))}
            </div>
            <div style={{ background: '#1c2540', borderRadius: 99, height: 4, overflow: 'hidden', marginBottom: 16 }}>
              <div style={{ height: '100%', borderRadius: 99, background: '#7c6fff', width: `${progress}%`, transition: 'width 0.4s ease' }} />
            </div>
            {phase === 'done' && (
              <button style={{ ...gamesStyles.btnPrimary, width: '100%' }} onClick={onClose}
                onMouseEnter={e => e.currentTarget.style.background = '#5249cc'}
                onMouseLeave={e => e.currentTarget.style.background = '#7c6fff'}>
                Done
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Edit Game Dialog ──────────────────────────────────────────
function EditGameDialog({ game, onClose, onSave }) {
  const [form, setForm] = React.useState({
    name:          game.name,
    savePath:      game.savePath,
    exe:           game.exe || '',
    drive:         game.drive || '',
    archive:       game.archive || '',
    triggerLaunch: game.trigger === 'launch',
    triggerClose:  game.trigger === 'close',
    interval:      game.interval || 0,
  });
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const handleSave = () => {
    onSave({ ...game, ...form, exe: form.exe || null, drive: form.drive || null, archive: form.archive || null });
    if (window.ssToast) window.ssToast(`${form.name} updated`, 'success');
    onClose();
  };

  const Field = ({ label, field, placeholder, mono }) => (
    <div style={{ marginBottom: 14 }}>
      <label style={wizStyles.label}>{label}</label>
      <input
        style={{ ...wizStyles.input, fontFamily: mono ? 'JetBrains Mono, monospace' : 'Inter, sans-serif' }}
        placeholder={placeholder}
        value={form[field]}
        onChange={e => set(field, e.target.value)}
      />
    </div>
  );

  return (
    <div style={gamesStyles.overlay}>
      <div style={{ ...gamesStyles.modal, maxWidth: 500 }} onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: '#e8eaf2', fontFamily: 'Inter, sans-serif' }}>
            Edit — {game.name}
          </div>
          <button onClick={onClose} style={gamesStyles.closeBtn}>✕</button>
        </div>

        <Field label="Game name"          field="name"     placeholder="Game name" />
        <Field label="Save path"          field="savePath" placeholder="C:/Users/…" mono />
        <Field label="Launcher exe"       field="exe"      placeholder="game.exe (optional)" mono />
        <Field label="Google Drive folder" field="drive"   placeholder="SaveSync/GameName (optional)" />
        <Field label="Local archive path" field="archive"  placeholder="D:/Backups/Game (optional)" mono />

        {/* Triggers */}
        <div style={{ marginBottom: 14 }}>
          <label style={wizStyles.label}>Triggers</label>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {[['triggerLaunch','On launch'], ['triggerClose','On close']].map(([key, label]) => (
              <button key={key} onClick={() => set(key, !form[key])}
                style={{ ...wizStyles.toggleBtn, ...(form[key] ? wizStyles.toggleBtnOn : {}) }}>
                {label}
              </button>
            ))}
          </div>
        </div>
        <div style={{ marginBottom: 20 }}>
          <label style={wizStyles.label}>Interval (minutes, 0 = off)</label>
          <input type="number" min="0" max="120" value={form.interval}
            onChange={e => set('interval', +e.target.value)}
            style={{ ...wizStyles.input, width: 80 }} />
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <button style={gamesStyles.btnGhost} onClick={onClose}
            onMouseEnter={e => e.currentTarget.style.background = '#1c2848'}
            onMouseLeave={e => e.currentTarget.style.background = '#131c35'}>
            Cancel
          </button>
          <button style={gamesStyles.btnPrimary} onClick={handleSave}
            onMouseEnter={e => e.currentTarget.style.background = '#5249cc'}
            onMouseLeave={e => e.currentTarget.style.background = '#7c6fff'}>
            Save Changes
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Onboarding empty state ────────────────────────────────────
function OnboardingEmpty({ onAddGame }) {
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 40 }}>
      <div style={{
        width: 80, height: 80, borderRadius: '50%',
        background: 'rgba(124,111,255,0.08)', border: '1.5px solid rgba(124,111,255,0.2)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        marginBottom: 20, fontSize: 32,
      }}>💾</div>
      <div style={{ fontSize: 18, fontWeight: 700, color: '#e8eaf2', fontFamily: 'Inter, sans-serif', marginBottom: 8 }}>
        No games yet
      </div>
      <div style={{ fontSize: 13, color: '#8b93b3', fontFamily: 'Inter, sans-serif', textAlign: 'center', maxWidth: 320, lineHeight: 1.6, marginBottom: 28 }}>
        Add your first game to start protecting save files with automatic backups to Google Drive and local archives.
      </div>
      <div style={{ display: 'flex', gap: 10 }}>
        <button style={{
          background: 'rgba(124,111,255,0.1)', color: '#a89fff',
          border: '1px solid rgba(124,111,255,0.25)', borderRadius: 8,
          padding: '9px 18px', fontSize: 12, fontWeight: 500, cursor: 'pointer',
          fontFamily: 'Inter, sans-serif',
        }}
        onMouseEnter={e => e.currentTarget.style.background = 'rgba(124,111,255,0.18)'}
        onMouseLeave={e => e.currentTarget.style.background = 'rgba(124,111,255,0.1)'}>
          Import from Drive
        </button>
        <button style={{ ...gamesStyles.btnPrimary, padding: '9px 22px' }} onClick={onAddGame}
          onMouseEnter={e => e.currentTarget.style.background = '#5249cc'}
          onMouseLeave={e => e.currentTarget.style.background = '#7c6fff'}>
          + Add First Game
        </button>
      </div>
    </div>
  );
}

// ── Add Game Wizard ───────────────────────────────────────────
const WIZARD_STEPS = ['Name', 'Save Path', 'Launcher', 'Destinations', 'Triggers', 'Confirm'];

function AddGameWizard({ onClose, onAdd }) {
  const [step, setStep] = React.useState(0);
  const [form, setForm] = React.useState({
    name: '', savePath: '', exe: '', drive: '', archive: '',
    triggerLaunch: true, triggerClose: true, interval: 0, maxSnapshots: 5,
  });
  const [dbResults, setDbResults] = React.useState([]);
  const [searching, setSearching] = React.useState(false);

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const fakeSearch = (q) => {
    if (!q) { setDbResults([]); return; }
    setSearching(true);
    setTimeout(() => {
      const candidates = [
        { name: q, path: `C:/Users/User/AppData/Roaming/${q.replace(/ /g,'')}/saves` },
        { name: q, path: `C:/Users/User/AppData/LocalLow/${q.replace(/ /g,'')}` },
        { name: q, path: `C:/Users/User/Documents/My Games/${q}/Saves` },
      ];
      setDbResults(candidates);
      setSearching(false);
    }, 600);
  };

  const stepContent = () => {
    switch(step) {
      case 0: return (
        <div>
          <p style={wizStyles.hint}>Enter the name of the game as it appears in your library.</p>
          <input
            style={wizStyles.input} autoFocus placeholder="e.g. Dark Souls III"
            value={form.name} onChange={e => { set('name', e.target.value); fakeSearch(e.target.value); }}
          />
          {dbResults.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <div style={{ fontSize: 11, color: '#4a5278', marginBottom: 6 }}>Ludusavi database matches:</div>
              {dbResults.slice(0,2).map((r,i) => (
                <div key={i} style={wizStyles.suggestion} onClick={() => { set('name', r.name); setDbResults([]); }}>
                  <span style={{ color: '#e8eaf2', fontWeight: 500 }}>{r.name}</span>
                  <span style={{ fontSize: 10, color: '#4a5278', marginLeft: 8 }}>{r.path}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      );
      case 1: return (
        <div>
          <p style={wizStyles.hint}>Where does <strong style={{color:'#e8eaf2'}}>{form.name}</strong> store save files?</p>
          {searching ? (
            <div style={{ fontSize: 12, color: '#8b93b3', margin: '12px 0' }}>Searching database…</div>
          ) : dbResults.length > 0 ? (
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 11, color: '#4a5278', marginBottom: 6 }}>Suggested paths from database:</div>
              {dbResults.map((r,i) => (
                <div key={i} style={{ ...wizStyles.suggestion, flexDirection: 'column', alignItems: 'flex-start', gap: 2 }}
                  onClick={() => { set('savePath', r.path); setDbResults([]); }}>
                  <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: '#6aacf5' }}>{r.path}</span>
                </div>
              ))}
            </div>
          ) : null}
          <input style={wizStyles.input} placeholder="C:/Users/…/SaveFolder"
            value={form.savePath} onChange={e => set('savePath', e.target.value)} />
          <button style={wizStyles.browseBtn}>Browse…</button>
        </div>
      );
      case 2: return (
        <div>
          <p style={wizStyles.hint}>Optional: path to the game executable. Enables automatic backups on launch/close.</p>
          <input style={wizStyles.input} placeholder="e.g. C:/Games/DarkSoulsIII/Game/DarkSoulsIII.exe"
            value={form.exe} onChange={e => set('exe', e.target.value)} />
          <button style={wizStyles.browseBtn}>Browse…</button>
          <p style={{ fontSize: 11, color: '#4a5278', marginTop: 12 }}>Leave blank to use manual backup only.</p>
        </div>
      );
      case 3: return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <p style={wizStyles.hint}>Where should backups be stored?</p>
          <div>
            <label style={wizStyles.label}>Google Drive folder</label>
            <input style={wizStyles.input} placeholder="SaveSync/GameName"
              value={form.drive} onChange={e => set('drive', e.target.value)} />
          </div>
          <div>
            <label style={wizStyles.label}>Local .7z archive path</label>
            <input style={wizStyles.input} placeholder="D:/Backups/GameName"
              value={form.archive} onChange={e => set('archive', e.target.value)} />
            <button style={wizStyles.browseBtn}>Browse…</button>
          </div>
        </div>
      );
      case 4: return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <p style={wizStyles.hint}>When should automatic backups run?</p>
          <div style={{ display: 'flex', gap: 10 }}>
            {[['triggerLaunch','On game launch'], ['triggerClose','On game close']].map(([key, label]) => (
              <button key={key}
                onClick={() => set(key, !form[key])}
                style={{ ...wizStyles.toggleBtn, ...(form[key] ? wizStyles.toggleBtnOn : {}) }}>
                {label}
              </button>
            ))}
          </div>
          <div>
            <label style={wizStyles.label}>Interval backup (minutes, 0 = disabled)</label>
            <input style={{ ...wizStyles.input, width: 80 }} type="number" min="0" max="120"
              value={form.interval} onChange={e => set('interval', +e.target.value)} />
          </div>
          <div>
            <label style={wizStyles.label}>Max local snapshots to keep</label>
            <input style={{ ...wizStyles.input, width: 80 }} type="number" min="1" max="50"
              value={form.maxSnapshots} onChange={e => set('maxSnapshots', +e.target.value)} />
          </div>
        </div>
      );
      case 5: return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <p style={wizStyles.hint}>Review your configuration before saving.</p>
          {[
            ['Game name', form.name || '—'],
            ['Save path', form.savePath || '—'],
            ['Launcher', form.exe || 'not set'],
            ['Google Drive', form.drive || 'not set'],
            ['Local archive', form.archive || 'not set'],
            ['Triggers', [form.triggerLaunch && 'launch', form.triggerClose && 'close', form.interval > 0 && `${form.interval} min`].filter(Boolean).join(', ') || 'none'],
            ['Max snapshots', form.maxSnapshots],
          ].map(([k,v]) => (
            <div key={k} style={{ display: 'flex', gap: 12, fontSize: 13, fontFamily: 'Inter, sans-serif' }}>
              <span style={{ color: '#4a5278', width: 120, flexShrink: 0 }}>{k}</span>
              <span style={{ color: '#e8eaf2', fontFamily: typeof v === 'string' && v.includes('/') ? 'JetBrains Mono, monospace' : 'Inter, sans-serif', fontSize: 12 }}>{v}</span>
            </div>
          ))}
        </div>
      );
      default: return null;
    }
  };

  const canNext = () => {
    if (step === 0 && !form.name) return false;
    return true;
  };

  return (
    <div style={gamesStyles.overlay}>
      <div style={gamesStyles.modal} onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <div>
            <div style={{ fontSize: 16, fontWeight: 700, color: '#e8eaf2', fontFamily: 'Inter, sans-serif' }}>Add Game</div>
            <div style={{ fontSize: 11, color: '#4a5278', marginTop: 2, fontFamily: 'Inter, sans-serif' }}>Step {step+1} of {WIZARD_STEPS.length}</div>
          </div>
          <button onClick={onClose} style={gamesStyles.closeBtn}>✕</button>
        </div>

        {/* Step dots */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 24 }}>
          {WIZARD_STEPS.map((s, i) => (
            <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5 }}>
              <div style={{
                height: 3, width: '100%', borderRadius: 99,
                background: i < step ? '#7c6fff' : i === step ? '#7c6fff' : '#1c2540',
                opacity: i > step ? 1 : 1,
                transition: 'background 0.3s',
              }} />
              <span style={{ fontSize: 9, color: i === step ? '#7c6fff' : i < step ? '#5249cc' : '#4a5278',
                fontFamily: 'Inter, sans-serif', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                {s}
              </span>
            </div>
          ))}
        </div>

        {/* Content */}
        <div style={{ minHeight: 180 }}>
          {stepContent()}
        </div>

        {/* Footer */}
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 24 }}>
          <button
            onClick={() => step > 0 ? setStep(s => s-1) : onClose()}
            style={gamesStyles.btnGhost}
            onMouseEnter={e => e.currentTarget.style.background = '#1c2848'}
            onMouseLeave={e => e.currentTarget.style.background = '#131c35'}
          >{step === 0 ? 'Cancel' : '← Back'}</button>
          <button
            onClick={() => step < WIZARD_STEPS.length-1 ? setStep(s => s+1) : onAdd(form)}
            disabled={!canNext()}
            style={{ ...gamesStyles.btnPrimary, opacity: canNext() ? 1 : 0.4 }}
            onMouseEnter={e => { if (canNext()) e.currentTarget.style.background = '#5249cc'; }}
            onMouseLeave={e => { if (canNext()) e.currentTarget.style.background = '#7c6fff'; }}
          >{step === WIZARD_STEPS.length-1 ? '✓ Save Game' : 'Next →'}</button>
        </div>
      </div>
    </div>
  );
}

// ── Backup Dialog ────────────────────────────────────────────
function BackupDialog({ game, onClose }) {
  const [done, setDone] = React.useState(false);
  const [progress, setProgress] = React.useState(0);
  const [log, setLog] = React.useState([]);

  const runBackup = (type) => {
    setProgress(0);
    const steps = [
      `Scanning save files in ${game.savePath.split('/').pop()}…`,
      `Found ${game.saveCount} save file(s) (${fmtSize(game.sizeKB)})`,
      type === 'drive' ? 'Connecting to Google Drive…' : 'Creating .7z archive…',
      type === 'drive' ? 'Uploading to SaveSync/' + game.name + '…' : 'Compressing with LZMA2…',
      'Writing backup timestamp…',
      '✓ Backup complete',
    ];
    let i = 0;
    const interval = setInterval(() => {
      setLog(l => [...l, steps[i]]);
      setProgress(Math.round(((i+1)/steps.length)*100));
      i++;
      if (i >= steps.length) { clearInterval(interval); setDone(true); }
    }, 500);
  };

  return (
    <div style={gamesStyles.overlay}>
      <div style={{ ...gamesStyles.modal, maxWidth: 480 }} onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: '#e8eaf2', fontFamily: 'Inter, sans-serif' }}>
            Backup — {game.name}
          </div>
          <button onClick={onClose} style={gamesStyles.closeBtn}>✕</button>
        </div>

        {log.length === 0 ? (
          <div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 20 }}>
              {[
                ['Save files', game.saveCount],
                ['Size', fmtSize(game.sizeKB)],
                ['Drive files', game.driveFiles || '—'],
                ['Last backup', relTime(game.lastSync)],
              ].map(([k,v]) => (
                <div key={k} style={{ background: '#0c1022', borderRadius: 8, padding: '10px 14px', border: '1px solid #1c2540' }}>
                  <div style={{ fontSize: 10, color: '#4a5278', fontFamily: 'Inter, sans-serif', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{k}</div>
                  <div style={{ fontSize: 15, fontWeight: 600, color: '#e8eaf2', fontFamily: 'Inter, sans-serif', marginTop: 4 }}>{v}</div>
                </div>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              {game.drive && (
                <button style={{ ...gamesStyles.btnPrimary, flex: 1 }} onClick={() => runBackup('drive')}
                  onMouseEnter={e => e.currentTarget.style.background = '#5249cc'}
                  onMouseLeave={e => e.currentTarget.style.background = '#7c6fff'}>
                  ↑ Backup to Drive
                </button>
              )}
              {game.archive && (
                <button style={{ ...gamesStyles.btnGhost, flex: 1 }} onClick={() => runBackup('archive')}
                  onMouseEnter={e => e.currentTarget.style.background = '#1c2848'}
                  onMouseLeave={e => e.currentTarget.style.background = '#131c35'}>
                  📦 Create .7z
                </button>
              )}
              {game.drive && game.archive && (
                <button style={{ ...gamesStyles.btnGhost, flex: 1 }} onClick={() => runBackup('both')}
                  onMouseEnter={e => e.currentTarget.style.background = '#1c2848'}
                  onMouseLeave={e => e.currentTarget.style.background = '#131c35'}>
                  Both
                </button>
              )}
            </div>
          </div>
        ) : (
          <div>
            <div style={{ background: '#0c1022', borderRadius: 8, padding: '12px 14px', border: '1px solid #1c2540', fontFamily: 'JetBrains Mono, monospace', fontSize: 11, marginBottom: 12, minHeight: 130 }}>
              {log.map((l,i) => (
                <div key={i} style={{ color: l.startsWith('✓') ? '#3dd68c' : '#8b93b3', padding: '2px 0' }}>{l}</div>
              ))}
            </div>
            <div style={{ background: '#1c2540', borderRadius: 99, height: 4, overflow: 'hidden', marginBottom: 16 }}>
              <div style={{ height: '100%', borderRadius: 99, background: '#7c6fff', width: `${progress}%`, transition: 'width 0.4s ease' }}/>
            </div>
            {done && (
              <button style={{ ...gamesStyles.btnPrimary, width: '100%' }} onClick={onClose}
                onMouseEnter={e => e.currentTarget.style.background = '#5249cc'}
                onMouseLeave={e => e.currentTarget.style.background = '#7c6fff'}>
                Done
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Games Panel ───────────────────────────────────────────────
function GamesPanel({ tweaks }) {
  const [games, setGames] = React.useState(SAMPLE_GAMES);
  const [showWizard, setShowWizard] = React.useState(false);
  const [backupGame, setBackupGame] = React.useState(null);
  const [syncGame, setSyncGame] = React.useState(null);
  const [editGame, setEditGame] = React.useState(null);
  const [search, setSearch] = React.useState('');
  const [thumbs, setThumbs] = React.useState({});  // name → { url, width, height }
  const gridRef = React.useRef(null);
  const [cols, setCols] = React.useState(4);

  // Prefetch thumbnails for all games on mount
  React.useEffect(() => {
    prefetchThumbs(
      SAMPLE_GAMES.map(g => g.name),
      (name, data) => setThumbs(t => ({ ...t, [name]: data }))
    );
  }, []);

  React.useEffect(() => {
    const obs = new ResizeObserver(entries => {
      const w = entries[0].contentRect.width;
      const cardW = tweaks.cardWidth || 220;
      const gap = 16;
      setCols(Math.max(1, Math.floor((w + gap) / (cardW + gap))));
    });
    if (gridRef.current) obs.observe(gridRef.current);
    return () => obs.disconnect();
  }, [tweaks.cardWidth]);

  const filtered = games.filter(g => g.name.toLowerCase().includes(search.toLowerCase()));
  const cardW = tweaks.cardWidth || 220;

  const handleAdd = (form) => {
    const newGame = {
      id: Date.now(), name: form.name,
      savePath: form.savePath, exe: form.exe || null,
      drive: form.drive || null, archive: form.archive || null,
      trigger: form.triggerClose ? 'close' : form.triggerLaunch ? 'launch' : 'none',
      interval: form.interval,
      lastSync: null, saveCount: 0, driveFiles: 0, sizeKB: 0,
    };
    setGames(g => [...g, newGame]);
    setShowWizard(false);
    if (window.ssToast) window.ssToast(`${form.name} added to SaveSync`, 'success');
    // Fetch thumbnail for the newly added game
    fetchGameThumb(form.name).then(data => {
      if (data) setThumbs(t => ({ ...t, [form.name]: data }));
    });
  };

  const handleSaveEdit = (updated) => {
    setGames(g => g.map(x => x.id === updated.id ? updated : x));
  };

  const handleRemove = (game) => {
    if (confirm(`Remove "${game.name}" from SaveSync?`)) {
      setGames(g => g.filter(x => x.id !== game.id));
      if (window.ssToast) window.ssToast(`${game.name} removed`, 'info');
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Top bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '18px 24px 0', flexShrink: 0 }}>
        <div style={{ fontSize: 17, fontWeight: 700, color: '#e8eaf2', fontFamily: 'Inter, sans-serif', letterSpacing: '-0.3px' }}>
          My Games
        </div>
        <span style={{ fontSize: 11, color: '#4a5278', background: '#131c35', borderRadius: 99, padding: '2px 8px', fontFamily: 'Inter, sans-serif' }}>
          {games.length}
        </span>
        {/* Search */}
        <div style={{ flex: 1, maxWidth: 260, position: 'relative', marginLeft: 8 }}>
          <span style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: '#4a5278', fontSize: 13 }}>⌕</span>
          <input
            style={{ ...gamesStyles.searchInput }}
            placeholder="Search games…"
            value={search} onChange={e => setSearch(e.target.value)}
          />
        </div>
        <div style={{ display: 'flex', gap: 8, marginLeft: 'auto' }}>
          <button style={gamesStyles.btnGhost}
            onMouseEnter={e => e.currentTarget.style.background = '#1c2848'}
            onMouseLeave={e => e.currentTarget.style.background = '#131c35'}>
            Add from Drive
          </button>
          <button style={gamesStyles.btnPrimary} onClick={() => setShowWizard(true)}
            onMouseEnter={e => e.currentTarget.style.background = '#5249cc'}
            onMouseLeave={e => e.currentTarget.style.background = '#7c6fff'}>
            + Add Game
          </button>
        </div>
      </div>

      {/* Grid */}
      <div ref={gridRef} style={{ flex: 1, overflowY: 'auto', padding: '16px 24px 24px' }}>
        {games.length === 0 ? (
          <OnboardingEmpty onAddGame={() => setShowWizard(true)} />
        ) : filtered.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '60px 0', color: '#4a5278', fontFamily: 'Inter, sans-serif' }}>
            No games match your search.
          </div>
        ) : (
          <div style={{
            display: 'grid',
            gridTemplateColumns: `repeat(${cols}, ${cardW}px)`,
            gap: 16, justifyContent: 'start', alignItems: 'start',
          }}>
            {filtered.map(game => (
              <GameCard key={game.id} game={game} cardWidth={cardW}
                thumbData={thumbs[game.name] || null}
                onSync={g => setSyncGame(g)}
                onBackup={g => setBackupGame(g)}
                onEdit={g => setEditGame(g)}
                onRemove={handleRemove}
              />
            ))}
          </div>
        )}
      </div>

      {showWizard && <AddGameWizard onClose={() => setShowWizard(false)} onAdd={handleAdd} />}
      {backupGame && <BackupDialog game={backupGame} onClose={() => setBackupGame(null)} />}
      {syncGame && <SyncDialog game={syncGame} onClose={() => setSyncGame(null)} />}
      {editGame && <EditGameDialog game={editGame} onClose={() => setEditGame(null)} onSave={handleSaveEdit} />}
    </div>
  );
}

const gamesStyles = {
  btnPrimary: {
    background: '#7c6fff', color: '#fff', border: 'none', borderRadius: 8,
    padding: '8px 16px', fontSize: 12, fontWeight: 600, cursor: 'pointer',
    fontFamily: 'Inter, sans-serif', transition: 'background 0.15s',
  },
  btnGhost: {
    background: '#131c35', color: '#8b93b3', border: '1px solid #1c2540', borderRadius: 8,
    padding: '8px 14px', fontSize: 12, fontWeight: 500, cursor: 'pointer',
    fontFamily: 'Inter, sans-serif', transition: 'background 0.15s',
  },
  searchInput: {
    width: '100%', background: '#0c1022', border: '1px solid #1c2540', borderRadius: 8,
    padding: '7px 10px 7px 28px', fontSize: 12, color: '#e8eaf2',
    fontFamily: 'Inter, sans-serif', outline: 'none',
    boxSizing: 'border-box',
  },
  overlay: {
    position: 'fixed', inset: 0, background: 'rgba(7,9,26,0.85)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    zIndex: 1000, backdropFilter: 'blur(4px)',
  },
  modal: {
    background: '#0f1628', border: '1px solid #1c2540', borderRadius: 16,
    padding: '24px 28px', width: 520, maxHeight: '85vh', overflowY: 'auto',
    boxShadow: '0 24px 80px rgba(7,9,26,0.8)',
  },
  closeBtn: {
    background: 'none', border: 'none', color: '#4a5278', fontSize: 16,
    cursor: 'pointer', padding: '4px 8px', borderRadius: 6,
    fontFamily: 'Inter, sans-serif',
  },
  dropMenu: {
    position: 'absolute', right: 0, bottom: '100%', marginBottom: 4,
    background: '#0f1628', border: '1px solid #1c2540', borderRadius: 10,
    padding: '6px', zIndex: 100, minWidth: 140,
    boxShadow: '0 8px 32px rgba(7,9,26,0.8)',
  },
  dropItem: {
    display: 'block', width: '100%', background: 'transparent', border: 'none',
    color: '#e8eaf2', fontSize: 12, padding: '8px 12px', borderRadius: 6,
    textAlign: 'left', cursor: 'pointer', fontFamily: 'Inter, sans-serif',
    transition: 'background 0.12s',
  },
};

const wizStyles = {
  hint: { fontSize: 12, color: '#8b93b3', marginBottom: 14, fontFamily: 'Inter, sans-serif', marginTop: 0 },
  label: { display: 'block', fontSize: 11, color: '#4a5278', marginBottom: 6, fontFamily: 'Inter, sans-serif', textTransform: 'uppercase', letterSpacing: '0.5px' },
  input: {
    width: '100%', background: '#0c1022', border: '1px solid #1c2540',
    borderRadius: 8, padding: '10px 12px', fontSize: 12, color: '#e8eaf2',
    fontFamily: 'JetBrains Mono, monospace', outline: 'none', boxSizing: 'border-box',
    transition: 'border-color 0.15s',
  },
  browseBtn: {
    background: '#131c35', color: '#8b93b3', border: '1px solid #1c2540',
    borderRadius: 6, padding: '6px 12px', fontSize: 11, cursor: 'pointer',
    marginTop: 8, fontFamily: 'Inter, sans-serif',
  },
  suggestion: {
    display: 'flex', alignItems: 'center', background: '#0c1022',
    border: '1px solid #1c2540', borderRadius: 8, padding: '8px 12px',
    cursor: 'pointer', marginBottom: 6, fontFamily: 'Inter, sans-serif', fontSize: 12,
    transition: 'border-color 0.15s',
  },
  toggleBtn: {
    background: '#131c35', color: '#8b93b3', border: '1px solid #1c2540',
    borderRadius: 8, padding: '8px 14px', fontSize: 12, cursor: 'pointer',
    fontFamily: 'Inter, sans-serif', transition: 'all 0.15s',
  },
  toggleBtnOn: {
    background: 'rgba(124,111,255,0.15)', color: '#a89fff', borderColor: '#5249cc',
  },
};

Object.assign(window, { GamesPanel });
