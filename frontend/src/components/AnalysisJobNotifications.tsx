import { useEffect, useMemo, useRef, useState } from 'react';
import { Bell } from 'lucide-react';
import { useAnalysisJobs } from '../state/analysisJobs';
import type { AnalysisJob } from '../state/analysisJobs';

type AnalysisJobNotificationsProps = {
  onNavigate?: (job: AnalysisJob) => void;
};

const formatTime = (timestamp: number) => {
  const date = new Date(timestamp);
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

export function AnalysisJobNotifications({ onNavigate }: AnalysisJobNotificationsProps) {
  const { jobs, markRead, markAllRead } = useAnalysisJobs();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const unread = useMemo(
    () => jobs.some((job) => job.unread && (job.status === 'done' || job.status === 'error')),
    [jobs]
  );

  const recentJobs = useMemo(() => {
    return [...jobs].sort((a, b) => b.updatedAt - a.updatedAt).slice(0, 10);
  }, [jobs]);

  useEffect(() => {
    if (!open) return;
    const handleClick = (event: MouseEvent) => {
      if (!containerRef.current) return;
      if (!containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  const handleJobClick = (job: AnalysisJob) => {
    markRead(job.jobId);
    setOpen(false);
    onNavigate?.(job);
  };

  return (
    <div className="relative z-[2100]" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className={`relative inline-flex h-9 w-9 items-center justify-center rounded-lg border shadow-sm transition ${
          unread
            ? 'border-rose-300 bg-rose-50 text-rose-600 hover:bg-rose-100'
            : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
        }`}
        aria-label="Analysis notifications"
      >
        <Bell className="h-4 w-4" />
        {unread && <span className="absolute -right-1 -top-1 h-3 w-3 rounded-full bg-rose-500" />}
      </button>
      {open && (
        <div className="absolute right-0 z-[2200] mt-2 w-72 rounded-xl border border-slate-200 bg-white shadow-xl">
          <div className="flex items-center justify-between px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            <span>Analysis Jobs</span>
            {unread && (
              <button
                type="button"
                onClick={() => markAllRead()}
                className="text-[10px] font-semibold text-rose-500 hover:text-rose-600"
              >
                Mark all read
              </button>
            )}
          </div>
          <div className="max-h-80 overflow-auto">
            {recentJobs.length === 0 ? (
              <div className="px-3 py-3 text-sm text-slate-500">No jobs yet.</div>
            ) : (
              recentJobs.map((job) => (
                <button
                  key={job.jobId}
                  type="button"
                  onClick={() => handleJobClick(job)}
                  className="w-full border-t border-slate-100 px-3 py-2 text-left transition hover:bg-slate-50"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-slate-700">
                      {job.selection
                        ? `${job.selection.state_name ?? job.selection.state_fips} · ${
                            job.selection.county_name ?? job.selection.county_fips
                          }`
                        : job.jobId}
                    </span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ${
                        job.status === 'done'
                          ? 'bg-emerald-100 text-emerald-700'
                          : job.status === 'error'
                          ? 'bg-rose-100 text-rose-700'
                          : job.status === 'running'
                          ? 'bg-blue-100 text-blue-700'
                          : 'bg-slate-100 text-slate-600'
                      }`}
                    >
                      {job.status}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-slate-500">
                    {job.message ?? 'No message'}
                  </div>
                  <div className="mt-1 text-[10px] text-slate-400">{formatTime(job.updatedAt)}</div>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
