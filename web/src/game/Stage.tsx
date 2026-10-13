// The 3D store canvas, split out so three.js loads only when the store is shown.
import { Canvas } from "@react-three/fiber";
import type { Hero, Night } from "../data";
import { StoreScene, type CamMode } from "../replay/Scene";

export default function Stage({ hero, night, tRef, mode }: { hero: Hero; night: Night; tRef: React.RefObject<number>; mode: CamMode }) {
  return (
    <Canvas shadows dpr={[1, 2]} camera={{ fov: 42, near: 0.1, far: 120 }} id="fps-start">
      <StoreScene hero={hero} night={night} tRef={tRef} mode={mode} floaters />
    </Canvas>
  );
}
