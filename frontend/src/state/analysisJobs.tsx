import type { ReactNode } from 'react';
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState
} from 'react';
import type { MoveODAnalysisSelection } from '../components/MoveODAnalysisPage';

type AnalysisJobStatus = 'queued' | 'running' | 'done' | 'error' | 'unknown';

export type AnalysisJob = {
  jobId: string;
  status: AnalysisJobStatus;
  message?: string;
  unread: boolean;
  createdAt: number;
  updatedAt: number;
  selection?: MoveODAnalysisSelection;
};

type AnalysisJobsContextValue = {
  jobs: AnalysisJob[];
  startJob: (jobId: string, selection?: MoveODAnalysisSelection) => void;
  markRead: (jobId: string) => void;
};

const AnalysisJobsContext = createContext<AnalysisJobsContextValue | null>(null);

const apiBase =
  (import.meta.env.VITE_API_URL as string | undefined) ??
  (typeof window !== 'undefined' ? window.location.origin : '');

const getNow = () => Date.now();

export function AnalysisJobsProvider({ children }: { children: ReactNode }) {
  const [jobs, setJobs] = useState<AnalysisJob[]>([]);
  const jobsRef = useRef<AnalysisJob[]>([]);
  const eventSourcesRef = useRef<Map<string, EventSource>>(new Map());
  const pollingRef = useRef<Map<string, number>>(new Map());

  useEffect(() => {
    jobsRef.current = jobs;
  }, [jobs]);

  const upsertJob = useCallback((jobId: string, partial: Partial<AnalysisJob>) => {
    setJobs((prev) => {
      const existingIndex = prev.findIndex((job) => job.jobId === jobId);
      const now = getNow();
      if (existingIndex === -1) {
        const createdAt = partial.createdAt ?? now;
        const next: AnalysisJob = {
          jobId,
          status: partial.status ?? 'queued',
          message: partial.message,
          unread: partial.unread ?? false,
          createdAt,
          updatedAt: partial.updatedAt ?? now,
          selection: partial.selection
        };
        return [next, ...prev].slice(0, 50);
      }
      const existing = prev[existingIndex];
      const updated: AnalysisJob = {
        ...existing,
        ...partial,
        updatedAt: partial.updatedAt ?? now
      };
      const next = [...prev];
      next[existingIndex] = updated;
      return next;
    });
  }, []);

  const stopPolling = useCallback((jobId: string) => {
    const handle = pollingRef.current.get(jobId);
    if (handle) {
      window.clearInterval(handle);
      pollingRef.current.delete(jobId);
    }
  }, []);

  const stopEventSource = useCallback((jobId: string) => {
    const source = eventSourcesRef.current.get(jobId);
    if (source) {
      source.close();
      eventSourcesRef.current.delete(jobId);
    }
  }, []);

  const finalizeJob = useCallback(
    (jobId: string) => {
      stopEventSource(jobId);
      stopPolling(jobId);
    },
    [stopEventSource, stopPolling]
  );

  const handleStatusPayload = useCallback(
    (jobId: string, payload: any) => {
      const status = (payload?.status ?? payload?.state ?? 'unknown') as AnalysisJobStatus;
      const message = typeof payload?.message === 'string' ? payload.message : undefined;
      const done = status === 'done' || status === 'error';
      upsertJob(jobId, {
        status,
        message,
        unread: done ? true : undefined,
        updatedAt: getNow()
      });
      if (done) {
        finalizeJob(jobId);
      }
    },
    [finalizeJob, upsertJob]
  );

  const startPolling = useCallback(
    (jobId: string) => {
      if (pollingRef.current.has(jobId)) return;
      console.log('[MoveOD][SSE] polling start', { jobId });
      upsertJob(jobId, { message: 'Polling status…', updatedAt: getNow() });
      const handle = window.setInterval(async () => {
        try {
          const response = await fetch(`${apiBase}/api/moveod/analysis/status?job_id=${encodeURIComponent(jobId)}`);
          if (!response.ok) {
            throw new Error(await response.text());
          }
          const payload = await response.json();
          handleStatusPayload(jobId, payload);
        } catch (err: any) {
          const message = typeof err?.message === 'string' ? err.message : 'Status polling failed';
          upsertJob(jobId, { message, updatedAt: getNow() });
        }
      }, 2500);
      pollingRef.current.set(jobId, handle);
    },
    [handleStatusPayload, upsertJob]
  );

  const startEventSource = useCallback(
    (jobId: string) => {
      if (eventSourcesRef.current.has(jobId)) return;
      const attempts = [
        `${apiBase}/api/moveod/analysis/stream?job_id=${encodeURIComponent(jobId)}`
      ];
      let attemptIndex = 0;

      const openSource = () => {
        if (attemptIndex >= attempts.length) {
          console.log('[MoveOD][SSE] falling back to polling', { jobId });
          startPolling(jobId);
          return;
        }
        const url = attempts[attemptIndex];
        attemptIndex += 1;
        try {
          console.log('[MoveOD][SSE] opening', { jobId, url });
          const source = new EventSource(url);
          eventSourcesRef.current.set(jobId, source);
          upsertJob(jobId, { message: 'Connecting…', updatedAt: getNow() });
          source.onopen = () => {
            console.log('[MoveOD][SSE] connected', { jobId, url });
            upsertJob(jobId, { message: 'Live updates connected', updatedAt: getNow() });
          };
          source.addEventListener('status', (event) => {
            try {
              const payload = JSON.parse((event as MessageEvent).data);
              console.log('[MoveOD][SSE] status', { jobId, payload });
              handleStatusPayload(jobId, payload);
            } catch {
              console.log('[MoveOD][SSE] status parse failed', { jobId });
              upsertJob(jobId, { message: 'Failed to parse status update', updatedAt: getNow() });
            }
          });
          source.onerror = () => {
            console.log('[MoveOD][SSE] error, retrying', { jobId, url });
            stopEventSource(jobId);
            const current = jobsRef.current.find((job) => job.jobId === jobId);
            if (!current || (current.status !== 'done' && current.status !== 'error')) {
              openSource();
            }
          };
        } catch {
          openSource();
        }
      };

      openSource();
    },
    [handleStatusPayload, startPolling, stopEventSource, upsertJob]
  );

  const startJob = useCallback(
    (jobId: string, selection?: MoveODAnalysisSelection) => {
      upsertJob(jobId, {
        status: 'queued',
        message: 'Queued',
        unread: false,
        createdAt: getNow(),
        selection
      });
      startEventSource(jobId);
    },
    [startEventSource, upsertJob]
  );

  const markRead = useCallback((jobId: string) => {
    upsertJob(jobId, { unread: false, updatedAt: getNow() });
  }, [upsertJob]);

  useEffect(() => {
    return () => {
      eventSourcesRef.current.forEach((source) => source.close());
      eventSourcesRef.current.clear();
      pollingRef.current.forEach((handle) => window.clearInterval(handle));
      pollingRef.current.clear();
    };
  }, []);

  const value = useMemo<AnalysisJobsContextValue>(
    () => ({
      jobs,
      startJob,
      markRead
    }),
    [jobs, markRead, startJob]
  );

  return <AnalysisJobsContext.Provider value={value}>{children}</AnalysisJobsContext.Provider>;
}

export function useAnalysisJobs() {
  const context = useContext(AnalysisJobsContext);
  if (!context) {
    throw new Error('useAnalysisJobs must be used within AnalysisJobsProvider');
  }
  return context;
}
