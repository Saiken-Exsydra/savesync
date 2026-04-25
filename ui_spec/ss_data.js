// SaveSync — shared data, constants, utilities

const SS_COLORS = {
  bg:          '#07091a',
  bg2:         '#0c1022',
  card:        '#0f1628',
  cardHover:   '#131c35',
  border:      '#1c2540',
  borderHover: '#3a4d8a',
  accent:      '#7c6fff',
  accentDim:   '#5249cc',
  accentGlow:  'rgba(124,111,255,0.18)',
  text:        '#e8eaf2',
  textMid:     '#8b93b3',
  textDim:     '#4a5278',
  success:     '#3dd68c',
  successDim:  'rgba(61,214,140,0.15)',
  warning:     '#f0a830',
  error:       '#f05060',
  driveBg:     '#0d1c3e', driveFg: '#6aacf5',
  zipBg:       '#1e1500', zipFg:   '#f0c040',
  autoBg:      '#091a10', autoFg:  '#3dd68c',
};

const SS_FONTS = {
  title: '700 17px Inter',
  head:  '600 14px Inter',
  body:  '400 13px Inter',
  small: '400 12px Inter',
  tiny:  '400 11px Inter',
  mono:  '400 12px "JetBrains Mono", monospace',
};

const NOW = new Date('2026-04-22T14:30:00Z');

const SAMPLE_GAMES = [
  {
    id: 1, name: 'Elden Ring',
    savePath: 'C:/Users/User/AppData/Roaming/EldenRing/76561198…/ER0000.sl2',
    exe: 'eldenring.exe',
    drive: 'SaveSync/EldenRing', archive: 'D:/Backups/EldenRing',
    trigger: 'close', interval: 0,
    lastSync: new Date(NOW - 2*3600*1000).toISOString(),
    saveCount: 3, driveFiles: 8, sizeKB: 43008,
  },
  {
    id: 2, name: 'Hollow Knight',
    savePath: 'C:/Users/User/AppData/LocalLow/Team Cherry/Hollow Knight',
    exe: 'hollow_knight.exe',
    drive: 'SaveSync/HollowKnight', archive: null,
    trigger: 'launch', interval: 0,
    lastSync: new Date(NOW - 30*3600*1000).toISOString(),
    saveCount: 4, driveFiles: 4, sizeKB: 8192,
  },
  {
    id: 3, name: 'Celeste',
    savePath: 'C:/Users/User/AppData/Local/Celeste/Saves',
    exe: null,
    drive: null, archive: 'D:/Backups/Celeste',
    trigger: 'interval', interval: 5,
    lastSync: new Date(NOW - 3*86400*1000).toISOString(),
    saveCount: 12, driveFiles: 0, sizeKB: 2048,
  },
  {
    id: 4, name: 'Stardew Valley',
    savePath: 'C:/Users/User/AppData/Roaming/StardewValley/Saves',
    exe: 'StardewModdingAPI.exe',
    drive: 'SaveSync/StardewValley', archive: 'D:/Backups/Stardew',
    trigger: 'close', interval: 0,
    lastSync: new Date(NOW - 15*60*1000).toISOString(),
    saveCount: 6, driveFiles: 12, sizeKB: 15360,
  },
  {
    id: 5, name: 'Hades',
    savePath: 'C:/Users/User/Documents/Saved Games/Supergiant Games/Hades',
    exe: 'Hades.exe',
    drive: 'SaveSync/Hades', archive: null,
    trigger: 'launch', interval: 0,
    lastSync: new Date(NOW - 5*86400*1000).toISOString(),
    saveCount: 2, driveFiles: 3, sizeKB: 12288,
  },
  {
    id: 6, name: 'Cyberpunk 2077',
    savePath: 'C:/Users/User/Saved Games/CD Projekt Red/Cyberpunk 2077',
    exe: 'Cyberpunk2077.exe',
    drive: null, archive: 'D:/Backups/Cyberpunk',
    trigger: 'interval', interval: 10,
    lastSync: new Date(NOW - 8*3600*1000).toISOString(),
    saveCount: 25, driveFiles: 0, sizeKB: 189440,
  },
  {
    id: 7, name: 'Baldur\'s Gate 3',
    savePath: 'C:/Users/User/AppData/Local/Larian Studios/Baldur\'s Gate 3/PlayerProfiles',
    exe: 'bg3.exe',
    drive: 'SaveSync/BG3', archive: 'D:/Backups/BG3',
    trigger: 'close', interval: 0,
    lastSync: new Date(NOW - 1*3600*1000).toISOString(),
    saveCount: 18, driveFiles: 22, sizeKB: 245760,
  },
  {
    id: 8, name: 'Terraria',
    savePath: 'C:/Users/User/Documents/My Games/Terraria',
    exe: 'Terraria.exe',
    drive: 'SaveSync/Terraria', archive: null,
    trigger: 'launch', interval: 0,
    lastSync: new Date(NOW - 12*86400*1000).toISOString(),
    saveCount: 3, driveFiles: 3, sizeKB: 4096,
  },
];

const WATCHER_LOG = [
  { time: '14:28:11', type: 'backup',  msg: "Elden Ring closed — backup complete (3 files, 42 MB)" },
  { time: '14:15:03', type: 'detect',  msg: "Elden Ring launched — watching process eldenring.exe" },
  { time: '13:52:40', type: 'backup',  msg: "Baldur's Gate 3 closed — backup complete (18 files, 240 MB)" },
  { time: '13:30:00', type: 'interval',msg: "Cyberpunk 2077 interval backup (10 min) — 25 files" },
  { time: '13:20:00', type: 'interval',msg: "Cyberpunk 2077 interval backup (10 min) — 25 files" },
  { time: '12:31:22', type: 'backup',  msg: "Stardew Valley closed — backup complete (6 files, 15 MB)" },
  { time: '12:15:44', type: 'detect',  msg: "Stardew Valley launched — watching StardewModdingAPI.exe" },
  { time: '11:08:03', type: 'sync',    msg: "Hollow Knight synced to Drive — 4 files uploaded" },
];

function relTime(isoStr) {
  if (!isoStr) return 'never';
  const diff = (NOW - new Date(isoStr)) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff/3600)}h ago`;
  if (diff < 2592000) return `${Math.floor(diff/86400)}d ago`;
  return `${Math.floor(diff/2592000)}mo ago`;
}

function fmtSize(kb) {
  if (kb < 1024) return `${kb} KB`;
  return `${(kb/1024).toFixed(0)} MB`;
}

function strHue(str) {
  let h = 0;
  for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) | 0;
  return Math.abs(h) % 360;
}

function gameColor(name) {
  const hue = strHue(name);
  return { from: `oklch(0.18 0.07 ${hue})`, to: `oklch(0.12 0.05 ${hue})`, text: `oklch(0.75 0.12 ${hue})` };
}

function initials(name) {
  return name.split(' ').filter(Boolean).slice(0,2).map(w => w[0]?.toUpperCase() || '').join('') || '?';
}
