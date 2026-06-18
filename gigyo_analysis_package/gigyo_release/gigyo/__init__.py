# -*- coding: utf-8 -*-
"""gigyo — 1930년대 기교주의 논쟁 텍스트마이닝 분석 패키지."""
from . import config, core, analyses
from .core import (ModernTokenizer, Corpus, ensure_sw_model,
                   export_marker_inventory, log_likelihood)

__all__ = ["config", "core", "analyses", "ModernTokenizer", "Corpus",
           "ensure_sw_model", "export_marker_inventory", "log_likelihood"]
__version__ = "1.0.0"


def build_corpus(corpus_dir=".", sw_model_path=None, auto_download=True):
    """토크나이저 준비 + 코퍼스 로드 헬퍼."""
    if sw_model_path is None and auto_download:
        sw_model_path = ensure_sw_model()
    tok = ModernTokenizer(sw_model_path=sw_model_path)
    return Corpus(corpus_dir, tok).load()
