export const readErrorMessage = async (response: Response): Promise<string> => {
  const fallback = `HTTP ${response.status}`;
  try {
    const text = await response.text();
    if (!text) return fallback;
    try {
      const parsed = JSON.parse(text) as Record<string, unknown>;
      const detail = parsed?.detail;
      if (typeof detail === 'string' && detail.trim()) return `${fallback}: ${detail}`;
      if (Array.isArray(detail) && detail.length > 0) return `${fallback}: ${JSON.stringify(detail[0])}`;
      const message = parsed?.message ?? parsed?.error;
      if (typeof message === 'string' && message.trim()) return `${fallback}: ${message}`;
      return `${fallback}: ${text}`;
    } catch {
      return `${fallback}: ${text}`;
    }
  } catch {
    return fallback;
  }
};

export const unknownToMessage = (err: unknown): string =>
  err instanceof Error ? err.message : String(err);
