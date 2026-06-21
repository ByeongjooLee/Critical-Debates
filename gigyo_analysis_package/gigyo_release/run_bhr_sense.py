#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_bhr_sense.py — '~ㄹ 수 있다' 의미 구분 후 BHR 민감도 재집계

문제: BHR의 완화 집계에서 '수 있다'가 압도적 비중을 차지하는데, 이 표현은
다의적이다(인식적 가능성=완화 / 능력·수행 / 제시·증거 / 양가). 현재 파이프라인은
전부 완화로 센다. 의미를 구분하면 결론이 어떻게 바뀌는지를 '정답 한 값'이 아니라
**민감도 밴드**로 보고한다(70%가 양가이므로 단일 정답은 존재하지 않는다).

설계(게재 파이프라인과의 정합성):
  · 강조·비(非)'수 있다' 완화는 gigyo 엔진 그대로.
  · '수 있다'의 실제 집계수(engine_suitda)는 파이프라인 값을 그대로 쓰되,
    그 안의 의미 구성비(regex 분류)를 곱해 규칙별로 완화에 가산.
    → 규칙 R0(전부 가산)일 때 BHR이 게재값과 정확히 일치한다.

분류 범주:
  epistemic   인식적 가능성   '~일/될/없을 수 있다'           → 완화
  judgment    판단 완화       '~라고/다고 할 수 있다'         → 완화
  ability     능력·수행       표현/설명/규정/처리할 수 있다    → 완화 아님
  present     제시·증거       볼/발견/찾을 수 있다(=관찰된다)  → 완화 아님(쟁점)
  ambiguous   양가            단독 '할 수 있다' 등            → 규칙에 따라

규칙:
  R0 전부완화(현행)      base + suitda×1.0
  R1 엄격(인식만)        base + suitda×(epi+judg)
  R2 중도(명백비완화만 제외) base + suitda×(epi+judg+amb)   # ability·present 제외
  R3 전부제외            base + 0

사용:
  python run_bhr_sense.py                       # 레포 루트 자동
  python run_bhr_sense.py --corpus ../.. --dump # 용례 분류표 TSV 저장(수작업 검증용)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from gigyo import build_corpus, config as C
from gigyo.core import BOOSTER_ENGINE, MarkerEngine

CRITICS = ["박용철", "임화", "김기림"]

# '... 수(가/도/는/를/만)? 있-' — kwic_suitda 와 동일 패턴(없- 제외: 코드 hedge와 동일)
PAT = re.compile(r'([가-힣]+)\s*수(?:가|도|는|를|만)?\s*(있[가-힣]*)')

EPISTEMIC_PREV = {"일", "될", "없을", "있을", "였을", "이었을", "않을", "아닐"}
ABILITY_HINT = ("표현", "설명", "구별", "구분", "규정", "도달", "포착", "처리",
                "수행", "묘사", "형상화", "재현", "전달", "번역", "구성")
PRESENT_HINT = ("보", "볼", "발견", "찾", "알", "들", "지적", "확인", "인식",
                "파악", "예상", "관찰", "엿보")


def classify(prev: str, prev2: str) -> str:
    if prev in EPISTEMIC_PREV:
        return "epistemic"
    if prev == "할" and prev2 and (prev2.endswith("고") or prev2.endswith("라고")
                                   or prev2.endswith("다고")):
        return "judgment"
    if any(prev.startswith(h) for h in ABILITY_HINT):
        return "ability"
    if any(prev.startswith(h) for h in PRESENT_HINT):
        return "present"
    return "ambiguous"


def classify_critic(raw: str):
    flat = re.sub(r"\s+", " ", raw)
    cls = {"epistemic": 0, "judgment": 0, "ability": 0, "present": 0, "ambiguous": 0}
    rows = []
    for m in PAT.finditer(flat):
        prev = m.group(1)
        pre = flat[max(0, m.start() - 20):m.start()].strip().split(" ")
        prev2 = pre[-1] if pre else ""
        c = classify(prev, prev2)
        cls[c] += 1
        s, e = max(0, m.start() - 28), min(len(flat), m.end() + 28)
        rows.append((c, flat[s:m.start()] + "【" + m.group(0) + "】" + flat[m.end():e]))
    return cls, rows


# 비'수 있다' 완화 엔진(= bhr_variants 의 drop 방식)
def hedge_engine_without_suitda() -> MarkerEngine:
    inv = {cat: [e for e in entries if e["label"] != "ㄹ 수 있다"]
           for cat, entries in C.HEDGES_INV.items()}
    return MarkerEngine(inv)


HEDGE_FULL = MarkerEngine(C.HEDGES_INV)
HEDGE_BASE = hedge_engine_without_suitda()

RULES = {
    "R0 전부완화(현행)":  lambda f: f["epistemic"] + f["judgment"] + f["ability"] + f["present"] + f["ambiguous"],
    "R1 엄격(인식만)":    lambda f: f["epistemic"] + f["judgment"],
    "R2 중도(비완화제외)": lambda f: f["epistemic"] + f["judgment"] + f["ambiguous"],
    "R3 전부제외":        lambda f: 0.0,
}


def bhr(b_count, h_count, eoj):
    b_nf = round(b_count / eoj * 1000, 2)
    h_nf = round(h_count / eoj * 1000, 2)
    return round(b_nf / h_nf, 3) if h_nf > 0 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument("--sw-tokenizer", default=None)
    ap.add_argument("--no-download", action="store_true")
    ap.add_argument("--dump", action="store_true", help="용례 분류표 TSV 저장")
    ap.add_argument("--output", default="output")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    corpus = build_corpus(a.corpus, sw_model_path=a.sw_tokenizer,
                          auto_download=not a.no_download)

    data, dump_rows = {}, []
    for c in CRITICS:
        raw = corpus.critic_raw_text(c)
        eoj = corpus.critic_eojeols(c)
        morphs = corpus.tokenizer.morphs(raw)
        booster = BOOSTER_ENGINE.count_all(morphs, raw)["강조"]["count"]
        h_full = HEDGE_FULL.count_all(morphs, raw)["완화"]["count"]
        h_base = HEDGE_BASE.count_all(morphs, raw)["완화"]["count"]
        eng_suitda = h_full - h_base                       # 엔진 기준 '수 있다' 집계수
        cls, rows = classify_critic(raw)
        n_regex = sum(cls.values()) or 1
        frac = {k: v / n_regex for k, v in cls.items()}    # 의미 구성비
        data[c] = {"eoj": eoj, "booster": booster, "h_base": h_base,
                   "eng_suitda": eng_suitda, "cls": cls, "frac": frac, "n_regex": n_regex}
        for cl, kwic in rows:
            dump_rows.append(f"{c}\t{cl}\t{kwic}")

    # ── 분류 요약 ──
    sep = "=" * 78
    print(sep, "\n  '수 있다' 의미 구분 (regex 분류·휴리스틱; 수작업 검증 권장)\n", sep, sep="")
    print(f"  {'비평가':<6}{'엔진집계':>7}{'regex':>7}  "
          f"{'인식':>5}{'판단':>5}{'능력':>5}{'제시':>5}{'양가':>5}")
    for c in CRITICS:
        d = data[c]; cl = d["cls"]
        print(f"  {c:<6}{d['eng_suitda']:>7}{d['n_regex']:>7}  "
              f"{cl['epistemic']:>5}{cl['judgment']:>5}{cl['ability']:>5}"
              f"{cl['present']:>5}{cl['ambiguous']:>5}")
    print("  ※ '완화로 셀 것' = 인식+판단(엄격) ~ +양가(중도). 능력·제시는 완화 아님(쟁점은 제시).")

    # ── 규칙별 BHR ──
    print("\n", sep, "\n  규칙별 BHR 재집계 (강조·비수있다완화 고정, '수 있다'만 의미가산)\n", sep, sep="")
    header = f"  {'규칙':<22}" + "".join(f"{c:>9}" for c in CRITICS) + "   판정"
    print(header); print("  " + "-" * 76)
    verdicts = {}
    for rname, rule in RULES.items():
        bhrs = {}
        for c in CRITICS:
            d = data[c]
            h = d["h_base"] + d["eng_suitda"] * rule(d["frac"])
            bhrs[c] = bhr(d["booster"], h, d["eoj"])
        below = all((v is not None and v < 1.0) for v in bhrs.values())
        park_low = (bhrs["박용철"] is not None and
                    all(bhrs["박용철"] < bhrs[o] for o in CRITICS if o != "박용철"))
        verdicts[rname] = (below, park_low)
        cells = "".join(f"{('%.3f' % bhrs[c]) if bhrs[c] is not None else '∞':>9}"
                        for c in CRITICS)
        tag = ("셋다<1 " if below else "임화≥1 ") + ("·박최저" if park_low else "·서열변동")
        print(f"  {rname:<22}{cells}   {tag}")

    # ── 결론 생존 요약 ──
    print("\n", sep, "\n  결론 생존 (규칙 전반)\n", sep, sep="")
    all_below = all(v[0] for v in verdicts.values())
    any_below = any(v[0] for v in verdicts.values())
    all_park = all(v[1] for v in verdicts.values())
    print(f"  · '셋 다 BHR<1 (register 수렴)'  : "
          + ("모든 규칙에서 성립" if all_below else
             ("현행(R0)에서만 성립 — 의미 구분하면 깨짐" if verdicts['R0 전부완화(현행)'][0] and not all_below
              else "성립 안 함")))
    print(f"  · '박용철 최저 BHR (영감-유보)'   : "
          + ("모든 규칙에서 성립(서열 견고)" if all_park else "규칙에 따라 변동"))
    print("  → 두 마커 변형(의미구분)을 모두 통과하는 것만 본문 주장으로 권장.")

    if a.dump:
        out = Path(a.output); out.mkdir(parents=True, exist_ok=True)
        p = out / "suitda_coding.tsv"
        p.write_text("critic\tclass\tkwic\n" + "\n".join(dump_rows), encoding="utf-8")
        print(f"\n  분류표 저장(수작업 검증용): {p}  (총 {len(dump_rows)}용례)")


if __name__ == "__main__":
    main()
