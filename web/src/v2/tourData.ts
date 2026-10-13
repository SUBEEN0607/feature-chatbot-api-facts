// The welcome tour's data contract (engines/_shared/ui/TOUR-SPEC.md): web/public/data/tour.json, written by
// `make tour` (sim/tour.py) from the season engine and the ontology. The web, Unity and Unreal read the same file;
// nothing here computes or types a card number.
export type TourAnchor = "sign" | "menu_board" | "tables" | "grill" | "staff" | "fridge" | "room";
export type TourParam = { criterion_id: string; name_ko: string; value: number | string; unit: string; display_ko: string;
  confidence: "H" | "M" | "L" | null; source_ids: string[]; is_lever: boolean; lever?: string | null; tag_ko: string; reviewed?: boolean };
export type TourSens = { lever: string; lever_ko?: string; step_ko: string; up_ko?: string; down_ko?: string; up: { op: number; covers: number } | null; down: { op: number; covers: number } | null };
export type TourStop = {
  order: number; anchor: TourAnchor; criterion_id: string; title_ko: string; side: "revenue" | "cost" | "result";
  value: number; unit: string; display_ko: string; share_of_revenue: number | null; formula_ko: string | null;
  params: TourParam[]; sensitivity: TourSens[]; question_ko: string; buckets: { label_ko: string; min: number | null; max: number | null }[];
  answer_bucket: number; reveal_ko: string; preliminary: boolean; source_ids?: string[]; confidence?: string | null;
};
export type TourData = {
  version: number; month: number; month_ko?: string; baseline_ko?: string; events?: string[]; plan: Record<string, unknown>;
  pnl: { revenue: number; cost: number; op: number; op_margin: number; lines: Record<"cogs" | "labor" | "rent" | "mgmt" | "fees", number>;
    lines_ko?: Record<string, string> };
  review?: { reviewed: number; total: number };
  stops: TourStop[];
};
export const PNL_ORDER = ["cogs", "labor", "rent", "mgmt", "fees"] as const;
