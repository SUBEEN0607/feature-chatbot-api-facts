// The store answers the player (interactivity #5): hover or click a table for that party's card (who, spend so far,
// satisfaction and why), a 만족도 tint ring under every table, and a short label at the object a lever just changed.
import { useEffect, useMemo, useRef, useState } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { Html } from "@react-three/drei";
import * as THREE from "three";
import { COUNTER, ROOM, type TableSpot } from "../replay/layout";
import { SEGMENTS, type Party } from "../replay/timeline";
import type { NightV2, Plan } from "../v2/types";

type PartyInfo = { party: Party; satisfaction: number | null; reason: string | null };

export function partyInfo(night: NightV2, list: Party[]): Map<number, PartyInfo> {
  const m = new Map<number, PartyInfo>();
  const byId = new Map(list.map((p) => [p.id, p]));
  for (const p of list) m.set(p.id, { party: p, satisfaction: null, reason: null });
  for (const e of night.events) {
    if ((e.type === "leave" || e.type === "balk") && e.party != null && byId.has(e.party)) {
      const info = m.get(e.party)!;
      if (e.satisfaction != null) info.satisfaction = e.satisfaction;
      if (e.bubble) info.reason = e.bubble.text;
    }
  }
  return m;
}

const satColor = (s: number | null) => (s == null ? "#b9bec4" : s >= 0.6 ? "#2f8f5b" : s >= 0.47 ? "#d9a441" : "#c8402e");
const satWord = (s: number | null) => (s == null ? "아직 모름" : s >= 0.6 ? "만족" : s >= 0.47 ? "보통" : "불만");

// which party sits at a table at time t (seat .. leave)
function partyAt(list: Party[], tableId: string, t: number) {
  return list.find((p) => p.table === tableId && p.seat != null && p.seat <= t && t < (p.leave ?? Infinity));
}

export function TableHotspots({ spots, list, info, tRef, plan, overlay }: {
  spots: TableSpot[]; list: Party[]; info: Map<number, PartyInfo>; tRef: React.RefObject<number>; plan: Plan; overlay: boolean;
}) {
  const [hover, setHover] = useState<string | null>(null);
  const [pinned, setPinned] = useState<string | null>(null);
  const [, force] = useState(0);
  const rings = useRef<Map<string, THREE.MeshBasicMaterial>>(new Map());
  const ringMeshes = useRef<Map<string, THREE.Mesh>>(new Map());
  const shown = pinned ?? hover;
  const lastT = useRef(-1);
  useFrame(() => {
    const t = tRef.current ?? 0;
    for (const s of spots) {
      const p = partyAt(list, s.id, t);
      const mat = rings.current.get(s.id);
      const mesh = ringMeshes.current.get(s.id);
      if (mat) mat.color.set(satColor(p ? info.get(p.id)?.satisfaction ?? null : null));
      if (mesh) mesh.visible = overlay && Boolean(p);
    }
    // refresh the open card a few times per second while the night runs
    if (shown && Math.abs(t - lastT.current) > 0.5) { lastT.current = t; force((x) => x + 1); }
  });
  const t = tRef.current ?? 0;
  const spot = shown ? spots.find((s) => s.id === shown) : undefined;
  const p = spot ? partyAt(list, spot.id, t) : undefined;
  const pi = p ? info.get(p.id) : undefined;
  return (
    <group>
      {spots.map((s) => (
        <group key={s.id}>
          {/* invisible hit box over the table and its stools */}
          <mesh position={[s.x, 0.6, s.z]}
            onPointerOver={(e) => { e.stopPropagation(); setHover(s.id); document.body.style.cursor = "pointer"; }}
            onPointerOut={() => { setHover((h) => (h === s.id ? null : h)); document.body.style.cursor = ""; }}
            onClick={(e) => { e.stopPropagation(); setPinned((x) => (x === s.id ? null : s.id)); }}>
            <boxGeometry args={[1.6, 1.2, 1.9]} />
            <meshBasicMaterial transparent opacity={0} depthWrite={false} />
          </mesh>
          <mesh position={[s.x, 0.012, s.z]} rotation={[-Math.PI / 2, 0, 0]} visible={false}
            ref={(m) => { if (m) ringMeshes.current.set(s.id, m); }}>
            <ringGeometry args={[0.95, 1.18, 40]} />
            <meshBasicMaterial ref={(m) => { if (m) rings.current.set(s.id, m); }} color="#b9bec4" transparent opacity={0.85} depthWrite={false} />
          </mesh>
        </group>
      ))}
      {spot && (
        <Html position={[spot.x, 1.95, spot.z]} center zIndexRange={[40, 30]} pointerEvents="none">
          <div className="s3-card" data-testid="table-card" data-table={spot.id}>
            <b>{spot.terrace ? "야장" : "테이블"} {spot.id}</b>
            {p ? (
              <>
                <span><i style={{ background: SEGMENTS[p.segment]?.color }} />{SEGMENTS[p.segment]?.label} {p.size}명</span>
                <span>{p.leave != null && t >= p.leave ? `계산 ${Math.round(p.bill).toLocaleString("ko-KR")}원` : `예상 계산 약 ${Math.round(p.bill || p.size * plan.meat_price * 1.4).toLocaleString("ko-KR")}원`}</span>
                <span>만족도 <b style={{ color: satColor(pi?.satisfaction ?? null) }}>{satWord(pi?.satisfaction ?? null)}</b>{pi?.satisfaction != null ? ` (${Math.round(pi.satisfaction * 100)})` : ""}</span>
                {pi?.reason && <span className="why">"{pi.reason}"</span>}
              </>
            ) : <span>빈 테이블</span>}
            {pinned === spot.id && <span className="hint">다시 누르면 닫힙니다</span>}
          </div>
        </Html>
      )}
    </group>
  );
}

// A short label at the object a lever just changed, so every plan change is visible in the store.
const PING_AT: Partial<Record<keyof Plan, [number, number, number]>> = {
  meat_price: [2.3, 2.3, ROOM.z1 + 0.2], soju_price: [5.0, 2.4, ROOM.z0 + 0.7], meat_grade: [ROOM.x0 + 0.6, 2.6, -0.2],
  menu_extras: [ROOM.x0 + 0.6, 2.6, -0.2], banchan: [0, 1.6, -1.9], staff_grilling: [2.55, 1.9, 1.35],
  staff_per_shift: [COUNTER[0], 2.2, COUNTER[1] + 0.4], close_hour: [2.3, 2.3, ROOM.z1 + 0.2], lunch: [-2.3, 2.1, ROOM.z1 + 0.2],
  terrace: [4.5, 2.5, 5.3], marketing_budget: [-1.6, 2.4, ROOM.z1 + 1.3], review_event: [2.3, 2.3, ROOM.z1 + 0.2],
  group_reservations: [5.1, 1.8, 1.35], hygiene: [0, 0.8, 0.4],
};

export function ChangePings({ plan, describe }: { plan: Plan; describe: (k: keyof Plan, p: Plan) => string }) {
  const prev = useRef<Plan | null>(null);
  const [pings, setPings] = useState<{ id: number; key: keyof Plan; text: string }[]>([]);
  const seq = useRef(0);
  useEffect(() => {
    const before = prev.current;
    prev.current = plan;
    if (!before) return;
    const changed = (Object.keys(plan) as (keyof Plan)[]).filter((k) => JSON.stringify(plan[k]) !== JSON.stringify(before[k]));
    if (!changed.length) return;
    const add = changed.filter((k) => PING_AT[k]).map((k) => ({ id: ++seq.current, key: k, text: describe(k, plan) }));
    setPings((x) => [...x.filter((p) => !changed.includes(p.key)), ...add]);
    const ids = add.map((a) => a.id);
    const timer = setTimeout(() => setPings((x) => x.filter((p) => !ids.includes(p.id))), 2600);
    return () => clearTimeout(timer);
  }, [plan, describe]);
  return (
    <>
      {pings.map((p) => (
        <Html key={p.id} position={PING_AT[p.key]!} center zIndexRange={[35, 25]} pointerEvents="none">
          <span className="s3-ping" data-testid="change-ping" data-lever={p.key}>{p.text}</span>
        </Html>
      ))}
    </>
  );
}

export function useInfo(night: NightV2, list: Party[]) {
  return useMemo(() => partyInfo(night, list), [night, list]);
}

// Planning view: every lever that differs from last month keeps a tag at its object until the month is played.
export function PlanTags({ plan, base, describe }: { plan: Plan; base: Plan; describe: (k: keyof Plan, p: Plan) => string }) {
  const changed = (Object.keys(plan) as (keyof Plan)[]).filter((k) => PING_AT[k] && JSON.stringify(plan[k]) !== JSON.stringify(base[k]));
  // levers that share an anchor stack upwards
  const seen = new Map<string, number>();
  return (
    <>
      {changed.map((k) => {
        const at = PING_AT[k]!;
        const key = at.join(",");
        const n = seen.get(key) ?? 0;
        seen.set(key, n + 1);
        return (
          <Html key={k} position={[at[0], at[1] + n * 0.45, at[2]]} center zIndexRange={[35, 25]} pointerEvents="none">
            <span className="s3-tag" data-testid="plan-tag" data-lever={k}>{describe(k, plan)}</span>
          </Html>
        );
      })}
    </>
  );
}

// The camera turns toward the object of the lever being changed (orbit view, planning only), then stays there.
const FOCUS_DIST = 16;
const HOME = { pos: [11.5, 25, -17.5] as [number, number, number], look: [0.4, 0, 3.4] as [number, number, number] }; // = CAMERA_POSES.orbit
export function FocusCam({ focus }: { focus: keyof Plan | null }) {
  const { camera, controls } = useThree() as unknown as { camera: THREE.PerspectiveCamera; controls: { target: THREE.Vector3; update: () => void } | null };
  const goal = useRef<{ target: THREE.Vector3; pos: THREE.Vector3; t0: number; from: [THREE.Vector3, THREE.Vector3] } | null>(null);
  const wasFocused = useRef(false);
  useEffect(() => {
    if (!controls) return;
    if (!focus && wasFocused.current) {
      // back to the diorama view when planning ends
      wasFocused.current = false;
      goal.current = { target: new THREE.Vector3(...HOME.look), pos: new THREE.Vector3(...HOME.pos), t0: performance.now(), from: [controls.target.clone(), camera.position.clone()] };
      return;
    }
    if (!focus || !PING_AT[focus]) return;
    wasFocused.current = true;
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const [x, y, z] = PING_AT[focus]!;
    const target = new THREE.Vector3(x, Math.min(1.2, y), z);
    const dir = camera.position.clone().sub(controls.target).normalize();
    const pos = target.clone().addScaledVector(dir, FOCUS_DIST);
    pos.y = Math.max(pos.y, 11);
    goal.current = { target, pos, t0: performance.now() - (reduced ? 10000 : 0), from: [controls.target.clone(), camera.position.clone()] };
  }, [focus, controls, camera]);
  useFrame(() => {
    const g = goal.current;
    if (!g || !controls) return;
    const f = Math.min(1, (performance.now() - g.t0) / 650);
    const e = 1 - Math.pow(1 - f, 3);
    controls.target.lerpVectors(g.from[0], g.target, e);
    camera.position.lerpVectors(g.from[1], g.pos, e);
    controls.update();
    if (f >= 1) goal.current = null;
  });
  return null;
}

// 원육 is visible in the store: a 숙성고 (dry-aging cabinet) for aged meat, stacked frozen boxes for imported.
export function GradeProps({ grade }: { grade: Plan["meat_grade"] }) {
  if (grade === "aged") {
    return (
      <group position={[ROOM.x0 + 0.55, 0, -2.7]}>
        <mesh position={[0, 1.0, 0]}><boxGeometry args={[0.8, 2.0, 1.1]} /><meshStandardMaterial color="#2a2d31" metalness={0.5} roughness={0.4} /></mesh>
        <mesh position={[0.41, 1.05, 0]}><boxGeometry args={[0.02, 1.6, 0.9]} /><meshStandardMaterial color="#ffd7c2" emissive="#ff8a66" emissiveIntensity={0.6} transparent opacity={0.85} /></mesh>
        {[0.55, 0.95, 1.35].map((y) => [-0.25, 0.05, 0.3].map((dz) => (
          <mesh key={`${y}-${dz}`} position={[0.2, y, dz]}><boxGeometry args={[0.22, 0.12, 0.2]} /><meshStandardMaterial color="#8e2f26" roughness={0.6} /></mesh>
        )))}
      </group>
    );
  }
  if (grade === "imported") {
    return (
      <group position={[ROOM.x0 + 0.6, 0, -2.6]}>
        {[0, 1, 2, 3].map((i) => (
          <mesh key={i} position={[0, 0.2 + i * 0.36, (i % 2) * 0.08]}><boxGeometry args={[0.7, 0.34, 0.9]} /><meshStandardMaterial color={i % 2 ? "#e7eef3" : "#d7e3ec"} roughness={0.8} /></mesh>
        ))}
        <mesh position={[0.36, 1.25, 0]} rotation={[0, Math.PI / 2, 0]}><planeGeometry args={[0.6, 0.18]} /><meshStandardMaterial color="#1d5fa8" /></mesh>
      </group>
    );
  }
  return null;
}

// In-night decisions: where each kind acts, and a label there for 40 minutes after the choice.
const MARK_AT: Record<string, [number, number, number]> = {
  walkin_group: [0, 2.3, ROOM.z1 + 0.8], staff_late: [COUNTER[0], 2.3, COUNTER[1] + 0.4], meat_low: [COUNTER[0] - 0.8, 2.3, COUNTER[1]],
  rain_burst: [4.5, 2.6, 5.3], blogger: [0, 2.3, ROOM.z1 + 0.8],
};
export function DecisionMarks({ marks, tRef }: { marks: { clock: number; kind: string; text: string }[]; tRef: React.RefObject<number> }) {
  const [live, setLive] = useState<typeof marks>([]);
  const sig = useRef("");
  useFrame(() => {
    const t = tRef.current ?? 0;
    const on = marks.filter((m) => t >= m.clock && t < m.clock + 40);
    const k = on.map((m) => m.clock + m.kind).join(",");
    if (k !== sig.current) { sig.current = k; setLive(on); }
  });
  return (
    <>
      {live.map((m) => (
        <Html key={m.clock + m.kind} position={MARK_AT[m.kind] ?? [0, 2.3, ROOM.z1]} center zIndexRange={[36, 26]} pointerEvents="none">
          <span className="s3-tag s3-choice" data-testid="decision-mark">{m.text}</span>
        </Html>
      ))}
    </>
  );
}

// Welcome tour (v2/Tour.tsx): a cinematic flight to each stop, then a white world callout at the object. The object
// lands in the left 60 % of the frame because the tour card sits on the right (UI-SPEC §3 camera framing rule).
export type TourShot = { stop: string; label: string | null };
const TOUR_POSES: Record<string, { pos: [number, number, number]; at: [number, number, number]; fov: number; call?: [number, number, number]; side?: boolean }> = {
  sign: { pos: [-3.6, 2.9, 11.6], at: [0, 2.6, 3.45], fov: 44, call: [0, 3.42, 3.6] },
  menu_board: { pos: [-3.1, 1.65, 1.75], at: [-6.9, 1.62, -0.2], fov: 46, call: [-6.86, 2.06, -0.72], side: true }, // the 삼겹살 row's price
  tables: { pos: [3.5, 2.35, 3.15], at: [0, 0.8, 1.0], fov: 50, call: [0, 0.82, 1.35] },
  fridge: { pos: [3.7, 1.55, -0.55], at: [5.0, 1.0, -4.2], fov: 48, call: [5.0, 1.64, -3.9] }, // soju shelves and 원육 trays
  grill: { pos: [1.15, 1.55, 3.0], at: [0, 0.78, 1.35], fov: 46, call: [0, 0.82, 1.35] }, // the meat on a table's grill
  staff: { pos: [-3.8, 1.75, 0.6], at: [-3.8, 1.1, -3.6], fov: 48, call: [-3.8, 1.55, -3.5] }, // servers and the owner at the counter
  room: { pos: [-9.6, 8.6, 13.8], at: [0.4, 0.4, -0.4], fov: 44 }, // the pull-back over the whole store
};
const SHIFT = 0.22; // look-at moved right by this share of the distance: the object sits left of centre
const easeInOut = (x: number) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2); // ~ cubic-bezier(0.65, 0, 0.35, 1)

export type TourPose = { pos: [number, number, number]; at: [number, number, number]; fov: number; call?: [number, number, number]; side?: boolean };
export function TourCam({ shot, home, ms = 1400, override }: { shot: TourShot | null; home: { pos: [number, number, number]; look: [number, number, number]; fov: number };
  ms?: number; override?: TourPose | null }) {
  const { camera, controls } = useThree() as unknown as { camera: THREE.PerspectiveCamera; controls: { target: THREE.Vector3; update: () => void } | null };
  const fly = useRef<{ from: [THREE.Vector3, THREE.Vector3, number]; to: [THREE.Vector3, THREE.Vector3, number]; t0: number; dur: number; lift: number } | null>(null);
  const was = useRef(false);
  const homeRef = useRef(home);
  homeRef.current = home;
  const overrideRef = useRef(override);
  overrideRef.current = override;
  const stop = shot?.stop ?? null;
  // keyed on the stop only: a new label (guess, then reveal) or a re-render never restarts the flight
  useEffect(() => {
    const home = homeRef.current;
    if (!controls) return;
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    let to: [THREE.Vector3, THREE.Vector3, number];
    const p = (stop && (overrideRef.current ?? TOUR_POSES[stop])) || null;
    if (stop && p) {
      was.current = true;
      const pos = new THREE.Vector3(...p.pos), at = new THREE.Vector3(...p.at);
      const fwd = at.clone().sub(pos);
      const right = new THREE.Vector3().crossVectors(fwd, new THREE.Vector3(0, 1, 0)).normalize();
      to = [pos, at.addScaledVector(right, fwd.length() * SHIFT), p.fov];
    } else if (!stop && was.current) {
      was.current = false; // the tour ended: back to the diorama view the planning board uses
      to = [new THREE.Vector3(...home.pos), new THREE.Vector3(...home.look), home.fov];
    } else return;
    const from: [THREE.Vector3, THREE.Vector3, number] = [camera.position.clone(), controls.target.clone(), camera.fov];
    const dist = from[0].distanceTo(to[0]);
    fly.current = { from, to, t0: performance.now(), dur: reduced ? 0 : ms, lift: Math.min(3.5, dist * 0.18) };
  }, [stop, controls, camera, ms]);
  useFrame(() => {
    const f0 = fly.current;
    if (!f0 || !controls) return;
    const f = f0.dur ? Math.min(1, (performance.now() - f0.t0) / f0.dur) : 1;
    const e = easeInOut(f);
    camera.position.lerpVectors(f0.from[0], f0.to[0], e);
    camera.position.y += Math.sin(Math.PI * e) * f0.lift; // a shallow arc instead of a straight dolly through walls
    controls.target.lerpVectors(f0.from[1], f0.to[1], e);
    camera.fov = f0.from[2] + (f0.to[2] - f0.from[2]) * e;
    camera.updateProjectionMatrix();
    controls.update();
    if (f >= 1) fly.current = null;
  });
  const p = stop ? override ?? TOUR_POSES[stop] : undefined;
  if (!p?.call || !shot?.label) return null;
  return (
    <Html position={p.call} zIndexRange={[38, 28]} pointerEvents="none">
      <span className={`s3-callout ${p.side ? "side" : ""}`} data-testid="tour-callout"><i /><b>{shot.label}</b></span>
    </Html>
  );
}
