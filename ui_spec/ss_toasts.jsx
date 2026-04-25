// SaveSync — Toast notification system

const TOAST_ICONS = {
  success: '✓',
  error:   '✕',
  warning: '⚠',
  info:    'ℹ',
};
const TOAST_COLORS = {
  success: { bg: 'rgba(61,214,140,0.12)',  border: 'rgba(61,214,140,0.3)',  text: '#3dd68c' },
  error:   { bg: 'rgba(240,80,96,0.12)',   border: 'rgba(240,80,96,0.3)',   text: '#f05060' },
  warning: { bg: 'rgba(240,168,48,0.12)',  border: 'rgba(240,168,48,0.3)',  text: '#f0a830' },
  info:    { bg: 'rgba(106,172,245,0.12)', border: 'rgba(106,172,245,0.3)', text: '#6aacf5' },
};

function ToastContainer() {
  const [toasts, setToasts] = React.useState([]);

  // Expose global push function
  React.useEffect(() => {
    window.ssToast = (message, type = 'info', duration = 4000) => {
      const id = Date.now() + Math.random();
      setToasts(t => [...t, { id, message, type, exiting: false }]);
      setTimeout(() => {
        // Mark as exiting (slide-out)
        setToasts(t => t.map(x => x.id === id ? { ...x, exiting: true } : x));
        setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 320);
      }, duration);
    };
    return () => { delete window.ssToast; };
  }, []);

  const dismiss = (id) => {
    setToasts(t => t.map(x => x.id === id ? { ...x, exiting: true } : x));
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 320);
  };

  if (!toasts.length) return null;

  return (
    <div style={{
      position: 'fixed', bottom: 42, right: 20,
      display: 'flex', flexDirection: 'column', gap: 8,
      zIndex: 9999, pointerEvents: 'none',
    }}>
      {toasts.map(toast => {
        const c = TOAST_COLORS[toast.type] || TOAST_COLORS.info;
        return (
          <div key={toast.id} style={{
            display: 'flex', alignItems: 'center', gap: 10,
            background: '#0f1628',
            border: `1px solid ${c.border}`,
            borderLeft: `3px solid ${c.text}`,
            borderRadius: 10,
            padding: '11px 14px',
            minWidth: 280, maxWidth: 380,
            boxShadow: '0 8px 32px rgba(7,9,26,0.7)',
            pointerEvents: 'all',
            animation: toast.exiting ? 'toastOut 0.3s ease forwards' : 'toastIn 0.3s ease',
            fontFamily: 'Inter, sans-serif',
          }}>
            <span style={{ fontSize: 13, color: c.text, flexShrink: 0, fontWeight: 700 }}>
              {TOAST_ICONS[toast.type]}
            </span>
            <span style={{ fontSize: 12, color: '#e8eaf2', flex: 1, lineHeight: 1.4 }}>
              {toast.message}
            </span>
            <button onClick={() => dismiss(toast.id)} style={{
              background: 'none', border: 'none', color: '#4a5278',
              fontSize: 14, cursor: 'pointer', padding: '0 2px', flexShrink: 0,
              fontFamily: 'Inter, sans-serif',
            }}>✕</button>
          </div>
        );
      })}
    </div>
  );
}

Object.assign(window, { ToastContainer });
