#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_smoke.py — 설치/동작 확인 + 핵심 교정 회귀 테스트.

실행:  python test_smoke.py
(서브워드 모델 없어도 통과 — 있으면 커버리지까지 확인)
"""
import sys
from gigyo import build_corpus
from gigyo.core import export_marker_inventory
from gigyo.analyses import (analyze_bhr, analyze_connectives, analyze_collocation,
                            analyze_keywords, analyze_tokenizer_coverage)

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    # 모델 자동 다운로드 시도하되 실패해도 진행
    cp = build_corpus("sample_corpus", auto_download=True)

    ok = True
    def check(name, cond):
        nonlocal ok
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        ok = ok and cond

    bhr = analyze_bhr(cp)
    # 1) 완화 표지가 실제로 잡히는가 (옛 버그면 모두 0)
    total_hedges = sum(d["hedge_count"] for d in bhr.values())
    check("완화 표지 탐지(>0)", total_hedges > 0)
    # 2) 강조도 잡히는가
    total_boost = sum(d["booster_count"] for d in bhr.values())
    check("강조 표지 탐지(>0)", total_boost > 0)

    conn = analyze_connectives(cp)
    # 3) '때문에'류 다형태소 접속이 원인-결과에 들어가는가(또는 어떤 접속이든 집계)
    any_conn = any(cat["count"] > 0 for d in conn.values()
                   for cat in d["categories"].values())
    check("접속 표지 집계(>0)", any_conn)

    kw = analyze_keywords(cp)
    check("LL keyness 산출", all("keywords" in v for v in kw["critic_vs_critic"].values()))

    col = analyze_collocation(cp, target_words=["형식"])
    check("MI 산출(형식)", "형식" in col)

    cov = analyze_tokenizer_coverage(cp)
    check("커버리지 진단 산출", "critics" in cov and len(cov["critics"]) == 3)
    print(f"  · ModernKoreanSubword loaded = {cov['subword_model_loaded']}")

    inv = export_marker_inventory()
    check("표지 목록 추출", "완화 표지(hedge)" in inv)

    print("\n결과:", "ALL PASS ✅" if ok else "FAIL ❌")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
