import { useState } from 'react';
import { useTrace } from '../context/TraceContext';

export const useControl = (endpoint: string, initialValue: number) => {
  const [value, setValue] = useState(initialValue);
  const [isPending, setIsPending] = useState(false);
  const { createTraceHeaders, generateTraceId } = useTrace();

  const updateValue = async (newValue: number) => {
    setValue(newValue);
    setIsPending(true);
    generateTraceId();
    try {
      await fetch(`/api/v1/${endpoint}`, {
        method: 'POST',
        headers: createTraceHeaders(),
        body: JSON.stringify({ value: newValue }),
      });
    } catch (error) {
      console.error(`Failed to update ${endpoint}:`, error);
    } finally {
      setIsPending(false);
    }
  };

  return { value, updateValue, isPending };
};
