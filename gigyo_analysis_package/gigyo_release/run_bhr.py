#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""표 1-4·1-8 재현 — BHR(담화 자세) + 내용축×자세."""
import argparse, json, sys
from gigyo import build_corpus
from gigyo.analyses import analyze_bhr, analyze_frequency, classify_content_identity
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--corpus", default="sample_corpus")
    ap.add_argument("--sw-tokenizer", default=None); a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    cp = build_corpus(a.corpus, sw_model_path=a.sw_tokenizer)
    bhr = analyze_bhr(cp); freq = analyze_frequency(cp)
    print("\n[표 1-4] BHR")
    for c, d in bhr.items():
        b = f"{d['bhr']:.3f}" if d["bhr"] is not None else "∞"
        print(f"  {d['display_name']:<7} 강조NF {d['booster_nf']:>6.2f} 완화NF {d['hedge_nf']:>6.2f} "
              f"BHR {b:>7}  {d['interpretation']}")
        print(f"      완화상세 {d['hedge_detail']}")
    print("\n[표 1-8] 내용축 우위 × 자세")
    for c, d in bhr.items():
        nfs = {t: x["nf"] for t, x in freq[c]["terms"].items()}
        b = f"{d['bhr']:.3f}" if d["bhr"] is not None else "∞"
        print(f"  {d['display_name']:<7} 준거 {classify_content_identity(nfs):<8} BHR {b}")
if __name__ == "__main__": main()
