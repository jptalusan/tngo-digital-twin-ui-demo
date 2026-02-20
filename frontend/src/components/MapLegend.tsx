import { Eye, EyeOff } from 'lucide-react';

export interface LegendItem {
  id: string;
  label: string;
  color: string;
  visible: boolean;
}

interface MapLegendProps {
  items: LegendItem[];
  onToggle: (id: string) => void;
}

export function MapLegend({ items, onToggle }: MapLegendProps) {
  if (items.length === 0) return null;

  return (
    <div className="absolute top-4 right-4 floating-card max-w-xs z-[1100]">
      <h4 className="text-sm font-semibold mb-3">Map Layers</h4>
      <div className="space-y-2">
        {items.map((item) => (
          <button
            key={item.id}
            onClick={() => onToggle(item.id)}
            className="btn btn-ghost w-full justify-between"
          >
            <div className="flex items-center gap-2">
              <div
                className="w-4 h-4 rounded"
                style={{ backgroundColor: item.color }}
              />
              <span className="text-sm">{item.label}</span>
            </div>
            {item.visible ? (
              <Eye size={16} style={{ color: 'var(--app-accent)' }} />
            ) : (
              <EyeOff size={16} style={{ color: 'var(--app-text-muted)' }} />
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
