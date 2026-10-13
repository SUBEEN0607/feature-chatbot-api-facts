// The store's 3D pieces, shared by the builder and the simulation view. Colours and the Box helper come from the
// existing store scene (store3d/Building).
import { useMemo } from "react";
import * as THREE from "three";
import { Box, C } from "../store3d/Building";
import { CELL, GRADES, ITEM, type Grade, type Placed } from "./model";

const WOOD = "#8a5a3c", DARK = "#2b2d30", LEAF = "#4d7a4a", PARTITION = "#e9e2d4";

// stool positions around a table, unrotated (x along item.w, z along item.d)
export const SEATS: Record<string, [number, number][]> = {
  table4: [[-0.34, -0.72], [0.34, -0.72], [-0.34, 0.72], [0.34, 0.72]],
  table2: [[-0.5, 0], [0.5, 0]],
};
export function seatSpots(items: Placed[]): [number, number][] {
  return items.flatMap((it) => (SEATS[it.id] ?? []).map(([x, z]): [number, number] => (it.rot ? [it.x + z, it.z - x] : [it.x + x, it.z + z])));
}

export function Cyl({ p, r, h, color, metal = 0 }: { p: [number, number, number]; r: number; h: number; color: string; metal?: number }) {
  return <mesh position={p} castShadow><cylinderGeometry args={[r, r, h, 16]} /><meshStandardMaterial color={color} metalness={metal} roughness={0.6} /></mesh>;
}

// Pieces are drawn unrotated (item.w along x, item.d along z); the parent group turns them.
export function Piece({ id }: { id: string }) {
  const it = ITEM[id];
  if (id === "table4" || id === "table2") return (
    <group>
      <Box p={[0, 0.72, 0]} s={id === "table4" ? [1.1, 0.05, 0.8] : [0.6, 0.05, 0.7]} color={C.steel} metal={0.5} rough={0.4} cast />
      <Cyl p={[0, 0.36, 0]} r={0.06} h={0.7} color={DARK} />
      <Cyl p={[0, 0.76, 0]} r={0.2} h={0.04} color={DARK} />
      <Cyl p={[0, 1.95, 0]} r={0.07} h={1.3} color={C.duct} metal={0.6} />
      <Cyl p={[0, 1.28, 0]} r={0.16} h={0.1} color={C.duct} metal={0.6} />
      {SEATS[id].map(([x, z], i) => <Cyl key={i} p={[x, 0.22, z]} r={0.17} h={0.44} color={WOOD} />)}
    </group>
  );
  if (id === "kitchen") { // a walled room in the back-left corner: serving hatch to the front, doorway on the right
    const w = it.w, d = it.d;
    return (
      <group>
        <Box p={[0, 0.011, 0]} s={[w, 0.02, d]} color={C.tile} />
        <Box p={[0, 0.5, d / 2 - 0.05]} s={[w, 1, 0.1]} color={PARTITION} cast />
        <Box p={[0, 1.02, d / 2 - 0.05]} s={[w, 0.05, 0.3]} color={C.steel} metal={0.5} />
        <Box p={[0, 2.35, d / 2 - 0.05]} s={[w, 0.5, 0.1]} color={PARTITION} />
        <Box p={[-w / 2 + 0.05, 1.55, d / 2 - 0.05]} s={[0.1, 1.1, 0.1]} color={PARTITION} />
        <Box p={[w / 2 - 0.05, 1.3, -d / 2 + 0.7]} s={[0.1, 2.6, 1.4]} color={PARTITION} cast />
        <Box p={[w / 2 - 0.05, 2.35, 0.7]} s={[0.1, 0.5, 1.1]} color={PARTITION} />
        <Box p={[w / 2 - 0.05, 1.3, d / 2 - 0.05]} s={[0.1, 2.6, 0.1]} color={PARTITION} />
        <Box p={[-0.3, 0.45, -d / 2 + 0.4]} s={[w - 1, 0.9, 0.7]} color={C.steel} metal={0.6} rough={0.35} cast />
        <Box p={[-1, 0.93, -d / 2 + 0.4]} s={[0.9, 0.06, 0.6]} color={DARK} />
        <Box p={[-1, 1.95, -d / 2 + 0.45]} s={[1.3, 0.3, 0.8]} color={C.duct} metal={0.6} />
      </group>
    );
  }
  if (id === "counter") return (
    <group>
      <Box p={[0, 0.5, 0]} s={[it.w - 0.1, 1, it.d - 0.3]} color={C.counter} cast />
      <Box p={[0.3, 1.15, 0]} s={[0.36, 0.28, 0.06]} color={DARK} />
    </group>
  );
  if (id === "kiosk") return (
    <group>
      <Box p={[0, 0.7, 0]} s={[0.12, 1.4, 0.12]} color={DARK} cast />
      <Box p={[0, 1.25, 0.05]} s={[0.4, 0.55, 0.06]} color="#3d63ea" />
    </group>
  );
  if (id === "fridge") return (
    <group>
      <Box p={[0, 0.95, 0]} s={[0.9, 1.9, 0.8]} color="#e9ecee" metal={0.3} cast />
      <Box p={[0, 1, 0.41]} s={[0.76, 1.5, 0.02]} color={C.glass} opacity={0.7} />
    </group>
  );
  if (id === "bench") return <Box p={[0, 0.22, 0]} s={[1.4, 0.44, 0.4]} color={WOOD} cast />;
  if (id === "plant") return (
    <group>
      <Cyl p={[0, 0.18, 0]} r={0.16} h={0.36} color="#b9836a" />
      <mesh position={[0, 0.72, 0]} castShadow><coneGeometry args={[0.24, 0.8, 9]} /><meshStandardMaterial color={LEAF} roughness={0.9} /></mesh>
    </group>
  );
  return ( // lamp
    <group>
      <Cyl p={[0, 0.7, 0]} r={0.025} h={1.4} color={DARK} />
      <mesh position={[0, 1.48, 0]}><coneGeometry args={[0.2, 0.26, 16, 1, true]} /><meshStandardMaterial color="#ffe9b0" emissive="#ffcf70" emissiveIntensity={0.7} side={THREE.DoubleSide} /></mesh>
    </group>
  );
}

export function Room({ w, d, grade }: { w: number; d: number; grade: Grade }) {
  const g = GRADES[grade];
  const lines = useMemo(() => {
    const pts: number[] = [];
    for (let x = -w / 2; x <= w / 2 + 1e-6; x += CELL) pts.push(x, 0.012, -d / 2, x, 0.012, d / 2);
    for (let z = -d / 2; z <= d / 2 + 1e-6; z += CELL) pts.push(-w / 2, 0.012, z, w / 2, 0.012, z);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
    return geo;
  }, [w, d]);
  return (
    <group>
      <Box p={[0, -0.05, 0]} s={[w, 0.1, d]} color={g.floor} receive />
      <lineSegments geometry={lines}><lineBasicMaterial color="#191f28" transparent opacity={0.12} /></lineSegments>
      <Box p={[0, 1.3, -d / 2 - 0.06]} s={[w + 0.24, 2.6, 0.12]} color={g.wall} />
      <Box p={[-w / 2 - 0.06, 1.3, 0]} s={[0.12, 2.6, d]} color={g.wall} />
      <Box p={[0, 0.45, -d / 2 + 0.005]} s={[w, 0.9, 0.02]} color={C.wainscot} />
      <Box p={[-w / 2 + 0.005, 0.45, 0]} s={[0.02, 0.9, d]} color={C.wainscot} />
      <Box p={[w / 2 - 1.2, 0.011, d / 2 - 0.25]} s={[1, 0.02, 0.5]} color="#3d63ea" opacity={0.55} />
      <Box p={[0, -0.12, 0]} s={[w + 6, 0.02, d + 6]} color="#e6eaf2" receive />
    </group>
  );
}

export function Items({ items, hide }: { items: Placed[]; hide?: number }) {
  return <>{items.filter((it) => it.uid !== hide).map((it) => (
    <group key={it.uid} position={[it.x, 0, it.z]} rotation={[0, it.rot ? Math.PI / 2 : 0, 0]}><Piece id={it.id} /></group>
  ))}</>;
}
