// Mock assistant: answers a fixed set of questions from the numbers already on screen. No model is called.
import { useEffect, useRef, useState } from "react";
import { guStat, iga, man, openingCost, rankOf, simulate, type Gu, type Levers, type Profile, type ShockId, type Store } from "./model";

type Msg = { who: "me" | "bot"; text: string };
const ASK = ["몇 달째부터 남기 시작해요?", "돈이 제일 많이 드는 곳은 어디예요?", "하루에 몇 명 받아야 본전이에요?", "이 동네 경쟁은 어때요?"];

export default function Chat({ profile, store, levers, shocks, gus, onClose }: {
  profile: Profile; store: Store; levers: Levers; shocks: ShockId[]; gus: Gu[]; onClose: () => void;
}) {
  const [log, setLog] = useState<Msg[]>([{ who: "bot", text: "화면에 나온 계산을 풀어서 설명해 드려요. 아래 질문을 누르거나 직접 적어 보세요." }]);
  const [text, setText] = useState("");
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ block: "end" }); }, [log]);

  const answer = (q: string): string => {
    const run = simulate(profile, store, levers, shocks);
    const st = guStat(profile.gu);
    if (/남기|흑자|언제/.test(q)) {
      const r = run.rows.find((x) => x.op - 300 >= 0);
      return r ? `지금 조건이면 ${r.m}개월째부터 사장님 생활비 300만원을 빼고도 남아요. 그달 영업이익은 ${man(r.op)}이에요. 오픈 직후에는 손님이 자리 잡은 뒤의 55%만 온다고 가정했어요.`
        : `6개월 안에는 사장님 생활비까지 벌지 못해요. 6개월째 영업이익이 ${man(run.rows[5].op)}이에요.`;
    }
    if (/많이 드는|비용|돈이/.test(q)) {
      const top = [...openingCost(store, profile.gu).lines].sort((a, b) => b.amount - a.amount);
      return `여는 데 드는 ${man(run.opening)} 가운데 ${iga(top[0].label)} ${man(top[0].amount)}으로 가장 커요. 그다음이 ${top[1].label} ${man(top[1].amount)}이에요.`;
    }
    if (/본전|몇 명|손익/.test(q)) {
      const ticket = levers.price + 8000;
      const fixed = levers.staff * 199 + st.rent * store.pyeong + 12.8 * store.pyeong + 300;
      const perCover = (ticket * levers.days * (1 - 0.31 * (19000 / levers.price) - 0.0084)) / 10000;
      return `하루 ${Math.ceil(fixed / perCover)}명쯤 받아야 사장님 생활비까지 나와요. 한 달 고정비 ${man(fixed)}을 손님 한 명이 남기는 돈으로 나눈 값이에요.`;
    }
    if (/경쟁|고깃집 수|옆 가게/.test(q)) {
      return `${profile.gu}에는 돼지고기 구이 가게가 ${st.pork.toLocaleString("ko-KR")}곳 있고, 25개 구 중 ${rankOf(profile.gu, "pork", gus.map((g) => g.name))}번째로 많아요 (소상공인 상가정보 2026년 6월). 한식음식점 전체로 보면 2025년 한 해에 ${st.closure}%가 문을 닫았어요.`;
    }
    if (/월세|임대/.test(q)) return `${profile.gu}의 평당 월세는 ${st.rent}만원으로 잡았어요. ${store.pyeong}평이면 한 달 ${man(st.rent * store.pyeong)}이에요. 예시값이에요.`;
    return "목업에서는 아래 네 가지 질문과 월세 질문에만 답해요. 대출 상품, 세금, 법률은 이 도구가 다루지 않아요.";
  };
  const send = (q: string) => {
    if (!q.trim()) return;
    setLog((l) => [...l, { who: "me", text: q.trim() }, { who: "bot", text: answer(q) }]);
    setText("");
  };

  return (
    <aside className="m-chat" aria-label="질문 창">
      <header><h2>궁금한 것 물어보기</h2><button type="button" className="m-link" onClick={onClose}>닫기</button></header>
      <div className="m-chatlog" aria-live="polite">
        {log.map((m, i) => <p key={i} className={`is-${m.who}`}>{m.text}</p>)}
        <div ref={end} />
      </div>
      <div className="m-asks">{ASK.map((a) => <button type="button" key={a} onClick={() => send(a)}>{a}</button>)}</div>
      <form onSubmit={(e) => { e.preventDefault(); send(text); }}>
        <label htmlFor="chat-in" className="m-sr">질문</label>
        <input id="chat-in" value={text} onChange={(e) => setText(e.target.value)} placeholder="예: 월세가 얼마예요?" />
        <button type="submit" className="m-btn">보내기</button>
      </form>
    </aside>
  );
}
