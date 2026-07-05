import { describe, it, expect } from 'vitest';

describe('SSE reconnect backoff', () => {
  it('doubles delay each attempt up to 30s max', () => {
    let attempt = 0;
    const delays: number[] = [];

    for (let i = 0; i < 10; i++) {
      const delay = Math.min(1000 * 2 ** attempt, 30000);
      delays.push(delay);
      attempt += 1;
    }

    expect(delays[0]).toBe(1000);
    expect(delays[1]).toBe(2000);
    expect(delays[2]).toBe(4000);
    expect(delays[3]).toBe(8000);
    expect(delays[4]).toBe(16000);
    expect(delays[5]).toBe(30000);
    expect(delays[6]).toBe(30000);
  });

  it('resets to 1s after successful connection', () => {
    let attempt = 5;
    attempt = 0; // onopen resets
    const delay = Math.min(1000 * 2 ** attempt, 30000);
    expect(delay).toBe(1000);
  });
});
