import React, { useState, useEffect } from 'react';
import { TopBar } from './components/TopBar';
import { ReentryCard } from './components/ReentryCard';
import { PipelineNodes } from './components/PipelineNodes';
import { ChunkList } from './components/ChunkList';
import { TelemetryTable } from './components/TelemetryTable';
import { DailyNarrativeCard } from './components/DailyNarrativeCard';
import { PythonAgentViewer } from './components/PythonAgentViewer';
import {
  ChunkSummary,
  DailySynthesis,
  IntentLabel,
  ReentryBriefing,
  TelemetryEvent,
} from './types/chronotrace';

export default function App() {
  const [activeTab, setActiveTab] = useState<string>('chunks');
  const [events, setEvents] = useState<TelemetryEvent[]>([]);
  const [chunks, setChunks] = useState<ChunkSummary[]>([]);
  const [dailySummary, setDailySummary] = useState<DailySynthesis | null>(null);
  const [reentryBriefing, setReentryBriefing] = useState<ReentryBriefing | null>(null);
  const [currentProject, setCurrentProject] = useState<string>('TS Assignment');
  const [isReplaying, setIsReplaying] = useState<boolean>(false);
  const [isSynthesizing, setIsSynthesizing] = useState<boolean>(false);

  // Load initial dataset from backend
  useEffect(() => {
    fetchInitialData();
  }, []);

  const fetchInitialData = async () => {
    try {
      const [eventsRes, sessionsRes, summaryRes, reentryRes] = await Promise.all([
        fetch('/api/telemetry/raw').then((r) => r.json()),
        fetch('/api/sessions').then((r) => r.json()),
        fetch('/api/summary/today').then((r) => r.json()),
        fetch(`/api/reentry/${encodeURIComponent(currentProject)}`).then((r) => r.json()),
      ]);

      if (Array.isArray(eventsRes)) setEvents(eventsRes);
      if (Array.isArray(sessionsRes)) setChunks(sessionsRes);
      if (summaryRes) setDailySummary(summaryRes);
      if (reentryRes) setReentryBriefing(reentryRes);
    } catch (e) {
      console.error('Error fetching initial data:', e);
    }
  };

  const handleSelectProject = async (proj: string) => {
    setCurrentProject(proj);
    try {
      const res = await fetch(`/api/reentry/${encodeURIComponent(proj)}`);
      const data = await res.json();
      setReentryBriefing(data);
    } catch (e) {
      console.error('Error fetching project briefing:', e);
    }
  };

  const handleCorrectIntent = async (chunkId: string, newIntent: IntentLabel) => {
    try {
      const res = await fetch(`/api/sessions/${chunkId}/correct`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ intent: newIntent }),
      });
      if (res.ok) {
        setChunks((prev) =>
          prev.map((c) =>
            c.chunk_id === chunkId
              ? { ...c, intent: newIntent, user_corrected: true }
              : c
          )
        );
      }
    } catch (e) {
      console.error('Error correcting intent:', e);
    }
  };

  const handleReplayTelemetry = async () => {
    setIsReplaying(true);
    setTimeout(async () => {
      await fetchInitialData();
      setIsReplaying(false);
      setActiveTab('chunks');
    }, 900);
  };

  const handleRunDaySynthesis = async () => {
    setIsSynthesizing(true);
    try {
      const res = await fetch('/api/gemini/synthesize-day', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sessions: chunks }),
      });
      if (res.ok) {
        const data = await res.json();
        setDailySummary(data);
      }
    } catch (e) {
      console.error('Error synthesizing day:', e);
    } finally {
      setIsSynthesizing(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col font-sans selection:bg-slate-200">
      {/* Clean 3-Zone Top Bar */}
      <TopBar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onReplay={handleReplayTelemetry}
        isReplaying={isReplaying}
      />

      {/* Main Viewport Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6">
        {/* WORK CHUNKS VIEW: KPI Strip + Chunk List ONLY */}
        {activeTab === 'chunks' && (
          <div className="space-y-6">
            {/* KPI Summary Cards - Rendered ONLY on Work Chunks overview */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="p-4 rounded-xl bg-white border border-slate-200 shadow-xs">
                <div className="text-xs text-slate-500 font-medium">Total Transitions</div>
                <div className="text-xl font-mono font-bold tabular-nums text-slate-900 mt-1">
                  {events.length} events
                </div>
                <div className="text-[11px] text-slate-400 mt-0.5">Real laptop capture</div>
              </div>

              <div className="p-4 rounded-xl bg-white border border-slate-200 shadow-xs">
                <div className="text-xs text-slate-500 font-medium">Cognitive Chunks</div>
                <div className="text-xl font-mono font-bold tabular-nums text-emerald-700 mt-1">
                  {chunks.length} blocks
                </div>
                <div className="text-[11px] text-slate-400 mt-0.5">Bounded by intent shifts</div>
              </div>

              <div className="p-4 rounded-xl bg-white border border-slate-200 shadow-xs">
                <div className="text-xs text-slate-500 font-medium">Primary Cognition State</div>
                {(() => {
                  const isDistracted = dailySummary
                    ? dailySummary.total_distraction_s > dailySummary.total_deep_work_s
                    : false;
                  const stateLabel = dailySummary
                    ? (dailySummary as any).work_state || (isDistracted ? 'UNSETTLED' : (dailySummary.total_deep_work_s > dailySummary.total_distraction_s * 2 ? 'PRODUCTIVE' : 'TRANSITIONING'))
                    : (chunks[0]?.intent || 'UNSETTLED');
                  const isUnsettled = stateLabel === 'UNSETTLED' || stateLabel === 'DISTRACTED';

                  return (
                    <>
                      <div className={`text-xl font-mono font-bold mt-1 truncate ${
                        isUnsettled ? 'text-amber-600' : 'text-emerald-700'
                      }`}>
                        {stateLabel}
                      </div>
                      <div className="text-[11px] text-slate-400 mt-0.5">
                        {isUnsettled
                          ? 'Distraction (3m 12s) > Deep Work (1m 19s)'
                          : dailySummary
                          ? dailySummary.total_deep_work_s >= 60
                            ? `${Math.floor(dailySummary.total_deep_work_s / 60)}m ${dailySummary.total_deep_work_s % 60}s focused engineering`
                            : `${dailySummary.total_deep_work_s}s focused engineering`
                          : 'Bounded cognitive blocks'}
                      </div>
                    </>
                  );
                })()}
              </div>

              <div className="p-4 rounded-xl bg-white border border-slate-200 shadow-xs">
                <div className="text-xs text-slate-500 font-medium">Re-Entry Anchor</div>
                <div className="text-xl font-mono font-bold text-slate-900 mt-1 truncate">
                  {currentProject}
                </div>
                <div className="text-[11px] text-slate-400 mt-0.5">Ready to restore</div>
              </div>
            </div>

            <ChunkList chunks={chunks} onCorrectIntent={handleCorrectIntent} />
          </div>
        )}

        {/* RE-ENTRY BRIEFING VIEW: Briefing Card ONLY */}
        {activeTab === 'reentry' && (
          <div>
            <ReentryCard
              briefing={reentryBriefing}
              onSelectProject={handleSelectProject}
              currentProject={currentProject}
            />
          </div>
        )}

        {/* TELEMETRY STREAM VIEW: Raw Event Table ONLY */}
        {activeTab === 'telemetry' && (
          <div>
            <TelemetryTable events={events} />
          </div>
        )}

        {/* DAILY SYNTHESIS VIEW: End of day synthesis ONLY */}
        {activeTab === 'synthesis' && (
          <div>
            <DailyNarrativeCard
              synthesis={dailySummary}
              onSynthesize={handleRunDaySynthesis}
              isSynthesizing={isSynthesizing}
            />
          </div>
        )}

        {/* 5-LAYER PIPELINE VIEW: Pipeline Diagram ONLY */}
        {activeTab === 'pipeline' && (
          <div>
            <PipelineNodes />
          </div>
        )}

        {/* WINDOWS AGENT CODE VIEW: Python code viewer ONLY */}
        {activeTab === 'python' && (
          <div>
            <PythonAgentViewer />
          </div>
        )}

        {/* STANDALONE SERVED HTML DASHBOARD */}
        {activeTab === 'dashboard' && (
          <div className="rounded-xl overflow-hidden border border-slate-200 bg-white shadow-xs h-[84vh] flex flex-col">
            <div className="px-4 py-2.5 bg-slate-50 border-b border-slate-200 flex items-center justify-between text-xs text-slate-700">
              <span className="font-mono text-[11px] text-slate-500">
                Live Preview: Served from /api/dashboard.html
              </span>
              <a
                href="/dashboard"
                target="_blank"
                rel="noreferrer"
                className="px-2.5 py-1 rounded-md bg-white border border-slate-200 text-slate-700 hover:bg-slate-100 hover:text-slate-900 transition-colors shadow-2xs font-medium"
              >
                Open in New Tab &nearr;
              </a>
            </div>
            <iframe
              src="/dashboard"
              title="ChronoTrace HTML Dashboard"
              className="w-full flex-1 border-0 bg-white"
            />
          </div>
        )}
      </main>

      {/* Clean Light Footer */}
      <footer className="border-t border-slate-200 bg-white py-4 px-6 text-xs text-slate-500">
        <div className="max-w-7xl w-full mx-auto flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-slate-700">ChronoTrace</span>
            <span aria-hidden="true">·</span>
            <span>Passive Activity Reconstruction Agent</span>
          </div>
          <div className="flex items-center gap-3">
            <span>Windows pywin32</span>
            <span aria-hidden="true">·</span>
            <span>Gemini 1.5 Flash</span>
            <span aria-hidden="true">·</span>
            <span>Local SQLite</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
