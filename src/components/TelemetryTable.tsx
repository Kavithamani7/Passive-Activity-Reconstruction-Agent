import React, { useState } from 'react';
import { Search } from 'lucide-react';
import { TelemetryEvent } from '../types/chronotrace';

interface TelemetryTableProps {
  events: TelemetryEvent[];
}

export const TelemetryTable: React.FC<TelemetryTableProps> = ({ events }) => {
  const [filter, setFilter] = useState<'all' | 'main' | 'micro'>('all');
  const [search, setSearch] = useState('');

  const filteredEvents = events.filter((ev) => {
    const isMain = ev.dwell_ms >= 10000;
    if (filter === 'main' && !isMain) return false;
    if (filter === 'micro' && isMain) return false;
    if (search) {
      const q = search.toLowerCase();
      return (
        ev.app_name.toLowerCase().includes(q) ||
        ev.window_title.toLowerCase().includes(q) ||
        ev.category.toLowerCase().includes(q)
      );
    }
    return true;
  });

  const getCategoryClass = (cat: string) => {
    switch (cat.toLowerCase()) {
      case 'deep work':
        return 'text-emerald-700 font-medium';
      case 'learning':
        return 'text-blue-700 font-medium';
      case 'entertainment':
      case 'entertain':
        return 'text-amber-700 font-medium';
      case 'utility':
        return 'text-slate-500 font-medium';
      case 'communication':
        return 'text-cyan-700 font-medium';
      default:
        return 'text-slate-700 font-medium';
    }
  };

  return (
    <div className="rounded-xl bg-white border border-slate-200 shadow-xs p-6 space-y-5">
      {/* Top Header & Interactive Filter Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-slate-900">
            Raw Laptop Telemetry Log
          </h2>
          <div className="flex items-center gap-2 text-xs text-slate-500 mt-0.5">
            <span>Captured from Windows pywin32 API</span>
            <span aria-hidden="true">·</span>
            <span>{events.length} window transitions</span>
          </div>
        </div>

        {/* Filter Tabs & Search */}
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Filter windows..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg text-slate-900 placeholder-slate-400 focus:outline-none focus:border-slate-400 focus:bg-white w-40 sm:w-52 transition-all shadow-2xs"
            />
          </div>

          <div className="flex items-center gap-1 p-1 bg-slate-100 rounded-lg border border-slate-200/60">
            <button
              onClick={() => setFilter('all')}
              className={`px-3 py-1 text-xs font-medium rounded-md transition-all whitespace-nowrap ${
                filter === 'all'
                  ? 'bg-white text-slate-900 shadow-xs font-semibold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              All ({events.length})
            </button>
            <button
              onClick={() => setFilter('main')}
              className={`px-3 py-1 text-xs font-medium rounded-md transition-all whitespace-nowrap ${
                filter === 'main'
                  ? 'bg-white text-slate-900 shadow-xs font-semibold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              MAIN (&gt;=10s)
            </button>
            <button
              onClick={() => setFilter('micro')}
              className={`px-3 py-1 text-xs font-medium rounded-md transition-all whitespace-nowrap ${
                filter === 'micro'
                  ? 'bg-white text-slate-900 shadow-xs font-semibold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              MICRO (&lt;10s)
            </button>
          </div>
        </div>
      </div>

      {/* Table of Events */}
      <div className="overflow-x-auto rounded-lg border border-slate-200">
        <table className="w-full text-left text-xs text-slate-700">
          <thead className="bg-slate-50 text-slate-500 text-[11px] font-mono border-b border-slate-200">
            <tr>
              <th className="py-2.5 px-3.5 font-semibold">TIMESTAMP</th>
              <th className="py-2.5 px-3.5 font-semibold">STREAM</th>
              <th className="py-2.5 px-3.5 font-semibold">APPLICATION</th>
              <th className="py-2.5 px-3.5 font-semibold">WINDOW TITLE</th>
              <th className="py-2.5 px-3.5 font-semibold">CATEGORY</th>
              <th className="py-2.5 px-3.5 font-semibold text-right">DWELL TIME</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 font-mono">
            {filteredEvents.map((ev, idx) => {
              const isMain = ev.dwell_ms >= 10000;
              const dwellSeconds = (ev.dwell_ms / 1000).toFixed(0);

              return (
                <tr
                  key={idx}
                  className="hover:bg-slate-50/70 transition-colors"
                >
                  <td className="py-2.5 px-3.5 text-slate-500 tabular-nums">
                    {ev.timestamp}
                  </td>
                  <td className="py-2.5 px-3.5">
                    {isMain ? (
                      <span className="text-[11px] font-semibold text-emerald-800 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-md">
                        MAIN
                      </span>
                    ) : (
                      <span className="text-[11px] font-semibold text-purple-800 bg-purple-50 border border-purple-200 px-2 py-0.5 rounded-md">
                        MICRO
                      </span>
                    )}
                  </td>
                  <td className="py-2.5 px-3.5 font-sans text-slate-900 font-semibold">
                    {ev.app_name}
                  </td>
                  <td className="py-2.5 px-3.5 font-sans text-slate-700 truncate max-w-xs font-normal">
                    {ev.window_title}
                  </td>
                  <td className={`py-2.5 px-3.5 font-sans ${getCategoryClass(ev.category)}`}>
                    {ev.category}
                  </td>
                  <td className="py-2.5 px-3.5 text-right tabular-nums text-slate-900 font-medium">
                    {dwellSeconds}s ({ev.dwell_ms}ms)
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between text-xs text-slate-500 pt-1">
        <span>Showing {filteredEvents.length} transitions</span>
        <span>Splitter rule: dwell &gt;= 10,000ms routes to MAIN focus stream</span>
      </div>
    </div>
  );
};
