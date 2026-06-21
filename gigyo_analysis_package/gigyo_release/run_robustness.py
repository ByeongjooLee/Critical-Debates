#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_robustness.py — 핵심 결론의 안정성 검정 (LOO + 부트스트랩)

작은 코퍼스를 약점이 아니라 '전수 검증이 가능한 조건'으로 뒤집는다.
텍스트를 한 편씩 빼거나(LOO·29회 전수) 비평가 내부에서 복원추출
(부트스트랩·기본 2000회)하여 핵심 결론이 흔들리는지 재계산한다.
결론이 보존되면 "이 규모가 이 결론에는 충분하다"는 직접 증거가 되고,
흔들리는 결론은 명시적으로 [불안정]으로 분리 보고하여
신뢰도를 결론별로 차등화한다.

검정 대상은 **BHR 정정표(논문정정표.md) 반영 후의 확정 결론**이다:
  C1. BHR 담화 자세  ① 세 비평가 모두 BHR<1(분석적 register 수렴)
                     ② 박용철 = 최저 BHR(가장 유보 — '영감-유보 역설')
                     ③ (참고) 임화>김기림 미세 우위가 견고한가
  C2. LL 변별 어휘   각 비평가 top-N 잔존(정정표상 LL 불변)
  C3. 기교/기술 방향 2분할 부호 조건(정정표상 궤적 불변)

모든 지표는 gigyo 패키지의 엔진·공식·상수를 그대로 재사용한다.
재토큰화 없이 텍스트별 1차량만 한 번 계산하므로 전 과정이 순수 산술이며,
난수는 고정 시드(--seed)로 완전 재현된다.

사용:
  python run_robustness.py                         # 실제 코퍼스(레포 루트) 자동
  python run_robustness.py --boot 2000 --topn 5
  python run_robustness.py --sw-tokenizer tokenizer/241112_vo32000_tokenizer.json
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import Counter
from pathlib import Path

from gigyo import build_corpus, config as C
from gigyo.core import (BOOSTER_ENGINE, HEDGE_ENGINE, CONNECTIVE_ENGINE,
                        log_likelihood)

CRITICS = ["박용철", "임화", "김기림"]
EARLY = C.SPLIT_2["전기"]                        # ["전사이전","전사","발단"]
LATE = C.SPLIT_2["논쟁기"]                       # ["전개","여파"]
CONN_CATS = list(C.CONNECTIVES_INV.keys())       # 대조·원인-결과·첨가·예시·환언·요약·결론

# 논문이 비평가별 변별 어휘로 제시한 LL 상위어(표 1-3; 정정표상 불변)
HEADLINE_LL = {
    "김기림": ["비평", "비평가", "모더니즘", "과학"],
    "임화":   ["낭만주의", "언어", "리얼리즘", "낭만"],
    "박용철": ["인상", "효과", "기술", "변설", "임화", "김기림"],
}


# ============================================================
# 1) 텍스트별 1차량 — 단 한 번 계산(재토큰화 없음)
# ============================================================
def build_primitives(corpus):
    prim = {}
    for key in corpus.texts:
        raw = corpus.raw_texts[key]
        morphs = corpus.tokenizer.morphs(raw)
        b = BOOSTER_ENGINE.count_all(morphs, raw)["강조"]["count"]
        h = HEDGE_ENGINE.count_all(morphs, raw)["완화"]["count"]
        conn = {cat: d["count"]
                for cat, d in CONNECTIVE_ENGINE.count_all(morphs, raw).items()}
        toks = corpus.texts[key]
        prim[key] = {
            "critic": key[0],
            "eoj": corpus.eojeol_counts[key],
            "booster": b,
            "hedge": h,
            "conn": conn,                       # 접속표지 범주별 count (텍스트별)
            "period": C.FILE_PERIOD_MAP.get(key, "미분류"),
            "tokens": toks,                     # MI(공기)용 순서 토큰
            "counter": Counter(toks),
        }
    return prim


# ============================================================
# 2) 지표 — gigyo 공식과 동일(검증된 로직 재사용)
# ============================================================
def bhr_of(keys, prim):
    """analyses._bhr 와 동일한 반올림 공식."""
    eoj = sum(prim[k]["eoj"] for k in keys)
    if eoj == 0:
        return None
    b_nf = round(sum(prim[k]["booster"] for k in keys) / eoj * 1000, 2)
    h_nf = round(sum(prim[k]["hedge"] for k in keys) / eoj * 1000, 2)
    return round(b_nf / h_nf, 3) if h_nf > 0 else None


def bhr_by_critic(keys, prim):
    return {c: bhr_of([k for k in keys if prim[k]["critic"] == c], prim) for c in CRITICS}


def _v(x):
    return float("inf") if x is None else x          # 완화 0 → 최강 단언


def claim_all_below_one(bhrs):
    return all(_v(bhrs[c]) < 1.0 for c in CRITICS)


def claim_park_lowest(bhrs):
    others = [_v(bhrs[c]) for c in CRITICS if c != "박용철"]
    return all(_v(bhrs["박용철"]) < o for o in others)


def claim_im_over_kim(bhrs):
    return _v(bhrs["임화"]) > _v(bhrs["김기림"])


def ll_top(keys, critic, prim, topn):
    """analyze_keywords 와 동일 필터로 critic의 LL 상위어 추출."""
    stop = set(C.STOP_WORDS) - set(C.KEY_TERMS)
    target, other = Counter(), Counter()
    for k in keys:
        (target if prim[k]["critic"] == critic else other).update(prim[k]["counter"])
    tsize, osize = sum(target.values()), sum(other.values())
    scores = []
    for w, f in target.items():
        if f < C.MIN_FREQ_KEYWORD or w in stop:
            continue
        if len(w) == 1 and w not in C.KEY_TERMS:
            continue
        of = other.get(w, 0)
        if (f / tsize if tsize else 0) <= (of / osize if osize else 0):
            continue
        scores.append((w, log_likelihood(f, of, tsize, osize)))
    scores.sort(key=lambda x: -x[1])
    return [w for w, _ in scores[:topn]]


def split_nf(keys, critic, term, periods, prim):
    ck = [k for k in keys if prim[k]["critic"] == critic and prim[k]["period"] in periods]
    eoj = sum(prim[k]["eoj"] for k in ck)
    if eoj == 0:
        return None
    cnt = sum(prim[k]["counter"].get(term, 0) for k in ck)
    return round(cnt / eoj * 1000, 2)


def direction_checks(keys, prim):
    """C3 — 2분할 기교/기술 방향 부호 조건. None(빈 셀)은 미충족 처리."""
    def nf(c, t, ps):
        return split_nf(keys, c, t, ps, prim)
    checks = {}
    # ① 비평가별 기교 논쟁기 상승 + 세 비평가 동시
    rises = {}
    for c in CRITICS:
        e, l = nf(c, "기교", EARLY), nf(c, "기교", LATE)
        rises[c] = (e is not None and l is not None and l > e)
        checks[f"기교상승_{c}"] = rises[c]
    checks["기교상승_3인동시"] = all(rises.values())
    # ② 박용철: 전기·논쟁기 모두 기술 > 기교
    pe_g, pe_t = nf("박용철", "기교", EARLY), nf("박용철", "기술", EARLY)
    pl_g, pl_t = nf("박용철", "기교", LATE), nf("박용철", "기술", LATE)
    checks["박용철_전시기_기술우위"] = (None not in (pe_g, pe_t, pl_g, pl_t)
                                       and pe_t > pe_g and pl_t > pl_g)
    # ③ 김기림: 전기 기술>기교 AND 논쟁기 기교>기술 (무게중심 역전)
    ke_g, ke_t = nf("김기림", "기교", EARLY), nf("김기림", "기술", EARLY)
    kl_g, kl_t = nf("김기림", "기교", LATE), nf("김기림", "기술", LATE)
    checks["김기림_무게중심역전"] = (None not in (ke_g, ke_t, kl_g, kl_t)
                                    and ke_t > ke_g and kl_g > kl_t)
    # ④ 임화: 논쟁기 기교 NF > 전기 기교 NF, 기술은 전 시기 저빈도(<1)
    ie_g, il_g = nf("임화", "기교", EARLY), nf("임화", "기교", LATE)
    ie_t, il_t = nf("임화", "기술", EARLY), nf("임화", "기술", LATE)
    checks["임화_기교일시동원"] = (None not in (ie_g, il_g, ie_t, il_t)
                                  and il_g > ie_g and ie_t < 1.0 and il_t < 1.0)
    return checks


def _jaccard(a, b):
    sa, sb = set(a), set(b)
    return len(sa & sb) / len(sa | sb) if (sa | sb) else 1.0


# ── 접속표지 NF (정정표 표 1-5; analyze_connectives 와 동일 NF) ──
def conn_nf(keys, critic, cat, prim):
    ck = [k for k in keys if prim[k]["critic"] == critic]
    eoj = sum(prim[k]["eoj"] for k in ck)
    if eoj == 0:
        return None
    cnt = sum(prim[k]["conn"].get(cat, 0) for k in ck)
    return round(cnt / eoj * 1000, 2)


def conn_all(keys, prim):
    return {c: {cat: conn_nf(keys, c, cat, prim) for cat in CONN_CATS} for c in CRITICS}


def _cross_max(critic, cat, cats):
    """critic의 cat NF가 세 비평가 중 유일한 최댓값인가."""
    v = cats[critic][cat]
    if v is None:
        return False
    return all((cats[o][cat] is None) or (v > cats[o][cat])
               for o in CRITICS if o != critic)


# ── MI 내용↔형식 (정정표 3.58; analyze_collocation 과 동일 공식) ──
def mi_pair(keys, critic, target, collo, prim, window=C.COLLOCATION_WINDOW):
    span = 2 * window
    co = N = tfreq = wf = 0
    for k in keys:
        if prim[k]["critic"] != critic:
            continue
        toks = prim[k]["tokens"]
        N += len(toks)
        wf += toks.count(collo)
        idx = [i for i, w in enumerate(toks) if w == target]
        tfreq += len(idx)
        for i in idx:
            lo, hi = max(0, i - window), min(len(toks), i + window + 1)
            co += sum(1 for j in range(lo, hi) if j != i and toks[j] == collo)
    if tfreq == 0 or wf == 0 or N == 0 or co < C.MIN_FREQ_COLLOCATE:
        return None                              # 파이프라인과 동일: 저빈도 공기는 제외
    expected = (tfreq * wf * span) / N
    return round(math.log2(co / expected), 2) if expected > 0 else None


def mi_all(keys, prim):
    return {c: mi_pair(keys, c, "내용", "형식", prim) for c in CRITICS}


def _mi_im_max(mi):
    """임화 내용-형식 MI가 세 비평가 중 유일 최고(유일한 긴밀 공기)인가."""
    vi = mi["임화"]
    if vi is None:
        return False
    return all((mi[o] is None) or (vi > mi[o]) for o in CRITICS if o != "임화")


# ── 정정표가 바꾼 결론(C4 접속표지 · C5 MI)을 불리언으로 ──
def eval_conn_mi_claims(keys, prim):
    cats = conn_all(keys, prim)
    mi = mi_all(keys, prim)
    kim = {cat: (cats["김기림"][cat] if cats["김기림"][cat] is not None else -1)
           for cat in CONN_CATS}
    return {
        "CONN_박용철_대조_최고": _cross_max("박용철", "대조", cats),
        "CONN_임화_원인결과_최고": _cross_max("임화", "원인-결과", cats),   # 정정표 핵심 역전
        "CONN_임화_첨가_최고": _cross_max("임화", "첨가", cats),
        "CONN_김기림_원인결과_내부최고": (max(kim, key=kim.get) == "원인-결과"),
        "MI_임화_내용형식_최고": _mi_im_max(mi),
    }, cats, mi


# ============================================================
# 3) LOO — 텍스트 1편씩 제거(전수)
# ============================================================
def run_loo(all_keys, prim, topn, base_top):
    n = len(all_keys)
    C1 = {"all_below_one": 0, "park_lowest": 0, "im_over_kim": 0}
    flip = {"all_below_one": [], "park_lowest": [], "im_over_kim": []}
    bhr_ranges = {c: [] for c in CRITICS}
    head_keep = {c: {w: 0 for w in ws} for c, ws in HEADLINE_LL.items()}
    jacc = {c: [] for c in HEADLINE_LL}
    dir_keep, dir_flip = None, {}
    cm_keep, cm_flip = None, {}                   # C4·C5 접속표지/MI

    for drop in all_keys:
        keys = [k for k in all_keys if k != drop]
        bhrs = bhr_by_critic(keys, prim)
        for c in CRITICS:
            bhr_ranges[c].append(bhrs[c])
        cm, _, _ = eval_conn_mi_claims(keys, prim)
        if cm_keep is None:
            cm_keep = {k: 0 for k in cm}
        for k, ok in cm.items():
            if ok:
                cm_keep[k] += 1
            else:
                cm_flip.setdefault(k, []).append("/".join(drop))
        for name, fn in (("all_below_one", claim_all_below_one),
                         ("park_lowest", claim_park_lowest),
                         ("im_over_kim", claim_im_over_kim)):
            if fn(bhrs):
                C1[name] += 1
            else:
                flip[name].append("/".join(drop))
        for c, ws in HEADLINE_LL.items():
            top = ll_top(keys, c, prim, topn)
            jacc[c].append(_jaccard(top, base_top[c]))
            for w in ws:
                if w in top:
                    head_keep[c][w] += 1
        dchecks = direction_checks(keys, prim)
        if dir_keep is None:
            dir_keep = {k: 0 for k in dchecks}
        for k, ok in dchecks.items():
            if ok:
                dir_keep[k] += 1
            else:
                dir_flip.setdefault(k, []).append("/".join(drop))

    def rng(vals):
        nums = [v for v in vals if v is not None]
        return (min(nums), max(nums)) if nums else (None, None)

    return {
        "n": n,
        "C1": {k: f"{v}/{n}" for k, v in C1.items()},
        "C1_flip_by": flip,
        "bhr_range": {c: rng(bhr_ranges[c]) for c in CRITICS},
        "ll_headline_keep": {c: {w: f"{head_keep[c][w]}/{n}" for w in ws}
                             for c, ws in HEADLINE_LL.items()},
        "ll_jaccard_mean": {c: round(sum(v) / len(v), 3) for c, v in jacc.items()},
        "direction_keep": {k: f"{v}/{n}" for k, v in dir_keep.items()},
        "direction_flip_by": dir_flip,
        "connmi_keep": {k: f"{v}/{n}" for k, v in cm_keep.items()},
        "connmi_flip_by": cm_flip,
    }


# ============================================================
# 4) 부트스트랩 — 비평가 내부 복원추출
# ============================================================
def run_bootstrap(all_keys, prim, topn, base_top, B, seed):
    rng_ = random.Random(seed)
    by_critic = {c: [k for k in all_keys if prim[k]["critic"] == c] for c in CRITICS}

    C1 = {"all_below_one": 0, "park_lowest": 0, "im_over_kim": 0}
    bhr_samples = {c: [] for c in CRITICS}
    gap_im_park, gap_im_kim = [], []
    head_sel = {c: {w: 0 for w in ws} for c, ws in HEADLINE_LL.items()}
    jacc = {c: [] for c in HEADLINE_LL}
    dir_ok = None
    cm_ok = None
    mi_im = []

    for _ in range(B):
        keys = []
        for c in CRITICS:
            pool = by_critic[c]
            keys += [rng_.choice(pool) for _ in pool]
        bhrs = bhr_by_critic(keys, prim)
        for c in CRITICS:
            bhr_samples[c].append(_v(bhrs[c]))
        cm, _, mi = eval_conn_mi_claims(keys, prim)
        if cm_ok is None:
            cm_ok = {k: 0 for k in cm}
        for k, ok in cm.items():
            if ok:
                cm_ok[k] += 1
        if mi["임화"] is not None:
            mi_im.append(mi["임화"])
        if claim_all_below_one(bhrs):
            C1["all_below_one"] += 1
        if claim_park_lowest(bhrs):
            C1["park_lowest"] += 1
        if claim_im_over_kim(bhrs):
            C1["im_over_kim"] += 1
        gap_im_park.append(_v(bhrs["임화"]) - _v(bhrs["박용철"]))
        gap_im_kim.append(_v(bhrs["임화"]) - _v(bhrs["김기림"]))
        for c, ws in HEADLINE_LL.items():
            top = ll_top(keys, c, prim, topn)
            jacc[c].append(_jaccard(top, base_top[c]))
            for w in ws:
                if w in top:
                    head_sel[c][w] += 1
        dchecks = direction_checks(keys, prim)
        if dir_ok is None:
            dir_ok = {k: 0 for k in dchecks}
        for k, ok in dchecks.items():
            if ok:
                dir_ok[k] += 1

    def ci(vals):
        s = sorted(v for v in vals if v != float("inf"))
        infs = sum(1 for v in vals if v == float("inf"))
        if not s:
            return {"note": "전부 완화0(∞)"}
        lo = s[max(0, int(0.025 * len(s)) - 1)]
        hi = s[min(len(s) - 1, int(0.975 * len(s)))]
        out = {"median": round(s[len(s) // 2], 3), "ci95": [round(lo, 3), round(hi, 3)]}
        if infs:
            out["inf_share"] = f"{infs}/{len(vals)}"
        return out

    return {
        "B": B, "seed": seed,
        "C1_pct": {k: round(v / B * 100, 1) for k, v in C1.items()},
        "bhr_ci": {c: ci(bhr_samples[c]) for c in CRITICS},
        "gap_임화-박용철": ci(gap_im_park),
        "gap_임화-김기림": ci(gap_im_kim),
        "ll_headline_select_pct": {c: {w: round(head_sel[c][w] / B * 100, 1) for w in ws}
                                   for c, ws in HEADLINE_LL.items()},
        "ll_jaccard_mean": {c: round(sum(v) / len(v), 3) for c, v in jacc.items()},
        "direction_pct": {k: round(v / B * 100, 1) for k, v in dir_ok.items()},
        "connmi_pct": {k: round(v / B * 100, 1) for k, v in cm_ok.items()},
        "mi_im_ci": ci(mi_im),
    }


# ============================================================
# 5) 단일텍스트·소규모 셀 — [불안정] 명시 분리
# ============================================================
def fragile_cells(prim):
    agg = {}
    for k, d in prim.items():
        a = agg.setdefault((d["critic"], d["period"]), {"eoj": 0, "n": 0})
        a["eoj"] += d["eoj"]
        a["n"] += 1
    out = []
    for (c, p), a in sorted(agg.items()):
        if p in ("미분류", "범위밖"):
            continue
        flags = []
        if a["n"] < 2:
            flags.append("단일텍스트")
        if a["eoj"] < C.MIN_CELL_EOJEOLS:
            flags.append(f"<{C.MIN_CELL_EOJEOLS}어절")
        if flags:
            out.append({"critic": c, "period": p, "eojeols": a["eoj"],
                        "texts": a["n"], "flags": flags})
    return out


# ============================================================
# 6) 보고서
# ============================================================
def report(baseline, base_top, loo, boot, fragile, topn):
    L, sep, sub = [], "=" * 74, "-" * 74
    L += [sep, "  핵심 결론 안정성 검정 — Leave-One-Out + 부트스트랩", sep,
          f"  · {loo['n']}편 전수 LOO + 부트스트랩 {boot['B']}회(seed={boot['seed']}), LL top-{topn}",
          "  · gigyo 엔진/공식 재사용. BHR·MI·접속표지는 정정표(논문정정표.md) 반영 후 값.",
          "  · 보존율↑ = 이 규모가 이 결론에 충분하다는 직접 증거.", sep]

    L += ["", "[기준값] 전체 코퍼스 BHR (정정 후)"]
    for c in CRITICS:
        v = baseline["bhr"][c]
        L.append(f"   {c:<5} BHR {('%.3f' % v) if v is not None else '∞':>7}")

    L += ["", sep, "  C1. BHR 담화 자세", sub]
    rows = [("① 세 비평가 모두 BHR<1 (분석적 register 수렴)", "all_below_one"),
            ("② 박용철 = 최저 BHR (가장 유보·영감-유보 역설)", "park_lowest"),
            ("③ 임화 > 김기림 미세 우위", "im_over_kim")]
    for lab, key in rows:
        L.append(f"   {lab}")
        L.append(f"        LOO {loo['C1'][key]:>7}   Boot {boot['C1_pct'][key]:>5}%")
        fl = loo["C1_flip_by"][key]
        if fl:
            L.append(f"        └ 교란 텍스트: {fl}")
    L.append("   BHR 범위/신뢰구간:")
    for c in CRITICS:
        lo, hi = loo["bhr_range"][c]
        ci = boot["bhr_ci"][c]
        ci_s = f"95%CI[{ci['ci95'][0]}, {ci['ci95'][1]}]" if "ci95" in ci else ci.get("note", "")
        L.append(f"        {c:<5} LOO[{lo}, {hi}]  Boot {ci_s}")
    gP, gK = boot["gap_임화-박용철"], boot["gap_임화-김기림"]
    if "ci95" in gP:
        L.append(f"   간격 임–박 95%CI{gP['ci95']} (>0 전부면 박 최저 견고)  "
                 f"임–김 95%CI{gK['ci95']} (0 포함이면 순위 불명)")

    L += ["", sep, f"  C2. LL 변별 어휘 잔존 (top-{topn} 유지; 정정표상 LL 불변)", sub]
    for c, ws in HEADLINE_LL.items():
        L.append(f"   >> {c}  (기준 top-{topn}: {base_top[c]})")
        L.append(f"      집합 안정성 Jaccard  LOO {loo['ll_jaccard_mean'][c]}  "
                 f"Boot {boot['ll_jaccard_mean'][c]}")
        for w in ws:
            keep = loo["ll_headline_keep"][c][w]
            sel = boot["ll_headline_select_pct"][c][w]
            mark = "" if "/".join(keep.split("/")[:1]) else ""
            L.append(f"      {w:<6} LOO {keep:>7}   Boot 선택률 {sel:>5}%{mark}")

    L += ["", sep, "  C3. 기교/기술 통시 방향 (2분할; 정정표상 궤적 불변)", sub]
    label = {
        "기교상승_김기림": "  · 김기림 기교 논쟁기 상승",
        "기교상승_임화": "  · 임화 기교 논쟁기 상승",
        "기교상승_박용철": "  · 박용철 기교 논쟁기 상승",
        "기교상승_3인동시": "세 비평가 동시 기교 상승",
        "박용철_전시기_기술우위": "박용철 전 시기 기술>기교",
        "김기림_무게중심역전": "김기림 기교/기술 역전",
        "임화_기교일시동원": "임화 기교 일시 동원·기술 저빈도",
    }
    for k, lab in label.items():
        keep = loo["direction_keep"][k]
        pct = boot["direction_pct"][k]
        L.append(f"   {lab:<28} LOO {keep:>7}   Boot {pct:>5}%")
        fl = loo["direction_flip_by"].get(k)
        if fl:
            L.append(f"        └ 교란 텍스트: {fl}")

    # ── C4. 접속표지 (정정표가 바꾼 표 1-5) ──
    L += ["", sep, "  C4. 접속 표지 NF 우위 (정정표 표 1-5 — 변경된 결론)", sub]
    bc = baseline["conn"]
    L.append("   기준 NF:  " + "  ".join(
        f"{c}[대조 {bc[c]['대조']}·인과 {bc[c]['원인-결과']}·첨가 {bc[c]['첨가']}]"
        for c in CRITICS))
    cmlab = {
        "CONN_박용철_대조_최고": "박용철 대조형 최고",
        "CONN_임화_원인결과_최고": "임화 원인-결과형 최고 (정정 역전)",
        "CONN_임화_첨가_최고": "임화 첨가형 최고",
        "CONN_김기림_원인결과_내부최고": "김기림 내부 원인-결과 최우위",
    }
    for k, lab in cmlab.items():
        L.append(f"   {lab:<28} LOO {loo['connmi_keep'][k]:>7}   "
                 f"Boot {boot['connmi_pct'][k]:>5}%")
        fl = loo["connmi_flip_by"].get(k)
        if fl:
            L.append(f"        └ 교란 텍스트: {fl}")

    # ── C5. MI 내용↔형식 (정정표 3.58) ──
    L += ["", sep, "  C5. 내용↔형식 공기 MI (정정표 3.58 — 임화 유일 긴밀)", sub]
    bm = baseline["mi"]
    L.append("   기준 MI:  " + "  ".join(
        f"{c} {('%.2f' % bm[c]) if bm[c] is not None else '—(저공기)'}" for c in CRITICS))
    k = "MI_임화_내용형식_최고"
    L.append(f"   임화 MI 최고(유일 긴밀)        LOO {loo['connmi_keep'][k]:>7}   "
             f"Boot {boot['connmi_pct'][k]:>5}%")
    mci = boot["mi_im_ci"]
    if "ci95" in mci:
        L.append(f"        임화 MI Boot 95%CI[{mci['ci95'][0]}, {mci['ci95'][1]}]")

    L += ["", sep, "  [불안정] 단일텍스트·소규모 셀 — 결론에서 분리(정직성)", sub]
    if fragile:
        for f in fragile:
            L.append(f"   {f['critic']:<5} {f['period']:<6} "
                     f"{f['eojeols']:>5}어절 {f['texts']}편  {'/'.join(f['flags'])}")
        L.append("   → 위 셀에 의존하는 하위시기 수치는 '확정'이 아니라 '경향 관찰'로 표기.")
    else:
        L.append("   (해당 없음)")

    L += ["", sep, "  해석 가이드", sub,
          "   · 보존율 ≥95%  → 견고: 본문에 그대로 주장 가능",
          "   · 80~95%      → 조건부: 교란 텍스트를 각주로 명시",
          "   · <80%        → 불안정: 톤다운 또는 셀 분리 보고", sep]
    return "\n".join(L)


# ============================================================
def main():
    ap = argparse.ArgumentParser()
    default_corpus = str(Path(__file__).resolve().parents[2])   # 레포 루트
    ap.add_argument("--corpus", default=default_corpus,
                    help="비평가 폴더(김기림/임화/박용철) 경로(기본: 레포 루트)")
    ap.add_argument("--output", default="output")
    ap.add_argument("--sw-tokenizer", default=None)
    ap.add_argument("--no-download", action="store_true")
    ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--topn", type=int, default=5)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    print(f"· 코퍼스 로드: {a.corpus}")
    corpus = build_corpus(a.corpus, sw_model_path=a.sw_tokenizer,
                          auto_download=not a.no_download)
    for c, d in corpus.stats().items():
        print(f"  {c}: {d['texts']}편 {d['eojeols']}어절")

    prim = build_primitives(corpus)
    all_keys = list(prim.keys())

    baseline = {"bhr": bhr_by_critic(all_keys, prim),
                "conn": conn_all(all_keys, prim),
                "mi": mi_all(all_keys, prim)}
    base_top = {c: ll_top(all_keys, c, prim, a.topn) for c in HEADLINE_LL}
    loo = run_loo(all_keys, prim, a.topn, base_top)
    boot = run_bootstrap(all_keys, prim, a.topn, base_top, a.boot, a.seed)
    fragile = fragile_cells(prim)

    rep = report(baseline, base_top, loo, boot, fragile, a.topn)
    print("\n" + rep)

    out = Path(a.output)
    out.mkdir(parents=True, exist_ok=True)
    payload = {"baseline": baseline, "baseline_ll_top": base_top,
               "loo": loo, "bootstrap": boot, "fragile_cells": fragile,
               "params": {"corpus": a.corpus, "boot": a.boot,
                          "topn": a.topn, "seed": a.seed}}
    (out / "robustness.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "robustness_report.txt").write_text(rep, encoding="utf-8")
    print(f"\n저장: {out/'robustness.json'} · {out/'robustness_report.txt'}")


if __name__ == "__main__":
    main()
