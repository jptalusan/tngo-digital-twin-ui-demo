import { useCallback, useRef, useState } from 'react';
import type { ApiError } from '../http';

export type MutationState<T> = {
  status: 'idle' | 'loading' | 'success' | 'error';
  data?: T;
  error?: ApiError;
};

export function useMutation<TVariables, TData>(
  mutate: (variables: TVariables) => Promise<TData>
) {
  const [state, setState] = useState<MutationState<TData>>({ status: 'idle' });
  const mountedRef = useRef(true);

  const execute = useCallback(async (variables: TVariables) => {
    mountedRef.current = true;
    setState({ status: 'loading' });
    try {
      const data = await mutate(variables);
      if (!mountedRef.current) return data;
      setState({ status: 'success', data });
      return data;
    } catch (error) {
      if (!mountedRef.current) throw error;
      setState({ status: 'error', error: error as ApiError });
      throw error;
    }
  }, [mutate]);

  const reset = useCallback(() => setState({ status: 'idle' }), []);

  return { ...state, execute, reset };
}
