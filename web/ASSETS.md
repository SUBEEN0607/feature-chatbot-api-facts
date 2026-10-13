# Assets and licenses

- **3D store, figures, furniture:** procedural geometry written in `src/replay/Scene.tsx` (v1) and `src/store3d/`
  (v2: instanced low-poly people, ducts, signs, street, weather). Signs, the menu board and particles are canvas
  textures drawn at runtime (`src/store3d/textures.ts`). The metal reflections use three.js `RoomEnvironment`
  (procedural, ships with three, MIT). No external models, image textures or HDRIs. Nothing to attribute.
- **Fonts (loaded from CDN at runtime, not bundled):**
  - Pretendard Variable, SIL Open Font License 1.1 (cdn.jsdelivr.net/gh/orioncactus/pretendard)
  - SUIT Variable, SIL Open Font License 1.1 (cdn.jsdelivr.net/gh/sun-typeface/SUIT)
  - Noto Serif KR, SIL Open Font License 1.1 (Google Fonts)
- **Map:** 상권 boundaries (서울시 상권분석서비스 영역, 공공누리 1유형) and store points (소상공인시장진흥공단
  상가정보, 이용허락범위 제한 없음), exported to `public/data/district.json` by `scripts/sync_data.py`.
  No map tiles.
- **Libraries:** React, three.js, @react-three/fiber, @react-three/drei, Vite (all MIT).

Kenney / Quaternius CC0 kits were not used in this version; the procedural store is enough for the first
review. If they are added later, list each kit and its CC0 license here.
