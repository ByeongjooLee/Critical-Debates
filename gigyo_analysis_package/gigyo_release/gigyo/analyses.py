# -*- coding: utf-8 -*-
"""
analyses.py — 분석 함수 모음 + 보고서

· LL(핵심어)·빈도는 검증상 정상이라 원본 로직 유지.
· MI·접속·BHR·시기별은 교정본(형태소 패턴/윈도 정규화) 적용.
· 커버리지는 ModernKoreanSubword 진단.
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from . import config as C
from . import core
from .core import (CONNECTIVE_ENGINE, BOOSTER_ENGINE, HEDGE_ENGINE,
                   log_likelihood, percent_diff, flag_cell)


# ── ① 빈도 (NF) ───────────────────────────────────────────
def analyze_frequency(corpus, key_terms=None) -> Dict:
    key_terms = key_terms or C.KEY_TERMS
    out = {}
    for critic in corpus.critics():
        tokens = corpus.critic_tokens(critic)
        eoj = corpus.critic_eojeols(critic)
        counter = Counter(tokens)
        terms = {t: {"count": counter.get(t, 0),
                     "nf": round(counter.get(t, 0) / eoj * 1000, 2) if eoj else 0.0}
                 for t in key_terms}
        out[critic] = {"display_name": corpus.display_name(critic),
                       "total_eojeols": eoj, "total_content_tokens": len(tokens),
                       "terms": terms}
    return out


# ── ② 핵심어 (LL) — 비평가 vs 나머지(keyness) ─────────────
def analyze_keywords(corpus, min_freq=C.MIN_FREQ_KEYWORD, top_n=C.TOP_N_KEYWORDS,
                     reference_counter=None, reference_size=None, stop_words=None) -> Dict:
    if stop_words is None:
        stop_words = set(C.STOP_WORDS) - set(C.KEY_TERMS)
    critics = corpus.critics()
    results = {"critic_vs_critic": {}, "critic_vs_reference": None,
               "note": "기준: 해당 비평가 vs 나머지 비평가 합(keyness). 전체 코퍼스 대비 아님."}
    for critic in critics:
        target = corpus.critic_tokens(critic)
        tc, tsize = Counter(target), len(target)
        others = []
        for o in critics:
            if o != critic:
                others.extend(corpus.critic_tokens(o))
        oc, osize = Counter(others), len(others)
        scores = []
        for w, f in tc.items():
            if f < min_freq or w in stop_words:
                continue
            if len(w) == 1 and w not in C.KEY_TERMS:
                continue
            of = oc.get(w, 0)
            if (f / tsize if tsize else 0) <= (of / osize if osize else 0):
                continue
            scores.append({"word": w, "ll": round(log_likelihood(f, of, tsize, osize), 2),
                           "target_freq": f, "reference_freq": of})
        scores.sort(key=lambda x: x["ll"], reverse=True)
        results["critic_vs_critic"][critic] = {
            "display_name": corpus.display_name(critic),
            "note": "귀납 추출 — 소규모 제약상 LL 절대값보다 상대순위 중시",
            "keywords": scores[:top_n]}
    if reference_counter and reference_size:
        allt = corpus.all_tokens()
        tc, tsize = Counter(allt), len(allt)
        scores = []
        for w, f in tc.items():
            if f < min_freq or w in stop_words:
                continue
            if len(w) == 1 and w not in C.KEY_TERMS:
                continue
            rf = reference_counter.get(w, 0)
            if (f / tsize) <= (rf / reference_size if reference_size else 0):
                continue
            scores.append({"word": w, "ll": round(log_likelihood(f, rf, tsize, reference_size), 2),
                           "target_freq": f, "reference_freq": rf})
        scores.sort(key=lambda x: x["ll"], reverse=True)
        results["critic_vs_reference"] = {"note": "비평 전체 vs 참조 — 비평 장르 특유어",
                                          "keywords": scores[:top_n]}
    return results


# ── ③ 공기어 (MI, 윈도 정규화) ────────────────────────────
def analyze_collocation(corpus, target_words=None, window=C.COLLOCATION_WINDOW,
                        min_freq=C.MIN_FREQ_COLLOCATE, top_n=C.TOP_N_COLLOCATES) -> Dict:
    target_words = target_words or C.COLLOCATION_TARGETS
    span = 2 * window
    out = {}
    for target in target_words:
        out[target] = {}
        for critic in corpus.critics():
            texts = corpus.critic_texts_separately(critic)
            co, wf = Counter(), Counter()
            tfreq, N = 0, 0
            for toks in texts:
                N += len(toks)
                wf.update(toks)
                idx = [i for i, w in enumerate(toks) if w == target]
                tfreq += len(idx)
                for i in idx:
                    for j in range(max(0, i - window), min(len(toks), i + window + 1)):
                        if j != i:
                            co[toks[j]] += 1
            if tfreq == 0:
                out[target][critic] = {"display_name": corpus.display_name(critic),
                                       "target_freq": 0, "collocates": [],
                                       "note": f"'{target}' 출현 없음"}
                continue
            scores = []
            for col, cof in co.items():
                if cof < min_freq or col == target:
                    continue
                w = wf.get(col, 0)
                if w == 0:
                    continue
                expected = (tfreq * w * span) / N if N else 0
                if expected <= 0:
                    continue
                scores.append({"word": col, "mi": round(math.log2(cof / expected), 2),
                               "co_freq": cof, "word_freq": w, "expected": round(expected, 3)})
            scores.sort(key=lambda x: x["mi"], reverse=True)
            out[target][critic] = {"display_name": corpus.display_name(critic),
                                   "target_freq": tfreq, "collocates": scores[:top_n],
                                   "note": f"윈도±{window}(span={span}) 정규화 MI; co_freq 병기"}
    return out


# ── ④ 접속 표지 (형태소 패턴) ─────────────────────────────
def analyze_connectives(corpus, markers=None) -> Dict:
    out = {}
    for critic in corpus.critics():
        eoj = corpus.critic_eojeols(critic)
        raw = corpus.critic_raw_text(critic)
        cats = CONNECTIVE_ENGINE.count_all(corpus.tokenizer.morphs(raw), raw)
        cd = {cat: {"count": d["count"],
                    "nf": round(d["count"] / eoj * 1000, 2) if eoj else 0.0,
                    "marker_detail": d["detail"]} for cat, d in cats.items()}
        out[critic] = {"display_name": corpus.display_name(critic),
                       "total_eojeols": eoj, "categories": cd}
    return out


# ── ⑤ BHR (강조/완화 대칭) ────────────────────────────────
def _interpret_bhr(bhr):
    if bhr is None:
        return "완화 0 — BHR 계산 불가"
    if bhr > 1.5:
        return "단언적·확신적 자세"
    if bhr > 1.0:
        return "약한 단언적 자세"
    if bhr > 0.7:
        return "균형 (약한 유보)"
    return "유보적·신중한 자세"


def _bhr(morphs, raw, eoj):
    b = BOOSTER_ENGINE.count_all(morphs, raw)["강조"]
    h = HEDGE_ENGINE.count_all(morphs, raw)["완화"]
    b_nf = round(b["count"] / eoj * 1000, 2) if eoj else 0.0
    h_nf = round(h["count"] / eoj * 1000, 2) if eoj else 0.0
    bhr = round(b_nf / h_nf, 3) if h_nf > 0 else None
    return b, h, b_nf, h_nf, bhr


def analyze_bhr(corpus, boosters=None, hedges=None) -> Dict:
    out = {}
    for critic in corpus.critics():
        raw = corpus.critic_raw_text(critic)
        eoj = corpus.critic_eojeols(critic)
        b, h, b_nf, h_nf, bhr = _bhr(corpus.tokenizer.morphs(raw), raw, eoj)
        out[critic] = {"display_name": corpus.display_name(critic),
                       "booster_count": b["count"], "hedge_count": h["count"],
                       "booster_nf": b_nf, "hedge_nf": h_nf, "bhr": bhr,
                       "interpretation": _interpret_bhr(bhr),
                       "booster_detail": b["detail"], "hedge_detail": h["detail"],
                       "genre_bhr": _genre_bhr(corpus, critic),
                       "note": "강조·완화 모두 어휘+구문 패턴으로 대칭 집계."}
    return out


def _genre_bhr(corpus, critic):
    g = defaultdict(lambda: {"raw": "", "eojeols": 0, "texts": 0})
    for k in corpus.texts:
        if k[0] != critic:
            continue
        ft = C.FILE_TYPE_MAP.get(k, "불명")
        g[ft]["raw"] += corpus.raw_texts[k] + "\n"
        g[ft]["eojeols"] += corpus.eojeol_counts[k]
        g[ft]["texts"] += 1
    out = {}
    for genre, d in g.items():
        b, h, b_nf, h_nf, bhr = _bhr(corpus.tokenizer.morphs(d["raw"]), d["raw"], d["eojeols"])
        out[genre] = {"texts": d["texts"], "eojeols": d["eojeols"],
                      "booster_nf": b_nf, "hedge_nf": h_nf, "bhr": bhr,
                      "interpretation": _interpret_bhr(bhr)}
    return out


# ── 시기별 ─────────────────────────────────────────────────
def analyze_term_trajectory(corpus, terms=None, periods=None) -> Dict:
    terms = terms or C.TRAJECTORY_TERMS
    periods = periods or C.PERIODS
    out = {}
    for critic in corpus.critics():
        out[critic] = {"display_name": corpus.display_name(critic), "periods": {}}
        for p in periods:
            tokens = corpus.period_tokens(critic, p)
            eoj = corpus.period_eojeols(critic, p)
            tc = corpus.period_text_count(critic, p)
            counter = Counter(tokens)
            out[critic]["periods"][p] = {
                "eojeols": eoj, "text_count": tc, "flag": flag_cell(eoj, tc),
                "date_range": C.PERIOD_DATES.get(p, ""),
                "term_nfs": {t: round(counter.get(t, 0) / eoj * 1000, 2) if eoj else 0.0
                             for t in terms}}
    return out


def analyze_period_bhr(corpus, boosters=None, hedges=None, periods=None) -> Dict:
    periods = periods or C.PERIODS
    out = {}
    for critic in corpus.critics():
        out[critic] = {"display_name": corpus.display_name(critic), "periods": {}}
        for p in periods:
            raw = corpus.period_raw_text(critic, p)
            eoj = corpus.period_eojeols(critic, p)
            tc = corpus.period_text_count(critic, p)
            if eoj == 0:
                out[critic]["periods"][p] = {"eojeols": 0, "text_count": tc,
                                             "flag": flag_cell(eoj, tc), "bhr": None}
                continue
            b, h, b_nf, h_nf, bhr = _bhr(corpus.tokenizer.morphs(raw), raw, eoj)
            out[critic]["periods"][p] = {"eojeols": eoj, "text_count": tc,
                                         "flag": flag_cell(eoj, tc),
                                         "booster_nf": b_nf, "hedge_nf": h_nf, "bhr": bhr,
                                         "interpretation": _interpret_bhr(bhr)}
    return out


def analyze_period_connectives(corpus, markers=None, periods=None) -> Dict:
    periods = periods or C.PERIODS
    out = {}
    for critic in corpus.critics():
        out[critic] = {"display_name": corpus.display_name(critic), "periods": {}}
        for p in periods:
            raw = corpus.period_raw_text(critic, p)
            eoj = corpus.period_eojeols(critic, p)
            tc = corpus.period_text_count(critic, p)
            if eoj == 0:
                out[critic]["periods"][p] = {"eojeols": 0, "text_count": tc,
                                             "flag": flag_cell(eoj, tc), "categories": {}}
                continue
            cats = CONNECTIVE_ENGINE.count_all(corpus.tokenizer.morphs(raw), raw)
            out[critic]["periods"][p] = {
                "eojeols": eoj, "text_count": tc, "flag": flag_cell(eoj, tc),
                "categories": {c: {"count": d["count"],
                                   "nf": round(d["count"] / eoj * 1000, 2)}
                               for c, d in cats.items()}}
    return out


def analyze_split2_nf(corpus, key_terms=None) -> Dict:
    key_terms = key_terms or C.TRAJECTORY_TERMS
    out = {}
    for critic in corpus.critics():
        out[critic] = {"display_name": corpus.display_name(critic), "splits": {}}
        for name, plist in C.SPLIT_2.items():
            tokens = corpus.split2_tokens(critic, name)
            eoj = corpus.split2_eojeols(critic, name)
            tc = sum(corpus.period_text_count(critic, p) for p in plist)
            counter = Counter(tokens)
            out[critic]["splits"][name] = {
                "eojeols": eoj, "text_count": tc, "flag": flag_cell(eoj, tc),
                "periods_included": plist,
                "term_nfs": {t: round(counter.get(t, 0) / eoj * 1000, 2) if eoj else 0.0
                             for t in key_terms}}
    return out


# ── ModernKoreanSubword 커버리지 진단 ─────────────────────
def analyze_tokenizer_coverage(corpus) -> Dict:
    tok = corpus.tokenizer
    has = tok.sw is not None
    out = {"subword_model_loaded": has, "subword_model_path": tok.sw_path, "critics": {}}
    for critic in corpus.critics():
        raw = corpus.critic_raw_text(critic)
        prox = tok.kiwi_oov_proxy(raw)
        unk = tok.subword_unk_rate(raw) if has else None
        swn = tok.subword_token_count(raw) if has else None
        decomp = round(swn / prox["total_morphs"], 3) if has and swn and prox["total_morphs"] else None
        out["critics"][critic] = {"display_name": corpus.display_name(critic),
                                  "kiwi_total_morphs": prox["total_morphs"],
                                  "kiwi_hanja_ratio": prox["hanja_ratio"],
                                  "kiwi_diag_token_ratio": prox["diag_token_ratio"],
                                  "subword_unk_rate": unk, "subword_token_count": swn,
                                  "subword_decomposition_ratio": decomp}
    return out


def classify_content_identity(term_nfs) -> str:
    form = sum(term_nfs.get(t, 0) for t in ["형식", "방법", "지성", "현대", "주지"])
    content = sum(term_nfs.get(t, 0) for t in ["내용", "사상", "계급", "현실", "반영"])
    spirit = sum(term_nfs.get(t, 0) for t in ["영감", "변용", "감정", "개성", "천재"])
    return max([("형식 우선", form), ("내용 우선", content), ("영감 우선", spirit)],
               key=lambda x: x[1])[0]


# ── 저장/보고서 ────────────────────────────────────────────
def save_json(results, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    p = output_dir / "results.json"
    p.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def generate_report(results, output_dir: Path) -> Path:
    L, sep, sub = [], "=" * 70, "-" * 70
    L += [sep, "  1930년대 기교주의 논쟁 분석 — 요약", sep,
          "  · 탐색적 분석(소규모 코퍼스). 강조·완화는 형태소 패턴으로 대칭 집계.",
          "  · MI는 윈도 정규화. [소규모-참고용]=500어절 미만, [단일텍스트]=1편.", sep]
    if "bhr" in results:
        L += ["", "[BHR] 강조-완화 비율", sub]
        for c, d in results["bhr"].items():
            bhr = f"{d['bhr']:.3f}" if d["bhr"] is not None else "∞"
            L.append(f"  {d['display_name']:<7} 강조NF {d['booster_nf']:>6.2f} "
                     f"완화NF {d['hedge_nf']:>6.2f}  BHR {bhr:>7}  {d['interpretation']}")
    if "connectives" in results:
        L += ["", "[접속 표지] NF", sub]
        for c, d in results["connectives"].items():
            L.append(f"  >> {d['display_name']}")
            for cat, cd in d["categories"].items():
                L.append(f"     {cat:<8} NF {cd['nf']:>6.2f} (raw {cd['count']})")
    if "tokenizer_coverage" in results:
        cov = results["tokenizer_coverage"]
        L += ["", f"[토크나이저 커버리지] ModernKoreanSubword loaded={cov['subword_model_loaded']}", sub]
        for c, d in cov["critics"].items():
            L.append(f"  {d['display_name']:<7} 한자비율 {d['kiwi_hanja_ratio']:>6} "
                     f"분해비율 {d['subword_decomposition_ratio']} UNK율 {d['subword_unk_rate']}")
    L += ["", sep, "  표↔스크립트: run_keyness(표1-3) run_bhr(표1-4·1-8) "
          "run_connectives(표1-5) run_collocation(MI)", sep]
    report = "\n".join(L)
    p = output_dir / "report.txt"
    p.write_text(report, encoding="utf-8")
    return p
