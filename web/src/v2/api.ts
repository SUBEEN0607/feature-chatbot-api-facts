// The local API (docs/GAME-V2-SPEC.md §11) and the offline guided data. VITE_API_BASE overrides the base URL.
import type { AskAnswer, MonthResult, MonthStart, Plan, PlanPreview, SeasonView, Survey } from "./types";

export const API_BASE: string = (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, msg: string) { super(msg); }
}

async function j<T>(path: string, body?: unknown, timeoutMs = 60000): Promise<T> {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const r = await fetch(API_BASE + path, body === undefined ? { signal: ctl.signal } : {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body), signal: ctl.signal,
    });
    if (!r.ok) throw new ApiError(r.status, `${path}: HTTP ${r.status} ${(await r.text()).slice(0, 200)}`);
    return (await r.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  health: () => j<{ status?: string; backend?: string }>("/health", undefined, 15000), // a busy single-worker API can be slow to answer
  // months < 6: a short season (1개월 체험) that ends, with its report, after that many months
  newSeason: (mode: "free" | "sandbox" | "guided", seed?: number, months?: number) => j<SeasonView>("/season", { mode, seed, ...(months ? { months } : {}) }),
  get: (id: string) => j<SeasonView>(`/season/${id}`),
  preview: (id: string, plan: Partial<Plan>, events?: string[]) => j<PlanPreview>(`/season/${id}/preview`, { plan, events }),
  // month_index (0-based): the month this play is for; the API refuses a stale one (409) and answers a repeat with the stored month
  play: (id: string, plan: Partial<Plan>, events?: string[], night_choices?: Record<string, string>, prediction?: unknown, month_index?: number) =>
    j<MonthResult>(`/season/${id}/play`, { plan, events, ...(night_choices ? { night_choices } : {}), ...(prediction ? { prediction } : {}),
      ...(month_index !== undefined ? { month_index } : {}) }),
  startMonth: (id: string, plan: Partial<Plan>) => j<MonthStart>(`/season/${id}/start_month`, { plan }),
  // a sandbox copy of a season at the start of one month (same state, same month events), for 비교 from the report
  fork: (id: string, month_index: number) => j<SeasonView>(`/season/${id}/fork`, { month_index }),
  ask: (id: string, who: string, question: string) => j<AskAnswer>(`/persona/${id}/ask`, { who, question }, 30000),
  survey: (id: string) => j<Survey>(`/season/${id}/survey`),
};

// --- guided (offline): web/public/guided, written by the workbook agent -----------------------------
export type GuidedOption = { id: string; label: string; changes: Partial<Plan>; file: string; op: number; revenue: number; cash_after: number;
  rating_after: number; p10_op: number; p90_op: number; regular_share_after?: number;
  followup?: { month: number; label: string; op: number; covers: number; cash: number; rating: number; regular_share: number; store_value?: number; scripted?: boolean }[];
  next_line?: string | null };
export type GuidedStep = { n: number; month: number; label: string; title: string; events: string[]; narration: string[];
  decision: { prompt: string; options: GuidedOption[] }; story_choice: string };
export type GuidedNightDecision = { decision_point: import("./types").DecisionPoint; story_option: string;
  branches: { option_id: string; label_ko: string; file: string; op: number; cash_after: number; next_line?: string }[] };
export type GuidedIndex = { engine: string; seed: number; representative?: boolean; representative_note?: string; start: Record<string, number>; baseline_op: number; illustrative?: boolean; note?: string;
  story: (GuidedStep & { night_decision?: GuidedNightDecision })[];
  summary?: { title: string; basis: string; takeaways: string[];
    branches: { month: number; label: string; option: string; option_label: string; is_story: boolean; cash: number; store_value: number;
      regular_share: number; rating: number; end_label: string; closed?: boolean }[] } };

const cache = new Map<string, Promise<unknown>>();
export function guided<T>(file: string): Promise<T> {
  if (!cache.has(file)) cache.set(file, fetch(`./guided/${file}`).then((r) => {
    if (!r.ok) throw new Error(`guided/${file}: HTTP ${r.status}`);
    return r.json();
  }));
  return cache.get(file) as Promise<T>;
}
