export interface SystemStats {
  latency: number | null;
  cpu: number | null;
  memory: number | null;
  temperature: number | null;
  currentCct: number;
  currentLux: number;
  systemOn: boolean;
  mode?: 'AUTO' | 'MANUAL';
  loadedScene?: string;
  runningScene?: string;
  sceneProgress?: number;
  timerStart?: string;
  timerEnd?: string;
  timerEnabled?: boolean;
  status: 'ACTIVE' | 'INACTIVE' | 'ERROR';
  lastSync: string;
}
