// 개선 리포트 (GAME-V2-SPEC §14): GET /season/{id}/report, /export.csv, /report.html, POST /report/ask; offline 시연
// reads web/public/guided/report.json (same shape + precomputed answers). Fields are read loosely: api/report.py
// serves a fallback shape until sim.report lands.
import { API_BASE, guided } from "./api";
import type { Plan } from "./types";

export type Improvement = {
  id?: string; month_index?: number; month_label?: string; lever?: keyof Plan; from?: unknown; to?: unknown; alt_plan?: Plan;
  cash_delta?: number; store_value_delta?: number; cost?: number; tag?: string; basis?: string; why_ko?: string;
  kind?: "lever" | "night_choice"; takeaway_ko?: string; lever_ko?: string; from_ko?: string; to_ko?: string; downside_ko?: string;
  decision?: string; decision_ko?: string; alt_night_choices?: Record<string, string>; month_indices?: number[]; alt_plans?: Record<string, Plan>; rating_delta?: number; regular_share_delta?: number;
  // fallback shape
  driver?: string; loss?: number; months?: string[]; levers?: string[]; events?: string[];
};
export type GoodDecision = { month_label: string; what?: string; what_ko?: string; why_ko?: string; net_vs_shadow: number | null;
  cash_delta?: number; store_value_delta?: number };
export type LuckMonth = { month_label: string; band_position: number; op: number; p10_op: number; p90_op: number; luck?: string; luck_ko?: string };
export type ReportRow = Record<string, string | number | null> & { month_label: string };
export type SeasonReport = {
  season_id?: string; source?: string; summary: Record<string, unknown>; improvements: Improvement[]; good_decisions: GoodDecision[];
  luck_months: LuckMonth[]; table: ReportRow[]; cash_only?: (Improvement & { warning_ko?: string })[]; data_limits?: { reviewed?: number; total?: number };
  asks?: { q: string; a: string; sources?: string[] }[];
};
export type ReportAnswer = { question: string; answer: string; citations?: string[]; backend?: string };

export const PRESET_QUESTIONS = ["가장 큰 실수는 뭐였어?", "운이 좋았던 달은?", "다음 시즌에 하나만 바꾼다면?", "잘한 결정은?"];

async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(API_BASE + path, init);
  if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
  return r.json() as Promise<T>;
}

export const reportApi = {
  get: (id: string) => j<SeasonReport>(`/season/${id}/report`),
  ask: (id: string, question: string) => j<ReportAnswer>(`/season/${id}/report/ask`, {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ question }) }),
  csvUrl: (id: string) => `${API_BASE}/season/${id}/export.csv`,
  htmlUrl: (id: string) => `${API_BASE}/season/${id}/report.html`,
  guided: () => guided<SeasonReport>("report.json"),
};

// columns shown in the month table (key, header, kind); the CSV carries everything
export const COLS: [string, string, "text" | "won" | "int" | "float2" | "pct"][] = [
  ["month_label", "월", "text"], ["events", "사건", "text"], ["levers_changed", "바꾼 운영", "text"], ["decisions", "밤 결정", "text"],
  ["op", "영업이익", "won"], ["net_vs_shadow", "평소 대비", "won"], ["covers", "손님", "int"], ["rating_after", "월말 평점", "float2"],
  ["cash_after", "월말 현금", "won"], ["band_position", "운의 위치", "pct"],
];

// CSV for the offline (시연) report, made in the browser: UTF-8 with BOM so Excel opens Korean correctly
export function reportCsv(rep: SeasonReport): string {
  const keys = [...new Set(rep.table.flatMap((r) => Object.keys(r)))];
  const esc = (v: unknown) => {
    const s = v == null ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return "﻿" + [keys.join(","), ...rep.table.map((r) => keys.map((k) => esc(r[k])).join(","))].join("\n");
}

// offline answer: the precomputed one when the question is a preset, else a short pointer at the table
export function offlineAnswer(rep: SeasonReport, q: string): ReportAnswer {
  const hit = rep.asks?.find((a) => a.q === q) ?? rep.asks?.find((a) => q.includes(a.q.slice(0, 4)));
  if (hit) return { question: q, answer: hit.a, citations: hit.sources, backend: "precomputed" };
  return { question: q, answer: "시연 모드에서는 미리 준비한 네 가지 질문에만 답합니다. 자유 플레이에서는 어떤 질문이든 이 시즌의 기록으로 답합니다.", backend: "offline" };
}
