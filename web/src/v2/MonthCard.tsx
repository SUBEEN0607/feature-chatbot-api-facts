// 달력 + 사건 card for the month about to be played, with the owner's reaction to the month's events.
import { Tag } from "./parts";
import type { SeasonMeta } from "./meta";
import type { SeasonEvent } from "./types";

// The owner's first reaction when an event is announced (before the month is played; persona text comes after).
const EVENT_LINES: Record<string, string> = {
  pork_up: "도매가가 또 올랐대요. 가격을 건드릴지 이번 달은 버틸지 고민이에요",
  pork_down: "도매가가 좀 내렸어요. 남는 걸로 버틸지 손님한테 돌려줄지 생각 중이에요",
  import_up: "수입 냉동육이 비싸졌대요. 수입육 쓰는 집들이 힘들겠어요",
  veg_up: "쌈채소값이 확 뛰었어요. 반찬 가짓수가 많으면 그만큼 부담이에요",
  rent_renewal: "재계약 때 월세를 올려 달래요. 한 번 오르면 안 내려가요",
  festival_week: "축제 주간이라 저녁에 사람이 몰릴 거예요. 줄 서다 돌아가는 손님이 없게 해야죠",
  exam_week: "시험 기간이라 학생들이 일찍 들어가요. 늦은 밤 테이블이 비겠네요",
  rain_week: "비 오는 주간이라 야장을 접어야겠네요",
  cold_wave: "한파가 온대요. 이런 날은 다들 집에 일찍 가요",
  competitor_open: "길 건너에 고깃집이 새로 생겼어요. 처음 몇 달은 손님을 나눠 가질 거예요",
  competitor_close: "근처 고깃집이 문을 닫았대요. 그쪽 손님이 좀 넘어올 수도 있어요",
  viral_blog: "블로거가 다녀갔대요. 이번 주에 손님이 몰릴 수도 있어요",
  bad_review: "악성 리뷰가 하나 달렸어요. 좋은 리뷰로 덮일 때까지 평점이 내려가 있겠죠",
  hygiene_inspection: "위생점검 나온대요. 평소에 치워 둔 만큼 결과가 나와요",
  noise_complaint: "야장 때문에 소음 민원이 들어왔어요. 당분간 야장을 덜 펴야겠어요",
  staff_quit: "알바 한 명이 갑자기 그만뒀어요. 당분간 제가 더 뛰어야겠네요",
  owner_sick: "몸살이 나서 며칠 문을 닫아야 할 것 같아요",
  aged_spoilage: "숙성 고기 상태가 들쭉날쭉해요. 이번 달은 버리는 고기가 좀 나오겠어요",
};

export function eventsOf(ids: string[], meta: SeasonMeta | null): SeasonEvent[] {
  return ids.map((id) => {
    const e = meta?.events[id];
    return { id, label: e?.label ?? id, group: e?.group, mechanism: e?.mechanism, tag: e?.tag ?? "가정" };
  });
}

export function ownerOpening(events: SeasonEvent[], calNote?: string): string {
  if (!events.length) return calNote ? `이번 달은 ${calNote.replace(/[.]$/, "")}. 계획만 잘 세우면 돼요` : "별일 없는 달이에요. 계획만 잘 세우면 돼요";
  return events.map((e) => EVENT_LINES[e.id] ?? `${e.label} 소식이 있네요`).join(". ");
}

export function OwnerFace() {
  return (
    <svg className="v2-owner-face" viewBox="0 0 40 40" aria-hidden="true">
      <circle cx="20" cy="20" r="20" fill="oklch(0.94 0.02 60)" />
      <path d="M8 40c1-8 6-12 12-12s11 4 12 12z" fill="oklch(0.97 0.004 90)" />
      <path d="M14 40l1-9h10l1 9z" fill="oklch(0.5 0.17 30)" />
      <circle cx="20" cy="18" r="7.5" fill="oklch(0.85 0.05 60)" />
      <path d="M12.3 15.5c1-5 4-7 7.7-7s6.7 2 7.7 7z" fill="oklch(0.22 0.02 40)" />
      <rect x="12" y="13.6" width="16" height="3" rx="1.5" fill="oklch(0.5 0.17 30)" />
    </svg>
  );
}

export function MonthCard({ label, note, demandIndex, calTag, events, meta, ownerText, onAsk, children }: {
  label: string; note?: string; demandIndex?: number; calTag?: string; events: SeasonEvent[]; meta: SeasonMeta | null; ownerText: string;
  onAsk?: () => void; children?: React.ReactNode;
}) {
  return (
    <aside className="v2-right" aria-label="이번 달 달력과 사건">
      <div className="v2-scroll">
        <div className="v2-cal">
          <span className="m">{label}</span>
          {note && <p className="note">{note}</p>}
          {demandIndex != null && (
            <span className="idx">수요 지수 {demandIndex.toFixed(2)} (10월 = 1.00) <Tag tag={calTag ?? "S12;가정"} title="달력 수요 지수"
              note="서울시 상권분석 3120012 한식 카드매출의 분기 수준 (S12). 분기를 달로 나눈 비율은 가정입니다." meta={meta} /></span>
          )}
        </div>
        <div className="v2-events" data-testid="events">
          <h3 style={{ fontSize: 13, fontWeight: 750 }}>이번 달 사건</h3>
          {events.length === 0 && <p className="v2-note">이번 달 바깥 사건은 없습니다. 달력의 계절 수요만 반영됩니다.</p>}
          {events.map((e) => (
            <div className="v2-event" key={e.id} data-event={e.id}>
              <span className="t">{e.label} <Tag tag={e.tag} title={e.label} note={e.mechanism} meta={meta} /></span>
              {e.group && <span className="g">{e.group}</span>}
              {e.mechanism && <p>{e.mechanism}</p>}
            </div>
          ))}
        </div>
        <div className="v2-owner">
          <OwnerFace />
          <p className="v2-owner-bubble"><span className="who">사장님</span>{ownerText}</p>
        </div>
        {onAsk && <div style={{ padding: "0 18px 16px" }}><button className="v2-btn" onClick={onAsk} data-testid="ask-owner">사장님에게 묻기</button></div>}
        {children}
      </div>
    </aside>
  );
}
