#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bhr_variants.py — '수 있다' 포함/제외 두 방식으로 BHR 재계산(전체+시기별).

BHR이 'ㄹ 수 있다'(가능성/능력 양가) 처리에 얼마나 민감한지 정량 비교.
"""
import argparse, sys
from pathlib import Path

from gigyo import config as C
from gigyo.core import ModernTokenizer, Corpus, MarkerEngine

PERIODS = ["전사", "발단", "전개", "여파"]


def make_engines(drop_suitda: bool):
    hedges = {}
    for cat, entries in C.HEDGES_INV.items():
        hedges[cat] = [e for e in entries if not (drop_suitda and e["label"] == "ㄹ 수 있다")]
    return MarkerEngine(C.BOOSTERS_INV), MarkerEngine(hedges)


def bhr_for(morphs, raw, eoj, be, he):
    b = be.count_all(morphs, raw)["강조"]["count"]
    h = he.count_all(morphs, raw)["완화"]["count"]
    b_nf = b / eoj * 1000 if eoj else 0
    h_nf = h / eoj * 1000 if eoj else 0
    return b, h, (b_nf / h_nf if h_nf else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="../..")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    cp = Corpus(a.corpus, ModernTokenizer()).load()
    be, he_full = make_engines(False)
    _, he_drop = make_engines(True)

    print("=" * 72)
    print("  [전체 BHR]  수 있다 포함 vs 제외")
    print("=" * 72)
    print(f"  {'비평가':<8}{'강조':>5}{'완화(포함)':>10}{'BHR포함':>9}{'완화(제외)':>10}{'BHR제외':>9}")
    for c in ["김기림", "임화", "박용철"]:
        raw = cp.critic_raw_text(c); eoj = cp.critic_eojeols(c)
        morphs = cp.tokenizer.morphs(raw)
        b, hf, bhrf = bhr_for(morphs, raw, eoj, be, he_full)
        _, hd, bhrd = bhr_for(morphs, raw, eoj, be, he_drop)
        sf = f"{bhrf:.3f}" if bhrf else "∞"
        sd = f"{bhrd:.3f}" if bhrd else "∞"
        print(f"  {cp.display_name(c):<8}{b:>5}{hf:>10}{sf:>9}{hd:>10}{sd:>9}")

    print()
    print("=" * 72)
    print("  [임화 시기별 BHR]  (논문 핵심: 급증 → 이념적 확신 강화)")
    print("=" * 72)
    print(f"  {'시기':<8}{'어절':>7}{'BHR포함':>9}{'BHR제외':>9}")
    for p in PERIODS:
        raw = cp.period_raw_text("임화", p); eoj = cp.period_eojeols("임화", p)
        if eoj == 0:
            continue
        morphs = cp.tokenizer.morphs(raw)
        _, _, bhrf = bhr_for(morphs, raw, eoj, be, he_full)
        _, _, bhrd = bhr_for(morphs, raw, eoj, be, he_drop)
        sf = f"{bhrf:.3f}" if bhrf else "∞"
        sd = f"{bhrd:.3f}" if bhrd else "∞"
        print(f"  {p:<8}{eoj:>7,}{sf:>9}{sd:>9}")


if __name__ == "__main__":
    main()
