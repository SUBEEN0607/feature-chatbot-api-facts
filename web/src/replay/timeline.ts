// Turns a simulated night's event log (docs/EVENT_LOG.md) into positions at any replay time t
// (minutes since opening). Walking durations are drawing choices, not simulation output.
import type { Night } from "../data";
import { AISLE_Z, DOOR_IN, DOOR_OUT, STREET_IN, STREET_OUT, queueSpot, staffHome, type TableSpot, type V2 } from "./layout";

export type Segment = "twenties" | "office" | "family";
export const SEGMENTS: Record<Segment, { label: string; color: string }> = {
  twenties: { label: "20대 친구 모임", color: "#e0735a" },
  office: { label: "직장인 회식", color: "#43648a" },
  family: { label: "동네 가족", color: "#d4a032" },
};
export const STAFF_COLOR = "#1f6b4e";

const WALK_IN = 0.8;
const TO_TABLE = 0.8;
const LEAVE = 1.6;
const BALK_EXIT = 1.4;

export type Party = {
  id: number;
  size: number;
  arrive: number;
  seat: number | null;
  table: string | null;
  leave: number | null;
  balk: number | null;
  bill: number;
  segment: Segment;
  simSegment: boolean;
  tables?: string[];
  closed?: boolean;
};

export type Pose = { x: number; z: number; seated: boolean; visible: boolean; faded: boolean };

// Fallback for event logs from before the sim assigned segments (display-only rule): 4-person parties before 19:30 read
// as 회식, 3+ before 18:30 as a family, the rest split by party id.
function segmentOf(id: number, size: number, arrive: number): Segment {
  if (size === 4 && arrive < 150) return "office";
  if (size >= 3 && arrive < 90) return "family";
  return (id * 37) % 100 < 58 ? "twenties" : "office";
}

export function parties(night: Night): Party[] {
  const byId = new Map<number, Party>();
  for (const e of night.events) {
    if (e.party == null) continue;
    let p = byId.get(e.party);
    if (!p) {
      p = { id: e.party, size: e.size ?? 2, arrive: e.t, seat: null, table: null, leave: null, balk: null, bill: 0,
        segment: e.segment ?? "twenties", simSegment: Boolean(e.segment) };
      byId.set(e.party, p);
    }
    if (e.type === "seat") {
      p.seat = e.t;
      p.table = e.table_id ?? null;
      if (e.tables && e.tables.length > 1) p.tables = e.tables;
    } else if (e.type === "leave") {
      p.leave = e.t;
      p.bill = e.bill ?? 0;
    } else if (e.type === "balk") { p.balk = e.t; if (e.closed) p.closed = true; }
  }
  const list = [...byId.values()].sort((a, b) => a.arrive - b.arrive);
  for (const p of list) if (!p.simSegment) p.segment = segmentOf(p.id, p.size, p.arrive);
  return list;
}

function lerp(a: V2, b: V2, f: number): V2 {
  return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f];
}

function along(path: V2[], f: number): V2 {
  if (f <= 0) return path[0];
  if (f >= 1) return path[path.length - 1];
  const lens = path.slice(1).map((p, i) => Math.hypot(p[0] - path[i][0], p[1] - path[i][1]));
  const total = lens.reduce((s, l) => s + l, 0);
  let d = f * total;
  for (let i = 0; i < lens.length; i++) {
    if (d <= lens[i]) return lerp(path[i], path[i + 1], lens[i] ? d / lens[i] : 1);
    d -= lens[i];
  }
  return path[path.length - 1];
}

function tablePath(t: TableSpot, seat: V2): V2[] {
  if (t.terrace) return [DOOR_OUT, [seat[0], DOOR_OUT[1] + 0.3], seat];
  return [DOOR_OUT, DOOR_IN, [DOOR_IN[0], AISLE_Z], [t.x, AISLE_Z], seat];
}

const walkOffset = (k: number): V2 => [((k % 2) - 0.5) * 0.45, Math.floor(k / 2) * 0.45];

export function makePoser(tables: Map<string, TableSpot>) {
  return function pose(p: Party, k: number, t: number, queueIndex: number): Pose {
    const off = walkOffset(k);
    const hidden: Pose = { x: 0, z: 0, seated: false, visible: false, faded: false };
    const spawn = p.arrive - WALK_IN;
    if (t < spawn) return hidden;
    const at = (v: V2, seated = false, faded = false): Pose => ({ x: v[0], z: v[1], seated, visible: true, faded });
    const withOff = (v: V2): V2 => [v[0] + off[0], v[1] + off[1]];
    if (t < p.arrive) return at(withOff(along([STREET_IN, [DOOR_OUT[0] - 1.2, STREET_IN[1] - 1.2], DOOR_OUT], (t - spawn) / WALK_IN)));

    const waitingUntil = p.seat ?? p.balk ?? p.arrive;
    if (t < waitingUntil) return at(withOff(queueSpot(queueIndex)));

    if (p.balk != null && p.seat == null) {
      const f = (t - p.balk) / BALK_EXIT;
      if (f >= 1) return hidden;
      return at(withOff(along([queueSpot(queueIndex), [queueSpot(0)[0], STREET_OUT[1]], STREET_OUT], f)), false, true);
    }
    if (p.seat == null || !p.table) return hidden;
    // a group across two tables: four per table, in order
    const table = tables.get(p.tables ? p.tables[Math.min(p.tables.length - 1, Math.floor(k / 4))] ?? p.table : p.table);
    if (!table) return hidden;
    if (p.tables) k = k % 4;
    // a booked 회식 of 8 on a 4-top: the extra four sit at the table ends
    const ends: V2[] = [[table.x - 0.95, table.z - 0.22], [table.x - 0.95, table.z + 0.22], [table.x + 0.95, table.z - 0.22], [table.x + 0.95, table.z + 0.22]];
    const seat = k < table.seats.length ? table.seats[k] : ends[(k - table.seats.length) % ends.length];
    const inPath = tablePath(table, seat);
    if (t < p.seat + TO_TABLE) return at(along(inPath, (t - p.seat) / TO_TABLE));
    const leave = p.leave ?? Infinity;
    if (t < leave) return at(seat, true);
    const f = (t - leave) / LEAVE;
    if (f >= 1) return hidden;
    return at(along([...inPath.slice().reverse(), [DOOR_OUT[0] + 1.5, STREET_OUT[1]], STREET_OUT], f));
  };
}

export type Stats = { seated: number; waiting: number; waitingParties: number; walkaways: number; revenue: number; arrived: number };

export function statsAt(list: Party[], t: number): Stats {
  const s: Stats = { seated: 0, waiting: 0, waitingParties: 0, walkaways: 0, revenue: 0, arrived: 0 };
  for (const p of list) {
    if (p.arrive > t) continue;
    s.arrived += 1;
    if (p.seat != null && p.seat <= t && (p.leave == null || t < p.leave)) s.seated += p.size;
    const until = p.seat ?? p.balk ?? p.arrive;
    if (t < until) {
      s.waiting += p.size;
      s.waitingParties += 1;
    }
    if (p.balk != null && p.balk <= t) s.walkaways += 1;
    if (p.leave != null && p.leave <= t) s.revenue += p.bill;
  }
  return s;
}

// Order in the waiting line at time t (earlier arrivals stand closer to the door).
export function queueOrder(list: Party[], t: number): Map<number, number> {
  const m = new Map<number, number>();
  let i = 0;
  for (const p of list) {
    if (p.arrive <= t && t < (p.seat ?? p.balk ?? p.arrive)) m.set(p.id, i++);
  }
  return m;
}

export function occupiedTables(list: Party[], t: number): Set<string> {
  const s = new Set<string>();
  for (const p of list) if (p.table && p.seat != null && p.seat <= t && (p.leave == null || t < p.leave + 4)) for (const id of p.tables ?? [p.table]) s.add(id);
  return s;
}

// Staff: every order, payment and clearing needs a server (as in sim/engine.py). Tasks are assigned greedily
// to the first free server; between tasks a server stands at the counter.
type Task = { start: number; end: number; at: V2 };
export function staffPlan(night: Night, tables: Map<string, TableSpot>, servers: number) {
  const tasks: Task[] = [];
  for (const e of night.events) {
    const tbl = e.table_id ? tables.get(e.table_id) : undefined;
    if (!tbl) continue;
    if (e.type === "order") tasks.push({ start: e.t - (e.reorder ? 1.5 : 3), end: e.t, at: tbl.serve });
    if (e.type === "leave") tasks.push({ start: e.t - 2, end: e.t, at: tbl.serve });
    if (e.type === "table_ready") tasks.push({ start: e.t - 4, end: e.t, at: tbl.serve });
  }
  tasks.sort((a, b) => a.start - b.start);
  const lanes: Task[][] = Array.from({ length: servers }, () => []);
  const freeAt = Array(servers).fill(-Infinity);
  for (const task of tasks) {
    let k = freeAt.findIndex((f) => f <= task.start);
    if (k < 0) k = freeAt.indexOf(Math.min(...freeAt));
    lanes[k].push(task);
    freeAt[k] = Math.max(task.end, freeAt[k] + (task.end - task.start));
  }
  const TRAVEL = 0.5;
  return function staffPose(k: number, t: number): V2 {
    const home = staffHome(k);
    for (const task of lanes[k]) {
      if (t >= task.start - TRAVEL && t < task.start) return lerp(home, task.at, (t - (task.start - TRAVEL)) / TRAVEL);
      if (t >= task.start && t < task.end) return task.at;
      if (t >= task.end && t < task.end + TRAVEL) return lerp(task.at, home, (t - task.end) / TRAVEL);
    }
    return home;
  };
}

export function clockLabel(t: number, openMin = 17 * 60): string {
  const c = openMin + t;
  const h = Math.floor(c / 60) % 24;
  const m = Math.floor(c % 60);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

export function parseClock(s: string, openMin = 17 * 60): number | null {
  const m = /^(\d{1,2}):(\d{2})$/.exec(s);
  if (!m) return null;
  let c = Number(m[1]) * 60 + Number(m[2]);
  if (c < openMin) c += 24 * 60;
  return c - openMin;
}
