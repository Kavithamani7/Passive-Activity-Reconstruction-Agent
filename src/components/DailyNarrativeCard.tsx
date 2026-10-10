import React from 'react';
import { DailySynthesis } from '../types/chronotrace';
import { Sparkles, AlertCircle, CheckCircle2 } from 'lucide-react';

interface DailyNarrativeCardProps {
  synthesis: DailySynthesis | null;
  onSynthesize?: () => void;
  isSynthesizing?: boolean;
}

export const DailyNarrativeCard: React.FC<DailyNarrativeCardProps> = ({
  synthesis,
  onSynthesize,
  isSynthesizing,
}) => {
  if (!synthesis) {
    return (
      <div className="rounded-xl bg-white border border-slate-200 p-8 text-center text-xs text-slate-500 shadow-xs">
        No daily synthesis available yet. Click "Re-Run Synthesis" to analyze today's sessions.
      </div>
    );
  }

  const deepWorkMinutes = Math.floor(synthesis.total_deep_work_s / 60);
  const deepWorkSeconds = synthesis.total_deep_work_s % 60;
  const distractionMinutes = Math.floor(synthesis.total_distraction_s / 60);
  const distractionSeconds = synthesis.total_distraction_s % 60;

  return (
    <div className="rounded-xl bg-white border border-slate-200 shadow-xs p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-100">
        <div>
          <h2 className="text-base font-semibold text-slate-900">
            End-of-Day Multi-Chunk Focus Synthesis
          </h2>
          <div className="flex items-center gap-2 text-xs text-slate-500 mt-0.5">
            <span>Date: {synthesis.date}</span>
            <span aria-hidden="true">·</span>
            <span>Gemini 1.5 Flash macro synthesis</span>
          </div>
        </div>

        {onSynthesize && (
          <button
            onClick={onSynthesize}
            disabled={isSynthesizing}
            className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold text-white bg-slate-900 hover:bg-slate-800 rounded-lg transition-colors disabled:opacity-50 shadow-xs"
          >
            <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
            <span>{isSynthesizing ? 'Synthesizing...' : 'Re-Run Synthesis'}</span>
          </button>
        )}
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="p-4 rounded-lg bg-slate-50 border border-slate-200/80 space-y-1">
          <div className="text-xs text-slate-500 font-medium">Sustained Deep Work</div>
          <div className="text-xl font-mono font-bold tabular-nums text-emerald-700">
            {deepWorkMinutes}m {deepWorkSeconds}s
          </div>
          <div className="text-[11px] text-slate-400">In anchor apps & coding</div>
        </div>

        <div className="p-4 rounded-lg bg-slate-50 border border-slate-200/80 space-y-1">
          <div className="text-xs text-slate-500 font-medium">Distraction Dwell</div>
          <div className="text-xl font-mono font-bold tabular-nums text-amber-700">
            {distractionMinutes}m {distractionSeconds}s
          </div>
          <div className="text-[11px] text-slate-400">Video & non-work browsing</div>
        </div>

        <div className="p-4 rounded-lg bg-slate-50 border border-slate-200/80 space-y-1">
          <div className="text-xs text-slate-500 font-medium">Fragmentation Score</div>
          <div className="text-xl font-mono font-bold tabular-nums text-slate-900 flex items-center gap-1.5">
            <span>{synthesis.fragmentation_score}</span>
            <span className="text-xs text-slate-400 font-normal">/ 10</span>
          </div>
          <div className="text-[11px] text-slate-400">0=flow, 10=extreme jitter</div>
        </div>

        <div className="p-4 rounded-lg bg-slate-50 border border-slate-200/80 space-y-1">
          <div className="text-xs text-slate-500 font-medium">Peak Focus Window</div>
          <div className="text-lg font-mono font-bold text-slate-900">
            {synthesis.peak_focus_window}
          </div>
          <div className="text-[11px] text-slate-400">{synthesis.context_switches} context switches</div>
        </div>
      </div>

      {/* Daily Narrative Prose */}
      <div className="p-4 rounded-lg bg-slate-50 border border-slate-200/80 space-y-2">
        <div className="text-xs font-semibold text-slate-800">
          Executive Daily Narrative
        </div>
        <p className="text-xs text-slate-700 leading-relaxed font-normal">
          {synthesis.daily_narrative}
        </p>
      </div>

      {/* Distraction Triggers and Unfinished Work */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Distraction Triggers */}
        <div className="space-y-2">
          <div className="text-xs font-semibold text-slate-800">
            Identified Distraction Triggers
          </div>
          <div className="space-y-1.5">
            {synthesis.distraction_triggers.map((trigger, idx) => (
              <div
                key={idx}
                className="flex items-start gap-2.5 p-3 rounded-lg bg-white border border-slate-200 text-xs text-slate-700 shadow-2xs"
              >
                <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                <span className="font-medium">{trigger}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Unfinished Work */}
        <div className="space-y-2">
          <div className="text-xs font-semibold text-slate-800">
            Unfinished Work & Open Threads
          </div>
          <div className="space-y-1.5">
            {synthesis.unfinished_work.map((task, idx) => (
              <div
                key={idx}
                className="flex items-start gap-2.5 p-3 rounded-lg bg-white border border-slate-200 text-xs text-slate-700 shadow-2xs"
              >
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <span className="font-medium">{task}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
