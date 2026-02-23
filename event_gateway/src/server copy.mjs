import cors from 'cors';
import express from 'express';
import { createClient } from 'redis';

const REDIS_URL = process.env.REDIS_URL || 'redis://127.0.0.1:6379/0';
const PORT = Number(process.env.PORT || 8088);
const SCHEDULER_CHANNEL = process.env.SCHEDULER_CHANNEL || 'scheduler:events';
const LUMINAIRE_CHANNEL = process.env.LUMINAIRE_CHANNEL || 'devices:luminaires';
const TIMER_CHANNEL = process.env.TIMER_CHANNEL || 'timer:events';

const app = express();
app.use(cors({ origin: '*' }));
app.use(express.json());

const snapshot = {
  scheduler: {
    system_on: false,
    mode: 'MANUAL',
    available_scenes: [],
    loaded_scene: '',
    running_scene: '',
    runtime: {
      cct: 5000,
      lux: 250,
      progress: 0,
    },
    scene_profile: {
      cct: [],
      intensity: [],
    },
  },
  timer: {
    enabled: false,
    start: '',
    end: '',
  },
  luminaires: {},
  last_updated: new Date().toISOString(),
};

const parseHmToHour = (value) => {
  if (typeof value !== 'string' || !value.includes(':')) return null;
  const [h, m] = value.split(':').map(Number);
  if (!Number.isFinite(h) || !Number.isFinite(m)) return null;
  return h + m / 60;
};

const mapScenePoints = (points = []) => {
  const cct = [];
  const intensity = [];
  for (const point of points) {
    const hour = parseHmToHour(point?.time);
    if (hour === null) continue;
    if (typeof point?.cct === 'number') cct.push([hour, point.cct]);
    if (typeof point?.lux === 'number') intensity.push([hour, point.lux]);
  }
  return { cct, intensity };
};

const applySchedulerEvent = (event, payload) => {
  const scheduler = snapshot.scheduler;
  if (event === 'scheduler:state') {
    scheduler.system_on = Boolean(payload?.system_on);
    scheduler.mode = payload?.mode === 'AUTO' ? 'AUTO' : 'MANUAL';
    scheduler.available_scenes = Array.isArray(payload?.available_scenes) ? payload.available_scenes : scheduler.available_scenes;
    scheduler.loaded_scene = payload?.loaded_scene || '';
    scheduler.running_scene = payload?.running_scene || '';
  } else if (event === 'scheduler:runtime') {
    if (typeof payload?.cct === 'number') scheduler.runtime.cct = payload.cct;
    if (typeof payload?.lux === 'number') scheduler.runtime.lux = payload.lux;
    if (typeof payload?.progress === 'number') scheduler.runtime.progress = payload.progress;
  } else if (event === 'scheduler:scene_load') {
    scheduler.loaded_scene = payload?.loaded_scene || scheduler.loaded_scene;
    scheduler.scene_profile = mapScenePoints(Array.isArray(payload?.points) ? payload.points : []);
  } else if (event === 'scheduler:available_scenes') {
    scheduler.available_scenes = Array.isArray(payload?.scenes) ? payload.scenes : scheduler.available_scenes;
  }
};

const applyLuminaireEvent = (event, payload) => {
  const ip = payload?.ip;
  if (!ip || typeof ip !== 'string') return;

  if (!snapshot.luminaires[ip]) {
    snapshot.luminaires[ip] = { ip, connected: false, cw: 0, ww: 0 };
  }

  if (event === 'connection') {
    snapshot.luminaires[ip].connected = true;
  } else if (event === 'disconnection') {
    snapshot.luminaires[ip].connected = false;
  } else if (event === 'ack') {
    if (typeof payload?.cw === 'number') snapshot.luminaires[ip].cw = payload.cw;
    if (typeof payload?.ww === 'number') snapshot.luminaires[ip].ww = payload.ww;
    snapshot.luminaires[ip].connected = true;
  }
};

const applyTimerEvent = (event, payload) => {
  if (event !== 'timer:state') return;
  snapshot.timer.enabled = Boolean(payload?.timer_enabled);
  snapshot.timer.start = typeof payload?.timer_start === 'string' ? payload.timer_start : '';
  snapshot.timer.end = typeof payload?.timer_end === 'string' ? payload.timer_end : '';
};

const sseClients = new Set();
const broadcast = (data) => {
  const body = `data: ${JSON.stringify(data)}\n\n`;
  for (const res of sseClients) {
    res.write(body);
  }
};

app.get('/snapshot', (_req, res) => {
  res.json(snapshot);
});

app.get('/events', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.flushHeaders();

  sseClients.add(res);
  res.write(`data: ${JSON.stringify({ type: 'snapshot', snapshot })}\n\n`);

  const heartbeat = setInterval(() => {
    res.write(': ping\n\n');
  }, 20000);

  req.on('close', () => {
    clearInterval(heartbeat);
    sseClients.delete(res);
  });
});

app.listen(PORT, () => {
  console.log(`event-gateway (SSE) listening on :${PORT}`);
});

const redis = createClient({ url: REDIS_URL });
await redis.connect();
const subscriber = redis.duplicate();
await subscriber.connect();

await subscriber.subscribe([SCHEDULER_CHANNEL, LUMINAIRE_CHANNEL, TIMER_CHANNEL], (raw, channel) => {
  try {
    const parsed = JSON.parse(raw);
    const event = parsed?.event;
    const payload = parsed?.payload ?? parsed;

    if (channel === SCHEDULER_CHANNEL) applySchedulerEvent(event, payload);
    if (channel === LUMINAIRE_CHANNEL) applyLuminaireEvent(event, payload);
    if (channel === TIMER_CHANNEL) applyTimerEvent(event, payload);
    snapshot.last_updated = new Date().toISOString();
    broadcast({ channel, event, payload, snapshot });
  } catch (err) {
    console.error('Failed to process redis event', err);
  }
});
