import React, { useState } from 'react';
import { Compass, CheckSquare, ArrowUpRight, Copy, Check } from 'lucide-react';
import { ReentryBriefing } from '../types/chronotrace';

interface ReentryCardProps {
  briefing: ReentryBriefing | null;
  onSelectProject: (proj: string) => void;
  currentProject: string;
}

export const ReentryCard: React.FC<ReentryCardProps> = ({
  briefing,
  onSelectProject,
  currentProject,
}) => {
  const [copied, setCopied] = useState(false);
  const projects = [
    'api-server',
    'TS Assignment',
    'Full_Stack_Dev_Learning_Monster2.0',
    'hooks-demo',
  ];

  const handleCopy = () => {
    if (!briefing) return;
    const text = `Context Briefing for ${briefing.project}:\n${briefing.headline}\nLast summary: ${briefing.summary}\nUnresolved threads:\n- ${briefing.unresolved_threads.join('\n- ')}`;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-xl bg-white border border-slate-200 shadow-xs p-6 space-y-6">
      {/* Header and Project Switcher */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-100">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-700 shrink-0">
            <Compass className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-slate-900">
              Laptop Wake Re-entry Briefing
            </h2>
            <div className="flex items-center gap-2 text-xs text-slate-500 mt-0.5">
              <span>Automatic context reconstruction</span>
              <span aria-hidden="true">·</span>
              <span>Windows sleep & wake trigger</span>
            </div>
          </div>
        </div>

        {/* Project Selector Segmented Control */}
        <div className="flex items-center gap-1 p-1 bg-slate-100 rounded-lg border border-slate-200/60">
          {projects.map((p) => (
            <button
              key={p}
              onClick={() => onSelectProject(p)}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all whitespace-nowrap ${
                currentProject === p
                  ? 'bg-white text-slate-900 shadow-xs font-semibold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Briefing Narrative */}
      {briefing ? (
        <div className="space-y-5">
          <div className="p-4 rounded-lg bg-slate-50 border border-slate-200/80">
            <div className="text-sm font-semibold text-slate-900 leading-relaxed">
              "{briefing.headline}"
            </div>
            {briefing.summary && (
              <p className="mt-2 text-xs text-slate-600 leading-normal">
                {briefing.summary}
              </p>
            )}
          </div>

          {/* Unresolved Threads List */}
          <div className="space-y-2.5">
            <div className="flex items-center justify-between text-xs text-slate-500">
              <span className="font-semibold text-slate-800">
                Unresolved Loops & Open Files ({briefing.unresolved_threads.length})
              </span>
              <span>Extracted from recent window titles</span>
            </div>

            <div className="space-y-2">
              {briefing.unresolved_threads.map((thread, idx) => (
                <div
                  key={idx}
                  className="flex items-start gap-3 p-3 rounded-lg bg-white border border-slate-200 text-xs text-slate-800 shadow-2xs hover:border-slate-300 transition-colors"
                >
                  <CheckSquare className="w-4 h-4 mt-0.5 text-emerald-600 shrink-0" />
                  <span className="leading-relaxed font-medium">{thread}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Action Row */}
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium text-slate-700 bg-white hover:bg-slate-50 border border-slate-200 rounded-lg transition-colors shadow-2xs"
            >
              {copied ? (
                <>
                  <Check className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Briefing Copied</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5 text-slate-500" />
                  <span>Copy Context</span>
                </>
              )}
            </button>

            <button
              onClick={() => {
                alert(`In a native Windows installation, ChronoTrace launches: code --goto "${briefing.project}"`);
              }}
              className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-slate-900 hover:bg-slate-800 rounded-lg transition-colors shadow-xs"
            >
              <span>Resume Workspace</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      ) : (
        <div className="py-8 text-center text-xs text-slate-500">
          No historical session found for this project.
        </div>
      )}
    </div>
  );
};
