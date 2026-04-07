import { TRACE_HEADER } from '../constants/trace';

interface FetchOptions extends RequestInit {
  traceId?: string;
}

export async function traceFetch(
  url: string,
  options: FetchOptions = {}
): Promise<Response> {
  const { traceId, ...fetchOptions } = options;
  
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(fetchOptions.headers as Record<string, string> || {}),
  };
  
  if (traceId) {
    headers[TRACE_HEADER] = traceId;
  }

  return fetch(url, {
    ...fetchOptions,
    headers,
  });
}
