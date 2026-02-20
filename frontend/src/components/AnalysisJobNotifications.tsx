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

const formatElapsed = (ms: number) => {
  if (!Number.isFinite(ms) || ms < 0) return '0s';
  const totalSeconds = Math.round(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes <= 0) return `${seconds}s`;
  return `${minutes}m ${seconds}s`;
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
        className="btn btn-outline relative"
        aria-label="Analysis notifications"
        data-active={unread}
      >
        <Bell className="h-4 w-4" />
        {unread && <span className="absolute -right-1 -top-1 h-3 w-3 rounded-full" style={{ backgroundColor: '#f43f5e' }} />}
      </button>
      {open && (
        <div className="absolute right-0 z-[2200] mt-2 w-96 floating-card">
          <div className="flex items-center justify-between px-2 py-2 text-xs font-semibold uppercase tracking-wide text-muted">
            <span>Analysis Jobs</span>
            {unread && (
              <button
                type="button"
                onClick={() => markAllRead()}
                className="btn btn-ghost"
              >
                Mark all read
              </button>
            )}
          </div>
          <div className="max-h-80 overflow-auto">
            {recentJobs.length === 0 ? (
              <div className="px-3 py-3 text-sm text-muted">No jobs yet.</div>
            ) : (
              recentJobs.map((job) => (
                <button
                  key={job.jobId}
                  type="button"
                  onClick={() => handleJobClick(job)}
                  className="w-full border-t border-default px-3 py-2 text-left list-row"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold">
                      {job.selection
                        ? `${job.selection.state_name ?? job.selection.state_fips} · ${
                            job.selection.county_name ?? job.selection.county_fips
                          }`
                        : job.jobId}
                    </span>
                    <span className="tag">
                      {job.status}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-muted">
                    {job.message ?? 'No message'}
                  </div>
                  <div className="mt-1 text-xs text-muted">
                    {formatTime(job.createdAt)}
                    {(job.status === 'done' || job.status === 'error') && (
                      <span>{` · ${formatElapsed(job.updatedAt - job.createdAt)}`}</span>
                    )}
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
