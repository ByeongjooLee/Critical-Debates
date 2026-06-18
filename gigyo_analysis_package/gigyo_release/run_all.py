#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""전체 파이프라인 — 모든 표를 한 번에 재현."""
import argparse, sys
from pathlib import Path
from gigyo import build_corpus, analyses as A
from gigyo.analyses import (analyze_frequency, analyze_keywords, analyze_collocation,
    analyze_connectives, analyze_bhr, analyze_term_trajectory, analyze_period_bhr,
    analyze_period_connectives, analyze_split2_nf, analyze_tokenizer_coverage,
    save_json, generate_report)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="sample_corpus")
    ap.add_argument("--output", default="output")
    ap.add_argument("--sw-tokenizer", default=None)
    ap.add_argument("--no-download", action="store_true")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    corpus = build_corpus(a.corpus, sw_model_path=a.sw_tokenizer,
                          auto_download=not a.no_download)
    r = {"corpus_stats": corpus.stats()}
    r["frequency"] = analyze_frequency(corpus)
    r["keywords"] = analyze_keywords(corpus)
    r["collocations"] = analyze_collocation(corpus)
    r["connectives"] = analyze_connectives(corpus)
    r["bhr"] = analyze_bhr(corpus)
    r["term_trajectory"] = analyze_term_trajectory(corpus)
    r["period_bhr"] = analyze_period_bhr(corpus)
    r["period_connectives"] = analyze_period_connectives(corpus)
    r["split2_nf"] = analyze_split2_nf(corpus)
    r["tokenizer_coverage"] = analyze_tokenizer_coverage(corpus)
    out = Path(a.output)
    save_json(r, out)
    rp = generate_report(r, out)
    print(rp.read_text(encoding="utf-8"))

if __name__ == "__main__":
    main()
