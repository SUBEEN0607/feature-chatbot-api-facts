// The pre-founder flow (mock): 내 조건 → 동네 분석 → 가게 꾸미기 (위험 신호 점검 포함) → 시뮬레이션. See DESIGN.md.
import { Suspense, lazy, useEffect, useState } from "react";
import { DEFAULT_LEVERS, DEFAULT_PROFILE, recommend, setGuData, starterStore, type Gu, type Levers, type Profile, type Store } from "./model";
import ProfileStep from "./Profile";
import Analysis from "./Analysis";
import Chat from "./Chat";
import "./mock.css";

const Builder = lazy(() => import("./Builder"));
const Simulate = lazy(() => import("./Simulate"));

export type Step = "profile" | "area" | "build" | "sim";
const STEPS: { key: Step; label: string }[] = [
  { key: "profile", label: "내 조건" },
  { key: "area", label: "동네 분석" },
  { key: "build", label: "가게 꾸미기" },
  { key: "sim", label: "시뮬레이션" },
];

export default function Mock() {
  const [step, setStep] = useState<Step>("profile");
  const [reached, setReached] = useState(0);
  const [profile, setProfile] = useState<Profile>(DEFAULT_PROFILE);
  const [store, setStoreRaw] = useState<Store>(() => starterStore());
  const [levers, setLevers] = useState<Levers>(DEFAULT_LEVERS);
  const [edited, setEdited] = useState(false);
  const setStore = (s: Store) => { setEdited(true); setStoreRaw(s); };
  const [gus, setGus] = useState<Gu[]>([]);
  const [ready, setReady] = useState(false);
  const [chat, setChat] = useState(false);

  useEffect(() => {
    const get = (f: string) => fetch(`${import.meta.env.BASE_URL}mock/${f}`).then((r) => r.json());
    Promise.all([get("seoul_gu.json"), get("gu_stats.json")]).then(([g, d]) => { setGuData(d); setGus(g); setReady(true); }).catch(() => setReady(true));
  }, []);

  useEffect(() => {
    if (!ready || edited) return;
    const plan = recommend(profile);
    setStoreRaw(plan.store);
    setLevers((l) => ({ ...l, staff: plan.staff }));
  }, [ready, edited, profile.gu, profile.capital]); // eslint-disable-line react-hooks/exhaustive-deps

  const go = (s: Step) => {
    setStep(s);
    setReached((r) => Math.max(r, STEPS.findIndex((x) => x.key === s)));
    scrollTo({ top: 0 });
  };
  const idx = STEPS.findIndex((s) => s.key === step);

  return (
    <div className={`m-app m-step-${step}`}>
      <header className="m-top">
        <a className="m-brand" href="#/" onClick={() => go("profile")}>ChangeUp</a>
        <nav aria-label="진행 단계">
          <ol>
            {STEPS.map((s, i) => (
              <li key={s.key}>
                <button type="button" aria-current={s.key === step ? "step" : undefined} disabled={i > reached} onClick={() => go(s.key)}>
                  <span className="m-num">{i + 1}</span>{s.label}
                </button>
              </li>
            ))}
          </ol>
        </nav>
        {idx >= 1 && (
          <button type="button" className="m-chatbtn" aria-expanded={chat} onClick={() => setChat((c) => !c)}>
            {chat ? "질문 창 닫기" : "궁금한 것 물어보기"}
          </button>
        )}
      </header>
      <p className="m-mocknote">목업 화면입니다. 지역 매출과 점포 수는 서울시 공개 자료, 날씨는 기상청 공개 자료, 비용과 월세는 가정이에요. <a href="#/sources">출처 보기</a></p>

      {!ready && <p className="m-loading">자료를 불러오는 중이에요</p>}
      {ready && step === "profile" && <ProfileStep profile={profile} setProfile={setProfile} gus={gus} onDone={() => go("area")} />}
      {ready && step === "area" && <Analysis profile={profile} setProfile={setProfile} gus={gus} store={store} onNext={() => go("build")} />}
      {ready && step === "build" && (
        <Suspense fallback={<p className="m-loading">가게 도면을 펴는 중이에요</p>}>
          <Builder profile={profile} store={store} setStore={setStore} levers={levers} setLevers={setLevers} onNext={() => go("sim")} />
        </Suspense>
      )}
      {ready && step === "sim" && (
        <Suspense fallback={<p className="m-loading">가게 문을 여는 중이에요</p>}>
          <Simulate profile={profile} store={store} levers={levers} setLevers={setLevers} onBack={() => go("build")} />
        </Suspense>
      )}

      {idx >= 1 && chat && <Chat profile={profile} store={store} levers={levers} shocks={[]} gus={gus} onClose={() => setChat(false)} />}
    </div>
  );
}
