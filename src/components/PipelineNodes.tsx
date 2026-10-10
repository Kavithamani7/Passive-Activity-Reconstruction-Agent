import React, { useState } from 'react';
import { Eye, Split, Box, FileText, Brain, CheckCircle2, Terminal, Copy, Check, Radio, RefreshCw, Laptop } from 'lucide-react';

export const PipelineNodes: React.FC = () => {
  const [selectedLayer, setSelectedLayer] = useState<number>(2);
  const [copied, setCopied] = useState<boolean>(false);
  const [testingConnection, setTestingConnection] = useState<boolean>(false);
  const [currentWindowData, setCurrentWindowData] = useState<any>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);

  const psScript = `# ChronoTrace Laptop Telemetry Bridge (Windows PowerShell 5.1 & PS Core Compatible)
# Extracts foreground window title card, process name & streams raw events to ChronoTrace
$targetUrl = if ($env:CHRONOTRACE_URL) { $env:CHRONOTRACE_URL + "/api/telemetry/ingest" } else { "https://ais-dev-fnyuc3v7x243csnvzmg3qg-863384055458.asia-southeast1.run.app/api/telemetry/ingest" }

Add-Type @"
  using System;
  using System.Runtime.InteropServices;
  using System.Text;
  public class WinApi {
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Auto)]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
    [DllImport("user32.dll", SetLastError = true)]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);
  }
"@

Write-Host ">> ChronoTrace: Streaming active laptop telemetry to $targetUrl..." -ForegroundColor Cyan
$lastTitle = ""; $lastTime = [DateTime]::UtcNow

while ($true) {
  $hwnd = [WinApi]::GetForegroundWindow()
  $sb = New-Object System.Text.StringBuilder 256
  [WinApi]::GetWindowText($hwnd, $sb, 256) | Out-Null
  $title = $sb.ToString()
  $pidVal = 0
  [WinApi]::GetWindowThreadProcessId($hwnd, [ref]$pidVal) | Out-Null
  $proc = if ($pidVal -gt 0) { (Get-Process -Id $pidVal -ErrorAction SilentlyContinue).ProcessName } else { "Unknown" }

  if ($title -ne $lastTitle -and $title.Length -gt 0) {
    $now = [DateTime]::UtcNow
    $dwell = [int]($now - $lastTime).TotalMilliseconds
    $category = if ($title -match 'Visual Studio|Code|GitHub|Terminal|cmd|PowerShell|Neovim') { 'Deep Work' }
                elseif ($title -match 'Stack Overflow|Documentation|MDN|Docs|Book|Paper') { 'Learning' }
                elseif ($title -match 'YouTube|Netflix|Reddit|Twitter|X.com|TikTok|Twitch') { 'Distraction' }
                else { 'Utility' }

    $payload = @{
      timestamp = $now.ToString("yyyy-MM-ddTHH:mm:ssZ")
      app_name = $proc
      window_title = $title
      category = $category
      dwell_ms = [Math]::Max(500, $dwell)
      keyboard_events = 0
    } | ConvertTo-Json

    try {
      Invoke-RestMethod -Uri $targetUrl -Method Post -Body $payload -ContentType "application/json" -TimeoutSec 3 | Out-Null
      Write-Host "[$($now.ToString('HH:mm:ss'))] Streamed: $proc -> $title ($category)" -ForegroundColor Green
    } catch {
      Write-Host "[$($now.ToString('HH:mm:ss'))] Telemetry POST error: $_" -ForegroundColor Yellow
    }
    $lastTitle = $title; $lastTime = $now
  }
  Start-Sleep -Milliseconds 500
}`;

  const copyScript = () => {
    navigator.clipboard.writeText(psScript);
    setCopied(true);
    setTimeout(() => setCopied(false), 2200);
  };

  const handleTestCurrentWindow = async () => {
    setTestingConnection(true);
    setConnectionError(null);
    try {
      const res = await fetch('/api/current-window');
      if (!res.ok) {
        throw new Error(`Server returned HTTP ${res.status}`);
      }
      const data = await res.json();
      setCurrentWindowData(data);
    } catch (err: any) {
      setConnectionError(err.message || 'Failed to fetch current window');
    } finally {
      setTestingConnection(false);
    }
  };

  const layers = [
    {
      num: 1,
      name: 'Event Collector',
      tech: 'pywin32 / psutil',
      desc: 'Samples foreground window title, process executable, dwell time, and keypress volume every 500ms.',
      icon: Eye,
      details: [
        'Uses win32gui.GetForegroundWindow() and GetWindowText()',
        'Resolves process name via psutil with exception resilience',
        'Runs low-level WH_KEYBOARD_LL daemon hook counting keystrokes without recording content',
        'Only emits when window title or process executable changes',
      ],
    },
    {
      num: 2,
      name: 'Stream Splitter',
      tech: 'Dwell Threshold (10,000ms)',
      desc: 'Routes >=10s to MAIN focus stream; aggregates <10s into high-fidelity micro-behavior counters.',
      icon: Split,
      details: [
        'Dwell < 10s: appends to MicroCounters (rapid_switches, tab_flickers, total_dwell_ms)',
        'Pattern evaluation: RESTLESS (switches >= 5 & avg dwell < 3s), TAB_HUNTING (flickers >= 3), SWITCHING (switches >= 3)',
        'Dwell >= 10s: attaches micro snapshot to chunker.add_event() and resets micro counters',
        'Prevents short tab flickers from polluting sustained focus logs while capturing restlessness',
      ],
    },
    {
      num: 3,
      name: 'Chunker Engine',
      tech: '4 Priority Boundaries',
      desc: 'Groups sustained main events into cognitive work blocks bounded by behavioral shifts.',
      icon: Box,
      details: [
        'B1: IDLE_GAP — Inactivity gap > 120s force closes chunk',
        'B2: ANCHOR_OPENED — VS Code / Figma opened when current chunk had no anchor',
        'B3: CATEGORY_SHIFT — Category changes with dwell >= 30s',
        'B4: MAX_DURATION — Total chunk duration >= 1,200s (20 minutes)',
        'Idle detector background thread polls every 30s to trigger B1 closures',
      ],
    },
    {
      num: 4,
      name: 'Aggregator',
      tech: '150-Token JSON Matrix',
      desc: 'Projects finalized chunk into a dense behavioral payload with novelty indicators.',
      icon: FileText,
      details: [
        'returned_to_anchor: True if anchor app was left and returned to (distinguishes doc lookups from distractions)',
        'session_start_restless: True if initial micro block had pattern RESTLESS',
        'Dominant category: weighted strictly by dwell duration, not event count',
        'Formats main window timeline with app, title, dwell_s, and keypress counts',
        'Asynchronously dispatches summary to Gemini LLM Engine',
      ],
    },
    {
      num: 5,
      name: 'LLM Intent Engine',
      tech: 'Google Gemini (gemini-3.8-flash)',
      desc: 'Two-tier cognition: per-chunk real-time classification + end-of-day multi-chunk synthesis.',
      icon: Brain,
      details: [
        'Per-Chunk: Outputs intent (DEEP_WORK, LEARNING, DISTRACTION, etc.), confidence, primary task, and open loops',
        'Respects returned_to_anchor to prevent false distraction flags on quick reference lookups',
        'Temperature 0.1 with structured JSON schema output and single retry on decode error',
        'End-of-day: Computes fragmentation score (0-10), peak focus window, and daily narrative',
      ],
    },
  ];

  const active = layers.find((l) => l.num === selectedLayer) || layers[0];
  const IconComponent = active.icon;

  return (
    <div className="rounded-xl bg-white border border-slate-200 shadow-xs p-6 space-y-6">
      {/* Title */}
      <div>
        <h2 className="text-base font-semibold text-slate-900">
          ChronoTrace 5-Layer Pipeline Architecture
        </h2>
        <div className="flex items-center gap-2 text-xs text-slate-500 mt-0.5">
          <span>Continuous zero-effort Windows telemetry processing</span>
          <span aria-hidden="true">·</span>
          <span>Click any layer to inspect operational mechanics</span>
        </div>
      </div>

      {/* Layer Flow Bar */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-2.5">
        {layers.map((layer) => {
          const isSelected = selectedLayer === layer.num;
          const LayerIcon = layer.icon;
          return (
            <button
              key={layer.num}
              onClick={() => setSelectedLayer(layer.num)}
              className={`p-3.5 rounded-lg text-left transition-all border flex flex-col justify-between ${
                isSelected
                  ? 'bg-slate-900 border-slate-900 text-white shadow-xs'
                  : 'bg-slate-50 border-slate-200 hover:bg-slate-100 text-slate-800'
              }`}
            >
              <div className="flex items-center justify-between">
                <span
                  className={`text-[11px] font-mono font-semibold ${
                    isSelected ? 'text-slate-400' : 'text-slate-500'
                  }`}
                >
                  L0{layer.num}
                </span>
                <LayerIcon
                  className={`w-4 h-4 ${
                    isSelected ? 'text-emerald-400' : 'text-slate-500'
                  }`}
                />
              </div>
              <div className="mt-3">
                <div className="text-xs font-semibold">
                  {layer.name}
                </div>
                <div
                  className={`text-[11px] truncate mt-0.5 ${
                    isSelected ? 'text-slate-300' : 'text-slate-500'
                  }`}
                >
                  {layer.tech}
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {/* Detailed Layer Inspection Card */}
      <div className="p-5 rounded-lg bg-slate-50 border border-slate-200/80 space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="w-9 h-9 rounded-lg bg-white border border-slate-200 flex items-center justify-center text-slate-900 shadow-2xs shrink-0">
              <IconComponent className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono font-bold text-emerald-700">
                  Layer {active.num}
                </span>
                <span className="text-sm font-semibold text-slate-900">
                  {active.name}
                </span>
              </div>
              <p className="text-xs text-slate-600 mt-0.5">{active.desc}</p>
            </div>
          </div>
          <span className="text-xs font-mono font-medium text-slate-500 shrink-0 bg-white px-2.5 py-1 rounded border border-slate-200">
            {active.tech}
          </span>
        </div>

        <div className="pt-3 border-t border-slate-200">
          <div className="text-xs font-semibold text-slate-800 mb-2.5">
            Execution Rules & Invariants:
          </div>
          <ul className="space-y-2">
            {active.details.map((item, idx) => (
              <li
                key={idx}
                className="flex items-start gap-2.5 text-xs text-slate-700"
              >
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <span className="leading-relaxed font-normal">{item}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Connect Laptop Telemetry Section */}
      <div className="mt-8 rounded-xl border border-indigo-200 bg-gradient-to-b from-indigo-50/50 to-white p-5 shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-indigo-100">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-lg bg-indigo-600 text-white flex items-center justify-center shadow-xs shrink-0 mt-0.5">
              <Laptop className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-slate-900">
                  Connect Laptop Telemetry & Full Title Card Extractor
                </h3>
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-800">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  Live Hook
                </span>
              </div>
              <p className="text-xs text-slate-600 mt-0.5">
                Stream real active foreground window transitions, process titles, and dwell timestamps from your Windows laptop straight to ChronoTrace instead of dummy data.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={copyScript}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all shadow-2xs ${
                copied
                  ? 'bg-emerald-600 text-white'
                  : 'bg-indigo-600 hover:bg-indigo-700 text-white'
              }`}
            >
              {copied ? (
                <>
                  <Check className="w-4 h-4" />
                  Copied Script!
                </>
              ) : (
                <>
                  <Copy className="w-4 h-4" />
                  Copy PowerShell Hook
                </>
              )}
            </button>

            <button
              onClick={handleTestCurrentWindow}
              disabled={testingConnection}
              className="flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 transition-colors shadow-2xs disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${testingConnection ? 'animate-spin text-indigo-600' : ''}`} />
              Test /api/current-window
            </button>
          </div>
        </div>

        {/* Live Window Test Card if fetched */}
        {currentWindowData && (
          <div className="mt-4 p-3.5 rounded-lg bg-slate-900 text-slate-100 font-mono text-xs border border-slate-800">
            <div className="flex items-center justify-between text-[11px] text-slate-400 pb-2 border-b border-slate-800 mb-2">
              <span className="flex items-center gap-1.5 text-emerald-400 font-bold">
                <Radio className="w-3.5 h-3.5 animate-pulse" />
                Latest Raw Event (via GET /api/current-window)
              </span>
              <span>{currentWindowData.timestamp}</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[12px]">
              <div>
                <span className="text-slate-400">App Name: </span>
                <span className="text-amber-300 font-bold">{currentWindowData.app_name}</span>
              </div>
              <div>
                <span className="text-slate-400">Category: </span>
                <span className="text-blue-300 font-semibold">{currentWindowData.category}</span>
              </div>
              <div className="sm:col-span-2">
                <span className="text-slate-400">Window Title Card: </span>
                <span className="text-emerald-300 font-medium">"{currentWindowData.window_title}"</span>
              </div>
              <div>
                <span className="text-slate-400">Dwell Duration: </span>
                <span className="text-purple-300">{currentWindowData.dwell_ms} ms</span>
              </div>
            </div>
          </div>
        )}

        {connectionError && (
          <div className="mt-3 p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs">
            Error: {connectionError}
          </div>
        )}

        {/* Script preview */}
        <div className="mt-4">
          <div className="flex items-center justify-between text-[11px] text-slate-600 mb-1.5 font-medium">
            <span className="flex items-center gap-1.5">
              <Terminal className="w-3.5 h-3.5 text-slate-500" />
              Run in Windows PowerShell (Admin or User):
            </span>
            <span className="text-[10px] text-slate-400 font-mono">500ms sampling · Extracts full title card</span>
          </div>
          <div className="relative rounded-lg bg-slate-950 p-3.5 text-[11px] font-mono text-slate-200 overflow-x-auto border border-slate-800 max-h-48 overflow-y-auto">
            <pre className="whitespace-pre">{psScript}</pre>
          </div>
        </div>
      </div>
    </div>
  );
};
