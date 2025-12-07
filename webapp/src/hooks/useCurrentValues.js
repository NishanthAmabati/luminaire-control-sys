import { useState, useEffect, useRef } from 'react';

/**
 * Custom hook to subscribe to current CCT and Intensity updates via WebSocket
 * Returns current values that update independently
 */
export const useCurrentValues = (ws) => {
  const [currentValues, setCurrentValues] = useState({
    current_cct: 3500,
    current_intensity: 250,
    cw: 50.0,
    ww: 50.0
  });

  const messageHandlerRef = useRef(null);

  useEffect(() => {
    if (!ws || !ws.current) return;

    const handleMessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === 'live_update') {
          setCurrentValues(prev => ({
            ...prev,
            ...(data.data.current_cct !== undefined && { current_cct: data.data.current_cct }),
            ...(data.data.current_intensity !== undefined && { current_intensity: data.data.current_intensity }),
            ...(data.data.cw !== undefined && { cw: data.data.cw }),
            ...(data.data.ww !== undefined && { ww: data.data.ww })
          }));
        }
      } catch (error) {
        console.error('[useCurrentValues] Error parsing message:', error);
      }
    };

    messageHandlerRef.current = handleMessage;
    ws.current.addEventListener('message', handleMessage);

    return () => {
      if (ws.current && messageHandlerRef.current) {
        ws.current.removeEventListener('message', messageHandlerRef.current);
      }
    };
  }, [ws]);

  return currentValues;
};
