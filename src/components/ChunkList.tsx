import React, { useState } from 'react';
import {
  ChevronDown,
  ChevronUp,
  Tag,
  CheckCircle2,
  Clock,
  Layers,
  Sparkles,
} from 'lucide-react';
import { ChunkSummary, IntentLabel } from '../types/chronotrace';

interface ChunkListProps {
  chunks: ChunkSummary[];
  onCorrectIntent: (chunkId: string, newIntent: IntentLabel) => void;
}

export const ChunkList: React.FC<ChunkListProps> = ({
  chunks,
  onCorrectIntent,
}) => {
  const [expandedId, setExpandedId] = useState<string | null>(chunks[0]?.chunk_id || null);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const pageSize = 15;

  const totalPages = Math.ceil(chunks.length / pageSize) || 1;
  const paginatedChunks = chunks.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  const intentOptions: IntentLabel[] = [
    'DEEP_WORK',
    'LEARNING',
    'DISTRACTION',
    'DISTRACTION_BREAK',
    'COMMUNICATION',
    'AMBIENT',
    'ADMIN',
    'RESTLESS_START',
  ];

  const getIntentStyle = (intent?: IntentLabel) => {
    switch (intent) {
      case 'DEEP_WORK':
        return 'text-emerald-800 bg-emerald-50 border-emerald-200';
      case 'LEARNING':
        return 'text-blue-800 bg-blue-50 border-blue-200';
      case 'DISTRACTION':
      case 'DISTRACTION_BREAK':
        return 'text-amber-800 bg-amber-50 border-amber-200';
      case 'RESTLESS_START':
        return 'text-purple-800 bg-purple-50 border-purple-200';
      case 'COMMUNICATION':
        return 'text-cyan-800 bg-cyan-50 border-cyan-200';
      default:
        return 'text-slate-700 bg-slate-100 border-slate-200';
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-slate-900">
            Reconstructed Activity Chunks ({chunks.length})
          </h2>
          <div className="flex items-center gap-2 text-xs text-slate-500 mt-0.5">
            <span>Aggregated cognitive work blocks</span>
            <span aria-hidden="true">·</span>
            <span>Gemini 1.5 Flash cognitive classification</span>
          </div>
        </div>
      </div>

      {/* Chunks List */}
      <div className="space-y-3">
        {paginatedChunks.map((chunk, idx) => {
          const overallIdx = (currentPage - 1) * pageSize + idx;
          const isExpanded = expandedId === chunk.chunk_id;
          const letter = overallIdx < 26 ? String.fromCharCode(65 + overallIdx) : `${overallIdx + 1}`;

          return (
            <div
              key={chunk.chunk_id}
              className="rounded-xl bg-white border border-slate-200 shadow-xs overflow-hidden transition-all hover:border-slate-300"
            >
              {/* Header Row */}
              <div
                onClick={() => setExpandedId(isExpanded ? null : chunk.chunk_id)}
                className="flex items-center justify-between p-5 cursor-pointer hover:bg-slate-50/60 transition-colors"
              >
                <div className="flex items-center gap-4 min-w-0">
                  <span className="w-8 h-8 rounded-lg bg-slate-100 border border-slate-200 flex items-center justify-center text-xs font-mono font-bold text-slate-800 shrink-0">
                    {letter}
                  </span>

                  <div className="min-w-0">
                    <div className="flex items-center gap-2.5 flex-wrap">
                      <span className="text-sm font-semibold text-slate-900 truncate">
                        {chunk.primary_task || `Activity Chunk ${letter}`}
                      </span>

                      {/* Intent label */}
                      <span
                        className={`text-xs font-mono px-2.5 py-0.5 rounded-md border font-medium ${getIntentStyle(
                          chunk.intent
                        )}`}
                      >
                        {chunk.intent || 'UNCLASSIFIED'}
                      </span>

                      {chunk.user_corrected && (
                        <span className="text-[11px] text-slate-400 font-medium">
                          (user corrected)
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-2 text-xs text-slate-500 mt-1 flex-wrap">
                      <span className="font-mono tabular-nums font-medium text-slate-700">
                        {chunk.start_time} – {chunk.end_time}
                      </span>
                      <span aria-hidden="true">·</span>
                      <span className="font-mono tabular-nums font-medium text-slate-700">
                        {chunk.duration_s}s duration
                      </span>
                      <span aria-hidden="true">·</span>
                      <span>Boundary: {chunk.closed_by}</span>
                      {chunk.anchor_app && (
                        <>
                          <span aria-hidden="true">·</span>
                          <span className="text-slate-700 font-medium">
                            Anchor: {chunk.anchor_app}
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-4 shrink-0">
                  {/* Micro Pattern indicator */}
                  <div className="hidden sm:flex flex-col items-end text-xs">
                    <span className="text-slate-400 text-[11px]">Micro Pattern:</span>
                    <span
                      className={`font-mono text-xs font-semibold ${
                        chunk.micro_behavior.dominant_pattern === 'RESTLESS'
                          ? 'text-purple-700'
                          : chunk.micro_behavior.dominant_pattern === 'TAB_HUNTING'
                          ? 'text-amber-700'
                          : 'text-slate-700'
                      }`}
                    >
                      {chunk.micro_behavior.dominant_pattern}
                    </span>
                  </div>

                  {isExpanded ? (
                    <ChevronUp className="w-5 h-5 text-slate-400" />
                  ) : (
                    <ChevronDown className="w-5 h-5 text-slate-400" />
                  )}
                </div>
              </div>

              {/* Expanded Detail Body */}
              {isExpanded && (
                <div className="px-5 pb-5 pt-2 border-t border-slate-100 space-y-4 bg-slate-50/40">
                  {/* Narrative Summary */}
                  {chunk.summary && (
                    <div className="p-3.5 rounded-lg bg-white border border-slate-200 text-xs text-slate-700 leading-relaxed shadow-2xs">
                      <span className="font-semibold text-slate-900">Summary: </span>
                      {chunk.summary}
                    </div>
                  )}

                  {/* Micro Behaviors & Key Metrics */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs">
                    <div className="p-3 rounded-lg bg-white border border-slate-200 shadow-2xs">
                      <div className="text-slate-500 text-[11px]">Rapid Switches</div>
                      <div className="font-mono tabular-nums font-bold text-slate-900 mt-1 text-sm">
                        {chunk.micro_behavior.total_rapid_switches}
                      </div>
                    </div>
                    <div className="p-3 rounded-lg bg-white border border-slate-200 shadow-2xs">
                      <div className="text-slate-500 text-[11px]">Tab Flickers</div>
                      <div className="font-mono tabular-nums font-bold text-slate-900 mt-1 text-sm">
                        {chunk.micro_behavior.tab_flickers}
                      </div>
                    </div>
                    <div className="p-3 rounded-lg bg-white border border-slate-200 shadow-2xs">
                      <div className="text-slate-500 text-[11px]">Avg Micro Dwell</div>
                      <div className="font-mono tabular-nums font-bold text-slate-900 mt-1 text-sm">
                        {chunk.micro_behavior.avg_micro_dwell_ms} ms
                      </div>
                    </div>
                    <div className="p-3 rounded-lg bg-white border border-slate-200 shadow-2xs">
                      <div className="text-slate-500 text-[11px]">Returned to Anchor</div>
                      <div className="font-semibold text-slate-900 mt-1 text-sm">
                        {chunk.returned_to_anchor ? 'YES (Tool lookup)' : 'NO'}
                      </div>
                    </div>
                  </div>

                  {/* Sustained Focus Timeline */}
                  <div>
                    <div className="text-xs font-semibold text-slate-800 mb-2">
                      Sustained Focus Timeline (&gt;=10s events)
                    </div>
                    <div className="space-y-1.5">
                      {chunk.main_events.map((ev, eIdx) => (
                        <div
                          key={eIdx}
                          className="flex items-center justify-between px-3.5 py-2.5 rounded-lg bg-white border border-slate-200 text-xs shadow-2xs"
                        >
                          <div className="flex items-center gap-2 truncate">
                            <span className="font-mono font-bold text-emerald-700 shrink-0">
                              [{ev.app}]
                            </span>
                            <span className="text-slate-800 truncate font-medium">
                              "{ev.title}"
                            </span>
                          </div>
                          <div className="flex items-center gap-3 shrink-0 font-mono tabular-nums text-slate-500">
                            <span>{ev.dwell_s}s dwell</span>
                            <span>{ev.keys} keys</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Unresolved Threads */}
                  {chunk.unresolved_threads && chunk.unresolved_threads.length > 0 && (
                    <div>
                      <div className="text-xs font-semibold text-slate-800 mb-1.5">
                        Detected Open Loops / Unresolved Context
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {chunk.unresolved_threads.map((thread, tIdx) => (
                          <div
                            key={tIdx}
                            className="px-3 py-1 rounded-md bg-white border border-slate-200 text-xs text-slate-700 shadow-2xs font-medium"
                          >
                            {thread}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Manual Intent Correction Row */}
                  <div className="pt-3 border-t border-slate-200/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                    <span className="text-slate-600 font-medium">
                      Disagree with Gemini classification? Override intent:
                    </span>
                    <div className="flex flex-wrap items-center gap-1.5">
                      {intentOptions.map((opt) => (
                        <button
                          key={opt}
                          onClick={() => onCorrectIntent(chunk.chunk_id, opt)}
                          className={`px-2.5 py-1 text-xs font-mono rounded-md border transition-all ${
                            chunk.intent === opt
                              ? 'bg-slate-900 text-white font-semibold border-slate-900 shadow-xs'
                              : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-100 hover:text-slate-900'
                          }`}
                        >
                          {opt}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Pagination Controls */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-3 text-xs text-slate-600">
          <div>
            Showing {(currentPage - 1) * pageSize + 1}–{Math.min(currentPage * pageSize, chunks.length)} of {chunks.length} chunks
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="px-3 py-1.5 rounded-md border border-slate-200 bg-white hover:bg-slate-50 disabled:opacity-40 disabled:hover:bg-white font-medium shadow-2xs transition-colors"
            >
              Previous
            </button>
            <span className="font-mono text-slate-700 font-semibold px-1">
              Page {currentPage} of {totalPages}
            </span>
            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="px-3 py-1.5 rounded-md border border-slate-200 bg-white hover:bg-slate-50 disabled:opacity-40 disabled:hover:bg-white font-medium shadow-2xs transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
