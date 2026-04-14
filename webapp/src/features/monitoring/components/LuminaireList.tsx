import React, { useMemo, useState } from 'react';
import { Network, Plug, Search } from 'lucide-react';
import { Card } from '../../../components/Card';
import { type Luminaire } from '../../../types/luminaire';
import { useEventSnapshot } from '../../../hooks/useEventSnapshot';

export const LuminaireList: React.FC = () => {
  const { snapshot } = useEventSnapshot();
  const [searchQuery, setSearchQuery] = useState('');
  const [showSearch, setShowSearch] = useState(false);

  const luminaires = useMemo<Luminaire[]>(() => {
    const map = (snapshot?.luminaires as Record<string, { cw?: number; ww?: number; connected?: boolean }> | undefined) ?? {};
    return Object.entries(map)
      .filter(([, value]) => value?.connected !== false)
      .map(([ip, value]) => ({
        id: ip,
        name: ip,
        status: value?.connected === false ? 'OFFLINE' : 'ONLINE',
        cw: Number(value?.cw ?? 0),
        ww: Number(value?.ww ?? 0),
      }));
  }, [snapshot]);

  const filtered = luminaires.filter((l) => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return true;
    return `${l.id} ${l.name}`.toLowerCase().includes(q);
  });

  return (
    <Card
      title="Connected Luminaires"
      icon={Network}
      headerClassName="accent-green"
      className="h-full"
      headerAction={
        <button
          type="button"
          className="icon-toggle"
          aria-label="Toggle search"
          onClick={() => setShowSearch((prev) => !prev)}
        >
          <Search size={25} />
        </button>
      }
    >
      {showSearch ? (
        <div className="relative mb-3">
          <Search
            size={14}
            className="absolute left-2 top-1/2 -translate-y-1/2"
            style={{ color: 'var(--text-muted)' }}
          />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search luminaires..."
            className="w-full h-9 pl-8 pr-2 rounded-lg text-sm motion-soft data-text"
            style={{
              border: '1px solid var(--border-color)',
              background: 'var(--card-bg-soft)',
              color: 'var(--text-primary)',
            }}
          />
        </div>
      ) : null}

      <div className="flex-1 soft-inset p-3 flex items-start justify-start overflow-y-auto">
        {filtered.length === 0 ? (
          <p className="text-xl data-text mt-2 mx-auto" style={{ color: 'var(--text-muted)' }}>
            No Luminaires Connected
          </p>
        ) : (
          <ul className="w-full space-y-2">
            {filtered.map((luminaire) => (
              <li
                key={luminaire.id}
                className="rounded-md px-3 py-2"
                style={{ background: 'var(--card-bg)', border: '1px solid var(--border-color)' }}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <span className="data-text text-sm font-semibold block truncate" style={{ color: 'var(--text-primary)' }}>
                      {luminaire.name}
                    </span>
                    <span className="data-text text-sm font-bold" style={{ color: 'var(--text-secondary)' }}>
                      CW {luminaire.cw.toFixed(2)} | WW {luminaire.ww.toFixed(2)}
                    </span>
                  </div>
                  <span
                    className="h-7 w-7 rounded-md inline-flex items-center justify-center shrink-0"
                    style={{
                      border: '1px solid color-mix(in oklab, var(--accent-blue) 30%, var(--border-color))',
                      background: 'color-mix(in oklab, var(--accent-blue) 8%, var(--card-bg-soft))',
                      color: 'var(--accent-blue)',
                    }}
                    title="Connected device"
                  >
                    <Plug size={25} />
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="mt-3 text-right text-sm font-semibold data-text" style={{ color: 'var(--text-secondary)' }}>
        Total Luminaires: <span style={{ color: 'var(--text-primary)' }}>{filtered.length}</span>
      </div>
    </Card>
  );
};
