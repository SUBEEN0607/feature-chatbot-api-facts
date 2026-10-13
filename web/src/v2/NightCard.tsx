// In-night decision card (interactivity #2): the replay pauses at a decision point; two or three options, each with
// what it gets, its modelled downside and its 가정/근거 tag. In 시연 모드 the card is drawn large for the room.
import { OwnerFace } from "./MonthCard";
import type { SeasonMeta } from "./meta";
import { Tag } from "./parts";
import type { DecisionPoint } from "./types";

export function NightCard({ dp, room, meta, onChoose, busy }: { dp: DecisionPoint; room: boolean; meta: SeasonMeta | null; onChoose: (id: string) => void; busy: boolean }) {
  return (
    <div className={`v2-sheet-wrap ${room ? "v2-room-wrap" : "v2-night-wrap"}`}>
      <section className={`v2-sheet v2-nightcard ${room ? "v2-room" : ""}`} role="dialog" aria-label={dp.title_ko ?? "밤의 결정"} data-testid="night-choice" data-dp={dp.id}>
        <div className="v2-sheet-body">
          <p className="v2-note"><b className="clock">{dp.clock}</b> {dp.title_ko}, 한 달에 이런 일이 약 {dp.monthly_count}번 <Tag tag={dp.count_tag} title="한 달에 몇 번" note="이 상황이 한 달에 몇 번 생기는지는 아직 근거가 없는 추정입니다. 정산에는 이 횟수만큼 반영됩니다." meta={meta} /></p>
          <h2>{dp.prompt_ko}</h2>
          {dp.owner_prompt && <div className="v2-owner" style={{ margin: 0 }}><OwnerFace /><p className="v2-owner-bubble"><span className="who">사장님</span>{dp.owner_prompt}</p></div>}
          <div className={room ? "v2-room-grid" : "v2-nc-grid"} style={{ gridTemplateColumns: `repeat(${dp.options.length}, 1fr)` }}>
            {dp.options.map((o, i) => (
              <div key={o.id} role="button" tabIndex={0} aria-disabled={busy} className={room ? "v2-room-opt" : "v2-nc-opt"} data-night-option={o.id}
                onClick={() => !busy && onChoose(o.id)} onKeyDown={(e) => { if (!busy && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); onChoose(o.id); } }}>
                {room && <span className="k">{String.fromCharCode(65 + i)}</span>}
                <strong>{o.label_ko}</strong>
                <span className="gain">{o.effect_hint_ko}</span>
                <span className="cost"><b>대가</b> {o.downside_ko}</span>
                <span className="tagrow" onClick={(e) => e.stopPropagation()}><Tag tag={o.tag === "근거" && o.source_id ? o.source_id : o.tag} title={o.label_ko} note={o.owner_foresight ?? null} downside={o.downside_ko} meta={meta} />{o.id === dp.default && <span className="v2-note">평소 대응</span>}</span>
              </div>
            ))}
          </div>
          {busy && <p className="v2-note">선택한 대로 남은 밤을 다시 돌리는 중입니다</p>}
        </div>
      </section>
    </div>
  );
}
