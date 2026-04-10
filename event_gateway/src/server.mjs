import express from 'express';
import cors from 'cors';
import { createClient } from 'redis';
import pino from 'pino';
import pinoHttp from 'pino-http';
import { randomUUID } from 'crypto';

const TRACE_HEADER = 'X-Trace-ID';

const requireEnv = (name) => {
  const value = process.env[name];
  if (!value) throw new Error(`missing required env var ${name}`);
  return value;
};

const logger = pino({
  level: process.env.GATEWAY_LOG_LEVEL || 'info',
  transport: process.env.NODE_ENV === 'production' ? undefined : { target: 'pino-pretty' },
});

const log = logger.child({ module: 'gateway' });

const PORT = Number(process.env.GATEWAY_PORT);
const REDIS_URL = requireEnv('GATEWAY_REDIS_URL');
const STATE_SERVICE_URL = requireEnv('GATEWAY_STATE_SERVICE_URL');
const HEARTBEAT = Number(process.env.GATEWAY_HEARTBEAT_MS);
const LATENCY_INTERVAL = Number(process.env.GATEWAY_LATENCY_INTERVAL_MS);

const CHANNELS = {
  scheduler: requireEnv('GATEWAY_CHANNEL_SCHEDULER'),
  luminaires: requireEnv('GATEWAY_CHANNEL_LUMINAIRES'),
  timer: requireEnv('GATEWAY_CHANNEL_TIMER'),
  metrics: requireEnv('GATEWAY_CHANNEL_METRICS'),
};

const app = express();
app.use(cors({ origin: '*' }));
app.use(express.json());

app.use((req, res, next) => {
  const incomingTraceId = req.headers[TRACE_HEADER.toLowerCase()];
  const traceId = (incomingTraceId && isValidUUID(incomingTraceId)) ? incomingTraceId : randomUUID();
  
  req.traceId = traceId;
  res.setHeader(TRACE_HEADER, traceId);
  req.log = log.child({ trace_id: traceId });
  
  next();
});

app.use(pinoHttp({ 
  logger,
  useLevel: 'debug',
  autoLogging: { ignore: (req) => req.url === '/health' } 
}));

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

const parseHmToHour = (v) => {
  if (!v?.includes(':')) return null;
  const [h, m] = v.split(':').map(Number);
  return Number.isFinite(h) ? h + m / 60 : null;
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
        sch.system_on = true;
      }
    }
    if (event === 'scheduler:scene_load' || event === 'scheduler:scene_loaded') {
      sch.loaded_scene = payload?.loaded_scene || payload?.scene || sch.loaded_scene;
      sch.scene_profile = mapScenePoints(Array.isArray(payload?.points) ? payload.points : []);
    }
    if (event === 'scheduler:available_scenes') {
      sch.available_scenes = payload?.scenes || payload?.available_scenes || sch.available_scenes;
    }
    if (event === 'scheduler:scene_stopped') {
      sch.running_scene = '';
      sch.loaded_scene = '';
      sch.scene_profile = { cct: [], intensity: [] };
    }
  });
}

const clients = new Set();

function broadcast(data) {
  const msg = `data: ${JSON.stringify(data)}\n\n`;
  clients.forEach(res => {
    try {
      res.write(msg);
    } catch (err) {
      clients.delete(res);
    }
  });
}

app.get('/events', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');

  clients.add(res);
  req.log.info(`new sse client connected total ${clients.size}`);

  res.write(`data: ${JSON.stringify({ type: 'snapshot', snapshot, trace_id: req.traceId })}\n\n`);

  const hb = setInterval(() => res.write(': ping\n\n'), HEARTBEAT);

  req.on('close', () => {
    clearInterval(hb);
    clients.delete(res);
    req.log.info(`sse client disconnected total ${clients.size}`);
  });
});

setInterval(() => {
  broadcast({ type: 'heartbeat', server_time: Date.now() });
}, LATENCY_INTERVAL);

const redis = createClient({ url: REDIS_URL });
const sub = redis.duplicate();

sub.on('error', (err) => log.error({ err }, 'redis subscriber error'));
redis.on('error', (err) => log.error({ err }, 'redis client error'));

async function startRedis() {
  await redis.connect();
  await sub.connect();
  log.info('connected to redis cluster');

  await sub.subscribe(Object.values(CHANNELS), (raw, channel) => {
    try {
      const msg = JSON.parse(raw);
      const event = msg?.event;
      const payload = msg?.payload ?? msg;

      if (!event) return;

      if (channel === CHANNELS.scheduler) applyScheduler(event, payload);

      broadcast({ channel, event, payload, snapshot, trace_id: msg?.trace_id });
    } catch (err) {
      log.error({ err }, 'failed to process redis message');
    }
  });
}

function isValidUUID(str) {
  const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
  return uuidRegex.test(str);
}

async function bootstrap() {
  log.info('bootstrapping snapshot from state service');
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    
    const response = await fetch(STATE_SERVICE_URL, { 
      signal: controller.signal,
      headers: { [TRACE_HEADER]: randomUUID() }
    });
    clearTimeout(timeout);

    if (response.ok) {
      const state = await response.json();
      updateSnapshot((s) => {
        if (typeof state?.system_on === 'boolean') {
          s.scheduler.system_on = state.system_on;
        }
        s.scheduler.mode = state?.mode === 'AUTO' ? 'AUTO' : 'MANUAL';
        s.scheduler.loaded_scene = state?.auto?.loaded_scene || '';
        s.scheduler.running_scene = state?.auto?.running_scene || '';
        if (state?.auto?.cct !== undefined) s.scheduler.runtime.cct = state.auto.cct;
        if (state?.auto?.lux !== undefined) s.scheduler.runtime.lux = state.auto.lux;
      });
      log.info('initial snapshot hydration complete');
    }
  } catch (err) {
    log.warn({ err }, 'bootstrap failed - waiting for redis events to fill state');
  }
}

app.listen(PORT, async () => {
  log.info(`event gateway listening on port ${PORT}`);
  await startRedis();
  await bootstrap();
});

async function shutdown() {
  log.info('initiating graceful shutdown');
  await sub.quit();
  await redis.quit();
  process.exit(0);
}

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
