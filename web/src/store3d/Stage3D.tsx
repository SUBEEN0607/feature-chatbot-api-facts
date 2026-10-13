// The v2 store canvas, split out so three.js loads only when the store is shown.
import { Canvas } from "@react-three/fiber";
import { Store3D, type StoreProps } from "./Store3D";
import "./store3d.css";

export default function Stage3D(props: StoreProps) {
  return (
    <Canvas shadows dpr={[1, 2]} camera={{ fov: 40, near: 0.1, far: 160 }} id="s3-canvas" gl={{ antialias: true }}>
      <Store3D {...props} />
    </Canvas>
  );
}
