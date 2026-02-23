import { createContext } from 'react';

export interface UiFeedbackContextValue {
  pushError: (message: string) => void;
  pushSuccess: (message: string) => void;
}

export const UiFeedbackContext = createContext<UiFeedbackContextValue | null>(null);
