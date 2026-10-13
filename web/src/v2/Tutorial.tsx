// Three-step coach marks for the first month of free play. Points at real elements; Esc or 건너뛰기 ends it.
import { useEffect, useLayoutEffect, useState } from "react";

const STEPS = [
  { sel: "[data-testid=plan-board] .v2-scroll", text: "여기가 운영 계획판입니다. 가격, 원육, 인력, 영업시간 같은 레버마다 얻는 것과 대가가 적혀 있습니다. 가정 표시를 누르면 그 숫자의 이유가 나옵니다." },
  { sel: "[data-testid=preview]", text: "레버를 움직일 때마다 이 달의 예상 영업이익이 바로 다시 계산됩니다. 가게 안의 메뉴판 가격과 직원 수도 같이 바뀝니다." },
  { sel: ".v2-hud-cash", text: "현금이 두 달 연속 0 아래로 내려가면 폐업입니다. 6개월을 버티고, 평소 계획보다 더 많은 현금을 남기면 이깁니다." },
];

export function Tutorial({ onDone }: { onDone: () => void }) {
  const [i, setI] = useState(0);
  const [rect, setRect] = useState<DOMRect | null>(null);
  useLayoutEffect(() => {
    const el = document.querySelector(STEPS[i].sel);
    const upd = () => setRect(el?.getBoundingClientRect() ?? null);
    upd();
    addEventListener("resize", upd);
    return () => removeEventListener("resize", upd);
  }, [i]);
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onDone();
    addEventListener("keydown", k);
    return () => removeEventListener("keydown", k);
  }, [onDone]);
  if (!rect) return null;
  const right = rect.right + 320 < innerWidth;
  const box = right ? { left: rect.right + 16, top: Math.max(16, Math.min(innerHeight - 220, rect.top)) }
    : { left: Math.max(16, Math.min(innerWidth - 316, rect.left)), top: Math.min(innerHeight - 220, rect.bottom + 16) };
  return (
    <>
      <div className="v2-spot" style={{ top: rect.top - 4, left: rect.left - 4, width: rect.width + 8, height: rect.height + 8 }} />
      <div className="v2-coach" role="dialog" aria-label="사용 안내" style={box} data-testid="tutorial">
        <span className="n">{i + 1} / {STEPS.length}</span>
        <p>{STEPS[i].text}</p>
        <div className="row">
          <button className="v2-btn quiet" onClick={onDone}>건너뛰기</button>
          <button className="v2-btn" onClick={() => (i < STEPS.length - 1 ? setI(i + 1) : onDone())}>{i < STEPS.length - 1 ? "다음" : "시작하기"}</button>
        </div>
      </div>
    </>
  );
}
