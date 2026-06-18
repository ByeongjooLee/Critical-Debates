#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""표 1-3 재현 — 비평가별 LL 상위 어휘(keyness)."""
import argparse, sys
from gigyo import build_corpus
from gigyo.analyses import analyze_keywords
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--corpus", default="sample_corpus")
    ap.add_argument("--sw-tokenizer", default=None); ap.add_argument("--top", type=int, default=8)
    a = ap.parse_args(); sys.stdout.reconfigure(encoding="utf-8")
    cp = build_corpus(a.corpus, sw_model_path=a.sw_tokenizer)
    kw = analyze_keywords(cp)
    print("\n[표 1-3] 비평가별 LL 상위 어휘")
    for c, d in kw["critic_vs_critic"].items():
        print(f"  >> {d['display_name']}")
        for s in d["keywords"][:a.top]:
            print(f"     {s['word']:<10} LL {s['ll']:>7.2f}  (대상 {s['target_freq']} / 타 {s['reference_freq']})")
if __name__ == "__main__": main()
