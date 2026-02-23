import { useState } from 'react';

export const useControl = (endpoint: string, initialValue: number) => {
  const [value, setValue] = useState(initialValue);
  const [isPending, setIsPending] = useState(false);

  const updateValue = async (newValue: number) => {
    setValue(newValue);
    setIsPending(true);
    try {
      await fetch(`/api/v1/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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