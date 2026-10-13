// Procedural low-poly 삼겹살집: indoor 4-tops with a round grill and exhaust duct each, 야장 tables with red
// plastic stools, counter, 소주 fridge, glass front with a door, and a waiting line on the sidewalk.
// Every mesh is generated here (no external assets).
import { useEffect, useMemo, useRef, useState } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { Html, OrbitControls, PointerLockControls } from "@react-three/drei";
import * as THREE from "three";
import type { Hero, Night } from "../data";
import { COUNTER, ROOM, buildTables, type TableSpot } from "./layout";
import { SEGMENTS, STAFF_COLOR, makePoser, occupiedTables, parties, queueOrder, staffPlan, type Party } from "./timeline";

export type CamMode = "orbit" | "fps";

const C = {
  floor: "#ddd6ca",
  wall: "#f3f1ec",
  wallTrim: "#cfc8bb",
  sidewalk: "#d3d6d8",
  street: "#a4aab0",
  curb: "#bfc3c6",
  steel: "#c3c8cd",
  grill: "#2b2b2b",
  ember: "#ff6a2b",
  stoolIn: "#6d5140",
  stoolOut: "#d2452f",
  plastic: "#f2efe8",
  counter: "#8b6a50",
  sign: "#8a2b1f",
  glass: "#cfe2ea",
  soju: "#2f8f5b",
};

function Box({ p, s, color, metal = 0, rough = 0.8, cast = true, receive = false, opacity = 1 }: {
  p: [number, number, number]; s: [number, number, number]; color: string; metal?: number; rough?: number;
  cast?: boolean; receive?: boolean; opacity?: number;
}) {
  return (
    <mesh position={p} castShadow={cast} receiveShadow={receive}>
      <boxGeometry args={s} />
      <meshStandardMaterial color={color} metalness={metal} roughness={rough} transparent={opacity < 1} opacity={opacity} />
    </mesh>
  );
}

function Stool({ x, z, color }: { x: number; z: number; color: string }) {
  return (
    <mesh position={[x, 0.225, z]} castShadow>
      <cylinderGeometry args={[0.17, 0.19, 0.45, 12]} />
      <meshStandardMaterial color={color} roughness={0.7} />
    </mesh>
  );
}

function Table({ spot, emberRef }: { spot: TableSpot; emberRef: (m: THREE.MeshStandardMaterial | null) => void }) {
  const top = spot.terrace ? C.plastic : C.steel;
  return (
    <group>
      <Box p={[spot.x, 0.72, spot.z]} s={[1.3, 0.06, 0.8]} color={top} metal={spot.terrace ? 0 : 0.55} rough={spot.terrace ? 0.9 : 0.35} />
      <Box p={[spot.x, 0.35, spot.z]} s={[0.12, 0.7, 0.12]} color="#8d9296" metal={0.4} />
      <mesh position={[spot.x, 0.78, spot.z]} castShadow>
        <cylinderGeometry args={[0.25, 0.22, 0.07, 20]} />
        <meshStandardMaterial color={C.grill} roughness={0.5} metalness={0.3} />
      </mesh>
      <mesh position={[spot.x, 0.818, spot.z]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[0.2, 20]} />
        <meshStandardMaterial ref={emberRef} color="#3a3a3a" emissive={C.ember} emissiveIntensity={0} roughness={0.9} />
      </mesh>
      {!spot.terrace && (
        <>
          <mesh position={[spot.x, 1.52, spot.z]} castShadow>
            <cylinderGeometry args={[0.13, 0.32, 0.26, 18, 1, true]} />
            <meshStandardMaterial color="#d7dbde" metalness={0.7} roughness={0.3} side={THREE.DoubleSide} />
          </mesh>
          <mesh position={[spot.x, 2.2, spot.z]}>
            <cylinderGeometry args={[0.11, 0.11, 1.2, 14]} />
            <meshStandardMaterial color="#d7dbde" metalness={0.7} roughness={0.3} />
          </mesh>
        </>
      )}
      {spot.seats.map(([x, z], i) => (
        <Stool key={i} x={x} z={z + (z > spot.z ? 0.12 : -0.12)} color={spot.terrace ? C.stoolOut : C.stoolIn} />
      ))}
    </group>
  );
}

function SojuFridge() {
  const bottles = useMemo(() => {
    const out: [number, number, number][] = [];
    for (let shelf = 0; shelf < 3; shelf++) for (let i = 0; i < 7; i++) out.push([4.35 + i * 0.2, 0.55 + shelf * 0.55, ROOM.z0 + 0.42]);
    return out;
  }, []);
  return (
    <group>
      <Box p={[5.0, 0.95, ROOM.z0 + 0.35]} s={[1.7, 1.9, 0.6]} color="#e8ecee" metal={0.2} rough={0.4} />
      {bottles.map((b, i) => (
        <mesh key={i} position={b}>
          <cylinderGeometry args={[0.055, 0.06, 0.3, 8]} />
          <meshStandardMaterial color={C.soju} roughness={0.3} />
        </mesh>
      ))}
      <Box p={[5.0, 0.95, ROOM.z0 + 0.66]} s={[1.6, 1.8, 0.02]} color={C.glass} opacity={0.3} cast={false} />
    </group>
  );
}

function Shell() {
  const { x0, x1, z0, z1, wallH } = ROOM;
  const w = x1 - x0;
  return (
    <group>
      <Box p={[0, -0.02, (z0 + z1) / 2]} s={[w, 0.04, z1 - z0]} color={C.floor} cast={false} receive />
      <Box p={[0, -0.03, 5.6]} s={[30, 0.04, 4.4]} color={C.sidewalk} cast={false} receive />
      <Box p={[0, 0.03, 7.85]} s={[30, 0.1, 0.18]} color={C.curb} cast={false} />
      <Box p={[0, -0.05, 11]} s={[30, 0.04, 6]} color={C.street} cast={false} receive />
      <Box p={[0, wallH / 2, z0]} s={[w, wallH, 0.14]} color={C.wall} cast={false} receive />
      <Box p={[x0, wallH / 2, (z0 + z1) / 2]} s={[0.14, wallH, z1 - z0]} color={C.wall} cast={false} receive />
      <Box p={[x1, wallH / 2, (z0 + z1) / 2]} s={[0.14, wallH, z1 - z0]} color={C.wall} cast={false} receive />
      <Box p={[0, 0.08, z0 + 0.08]} s={[w, 0.16, 0.04]} color={C.wallTrim} cast={false} />
      {/* glass front with a door gap at x = 0 */}
      {[-1, 1].map((sgn) => (
        <group key={sgn}>
          <Box p={[sgn * (0.8 + (x1 - 0.8) / 2), 0.35, z1]} s={[x1 - 0.8, 0.7, 0.14]} color={C.wallTrim} />
          <Box p={[sgn * (0.8 + (x1 - 0.8) / 2), 1.6, z1]} s={[x1 - 0.8, 1.8, 0.04]} color={C.glass} opacity={0.22} cast={false} />
          <Box p={[sgn * 0.8, 1.1, z1]} s={[0.07, 2.2, 0.1]} color="#8a8f94" metal={0.5} />
        </group>
      ))}
      <Box p={[0, 2.62, z1 + 0.06]} s={[2.2, 0.36, 0.1]} color={C.sign} />
      <Box p={[0, 2.62, z1 + 0.12]} s={[1.6, 0.08, 0.02]} color="#f6e7d8" cast={false} />
      {/* counter and kitchen pass */}
      <Box p={[COUNTER[0], 0.5, COUNTER[1]]} s={[3.6, 1.0, 0.7]} color={C.counter} />
      <Box p={[COUNTER[0], 1.03, COUNTER[1]]} s={[3.7, 0.06, 0.8]} color="#e9e4dc" />
      <Box p={[COUNTER[0] - 2.4, 1.6, z0 + 0.1]} s={[1.4, 0.8, 0.04]} color="#f7f3ea" cast={false} />
      <SojuFridge />
    </group>
  );
}

type FigureRef = { group: THREE.Group; body: THREE.Mesh; head: THREE.Mesh };

function Crowd({ list, tables, tRef }: { list: Party[]; tables: Map<string, TableSpot>; tRef: React.RefObject<number> }) {
  const pose = useMemo(() => makePoser(tables), [tables]);
  const figs = useMemo(() => list.flatMap((p) => Array.from({ length: p.size }, (_, k) => ({ p, k }))), [list]);
  const refs = useRef<(FigureRef | null)[]>([]);
  const mats = useMemo(() => {
    const m: Record<string, THREE.MeshStandardMaterial> = {};
    for (const [k, v] of Object.entries(SEGMENTS)) m[k] = new THREE.MeshStandardMaterial({ color: v.color, roughness: 0.6 });
    m.faded = new THREE.MeshStandardMaterial({ color: "#b7b9bb", roughness: 0.8, transparent: true, opacity: 0.7 });
    return m;
  }, []);
  useFrame(() => {
    const t = tRef.current ?? 0;
    const order = queueOrder(list, t);
    figs.forEach(({ p, k }, i) => {
      const r = refs.current[i];
      if (!r) return;
      const ps = pose(p, k, t, order.get(p.id) ?? 0);
      r.group.visible = ps.visible;
      if (!ps.visible) return;
      r.group.position.set(ps.x, ps.seated ? 0.3 : 0, ps.z);
      r.body.scale.y = ps.seated ? 0.66 : 1;
      r.body.position.y = ps.seated ? 0.38 : 0.58;
      r.head.position.y = ps.seated ? 0.95 : 1.3;
      r.body.material = ps.faded ? mats.faded : mats[p.segment];
    });
  });
  return (
    <group>
      {figs.map(({ p, k }, i) => (
        <group key={`${p.id}-${k}`} visible={false} ref={(g) => {
          if (g) refs.current[i] = { group: g, body: g.children[0] as THREE.Mesh, head: g.children[1] as THREE.Mesh };
        }}>
          <mesh position={[0, 0.58, 0]} castShadow material={mats[p.segment]}>
            <capsuleGeometry args={[0.2, 0.72, 4, 10]} />
          </mesh>
          <mesh position={[0, 1.3, 0]} castShadow>
            <sphereGeometry args={[0.15, 12, 10]} />
            <meshStandardMaterial color="#f0d9c4" roughness={0.7} />
          </mesh>
        </group>
      ))}
    </group>
  );
}

function Staff({ night, tables, servers, tRef }: { night: Night; tables: Map<string, TableSpot>; servers: number; tRef: React.RefObject<number> }) {
  const plan = useMemo(() => staffPlan(night, tables, servers), [night, tables, servers]);
  const refs = useRef<(THREE.Group | null)[]>([]);
  useFrame(() => {
    const t = tRef.current ?? 0;
    refs.current.forEach((g, k) => {
      if (!g) return;
      const [x, z] = plan(k, t);
      g.position.set(x, 0, z);
    });
  });
  return (
    <group>
      {Array.from({ length: servers }, (_, k) => (
        <group key={k} ref={(g) => { refs.current[k] = g; }}>
          <mesh position={[0, 0.62, 0]} castShadow>
            <capsuleGeometry args={[0.21, 0.8, 4, 10]} />
            <meshStandardMaterial color={STAFF_COLOR} roughness={0.6} />
          </mesh>
          <mesh position={[0, 0.55, 0.12]}>
            <boxGeometry args={[0.34, 0.5, 0.12]} />
            <meshStandardMaterial color="#f4f1ea" roughness={0.9} />
          </mesh>
          <mesh position={[0, 1.4, 0]} castShadow>
            <sphereGeometry args={[0.15, 12, 10]} />
            <meshStandardMaterial color="#f0d9c4" roughness={0.7} />
          </mesh>
        </group>
      ))}
    </group>
  );
}

function Embers({ list, tRef, mats }: { list: Party[]; tRef: React.RefObject<number>; mats: React.RefObject<Map<string, THREE.MeshStandardMaterial>> }) {
  useFrame(() => {
    const occ = occupiedTables(list, tRef.current ?? 0);
    mats.current?.forEach((m, id) => {
      m.emissiveIntensity = occ.has(id) ? 1.6 : 0;
    });
  });
  return null;
}

// Small floating labels: "+₩" when a table pays, "돌아감" when a waiting party walks away.
function Floaters({ list, tables, tRef }: { list: Party[]; tables: Map<string, TableSpot>; tRef: React.RefObject<number> }) {
  const [live, setLive] = useState<{ key: string; x: number; z: number; text: string; kind: "pay" | "balk" }[]>([]);
  const last = useRef("");
  useFrame(() => {
    const t = tRef.current ?? 0;
    const out: { key: string; x: number; z: number; text: string; kind: "pay" | "balk" }[] = [];
    for (const p of list) {
      if (p.leave != null && p.table && t >= p.leave && t < p.leave + 2.5) {
        const tb = tables.get(p.table);
        if (tb) out.push({ key: `p${p.id}`, x: tb.x, z: tb.z, text: `+${Math.round(p.bill).toLocaleString("ko-KR")}원`, kind: "pay" });
      }
      if (p.balk != null && p.seat == null && t >= p.balk && t < p.balk + 2) {
        out.push({ key: `b${p.id}`, x: -2.2, z: 5.0, text: "기다리다 돌아감", kind: "balk" });
      }
    }
    const sig = out.map((o) => o.key).join(",");
    if (sig !== last.current) {
      last.current = sig;
      setLive(out);
    }
  });
  return (
    <>
      {live.map((o) => (
        <Html key={o.key} position={[o.x, 2.1, o.z]} center zIndexRange={[20, 0]} pointerEvents="none">
          <span className={`floater floater-${o.kind}`}>{o.text}</span>
        </Html>
      ))}
    </>
  );
}

function FirstPerson({ active }: { active: boolean }) {
  const keys = useRef<Record<string, boolean>>({});
  const { camera } = useThree();
  useEffect(() => {
    const down = (e: KeyboardEvent) => { keys.current[e.code] = true; };
    const up = (e: KeyboardEvent) => { keys.current[e.code] = false; };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, []);
  useFrame((_, dt) => {
    if (!active) return;
    const k = keys.current;
    const f = (k.KeyW ? 1 : 0) - (k.KeyS ? 1 : 0);
    const s = (k.KeyD ? 1 : 0) - (k.KeyA ? 1 : 0);
    if (!f && !s) return;
    const dir = new THREE.Vector3();
    camera.getWorldDirection(dir);
    dir.y = 0;
    dir.normalize();
    const right = new THREE.Vector3().crossVectors(dir, new THREE.Vector3(0, 1, 0));
    camera.position.addScaledVector(dir, f * 2.6 * dt).addScaledVector(right, s * 2.6 * dt);
    camera.position.x = THREE.MathUtils.clamp(camera.position.x, -11, 11);
    camera.position.z = THREE.MathUtils.clamp(camera.position.z, ROOM.z0 + 0.4, 9);
    camera.position.y = 1.6;
  });
  return active ? <PointerLockControls selector="#fps-start" /> : null;
}

export const CAMERA_POSES: Record<CamMode, { pos: [number, number, number]; look: [number, number, number] }> = {
  orbit: { pos: [0.5, 15.5, 12.8], look: [0, 0, 0.9] },
  fps: { pos: [1.3, 1.6, 3.0], look: [-2.4, 1.05, -3.2] },
};

function CameraRig({ mode }: { mode: CamMode }) {
  const { camera, size } = useThree();
  const portrait = size.width < size.height;
  useEffect(() => {
    const p = CAMERA_POSES[mode];
    const cam = camera as THREE.PerspectiveCamera;
    cam.fov = mode === "fps" ? 70 : 42;
    if (mode === "orbit" && portrait) {
      cam.position.set(0.3, 40, 21);
      cam.lookAt(0, 0, 1.4);
    } else {
      cam.position.set(...p.pos);
      cam.lookAt(...p.look);
    }
    cam.updateProjectionMatrix();
  }, [mode, camera, portrait]);
  return null;
}

export function StoreScene({ hero, night, tRef, mode, floaters = false }: { hero: Hero; night: Night; tRef: React.RefObject<number>; mode: CamMode; floaters?: boolean }) {
  const spots = useMemo(() => buildTables(hero).filter((s) => !s.terrace || night.terrace_open), [hero, night]);
  const tables = useMemo(() => new Map(spots.map((s) => [s.id, s])), [spots]);
  const list = useMemo(() => parties(night), [night]);
  const emberMats = useRef(new Map<string, THREE.MeshStandardMaterial>());
  return (
    <>
      <color attach="background" args={["#eceeef"]} />
      <hemisphereLight args={["#ffffff", "#d9d2c6", 1.1]} />
      <directionalLight position={[6, 12, 8]} intensity={1.5} castShadow shadow-mapSize={[1024, 1024]}
        shadow-camera-left={-14} shadow-camera-right={14} shadow-camera-top={12} shadow-camera-bottom={-12} />
      <CameraRig mode={mode} />
      {mode === "orbit" && <OrbitControls target={CAMERA_POSES.orbit.look as [number, number, number]} maxPolarAngle={Math.PI / 2.15} minDistance={5} maxDistance={60} />}
      <FirstPerson active={mode === "fps"} />
      <Shell />
      {spots.map((s) => (
        <Table key={s.id} spot={s} emberRef={(m) => { if (m) emberMats.current.set(s.id, m); }} />
      ))}
      <Embers list={list} tRef={tRef} mats={emberMats} />
      <Crowd list={list} tables={tables} tRef={tRef} />
      <Staff night={night} tables={tables} servers={hero.servers} tRef={tRef} />
      {floaters && <Floaters list={list} tables={tables} tRef={tRef} />}
    </>
  );
}
