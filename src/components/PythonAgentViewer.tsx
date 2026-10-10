import React, { useState } from 'react';
import { Copy, Check, FileCode } from 'lucide-react';

export const PythonAgentViewer: React.FC = () => {
  const [selectedFile, setSelectedFile] = useState<string>('main.py');
  const [copied, setCopied] = useState<boolean>(false);

  const fileSummaries: Record<string, { desc: string; snippet: string }> = {
    'main.py': {
      desc: 'Orchestrator wiring DB, LLM, Aggregator, Chunker, Splitter, and WinCollector',
      snippet: `agent = ChronoTraceAgent()
# Wires 7 layers:
# Database -> LLMEngine -> Aggregator -> Chunker -> Splitter -> WinCollector -> IdleDetector
agent.start() # Blocking loop running pywin32 hook on main thread, uvicorn on port 8000`,
    },
    'config.py': {
      desc: 'Global timing thresholds and Anchor applications set',
      snippet: `MICRO_THRESHOLD_MS = 10000  # Dwell < 10s belongs to MICRO stream
IDLE_GAP_S = 120            # Inactivity > 2 minutes splits chunks
MAX_CHUNK_DURATION_S = 1200 # 20 minutes maximum chunk size
CATEGORY_SHIFT_S = 30       # Sustained category shift threshold
ANCHOR_APPS = {"VS Code", "Code", "Figma", "Excel", "Word", "PyCharm", "IntelliJ", "devenv"}
GEMINI_MODEL = "gemini-1.5-flash"
DB_PATH = "chronotrace.db"`,
    },
    'collector/win_collector.py': {
      desc: 'Windows pywin32 active window polling (500ms) + WH_KEYBOARD_LL hook',
      snippet: `hwnd = win32gui.GetForegroundWindow()
window_title = win32gui.GetWindowText(hwnd)
_, pid = win32process.GetWindowThreadProcessId(hwnd)
app_name = psutil.Process(pid).name()
# Non-blocking low-level hook daemon increments keystroke count without recording keys`,
    },
    'collector/enricher.py': {
      desc: 'Category taxonomy heuristics and YouTube tutorial vs entertainment regex',
      snippet: `def get_category(app, title):
    # Regex heuristic differentiates tutorials from entertainment
    if "youtube" in title.lower():
        if any(k in title.lower() for k in ["tutorial", "how to", "course", "learn"]):
            return "Learning"
        return "Entertainment"
    ...`,
    },
    'pipeline/splitter.py': {
      desc: 'Routes >=10s to MAIN focus stream, <10s to MicroCounters',
      snippet: `class MicroCounters:
    rapid_switches = 0
    tab_flickers = 0
    def pattern(self):
        if self.rapid_switches >= 5 and self.avg_dwell < 3000:
            return "RESTLESS"
        if self.tab_flickers >= 3:
            return "TAB_HUNTING"
        if self.rapid_switches >= 3:
            return "SWITCHING"
        return "NORMAL"`,
    },
    'pipeline/chunker.py': {
      desc: 'Boundary detection: B1 IDLE_GAP, B2 ANCHOR_OPENED, B3 CATEGORY_SHIFT, B4 MAX_DURATION',
      snippet: `if idle_gap > IDLE_GAP_S:
    boundary = "IDLE_GAP"
elif is_anchor(app) and not chunk.anchor_opened:
    boundary = "ANCHOR_OPENED"
elif cat != last_cat and dwell >= CATEGORY_SHIFT_S:
    boundary = "CATEGORY_SHIFT"
elif chunk.duration_s() + dwell >= MAX_CHUNK_DURATION_S:
    boundary = "MAX_DURATION"`,
    },
    'pipeline/aggregator.py': {
      desc: 'Compact ~150 token JSON builder with returned_to_anchor detection',
      snippet: `summary = {
    "chunk_id": f"{date}_{time}_{counter}",
    "duration_s": chunk.duration_s(),
    "anchor_app": primary_anchor,
    "returned_to_anchor": left_and_returned, # Distinguishes reference lookup from distraction!
    "dominant_category": max_by_dwell_time,  # Weighted by dwell, NOT count
    "session_start_restless": first_micro == "RESTLESS"
}`,
    },
    'pipeline/llm_engine.py': {
      desc: 'Gemini 1.5 Flash real-time classification + end-of-day narrative pass',
      snippet: `model = genai.GenerativeModel("gemini-1.5-flash", generation_config={"temperature": 0.1})
# Formats summary as human readable prose
# Enforces exact 9-field JSON: intent, confidence, distraction_detected, work_state, etc.`,
    },
    'storage/db.py': {
      desc: 'Thread-safe SQLite connection pool, schema migrations, and re-entry queries',
      snippet: `def get_last_session_for_project(project):
    # Returns last session matching project keyword for laptop wake briefing
    # "Last time on this project was 3 days ago. You were doing X, left Y unresolved."`,
    },
  };

  const copyCommand = 'pip install -r requirements.txt && python main.py';

  const handleCopyCmd = () => {
    navigator.clipboard.writeText(copyCommand);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-xl bg-white border border-slate-200 shadow-xs p-6 space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-100">
        <div>
          <h2 className="text-base font-semibold text-slate-900">
            Local Windows Python Agent
          </h2>
          <div className="flex items-center gap-2 text-xs text-slate-500 mt-0.5">
            <span>Runs locally in background on Windows 10/11</span>
            <span aria-hidden="true">·</span>
            <span>Zero cloud telemetry upload; all local SQLite</span>
          </div>
        </div>

        {/* Quick Launch Command */}
        <div className="flex items-center gap-2">
          <div className="px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg font-mono text-xs text-slate-800">
            {copyCommand}
          </div>
          <button
            onClick={handleCopyCmd}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-slate-900 hover:bg-slate-800 rounded-lg transition-colors shadow-xs"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copied ? 'Copied' : 'Copy'}</span>
          </button>
        </div>
      </div>

      {/* Code File Explorer */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* File List */}
        <div className="space-y-1">
          <div className="text-[11px] font-mono font-semibold text-slate-500 px-2 py-1">
            PROJECT FILES
          </div>
          {Object.keys(fileSummaries).map((fname) => (
            <button
              key={fname}
              onClick={() => setSelectedFile(fname)}
              className={`w-full text-left px-3 py-2 rounded-lg text-xs font-mono transition-colors flex items-center justify-between ${
                selectedFile === fname
                  ? 'bg-slate-100 text-slate-900 font-semibold'
                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
              }`}
            >
              <span className="truncate">{fname}</span>
              <FileCode className="w-3.5 h-3.5 text-slate-400 shrink-0" />
            </button>
          ))}
        </div>

        {/* Code Content Preview */}
        <div className="md:col-span-3 rounded-lg bg-slate-900 text-slate-100 p-4 space-y-2 shadow-xs">
          <div className="flex items-center justify-between pb-2 border-b border-slate-800">
            <div>
              <div className="text-xs font-mono font-semibold text-emerald-400">
                {selectedFile}
              </div>
              <div className="text-[11px] text-slate-400 mt-0.5">
                {fileSummaries[selectedFile]?.desc}
              </div>
            </div>
            <span className="text-[10px] font-mono text-slate-400">Python 3.11</span>
          </div>

          <pre className="text-xs font-mono text-slate-200 leading-relaxed overflow-x-auto p-3 rounded-md bg-slate-950/80 border border-slate-800">
            <code>{fileSummaries[selectedFile]?.snippet}</code>
          </pre>
        </div>
      </div>
    </div>
  );
};
