# -*- coding: utf-8 -*-
"""
core.py — 엔진(토크나이저 · 마커 엔진 · 코퍼스 · 계산식)

config.py 에만 의존한다. 거의 수정할 일 없는 부분.
"""
from __future__ import annotations

import math
import re
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from . import config as C

Morph = Tuple[str, str]


# ============================================================
# ModernKoreanSubword 모델 자동 확보
# ============================================================

def ensure_sw_model(dest_dir: str = "tokenizer") -> Optional[str]:
    """서브워드 모델이 없으면 GitHub(raw)에서 내려받아 경로를 반환.
    네트워크가 막혀 있으면 None(→ Kiwi 단독으로 동작)."""
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / C.SW_MODEL_FILENAME
    if path.exists() and path.stat().st_size > 100_000:
        return str(path)
    try:
        print(f"  · ModernKoreanSubword 모델 다운로드: {C.SW_MODEL_URL}")
        urllib.request.urlretrieve(C.SW_MODEL_URL, path)
        if path.stat().st_size > 100_000:
            print(f"  ✓ 저장: {path}")
            return str(path)
    except Exception as e:
        print(f"  ⚠ 모델 다운로드 실패({e}) — Kiwi 단독 진행")
    return None


# ============================================================
# 토크나이저 — Kiwi(본체) + ModernKoreanSubword(진단/교차검증)
# ============================================================

class ModernTokenizer:
    """Kiwi 형태소 분석을 개념·표지 산출의 본체로,
    ModernKoreanSubword(SwTokenizer)를 국한문혼용체 OOV 진단에 사용.
    서브워드는 개념어를 조각내므로 개념 계산에 쓰지 않는다."""

    def __init__(self, sw_model_path: Optional[str] = None):
        try:
            from kiwipiepy import Kiwi
        except ImportError as e:
            raise ImportError("kiwipiepy 필요: pip install kiwipiepy==0.23.2") from e
        self.kiwi = Kiwi()
        self.sw = None
        self.sw_path = sw_model_path
        self._morph_cache: Dict[str, List[Morph]] = {}
        if sw_model_path:
            try:
                from kiwipiepy.sw_tokenizer import SwTokenizer
                self.sw = SwTokenizer(sw_model_path, kiwi=self.kiwi)
                print(f"  ✓ ModernKoreanSubword 로드: {Path(sw_model_path).name}")
            except Exception as e:
                print(f"  ⚠ SwTokenizer 로드 실패 → Kiwi 단독: {e}")
                self.sw = None

    def morphs(self, text: str) -> List[Morph]:
        if text not in self._morph_cache:
            self._morph_cache[text] = [(t.form, t.tag) for t in self.kiwi.tokenize(text)]
        return self._morph_cache[text]

    def tokenize(self, text: str, content_only: bool = True) -> List[str]:
        ms = self.kiwi.tokenize(text)
        if content_only:
            return [t.form for t in ms if t.tag in C.CONTENT_TAGS]
        return [t.form for t in ms]

    # ── ModernKoreanSubword 실제 사용부 ─────────────────────
    def _encode_ids(self, text: str) -> List[int]:
        ids = self.sw.encode(text)
        if isinstance(ids, tuple):
            ids = ids[0]
        return [int(i) for i in list(ids)]

    def subword_segments(self, text: str) -> Optional[List[str]]:
        if self.sw is None:
            return None
        try:
            id2v = self.sw.id2vocab
            return [id2v[i].lstrip("#") for i in self._encode_ids(text)]
        except Exception:
            return None

    def subword_unk_rate(self, text: str) -> Optional[float]:
        if self.sw is None:
            return None
        try:
            ids = self._encode_ids(text)
            if not ids:
                return 0.0
            unk = getattr(self.sw, "unk_token_id", None)
            if unk is None:
                return None
            return round(sum(1 for i in ids if i == int(unk)) / len(ids), 4)
        except Exception:
            return None

    def subword_token_count(self, text: str) -> Optional[int]:
        if self.sw is None:
            return None
        try:
            return len(self._encode_ids(text))
        except Exception:
            return None

    def kiwi_oov_proxy(self, text: str) -> Dict[str, float]:
        ms = self.morphs(text)
        n = len(ms) or 1
        diag = sum(1 for _, tag in ms if tag in C.DIAG_TAGS)
        hanja = sum(1 for _, tag in ms if tag == "SH")
        return {"total_morphs": len(ms),
                "diag_token_ratio": round(diag / n, 4),
                "hanja_ratio": round(hanja / n, 4)}


# ============================================================
# 마커 엔진 — 형태소 패턴 + 표면 정규식 (통일 집계)
# ============================================================

def _cond_ok(morph: Morph, cond) -> bool:
    form, tag = morph
    want_form, want_tag = cond
    if want_form is not None and form != want_form:
        return False
    if want_tag is not None and not tag.startswith(want_tag):
        return False
    return True


def _match_construction(morphs: Sequence[Morph], pattern, max_gap: int = 2) -> int:
    n = len(morphs)
    count, i = 0, 0
    while i < n:
        if not _cond_ok(morphs[i], pattern[0]):
            i += 1
            continue
        ok, last = True, i
        for cond in pattern[1:]:
            found = -1
            for k in range(last + 1, min(n, last + 1 + max_gap + 1)):
                if _cond_ok(morphs[k], cond):
                    found = k
                    break
            if found < 0:
                ok = False
                break
            last = found
        if ok:
            count += 1
            i = last + 1
        else:
            i += 1
    return count


class MarkerEngine:
    """접속·강조·완화 표지를 한 방식으로 일괄 집계."""

    def __init__(self, inventory: Dict[str, List[dict]], max_gap: int = 2):
        self.inventory = inventory
        self.max_gap = max_gap

    def count_all(self, morphs: Sequence[Morph], raw_text: str) -> Dict[str, dict]:
        raw_norm = re.sub(r"\s+", " ", raw_text)
        forms = [f for f, _ in morphs]
        out: Dict[str, dict] = {}
        for cat, entries in self.inventory.items():
            total, detail = 0, {}
            for e in entries:
                kind, val, label = e["kind"], e["value"], e["label"]
                if kind == "lex":
                    c = forms.count(val)
                elif kind == "con":
                    c = _match_construction(morphs, val, self.max_gap)
                elif kind == "sur":
                    c = len(re.findall(val, raw_norm))
                else:
                    c = 0
                if c > 0:
                    detail[label] = detail.get(label, 0) + c
                total += c
            out[cat] = {"count": total, "detail": detail}
        return out


CONNECTIVE_ENGINE = MarkerEngine(C.CONNECTIVES_INV)
BOOSTER_ENGINE = MarkerEngine(C.BOOSTERS_INV)
HEDGE_ENGINE = MarkerEngine(C.HEDGES_INV)


def export_marker_inventory() -> Dict[str, Dict[str, List[str]]]:
    """부록용 — 실제 사용 표지 목록(어휘/구문/표면 표시)."""
    def fmt(inv):
        out = {}
        for cat, entries in inv.items():
            out[cat] = [f"{e['label']}({ {'lex':'어휘','con':'구문','sur':'표면'}[e['kind']] })"
                        for e in entries]
        return out
    return {"접속 표지": fmt(C.CONNECTIVES_INV),
            "강조 표지(booster)": fmt(C.BOOSTERS_INV),
            "완화 표지(hedge)": fmt(C.HEDGES_INV)}


# ============================================================
# 계산식 (순수 함수)
# ============================================================

def log_likelihood(a: int, b: int, c: int, d: int) -> float:
    """Dunning LL. a,b=대상/참조 빈도, c,d=대상/참조 크기."""
    if a == 0 and b == 0:
        return 0.0
    total = c + d
    if total == 0:
        return 0.0
    E1 = c * (a + b) / total
    E2 = d * (a + b) / total
    ll = 0.0
    if a > 0 and E1 > 0:
        ll += a * math.log(a / E1)
    if b > 0 and E2 > 0:
        ll += b * math.log(b / E2)
    return 2 * ll


def percent_diff(a: int, b: int, c: int, d: int) -> float:
    if c == 0 or d == 0:
        return 0.0
    t = (a / c) * 1_000_000
    r = (b / d) * 1_000_000
    if r == 0:
        return float("inf") if a > 0 else 0.0
    return ((t - r) / r) * 100


def flag_cell(eojeols: int, text_count: int,
              min_eojeols: int = C.MIN_CELL_EOJEOLS) -> str:
    if eojeols == 0:
        return "[없음]"
    flags = []
    if eojeols < min_eojeols:
        flags.append("소규모-참고용")
    if text_count < 2:
        flags.append("단일텍스트")
    return f"[{'/'.join(flags)}]" if flags else ""


# ============================================================
# 코퍼스
# ============================================================

class Corpus:
    """폴더 구조: {corpus_dir}/{비평가}/*.txt"""

    def __init__(self, corpus_dir: str, tokenizer: ModernTokenizer):
        self.corpus_dir = Path(corpus_dir)
        self.tokenizer = tokenizer
        self.texts: Dict[Tuple[str, str], List[str]] = {}
        self.raw_texts: Dict[Tuple[str, str], str] = {}
        self.eojeol_counts: Dict[Tuple[str, str], int] = {}

    def load(self) -> "Corpus":
        if not self.corpus_dir.exists():
            raise FileNotFoundError(f"코퍼스 폴더 없음: {self.corpus_dir}")
        for critic_dir in sorted(self.corpus_dir.iterdir()):
            if not critic_dir.is_dir() or critic_dir.name.startswith("."):
                continue
            if critic_dir.name not in C.CRITIC_NAMES:
                continue
            critic = critic_dir.name
            for txt in sorted(critic_dir.glob("*.txt")):
                text = txt.read_text(encoding="utf-8")
                if not text.strip():
                    continue
                key = (critic, txt.stem)
                self.texts[key] = self.tokenizer.tokenize(text, content_only=True)
                self.raw_texts[key] = text
                self.eojeol_counts[key] = len(text.split())
                if key not in C.FILE_PERIOD_MAP:
                    print(f"  ⚠ FILE_PERIOD_MAP 미등록: {critic}/{txt.stem}")
        if not self.texts:
            raise ValueError(f"텍스트 없음: {self.corpus_dir}")
        return self

    def critics(self) -> List[str]:
        return sorted({c for c, _ in self.texts})

    def display_name(self, c: str) -> str:
        return C.CRITIC_NAMES.get(c, c)

    def critic_tokens(self, c: str) -> List[str]:
        out = []
        for (cc, _), t in self.texts.items():
            if cc == c:
                out.extend(t)
        return out

    def critic_texts_separately(self, c: str) -> List[List[str]]:
        return [t for (cc, _), t in self.texts.items() if cc == c]

    def critic_raw_text(self, c: str) -> str:
        return "\n\n".join(v for (cc, _), v in self.raw_texts.items() if cc == c)

    def critic_eojeols(self, c: str) -> int:
        return sum(n for (cc, _), n in self.eojeol_counts.items() if cc == c)

    def all_tokens(self) -> List[str]:
        out = []
        for t in self.texts.values():
            out.extend(t)
        return out

    def stats(self) -> Dict[str, Dict]:
        s = defaultdict(lambda: {"texts": 0, "tokens": 0, "eojeols": 0})
        for key, t in self.texts.items():
            s[key[0]]["texts"] += 1
            s[key[0]]["tokens"] += len(t)
            s[key[0]]["eojeols"] += self.eojeol_counts[key]
        return {c: dict(d) for c, d in s.items()}

    # 시기 접근
    def _period_keys(self, c, p):
        return [k for k in self.texts if k[0] == c and C.FILE_PERIOD_MAP.get(k, "미분류") == p]

    def period_tokens(self, c, p):
        out = []
        for k in self._period_keys(c, p):
            out.extend(self.texts[k])
        return out

    def period_eojeols(self, c, p):
        return sum(self.eojeol_counts[k] for k in self._period_keys(c, p))

    def period_text_count(self, c, p):
        return len(self._period_keys(c, p))

    def period_raw_text(self, c, p):
        return "\n\n".join(self.raw_texts[k] for k in self._period_keys(c, p))

    def split2_tokens(self, c, name):
        out = []
        for p in C.SPLIT_2.get(name, []):
            out.extend(self.period_tokens(c, p))
        return out

    def split2_eojeols(self, c, name):
        return sum(self.period_eojeols(c, p) for p in C.SPLIT_2.get(name, []))
