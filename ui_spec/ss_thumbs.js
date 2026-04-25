// SaveSync — SteamGridDB thumbnail manager (browser, localStorage cache)

const SGDB_KEY   = 'eef436c06c902672e16d69ba375c0cb7';
const SGDB_BASE  = 'https://www.steamgriddb.com/api/v2';
const CACHE_KEY  = 'ss_thumb_cache_v1';

// ── Persistent cache (localStorage) ──────────────────────────
function _loadCache() {
  try { return JSON.parse(localStorage.getItem(CACHE_KEY) || '{}'); }
  catch { return {}; }
}
function _saveCache(c) {
  try { localStorage.setItem(CACHE_KEY, JSON.stringify(c)); }
  catch {}
}
let _cache = _loadCache();

// ── Fetch helpers ─────────────────────────────────────────────
async function _sgdb(path) {
  const res = await fetch(`${SGDB_BASE}${path}`, {
    headers: { Authorization: `Bearer ${SGDB_KEY}` },
  });
  if (!res.ok) throw new Error(`SGDB ${res.status} ${path}`);
  return res.json();
}

// ── Public API ────────────────────────────────────────────────
/**
 * Returns { url, width, height } or null.
 * Checks localStorage first; fetches from SGDB on miss.
 */
async function fetchGameThumb(gameName) {
  // Cache hit
  if (_cache[gameName] !== undefined) return _cache[gameName];

  try {
    // 1. Find the game ID
    const search = await _sgdb(
      `/search/autocomplete/${encodeURIComponent(gameName)}`
    );
    const games = search.data || [];
    if (!games.length) { _cache[gameName] = null; _saveCache(_cache); return null; }
    const id = games[0].id;

    // 2. Try portrait grids first (600×900), then any
    let grids = [];
    try {
      const p = await _sgdb(`/grids/game/${id}?dimensions=600x900&limit=5&nsfw=false`);
      grids = p.data || [];
    } catch {}

    if (!grids.length) {
      try {
        const a = await _sgdb(`/grids/game/${id}?limit=5&nsfw=false`);
        grids = a.data || [];
      } catch {}
    }

    if (!grids.length) { _cache[gameName] = null; _saveCache(_cache); return null; }

    const g = grids[0];
    const result = { url: g.url, width: g.width || 600, height: g.height || 900 };
    _cache[gameName] = result;
    _saveCache(_cache);
    return result;

  } catch (err) {
    console.warn(`[SGDB] "${gameName}":`, err.message);
    _cache[gameName] = null;
    _saveCache(_cache);
    return null;
  }
}

/**
 * Prefetch thumbnails for an array of game names.
 * Fires all requests in parallel; callers listen via React state.
 */
function prefetchThumbs(names, onEach) {
  names.forEach(name => {
    fetchGameThumb(name).then(result => {
      if (result) onEach(name, result);
    });
  });
}

/**
 * Clear the entire thumbnail cache (e.g. from Settings).
 */
function clearThumbCache() {
  _cache = {};
  localStorage.removeItem(CACHE_KEY);
}
