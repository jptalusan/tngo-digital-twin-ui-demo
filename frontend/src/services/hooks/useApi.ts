import { useCallback, useEffect, useRef, useState } from 'react';
import type { ApiError } from '../http';

export type ApiState<T> = {
  status: 'idle' | 'loading' | 'success' | 'error';
  data?: T;
  error?: ApiError;
};

export type UseApiOptions<T> = {
  enabled?: boolean;
  initialData?: T;
};

export function useApi<T>(
  fetcher: () => Promise<T>,
  deps: React.DependencyList,
  options: UseApiOptions<T> = {}
) {
  const { enabled = true, initialData } = options;
  const [state, setState] = useState<ApiState<T>>({
    status: initialData ? 'success' : 'idle',
    data: initialData,
  });
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const run = useCallback(async () => {
    setState((prev) => ({ ...prev, status: 'loading', error: undefined }));
    try {
      const data = await fetcher();
      if (!mountedRef.current) return;
      setState({ status: 'success', data });
    } catch (error) {
      if (!mountedRef.current) return;
      setState({ status: 'error', error: error as ApiError });
    }
  }, deps);

  useEffect(() => {
    if (!enabled) return;
    void run();
  }, [enabled, run]);

  return { ...state, refetch: run };
}
