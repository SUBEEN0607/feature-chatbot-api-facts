// Season metadata for offline display: every 가정/source tag with its note (web/public/data/season.json, written by
// web/scripts/sync_season.py from research/*.yaml and ontology/sources.csv).
import { useData } from "../data";
import type { Plan, Review } from "./types";

type Leaf = { value?: unknown; tag?: string; note?: string; [k: string]: unknown };
export type Source = { title: string; by: string; year: string; url: string; note: string };
export type SurvivalTable = { n: number; events: number; table: { month: number; survival: number; ci_low: number; ci_high: number; at_risk: number }[]; share_closed_within_24m?: number };
export type SeasonMeta = {
  params: Record<string, Record<string, Leaf | unknown>>;
  events: Record<string, { label: string; group: string; mechanism: string; tag: string; prob?: Record<string, number> }>;
  calendar: Record<string, { label: string; note: string; demand_index: number; tags?: Record<string, string> }>;
  sources: Record<string, Source>;
  district: {
    rent: { hyehwa_per_m2: number; seoul_per_m2: number; national_per_m2: number; unit: string; source_ids: string[]; hyehwa_per_m2_label?: string };
    survival: { areas?: string[]; cohort?: string; wide_pork_name_only?: SurvivalTable; wide_hansik_all?: SurvivalTable; study_area_hansik?: SurvivalTable };
  };
};

export const useSeasonMeta = () => useData<SeasonMeta>("season.json");

export function leaf(meta: SeasonMeta | null, path: string): Leaf | null {
  let node: unknown = meta?.params;
  for (const k of path.split(".")) {
    if (!node || typeof node !== "object") return null;
    node = (node as Record<string, unknown>)[k];
  }
  return node && typeof node === "object" ? (node as Leaf) : null;
}

export type TagInfo = { assume: boolean; ids: string[] };
export function parseTag(tag: string | undefined | null): TagInfo {
  const parts = (tag ?? "가정").split(/[;,]/).map((x) => x.trim()).filter(Boolean);
  return { assume: parts.some((p) => p.includes("가정")) || parts.length === 0, ids: parts.map((p) => p.match(/S\d+/)?.[0]).filter((x): x is string => Boolean(x)) };
}

// mirror of sim/season.py REASON_KO
export const REASON_KO: Record<string, string> = {
  wait_long: "너무 오래 기다림", service_slow: "주문이 늦게 나옴", price_high: "비싸다", price_good: "가격이 착하다",
  meat_good: "고기 좋다", meat_bad: "고기가 별로", banchan_good: "반찬이 푸짐", banchan_poor: "반찬이 아쉽다",
  clean: "깔끔하다", dirty: "위생이 아쉽다", staff_grill: "구워 줘서 편하다", soju_high: "소주가 비싸다",
  crowded: "북적거린다", menu_fun: "메뉴가 재밌다", hyped: "기대보다 별로", understaffed: "직원 부르기 힘들다",
  tired_staff: "직원이 지쳐 보인다", comped: "이벤트 서비스를 받고 쓴 리뷰", reviews_inflated: "별점이 이벤트로 부풀려진 것 같다",
};
export const SEGMENT_KO: Record<string, string> = { twenties: "20대 친구 모임", office: "직장인 회식", family: "동네 가족" };

// Used only when a month file has no persona text (guided files before agents.persona.render_month ran).
export function reviewFallback(r: Review, plan?: Plan): string {
  if (r.text) return r.text;
  const codes = r.reason_codes ?? [];
  const bits = codes.map((c) => {
    if (c === "wait_long") return r.walked_away ? "기다리다 그냥 돌아왔어요" : `${Math.round(r.wait_min ?? 0)}분 기다렸어요`;
    if (c === "price_high" && plan) return `1인분 ${plan.meat_price.toLocaleString("ko-KR")}원은 좀 비싸요`;
    return REASON_KO[c] ?? c;
  });
  const lead = r.stars >= 4 ? "좋았어요" : r.stars <= 2 ? "아쉬웠어요" : "무난했어요";
  return bits.length ? `${bits.join(", ")}. ${lead}` : lead;
}
