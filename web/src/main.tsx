import { StrictMode, Suspense, lazy, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import DirectionA from "./directions/A";
import DirectionB from "./directions/B";
import DirectionC from "./directions/C";
import "./styles/base.css";

const Replay = lazy(() => import("./replay/Replay"));
const Game = lazy(() => import("./game/Game"));
const StorePreview = lazy(() => import("./store3d/StorePreview"));
const GameV2 = lazy(() => import("./v2/GameV2"));
const ReportPrint = lazy(() => import("./v2/ReportPrint"));
const Mock = lazy(() => import("./mock/Mock"));
const Sources = lazy(() => import("./mock/Sources"));

function useHash() {
  const [hash, setHash] = useState(location.hash || "#/");
  useEffect(() => {
    const on = () => setHash(location.hash || "#/");
    addEventListener("hashchange", on);
    return () => removeEventListener("hashchange", on);
  }, []);
  const [path, qs = ""] = hash.slice(1).split("?");
  return { path, query: new URLSearchParams(qs) };
}

function setQuery(path: string, key: string, value: string) {
  const q = new URLSearchParams(location.hash.split("?")[1] ?? "");
  q.set(key, value);
  location.hash = `${path}?${q}`;
}

const VIEWS = [
  { href: "#/v2", name: "게임 v2 (이전 본편)", text: "시연 모드, 자유 플레이, 비교. 한 달마다 운영 계획을 세우고 3D 가게와 정산으로 결과를 봅니다." },
  { href: "#/v1", name: "게임 v1", text: "지도에서 가게로 들어가 매달 생기는 사건에 사장님의 선택을 고르고, 시뮬레이션으로 한 달을 돌린 뒤 정산합니다." },
  { href: "#/lab/replay", name: "3D 재생", text: "토요일 밤 하나를 평소와 충격 후로 나눠 다시 봅니다. 손님이 오고, 기다리고, 앉고, 떠나는 모습을 시간대별로 확인합니다." },
  { href: "#/lab/a", name: "시안 A. 보고서", text: "한 문장으로 결과를 말하고, 표와 그림으로 뒷받침합니다. 대표에게 읽히는 문서처럼 구성했습니다." },
  { href: "#/lab/b", name: "시안 B. 운영 콘솔", text: "지표, 상황, 매장, 요인 나무, 대화를 한 화면에 모았습니다. 여러 상황을 빠르게 비교할 때 씁니다." },
  { href: "#/lab/c", name: "시안 C. 지도 먼저", text: "대학로 상권 지도에서 출발해 매장 안으로 들어갑니다. 장소와 경쟁이 먼저 보입니다." },
];

function Home() {
  return (
    <main className="home">
      <h1>대학로 삼겹살집 디지털 트윈, 실험실</h1>
      <p className="home-lead">합성 매장 한 곳을 공공데이터와 추정값으로 만들고, 시뮬레이션으로 충격을 줘 봅니다. 화면의 숫자는 모두 사람이 검토하기 전의 예시값입니다.</p>
      <ul>
        {VIEWS.map((v) => (
          <li key={v.href}>
            <a href={v.href}>
              <strong>{v.name}</strong>
              <span>{v.text}</span>
            </a>
          </li>
        ))}
      </ul>
    </main>
  );
}

function App() {
  const { path: raw, query } = useHash();
  const path = raw.replace(/^\/lab(?=\/.)/, "");
  const shock = query.get("shock") ?? "SH03";
  const set = (s: string) => setQuery(raw, "shock", s);
  if (path === "/replay") return <Suspense fallback={null}><Replay query={query} /></Suspense>;
  if (path === "/a") return <DirectionA shock={shock} setShock={set} />;
  if (path === "/b") return <DirectionB shock={shock} setShock={set} />;
  if (path === "/c") return <DirectionC shock={shock} setShock={set} />;
  if (raw === "/lab") return <Home />;
  if (raw === "/store") return <Suspense fallback={null}><StorePreview query={query} /></Suspense>;
  if (raw === "/report-print") return <Suspense fallback={null}><ReportPrint /></Suspense>;
  if (raw === "/v1") return <Suspense fallback={<p className="g-loading">게임 데이터를 불러오는 중입니다</p>}><Game query={query} /></Suspense>;
  if (raw === "/sources") return <Suspense fallback={null}><Sources /></Suspense>;
  if (raw === "/v2") return <Suspense fallback={null}><GameV2 query={query} /></Suspense>;
  return <Suspense fallback={null}><Mock /></Suspense>; // #/: the pre-founder flow (mock); the old game is #/v2
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
