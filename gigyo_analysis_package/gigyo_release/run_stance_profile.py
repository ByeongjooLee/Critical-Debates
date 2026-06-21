#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_stance_profile.py — 3원 양태 프로파일 (강조 · 완화 · 제시)

BHR(강조/완화 비율)을 폐기하고, 비율 대신 세 양태의 구성(NF)으로 비평가를 변별한다.
비율이 깨진 이유 = 제시적 양태를 강조/완화 이진에 욱여넣어서. → 제시를 제3 범주로 분리.

추가로, register 감사로 드러난 오분류 표지를 강조·완화에서 제거한다:
  · 강조에서 제거: 물론(양보), 특히·무엇보다(초점), 실로·진실로·참으로(정서 강조), 당연히(당위)
      └ '물론'은 KWIC 검증: 본 코퍼스에서 "물론 X(이)나/지만 Y" 양보 구조가 지배적
  · 완화에서 제거: 게 되다(기동상), 기도 하다(첨가), ㄹ 만하다(평가)
  · '수 있다'는 형태 규칙으로 분기:
      양보·추측형(-ㄹ 수는 있으나/있으리라) → 완화
      평서·관형형(볼/파악할 수 있다)        → 제시(evidential)

전부(full)와 청소(clean) 두 버전을 함께 내어 제거의 영향을 투명화한다.
주의: 청소 후 강조 카운트가 작아져(특히 박용철) 소표본 노이즈가 커진다 — raw 병기.

  python run_stance_profile.py
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from gigyo import build_corpus, config as C
from gigyo.core import MarkerEngine

CRITICS = ["박용철", "임화", "김기림"]
PAT = re.compile(r'([가-힣]+)\s*수(가|도|는|를|만)?\s*(있[가-힣]*)')
HEDGE_END = re.compile(r'(으나|지마|지만|으리|을지|는지|을까|을런지|음직)')

# register 감사로 제거할 오분류 표지(라벨 기준)
BOOSTER_DROP = {"물론", "특히", "무엇보다", "실로", "진실로", "참으로", "당연히"}
HEDGE_DROP = {"게 되다", "기도 하다", "ㄹ 만하다", "ㄹ 수 있다"}  # 수있다는 형태규칙 별도


def engine(inv_cat_entries):
    return MarkerEngine(inv_cat_entries)


BOOSTER_FULL = MarkerEngine(C.BOOSTERS_INV)
BOOSTER_CLEAN = MarkerEngine({"강조": [e for e in C.BOOSTERS_INV["강조"]
                                      if e["label"] not in BOOSTER_DROP]})
HEDGE_FULL = MarkerEngine(C.HEDGES_INV)
HEDGE_CLEAN = MarkerEngine({"완화": [e for e in C.HEDGES_INV["완화"]
                                    if e["label"] not in HEDGE_DROP]})


def suitda_split(raw):
    """평서·관형형(제시) vs 양보·추측형(완화) 카운트."""
    flat = re.sub(r"\s+", " ", raw)
    hedge = present = 0
    for m in PAT.finditer(flat):
        if (m.group(2) in ("는", "도")) or HEDGE_END.search(m.group(3)):
            hedge += 1
        else:
            present += 1
    return hedge, present


def nf(count, eoj):
    return round(count / eoj * 1000, 2) if eoj else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument("--sw-tokenizer", default=None)
    ap.add_argument("--no-download", action="store_true")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    corpus = build_corpus(a.corpus, sw_model_path=a.sw_tokenizer,
                          auto_download=not a.no_download)

    rows = {}
    for c in CRITICS:
        raw = corpus.critic_raw_text(c)
        eoj = corpus.critic_eojeols(c)
        morphs = corpus.tokenizer.morphs(raw)
        b_full = BOOSTER_FULL.count_all(morphs, raw)["강조"]["count"]
        b_clean = BOOSTER_CLEAN.count_all(morphs, raw)["강조"]["count"]
        h_clean_base = HEDGE_CLEAN.count_all(morphs, raw)["완화"]["count"]
        h_form, present = suitda_split(raw)
        h_clean = h_clean_base + h_form
        rows[c] = {"eoj": eoj, "b_full": b_full, "b_clean": b_clean,
                   "h_clean": h_clean, "present": present}

    sep = "=" * 78
    print(sep, "\n  감사: 강조에서 제거한 오분류 표지(전부→청소)\n", sep, sep="")
    print(f"  {'비평가':<6}{'강조(full)':>10}{'강조(clean)':>11}{'제거분':>8}")
    for c in CRITICS:
        d = rows[c]
        print(f"  {c:<6}{d['b_full']:>10}{d['b_clean']:>11}{d['b_full']-d['b_clean']:>8}")
    print("  제거: 물론·특히·무엇보다·실로·진실로·참으로·당연히 (양보/초점/정서/당위)")

    print("\n", sep, "\n  3원 양태 프로파일 — NF(1,000어절당), raw 병기\n", sep, sep="")
    print(f"  {'비평가':<6}{'강조':>14}{'완화':>14}{'제시':>14}   해석")
    interp = {"박용철": "양보·신중 (강조 최저)",
              "임화": "관찰 제시형 (제시 우세)",
              "김기림": "단정·분석 (강조 우위, 제시 회피)"}
    for c in CRITICS:
        d = rows[c]
        bn = nf(d["b_clean"], d["eoj"]); hn = nf(d["h_clean"], d["eoj"]); pn = nf(d["present"], d["eoj"])
        print(f"  {c:<6}"
              f"{bn:>7}({d['b_clean']:>3}){hn:>7}({d['h_clean']:>3})"
              f"{pn:>7}({d['present']:>3})   {interp[c]}")

    print("\n", sep, "\n  읽기\n", sep, sep="")
    print("  · 박용철: 강조 거의 없음 + 완화 최고 → 양보적·신중. (옛 BHR의 '강조'는 대부분")
    print("            정서강조 실로/진실로였음 → 제거 후 epistemic 강조는 미미.)")
    print("  · 임화  : 제시(관찰)가 가장 두드러짐 → 판단을 '관찰의 제시'로 제출하는 수사.")
    print("  · 김기림: 강조 우위 + 제시 회피 → 직접 단정하는 분석적 어조. (오형엽 '객관주의'와 호응)")
    print("\n  ⚠ 한계: 청소 후 강조 카운트가 작다(특히 박용철). 소표본 노이즈 큼 — 절대단정 금물.")
    print("     각 제거 판정(물론 외)은 '물론'처럼 KWIC+제2코더 κ로 확정해야 본문 사용 가능.")
    print("     '제시'는 '수 있다' 기반 부분 조작화. 다른 evidential(보다시피 등)은 미포함.")


if __name__ == "__main__":
    main()
