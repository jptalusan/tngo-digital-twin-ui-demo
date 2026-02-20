import { ReactNode } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

interface SidebarShellProps {
  title: string;
  subtitle?: string;
  collapsed?: boolean;
  collapsible?: boolean;
  onToggleCollapse?: () => void;
  headerAction?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  collapsedLabel?: string;
}

export function SidebarShell({
  title,
  subtitle,
  collapsed = false,
  collapsible = false,
  onToggleCollapse,
  headerAction,
  children,
  footer,
  collapsedLabel
}: SidebarShellProps) {
  const showCollapse = collapsible && onToggleCollapse;
  const label = collapsedLabel ?? title;

  return (
    <aside className={`sidebar-shell${collapsed ? ' is-collapsed' : ''}`}>
      <div className="sidebar-header">
        {!collapsed && (
          <div className="sidebar-title">
            <h2>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
        )}
        {collapsed && <div className="sidebar-title" />}
        <div className="flex items-center gap-2">
          {headerAction}
          {showCollapse && (
            <button
              type="button"
              className="btn btn-ghost"
              onClick={onToggleCollapse}
              title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
            </button>
          )}
        </div>
      </div>

      {collapsed ? (
        <div className="sidebar-collapsed-label">{label}</div>
      ) : (
        <div className="sidebar-body">{children}</div>
      )}

      {!collapsed && footer && <div className="sidebar-footer">{footer}</div>}
    </aside>
  );
}
