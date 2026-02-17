import { useState } from 'react';
import { X, ChevronUp, ChevronDown } from 'lucide-react';
import { EvaluationMetrics } from '../services/api';
import { BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

interface EvaluationDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  metrics: EvaluationMetrics | null;
}

export function EvaluationDrawer({ isOpen, onClose, metrics }: EvaluationDrawerProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);

  if (!isOpen || !metrics) return null;

  // Mock chart data
  const coverageData = [
    { name: 'Zone A', coverage: 85 },
    { name: 'Zone B', coverage: 75 },
    { name: 'Zone C', coverage: 90 },
    { name: 'Zone D', coverage: 65 },
  ];

  const ridershipData = [
    { time: '6 AM', riders: 450 },
    { time: '9 AM', riders: 1200 },
    { time: '12 PM', riders: 800 },
    { time: '3 PM', riders: 950 },
    { time: '6 PM', riders: 1400 },
    { time: '9 PM', riders: 600 },
  ];

  const costData = [
    { category: 'Operations', value: 60 },
    { category: 'Maintenance', value: 25 },
    { category: 'Personnel', value: 15 },
  ];

  const COLORS = ['#3b82f6', '#10b981', '#f59e0b'];

  return (
    <div 
      className={`absolute bottom-0 left-0 right-0 bg-white border-t shadow-lg z-[1050] transition-all duration-300 ease-in-out ${isCollapsed ? 'h-16' : 'h-1/2'}`}
    >
      <div className="h-full flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b bg-gray-50 cursor-pointer" onClick={() => setIsCollapsed(!isCollapsed)}>
          <div className="flex items-center gap-2">
            <h3 className="text-lg font-medium">Evaluation Results</h3>
            {isCollapsed && (
              <div className="flex gap-4 text-sm text-gray-500 ml-4">
                <span>Coverage: {metrics.totalCoverage}</span>
                <span>Cost: {metrics.estimatedCost}</span>
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={(e) => {
                e.stopPropagation();
                setIsCollapsed(!isCollapsed);
              }}
              className="p-1 text-gray-500 hover:text-gray-700 hover:bg-gray-200 rounded"
            >
              {isCollapsed ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
            </button>
            <div className="w-px h-4 bg-gray-300 mx-1" />
            <button
              onClick={(e) => {
                e.stopPropagation();
                onClose();
              }}
              className="p-1 text-gray-500 hover:text-gray-700 hover:bg-gray-200 rounded"
            >
              <X size={20} />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className={`flex-1 overflow-y-auto px-6 py-4 ${isCollapsed ? 'hidden' : 'block'}`}>
          <div className="grid grid-cols-3 gap-6">
            {/* Metrics Overview */}
            <div>
              <h4 className="font-medium mb-4">Key Metrics</h4>
              <div className="space-y-3">
                <div className="p-3 bg-blue-50 rounded-lg">
                  <div className="text-sm text-gray-600">Total Coverage</div>
                  <div className="text-xl">{metrics.totalCoverage}</div>
                </div>
                <div className="p-3 bg-green-50 rounded-lg">
                  <div className="text-sm text-gray-600">Estimated Cost</div>
                  <div className="text-xl">{metrics.estimatedCost}</div>
                </div>
                <div className="p-3 bg-purple-50 rounded-lg">
                  <div className="text-sm text-gray-600">Ridership</div>
                  <div className="text-xl">{metrics.ridership}</div>
                </div>
                <div className="p-3 bg-orange-50 rounded-lg">
                  <div className="text-sm text-gray-600">Avg Wait Time</div>
                  <div className="text-xl">{metrics.averageWaitTime}</div>
                </div>
                <div className="p-3 bg-pink-50 rounded-lg">
                  <div className="text-sm text-gray-600">Service Hours</div>
                  <div className="text-xl">{metrics.serviceHours}</div>
                </div>
              </div>
            </div>

            {/* Coverage by Zone */}
            <div>
              <h4 className="font-medium mb-4">Coverage by Zone</h4>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={coverageData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="coverage" fill="#3b82f6" />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Ridership Pattern */}
            <div>
              <h4 className="font-medium mb-4">Ridership Pattern</h4>
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={ridershipData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="time" />
                  <YAxis />
                  <Tooltip />
                  <Line type="monotone" dataKey="riders" stroke="#10b981" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Cost Breakdown */}
          <div className="mt-6">
            <h4 className="font-medium mb-4">Cost Breakdown</h4>
            <div className="flex items-center gap-8">
              <ResponsiveContainer width={200} height={200}>
                <PieChart>
                  <Pie
                    data={costData}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={(entry) => `${entry.category}: ${entry.value}%`}
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {costData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex-1">
                <p className="text-sm text-gray-600">
                  The evaluation shows strong coverage in most zones with peak ridership during morning and evening commute hours. 
                  Cost distribution is weighted toward operations with opportunities for efficiency improvements.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}