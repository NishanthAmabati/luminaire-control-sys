import express from 'express';
import cors from 'cors';
import { createClient } from 'redis';
import pino from 'pino';
import pinoHttp from 'pino-http';

const requireEnv = (name) => {
  const value = process.env[name];
  if (!value) throw new Error(`missing required env var: ${name}`);
  return value;
};

const toInt = (name) => {
  const value = Number(requireEnv(name));
  if (!Number.isFinite(value)) throw new Error(`invalid integer env var: ${name}`);
  return value;
};

const PORT = toInt('GATEWAY_PORT');
const REDIS_URL = requireEnv('GATEWAY_REDIS_URL');
const STATE_SERVICE_URL = requireEnv('GATEWAY_STATE_SERVICE_URL');
const HEARTBEAT = toInt('GATEWAY_HEARTBEAT_MS');
const LATENCY_INTERVAL = toInt('GATEWAY_LATENCY_INTERVAL_MS');

const CHANNELS = {
  scheduler: requireEnv('GATEWAY_CHANNEL_SCHEDULER'),
  luminaires: requireEnv('GATEWAY_CHANNEL_LUMINAIRES'),
  timer: requireEnv('GATEWAY_CHANNEL_TIMER'),
  metrics: requireEnv('GATEWAY_CHANNEL_METRICS'),
};

const REDIS_RECONNECT_MS = toInt('GATEWAY_REDIS_RECONNECT_MS');

/* ===============================
   LOGGER
================================ */

const logger = pino({
  level: requireEnv('GATEWAY_LOG_LEVEL'),
  transport: { target: 'pino-pretty' },
});

/* ===============================
   EXPRESS
================================ */

const app = express();
app.use(cors({ origin: '*' }));
app.use(express.json());
app.use(pinoHttp({ logger }));

/* ===============================
   SNAPSHOT STATE
================================ */

const snapshot = {
  scheduler: {
    system_on: false,
    mode: 'MANUAL',
    available_scenes: [],
    loaded_scene: '',
    running_scene: '',
    runtime: { cct: 5000, lux: 250, progress: 0 },
    manual_input: { cw: null, ww: null },
    scene_profile: { cct: [], intensity: [] },
  },
  timer: { enabled: false, start: '', end: '' },
  metrics: { cpu: null, memory: null, temperature: null },
  luminaires: {},
  last_updated: new Date().toISOString(),
};

function updateSnapshot(mutator) {
  mutator(snapshot);
  snapshot.last_updated = new Date().toISOString();
}

/* ===============================
   UTILITIES
================================ */

const parseHmToHour = (v) => {
  if (!v?.includes(':')) return null;
  const [h, m] = v.split(':').map(Number);
  if (!Number.isFinite(h)) return null;
  return h + m / 60;
};

const mapScenePoints = (points = []) => {
  const cct = [];
  const intensity = [];

  for (const p of points) {
    const hour = parseHmToHour(p.time);
    if (hour === null) continue;

    if (typeof p.cct === 'number') cct.push([hour, p.cct]);
    if (typeof p.lux === 'number') intensity.push([hour, p.lux]);
  }

  return { cct, intensity };
};

/* ===============================
   EVENT HANDLERS
================================ */

function applyScheduler(event, payload) {
  updateSnapshot((s) => {
    const sch = s.scheduler;

    if (event === 'scheduler:state') {
      if (typeof payload?.system_on === 'boolean') sch.system_on = payload.system_on;
      sch.mode = payload?.mode === 'AUTO' ? 'AUTO' : 'MANUAL';
      sch.available_scenes = payload?.available_scenes ?? sch.available_scenes;
      sch.loaded_scene = payload?.loaded_scene || '';
      sch.running_scene = payload?.running_scene || '';
    }

    if (event === 'scheduler:runtime') {
      Object.assign(sch.runtime, payload || {});

      if (typeof payload?.system_on === 'boolean') {
        sch.system_on = payload.system_on;
      } else if (
        sch.system_on === false &&
        (Number(payload?.cct ?? 0) > 0 || Number(payload?.lux ?? 0) > 0 || Boolean(sch.running_scene))
      ) {
        // If state event was missed, infer "on" from active runtime.
        sch.system_on = true;
      }
    }

    if (event === 'scheduler:scene_load' || event === 'scheduler:scene_loaded') {
      sch.loaded_scene = payload?.loaded_scene || payload?.scene || sch.loaded_scene;
      sch.scene_profile = mapScenePoints(Array.isArray(payload?.points) ? payload.points : []);
    }

    if (event === 'scheduler:available_scenes') {
      sch.available_scenes = Array.isArray(payload?.scenes)
        ? payload.scenes
        : Array.isArray(payload?.available_scenes)
          ? payload.available_scenes
          : sch.available_scenes;
    }
  });
}

function applyLuminaire(event, payload) {
  updateSnapshot((s) => {
    const ip = payload?.ip;
    if (!ip) return;

    if (!s.luminaires[ip]) {
      s.luminaires[ip] = { ip, connected: false, cw: 0, ww: 0 };
    }

    const dev = s.luminaires[ip];

    if (event === 'connection') dev.connected = true;
    if (event === 'disconnection') dev.connected = false;

    if (event === 'ack') {
      dev.connected = true;
      dev.cw = payload?.cw ?? dev.cw;
      dev.ww = payload?.ww ?? dev.ww;
    }
  });
}

function applyTimer(event, payload) {
  if (event !== 'timer:state') return;

  updateSnapshot((s) => {
    s.timer.enabled = !!payload?.timer_enabled;
    s.timer.start = payload?.timer_start || '';
    s.timer.end = payload?.timer_end || '';
  });
}

function applyMetrics(event, payload) {
  if (event !== 'metrics:events') return;
  updateSnapshot((s) => {
    s.metrics = {
      cpu: typeof payload?.cpu === 'number' ? payload.cpu : s.metrics.cpu,
      memory: typeof payload?.memory === 'number' ? payload.memory : s.metrics.memory,
      temperature: typeof payload?.temperature === 'number' ? payload.temperature : s.metrics.temperature,
    };
  });
}

function applyStateSnapshot(state) {
  if (!state || typeof state !== 'object') return;
  updateSnapshot((s) => {
    const scheduler = s.scheduler;
    const timer = s.timer;
    const metrics = s.metrics;

    if (typeof state.system_on === 'boolean') scheduler.system_on = state.system_on;
    scheduler.mode = state?.mode === 'AUTO' ? 'AUTO' : 'MANUAL';

    if (state?.auto && typeof state.auto === 'object') {
      scheduler.loaded_scene = state.auto.loaded_scene || scheduler.loaded_scene;
      scheduler.running_scene = state.auto.running_scene || scheduler.running_scene;
      if (scheduler.mode === 'AUTO') {
        if (typeof state.auto.cct === 'number') scheduler.runtime.cct = state.auto.cct;
        if (typeof state.auto.lux === 'number') scheduler.runtime.lux = state.auto.lux;
      }
    }

    if (state?.manual && typeof state.manual === 'object' && scheduler.mode === 'MANUAL') {
      if (typeof state.manual.cct === 'number') scheduler.runtime.cct = state.manual.cct;
      if (typeof state.manual.lux === 'number') scheduler.runtime.lux = state.manual.lux;
      if (typeof state.manual.cw === 'number') scheduler.manual_input.cw = state.manual.cw;
      if (typeof state.manual.ww === 'number') scheduler.manual_input.ww = state.manual.ww;
    }

    if (state?.timer && typeof state.timer === 'object') {
      if (typeof state.timer.enabled === 'boolean') timer.enabled = state.timer.enabled;
      if (typeof state.timer.start === 'string') timer.start = state.timer.start;
      if (typeof state.timer.end === 'string') timer.end = state.timer.end;
    }

    if (state?.metrics && typeof state.metrics === 'object') {
      if (typeof state.metrics.cpu === 'number') metrics.cpu = state.metrics.cpu;
      if (typeof state.metrics.memory === 'number') metrics.memory = state.metrics.memory;
      if (typeof state.metrics.temperature === 'number') metrics.temperature = state.metrics.temperature;
    }
  });
}

async function bootstrapFromStateService() {
  if (!STATE_SERVICE_URL) return false;
  try {
    const response = await fetch(STATE_SERVICE_URL);
    if (!response.ok) throw new Error(`state service responded ${response.status}`);
    const state = await response.json();
    applyStateSnapshot(state);
    if (state?.mode === 'AUTO') {
      const base = STATE_SERVICE_URL.replace(/\/state$/, '');
      const sceneToLoad = state?.auto?.running_scene || state?.auto?.loaded_scene;
      try {
        await fetch(`${base}/scene/available`);
      } catch (err) {
        logger.warn({ err }, 'failed to refresh available scenes');
      }
      if (sceneToLoad) {
        try {
          // Trigger scheduler to publish scheduler:scene_load with full profile points.
          await fetch(`${base}/scene/load`, {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ scene: sceneToLoad }),
          });
        } catch (err) {
          logger.warn({ err, scene: sceneToLoad }, 'failed to refresh scene profile');
        }
      }
    }
    logger.info('state service snapshot loaded');
    return true;
  } catch (err) {
    logger.warn({ err }, 'failed to fetch state service snapshot');
    return false;
  }
}

/* ===============================
   SSE
================================ */

const clients = new Set();

async function broadcast(data) {
  if (STATE_SERVICE_URL) {
    try {
      const response = await fetch(STATE_SERVICE_URL);
      if (response.ok) {
        const state = await response.json();
        // Update manual_input from state service
        if (state?.manual && snapshot.scheduler.mode === 'MANUAL') {
          if (typeof state.manual.cw === 'number') {
            snapshot.scheduler.manual_input.cw = state.manual.cw;
          }
          if (typeof state.manual.ww === 'number') {
            snapshot.scheduler.manual_input.ww = state.manual.ww;
          }
        }
      }
    } catch (err) {
      // Silently fail - use existing values
    }
  }
  const msg = `data: ${JSON.stringify(data)}\n\n`;
  for (const res of clients) {
    try {
      res.write(msg);
    } catch {
      clients.delete(res);
    }
  }
}

app.get('/events', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');

  clients.add(res);

  res.write(
    `data: ${JSON.stringify({ type: 'snapshot', snapshot })}\n\n`
  );

  const hb = setInterval(() => res.write(': ping\n\n'), HEARTBEAT);

  req.on('close', () => {
    clearInterval(hb);
    clients.delete(res);
    logger.info('SSE client disconnected');
  });
});

setInterval(() => {
  broadcast({ type: 'heartbeat', server_time: Date.now() });
}, LATENCY_INTERVAL);

/* ===============================
   HEALTH
================================ */

app.get('/health', (_, res) => {
  res.json({
    status: 'ok',
    redis: redis.isOpen,
    clients: clients.size,
  });
});

app.get('/snapshot', (_, res) => res.json(snapshot));

/* ===============================
   REDIS
================================ */

const redis = createClient({
  url: REDIS_URL,
  socket: {
    reconnectStrategy: () => REDIS_RECONNECT_MS,
  },
});

redis.on('error', (e) => logger.error(e, 'Redis error'));

await redis.connect();

const sub = redis.duplicate();
await sub.connect();

await sub.subscribe([CHANNELS.scheduler, CHANNELS.luminaires, CHANNELS.timer, CHANNELS.metrics], (raw, channel) => {
  try {
    const msg = JSON.parse(raw);
    const event = msg?.event;
    const payload = msg?.payload ?? msg;

    if (!event) {
      logger.warn({ channel, msg }, 'Redis message missing event field');
      return;
    }

    if (channel === CHANNELS.scheduler) applyScheduler(event, payload);
    if (channel === CHANNELS.luminaires) applyLuminaire(event, payload);
    if (channel === CHANNELS.timer) applyTimer(event, payload);
    if (channel === CHANNELS.metrics) applyMetrics(event, payload);

    broadcast({ channel, event, payload, snapshot });
  } catch (err) {
    logger.error(err, 'Redis event parse failed');
  }
});

/* ===============================
   START
================================ */

const startBootstrap = async () => {
  let attempts = 0;
  const maxAttempts = 12;
  const intervalMs = 5000;
  while (attempts < maxAttempts) {
    attempts += 1;
    const ok = await bootstrapFromStateService();
    if (ok) return;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  logger.warn('state service snapshot bootstrap failed after retries');
};

void startBootstrap();

app.listen(PORT, () => logger.info(`event-gateway listening on ${PORT}`));

/* ===============================
   GRACEFUL SHUTDOWN
================================ */

async function shutdown() {
  logger.info('Shutting down');

  await sub.quit();
  await redis.quit();

  process.exit(0);
}

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
