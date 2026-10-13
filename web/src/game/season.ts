// Season helpers: headlines (same wording as sim/labels.py) and "what moved" (same as sim/precompute.py).
import type { Bands, Drivers, Moved } from "../data";

const man = (v: number) => `${v < 0 ? "적자 " : ""}${Math.round(Math.abs(v) / 10000).toLocaleString("ko-KR")}만원`;

export function headline(shockIf: string | null, actionPhrase: string | null, before: number, after: number): string {
  const parts: string[] = [];
  if (shockIf) parts.push(actionPhrase ? shockIf.slice(0, -1) + "고" : shockIf);
  if (actionPhrase) parts.push(actionPhrase === shockIf ? actionPhrase.replace("한 명", "한 명 더") : actionPhrase);
  const lead = parts.length ? parts.join(" ") : "평소대로라면";
  if (Math.abs(after - before) < 5000) return `${lead}, 한 달 영업이익은 ${man(before)}에서 거의 변하지 않습니다`;
  return `${lead}, 한 달 영업이익은 ${man(before)}에서 ${man(after)}으로 ${after < before ? "줄어듭니다" : "늘어납니다"}`;
}

const OP_PARTS: [string, number, string][] = [
  ["drv_revenue", 1, "매출"], ["drv_food_cost", -1, "식재료비"], ["drv_labor_cost", -1, "인건비"],
  ["drv_rent", -1, "임차료"], ["drv_mgmt_cost", -1, "관리비"], ["drv_fees", -1, "수수료"],
];

export function moved(before: Drivers, after: Drivers): Moved[] {
  return OP_PARTS.map(([d, sign, label]) => ({ driver: d, label, op_effect: sign * (after[d] - before[d]) }))
    .sort((a, b) => Math.abs(b.op_effect) - Math.abs(a.op_effect));
}

// One finished month, kept so the season summary can reopen its receipt.
export type MonthRecord = {
  month: number;
  shock: string;
  action: string;
  stateBefore: string;
  stateAfter: string;
  lasting: string[];
  base: Bands;
  shocked: Bands;
  reacted: Bands;
  drivers: { base: Drivers; shocked: Drivers; reacted: Drivers };
  headline: string;
  op: number;
  baseOp: number;
};
