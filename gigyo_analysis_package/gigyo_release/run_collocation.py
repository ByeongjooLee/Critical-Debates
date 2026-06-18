#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MI(공기어) 재현 — 윈도 정규화 + 공기 실측치."""
import argparse, sys
from gigyo import build_corpus
from gigyo.analyses import analyze_collocation
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--corpus", default="sample_corpus")
    ap.add_argument("--sw-tokenizer", default=None)
    ap.add_argument("--targets", nargs="*", default=["내용", "형식", "기교", "기술"])
    a = ap.parse_args(); sys.stdout.reconfigure(encoding="utf-8")
    cp = build_corpus(a.corpus, sw_model_path=a.sw_tokenizer)
    col = analyze_collocation(cp, target_words=a.targets)
    for tgt, cd in col.items():
        print(f"\n[MI] 대상 '{tgt}'")
        for c, d in cd.items():
            print(f"  [{d['display_name']}] '{tgt}' {d['target_freq']}회")
            for s in d["collocates"][:5]:
                print(f"     {s['word']:<8} MI {s['mi']:>5} (공기 {s['co_freq']}/총 {s['word_freq']}/기대 {s['expected']})")
if __name__ == "__main__": main()
