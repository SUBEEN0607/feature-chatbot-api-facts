// Predict, then reveal (interactivity #1): one tap to guess the month's 영업이익 before it plays; the 정산 shows the
// guess against the result and the season end counts the hits.
export type Bucket = { id: string; label: string; lo: number; hi: number };
export const BUCKETS: Bucket[] = [
  { id: "loss", label: "적자", lo: -Infinity, hi: 0 },
  { id: "low", label: "0~100만원", lo: 0, hi: 1_000_000 },
  { id: "mid", label: "100~250만원", lo: 1_000_000, hi: 2_500_000 },
  { id: "high", label: "250만원 넘게", lo: 2_500_000, hi: Infinity },
];
export const bucketOf = (op: number) => BUCKETS.find((b) => op >= b.lo && op < b.hi) ?? BUCKETS[0];

export function GuessSheet({ monthLabel, room, onGuess, onSkip }: { monthLabel: string; room?: boolean; onGuess: (id: string) => void; onSkip: () => void }) {
  return (
    <div className="v2-sheet-wrap">
      <section className={`v2-sheet v2-guess ${room ? "room" : ""}`} role="dialog" aria-label="영업이익 맞히기" data-testid="guess">
        <div className="v2-sheet-body" style={{ paddingBlockStart: 24 }}>
          <h2>{monthLabel} 영업이익은 얼마쯤 나올까요?</h2>
          <p className="v2-note">{room ? "대표님, 하나 골라 주세요. 한 달을 돌린 뒤 정산에서 맞혔는지 봅니다." : "하나 고르면 바로 한 달이 시작됩니다. 정산에서 맞혔는지 봅니다."}</p>
          <div className="v2-guess-grid">
            {BUCKETS.map((b) => (
              <button key={b.id} className={`v2-guess-btn ${b.id === "loss" ? "loss" : ""}`} data-guess={b.id} onClick={() => onGuess(b.id)}>{b.label}</button>
            ))}
          </div>
          <button className="v2-btn quiet" onClick={onSkip} data-testid="guess-skip">맞히지 않고 시작</button>
        </div>
      </section>
    </div>
  );
}

export function GuessResult({ guess, op }: { guess: string | undefined; op: number }) {
  if (!guess) return null;
  const g = BUCKETS.find((b) => b.id === guess)!;
  const hit = bucketOf(op).id === guess;
  return (
    <span className={`sub v2-guess-result ${hit ? "hit" : "miss"}`} data-testid="guess-result" data-hit={hit ? "1" : "0"}>
      예측 {g.label}, 실제 {bucketOf(op).label}: {hit ? "맞혔습니다" : "빗나갔습니다"}
    </span>
  );
}

// What the API stores with the month (POST /play prediction): the bucket and a representative 영업이익 for it.
const MID: Record<string, number> = { loss: -1_000_000, low: 500_000, mid: 1_750_000, high: 3_500_000 };
export function predictionPayload(id: string | null | undefined) {
  if (!id) return undefined;
  const b = BUCKETS.find((x) => x.id === id);
  return b ? { metric: "op", value: MID[id], bucket: id, lo: Number.isFinite(b.lo) ? b.lo : null, hi: Number.isFinite(b.hi) ? b.hi : null } : undefined;
}
