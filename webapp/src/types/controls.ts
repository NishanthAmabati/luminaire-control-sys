// src/types/controls.ts
export type ControlMode = 'MANUAL' | 'AUTO';

export interface LuminaireState {
  intensity: number;
  cct: number;
  mode: ControlMode;
}