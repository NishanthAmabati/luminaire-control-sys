import { useContext } from 'react';
import { UiFeedbackContext } from './uiFeedback.context';

export const useUiFeedback = () => {
  const ctx = useContext(UiFeedbackContext);
  if (!ctx) throw new Error('useUiFeedback must be used within UiFeedbackProvider');
  return ctx;
};
