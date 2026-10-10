import React from 'react';
import { Activity, Play, RefreshCw } from 'lucide-react';

interface TopBarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  onReplay: () => void;
  isReplaying: boolean;
}

export const TopBar: React.FC<TopBarProps> = ({
  activeTab,
  setActiveTab,
  onReplay,
  isReplaying,
}) => {
  const navItems = [
    { id: 'chunks', label: 'Work Chunks' },
    { id: 'reentry', label: 'Re-entry Briefing' },
    { id: 'telemetry', label: 'Telemetry Stream' },
    { id: 'synthesis', label: 'Daily Synthesis' },
    { id: 'pipeline', label: '5-Layer Pipeline' },
    { id: 'python', label: 'Windows Agent' },
    { id: 'dashboard', label: 'HTML Dashboard' },
  ];

  return (
    <header className="sticky top-0 z-40 flex items-center justify-between gap-8 px-6 py-3.5 bg-white/95 backdrop-blur-md border-b border-slate-200 shadow-xs">
      {/* Zone 1: Brand Wordmark (Clean light mode, no pill tags) */}
      <div className="flex items-center gap-3 shrink-0">
        <div className="w-8 h-8 rounded-lg bg-slate-900 flex items-center justify-center text-white shadow-xs">
          <Activity className="w-4 h-4 text-emerald-400" />
        </div>
        <a
          href="/"
          onClick={(e) => {
            e.preventDefault();
            setActiveTab('chunks');
          }}
          className="text-base font-semibold tracking-tight text-slate-900 whitespace-nowrap"
        >
          ChronoTrace
        </a>
      </div>

      {/* Zone 2: Navigation Links with subtle hover and active indicator */}
      <nav className="hidden md:flex items-center gap-6 text-xs font-medium text-slate-600">
        {navItems.map((item) => {
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`transition-colors whitespace-nowrap shrink-0 py-1 border-b-2 ${
                isActive
                  ? 'text-slate-900 border-slate-900 font-semibold'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              {item.label}
            </button>
          );
        })}
      </nav>

      {/* Zone 3: Primary Action */}
      <div className="flex items-center gap-3 shrink-0">
        <button
          onClick={onReplay}
          disabled={isReplaying}
          className="flex items-center gap-2 px-3.5 py-1.5 text-xs font-medium text-white bg-slate-900 rounded-md hover:bg-slate-800 transition-colors whitespace-nowrap shrink-0 disabled:opacity-50 shadow-xs"
        >
          {isReplaying ? (
            <>
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              <span>Simulating...</span>
            </>
          ) : (
            <>
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>Replay Telemetry</span>
            </>
          )}
        </button>
      </div>
    </header>
  );
};
