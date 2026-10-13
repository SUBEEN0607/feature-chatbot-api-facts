// 사장님에게 묻기: POST {API}/chat; when the API is unreachable, answer offline from the precomputed run.
import { useEffect, useRef, useState } from "react";
import { man, useData, type RunFile } from "../data";
import { API_BASE } from "./parts";

type Msg = { who: "me" | "owner"; text: string; offline?: boolean; sources?: string[] };
// Exactly agents.prewarm.QUESTIONS (web/public/data/chat_presets.json via sync_data.py): same bytes = cache hit.
type Preset = { q: string; shocks: string[] | null; after_choice: boolean };

function relevant(presets: Preset[], shock: string | null, chosen: boolean): Preset[] {
  const forShock = shock ? presets.filter((p) => p.shocks?.includes(shock) && (!p.after_choice || chosen)) : [];
  const general = presets.filter((p) => p.shocks === null);
  return [...forShock, ...general].slice(0, shock ? 6 : 8);
}

function offlineAnswer(run: RunFile | null, baseOp: number): string {
  if (!run) return `지금은 평소대로 장사하는 달입니다. 시뮬레이션으로 보면 한 달 영업이익은 ${man(baseOp)} 정도입니다.`;
  const choice = run.action.id === "absorb" ? "이번 달은 일단 그대로 버텨 보려고 합니다" : `그래서 ${run.action.label.replace(/기$/, "는")} 쪽을 생각하고 있습니다`;
  return `${run.shock.label} 소식을 들었습니다. ${choice}. 시뮬레이션으로 보면 ${run.headline}.`;
}

export function OwnerChat({ run, baseOp, onClose }: { run: RunFile | null; baseOp: number; onClose: () => void }) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const offline = useRef(false);
  // Free typing only when a real model answers: GET /health reports backend; mock or unreachable = chips only.
  const [mode, setMode] = useState<"checking" | "live" | "mock" | "offline">("checking");
  useEffect(() => {
    let cancelled = false;  // StrictMode/unmount cleanup aborts the request; that is not "offline"
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 3000);
    fetch(`${API_BASE}/health`, { signal: ctrl.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d) => {
        if (cancelled) return;
        offline.current = false;
        setMode(d.backend === "mock" ? "mock" : "live");
      })
      .catch(() => {
        if (cancelled) return;
        offline.current = true;
        setMode("offline");
      })
      .finally(() => clearTimeout(timer));
    return () => { cancelled = true; clearTimeout(timer); ctrl.abort(); };
  }, []);
  const presets = useData<Preset[]>("chat_presets.json") ?? [];
  const chips = relevant(presets, run?.shock.id ?? null, Boolean(run && run.action.id !== "absorb"));

  async function send(e?: React.FormEvent, preset?: string) {
    e?.preventDefault();
    const q = preset ?? text.trim();
    if (!q || busy) return;
    if (!preset) setText("");
    setMsgs((m) => [...m, { who: "me", text: q }]);
    setBusy(true);
    const context = { shock: run?.shock.id ?? null, action: run?.action.id ?? null };
    try {
      if (offline.current) throw new Error("offline");
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 15000);
      const r = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ persona: "owner", message: q, context }),
        signal: ctrl.signal,
      });
      clearTimeout(timer);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      const answer: string = d.answer ?? d.reply ?? d.text ?? d.message ?? "";
      if (!answer) throw new Error("empty answer");
      const sources = Array.isArray(d.citations) ? d.citations.map((c: { source_id?: string; doc_id?: string }) => c.source_id ?? c.doc_id).filter(Boolean) : [];
      setMsgs((m) => [...m, { who: "owner", text: answer, sources }]);
    } catch {
      offline.current = true;
      setMsgs((m) => [...m, { who: "owner", text: offlineAnswer(run, baseOp), offline: true }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="g-chat" aria-label="사장님에게 묻기">
      <header>
        <h2>사장님에게 묻기</h2>
        <button className="g-icon-btn" onClick={onClose} aria-label="대화 닫기">닫기</button>
      </header>
      <ol className="g-chat-log" aria-live="polite">
        {msgs.length === 0 && <li className="g-chat-empty">예: 도매가가 오르면 가격을 올리실 건가요?</li>}
        {msgs.map((m, i) => (
          <li key={i} className={`g-msg g-msg-${m.who}`}>
            {m.offline && <span className="g-offline">오프라인 답변: 서버에 연결하지 못해 미리 계산한 결과로 답합니다</span>}
            <p>{m.text}</p>
            {m.sources && m.sources.length > 0 && <span className="g-msg-src">출처 {m.sources.join(", ")}</span>}
          </li>
        ))}
        {busy && <li className="g-msg g-msg-owner g-typing">답을 쓰는 중</li>}
      </ol>
      {chips.length > 0 && (
        <ul className="g-chips" aria-label="자주 묻는 질문">
          {chips.map((c) => (
            <li key={c.q}><button type="button" className="g-chip" disabled={busy} onClick={() => send(undefined, c.q)}>{c.q}</button></li>
          ))}
        </ul>
      )}
      {mode === "live" ? (
        <form onSubmit={send}>
          <input value={text} onChange={(e) => setText(e.target.value)} aria-label="질문" placeholder="사장님에게 물어볼 내용" />
          <button className="g-btn g-btn-primary" disabled={busy || !text.trim()}>보내기</button>
        </form>
      ) : (
        <p className="g-chat-mode" data-testid="chat-mode" data-mode={mode}>
          {mode === "checking" ? "서버 연결을 확인하는 중입니다."
            : mode === "mock" ? "지금은 연습용 응답 모드라 위의 준비된 질문만 받습니다."
            : "서버에 연결되지 않아 위의 준비된 질문에 미리 계산한 결과로 답합니다."}
        </p>
      )}
    </section>
  );
}
