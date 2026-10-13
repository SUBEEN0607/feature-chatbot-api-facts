// Level select: the real 대학로 상권 map. "가게로 들어가기" zooms into the (symbolic) hero marker.
import { useRef, useState } from "react";
import type { District } from "../data";
import { DistrictMap } from "../shared/components";

export function MapIntro({ district, resume, onEnter }: { district: District; resume: boolean; onEnter: () => void }) {
  const box = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState<string | null>(null);
  const p = district.profile;
  function enter() {
    const hero = box.current?.querySelector(".dm-hero") as SVGCircleElement | null;
    const rect = box.current?.getBoundingClientRect();
    if (!hero || !rect || matchMedia("(prefers-reduced-motion: reduce)").matches) return onEnter();
    const h = hero.getBoundingClientRect();
    setZoom(`${h.left + h.width / 2 - rect.left}px ${h.top + h.height / 2 - rect.top}px`);
    setTimeout(onEnter, 650);
  }
  return (
    <div className="g-map">
      <div ref={box} className={`g-map-canvas ${zoom ? "is-zooming" : ""}`} style={zoom ? { transformOrigin: zoom } : undefined}>
        <DistrictMap district={district} className="dm g-dm" heroLabel="상징 위치" />
      </div>
      <div className="g-map-copy">
        <p className="g-step">대학로(혜화역) 상권</p>
        <h1>대학로 삼겹살집, 한 달씩 운영해 보기</h1>
        <p>
          한식당 {p.hansik_stores}곳, 돼지고기 구이집 {p.pork_stores}곳이 모인 거리에 합성 매장 하나를 세웠습니다.
          매달 생기는 사건에 사장님이 어떻게 대응하는지 고르고, 시뮬레이션으로 한 달을 돌려 봅니다.
        </p>
        <button className="g-btn g-btn-primary g-btn-big" onClick={enter}>{resume ? "가게로 돌아가기" : "가게로 들어가기"}</button>
        <p className="g-fine">숫자는 공공데이터와 검토 전 추정값으로 만든 예시입니다. 매장 위치는 상징입니다.</p>
      </div>
      <ul className="g-map-legend" aria-label="지도 범례">
        <li><i className="lg-hero" />합성 매장</li>
        <li><i className="lg-pork" />돼지고기 구이집</li>
        <li><i className="lg-other" />소고기·곱창집</li>
        <li><i className="lg-hansik" />그 밖의 한식당</li>
      </ul>
    </div>
  );
}
