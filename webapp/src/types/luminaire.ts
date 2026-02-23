export interface Luminaire {
  id: string;
  name: string;
  status: 'ONLINE' | 'OFFLINE';
  cw: number;
  ww: number;
}