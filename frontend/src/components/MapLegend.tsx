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
    <div className="absolute top-4 right-4 bg-white rounded-lg shadow-lg p-4 max-w-xs z-[1100]">
      <h4 className="text-sm mb-3">Map Layers</h4>
      <div className="space-y-2">
        {items.map((item) => (
          <button
            key={item.id}
            onClick={() => onToggle(item.id)}
            className="w-full flex items-center justify-between gap-3 px-3 py-2 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <div className="flex items-center gap-2">
              <div
                className="w-4 h-4 rounded"
                style={{ backgroundColor: item.color }}
              />
              <span className="text-sm">{item.label}</span>
            </div>
            {item.visible ? (
              <Eye size={16} className="text-blue-600" />
            ) : (
              <EyeOff size={16} className="text-gray-400" />
            )}
          </button>
        ))}
      </div>
    </div>
  );
}