/**
 * ChronoTrace Type Definitions
 */

export type IntentLabel =
  | 'DEEP_WORK'
  | 'LEARNING'
  | 'DISTRACTION'
  | 'DISTRACTION_BREAK'
  | 'COMMUNICATION'
  | 'AMBIENT'
  | 'ADMIN'
  | 'RESTLESS_START'
  | 'PARSE_ERROR';

export type MicroPattern = 'RESTLESS' | 'TAB_HUNTING' | 'SWITCHING' | 'NORMAL';

export interface TelemetryEvent {
  id?: string;
  timestamp: string;
  dwell_ms: number;
  category: string;
  app_name: string;
  window_title: string;
  keyboard_events: number;
}

export interface MicroCountersState {
  rapid_switches: number;
  unique_apps: string[];
  tab_flickers: number;
  total_dwell_ms: number;
  avg_dwell_ms: number;
  pattern: MicroPattern;
  events_count: number;
}

export interface MainEventSummary {
  app: string;
  title: string;
  dwell_s: number;
  keys: number;
}

export interface ChunkSummary {
  chunk_id: string;
  duration_s: number;
  start_time: string;
  end_time: string;
  closed_by: string;
  main_events: MainEventSummary[];
  anchor_app: string | null;
  anchor_held_s: number;
  returned_to_anchor: boolean;
  keyboard: {
    total_keys: number;
    rate_per_min: number;
  };
  micro_behavior: {
    total_rapid_switches: number;
    tab_flickers: number;
    avg_micro_dwell_ms: number;
    dominant_pattern: MicroPattern;
    unique_micro_apps: string[];
  };
  categories_present: string[];
  dominant_category: string;
  copy_paste_events: number;
  session_start_restless: boolean;
  // LLM Classification enrichment
  intent?: IntentLabel;
  confidence?: number;
  primary_task?: string;
  distraction_detected?: boolean;
  distraction_type?: 'procrastination' | 'rabbit_hole' | 'social' | 'break' | null;
  work_state?: 'settled' | 'unsettled' | 'interrupted' | 'productive';
  pre_distraction_signal?: string | null;
  summary?: string;
  unresolved_threads?: string[];
  user_corrected?: boolean;
}

export interface DailySynthesis {
  date: string;
  work_state?: 'settled' | 'unsettled' | 'interrupted' | 'productive' | 'UNSETTLED' | 'PRODUCTIVE' | 'TRANSITIONING';
  total_deep_work_s: number;
  total_distraction_s: number;
  fragmentation_score: number;
  peak_focus_window: string;
  context_switches: number;
  distraction_triggers: string[];
  daily_narrative: string;
  unfinished_work: string[];
  in_progress?: boolean;
}

export interface ReentryBriefing {
  project: string;
  found: boolean;
  days_ago?: number;
  time_desc?: string;
  headline: string;
  primary_task?: string;
  summary?: string;
  unresolved_threads: string[];
  last_session?: ChunkSummary;
}
