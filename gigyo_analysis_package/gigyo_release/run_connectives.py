#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""표 1-5 재현 — 접속 표지 유형별 NF."""
import argparse, sys
from gigyo import build_corpus
from gigyo.analyses import analyze_connectives
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--corpus", default="sample_corpus")
    ap.add_argument("--sw-tokenizer", default=None); a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    cp = build_corpus(a.corpus, sw_model_path=a.sw_tokenizer)
    conn = analyze_connectives(cp)
    print("\n[표 1-5] 접속 표지 NF")
    for c, d in conn.items():
        print(f"  >> {d['display_name']}")
        for cat, cd in d["categories"].items():
            print(f"     {cat:<8} NF {cd['nf']:>6.2f}  {cd['marker_detail']}")
if __name__ == "__main__": main()
