import { createContext, useContext, useCallback, useState, type ReactNode } from 'react';
import { TRACE_HEADER } from '../constants/trace';

interface TraceContextValue {
  traceId: string | null;
  generateTraceId: () => string;
  withTraceId: <T extends Record<string, unknown>>(data: T) => T;
  createTraceHeaders: () => Record<string, string>;
}

const TraceContext = createContext<TraceContextValue | null>(null);

export const TraceProvider = ({ children }: { children: ReactNode }) => {
  const [traceId, setTraceId] = useState<string | null>(null);

  const generateTraceId = useCallback((): string => {
    const id = crypto.randomUUID();
    setTraceId(id);
    console.debug('[Trace] Generated new trace_id:', id);
    return id;
  }, []);

  const withTraceId = useCallback(<T extends Record<string, unknown>>(data: T): T => {
    return {
      ...data,
      trace_id: traceId,
    };
  }, [traceId]);

  const createTraceHeaders = useCallback((): Record<string, string> => {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (traceId) {
      headers[TRACE_HEADER] = traceId;
    }
    return headers;
  }, [traceId]);

  return (
    <TraceContext.Provider value={{
      traceId,
      generateTraceId,
      withTraceId,
      createTraceHeaders,
    }}>
      {children}
    </TraceContext.Provider>
  );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useTrace = (): TraceContextValue => {
  const context = useContext(TraceContext);
  if (!context) {
    throw new Error('useTrace must be used within a TraceProvider');
  }
  return context;
};
