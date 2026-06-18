#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kwic_suitda.py — 'ㄹ 수 있다' 용례 KWIC 추출 + 가능성/능력 진단.

코퍼스에서 '... 수 있-' 패턴을 찾아, 앞 서술어를 집계하고
인식적 가능성(완충)인지 능력/수행(완충 아님)인지 거칠게 분류한다.
자동 분류는 참고용이며, 최종 판단은 KWIC 표본으로 사람이 검증한다.
"""
import argparse, re, sys
from collections import Counter
from pathlib import Path

CRITICS = ["김기림", "임화", "박용철"]

# '... 수 (있)' — 수가/수도/수는 변이 허용, 있-만(없- 제외: 코드 hedge와 동일)
PAT = re.compile(r'([가-힣]+)\s*수(?:가|도|는|를|만)?\s*(있[가-힣]*)')

# 인식적(가능성) 신호: 앞 서술어가 계사/존재/생성/판단류
EPISTEMIC_PREV = {"일", "있을", "없을", "될", "였을", "이었을", "라고", "다고", "할"}
# '할 수 있다'는 양가적이지만 '~라고/~다고 할 수 있다'(인용+판단)는 인식적
# 능력/수행 신호: 구체 행위동사
ABILITY_HINT = ("표현", "이해", "설명", "구별", "구분", "발견", "파악", "인식",
                "규정", "도달", "포착", "지적", "확인", "처리", "수행")


def classify(prev_eojeol, prev2):
    """거친 3분류: epistemic(가능성) / ability(능력) / ambiguous."""
    if prev_eojeol in ("일", "있을", "없을", "될", "였을", "이었을"):
        return "epistemic"            # ~일/될 수 있다 = 가능성
    if prev2 and (prev2.endswith("고") or prev2.endswith("라고") or prev2.endswith("다고")):
        return "epistemic"            # ~라고 할 수 있다 = 판단 완화
    for h in ABILITY_HINT:
        if prev_eojeol.startswith(h):
            return "ability"
    if prev_eojeol == "할":
        return "ambiguous"            # 단독 '할 수 있다' = 양가
    return "ambiguous"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="../..")
    ap.add_argument("--sample", type=int, default=12, help="비평가별 KWIC 표본 수")
    ap.add_argument("--win", type=int, default=22, help="좌우 문맥 글자수")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(a.corpus)

    grand = Counter()
    for critic in CRITICS:
        cdir = root / critic
        if not cdir.is_dir():
            print(f"  ⚠ 폴더 없음: {cdir}"); continue
        text = "\n".join(f.read_text(encoding="utf-8") for f in sorted(cdir.glob("*.txt")))
        flat = re.sub(r"\s+", " ", text)

        prev_counter = Counter()
        cls = Counter()
        samples = []
        for m in PAT.finditer(flat):
            prev = m.group(1)
            # 직전 2번째 어절
            pre_span = flat[max(0, m.start() - 20):m.start()].strip().split(" ")
            prev2 = pre_span[-1] if pre_span else ""
            c = classify(prev, prev2)
            prev_counter[prev + " 수 " + m.group(2)] += 1
            cls[c] += 1
            if len(samples) < a.sample:
                s, e = max(0, m.start() - a.win), min(len(flat), m.end() + a.win)
                kwic = flat[s:m.start()] + "【" + m.group(0) + "】" + flat[m.end():e]
                samples.append((c, kwic))
        total = sum(cls.values())
        grand.update(cls)

        print("=" * 74)
        print(f"  {critic} — 'ㄹ 수 있-' 총 {total}회")
        print("=" * 74)
        ep, ab, am = cls["epistemic"], cls["ability"], cls["ambiguous"]
        def pct(x): return f"{x/total*100:.0f}%" if total else "0%"
        print(f"  [자동 분류·참고용]  가능성(완충) {ep} ({pct(ep)})  |  "
              f"능력(비완충) {ab} ({pct(ab)})  |  양가 {am} ({pct(am)})")
        print(f"  [앞 서술어 상위]")
        for form, n in prev_counter.most_common(8):
            print(f"     {form:<18} {n}")
        print(f"  [KWIC 표본 {len(samples)}]")
        for c, k in samples:
            tag = {"epistemic": "가능", "ability": "능력", "ambiguous": "양가"}[c]
            print(f"     ({tag}) …{k}…")
        print()

    t = sum(grand.values())
    print("#" * 74)
    print(f"  전체 {t}회  →  가능성 {grand['epistemic']} ({grand['epistemic']/t*100:.0f}%)  "
          f"능력 {grand['ability']} ({grand['ability']/t*100:.0f}%)  "
          f"양가 {grand['ambiguous']} ({grand['ambiguous']/t*100:.0f}%)")
    print("  ※ 자동 분류는 휴리스틱이며, '양가(할 수 있다)'가 핵심 판단 대상.")


if __name__ == "__main__":
    main()
