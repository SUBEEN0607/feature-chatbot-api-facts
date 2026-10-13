// The v2 store: one simulated night (EVENT_LOG + bubbles) drawn so that the plan and the month's events are
// visible. Prices on the menu board and window poster come from the plan; staff count = plan.staff (+ the
// owner, who wears the red apron and headband); meat on the grills and soju bottles accumulate per table from
// the order events; smoke rises while meat cooks; a queue forms outside; rain/snow, the 야장 with string
// lights, and the competitor across the street follow the month's events. Lighting runs dusk to neon night.
import { useEffect, useMemo, useRef, useState } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { Html, OrbitControls, PointerLockControls } from "@react-three/drei";
import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import type { Hero } from "../data";
import { COUNTER, DOOR_OUT, ROOM, buildTables, queueSpot, staffHome, type TableSpot, type V2 } from "../replay/layout";
import { makePoser, occupiedTables, parties, queueOrder, type Party } from "../replay/timeline";
import type { NightV2, Plan, Weather } from "../v2/types";
import { Box, Building, type Env } from "./Building";
import { Figures, hash, type FigPose } from "./Figures";
import { cardSign, grate, softDot } from "./textures";
import { ChangePings, DecisionMarks, FocusCam, GradeProps, PlanTags, TableHotspots, TourCam, useInfo, type TourPose, type TourShot } from "./Interact";
import { leverValueLabel, LEVERS } from "../v2/levers";

const describeLever = (k: keyof Plan, p: Plan) => { const l = LEVERS.find((x) => x.key === k); return l ? `${l.label} ${leverValueLabel(l, p[k])}` : String(k); };

export type CamMode = "orbit" | "fps" | "street";

export const SEG_PALETTE: Record<string, { shirts: string[]; pants: string[] }> = {
  twenties: { shirts: ["#e0735a", "#ec8a4f", "#d4584a", "#f0a07a"], pants: ["#3d4f6b", "#6a7fa0", "#2e2f33", "#8b7d6b"] },
  office: { shirts: ["#43648a", "#35506f", "#5679a3", "#2e4560"], pants: ["#2f3338", "#3a3f45", "#24272b"] },
  family: { shirts: ["#d4a032", "#c99227", "#e3b552", "#b98a2a"], pants: ["#6b5d48", "#4f4a42", "#7a6a52"] },
};
const SKINS = ["#f1d3b8", "#e8c4a2", "#d9b08c", "#f3dcc6"];
const HAIRS = ["#1f1a17", "#2b211c", "#3b2c22", "#141210", "#5a4232"];
const UMBRELLAS = ["#2f3a4a", "#c7452f", "#e8e3d7", "#35614a", "#1d1d1f"];
export const STAFF_SHIRT = "#1f6b4e";


// sunset clock (minutes) by calendar month, 서울 approx.; used only for lighting
const SUNSET: Record<number, number> = { 10: 17 * 60 + 50, 11: 17 * 60 + 20, 12: 17 * 60 + 15, 1: 17 * 60 + 35, 2: 18 * 60 + 5, 3: 18 * 60 + 30 };

const smooth = (a: number, b: number, x: number) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};

// ---------- table state from the event log -------------------------------------------------------------
type Seating = { party: number; seat: number; leave: number; ready: number; orders: { t: number; portions: number; bottles: number }[] };

function tableSeatings(night: NightV2): Map<string, Seating[]> {
  const out = new Map<string, Seating[]>();
  const open = new Map<number, Seating>();
  const lastLeft = new Map<string, Seating>();
  for (const e of night.events) {
    const tid = e.table_id;
    if (e.type === "seat" && tid && e.party != null) {
      const s: Seating = { party: e.party, seat: e.t, leave: Infinity, ready: Infinity, orders: [] };
      open.set(e.party, s);
      for (const id of e.tables ?? [tid]) {
        if (!out.has(id)) out.set(id, []);
        out.get(id)!.push(s);
      }
    } else if (e.type === "order" && e.party != null) {
      open.get(e.party)?.orders.push({ t: e.t, portions: e.portions ?? 0, bottles: e.bottles ?? 0 });
    } else if (e.type === "leave" && e.party != null && tid) {
      const s = open.get(e.party);
      if (s) {
        s.leave = e.t;
        lastLeft.set(tid, s);
      }
    } else if (e.type === "table_ready" && tid) {
      const s = lastLeft.get(tid);
      if (s) s.ready = e.t;
    }
  }
  for (const list of out.values()) for (const s of list) if (!Number.isFinite(s.ready)) s.ready = s.leave + 4;
  return out;
}

const activeSeating = (list: Seating[] | undefined, t: number) => list?.find((s) => s.seat <= t && t < s.ready);

// ---------- tables, food, bottles, smoke ----------------------------------------------------------------
const RAW = new THREE.Color("#e9a19a");
const COOKED = new THREE.Color("#9a5530");
const AGED_RAW = new THREE.Color("#b8564c");
const FULL = new THREE.Color("#2f8f5b");
const EMPTY = new THREE.Color("#a9d7bb");
const DISHES = ["#c8402e", "#4f8a3a", "#e8d38a", "#f1ece2", "#8a5a33", "#c8402e", "#6aa04a", "#d9a441"].map((c) => new THREE.Color(c));
const MAXM = 6, MAXB = 10, MAXD = 8;
const ZERO = new THREE.Matrix4().makeScale(0, 0, 0);

function ReservedCard() {
  const tex = useMemo(() => cardSign("예약석", "#f7f3ea", "#7d1f16"), []);
  return (
    <group>
      <mesh position={[0, 0.84, 0]} rotation={[0, 0, 0]}>
        <planeGeometry args={[0.26, 0.13]} />
        <meshStandardMaterial map={tex} side={THREE.DoubleSide} />
      </mesh>
    </group>
  );
}

function TableMeshes({ spot }: { spot: TableSpot }) {
  const top = spot.terrace ? "#ece7dc" : "#b9bfc4";
  return (
    <group>
      <Box p={[spot.x, 0.7, spot.z]} s={[1.3, 0.05, 0.8]} color={top} metal={spot.terrace ? 0 : 0.6} rough={spot.terrace ? 0.9 : 0.3} cast />
      <Box p={[spot.x, 0.34, spot.z]} s={[0.1, 0.68, 0.1]} color="#6b7075" metal={0.4} />
      <Box p={[spot.x, 0.02, spot.z]} s={[0.6, 0.03, 0.4]} color="#6b7075" metal={0.4} />
      <mesh position={[spot.x, 0.745, spot.z]}>
        <cylinderGeometry args={[0.24, 0.22, 0.06, 18]} />
        <meshStandardMaterial color="#26282a" roughness={0.5} metalness={0.4} />
      </mesh>
      {spot.seats.map(([x, z], i) => {
        const zz = z + (z > spot.z ? 0.12 : -0.12);
        return (
          <mesh key={i} position={[x, 0.225, zz]} castShadow>
            <cylinderGeometry args={[0.16, 0.18, 0.45, 10]} />
            <meshStandardMaterial color={spot.terrace ? "#d2452f" : "#6d5140"} roughness={0.7} />
          </mesh>
        );
      })}
    </group>
  );
}

function TableLife({ spots, seatings, plan, tRef, planning = false }: { spots: TableSpot[]; seatings: Map<string, Seating[]>; plan: Plan; tRef: React.RefObject<number>; planning?: boolean }) {
  const meat = useRef<THREE.InstancedMesh>(null);
  const bottles = useRef<THREE.InstancedMesh>(null);
  const dishes = useRef<THREE.InstancedMesh>(null);
  const embers = useRef<THREE.InstancedMesh>(null);
  const smokeRefs = useRef<(THREE.Points<THREE.BufferGeometry> | null)[]>([]);
  const smokeTex = useMemo(() => softDot("rgba(235,235,235,0.9)"), []);
  const grateTex = useMemo(grate, []);
  const smokeGeos = useMemo(() => spots.map(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(14 * 3), 3));
    return g;
  }), [spots]);
  // 단체 예약: the last indoor table holds a 예약석 card whenever it is empty (the walk-ins it blocks)
  const reserved = [...spots].reverse().find((s) => !s.terrace);
  const reservedRef = useRef<THREE.Group>(null);
  const thick = plan.menu_extras.includes("tongsam") || plan.meat_grade === "aged";
  const thin = plan.menu_extras.includes("naengsam") && !thick;
  const raw = plan.meat_grade === "aged" ? AGED_RAW : RAW;
  const m4 = useMemo(() => new THREE.Matrix4(), []);
  const col = useMemo(() => new THREE.Color(), []);
  const q = useMemo(() => new THREE.Quaternion(), []);
  const v = useMemo(() => new THREE.Vector3(), []);
  const sc = useMemo(() => new THREE.Vector3(), []);

  useFrame((state) => {
    const t = tRef.current ?? 0;
    const clock = state.clock.elapsedTime;
    if (!meat.current || !bottles.current || !dishes.current || !embers.current) return;
    if (reservedRef.current && reserved) reservedRef.current.visible = !activeSeating(seatings.get(reserved.id), t);
    spots.forEach((spot, ti) => {
      const s = activeSeating(seatings.get(spot.id), t);
      const eating = s && t < s.leave;
      const first = s?.orders[0];
      const last = s ? [...s.orders].reverse().find((o) => o.t <= t) : undefined;
      // embers glow while a party sits
      m4.compose(v.set(spot.x, 0.779, spot.z), q.identity(), sc.set(eating && first && t >= first.t ? 1 : 0.0001, 1, eating && first && t >= first.t ? 1 : 0.0001));
      embers.current!.setMatrixAt(ti, m4);
      // meat strips on the grill: the latest order, raw to browned over 10 min, eaten from minute 14
      let strips = 0, cook = 0;
      if (eating && last) {
        const age = t - last.t;
        const n = Math.min(MAXM, last.portions + 1);
        strips = Math.round(n * (1 - Math.min(1, Math.max(0, (age - 14) / 18))));
        if (strips < 1 && age < 40) strips = 1;
        cook = Math.min(1, age / 10);
      }
      for (let k = 0; k < MAXM; k++) {
        const idx = ti * MAXM + k;
        if (k < strips) {
          const dx = (k % 3 - 1) * 0.12, dz = (Math.floor(k / 3) - 0.5) * 0.16;
          q.setFromAxisAngle(v.set(0, 1, 0), 0.2 + (k % 2) * 0.15);
          m4.compose(v.set(spot.x + dx, 0.79, spot.z + dz), q, sc.set(thin ? 0.08 : 0.1, thick ? 0.045 : thin ? 0.016 : 0.028, thin ? 0.22 : 0.19));
          meat.current!.setMatrixAt(idx, m4);
          meat.current!.setColorAt(idx, col.copy(raw).lerp(COOKED, cook));
        } else meat.current!.setMatrixAt(idx, ZERO);
      }
      // soju bottles: every bottle ordered so far stays on the table until it is cleared; empties go pale
      const placed: number[] = [];
      if (s) for (const o of s.orders) if (o.t <= t) for (let b = 0; b < o.bottles; b++) placed.push(o.t);
      for (let k = 0; k < MAXB; k++) {
        const idx = ti * MAXB + k;
        if (k < placed.length) {
          const side = k % 2 ? 1 : -1;
          const along = Math.floor(k / 2);
          m4.compose(v.set(spot.x + side * (0.42 + (along % 2) * 0.1), 0.84, spot.z + (along - 2) * 0.12), q.identity(), sc.set(1, 1, 1));
          bottles.current!.setMatrixAt(idx, m4);
          bottles.current!.setColorAt(idx, t - placed[k] > 22 || (s && t >= s.leave) ? EMPTY : FULL);
        } else bottles.current!.setMatrixAt(idx, ZERO);
      }
      // 반찬 dishes from the first order until the table is cleared; count = plan.banchan
      // while planning, every table is set with the plan's 반찬 so the lever is visible on all of them
      const showD = (s && first && t >= first.t) || planning ? Math.min(MAXD, plan.banchan) : 0;
      for (let k = 0; k < MAXD; k++) {
        const idx = ti * MAXD + k;
        if (k < showD) {
          const a = (k / Math.max(1, showD)) * Math.PI * 2;
          m4.compose(v.set(spot.x + Math.cos(a) * 0.4, 0.735, spot.z + Math.sin(a) * 0.26), q.identity(), sc.set(1, 1, 1));
          dishes.current!.setMatrixAt(idx, m4);
          dishes.current!.setColorAt(idx, plan.menu_extras.includes("minari") && k === 1 ? DISHES[6] : DISHES[k % DISHES.length]);
        } else dishes.current!.setMatrixAt(idx, ZERO);
      }
      // smoke while meat is on the grill
      const pts = smokeRefs.current[ti];
      if (pts) {
        pts.visible = strips > 0;
        if (strips > 0) {
          const arr = (pts.geometry.getAttribute("position") as THREE.BufferAttribute).array as Float32Array;
          const top = spot.terrace ? 2.3 : 1.5;
          for (let k = 0; k < 14; k++) {
            const f = (clock * 0.35 + hash(k + ti * 31)) % 1;
            arr[k * 3] = spot.x + Math.sin(clock * 1.7 + k) * 0.08 * (1 + f * 2) + (spot.terrace ? f * 0.3 : 0);
            arr[k * 3 + 1] = 0.82 + f * (top - 0.82);
            arr[k * 3 + 2] = spot.z + Math.cos(clock * 1.3 + k * 1.7) * 0.08 * (1 + f * 2);
          }
          pts.geometry.getAttribute("position").needsUpdate = true;
          (pts.material as THREE.PointsMaterial).opacity = 0.16 + 0.05 * strips;
        }
      }
    });
    for (const m of [meat.current, bottles.current, dishes.current, embers.current]) {
      m.instanceMatrix.needsUpdate = true;
      if (m.instanceColor) m.instanceColor.needsUpdate = true;
    }
  });
  const init = (n: number) => (m: THREE.InstancedMesh | null) => {
    if (!m) return;
    for (let i = 0; i < n; i++) {
      m.setMatrixAt(i, ZERO);
      m.setColorAt(i, new THREE.Color("#ffffff"));
    }
    m.frustumCulled = false;
  };
  const N = spots.length;
  return (
    <group>
      {spots.map((s) => <TableMeshes key={s.id} spot={s} />)}
      {plan.group_reservations && reserved && <group ref={reservedRef} position={[reserved.x + 0.45, 0, reserved.z - 0.2]}><ReservedCard /></group>}
      {plan.group_reservations && reserved && [[-1, -0.22], [-1, 0.22], [1, -0.22], [1, 0.22]].map(([sx, dz], i) => (
        <mesh key={i} position={[reserved.x + sx * 1.0, 0.225, reserved.z + dz]} castShadow>
          <cylinderGeometry args={[0.16, 0.18, 0.45, 10]} />
          <meshStandardMaterial color="#6d5140" roughness={0.7} />
        </mesh>
      ))}
      <instancedMesh ref={(m) => { meat.current = m; init(N * MAXM)(m); }} args={[undefined, undefined, N * MAXM]}>
        <boxGeometry args={[1, 1, 1]} />
        <meshStandardMaterial roughness={0.6} />
      </instancedMesh>
      <instancedMesh ref={(m) => { bottles.current = m; init(N * MAXB)(m); }} args={[undefined, undefined, N * MAXB]}>
        <cylinderGeometry args={[0.035, 0.04, 0.22, 7]} />
        <meshStandardMaterial roughness={0.25} />
      </instancedMesh>
      <instancedMesh ref={(m) => { dishes.current = m; init(N * MAXD)(m); }} args={[undefined, undefined, N * MAXD]}>
        <cylinderGeometry args={[0.065, 0.05, 0.035, 10]} />
        <meshStandardMaterial roughness={0.5} />
      </instancedMesh>
      <instancedMesh ref={(m) => { embers.current = m; init(N)(m); }} args={[undefined, undefined, N]}>
        <cylinderGeometry args={[0.21, 0.21, 0.01, 18]} />
        <meshStandardMaterial color="#ffffff" map={grateTex} emissive="#ffffff" emissiveMap={grateTex} emissiveIntensity={0.8} />
      </instancedMesh>
      {spots.map((s, i) => (
        <points key={s.id} ref={(p) => { smokeRefs.current[i] = p as THREE.Points<THREE.BufferGeometry> | null; }} geometry={smokeGeos[i]} visible={false} frustumCulled={false}>
          <pointsMaterial map={smokeTex} size={0.42} transparent opacity={0.3} depthWrite={false} color="#e9e6e2" sizeAttenuation />
        </points>
      ))}
    </group>
  );
}

// ---------- 야장 string lights, stacked stools when the terrace is closed ------------------------------
function Terrace({ env, open }: { env: React.RefObject<Env>; open: boolean }) {
  const bulbMat = useMemo(() => new THREE.MeshStandardMaterial({ color: "#fff1c9", emissive: "#ffcf73", emissiveIntensity: 0.4 }), []);
  useEffect(() => {
    const g = { mat: bulbMat, day: 0.3, night: 3.2 };
    env.current?.glows.push(g);
    return () => { if (env.current) env.current.glows = env.current.glows.filter((x) => x !== g); };
  }, [env, bulbMat]);
  const wires = useMemo(() => {
    const z1 = ROOM.z1;
    const lines: [THREE.Vector3, THREE.Vector3][] = [
      [new THREE.Vector3(2.0, 2.3, z1 + 0.1), new THREE.Vector3(2.2, 2.55, 7.3)],
      [new THREE.Vector3(4.6, 2.3, z1 + 0.1), new THREE.Vector3(4.6, 2.55, 7.3)],
      [new THREE.Vector3(7.0, 2.3, z1 + 0.1), new THREE.Vector3(7.0, 2.55, 7.3)],
      [new THREE.Vector3(2.2, 2.55, 7.3), new THREE.Vector3(7.0, 2.55, 7.3)],
    ];
    return lines.map(([a, b]) => {
      const pts: THREE.Vector3[] = [];
      for (let i = 0; i <= 12; i++) {
        const f = i / 12;
        pts.push(new THREE.Vector3().lerpVectors(a, b, f).add(new THREE.Vector3(0, -Math.sin(Math.PI * f) * 0.28, 0)));
      }
      return pts;
    });
  }, []);
  const bulbs = useMemo(() => wires.flatMap((pts) => pts.filter((_, i) => i % 2 === 1)), [wires]);
  if (!open) {
    return (
      <group>
        {[0, 1].map((st) => Array.from({ length: 5 }, (_, i) => (
          <mesh key={`${st}-${i}`} position={[5.6 + st * 0.5, 0.2 + i * 0.12, ROOM.z1 + 0.35]}>
            <cylinderGeometry args={[0.17, 0.19, 0.4, 10, 1, true]} />
            <meshStandardMaterial color="#d2452f" side={THREE.DoubleSide} />
          </mesh>
        )))}
        <Box p={[6.6, 0.45, ROOM.z1 + 0.25]} s={[0.05, 0.9, 0.8]} color="#ece7dc" />
      </group>
    );
  }
  return (
    <group>
      {[2.2, 7.0].map((x) => (
        <mesh key={x} position={[x, 1.28, 7.3]}>
          <cylinderGeometry args={[0.035, 0.04, 2.56, 6]} />
          <meshStandardMaterial color="#3d3a36" />
        </mesh>
      ))}
      {wires.map((pts, i) => (
        <line key={i}>
          <bufferGeometry attach="geometry" onUpdate={(g) => g.setFromPoints(pts)} />
          <lineBasicMaterial color="#2a2724" />
        </line>
      ))}
      {bulbs.map((p, i) => (
        <mesh key={i} position={p} material={bulbMat}>
          <sphereGeometry args={[0.045, 6, 5]} />
        </mesh>
      ))}
    </group>
  );
}

// ---------- weather -------------------------------------------------------------------------------------
function Precip({ kind }: { kind: Weather }) {
  const N = kind === "rain" ? 1600 : 1100;
  const seeds = useMemo(() => Array.from({ length: N }, (_, i) => [hash(i * 3 + 1), hash(i * 3 + 2), hash(i * 3 + 3)]), [N]);
  const geo = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(N * (kind === "rain" ? 6 : 3)), 3));
    return g;
  }, [N, kind]);
  const dot = useMemo(() => softDot("#ffffff"), []);
  useFrame((state) => {
    const clock = state.clock.elapsedTime;
    const arr = (geo.getAttribute("position") as THREE.BufferAttribute).array as Float32Array;
    for (let i = 0; i < N; i++) {
      const [a, b, c] = seeds[i];
      const x = -22 + a * 44;
      const z = ROOM.z1 + 0.3 + b * 16;
      const H = 11;
      if (kind === "rain") {
        const y = H - ((clock * 13 + c * H) % H);
        arr.set([x, y, z, x + 0.03, y + 0.38, z + 0.02], i * 6);
      } else {
        const y = H - ((clock * 0.9 + c * H) % H);
        arr.set([x + Math.sin(clock * 0.8 + i) * 0.3, y, z + Math.cos(clock * 0.6 + i) * 0.2], i * 3);
      }
    }
    geo.getAttribute("position").needsUpdate = true;
  });
  if (kind === "rain") {
    return (
      <lineSegments geometry={geo} frustumCulled={false}>
        <lineBasicMaterial color="#c9d8e6" transparent opacity={0.55} />
      </lineSegments>
    );
  }
  return (
    <points geometry={geo} frustumCulled={false}>
      <pointsMaterial map={dot} color="#ffffff" size={0.12} transparent depthWrite={false} sizeAttenuation />
    </points>
  );
}

// ---------- lighting: dusk to neon night ----------------------------------------------------------------
const SKY = [
  [-90, "#cfdbe6"], [-20, "#f0cba6"], [10, "#e3a487"], [35, "#6b77a0"], [70, "#3a4675"], [120, "#2f3a66"],
] as const;
function skyAt(min: number, out: THREE.Color) {
  if (min <= SKY[0][0]) return out.set(SKY[0][1]);
  for (let i = 1; i < SKY.length; i++) {
    if (min <= SKY[i][0]) {
      const f = (min - SKY[i - 1][0]) / (SKY[i][0] - SKY[i - 1][0]);
      return out.set(SKY[i - 1][1]).lerp(new THREE.Color(SKY[i][1]), f);
    }
  }
  return out.set(SKY[SKY.length - 1][1]);
}

function Lighting({ env, tRef, monthNum, weather }: { env: React.RefObject<Env>; tRef: React.RefObject<number>; monthNum: number; weather: Weather }) {
  const { scene } = useThree();
  const hemi = useRef<THREE.HemisphereLight>(null);
  const sun = useRef<THREE.DirectionalLight>(null);
  const street = useRef<THREE.PointLight[]>([]);
  const neon = useRef<THREE.PointLight>(null);
  const sky = useMemo(() => new THREE.Color(), []);
  const { gl } = useThree();
  useEffect(() => {
    const pm = new THREE.PMREMGenerator(gl);
    const envTex = pm.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environment = envTex;
    scene.environmentIntensity = 0.45;
    return () => { scene.environment = null; envTex.dispose(); pm.dispose(); };
  }, [gl, scene]);
  useEffect(() => {
    scene.background = new THREE.Color("#cfdbe6");
    scene.fog = new THREE.Fog("#cfdbe6", 38, 95);
    return () => { scene.background = null; scene.fog = null; };
  }, [scene]);
  useFrame(() => {
    const clockMin = 17 * 60 + (tRef.current ?? 0);
    const rel = clockMin - (SUNSET[monthNum] ?? SUNSET[10]);
    const night = smooth(-20, 70, rel);
    if (env.current) env.current.night = night;
    skyAt(rel, sky);
    if (weather !== "clear") sky.lerp(new THREE.Color(weather === "snow" ? "#9aa3b3" : "#55606e"), 0.35 * (1 - night * 0.5));
    (scene.background as THREE.Color).copy(sky);
    (scene.fog as THREE.Fog).color.copy(sky);
    scene.environmentIntensity = 0.45 - night * 0.3;
    if (hemi.current) {
      hemi.current.intensity = 1.25 - night * 0.75;
      hemi.current.color.set(night > 0.5 ? "#9fb0d8" : "#ffffff");
    }
    if (sun.current) {
      sun.current.intensity = (weather === "clear" ? 1.7 : 0.8) * (1 - night * 0.85);
      sun.current.color.set(rel > -40 && night < 0.6 ? "#ffc58f" : night >= 0.6 ? "#9db2ff" : "#ffffff");
      const elev = Math.max(0.15, 1 - smooth(-120, 0, rel) * 0.85);
      sun.current.position.set(-14, 22 * elev, 10);
    }
    for (const l of street.current) if (l) l.intensity = night * 40;
    if (neon.current) neon.current.intensity = night * 14;
    for (const g of env.current?.glows ?? []) g.mat.emissiveIntensity = g.day + (g.night - g.day) * night;
  });
  return (
    <>
      <hemisphereLight ref={hemi} args={["#ffffff", "#bfb4a3", 1.2]} />
      <directionalLight ref={sun} position={[-14, 20, 10]} intensity={1.6} castShadow shadow-mapSize={[1024, 1024]}
        shadow-camera-left={-16} shadow-camera-right={16} shadow-camera-top={14} shadow-camera-bottom={-14} shadow-bias={-0.0005} />
      {/* interior: warm ceiling light, always on */}
      {[-4.2, 0, 4.2].map((x) => <pointLight key={x} position={[x, 2.45, -0.3]} intensity={9} distance={9} decay={1.6} color="#ffe2b8" />)}
      {[-11, 11].map((x, i) => <pointLight key={x} ref={(l) => { if (l) street.current[i] = l; }} position={[x, 4.8, 8.4]} intensity={0} distance={14} decay={1.8} color="#ffd59a" />)}
      <pointLight ref={neon} position={[0, 2.6, ROOM.z1 + 1.4]} intensity={0} distance={7} decay={1.8} color="#ff6a50" />
    </>
  );
}

// ---------- people --------------------------------------------------------------------------------------
function Customers({ list, tables, tRef, weather }: { list: Party[]; tables: Map<string, TableSpot>; tRef: React.RefObject<number>; weather: Weather }) {
  const pose = useMemo(() => makePoser(tables), [tables]);
  const figs = useMemo(() => list.flatMap((p) => Array.from({ length: p.size }, (_, k) => {
    const pal = SEG_PALETTE[p.segment] ?? SEG_PALETTE.twenties;
    const r = (o: number) => hash(p.id * 7 + k * 13 + o);
    return {
      p, k,
      shirt: new THREE.Color(pal.shirts[Math.floor(r(1) * pal.shirts.length)]),
      pants: new THREE.Color(pal.pants[Math.floor(r(2) * pal.pants.length)]),
      skin: new THREE.Color(SKINS[Math.floor(r(3) * SKINS.length)]),
      hair: new THREE.Color(HAIRS[Math.floor(r(4) * HAIRS.length)]),
      umbrella: new THREE.Color(UMBRELLAS[Math.floor(r(5) * UMBRELLAS.length)]),
      scale: (p.segment === "family" && k >= 2 ? 0.78 : 0.94) + r(6) * 0.1,
      prev: [NaN, NaN] as [number, number],
      heading: 0,
    };
  })), [list]);
  const order = useRef<Map<number, number>>(new Map());
  const lastT = useRef(-1);
  const grey = useMemo(() => new THREE.Color("#a9abad"), []);
  const poseAt = (i: number, out: FigPose, clock: number) => {
    const t = tRef.current ?? 0;
    if (i === 0 && t !== lastT.current) {
      order.current = queueOrder(list, t);
      lastT.current = t;
    }
    const f = figs[i];
    const ps = pose(f.p, f.k, t, order.current.get(f.p.id) ?? 0);
    out.visible = ps.visible;
    if (!ps.visible) return;
    out.x = ps.x;
    out.z = ps.z;
    out.seated = ps.seated;
    const dx = ps.x - f.prev[0], dz = ps.z - f.prev[1];
    const moving = Number.isFinite(dx) && Math.hypot(dx, dz) > 1e-4;
    if (moving) f.heading = Math.atan2(dx, dz);
    else if (ps.seated && f.p.table) {
      const tb = tables.get(f.p.table);
      if (tb) f.heading = Math.atan2(tb.x - ps.x, tb.z - ps.z);
    } else if (!ps.seated) f.heading = Math.atan2(DOOR_OUT[0] - ps.x, DOOR_OUT[1] + 0.2 - ps.z);
    f.prev = [ps.x, ps.z];
    out.heading = f.heading;
    out.walk = moving ? clock * 9 + f.k : NaN;
    out.scale = f.scale;
    out.shirt = ps.faded ? grey : f.shirt;
    out.pants = f.pants;
    out.skin = f.skin;
    out.hair = f.hair;
    out.apron = null;
    out.umbrella = weather === "rain" && !ps.seated && ps.z > ROOM.z1 + 0.2 ? f.umbrella : null;
    out.armsUp = ps.seated ? 0.55 + 0.25 * Math.sin(clock * 1.3 + f.k + f.p.id) : 0;
  };
  return <Figures count={figs.length} poseAt={poseAt} />;
}

type Task = { start: number; end: number; at: V2 };
function staffLanes(night: NightV2, tables: Map<string, TableSpot>, lanes: number) {
  const tasks: Task[] = [];
  for (const e of night.events) {
    const tbl = e.table_id ? tables.get(e.table_id) : undefined;
    if (!tbl) continue;
    if (e.type === "order") tasks.push({ start: e.t - (e.reorder ? 1.5 : 3), end: e.t, at: tbl.serve });
    if (e.type === "leave") tasks.push({ start: e.t - 2, end: e.t, at: tbl.serve });
    if (e.type === "table_ready") tasks.push({ start: e.t - 4, end: e.t, at: tbl.serve });
  }
  tasks.sort((a, b) => a.start - b.start);
  const out: Task[][] = Array.from({ length: lanes }, () => []);
  const freeAt = Array(lanes).fill(-Infinity);
  for (const task of tasks) {
    let k = freeAt.findIndex((f) => f <= task.start);
    if (k < 0) k = freeAt.indexOf(Math.min(...freeAt));
    const start = Math.max(task.start, freeAt[k]);
    const t2 = { start, end: start + (task.end - task.start), at: task.at };
    out[k].push(t2);
    freeAt[k] = t2.end;
  }
  return out;
}

function lerp2(a: V2, b: V2, f: number): V2 {
  return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f];
}

// Staff (green shirts, black aprons) and the owner (white shirt, red apron, slightly bigger). Every order,
// payment and clearing needs a server; tasks go to the first free lane. Back-to-back tasks are walked faster
// (the load is visible as hurrying).
function Crew({ night, tables, staff, tRef, grill, list }: { night: NightV2; tables: Map<string, TableSpot>; staff: number; tRef: React.RefObject<number>; grill: boolean; list: Party[] }) {
  const lanesN = staff + 1;
  const lanes = useMemo(() => staffLanes(night, tables, lanesN), [night, tables, lanesN]);
  const mem = useRef<{ prev: [number, number]; heading: number }[]>([]);
  while (mem.current.length < lanesN) mem.current.push({ prev: [NaN, NaN], heading: Math.PI });
  const cols = useMemo(() => ({
    staffShirt: new THREE.Color(STAFF_SHIRT), staffPants: new THREE.Color("#22252a"), staffApron: new THREE.Color("#1b1c1e"),
    ownerShirt: new THREE.Color("#f4f1ea"), ownerPants: new THREE.Color("#3a3f45"), ownerApron: new THREE.Color("#a3261b"),
    skin: new THREE.Color("#e8c4a2"), hair: new THREE.Color("#1f1a17"), ownerHair: new THREE.Color("#b3261b"),
  }), []);
  const poseAt = (i: number, out: FigPose, clock: number) => {
    const t = tRef.current ?? 0;
    const owner = i === lanesN - 1;
    const home: V2 = owner ? [COUNTER[0] - 0.8, COUNTER[1] - 0.5] : staffHome(i);
    let pos: V2 = home;
    let busy = false;
    for (const [j, task] of lanes[i].entries()) {
      const prevEnd = j > 0 ? lanes[i][j - 1].end : -Infinity;
      const travel = task.start - prevEnd < 1.5 ? 0.3 : 0.6;
      if (t >= task.start - travel && t < task.start) { pos = lerp2(j > 0 && task.start - prevEnd < travel * 2 ? lanes[i][j - 1].at : home, task.at, (t - (task.start - travel)) / travel); break; }
      if (t >= task.start && t < task.end) { pos = task.at; busy = true; break; }
      const next = lanes[i][j + 1];
      if (t >= task.end && t < task.end + travel && !(next && next.start - travel <= t)) { pos = lerp2(task.at, home, (t - task.end) / travel); break; }
    }
    // 직원이 구워주기: an idle server grills at an occupied table (a new table every 6 minutes)
    let grilling = false;
    if (grill && !owner && !busy && pos === home) {
      const occ = [...occupiedTables(list, t)].sort();
      if (occ.length) {
        const slot = Math.floor(t / 6);
        const tb = tables.get(occ[(slot + i * 3) % occ.length]);
        if (tb) {
          const spot: V2 = [tb.x - 0.95, tb.z];
          const f = Math.min(1, (t - slot * 6) / 0.5);
          pos = f < 1 ? lerp2(home, spot, f) : spot;
          grilling = f >= 1;
          busy = grilling;
        }
      }
    }
    const m = mem.current[i];
    const dx = pos[0] - m.prev[0], dz = pos[1] - m.prev[1];
    const moving = Number.isFinite(dx) && Math.hypot(dx, dz) > 1e-4;
    if (moving) m.heading = Math.atan2(dx, dz);
    else if (busy) {
      const tb = [...tables.values()].find((s) => (s.serve[0] === pos[0] || s.x - 0.95 === pos[0]) && s.serve[1] === pos[1]);
      if (tb) m.heading = Math.atan2(tb.x - pos[0], tb.z - pos[1]);
    } else m.heading = owner ? Math.PI : 0;
    m.prev = [pos[0], pos[1]];
    out.visible = true;
    out.x = pos[0];
    out.z = pos[1];
    out.heading = m.heading;
    out.seated = false;
    out.walk = moving ? clock * 12 + i : NaN;
    out.scale = owner ? 1.06 : 0.98;
    out.shirt = owner ? cols.ownerShirt : cols.staffShirt;
    out.pants = owner ? cols.ownerPants : cols.staffPants;
    out.apron = owner ? cols.ownerApron : cols.staffApron;
    out.skin = cols.skin;
    out.hair = owner ? cols.ownerHair : cols.hair;
    out.umbrella = null;
    out.armsUp = busy || (owner && !moving) ? 0.7 : 0;
  };
  return <Figures count={lanesN} poseAt={poseAt} />;
}

// Welcome tour, 인건비 stop: the first moment of the night when a server (not the owner) is busy at a back-row table,
// and a camera between the rows looking at them past their own table's hood (the night is held at that moment).
function serverAtWork(night: NightV2, tables: Map<string, TableSpot>, staff: number): { t: number; pose: TourPose } | null {
  if (staff < 1) return null;
  const lanes = staffLanes(night, tables, staff + 1).slice(0, staff);
  const indoor = new Set([...tables.values()].filter((s) => !s.terrace).map((s) => `${s.serve[0]},${s.serve[1]}`));
  const tasks = lanes.flat().filter((k) => indoor.has(`${k.at[0]},${k.at[1]}`) && k.end - k.start >= 2.5 && k.start >= 60 && k.end <= 330)
    .sort((a, b) => Number(a.at[1] > 0) - Number(b.at[1] > 0) || a.start - b.start);   // back row first, then earliest
  const k = tasks[0];
  if (!k) return null;
  const [x, z] = k.at;
  return { t: (k.start + k.end) / 2, pose: { pos: [x + 0.9, 2.05, Math.min(3.1, z + 2.9)], at: [x, 1.05, z], fov: 48, call: [x, 1.9, z] } };
}

// ---------- passers-by on the sidewalks: a few on a normal night, a crowd in a festival week -------------
function Passersby({ count, weather }: { count: number; weather: Weather }) {
  const people = useMemo(() => Array.from({ length: count }, (_, i) => {
    const r = (o: number) => hash(i * 11 + o + 900);
    const pal = SEG_PALETTE[["twenties", "office", "family"][Math.floor(r(1) * 3)]];
    return {
      dir: r(2) < 0.5 ? 1 : -1, z: r(3) < 0.55 ? 6.4 + r(4) * 1.1 : 14.9 + r(4) * 1.0, speed: 0.9 + r(5) * 0.5, off: r(6) * 50,
      shirt: new THREE.Color(pal.shirts[Math.floor(r(7) * pal.shirts.length)]), pants: new THREE.Color(pal.pants[Math.floor(r(8) * pal.pants.length)]),
      skin: new THREE.Color(SKINS[Math.floor(r(9) * SKINS.length)]), hair: new THREE.Color(HAIRS[Math.floor(r(10) * HAIRS.length)]),
      umbrella: new THREE.Color(UMBRELLAS[Math.floor(r(11) * UMBRELLAS.length)]),
    };
  }), [count]);
  const poseAt = (i: number, out: FigPose, clock: number) => {
    const p = people[i];
    const span = 50;
    const x = ((((clock * p.speed + p.off) % span) + span) % span) - span / 2;
    out.visible = true;
    out.x = p.dir * x;
    out.z = p.z;
    out.heading = p.dir > 0 ? Math.PI / 2 : -Math.PI / 2;
    out.seated = false;
    out.walk = clock * 8 + i;
    out.scale = 0.95;
    out.shirt = p.shirt;
    out.pants = p.pants;
    out.skin = p.skin;
    out.hair = p.hair;
    out.apron = null;
    out.umbrella = weather === "rain" ? p.umbrella : null;
    out.armsUp = 0;
  };
  return <Figures count={count} poseAt={poseAt} castShadow={false} />;
}

// ---------- speech bubbles and floating payments --------------------------------------------------------
type Float = { key: string; x: number; y: number; z: number; text: string; kind: "pay" | "balk" | "bubble" };

function Overlays({ night, list, tables, tRef }: { night: NightV2; list: Party[]; tables: Map<string, TableSpot>; tRef: React.RefObject<number> }) {
  const [live, setLive] = useState<Float[]>([]);
  const sig = useRef("");
  const byParty = useMemo(() => new Map(list.map((p) => [p.id, p])), [list]);
  const bubbles = useMemo(() => night.events.filter((e) => e.bubble), [night]);
  useFrame(() => {
    const t = tRef.current ?? 0;
    const out: Float[] = [];
    for (const p of list) {
      if (p.leave != null && p.table && t >= p.leave && t < p.leave + 2.5) {
        const tb = tables.get(p.table);
        if (tb) out.push({ key: `p${p.id}`, x: tb.x, y: 1.75, z: tb.z, text: `₩${Math.round(p.bill).toLocaleString("ko-KR")}`, kind: "pay" });
      }
      if (p.balk != null && p.seat == null && t >= p.balk && t < p.balk + 2) out.push({ key: `b${p.id}`, x: -3.2, y: 2.2, z: 4.8, text: p.closed ? "문 앞에서 돌려보냄" : "기다리다 돌아감", kind: "balk" });
    }
    const order = queueOrder(list, t);
    for (const [i, e] of bubbles.entries()) {
      if (!(t >= e.t && t < e.t + 7) || !e.bubble) continue;
      let x = 0, z = 5, y = 2.0;
      const p = e.party != null ? byParty.get(e.party) : undefined;
      const tid = e.table_id ?? p?.table ?? undefined;
      const tb = tid ? tables.get(tid) : undefined;
      if (tb && (p?.seat ?? Infinity) <= t) {
        x = tb.x - 0.3;
        z = tb.z;
        y = 1.55;
      } else if (p) {
        [x, z] = queueSpot(order.get(p.id) ?? 0);
        y = 2.1;
      }
      out.push({ key: `s${i}`, x, y, z, text: e.bubble.text, kind: "bubble" });
    }
    const s = out.map((o) => o.key).join(",");
    if (s !== sig.current) {
      sig.current = s;
      setLive(out);
    }
  });
  return (
    <>
      {live.map((o) => (
        <Html key={o.key} position={[o.x, o.y, o.z]} center zIndexRange={[20, 0]} pointerEvents="none">
          <span className={`s3-float s3-${o.kind}`}>{o.text}</span>
        </Html>
      ))}
    </>
  );
}

// ---------- cameras -------------------------------------------------------------------------------------
export const CAMERA_POSES: Record<CamMode, { pos: [number, number, number]; look: [number, number, number]; fov: number }> = {
  orbit: { pos: [11.5, 25, -17.5], look: [0.4, 0, 3.4], fov: 40 },
  fps: { pos: [0.35, 1.6, 3.15], look: [-1.6, 1.25, -3.6], fov: 68 }, // just inside the door, facing in
  street: { pos: [-6.0, 1.75, 13.6], look: [-0.6, 2.0, 3.4], fov: 52 },
};

type Rect = [number, number, number, number];
function colliders(spots: TableSpot[]): Rect[] {
  const { x0, x1, z0, z1 } = ROOM;
  const r: Rect[] = spots.map((s) => [s.x - 0.75, s.x + 0.75, s.z - 1.0, s.z + 1.0]);
  r.push([COUNTER[0] - 1.85, COUNTER[0] + 1.85, COUNTER[1] - 0.4, COUNTER[1] + 0.4], [4.15, 5.85, z0, z0 + 0.7]);
  r.push([x0 - 0.2, x0 + 0.1, z0, z1 + 0.1], [x1 - 0.1, x1 + 0.2, z0, z1 + 0.1], [x0, x1, z0 - 0.3, z0 + 0.08]);
  r.push([x0 - 0.2, -0.72, z1 - 0.1, z1 + 0.1], [0.72, x1 + 0.2, z1 - 0.1, z1 + 0.1]);
  r.push([-18, x0, z0 - 10, z1], [x1, 18, z0 - 10, z1]);
  return r;
}

function FirstPerson({ active, spots }: { active: boolean; spots: TableSpot[] }) {
  const keys = useRef<Record<string, boolean>>({});
  const { camera } = useThree();
  const rects = useMemo(() => colliders(spots), [spots]);
  useEffect(() => {
    const down = (e: KeyboardEvent) => { keys.current[e.code] = true; };
    const up = (e: KeyboardEvent) => { keys.current[e.code] = false; };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => { window.removeEventListener("keydown", down); window.removeEventListener("keyup", up); };
  }, []);
  useFrame((_, dt) => {
    if (!active) return;
    const k = keys.current;
    const turn = (k.ArrowLeft || k.KeyQ ? 1 : 0) - (k.ArrowRight || k.KeyE ? 1 : 0);
    if (turn) camera.rotateOnWorldAxis(new THREE.Vector3(0, 1, 0), turn * 1.6 * dt);
    const f = (k.KeyW || k.ArrowUp ? 1 : 0) - (k.KeyS || k.ArrowDown ? 1 : 0);
    const s = (k.KeyD ? 1 : 0) - (k.KeyA ? 1 : 0);
    camera.position.y = 1.6;
    if (!f && !s) return;
    const dir = new THREE.Vector3();
    camera.getWorldDirection(dir);
    dir.y = 0;
    dir.normalize();
    const right = new THREE.Vector3().crossVectors(dir, new THREE.Vector3(0, 1, 0));
    const step = new THREE.Vector3().addScaledVector(dir, f * 2.4 * dt).addScaledVector(right, s * 2.4 * dt);
    const R = 0.28;
    const hit = (x: number, z: number) => x < -16 || x > 16 || z < ROOM.z0 + R || z > 14 || rects.some(([a, b, c, d]) => x > a - R && x < b + R && z > c - R && z < d + R);
    const p = camera.position;
    if (!hit(p.x + step.x, p.z)) p.x += step.x;
    if (!hit(p.x, p.z + step.z)) p.z += step.z;
  });
  return active ? <PointerLockControls selector="#s3-canvas" /> : null;
}

function CameraRig({ mode }: { mode: CamMode }) {
  const { camera, size } = useThree();
  const portrait = size.width < size.height;
  useEffect(() => {
    const p = CAMERA_POSES[mode];
    const cam = camera as THREE.PerspectiveCamera;
    cam.fov = p.fov;
    cam.near = mode === "fps" ? 0.05 : 0.1;
    cam.position.set(...p.pos);
    if (mode === "orbit" && portrait) cam.position.set(6, 34, -20);
    cam.lookAt(...p.look);
    cam.updateProjectionMatrix();
  }, [mode, camera, portrait]);
  return null;
}

// ---------- the scene -----------------------------------------------------------------------------------
export type StoreProps = {
  overlay?: boolean;
  planning?: boolean; // planning view: plan changes are marked in the store and the camera turns to them
  basePlan?: Plan; // last month's plan; levers that differ get a tag at their object
  focus?: keyof Plan | null;
  marks?: { clock: number; kind: string; text: string }[]; // in-night decisions taken: a label at the place they act
  tour?: TourShot | null; // welcome tour: the camera flies to this stop and labels its object; orbit input is off meanwhile
  hero: Hero;
  night: NightV2;
  plan: Plan;
  tRef: React.RefObject<number>;
  mode: CamMode;
  monthNum?: number;
  weather?: Weather;
  competitor?: boolean;
};

export function Store3D({ hero, night, plan, tRef, mode, monthNum = 10, weather, competitor, overlay = false, planning = false, basePlan, focus, marks = [], tour = null }: StoreProps) {
  const wx: Weather = weather ?? night.weather ?? "clear";
  const comp = competitor ?? night.competitor ?? false;
  const terraceOpen = night.terrace_open && plan.terrace && wx === "clear";
  const spots = useMemo(() => buildTables(hero).filter((s) => !s.terrace || night.terrace_open), [hero, night]);
  const tables = useMemo(() => new Map(spots.map((s) => [s.id, s])), [spots]);
  const list = useMemo(() => parties(night), [night]);
  const seatings = useMemo(() => tableSeatings(night), [night]);
  const env = useRef<Env>({ night: 0, glows: [] });
  const staff = night.staff ?? plan.staff_per_shift;
  const info = useInfo(night, list);
  // the tour holds the night still on the 인건비 stop, at a moment a server is working (GameV2 stops the clock)
  const atWork = useMemo(() => (tour?.stop === "staff" ? serverAtWork(night, tables, staff) : null), [tour?.stop, night, tables, staff]);
  useEffect(() => { if (atWork) tRef.current = atWork.t; }, [atWork, tRef]);
  return (
    <>
      <Lighting env={env} tRef={tRef} monthNum={monthNum} weather={wx} />
      <CameraRig mode={mode} />
      {mode !== "fps" && <OrbitControls key={mode} makeDefault enabled={!tour} target={CAMERA_POSES[mode].look} maxPolarAngle={Math.PI / 2.05} minDistance={3} maxDistance={60} />}
      {mode === "orbit" && <FocusCam focus={planning && !tour ? focus ?? null : null} />}
      {mode === "orbit" && <TourCam shot={tour} home={CAMERA_POSES.orbit} override={atWork?.pose ?? null} />}
      <FirstPerson active={mode === "fps"} spots={spots} />
      <Building env={env} spots={spots} plan={plan} competitor={comp} weather={wx} />
      <Terrace env={env} open={terraceOpen || spots.some((s) => s.terrace)} />
      <TableLife spots={spots} seatings={seatings} plan={plan} tRef={tRef} planning={planning} />
      <Customers list={list} tables={tables} tRef={tRef} weather={wx} />
      <Crew night={night} tables={tables} staff={staff} tRef={tRef} grill={plan.staff_grilling} list={list} />
      {/* the tour narrates numbers only: no speech bubbles, payments, walk-aways or table cards while it runs */}
      {!tour && <Overlays night={night} list={list} tables={tables} tRef={tRef} />}
      {!tour && <TableHotspots spots={spots} list={list} info={info} tRef={tRef} plan={plan} overlay={overlay} />}
      {tour ? null : planning && basePlan ? <PlanTags plan={plan} base={basePlan} describe={describeLever} /> : <ChangePings plan={plan} describe={describeLever} />}
      <GradeProps grade={plan.meat_grade} />
      {!tour && <DecisionMarks marks={marks} tRef={tRef} />}
      {wx !== "clear" && <Precip kind={wx} />}
      <Passersby key={night.festival ? "fest" : "calm"} count={night.festival ? 26 : wx === "clear" ? 6 : 3} weather={wx} />
    </>
  );
}
