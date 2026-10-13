// Number formatting for the v2 screens. Money in 만원 with a sign; every changing number uses tabular figures (CSS).
export const man = (v: number) => {
  const r = Math.round(v / 10000);
  return `${r < 0 ? "−" : ""}${Math.abs(r).toLocaleString("ko-KR")}만원`;
};
export const manSigned = (v: number) => {
  const r = Math.round(v / 10000);
  return r === 0 ? "0만원" : `${r > 0 ? "+" : "−"}${Math.abs(r).toLocaleString("ko-KR")}만원`;
};
export const won = (v: number) => `${Math.round(v).toLocaleString("ko-KR")}원`;
export const pct = (v: number, d = 0) => `${(v * 100).toFixed(d)}%`;
export const num = (v: number, d = 0) => v.toLocaleString("ko-KR", { maximumFractionDigits: d, minimumFractionDigits: d });
// months the cash lasts at this month's loss, as every screen says it: whole months, at least 1 (agents/persona.py,
// sim/season.py _owner_line use the same rule); null = not losing money or no cash left
export const runwayMonths = (cash: number, op: number | null | undefined) => (op != null && op < 0 && cash > 0 ? Math.max(1, Math.floor(cash / -op)) : null);
export const tone = (v: number, eps = 5000) => (v > eps ? "up" : v < -eps ? "down" : "flat");
// Engine label text may use "A → B"; the UI says it in words ("A에 따른 B").
export const noArrow = (t: string) => t.replace(/\s*(→|->)\s*/g, "에 따른 ");
