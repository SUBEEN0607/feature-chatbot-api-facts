// Mock assistant: numbers on screen are explained locally from the model. Questions outside those rules, and the
// citations for every answer, come from the citation API (api/cite_api.py), which only uses credible sources.
import { useEffect, useRef, useState } from "react";
import { guStat, iga, man, openingCost, rankOf, simulate, type Gu, type Levers, type Profile, type ShockId, type Store } from "./model";
import "./cite.css";

type Cite = { id: string; title: string; publisher: string; year: string; type: string; url: string; note: string };
type Msg = { who: "me" | "bot"; text: string; cites?: Cite[]; offline?: boolean };
const ASK = ["몇 달째부터 남기 시작해요?", "돈이 제일 많이 드는 곳은 어디예요?", "하루에 몇 명 받아야 본전이에요?", "이 동네 경쟁은 어때요?"];
const CITE_API = (import.meta.env.VITE_CITE_API as string | undefined) ?? "http://127.0.0.1:8001";
type Local = { text: string; cq: string };

export default function Chat({ profile, store, levers, shocks, gus, onClose }: {
  profile: Profile; store: Store; levers: Levers; shocks: ShockId[]; gus: Gu[]; onClose: () => void;
}) {
  const [log, setLog] = useState<Msg[]>([{ who: "bot", text: "화면에 나온 계산을 풀어서 설명해 드려요. 아래 질문을 누르거나 직접 적어 보세요." }]);
  const [text, setText] = useState("");
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ block: "end" }); }, [log]);

  // Returns the explanation of a number on screen (null when the question is outside those rules) plus the query
  // used to find sources for it.
  const answer = (q: string): Local | null => {
    const run = simulate(profile, store, levers, shocks);
    const st = guStat(profile.gu);
    if (/남기|흑자|언제/.test(q)) {
      const r = run.rows.find((x) => x.op - 300 >= 0);
      const text = r ? `지금 조건이면 ${r.m}개월째부터 사장님 생활비 300만원을 빼고도 남아요. 그달 영업이익은 ${man(r.op)}이에요. 오픈 직후에는 손님이 자리 잡은 뒤의 55%만 온다고 가정했어요.`
        : `6개월 안에는 사장님 생활비까지 벌지 못해요. 6개월째 영업이익이 ${man(run.rows[5].op)}이에요.`;
      return { text, cq: "외식 폐업 생존 영업기간" };
    }
    if (/많이 드는|비용|돈이/.test(q)) {
      const top = [...openingCost(store, profile.gu).lines].sort((a, b) => b.amount - a.amount);
      return { text: `여는 데 드는 ${man(run.opening)} 가운데 ${iga(top[0].label)} ${man(top[0].amount)}으로 가장 커요. 그다음이 ${top[1].label} ${man(top[1].amount)}이에요.`, cq: "외식업 경영 비용 임차 인건비 식재료" };
    }
    if (/본전|몇 명|손익/.test(q)) {
      const ticket = levers.price + 8000;
      const fixed = levers.staff * 199 + st.rent * store.pyeong + 12.8 * store.pyeong + 300;
      const perCover = (ticket * levers.days * (1 - 0.31 * (19000 / levers.price) - 0.0084)) / 10000;
      return { text: `하루 ${Math.ceil(fixed / perCover)}명쯤 받아야 사장님 생활비까지 나와요. 한 달 고정비 ${man(fixed)}을 손님 한 명이 남기는 돈으로 나눈 값이에요.`, cq: "외식업 경영실태 영업이익" };
    }
    if (/경쟁|고깃집 수|옆 가게/.test(q)) {
      return { text: `${profile.gu}에는 돼지고기 구이 가게가 ${st.pork.toLocaleString("ko-KR")}곳 있고, 25개 구 중 ${rankOf(profile.gu, "pork", gus.map((g) => g.name))}번째로 많아요 (소상공인 상가정보 2026년 6월). 한식음식점 전체로 보면 2025년 한 해에 ${st.closure}%가 문을 닫았어요.`, cq: "상가 정보 음식점 폐업 생존" };
    }
    if (/월세|임대/.test(q)) return { text: `${profile.gu}의 평당 월세는 ${st.rent}만원으로 잡았어요. ${store.pyeong}평이면 한 달 ${man(st.rent * store.pyeong)}이에요. 예시값이에요.`, cq: "상가 임대료 임대동향" };
    return null;
  };
  const send = async (q: string) => {
    const question = q.trim();
    if (!question) return;
    const local = answer(question);
    setLog((l) => [...l, { who: "me", text: question }]);
    setText("");
    // 화면 숫자 질문: 설명은 화면 계산값, 출처는 문헌 목록(/cite).
    // 그 밖의 질문: 답과 출처 모두 근거 항목(/ask, 공공 API 결과)에서 가져온다.
    let cites: Cite[] = [];
    let apiAnswer: string | null = null;
    let apiMessage = "";
    let offline = false;
    try {
      const path = local ? `/cite?q=${encodeURIComponent(local.cq)}` : `/ask?q=${encodeURIComponent(question)}`;
      const r = await fetch(`${CITE_API}${path}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      cites = d.citations ?? [];
      apiAnswer = d.answer ?? null;
      apiMessage = d.message ?? "";
    } catch {
      offline = true;
    }
    const text = local ? local.text
      : apiAnswer ? apiAnswer
      : apiMessage || "목업에서는 화면의 숫자에 대한 질문과, 등록된 근거 자료에 있는 내용만 답해요. 대출 상품, 세금, 법률은 이 도구가 다루지 않아요.";
    const note = offline ? " (출처 서버가 꺼져 있어 출처를 붙이지 못했어요. npm 실행과 함께 api/cite_api.py를 켜 주세요.)" : "";
    setLog((l) => [...l, { who: "bot", text: text + note, cites: cites.length ? cites : undefined, offline }]);
  };

  return (
    <aside className="m-chat" aria-label="질문 창">
      <header><h2>궁금한 것 물어보기</h2><button type="button" className="m-link" onClick={onClose}>닫기</button></header>
      <div className="m-chatlog" aria-live="polite">
        {log.map((m, i) => (
          <div key={i}>
            <p className={`is-${m.who}`}>{m.text}</p>
            {m.cites && (
              <details className="m-cite-box">
                <summary>근거 {m.cites.length}건 보기</summary>
                <ol className="m-cites" aria-label="출처">
                  {m.cites.map((c) => (
                    <li key={c.id}>
                      {c.url ? <a href={c.url} target="_blank" rel="noopener noreferrer">{c.title}</a> : <span>{c.title}</span>}
                      <span className="m-cite-meta"> · {c.publisher}{c.year ? `, ${c.year}` : ""} · {c.type} ({c.id})</span>
                    </li>
                  ))}
                </ol>
              </details>
            )}
          </div>
        ))}
        <div ref={end} />
      </div>
      <div className="m-asks">{ASK.map((a) => <button type="button" key={a} onClick={() => void send(a)}>{a}</button>)}</div>
      <form onSubmit={(e) => { e.preventDefault(); void send(text); }}>
        <label htmlFor="chat-in" className="m-sr">질문</label>
        <input id="chat-in" value={text} onChange={(e) => setText(e.target.value)} placeholder="예: 월세가 얼마예요?" />
        <button type="submit" className="m-btn">보내기</button>
      </form>
    </aside>
  );
}
