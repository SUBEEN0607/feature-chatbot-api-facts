"""Build research/guesstimate.xlsx, research/hero_base.yaml and research/shocks.yaml for the composite hero store.

Source of truth:
  - ontology/criteria.csv, ontology/edges.csv, ontology/sources.csv  (the ontology)
  - HERO, BENCHMARKS, SHOCKS below                                   (seed values, all illustrative)

Run:
  .venv/bin/python research/build_workbook.py                  # build xlsx + yaml from this file
  .venv/bin/python research/build_workbook.py --force          # overwrite even if members have reviewed rows
  .venv/bin/python research/build_workbook.py --yaml-from-xlsx # re-export both yamls from a member-edited xlsx
  .venv/bin/python research/build_workbook.py --apply-patch research/review/accepted_patch.yaml
      # apply reviewed rows (AI-helper patch or interview patch); every change is logged in the ChangeLog sheet
  .venv/bin/python research/build_workbook.py --apply-patch research/interview/T01/accepted_patch.yaml \
      --out research/interview/T01        # a second twin: writes guesstimate.xlsx / hero_base.yaml / shocks.yaml there

The P&L sheet is live Excel formulas over HeroStore base values (defined names v_<criterion_id>).
compute_pnl() mirrors those formulas in Python so the yaml carries the same derived numbers.
No network, no paid APIs.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import yaml
from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName

ROOT = Path(__file__).resolve().parents[1]
ONT = ROOT / "ontology"
OUT_XLSX = ROOT / "research" / "guesstimate.xlsx"
OUT_YAML = ROOT / "research" / "hero_base.yaml"
OUT_SHOCKS = ROOT / "research" / "shocks.yaml"

FONT = "맑은 고딕"
BLUE, BLACK = "0000FF", "000000"
YELLOW = PatternFill("solid", fgColor="FFF2CC")
HEAD = PatternFill("solid", fgColor="D9D9D9")
SECTION = PatternFill("solid", fgColor="EDEDED")
THIN = Border(bottom=Side(style="thin", color="BFBFBF"))
WON = '"₩"#,##0'
PCT = "0.0%"
PP = '+0.0"pp";-0.0"pp";0.0"pp"'

GUESS_NOTE = "ILLUSTRATIVE 예시 추정치 (검토 필요)"
PUBLIC_NOTE = "공공데이터/공식 수치"
PENDING_NOTE = "대기 (파이프라인 또는 인터뷰로 채움)"

# ---------------------------------------------------------------------------------------------
# HERO: one row per non-derived, non-label criterion. (criterion_id, low, base, high,
# reasoning_chain, source_id, confidence). None = not filled yet. Every number here is a guess
# unless method=public in criteria.csv. A blank source_id is allowed only with confidence L.
# ---------------------------------------------------------------------------------------------
HERO = [
    ("drv_dwell_time", 75, 105, 140, "국내 측정 없음. 고기 무한리필 체인 이용시간 상한 100~120분(S71), 미국 캐주얼 평균 47분(S72) 사이에서 굽기·음주로 길다고 보고 105분 유지", "S71;S72;S73", "L"),
    ("drv_balk_rate", 0.003, 0.01, 0.05, "시뮬레이션 기준 달의 대기 이탈 손님 비율 ≈1% (python -m sim.calibrate; 인내 25분, 19~21시 피크 가정 반영); 5%는 피크 가정 상한", "", "L"),
    ("drv_open_hours", 6, 7, 9, "17:00–24:00 = 7h; 대학로 한식 매출 63%가 17–24시(S12); 저녁 전용 삼겹살집 6h 사례(S35)", "S12;S35", "M"),
    ("drv_rent", 3000000, 4700000, 5800000, "R-ONE 혜화동 소규모 상가 1층 ₩60,033/㎡/월(2026Q2, 보증금 환산 포함) × 82.64㎡(25평) ÷ 1.0623(보증금 = 월세 10배 가정, 전환율 7.481%) ≈ ₩467만 현금 월세", "S52;S53;S55", "M"),
    ("prd_meat_origin", "수입", "국내산", "국내산", "대학가 독립점 국내산 삼겹살 가정; 원산지 표시는 인터뷰로 확인", "", "L"),
    ("prd_cut_style", "냉삼/대패", "일반 생삼겹", "숙성/통삼", "대학가 저가~중가 독립점의 일반형 가정", "", "L"),
    ("prd_chobeol", "N", "N", "Y", "생고기 자가 굽기 가정 (초벌은 차별화 옵션)", "", "L"),
    ("prd_signature_side", "없음", "없음", "미나리", "composite 기본형 = 시그니처 없음", "", "L"),
    ("prd_food_quality", None, None, None, "인터뷰/방문 평가로 채움", "S03", "L"),
    ("prd_meat_price", 17000, 19000, 21321, "서울 평균 200g ₩21,321(참가격 2026-06) ~ 골목 ₩17,000(마포 2026-03) → 대학가 독립점 ₩19,000", "S23;S25", "M"),
    ("prd_portion_grams", 150, 200, 200, "참가격 기준 200g; 골목점은 150–180g도 있음", "S23", "M"),
    ("prd_portions_per_cover", 0.8, 1.0, 1.5, "2인 2인분 + 소주 → 1인 1인분 (쿠키뉴스 예시); 성인 남성 4명 6~12인분 일화(S74)로 상한 1.5", "S28;S74", "L"),
    ("prd_alcohol_price", 4000, 5000, 6000, "마포 2026 소주 ₩4,000–6,000의 중간", "S25;S26", "M"),
    ("prd_alcohol_per_cover", 0.6, 0.9, 1.2, "음주자 1회 평균 소주 6.1잔(50ml) ≈ 0.85병(S62); 비음주 손님과 소맥을 감안해 0.9병", "S62", "L"),
    ("prd_side_spend_per_cover", 2000, 3500, 5000, "식사(냉면·된장 ₩7,000) × 주문률 0.5 = ₩3,500; 식사 비중 15%(블로그) 대조", "S30", "L"),
    ("prd_menu_count", 6, 8, 12, "고기 3–4종 + 식사 2–3종 + 사이드 1–2종 (출처 없음)", "", "L"),
    ("svc_staff_grilling", "N", "N", "Y", "대학가 저가 독립점은 자가 굽기 가정", "", "L"),
    ("svc_banchan_count", 3, 5, 8, "쌈채소·파절이·김치·쌈장·계란찜 가정", "", "L"),
    ("cst_banchan_cost_per_cover", 800, 1200, 1800, "출처 없음. 처음에는 KREI 식재료 37%에서 옛 고기 원가(₩6,500)를 뺀 잔여로 역산한 값이라 고기 원가 교체 후 근거가 없음; 사장님 인터뷰로 확인", "", "L"),
    ("svc_qr_kiosk", "N", "N", "N", "미도입 정의상 N (기술 도입은 이번 과제 범위 밖)", "D0930", "H"),
    ("svc_corkage", "N", "N", "Y", "대학가 소주 중심 매장은 콜키지 없음 가정", "", "L"),
    ("svc_cleanliness", None, None, None, "방문 점검/인터뷰로 채움", "", "L"),
    ("mkt_review_count", None, None, None, "composite라 실리뷰 없음; 비교 매장 수기 입력만 (스크래핑 금지)", "S03;S06", "L"),
    ("mkt_review_rating", None, None, None, "composite라 실리뷰 없음; 인터뷰 매장 기준 수기 입력", "S03", "L"),
    ("mkt_review_event", "N", "N", "Y", "미도입 composite 기본형 = 없음 (인터뷰로 확인)", "", "L"),
    ("mkt_sponsorship", "N", "N", "Y", "미도입 composite 기본형 = 없음 (인터뷰로 확인)", "", "L"),
    ("mkt_celebrity_visits", 0, 0, 0.01, "composite 기본형 = 0 (인터뷰로 확인)", "", "L"),
    ("mkt_waitlist_app", "N", "N", "N", "미도입 정의상 N", "D0930", "H"),
    ("mkt_delivery", "N", "N", "N", "미도입 정의상 N (배달 플랫폼 미사용)", "D0930", "H"),
    ("mkt_price_elasticity", -0.3, -0.81, -2.5, "−0.81은 외식(FAFH) 범주 수준의 메타분석 평균(S58)이고 한국 음식서비스 범주는 유의하지 않음(S59, 하한 −0.3). 근처 고깃집 27곳 중 한 매장의 탄력성은 범주보다 클 것이라 상한을 −2.5로 넓힘 (매장 수준 값은 출처 없음)", "S58;S59", "L"),
    ("mkt_party_size", 2.2, 2.8, 3.5, "국내 일행 분포 없음. 미국 캐주얼 평균 2.61(S72); 대학로 21~24시 결제 1건 ₩60,464 ÷ 1인 ₩2.8만 ≥ 2.2명 → 2.8 유지 (민감도 분석은 SIMULATION.md)", "S72;S12", "L"),
    ("mkt_patience", 10, 25, 35, "손님 72%가 30분 넘게 기다리지 않음(S60) → Gamma(형상 4)에서 P(≤30분)=0.72인 평균 ≈ 24.5분", "S60;S61", "L"),
    # Customer segments (relative factors; the sim pins each store-wide mean to its base parameter above).
    ("seg_twenties_party_factor", 0.8, 0.9, 1.0, "20대 친구 모임은 2~3명이 많다고 가정 (출처 없음)", "", "L"),
    ("seg_twenties_dwell_factor", 0.9, 1.05, 1.2, "대화·2차 전 체류가 길다고 가정 (출처 없음)", "", "L"),
    ("seg_twenties_alcohol_factor", 0.9, 1.1, 1.3, "평균보다 약간 더 마신다고 가정 (출처 없음)", "", "L"),
    ("seg_twenties_patience_factor", 1.0, 1.3, 1.6, "소문난 집이면 더 오래 기다린다고 가정 (출처 없음)", "", "L"),
    ("seg_twenties_early_mult", 0.4, 0.6, 0.9, "수업·알바 뒤 늦게 온다고 가정 (출처 없음)", "", "L"),
    ("seg_twenties_late_mult", 1.2, 1.6, 2.0, "21시 이후 비중이 높다고 가정 (출처 없음)", "", "L"),
    ("seg_office_party_factor", 1.1, 1.25, 1.4, "회식은 3~4명 테이블이 많다고 가정 (출처 없음)", "", "L"),
    ("seg_office_dwell_factor", 1.0, 1.15, 1.35, "회식은 오래 앉아 있다고 가정 (출처 없음)", "", "L"),
    ("seg_office_alcohol_factor", 1.1, 1.3, 1.6, "회식 음주량이 가장 많다고 가정 (출처 없음)", "", "L"),
    ("seg_office_patience_factor", 0.5, 0.7, 0.9, "단체는 바로 다른 집으로 옮긴다고 가정 (출처 없음)", "", "L"),
    ("seg_office_early_mult", 0.7, 0.9, 1.1, "퇴근 직후 18~19시 도착 가정 (출처 없음)", "", "L"),
    ("seg_office_late_mult", 0.8, 1.0, 1.2, "21시 이후는 평균 수준 가정 (출처 없음)", "", "L"),
    ("seg_family_party_factor", 0.95, 1.05, 1.2, "부모와 자녀 3~4명 가정 (출처 없음)", "", "L"),
    ("seg_family_dwell_factor", 0.7, 0.8, 0.95, "식사 위주라 빨리 일어난다고 가정 (출처 없음)", "", "L"),
    ("seg_family_alcohol_factor", 0.2, 0.4, 0.7, "음주가 적다고 가정 (출처 없음)", "", "L"),
    ("seg_family_patience_factor", 0.7, 0.9, 1.1, "아이와 함께라 오래 못 기다린다고 가정 (출처 없음)", "", "L"),
    ("seg_family_early_mult", 1.3, 1.8, 2.3, "이른 저녁 식사 가정 (출처 없음)", "", "L"),
    ("seg_family_late_mult", 0.1, 0.3, 0.5, "21시 이후는 드물다고 가정 (출처 없음)", "", "L"),
    ("reg_age_mix", None, 0.28, None, "대학로 2025 한식 매출 20대 28% (30대 25%)", "S12", "H"),
    ("reg_evening_share", 0.62, 0.63, 0.64, "대학로 한식 17–24시 매출 비중 62–64% (2026-09-30 실측)", "S12", "H"),
    ("reg_foot_traffic", None, None, None, "파이프라인(OA-15568)이 채움", "S14", "L"),
    ("reg_trade_area_facilities", None, None, None, "파이프라인(OA-15580 UNIV_CO, SUBWAY_STATN_CO)이 채움", "S17", "L"),
    ("reg_worker_pop", None, None, None, "파이프라인(OA-15569)이 채움", "S16", "L"),
    ("reg_competitors", None, 27, None, "3120012 경계 안 I20107 27개 (지점명 있는 6개 제외 시 독립 ~20)", "S20;S18", "H"),
    ("cst_meat_cost_per_portion", 3700, 4500, 5200, "KMTA 냉장 삼겹 공장출고 2026년 1~9월 평균 ₩18,647/kg × 0.2kg = ₩3,729 + 유통·손질 손실 15~25% 가정(출처 없음) ≈ ₩4,500; 상한은 소매가 ₩2,559/100g × 2 = ₩5,118", "S68;S69", "M"),
    ("cst_alcohol_cost_per_bottle", 1400, 1600, 1800, "₩6,000 판매 시 마진 ₩4,400 → 원가 ₩1,600 (2023)", "S27", "M"),
    ("cst_side_cost_ratio", 0.30, 0.35, 0.45, "식사류 원가율 30–45% 가정 (출처 없음)", "", "L"),
    ("cst_employee_wage", 2156880, 2400000, 3000000, "최저임금 209h ₩2,156,880 하한 + 주방 경력 가산", "S36", "L"),
    ("cst_owner_imputed_wage", 2156880, 3000000, 3700000, "KREI 대표자 인건비 영업비용의 14.9%(2022) × ≈₩2,500만 ≈ ₩370만 상한; 최저임금 풀타임 하한", "S32;S36", "L"),
    ("cst_holiday_pay_factor", 1.2, 1.33, 1.43, "주휴 1.20(주 15시간 이상) × 사업주 4대보험 1.108(국민연금 4.75, 건강 3.595, 장기요양, 산재, 고용) ≈ 1.33; 상한은 퇴직금 적립 1/12 추가", "S36;S66;S67", "M"),
    ("cst_utilities", 1200000, 1700000, 2300000, "숯·가스·전기·수도; KREI 잔여 비용(매출 14%) 중 약 6%", "S31", "L"),
    ("cst_other_opex", 1000000, 1500000, 2200000, "소모품·세탁·보험·세무·마케팅; KREI 잔여 비용 중 약 5.5%", "S31", "L"),
    ("cst_card_share", 0.80, 0.88, 0.95, "한국은행 지급수단 조사: 카드 결제 건수 비중 75.5%(S65); 저녁 객단가가 커서 카드 비중이 더 높다고 보고 88%", "S65", "M"),
    ("cst_card_fee_rate", 0.004, 0.0095, 0.0115, "연매출 3억~5억 구간 우대수수료 신용 1.00%·체크 0.75%(S63) × 신용:체크 74:26(S65) = 0.935% → 간편결제 감안 0.95%", "S63;S65", "H"),
    ("sto_area_pyeong", 18, 25, 35, "30평 15테이블 사례(S34)보다 작은 골목 독립점; 인허가 소재지면적 중앙값으로 교체 예정", "S34;S21", "L"),
    ("sto_tables", 8, 10, 14, "25평 ≈ 30평/15테이블(S34) 비례 12 → 주방·통로 감안 10", "S34", "L"),
    ("sto_seats_per_table", 4, 4, 4, "60석 ÷ 15테이블 = 4", "S34", "M"),
    ("sto_terrace", 0, 8, 12, "야장 2테이블 × 4석 가정 (출처 없음)", "", "L"),
    ("sto_terrace_availability", 0, 0.4, 0.6, "봄·가을 영업, 비·겨울 제외 → 월평균 40% 가정", "", "L"),
    ("wx_rain_nights_share", 0, 0, 0.35, "기준 달은 날씨를 야장 가용률에만 반영해 0. 비 충격 SH10은 기상청 10월 전국 평년 강수일수 5.9일 ÷ 31일 = 0.19 (2024년 10월은 11일 = 0.35)", "S75", "H"),
    ("wx_rain_arrival_effect", -0.15, -0.10, -0.05, "비 오는 밤 거리 유입 10% 감소 가정 (출처 없음)", "", "L"),
    ("sto_occupancy", 0.6, 0.7, 0.8, "일행 2.8명 ÷ 4인석 = 0.70", "", "L"),
    ("sto_table_turns", 0.9, 1.25, 2.0, "주말 ~2회 + 평일 ~1회 → 요일 평균 1.25; '3회+'는 미검증 블로그(S30) 상한 참고", "S30", "L"),
    ("sto_open_days", 24, 26, 30, "주 1회 휴무 가정", "", "L"),
    ("sto_parttimers", 1, 2, 3, "KREI 육류구이 평균 종사자 3.2명: 대표 + 정직원 1 + 교대당 알바 2", "S31", "L"),
    ("sto_parttime_wage", None, 10320, None, "2026 최저임금 ₩10,320", "S36", "H"),
    ("sto_parttime_shift_hours", 4, 5, 7, "피크 18–23시 커버 가정", "", "L"),
    ("sto_employees", 0, 1, 2, "KREI 평균 3.2명 중 대표·알바 제외 1명", "S31", "L"),
    ("sto_wifi", "N", "Y", "Y", "대부분 매장 제공 가정 (BBQ에서는 영향 작음)", "", "L"),
    ("sto_franchise", "개인", "개인", "개인", "hero = 독립점 (범위 정의); 지구 모집단은 지점명으로 구분", "D0930;S20", "H"),
]

# (bench_id, name_ko, low, value, high, unit, basis, source_id, note). A str value starting with
# "=" is a formula; {BMxx} is replaced by that benchmark's value cell.
BENCHMARKS = [
    ("BM01", "대학로 한식 연 카드매출 (2025)", None, 59090000000, None, "₩/년", "3120012 × CS100001, 2025 4개 분기 합", "S12", "2026-09-30 실측(파이프라인); 연구 파일 반올림 ₩591억"),
    ("BM02", "대학로 한식 점포수 (2025Q4)", None, 191, None, "개", "3120012 × CS100001", "S13", "프랜차이즈 31"),
    ("BM03", "점포당 월매출 앵커", None, "={BM01}/{BM02}/12", None, "₩/월", "BM01 ÷ BM02 ÷ 12", "S12;S13", "보정 목표 (≈₩2,580만)"),
    ("BM04", "소형 독립 삼겹살집 월매출 prior", 20000000, None, 50000000, "₩/월", "전국 평균·사례 기반 working prior", "S33;S34;S35", "서울 돼지고기 통계로는 미검증"),
    ("BM05", "전국 육류구이 연매출 (2018)", None, 225600000, None, "₩/년", "KREI 한식 육류요리전문점", "S31", ""),
    ("BM06", "전국 육류구이 월매출 (2018)", None, "={BM05}/12", None, "₩/월", "BM05 ÷ 12", "S31", "≈₩1,880만"),
    ("BM07", "대학로 한식 저녁(17–24) 매출 비중", 0.62, 0.63, 0.64, "비율", "2025", "S12", ""),
    ("BM08", "대학로 한식 20대 매출 비중", None, 0.28, None, "비율", "2025", "S12", "연령·성별 합계는 법인카드 제외"),
    ("BM09", "대학로 한식 30대 매출 비중", None, 0.25, None, "비율", "2025", "S12", ""),
    ("BM10", "대학로 돼지고기 구이(I20107) 점포수", None, 27, None, "개", "상권 경계 내 점포 좌표", "S20;S18", "지점명 있는 6개"),
    ("BM11", "KREI 육류구이 영업이익률", None, 0.094, None, "매출 대비", "2018, 전국", "S31", "대표자 귀속 인건비 차감 후"),
    ("BM12", "KREI 식재료비 (영업비용 대비)", None, 0.410, None, "비용 대비", "2018, 전국", "S31", ""),
    ("BM13", "KREI 식재료비 (매출 대비)", None, "={BM12}*(1-{BM11})", None, "매출 대비", "비용 비중 × (1 − 영업이익률)", "S31", "≈37%"),
    ("BM14", "KREI 인건비 (영업비용 대비)", None, 0.342, None, "비용 대비", "2018, 전국", "S31", ""),
    ("BM15", "KREI 인건비 (매출 대비)", None, "={BM14}*(1-{BM11})", None, "매출 대비", "비용 비중 × (1 − 영업이익률)", "S31", "≈31%"),
    ("BM16", "KREI 임차료 (영업비용 대비)", None, 0.093, None, "비용 대비", "2018, 전국", "S31", ""),
    ("BM17", "KREI 임차료 (매출 대비)", None, "={BM16}*(1-{BM11})", None, "매출 대비", "비용 비중 × (1 − 영업이익률)", "S31", "≈8.4%"),
    ("BM18", "KREI 기타 비용 (영업비용 대비)", None, "=1-{BM12}-{BM14}-{BM16}", None, "비용 대비", "잔여 = 관리비·수수료·기타", "S31", "파생값"),
    ("BM19", "KREI 기타 비용 (매출 대비)", None, "={BM18}*(1-{BM11})", None, "매출 대비", "비용 비중 × (1 − 영업이익률)", "S31", "≈14%"),
    ("BM20", "외식업 대표자 인건비 (영업비용 대비, 2022)", None, 0.149, None, "비용 대비", "전체 외식", "S32", "고용인 14.8%, 가족 3.5%"),
    ("BM21", "참가격 삼겹살 200g 서울 (2026-06)", None, 21321, None, "₩/200g", "외식비 공시", "S23", "전년 대비 +4.3%"),
    ("BM22", "참가격 삼겹살 200g 서울 (2026-01)", None, 21056, None, "₩/200g", "외식비 공시", "S24", ""),
    ("BM23", "골목 삼겹살집 가격 (마포 2026-03)", None, 17000, None, "₩/200g", "기사 사례", "S25", "기사 원문: 1인분(200g) 기준 1만7000원 안팎"),
    ("BM24", "소주 판매가 (마포 2026)", 4000, None, 6000, "₩/병", "기사 사례", "S25", ""),
    ("BM25", "소주 판매가 (강남 2023)", 7000, None, 8000, "₩/병", "기사 사례", "S26", ""),
    ("BM26", "소주 식당 마진 (₩6,000 판매 시)", None, 4400, None, "₩/병", "마진율 73.4%", "S27", "원가 ≈₩1,600"),
    ("BM27", "객단가 (주류 포함)", 28000, None, 40000, "₩/인", "연구 파일 파생값", "S25;S28", "2인 2인분 + 소주 = ₩5만+"),
    ("BM28", "주류 매출 비중", 0.17, 0.20, 0.25, "비율", "블로그 65/20/15 + 파생", "S30", "UNVERIFIED"),
    ("BM29", "2026 최저임금", None, 10320, None, "₩/시간", "법정", "S36", "+2.9%"),
    ("BM30", "2026 최저임금 월 환산 (209h)", None, "={BM29}*209", None, "₩/월", "BM29 × 209h", "S36", "₩2,156,880"),
    ("BM31", "KREI 육류구이 종사자 수", None, 3.2, None, "명", "2018, 무급가족 18.3% 포함", "S31", ""),
    ("BM32", "KREI 육류구이 종사자 1인당 매출", None, 70990000, None, "₩/년", "2018", "S31", ""),
    ("BM33", "30평 삼겹살 사례 좌석수", None, 60, None, "석", "15테이블, 월 ~₩3,000만", "S34", "미금(성남) 프랜차이즈"),
    ("BM34", "외식업 평균 연매출 (2024)", None, 255300000, None, "₩/년", "전체 외식", "S33;S29", ""),
    ("BM35", "한식 평균 연매출 (2024)", None, 291100000, None, "₩/년", "한식", "S33", ""),
    ("BM36", "비프랜차이즈 평균 연매출 (2024)", None, 230000000, None, "₩/년", "개인 외식업", "S33", ""),
    ("BM37", "한식음식점 5년 생존율 (국세청)", None, 0.34, None, "비율", "2023, 사업자 폐업 기준", "S38", "인허가 기준과 정의 다름"),
    ("BM38", "서울 한식 3년 생존율 (인허가)", None, 0.70, None, "비율", "LOCALDATA 기준", "S09", ""),
    ("BM39", "서울 외식업 폐업률 (2023)", None, 0.1899, None, "비율", "핀다 오픈업", "S40", "민간 추정"),
    ("BM40", "대학로 한식 폐업 점포수 (2025)", None, 11, None, "개", "개업 25", "S13", "폐업 적음 → 인허가 이력 필요"),
    ("BM41", "외식업 평균 임차 보증금 (2022)", None, 33010000, None, "₩", "88.3%가 임차", "S32", ""),
    ("BM42", "혜화동 소규모 상가 1층 임대료 (2026Q2)", None, 60033, None, "₩/㎡/월", "보증금 환산 포함", "S52", "R-ONE 상권 혜화동"),
    ("BM43", "서울 소규모 상가 임대료 (2026Q2)", None, 52778, None, "₩/㎡/월", "1층 기준", "S52", ""),
    ("BM44", "전국 소규모 상가 임대료 (2026Q2)", None, 20646, None, "₩/㎡/월", "1층 기준", "S52;S54", ""),
    ("BM45", "혜화동 임대료 ÷ 전국 임대료", None, "={BM42}/{BM44}", None, "배", "BM42 ÷ BM44", "S52", "≈2.9배: 전국 비용 비중이 이 상권에 맞지 않는 이유"),
    ("BM46", "KMTA 냉장 삼겹 공장출고가 (2026년 1~9월 평균)", None, 18647, None, "₩/kg", "주간 시세 2주차", "S68", ""),
    ("BM47", "소매 삼겹살 가격 (2026-04)", None, 2559, None, "₩/100g", "소매", "S69", "식당 원가 상한"),
    ("BM48", "KAMIS 삼겹살 1인분 상차림 재료비 (2026 상반기)", None, 7082, None, "₩/인분", "소매 기준 고기+쌈채소", "S51", "중량 미기재"),
    ("BM49", "외식 가격탄력성 (메타분석 평균)", -1.07, -0.81, -0.56, "탄력성", "미국, 범주 수준", "S58", "95% 신뢰구간"),
]

# Shock catalog: main profit drivers only (D0930). One row per (shock, parameter); a compound shock
# has several rows with the same shock_id. delta_type: pct (relative, 0.10 = +10%), abs, set.
SHOCKS = [
    ("SH01", "가격", "prd_meat_price", "pct", 0.05, 0.10, 0.15, "고기 가격이 오르면 객단가는 오르고, 가격탄력성만큼 찾아오는 손님이 줄어든다", "S23;S25", "인상폭과 가격탄력성(mkt_price_elasticity)은 가정값", "L"),
    ("SH02", "가격", "prd_meat_price", "pct", -0.05, -0.10, -0.15, "고기 가격이 내리면 객단가는 내려가고, 좌석이 남는 한 손님이 늘어난다", "S23;S25", "인하폭은 가정값", "L"),
    ("SH03", "COGS", "cst_meat_cost_per_portion", "pct", 0.05, 0.08, 0.28, "1인분 원가가 오른다. 사장은 그대로 버티거나 가격에 반영할 수 있다", "S68;S48", "삼겹 부분육 도매가는 2024년 대비 2025년 +8.1%, 월별 전년 대비 최대 +15%, 1월 대비 8월 +28%", "M"),
    ("SH04", "주류", "prd_alcohol_price", "abs", 500, 1000, 1500, "객단가는 오르고, 1인당 소주 병수는 가격탄력성만큼 줄어든다", "S25;S26;S27", "소주 4,000~6,000원(마포)과 7,000~8,000원(강남) 사례", "M"),
    ("SH05", "주류", "prd_alcohol_per_cover", "pct", -0.10, -0.20, -0.30, "주류 매출 비중이 줄어 이익률이 높은 매출이 빠진다", "S27;S30", "음주 감소 폭은 가정값", "L"),
    ("SH06", "인건비", "sto_parttime_wage", "pct", 0.029, 0.05, 0.10, "알바 인건비가 오른다", "S36", "2026년 인상률 2.9%를 하한으로 둔다", "M"),
    ("SH07", "인건비", "sto_parttimers", "abs", -1, -1, -1, "인건비는 줄지만 서빙 인력이 줄어 대기와 이탈이 늘 수 있다", "S31", "교대당 알바 1명 감축", "L"),
    ("SH08", "임차료", "drv_rent", "pct", 0.05, 0.05, 0.15, "재계약 때 임대료가 오르면 고정비가 늘어 손익분기 손님 수가 늘어난다", "S57;S52", "재계약 때는 법정 상한 5%(환산보증금 9억 이하). +15%는 새로 계약할 때만 가능", "H"),
    ("SH09", "수요", "drv_arrival_rate", "pct", -0.05, -0.08, -0.15, "방학과 비수기에는 찾아오는 손님이 줄어든다", "S12;S59", "대학로 한식 3분기 매출은 2분기의 0.96배(전체), 0.92배(21~24시)라 방학 달은 −6%~−11%", "H"),
    ("SH10", "수요(비)", "wx_rain_nights_share", "set", 0.13, 0.19, 0.35, "비 오는 밤에는 야장을 접고 손님이 줄어든다. 평년 10월처럼 한 달에 6일쯤", "S75", "기상청 10월 전국 평년 강수일수 5.9일 (1991~2020) ÷ 31일. 비 오는 밤 손님 감소폭(−10%)은 가정", "M"),
    ("SH10b", "수요(비)", "wx_rain_nights_share", "set", 1.0, 1.0, 1.0, "한 달 내내 비가 와 야장을 한 번도 못 펴고 매일 손님이 줄어든다 (최악의 경우)", "S75", "현실적인 달이 아니라 상한. 비 오는 밤 손님 감소폭(−10%)은 가정", "L"),
    ("SH11", "경쟁", "reg_competitors", "abs", 1, 1, 1, "근처에 경쟁 고깃집이 한 곳 문을 연다", "S20", "27곳에서 28곳으로", "H"),
    ("SH11", "경쟁", "drv_arrival_rate", "pct", -0.05, -0.10, -0.20, "거리에 따라 손님을 나눠 갖는다", "S20", "균등하게 나누면 3.6% 감소, 바로 옆 개점이면 더 크다 (가정)", "L"),
]


# ---------------------------------------------------------------------------------------------
def read_csv(name: str) -> list[dict]:
    with open(ONT / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def split_ids(s: str) -> list[str]:
    return [t.strip() for t in (s or "").split(";") if t.strip()]


def validate(criteria, edges, sources) -> None:
    """Fail loudly on unknown ids, missing hero rows, or unsourced non-L values."""
    errors = []
    src = {s["source_id"] for s in sources}
    crit = {c["criterion_id"]: c for c in criteria}
    if len(crit) != len(criteria):
        errors.append("duplicate criterion_id in criteria.csv")

    def check_src(where, ids):
        for sid in split_ids(ids):
            if sid not in src:
                errors.append(f"{where}: unknown source_id {sid}")

    for c in criteria:
        check_src(f"criteria {c['criterion_id']}", c["source_id"])
        if c["driver_node"] and c["driver_node"] not in crit:
            errors.append(f"criteria {c['criterion_id']}: unknown driver_node {c['driver_node']}")
    for e in edges:
        for k in ("from_id", "to_id"):
            if e[k] not in crit:
                errors.append(f"edge {e['from_id']}->{e['to_id']}: unknown {k}")
        if e["sign"] not in ("+", "−", "±"):
            errors.append(f"edge {e['from_id']}->{e['to_id']}: bad sign {e['sign']}")
        check_src(f"edge {e['from_id']}->{e['to_id']}", e["source_id"])

    hero_ids = [h[0] for h in HERO]
    need = [c["criterion_id"] for c in criteria if c["method"] != "derived" and not c["criterion_id"].startswith("lbl_")]
    for cid in need:
        if cid not in hero_ids:
            errors.append(f"HERO missing row for {cid}")
    for h in HERO:
        cid, lo, base, hi, why, sid, conf = h
        if cid not in crit:
            errors.append(f"HERO {cid}: not in criteria.csv")
        check_src(f"HERO {cid}", sid)
        if not sid and conf != "L":
            errors.append(f"HERO {cid}: no source_id so confidence must be L")
        if not why:
            errors.append(f"HERO {cid}: empty reasoning_chain")
    if len(set(hero_ids)) != len(hero_ids):
        errors.append("duplicate HERO row")
    for b in BENCHMARKS:
        check_src(f"benchmark {b[0]}", b[7])
    for s in SHOCKS:
        check_src(f"shock {s[0]}", s[8])
        if s[2] not in crit:
            errors.append(f"shock {s[0]}: unknown parameter {s[2]}")
    if errors:
        sys.exit("VALIDATION FAILED:\n  " + "\n  ".join(errors))


# ---------------------------------------------------------------------------------------------
# P&L: (key, label, excel_formula, python_fn, unit, fmt, krei_bench or None, note).
# Formulas use defined names v_<criterion_id> (HeroStore base) and b_<bench_id> (Benchmarks
# value); {key} is replaced with this sheet's value cell for that key. python_fn mirrors it.
# ---------------------------------------------------------------------------------------------
PNL = [
    ("#", "용량·수요", None, None, None, None, None, None),
    ("seats", "유효 좌석수", "=v_sto_tables*v_sto_seats_per_table+v_sto_terrace*v_sto_terrace_availability",
     lambda v, p: v["sto_tables"] * v["sto_seats_per_table"] + v["sto_terrace"] * v["sto_terrace_availability"],
     "석", "0.0", None, "테이블 × 의자 + 야장 × 가용률"),
    ("occ", "좌석 점유율 (착석 시)", "=v_sto_occupancy", lambda v, p: v["sto_occupancy"], "비율", "0.00", None, "HeroStore"),
    ("turns", "테이블 회전율", "=v_sto_table_turns", lambda v, p: v["sto_table_turns"], "회/일", "0.00", None, "HeroStore"),
    ("covers_day", "일 착석고객수", "={seats}*{occ}*{turns}", lambda v, p: p["seats"] * p["occ"] * p["turns"],
     "명/일", "0.0", None, "좌석 × 점유율 × 회전율"),
    ("days", "월 영업일수", "=v_sto_open_days", lambda v, p: v["sto_open_days"], "일", "0", None, "HeroStore"),
    ("covers_month", "월 착석고객수", "={covers_day}*{days}", lambda v, p: p["covers_day"] * p["days"], "명/월", "#,##0", None, ""),
    ("arrivals_day", "일 도착 팀수 (이탈 전)", "={covers_day}/(1-v_drv_balk_rate)/v_mkt_party_size",
     lambda v, p: p["covers_day"] / (1 - v["drv_balk_rate"]) / v["mkt_party_size"], "팀/일", "0.0", None, "착석 ÷ (1 − 이탈률) ÷ 일행 수"),
    ("#", "객단가", None, None, None, None, None, None),
    ("t_meat", "고기 매출 / 인", "=v_prd_portions_per_cover*v_prd_meat_price",
     lambda v, p: v["prd_portions_per_cover"] * v["prd_meat_price"], "₩/인", WON, None, "인분/인 × 고기가"),
    ("t_alc", "주류 매출 / 인", "=v_prd_alcohol_per_cover*v_prd_alcohol_price",
     lambda v, p: v["prd_alcohol_per_cover"] * v["prd_alcohol_price"], "₩/인", WON, None, "병/인 × 소주가"),
    ("t_side", "식사·사이드 매출 / 인", "=v_prd_side_spend_per_cover", lambda v, p: v["prd_side_spend_per_cover"], "₩/인", WON, None, "HeroStore"),
    ("ticket", "객단가", "={t_meat}+{t_alc}+{t_side}", lambda v, p: p["t_meat"] + p["t_alc"] + p["t_side"], "₩/인", WON, None, "합계"),
    ("#", "매출", None, None, None, None, None, None),
    ("rev", "월 매출", "={covers_month}*{ticket}", lambda v, p: p["covers_month"] * p["ticket"], "₩/월", WON, None,
     "좌석 × 회전 × 점유율 × 객단가 × 영업일"),
    ("rev_meat", "  고기 매출", "={covers_month}*{t_meat}", lambda v, p: p["covers_month"] * p["t_meat"], "₩/월", WON, None, ""),
    ("rev_alc", "  주류 매출", "={covers_month}*{t_alc}", lambda v, p: p["covers_month"] * p["t_alc"], "₩/월", WON, "BM28", "주류 비중 기준: 블로그 20% (미검증)"),
    ("rev_side", "  식사·사이드 매출", "={covers_month}*{t_side}", lambda v, p: p["covers_month"] * p["t_side"], "₩/월", WON, None, ""),
    ("alc_meat_ratio", "주류/고기 판매 비율", "={rev_alc}/{rev_meat}", lambda v, p: p["rev_alc"] / p["rev_meat"], "비율", "0.00", None, "cst_alcohol_meat_ratio"),
    ("#", "비용", None, None, None, None, None, None),
    ("c_meat", "  고기 원가", "={covers_month}*v_prd_portions_per_cover*v_cst_meat_cost_per_portion",
     lambda v, p: p["covers_month"] * v["prd_portions_per_cover"] * v["cst_meat_cost_per_portion"], "₩/월", WON, None, "고객 × 인분 × 1인분 원가"),
    ("c_alc", "  주류 원가", "={covers_month}*v_prd_alcohol_per_cover*v_cst_alcohol_cost_per_bottle",
     lambda v, p: p["covers_month"] * v["prd_alcohol_per_cover"] * v["cst_alcohol_cost_per_bottle"], "₩/월", WON, None, "고객 × 병수 × 병당 원가"),
    ("c_side", "  식사·사이드 원가", "={covers_month}*v_prd_side_spend_per_cover*v_cst_side_cost_ratio",
     lambda v, p: p["covers_month"] * v["prd_side_spend_per_cover"] * v["cst_side_cost_ratio"], "₩/월", WON, None, "식사 매출 × 원가율"),
    ("c_banchan", "  반찬·쌈채소 원가", "={covers_month}*v_cst_banchan_cost_per_cover",
     lambda v, p: p["covers_month"] * v["cst_banchan_cost_per_cover"], "₩/월", WON, None, "고객 × 1인 반찬 원가"),
    ("food", "식재료비", "={c_meat}+{c_alc}+{c_side}+{c_banchan}", lambda v, p: p["c_meat"] + p["c_alc"] + p["c_side"] + p["c_banchan"],
     "₩/월", WON, "BM13", "drv_food_cost"),
    ("l_pt", "  알바 인건비", "=v_sto_parttimers*v_sto_parttime_shift_hours*{days}*v_sto_parttime_wage*v_cst_holiday_pay_factor",
     lambda v, p: v["sto_parttimers"] * v["sto_parttime_shift_hours"] * p["days"] * v["sto_parttime_wage"] * v["cst_holiday_pay_factor"],
     "₩/월", WON, None, "알바 수 × 시간 × 영업일 × 시급 × 주휴계수"),
    ("l_emp", "  정직원 인건비", "=v_sto_employees*v_cst_employee_wage", lambda v, p: v["sto_employees"] * v["cst_employee_wage"],
     "₩/월", WON, None, "정직원 수 × 월급"),
    ("l_owner", "  대표자 귀속 인건비", "=v_cst_owner_imputed_wage", lambda v, p: v["cst_owner_imputed_wage"], "₩/월", WON, None, "KREI 기준 인건비에 포함"),
    ("labor", "인건비", "={l_pt}+{l_emp}+{l_owner}", lambda v, p: p["l_pt"] + p["l_emp"] + p["l_owner"], "₩/월", WON, "BM15", "drv_labor_cost"),
    ("rent", "임차료", "=v_drv_rent", lambda v, p: v["drv_rent"], "₩/월", WON, "BM17", "drv_rent (R-ONE 혜화동 1층 시세)"),
    ("m_util", "  공과금·가스·숯", "=v_cst_utilities", lambda v, p: v["cst_utilities"], "₩/월", WON, None, ""),
    ("m_other", "  기타경비", "=v_cst_other_opex", lambda v, p: v["cst_other_opex"], "₩/월", WON, None, ""),
    ("mgmt", "관리비", "={m_util}+{m_other}", lambda v, p: p["m_util"] + p["m_other"], "₩/월", WON, None, "drv_mgmt_cost"),
    ("fees", "수수료", "={rev}*v_cst_card_share*v_cst_card_fee_rate", lambda v, p: p["rev"] * v["cst_card_share"] * v["cst_card_fee_rate"],
     "₩/월", WON, None, "매출 × 카드 비중 × 수수료율"),
    ("other", "관리비 + 수수료", "={mgmt}+{fees}", lambda v, p: p["mgmt"] + p["fees"], "₩/월", WON, "BM19", "KREI 잔여 비용과 비교"),
    ("cost", "총비용", "={food}+{labor}+{rent}+{mgmt}+{fees}", lambda v, p: p["food"] + p["labor"] + p["rent"] + p["mgmt"] + p["fees"],
     "₩/월", WON, None, "drv_total_cost"),
    ("#", "이익·KPI", None, None, None, None, None, None),
    ("op", "영업이익", "={rev}-{cost}", lambda v, p: p["rev"] - p["cost"], "₩/월", WON, "BM11", "drv_operating_profit (대표자 인건비 차감 후)"),
    ("owner_take", "사장 실수령 (영업이익 + 대표자 인건비)", "={op}+{l_owner}", lambda v, p: p["op"] + p["l_owner"], "₩/월", WON, None, "세전"),
    ("revpash", "RevPASH", "={rev}/({seats}*v_drv_open_hours*{days})", lambda v, p: p["rev"] / (p["seats"] * v["drv_open_hours"] * p["days"]),
     "₩/석·시간", WON, None, "매출 ÷ (좌석 × 영업시간 × 영업일)"),
    ("rel_rev", "상대매출 (앵커 대비)", "={rev}/b_bm03", lambda v, p: p["rev"] / p["_anchor"], "배", "0.00", None, "lbl_rel_revenue_tercile 입력"),
    ("order_kg", "월 고기 발주량", "={covers_month}*v_prd_portions_per_cover*v_prd_portion_grams/1000",
     lambda v, p: p["covers_month"] * v["prd_portions_per_cover"] * v["prd_portion_grams"] / 1000, "kg/월", "#,##0.0", None, "cst_order_volume"),
    ("be_covers", "손익분기 월 고객수",
     "=({labor}+{rent}+{mgmt})/({ticket}-({food}/{covers_month})-{ticket}*v_cst_card_share*v_cst_card_fee_rate)",
     lambda v, p: (p["labor"] + p["rent"] + p["mgmt"]) / (p["ticket"] - p["food"] / p["covers_month"] - p["ticket"] * v["cst_card_share"] * v["cst_card_fee_rate"]),
     "명/월", "#,##0", None, "고정비 ÷ 1인 공헌이익 (인건비를 고정비로 취급)"),
]

# Which P&L keys feed which criterion_id in hero_base.yaml (derived values).
PNL_TO_CRITERION = {
    "rev": "drv_revenue", "cost": "drv_total_cost", "op": "drv_operating_profit", "covers_day": "drv_covers",
    "ticket": "drv_ticket", "arrivals_day": "drv_arrival_rate", "seats": "drv_seats", "food": "drv_food_cost",
    "labor": "drv_labor_cost", "mgmt": "drv_mgmt_cost", "fees": "drv_fees", "alc_meat_ratio": "cst_alcohol_meat_ratio",
    "order_kg": "cst_order_volume", "revpash": "lbl_revpash",
}


def bench_values() -> dict:
    """Evaluate benchmark formulas in Python (same arithmetic as the sheet)."""
    out = {}
    for bid, *_rest in BENCHMARKS:
        val = _rest[2]
        if isinstance(val, str) and val.startswith("="):
            expr = val[1:]
            for k, v in out.items():
                expr = expr.replace("{" + k + "}", repr(v))
            val = eval(expr)  # trusted, literal arithmetic from this file
        out[bid] = val
    return out


def compute_pnl(v: dict) -> dict:
    p = {"_anchor": bench_values()["BM03"]}
    for key, _lbl, _f, fn, *_ in PNL:
        if key != "#":
            p[key] = fn(v, p)
    return p


# ---------------------------------------------------------------------------------------------
def style_header(ws, row: int, ncol: int) -> None:
    for c in range(1, ncol + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = Font(name=FONT, bold=True, size=10)
        cell.fill = HEAD
        cell.alignment = Alignment(vertical="center", wrap_text=True)


def f(color=BLACK, bold=False, italic=False, size=10) -> Font:
    return Font(name=FONT, color=color, bold=bold, italic=italic, size=size)


def num_fmt(x) -> str:
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return "#,##0" if abs(x) >= 1000 else "General"
    return "@"


def as_text(cell) -> None:
    """Keep free text such as '= 테이블 × 의자' from being written as an Excel formula."""
    if cell.data_type == "f":
        cell.data_type = "s"
        cell.quotePrefix = True


def write_table(ws, header: list[str], rows: list[list], widths: list[int]) -> None:
    ws.append(header)
    style_header(ws, 1, len(header))
    for r in rows:
        ws.append(r)
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            as_text(cell)
            cell.font = f()
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions


def add_name(wb, name: str, ref: str) -> None:
    wb.defined_names[name] = DefinedName(name, attr_text=ref)


def build(criteria, edges, sources, hero=None, shocks=None, review=None, changelog=None) -> dict:
    hero = hero if hero is not None else HERO
    shocks = shocks if shocks is not None else SHOCKS
    review = review or {}
    crit = {c["criterion_id"]: c for c in criteria}
    wb = Workbook()

    # README -------------------------------------------------------------------------------
    ws = wb.active
    ws.title = "README"
    lines = [
        ("대학로 삼겹살집 디지털 트윈: 리서치 입력 워크북", f(bold=True, size=14)),
        ("composite 미도입 독립 삼겹살집 (대학로·혜화역 상권 3120012). 실제 상호 없음. 모든 추정값은 예시(ILLUSTRATIVE)이며 검토 전까지 사실이 아님.", f(color="C00000", bold=True)),
        ("", f()),
        ("작성 방법", f(bold=True, size=12)),
        ("1. HeroStore 시트에서 한 행 = 한 기준(criterion). low / base / high 를 채우고, reasoning_chain 에 한 줄 계산 근거를 적는다 (예: 43석 × 0.70 × 1.25회전 × ₩28,000 × 26일).", f()),
        ("2. source_id 는 Sources 시트의 ID만 사용. 출처가 없으면 source_id 를 비우고 confidence 를 반드시 L 로 둔다.", f()),
        ("3. confidence: H = 공공데이터·공식 수치 / M = 기사·보고서 근거 / L = 가정 또는 약한 근거.", f()),
        ("4. filled_by 에 채운 사람(AI 또는 이름)을 적는다.", f()),
        ("5. 규칙: AI가 채운 칸은 반드시 사람이 검토하고 reviewed_by에 이름을 적는다. 검토 전 값은 발표·시뮬레이션 결론에 쓰지 않는다.", f(color="C00000", bold=True)),
        ("6. P&L, Checks 시트는 수식이다. 숫자를 직접 입력하지 말 것. HeroStore base 값을 바꾸면 자동으로 다시 계산된다.", f()),
        ("7. Checks 시트의 PASS/FAIL 행이 모두 PASS 인지 확인한다 (앵커 ₩2,580만 ±40%, 인건비·기타 비용·영업이익률은 KREI ±5pp). 식재료·임차료·주류 비중은 INFO 행으로 차이만 보여 준다.", f()),
        ("8. 새 기준을 추가하려면 ontology/criteria.csv 에 먼저 추가하고 build_workbook.py 를 다시 실행한다 (시트에만 추가하면 로더가 무시).", f()),
        ("", f()),
        ("색상 범례", f(bold=True, size=12)),
        ("파란 글씨 = 입력값 (사람 또는 AI가 입력)", f(color=BLUE)),
        ("검은 글씨 = 수식 (직접 수정 금지)", f()),
        ("노란 배경 = 가정·추정값 (ILLUSTRATIVE, 검토 필요)", f()),
        ("빈칸 = 파이프라인 또는 인터뷰로 채울 값", f(italic=True)),
        ("", f()),
        ("시트 안내", f(bold=True, size=12)),
        ("Criteria: 온톨로지 전체 기준 (ontology/criteria.csv). method = public | guesstimate | interview_later | derived", f()),
        ("HeroStore: hero 매장의 입력값 (long format). 시뮬레이션은 research/hero_base.yaml 로 읽는다.", f()),
        ("P&L: HeroStore base 값으로 계산한 월 손익 (라이브 수식).", f()),
        ("Benchmarks: 앵커·KREI 비용 비중·가격 기준 (각 행 source_id).", f()),
        ("Shocks: 주요 이익 드라이버 충격 목록 (기술 도입은 범위 밖).", f()),
        ("Edges / Sources: 드라이버 간 연결과 출처 목록.", f()),
        ("Checks: 보정·데이터 품질 검사 (수식).", f()),
        ("", f()),
        ("주의: 임차료(R-ONE)와 고기 원가(KMTA)는 이제 실제 시세다. 반찬 원가와 일부 기타 비용은 아직 출처가 없다. 전국 KREI 비중과 다른 부분은 대학로의 특징으로 본다.", f(italic=True)),
    ]
    for i, (text, font) in enumerate(lines, start=1):
        c = ws.cell(row=i, column=1, value=text)
        c.font = font
        c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.cell(row=15, column=1).font = f(color=BLUE)
    ws.cell(row=17, column=1).fill = YELLOW
    ws.column_dimensions["A"].width = 120

    # Criteria -----------------------------------------------------------------------------
    ws = wb.create_sheet("Criteria")
    cols = list(criteria[0].keys())
    write_table(ws, cols, [[c[k] for k in cols] for c in criteria], [26, 26, 28, 11, 22, 11, 9, 14, 16, 10, 7, 60])

    # HeroStore ----------------------------------------------------------------------------
    ws = wb.create_sheet("HeroStore")
    hcols = ["criterion_id", "name_ko", "low", "base", "high", "unit", "method", "reasoning_chain",
             "source_id", "confidence", "filled_by", "reviewed_by", "illustrative"]
    ws.append(hcols)
    style_header(ws, 1, len(hcols))
    for r, (cid, lo, base, hi, why, sid, conf) in enumerate(hero, start=2):
        c = crit[cid]
        pending = base is None
        note = PENDING_NOTE if pending else (PUBLIC_NOTE if c["method"] == "public" else GUESS_NOTE)
        filled, reviewer = review.get(cid, ("" if pending else "AI", ""))
        ws.append([cid, c["name_ko"], lo, base, hi, c["unit"], c["method"], why, sid, conf, filled, reviewer, note])
        for col in range(1, len(hcols) + 1):
            cell = ws.cell(row=r, column=col)
            if col != 4:
                as_text(cell)
            cell.font = f()
            cell.alignment = Alignment(vertical="top", wrap_text=col in (2, 8, 13))
        for col, val in ((3, lo), (4, base), (5, hi)):
            cell = ws.cell(row=r, column=col)
            cell.font = f(color=BLUE)
            cell.number_format = num_fmt(val)
            if c["method"] != "public" and val is not None:
                cell.fill = YELLOW
        if c["method"] != "public" and not pending:
            ws.cell(row=r, column=13).fill = YELLOW
        if isinstance(base, (int, float)) and not isinstance(base, bool):
            add_name(wb, f"v_{cid}", f"HeroStore!$D${r}")
    n_hero_last = len(hero) + 1
    for i, w in enumerate([27, 24, 11, 12, 11, 11, 13, 62, 12, 10, 9, 11, 22], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:M{n_hero_last}"

    # Benchmarks ---------------------------------------------------------------------------
    ws = wb.create_sheet("Benchmarks")
    bcols = ["bench_id", "name_ko", "low", "value", "high", "unit", "basis", "source_id", "note"]
    ws.append(bcols)
    style_header(ws, 1, len(bcols))
    brow = {b[0]: i for i, b in enumerate(BENCHMARKS, start=2)}
    for r, (bid, name, lo, val, hi, unit, basis, sid, note) in enumerate(BENCHMARKS, start=2):
        if isinstance(val, str) and val.startswith("="):
            for k, rr in brow.items():
                val = val.replace("{" + k + "}", f"$D${rr}")
        ws.append([bid, name, lo, val, hi, unit, basis, sid, note])
        for col in range(1, len(bcols) + 1):
            ws.cell(row=r, column=col).font = f()
            ws.cell(row=r, column=col).alignment = Alignment(vertical="top", wrap_text=col in (2, 7, 9))
        for col in (3, 4, 5):
            cell = ws.cell(row=r, column=col)
            v = cell.value
            is_formula = isinstance(v, str) and v.startswith("=")
            cell.font = f(color=BLACK if is_formula else BLUE)
            if unit in ("비율", "매출 대비", "비용 대비"):
                cell.number_format = "0.0%"
            elif unit.startswith("₩"):
                cell.number_format = WON
            else:
                cell.number_format = "#,##0.##" if not is_formula else "#,##0"
        add_name(wb, f"b_{bid.lower()}", f"Benchmarks!$D${r}")
        if lo is not None:
            add_name(wb, f"b_{bid.lower()}_low", f"Benchmarks!$C${r}")
        if hi is not None:
            add_name(wb, f"b_{bid.lower()}_high", f"Benchmarks!$E${r}")
    for i, w in enumerate([9, 36, 14, 18, 14, 11, 32, 13, 36], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "C2"

    # P&L ----------------------------------------------------------------------------------
    ws = wb.create_sheet("P&L")
    ws["A1"] = "Hero 매장 월 손익 (base case)"
    ws["A1"].font = f(bold=True, size=13)
    ws["A2"] = ("ILLUSTRATIVE: 모든 값은 HeroStore base 입력에서 계산된 예시다. 이 시트에 숫자를 직접 입력하지 말 것. "
                "KREI 기준 = 2018 전국 육류구이 (매출 대비).")
    ws["A2"].font = f(color="C00000", italic=True)
    pcols = ["항목", "값", "단위", "매출 대비", "KREI 기준", "차이", "산식·메모"]
    for c, h in enumerate(pcols, start=1):
        ws.cell(row=4, column=c, value=h)
    style_header(ws, 4, len(pcols))
    for c in (2, 4, 5, 6):
        ws.cell(row=4, column=c).alignment = Alignment(horizontal="right", vertical="center")
    prow, r = {}, 5
    for key, label, formula, _fn, unit, fmt, bench, note in PNL:
        if key == "#":
            ws.cell(row=r, column=1, value=label).font = f(bold=True)
            for c in range(1, len(pcols) + 1):
                ws.cell(row=r, column=c).fill = SECTION
        else:
            prow[key] = r
        r += 1
    for key, label, formula, _fn, unit, fmt, bench, note in PNL:
        if key == "#":
            continue
        rr = prow[key]
        expr = formula
        for k, kr in prow.items():
            expr = expr.replace("{" + k + "}", f"$B${kr}")
        ws.cell(row=rr, column=1, value=label).font = f(bold=not label.startswith("  "))
        cell = ws.cell(row=rr, column=2, value=expr)
        cell.font = f(bold=key in ("rev", "op"))
        cell.number_format = fmt
        uc = ws.cell(row=rr, column=3, value=unit)
        uc.font, uc.alignment = f(), Alignment(indent=1)
        if unit == "₩/월" and key != "rev":
            sc = ws.cell(row=rr, column=4, value=f"=$B${rr}/$B${prow['rev']}")
            sc.font, sc.number_format = f(), PCT
        if key == "rev":
            sc = ws.cell(row=rr, column=4, value=1)
            sc.font, sc.number_format = f(), PCT
        if bench:
            bc = ws.cell(row=rr, column=5, value=f"=b_{bench.lower()}")
            bc.font, bc.number_format = f(), PCT
            dc = ws.cell(row=rr, column=6, value=f"=(D{rr}-E{rr})*100")
            dc.font, dc.number_format = f(), PP
        ws.cell(row=rr, column=7, value=note).font = f(color="595959")
        for c in range(1, len(pcols) + 1):
            ws.cell(row=rr, column=c).border = THIN
    add_name(wb, "pnl_revenue", f"'P&L'!$B${prow['rev']}")
    for i, w in enumerate([36, 18, 11, 11, 11, 10, 44], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A5"

    # Shocks -------------------------------------------------------------------------------
    ws = wb.create_sheet("Shocks")
    scols = ["shock_id", "driver", "parameter", "delta_type", "delta_low", "delta_base", "delta_high",
             "mechanism", "source_id", "rationale", "confidence"]
    write_table(ws, scols, [list(s) for s in shocks], [9, 10, 26, 10, 10, 10, 10, 48, 14, 52, 10])
    for row in ws.iter_rows(min_row=2, min_col=5, max_col=7):
        for cell in row:
            cell.font = f(color=BLUE)
            cell.fill = YELLOW
            dtype = ws.cell(row=cell.row, column=4).value
            cell.number_format = "+0.0%;-0.0%;0%" if dtype == "pct" else "+#,##0;-#,##0;0"

    # Edges / Sources ----------------------------------------------------------------------
    ws = wb.create_sheet("Edges")
    ecols = list(edges[0].keys())
    write_table(ws, ecols, [[e[k] for k in ecols] for e in edges], [28, 26, 6, 56, 14, 11])
    ws = wb.create_sheet("Sources")
    scols2 = list(sources[0].keys())
    write_table(ws, scols2, [[s[k] for k in scols2] for s in sources], [9, 44, 30, 7, 40, 12, 60])

    # Checks -------------------------------------------------------------------------------
    ws = wb.create_sheet("Checks")
    ccols = ["check_id", "항목", "값", "하한", "상한", "결과", "설명"]
    hs = lambda col: f"HeroStore!${col}$2:${col}${n_hero_last}"  # noqa: E731
    R = lambda k: f"'P&L'!$B${prow[k]}"  # noqa: E731
    D = lambda k: f"'P&L'!$D${prow[k]}"  # noqa: E731
    checks = [
        ("C01", "월 매출이 prior ₩2,000–5,000만 안", f"={R('rev')}", "=b_bm04_low", "=b_bm04_high", WON, "P&L 매출 vs Benchmarks BM04"),
        ("C02", "월 매출이 앵커 ±40% 안 (편차)", f"={R('rev')}/b_bm03-1", -0.4, 0.4, "+0.0%;-0.0%", "앵커 = 대학로 한식 점포당 월매출 (BM03)"),
        ("C03", "식재료비 비중 vs KREI (pp)", f"=({D('food')}-b_bm13)*100", None, None, PP,
         "INFO: 고기 원가를 KMTA 시세로 바꾼 뒤 아래에서 쌓아 올린 값. KREI 2018 전국 비중은 목표가 아님. 반찬·식사 원가는 출처 없음"),
        ("C04", "인건비 비중 vs KREI (pp)", f"=({D('labor')}-b_bm15)*100", -5, 5, PP, "±5pp; 대표자 귀속 인건비 포함"),
        ("C05", "임차료 비중 vs KREI (pp)", f"=({D('rent')}-b_bm17)*100", None, None, PP,
         "INFO: 혜화동 1층 임대료가 전국의 약 3배(BM45)라 전국 비용 비중이 맞지 않음. 오류가 아니라 이 상권의 특징"),
        ("C06", "관리비+수수료 비중 vs KREI 잔여 (pp)", f"=({D('other')}-b_bm19)*100", -5, 5, PP, "±5pp; KREI 잔여 = 1 - 식재료 - 인건비 - 임차"),
        ("C07", "영업이익률 vs KREI (pp)", f"=({D('op')}-b_bm11)*100", -5, 5, PP, "±5pp (추가 검사)"),
        ("C08", "주류 매출 비중 (참고 17–25%)", f"={D('rev_alc')}", None, None, PCT,
         "INFO: 17–25%는 미검증 블로그 범위. 식약처 음주량(S62)을 적용한 값이 더 낮음"),
        ("C09", "HeroStore confidence 빈칸 수", f"=SUMPRODUCT(--(LEN({hs('J')})=0))", 0, 0, "0", "모든 행에 H/M/L"),
        ("C10", "source_id 없는데 confidence ≠ L 인 행 수", f"=SUMPRODUCT((LEN({hs('I')})=0)*({hs('J')}<>\"L\"))", 0, 0, "0",
         "출처가 없으면 반드시 L"),
        ("C11", "reasoning_chain 빈칸 수", f"=SUMPRODUCT(--(LEN({hs('H')})=0))", 0, 0, "0", "모든 행에 계산 근거 한 줄"),
        ("C12", "source_id 없는 행 수 (L 가정값)", f"=SUMPRODUCT(--(LEN({hs('I')})=0))", None, None, "0", "INFO: 출처 확보 대상 목록"),
        ("C13", "reviewed_by 빈칸 수 (검토 대기)", f"=SUMPRODUCT(--(LEN({hs('L')})=0))", None, None, "0", "INFO: 0이 될 때까지 사람이 검토"),
        ("C14", "값이 비어 있는 행 수 (파이프라인·인터뷰 대기)", f"=SUMPRODUCT(--(LEN({hs('D')})=0))", None, None, "0", "INFO"),
    ]
    ws.append(ccols)
    style_header(ws, 1, len(ccols))
    for r, (cid, name, val, lo, hi, fmt, note) in enumerate(checks, start=2):
        info = lo is None
        res = '"INFO"' if info else f'IF(AND(C{r}>=D{r},C{r}<=E{r}),"PASS","FAIL")'
        ws.append([cid, name, val, lo, hi, f"={res}" if not info else "INFO", note])
        for col in range(1, len(ccols) + 1):
            ws.cell(row=r, column=col).font = f(bold=col == 6)
            ws.cell(row=r, column=col).alignment = Alignment(vertical="top", wrap_text=col in (2, 7))
        for col in (3, 4, 5):
            ws.cell(row=r, column=col).number_format = fmt
    last = len(checks) + 1
    ws.cell(row=last + 2, column=2, value="전체 결과").font = f(bold=True)
    tot = ws.cell(row=last + 2, column=6, value=f'=IF(COUNTIF(F2:F{last},"FAIL")=0,"ALL PASS","FAIL 있음")')
    tot.font = f(bold=True)
    green = PatternFill("solid", fgColor="C6EFCE")
    red = PatternFill("solid", fgColor="FFC7CE")
    rng = f"F2:F{last + 2}"
    ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"PASS"'], fill=green))
    ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"ALL PASS"'], fill=green))
    ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"FAIL"'], fill=red))
    ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"FAIL 있음"'], fill=red))
    for i, w in enumerate([9, 44, 18, 14, 14, 10, 46], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"

    for sheet in wb.worksheets:  # print/PDF: landscape, one page wide
        sheet.page_setup.orientation = "landscape"
        sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
        sheet.sheet_properties.pageSetUpPr.fitToPage = True
        sheet.page_setup.fitToWidth = 1
        sheet.page_setup.fitToHeight = 0
        sheet.print_title_rows = "4:4" if sheet.title == "P&L" else ("1:1" if sheet.title != "README" else None)

    # ChangeLog --------------------------------------------------------------------------
    ws = wb.create_sheet("ChangeLog")
    write_table(ws, CHANGELOG_COLS, [[c.get(k, "") for k in CHANGELOG_COLS] for c in (changelog or [])],
                [26, 12, 14, 14, 14, 12, 16, 40])

    OUT_XLSX.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT_XLSX)
    return {"pnl_rows": prow, "checks": len(checks)}


# ---------------------------------------------------------------------------------------------
def review_from_xlsx() -> dict:
    """criterion_id -> (filled_by, reviewed_by) from the HeroStore sheet."""
    ws = load_workbook(OUT_XLSX, read_only=True)["HeroStore"]
    head = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    ix = {h: i for i, h in enumerate(head)}
    return {r[ix["criterion_id"]]: (r[ix["filled_by"]] or "", r[ix["reviewed_by"]] or "")
            for r in ws.iter_rows(min_row=2, values_only=True) if r[ix["criterion_id"]]}


def hero_from_xlsx() -> list[tuple]:
    ws = load_workbook(OUT_XLSX, data_only=False)["HeroStore"]
    head = [c.value for c in ws[1]]
    ix = {h: i for i, h in enumerate(head)}
    rows = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row[ix["criterion_id"]]:
            continue
        rows.append((row[ix["criterion_id"]], row[ix["low"]], row[ix["base"]], row[ix["high"]],
                     row[ix["reasoning_chain"]], row[ix["source_id"]] or "", row[ix["confidence"]]))
    return rows


def write_yaml(criteria, hero_rows, review: dict | None = None) -> dict:
    crit = {c["criterion_id"]: c for c in criteria}
    out: dict = {
        "_meta": {
            "generated_by": "research/build_workbook.py",
            "store": "composite 미도입 independent 삼겹살집, 대학로(혜화역) 3120012",
            "illustrative": True,
            "note": "Seed guesstimates, not facts, until reviewed_by is filled in research/guesstimate.xlsx.",
        }
    }
    vals = {}
    for cid, lo, base, hi, _why, sid, conf in hero_rows:
        out[cid] = {"base": base, "low": lo, "high": hi, "unit": crit[cid]["unit"],
                    "method": crit[cid]["method"], "confidence": conf, "source_id": sid or None,
                    "reviewed_by": ((review or {}).get(cid, ("", ""))[1] or None)}
        vals[cid] = base
    pnl = compute_pnl(vals)
    for key, cid in PNL_TO_CRITERION.items():
        out[cid] = {"base": round(pnl[key], 4), "low": None, "high": None, "unit": crit[cid]["unit"],
                    "method": "derived", "confidence": None, "source_id": None}
    out["_pnl_base"] = {k: round(v, 4) for k, v in pnl.items() if not k.startswith("_")}
    with open(OUT_YAML, "w", encoding="utf-8") as fh:
        yaml.safe_dump(out, fh, allow_unicode=True, sort_keys=False)
    return pnl


SHOCK_COLS = ["shock_id", "driver", "parameter", "delta_type", "delta_low", "delta_base", "delta_high",
              "mechanism", "source_id", "rationale", "confidence"]


def shocks_from_xlsx() -> list[tuple]:
    ws = load_workbook(OUT_XLSX, data_only=False)["Shocks"]
    ix = {c.value: i for i, c in enumerate(ws[1])}
    return [tuple(row[ix[k]] for k in SHOCK_COLS) for row in ws.iter_rows(min_row=2, values_only=True)
            if row[ix["shock_id"]]]


def write_shocks_yaml(rows) -> int:
    """Group Shocks rows by shock_id; sim/shocks.py reads this file (never hard-coded shocks)."""
    out: dict = {"_meta": {"generated_by": "research/build_workbook.py (Shocks sheet)",
                           "scope": "main profit drivers only; tech adoption out of scope (D0930)",
                           "delta_types": {"pct": "relative, 0.10 = +10%", "abs": "added to the base value",
                                           "set": "replaces the base value"},
                           "illustrative": True}}
    for sid, driver, param, dtype, lo, base, hi, mech, src, why, conf in rows:
        entry = out.setdefault(sid, {"driver": driver, "params": []})
        entry["params"].append({"parameter": param, "delta_type": dtype, "low": lo, "base": base, "high": hi,
                                "mechanism": mech, "source_id": src or None, "rationale": why, "confidence": conf})
    with open(OUT_SHOCKS, "w", encoding="utf-8") as fh:
        yaml.safe_dump(out, fh, allow_unicode=True, sort_keys=False)
    return len(out) - 1


def reviewed_rows_exist() -> int:
    if not OUT_XLSX.exists():
        return 0
    ws = load_workbook(OUT_XLSX, read_only=True)["HeroStore"]
    head = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    k = head.index("reviewed_by")
    return sum(1 for row in ws.iter_rows(min_row=2, values_only=True) if row[k])


CHANGELOG_COLS = ["criterion_id", "field", "old", "new", "source_id", "reviewed_by", "date", "patch"]
HERO_FIELDS = ("low", "base", "high", "reasoning_chain", "source_id", "confidence")
SHOCK_FIELDS = {"delta_low": 4, "delta_base": 5, "delta_high": 6, "mechanism": 7, "source_id": 8, "rationale": 9,
                "confidence": 10}


def apply_patch(path: Path, sources: list[dict], hero=None, shocks=None):
    """Apply a reviewed patch. Two shapes are read:
    - research/review/accepted_patch.yaml (agents.guesstimate): top-level keys are criterion_ids;
    - research/interview/<T>/accepted_patch.yaml: `hero:` (criterion_id -> HeroStore fields) and `shocks:`
      (shock_id -> parameter + delta_low/base/high ...). `sim_assumptions`, `owner_policy` and `rejected` are
      reported, not applied (they are not workbook values).
    A row is applied only when it names a reviewer (row `reviewed_by`, or `_meta.reviewed_by` for an interview
    patch). Rows without one, with an unknown criterion / shock / source id, or with base outside [low, high]
    are refused. Returns (hero, shocks, review, changelog, refused, ignored)."""
    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    meta = doc.get("_meta") or {}
    meta_reviewer = str(meta.get("reviewed_by") or "").strip()
    date = str(meta.get("interview_date") or meta.get("date") or __import__("datetime").date.today().isoformat())
    known_src = {s["source_id"] for s in sources}
    hero = [list(h) for h in (hero if hero is not None else HERO)]
    shocks = [list(s) for s in (shocks if shocks is not None else SHOCKS)]
    by_id = {h[0]: h for h in hero}
    hero_rows = doc.get("hero") if isinstance(doc.get("hero"), dict) else {
        k: v for k, v in doc.items() if k not in ("_meta", "shocks", "sim_assumptions", "owner_policy", "rejected")}
    review, changelog, refused = {}, [], []
    ignored = [k for k in ("sim_assumptions", "owner_policy", "rejected") if doc.get(k)]

    def bad_sources(sid):
        return [x for x in split_ids(str(sid or "")) if x not in known_src]

    for cid, row in (hero_rows or {}).items():
        if not isinstance(row, dict):
            refused.append((cid, "row is not a mapping"))
            continue
        reviewer = str(row.get("reviewed_by") or meta_reviewer).strip()
        if not reviewer:
            refused.append((cid, "no reviewed_by"))
            continue
        if cid not in by_id:
            refused.append((cid, "not a HeroStore criterion"))
            continue
        if bad_sources(row.get("source_id")):
            refused.append((cid, f"unknown source_id {bad_sources(row.get('source_id'))}; add it to ontology/sources.csv"))
            continue
        h = by_id[cid]
        new = {"low": h[1], "base": h[2], "high": h[3], "reasoning_chain": h[4], "source_id": h[5], "confidence": h[6]}
        new.update({k: row[k] for k in HERO_FIELDS if k in row})
        nums = [new[k] for k in ("low", "base", "high")]
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in nums) and \
                not min(nums[0], nums[2]) <= nums[1] <= max(nums[0], nums[2]):
            refused.append((cid, "base outside [low, high]"))
            continue
        if not new["source_id"] and new["confidence"] != "L":
            refused.append((cid, "no source_id, so confidence must be L"))
            continue
        for i, k in enumerate(HERO_FIELDS, start=1):
            if h[i] != new[k]:
                changelog.append({"criterion_id": cid, "field": k, "old": h[i], "new": new[k],
                                  "source_id": new["source_id"], "reviewed_by": reviewer, "date": date, "patch": str(path)})
        h[1:7] = [new[k] for k in HERO_FIELDS]
        review[cid] = (str(row.get("filled_by") or meta.get("interviewer") or "AI"), reviewer)

    for sid_key, row in (doc.get("shocks") or {}).items():
        reviewer = str((row or {}).get("reviewed_by") or meta_reviewer).strip()
        if not reviewer:
            refused.append((sid_key, "no reviewed_by"))
            continue
        target = [s for s in shocks if s[0] == sid_key and s[2] == row.get("parameter")]
        if not target:
            refused.append((sid_key, f"no Shocks row for parameter {row.get('parameter')}"))
            continue
        if bad_sources(row.get("source_id")):
            refused.append((sid_key, f"unknown source_id {bad_sources(row.get('source_id'))}"))
            continue
        s_row = target[0]
        for k, i in SHOCK_FIELDS.items():
            if k in row and s_row[i] != row[k]:
                changelog.append({"criterion_id": f"{sid_key}.{row['parameter']}", "field": k, "old": s_row[i],
                                  "new": row[k], "source_id": row.get("source_id"), "reviewed_by": reviewer,
                                  "date": date, "patch": str(path)})
                s_row[i] = row[k]
    return [tuple(h) for h in hero], [tuple(s) for s in shocks], review, changelog, refused, ignored


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="overwrite the xlsx even if rows were reviewed")
    ap.add_argument("--yaml-from-xlsx", action="store_true", help="export hero_base.yaml from the edited xlsx")
    ap.add_argument("--apply-patch", type=Path, help="reviewed patch yaml (AI-helper or interview shape)")
    ap.add_argument("--out", type=Path, help="directory for guesstimate.xlsx, hero_base.yaml and shocks.yaml "
                                              "(default research/; use it to build a second twin)")
    args = ap.parse_args()
    global OUT_XLSX, OUT_YAML, OUT_SHOCKS
    if args.out:
        out = args.out if args.out.is_absolute() else ROOT / args.out
        OUT_XLSX, OUT_YAML, OUT_SHOCKS = out / "guesstimate.xlsx", out / "hero_base.yaml", out / "shocks.yaml"

    criteria, edges, sources = read_csv("criteria.csv"), read_csv("edges.csv"), read_csv("sources.csv")
    validate(criteria, edges, sources)

    if args.yaml_from_xlsx:
        pnl = write_yaml(criteria, hero_from_xlsx(), review_from_xlsx())
        n = write_shocks_yaml(shocks_from_xlsx())
        print(f"wrote {OUT_YAML} and {OUT_SHOCKS} ({n} shocks) from xlsx; "
              f"revenue ₩{pnl['rev']:,.0f}")
        return
    n = reviewed_rows_exist()
    if n and not args.force:
        sys.exit(f"{OUT_XLSX.name} has {n} reviewed rows; refusing to overwrite. Use --yaml-from-xlsx or --force.")
    hero, shocks, review, changelog = HERO, SHOCKS, {}, []
    if args.apply_patch:
        hero, shocks, review, changelog, refused, ignored = apply_patch(args.apply_patch, sources)
        print(f"patch {args.apply_patch}: {len({c['criterion_id'] for c in changelog})} rows changed, "
              f"{len(changelog)} field changes, {len(refused)} refused")
        for cid, why in refused:
            print(f"  REFUSED {cid}: {why}")
        if ignored:
            print(f"  not applied here (not workbook values): {', '.join(ignored)}")
    info = build(criteria, edges, sources, hero, shocks, review, changelog)
    pnl = write_yaml(criteria, hero, review)
    write_shocks_yaml(shocks)
    rel = lambda p: p.relative_to(ROOT) if p.is_relative_to(ROOT) else p  # noqa: E731
    print(f"criteria={len(criteria)} edges={len(edges)} sources={len(sources)} hero_rows={len(hero)} checks={info['checks']}")
    print(f"revenue ₩{pnl['rev']:,.0f}  cost ₩{pnl['cost']:,.0f}  OP ₩{pnl['op']:,.0f} ({pnl['op'] / pnl['rev']:.1%})")
    print(f"wrote {rel(OUT_XLSX)}, {rel(OUT_YAML)}, {rel(OUT_SHOCKS)}")


if __name__ == "__main__":
    main()
