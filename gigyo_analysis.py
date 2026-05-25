#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gigyo_analysis.py — 1930년대 기교주의 논쟁 분석 파이프라인 (시계열 확장판)

4장에서 명시한 다섯 분석 도구 + 시기별 시계열 분석을 실제 코퍼스에 적용.

  ┌───────────────────┬──────────────────────────────┐
  │ 텍스트언어학 개념     │ 운용 도구                       │
  ├───────────────────┼──────────────────────────────┤
  │ 미시 결속            │ 접속 표지 분석 (5범주 NF)         │
  │ 어휘적 응결          │ 빈도(NF) · 핵심어(LL) · 공기어(MI)  │
  │ 메타담화            │ BHR (강조-완화 비율)              │
  │ 시계열              │ 용어 궤적·시기별 BHR/접속 표지      │
  └───────────────────┴──────────────────────────────┘

사용법:
    python gigyo_analysis.py --corpus . --output output/
    python gigyo_analysis.py --corpus . --output output/ --reference chosun.txt

폴더 구조 (corpus):
    ./김기림/*.txt
    ./임화/*.txt
    ./박용철/*.txt

방법론적 비판 극복 방안 (5가지):
    1. [순환성]  KEY_TERMS는 '사전 설정' 어휘임을 명시; LL이 '귀납적 추출' 역할
    2. [소규모]  MIN_CELL_EOJEOLS=500 기준 미달 셀에 [소규모-참고용] 경고 표시
    3. [장르]    FILE_TYPE_MAP으로 BHR을 신문연재/잡지평론별 분리 보고
    4. [도구-객체 불일치] 탐색적 레이블 강화; 코퍼스 규모 제약 명시
    5. [셀 희소] 궤적 표에 텍스트 수 표시; 텍스트 <2개 셀 경고
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ============================================================
# 어휘·표지 사전 (4장 명시 설정)
# ============================================================

KEY_TERMS: List[str] = [
    # 핵심 논쟁 어휘 — [사전 설정: 기교주의 논쟁 핵심어]
    "기교", "기술", "형식", "내용",
    # 김기림 준거점
    "지성", "방법", "현대", "주지", "객관", "인텔리겐치아",
    # 임화 준거점
    "사상", "현실", "계급", "반영", "변증법", "부르주아",
    # 박용철 준거점
    "영감", "변용", "감정", "개성", "천재", "음악",
    # 공통 어휘
    "비평", "시", "시인", "예술", "창작", "문학",
    "주관", "논쟁", "시론", "비판",
]

CONNECTIVES: Dict[str, List[str]] = {
    "대조": [
        "그러나", "하지만", "그렇지만", "그래도",
        "도리어", "오히려", "반대로", "그렇다고",
    ],
    "원인-결과": [
        "따라서", "그러므로", "그래서", "그러니까",
        "때문에", "왜냐하면", "그리하여", "고로",
    ],
    "첨가": [
        "또한", "또", "게다가", "아울러",
        "나아가", "한편", "뿐만 아니라", "더욱이",
    ],
    "예시·환언": [
        "예컨대", "예를 들면", "예를 들어",
        "말하자면", "다시 말해", "바꾸어 말하면",
        "바꿔 말하면", "이른바", "즉",
    ],
    "요약·결론": [
        "요컨대", "결국", "결론적으로",
        "요약하면", "무론", "아무튼", "한 마디로",
    ],
}

BOOSTERS: List[str] = [
    "분명히", "확실히", "반드시", "결단코",
    "명백히", "명백하게", "뚜렷이", "단언컨대",
    "진실로", "참으로", "실로", "필연적으로",
    "의심할 여지 없이",
    "확언하건대", "단정컨대", "엄연한", "엄연히",
    "단연코", "응당",
]

HEDGES: List[str] = [
    "아마도", "아마", "어쩌면", "혹시",
    "대체로", "다소", "비교적", "대개",
    "인 듯하다", "로 보인다", "일 수도", "지 모른다",
    "인 것 같", "는 것 같", "ㄴ 셈이",
    "미상불", "대저", "한 듯", "하나니",
]

STOP_WORDS: List[str] = [
    "것", "수", "줄", "바", "데", "리", "그것", "이것", "저것",
    "이", "그", "저", "나", "너", "우리", "그들",
    "때", "곳", "분", "번", "쪽", "터",
    "말", "일", "사실", "정도", "경우", "면", "점",
    "하", "되", "있", "없", "같", "보", "주", "받",
    "오", "가", "알", "모르", "생각", "만들",
    "더", "또", "다", "잘", "왜", "어떻", "이렇",
]

COLLOCATION_TARGETS: List[str] = ["기교", "기술", "형식", "내용", "영감"]

COLLOCATION_WINDOW: int = 5
MIN_FREQ_KEYWORD: int = 5
MIN_FREQ_COLLOCATE: int = 3
TOP_N_KEYWORDS: int = 30
TOP_N_COLLOCATES: int = 15

CRITIC_NAMES: Dict[str, str] = {
    "kim": "김기림",
    "im": "임화",
    "park": "박용철",
    "김기림": "김기림",
    "임화": "임화",
    "박용철": "박용철",
}


# ============================================================
# 시계열 분석 설정
# ============================================================

# 4단계 시기 구분 (발단~여파 = 논쟁 핵심 범위)
# 전사이전·범위밖은 참조용으로 포함하되 핵심 분석은 전사~여파 대상
PERIODS: List[str] = ["전사이전", "전사", "발단", "전개", "여파", "범위밖"]

PERIOD_DATES: Dict[str, str] = {
    "전사이전": "~1932",
    "전사": "1933~1934",
    "발단": "1935.2~1935.11",
    "전개": "1935.12~1936.3",
    "여파": "1936.4~1937",
    "범위밖": "1939~",
}

# 보수적 2분할 (코퍼스 규모 제약 시 사용)
SPLIT_2: Dict[str, List[str]] = {
    "전기": ["전사이전", "전사", "발단"],
    "논쟁기": ["전개", "여파"],
}

# 시계열 추적 대상 용어 (기교→기술 전환, 형식/내용 대립 등)
TRAJECTORY_TERMS: List[str] = [
    "기교", "기술", "영감", "변용",
    "내용", "형식", "사상", "현실",
    "낭만", "리얼리즘", "방법",
]

# 셀 신뢰성 임계값 (어절 수 기준)
MIN_CELL_EOJEOLS: int = 500

# 시기별 파일 귀속 — (비평가폴더명, 파일stem) → 시기
FILE_PERIOD_MAP: Dict[Tuple[str, str], str] = {
    # ──── 김기림 (12편) ────────────────────────────────────
    ("김기림", "(시론사)상아탑의 비극 (p.304)"): "전사이전",   # 1931.7  東亞日報
    ("김기림", "시평의 재비평"): "전사",                        # 1933.5
    ("김기림", "김기림_포에시와 모더니티"): "전사",              # 1933.7  新東亞
    ("김기림", "김기림_현대 예술의 원시에 대한 욕구"): "전사",   # 1933.8  朝鮮日報
    ("김기림", "문예비평(3)—비평의 태도와 표정"): "전사",        # 1934.3
    ("김기림", "김기림_새 인간성과 비평 정신"): "전사",          # 1934.11
    ("김기림", "김기림_시에 있어서의 기교주의의 반성과 발전"): "발단",  # 1935.2  朝鮮日報
    ("김기림", "김기림〈시의 기술, 인식, 현실 등 제문제〉"): "발단",    # 1935.4  詩苑
    ("김기림", "현대비평의 딜렘마"): "발단",                     # 1935.11 朝鮮日報
    ("김기림", "김기림_시인으로서 현실에 적극 관심"): "전개",     # 1936.1
    ("김기림", "과학과 비평과 시"): "여파",                      # 1937.2  朝鮮日報
    ("김기림", "김기림_모더니즘의 역사적 위치"): "범위밖",        # 1939.10 人文評論
    # ──── 임화 (11편) ─────────────────────────────────────
    ("임화", "동지 백철군을 논함 - 그의 시작과 평론에 대하야"): "전사",  # 1933.6  朝鮮日報
    ("임화", "33년을 통하여 본 현대 조선의 시문학"): "전사",      # 1934.1  新東亞
    ("임화", "현대의 문학에 관한 단상"): "전사",                  # 1934.2
    ("임화", "낭만적 정신의 현실적 구조"): "전사",                # 1934.4  朝鮮日報
    ("임화", "담천하의 시단 일년"): "전개",                       # 1935.12 (전개 시작)
    ("임화", "위대한 낭만정신"): "전개",                          # 1936.1  東亞日報
    ("임화", "기교파와 조선시단"): "전개",                        # 1936.2
    ("임화", "언어의 마술성"): "전개",                            # 1936.3
    ("임화", "언어의 현실성"): "여파",                            # 1936.5
    ("임화", "예술적 인식과 표현수단으로서의 언어"): "여파",       # 1936.6
    ("임화", "사실주의의 재인식"): "여파",                        # 1937.10
    # ──── 박용철 (6편) ────────────────────────────────────
    ("박용철", "시문학 창간에 대하여"): "전사이전",               # 1930.3  朝鮮日報
    ("박용철", "효과주의적 비평론강"): "전사이전",                # 1931.11 문예월간
    ("박용철", "신미시단의 회고와 비판"): "전사이전",             # 1931.12 中央日報
    ("박용철", "을해 시단 총평"): "전개",                         # 1935.12
    ("박용철", "기교주의설의 허망"): "전개",                      # 1936.3  東亞日報
    ("박용철", "시적변용에 대해서"): "여파",                      # 1937.1  삼천리문학
}

# 발표 매체 유형 — BHR 장르 보정 분석에 사용
FILE_TYPE_MAP: Dict[Tuple[str, str], str] = {
    # 김기림
    ("김기림", "(시론사)상아탑의 비극 (p.304)"): "신문연재",
    ("김기림", "시평의 재비평"): "잡지평론",
    ("김기림", "김기림_포에시와 모더니티"): "잡지평론",
    ("김기림", "김기림_현대 예술의 원시에 대한 욕구"): "신문연재",
    ("김기림", "문예비평(3)—비평의 태도와 표정"): "신문연재",
    ("김기림", "김기림_새 인간성과 비평 정신"): "신문연재",
    ("김기림", "김기림_시에 있어서의 기교주의의 반성과 발전"): "신문연재",
    ("김기림", "김기림〈시의 기술, 인식, 현실 등 제문제〉"): "잡지평론",
    ("김기림", "현대비평의 딜렘마"): "신문연재",
    ("김기림", "김기림_시인으로서 현실에 적극 관심"): "신문연재",
    ("김기림", "과학과 비평과 시"): "신문연재",
    ("김기림", "김기림_모더니즘의 역사적 위치"): "잡지평론",
    # 임화
    ("임화", "동지 백철군을 논함 - 그의 시작과 평론에 대하야"): "신문연재",
    ("임화", "33년을 통하여 본 현대 조선의 시문학"): "잡지평론",
    ("임화", "현대의 문학에 관한 단상"): "잡지평론",
    ("임화", "낭만적 정신의 현실적 구조"): "신문연재",
    ("임화", "담천하의 시단 일년"): "잡지평론",
    ("임화", "위대한 낭만정신"): "신문연재",
    ("임화", "기교파와 조선시단"): "잡지평론",
    ("임화", "언어의 마술성"): "잡지평론",
    ("임화", "언어의 현실성"): "잡지평론",
    ("임화", "예술적 인식과 표현수단으로서의 언어"): "잡지평론",
    ("임화", "사실주의의 재인식"): "신문연재",
    # 박용철
    ("박용철", "시문학 창간에 대하여"): "신문연재",
    ("박용철", "효과주의적 비평론강"): "잡지평론",
    ("박용철", "신미시단의 회고와 비판"): "신문연재",
    ("박용철", "을해 시단 총평"): "신문연재",
    ("박용철", "기교주의설의 허망"): "신문연재",
    ("박용철", "시적변용에 대해서"): "잡지평론",
}


# ============================================================
# 한국어 토크나이저
# ============================================================

class KoreanTokenizer:
    """한국어 형태소 분석기. kiwipiepy 기반.

    1930년대 국한문혼용체에는 ModernKoreanSubword(김병준 2024)의
    SwTokenizer를 사용하는 것이 이상적이나, 모델이 없으면 기본 Kiwi 사용.
    NF 분모는 어절 수(whitespace 분리) — 4장 명시 "천 어절당 빈도".
    """

    CONTENT_TAGS = (
        "NNG", "NNP", "NNB", "NR", "NP",
        "VV", "VA", "VX",
        "MM", "MAG", "MAJ",
        "SL", "SH",
    )

    def __init__(self, sw_model_path: Optional[str] = None):
        try:
            from kiwipiepy import Kiwi
        except ImportError as e:
            raise ImportError("kiwipiepy 필요: pip install kiwipiepy") from e

        self.kiwi = Kiwi()
        self.sw_tokenizer = None

        if sw_model_path:
            try:
                from kiwipiepy.sw_tokenizer import SwTokenizer
                self.sw_tokenizer = SwTokenizer(sw_model_path, kiwi=self.kiwi)
                print(f"  ✓ SwTokenizer 로드: {sw_model_path}")
            except Exception as e:
                print(f"  ⚠ SwTokenizer 로드 실패, 기본 Kiwi 사용: {e}")

    def tokenize(self, text: str, content_only: bool = True) -> List[str]:
        result = self.kiwi.tokenize(text)
        if content_only:
            return [t.form for t in result if t.tag in self.CONTENT_TAGS]
        return [t.form for t in result]


# ============================================================
# 코퍼스 클래스
# ============================================================

class Corpus:
    """비평가별로 정리된 코퍼스.

    폴더 구조: {corpus_dir}/{critic}/*.txt
    FILE_PERIOD_MAP을 통해 시기별 집계를 지원.
    """

    def __init__(self, corpus_dir: str, tokenizer: KoreanTokenizer):
        self.corpus_dir = Path(corpus_dir)
        self.tokenizer = tokenizer

        self.texts: Dict[Tuple[str, str], List[str]] = {}
        self.raw_texts: Dict[Tuple[str, str], str] = {}
        self.eojeol_counts: Dict[Tuple[str, str], int] = {}

    def load(self) -> "Corpus":
        if not self.corpus_dir.exists():
            raise FileNotFoundError(f"코퍼스 폴더 없음: {self.corpus_dir}")

        for critic_dir in sorted(self.corpus_dir.iterdir()):
            if not critic_dir.is_dir():
                continue
            if critic_dir.name.startswith("."):
                continue
            if critic_dir.name not in CRITIC_NAMES:
                continue
            critic = critic_dir.name

            for txt_file in sorted(critic_dir.glob("*.txt")):
                try:
                    text = txt_file.read_text(encoding="utf-8")
                except Exception as e:
                    print(f"  ⚠ {txt_file.name} 읽기 실패: {e}")
                    continue

                if not text.strip():
                    print(f"  ⚠ {txt_file.name} 빈 파일 — 건너뜀")
                    continue

                tokens = self.tokenizer.tokenize(text, content_only=True)
                key = (critic, txt_file.stem)
                self.texts[key] = tokens
                self.raw_texts[key] = text
                self.eojeol_counts[key] = len(text.split())

                # 시기 확인 (FILE_PERIOD_MAP 미등록 파일 경고)
                if key not in FILE_PERIOD_MAP:
                    print(f"  ⚠ FILE_PERIOD_MAP 미등록: {critic}/{txt_file.stem}")

        if not self.texts:
            raise ValueError(
                f"텍스트 없음: {self.corpus_dir}\n"
                f"폴더 구조 확인: {{김기림,임화,박용철}}/*.txt"
            )
        return self

    def critics(self) -> List[str]:
        return sorted(set(c for c, _ in self.texts.keys()))

    def display_name(self, critic: str) -> str:
        return CRITIC_NAMES.get(critic, critic)

    def critic_tokens(self, critic: str) -> List[str]:
        tokens = []
        for (c, _), t in self.texts.items():
            if c == critic:
                tokens.extend(t)
        return tokens

    def critic_texts_separately(self, critic: str) -> List[List[str]]:
        return [t for (c, _), t in self.texts.items() if c == critic]

    def critic_raw_text(self, critic: str) -> str:
        parts = [t for (c, _), t in self.raw_texts.items() if c == critic]
        return "\n\n".join(parts)

    def critic_eojeols(self, critic: str) -> int:
        return sum(n for (c, _), n in self.eojeol_counts.items() if c == critic)

    def all_tokens(self) -> List[str]:
        out = []
        for t in self.texts.values():
            out.extend(t)
        return out

    def stats(self) -> Dict[str, Dict]:
        s: Dict[str, Dict] = defaultdict(lambda: {"texts": 0, "tokens": 0, "eojeols": 0})
        for key, tokens in self.texts.items():
            critic = key[0]
            s[critic]["texts"] += 1
            s[critic]["tokens"] += len(tokens)
            s[critic]["eojeols"] += self.eojeol_counts[key]
        return {c: dict(d) for c, d in s.items()}

    # ── 시기별 접근 메서드 ───────────────────────────────────

    def get_file_period(self, critic: str, stem: str) -> str:
        return FILE_PERIOD_MAP.get((critic, stem), "미분류")

    def period_keys(self, critic: str, period: str) -> List[Tuple[str, str]]:
        return [k for k in self.texts if k[0] == critic
                and FILE_PERIOD_MAP.get(k, "미분류") == period]

    def period_tokens(self, critic: str, period: str) -> List[str]:
        out: List[str] = []
        for k in self.period_keys(critic, period):
            out.extend(self.texts[k])
        return out

    def period_eojeols(self, critic: str, period: str) -> int:
        return sum(self.eojeol_counts[k] for k in self.period_keys(critic, period))

    def period_text_count(self, critic: str, period: str) -> int:
        return len(self.period_keys(critic, period))

    def period_raw_text(self, critic: str, period: str) -> str:
        parts = [self.raw_texts[k] for k in self.period_keys(critic, period)]
        return "\n\n".join(parts)

    def split2_tokens(self, critic: str, split_name: str) -> List[str]:
        out: List[str] = []
        for period in SPLIT_2.get(split_name, []):
            out.extend(self.period_tokens(critic, period))
        return out

    def split2_eojeols(self, critic: str, split_name: str) -> int:
        return sum(
            self.period_eojeols(critic, p)
            for p in SPLIT_2.get(split_name, [])
        )

    def period_file_types(self, critic: str, period: str) -> Dict[str, int]:
        """해당 시기의 매체 유형 분포"""
        counts: Counter = Counter()
        for k in self.period_keys(critic, period):
            ftype = FILE_TYPE_MAP.get(k, "불명")
            counts[ftype] += 1
        return dict(counts)


# ============================================================
# 분석 도구 ─ 5개 (기존)
# ============================================================

def analyze_frequency(corpus: Corpus, key_terms: List[str] = None) -> Dict:
    """① 빈도 분석 (NF: 천 어절당)

    주의: KEY_TERMS는 '사전 설정' 어휘 목록 — 순환성 위험 있음.
    귀납적 검증은 analyze_keywords()의 LL 결과와 병행할 것.
    """
    key_terms = key_terms or KEY_TERMS
    results: Dict[str, Dict] = {}

    for critic in corpus.critics():
        tokens = corpus.critic_tokens(critic)
        eojeols = corpus.critic_eojeols(critic)
        counter = Counter(tokens)

        term_data = {}
        for term in key_terms:
            count = counter.get(term, 0)
            nf = round((count / eojeols) * 1000, 2) if eojeols > 0 else 0.0
            term_data[term] = {"count": count, "nf": nf}

        results[critic] = {
            "display_name": corpus.display_name(critic),
            "total_eojeols": eojeols,
            "total_content_tokens": len(tokens),
            "terms": term_data,
        }

    return results


def log_likelihood(a: int, b: int, c: int, d: int) -> float:
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
    target_norm = (a / c) * 1_000_000
    ref_norm = (b / d) * 1_000_000
    if ref_norm == 0:
        return float("inf") if a > 0 else 0.0
    return ((target_norm - ref_norm) / ref_norm) * 100


def analyze_keywords(corpus: Corpus,
                     min_freq: int = MIN_FREQ_KEYWORD,
                     top_n: int = TOP_N_KEYWORDS,
                     reference_counter: Optional[Counter] = None,
                     reference_size: Optional[int] = None,
                     stop_words: Optional[set] = None) -> Dict:
    """② 핵심어 분석 (LL) — 귀납적 추출 (사전 설정 KEY_TERMS 무관)

    두 종류:
    - critic_vs_critic: 비평가 vs 나머지 두 비평가 합 (탐색적)
    - critic_vs_reference: 비평 전체 vs 신문 참조 (장르 변별)
    """
    if stop_words is None:
        stop_words = set(STOP_WORDS) - set(KEY_TERMS)
    critics = corpus.critics()
    results: Dict = {"critic_vs_critic": {}, "critic_vs_reference": None}

    for critic in critics:
        target = corpus.critic_tokens(critic)
        target_counter = Counter(target)
        target_size = len(target)

        others: List[str] = []
        for other in critics:
            if other != critic:
                others.extend(corpus.critic_tokens(other))
        other_counter = Counter(others)
        other_size = len(others)

        scores = []
        for word, freq in target_counter.items():
            if freq < min_freq:
                continue
            if word in stop_words:
                continue
            if len(word) == 1 and word not in KEY_TERMS:
                continue
            other_freq = other_counter.get(word, 0)
            target_rate = freq / target_size if target_size > 0 else 0
            other_rate = other_freq / other_size if other_size > 0 else 0
            if target_rate <= other_rate:
                continue
            ll = log_likelihood(freq, other_freq, target_size, other_size)
            pdiff = percent_diff(freq, other_freq, target_size, other_size)
            scores.append({
                "word": word,
                "ll": round(ll, 2),
                "effect_size_pct": round(pdiff, 1) if pdiff != float("inf") else None,
                "target_freq": freq,
                "reference_freq": other_freq,
            })

        scores.sort(key=lambda x: x["ll"], reverse=True)
        results["critic_vs_critic"][critic] = {
            "display_name": corpus.display_name(critic),
            "note": "귀납적 추출 — 탐색적 결과 (코퍼스 규모 제약: LL 절대값보다 상대 순위 중시)",
            "keywords": scores[:top_n],
        }

    if reference_counter and reference_size:
        all_tokens = corpus.all_tokens()
        target_counter = Counter(all_tokens)
        target_size = len(all_tokens)

        scores = []
        for word, freq in target_counter.items():
            if freq < min_freq:
                continue
            if word in stop_words:
                continue
            if len(word) == 1 and word not in KEY_TERMS:
                continue
            ref_freq = reference_counter.get(word, 0)
            target_rate = freq / target_size
            ref_rate = ref_freq / reference_size if reference_size > 0 else 0
            if target_rate <= ref_rate:
                continue
            ll = log_likelihood(freq, ref_freq, target_size, reference_size)
            pdiff = percent_diff(freq, ref_freq, target_size, reference_size)
            scores.append({
                "word": word,
                "ll": round(ll, 2),
                "effect_size_pct": round(pdiff, 1) if pdiff != float("inf") else None,
                "target_freq": freq,
                "reference_freq": ref_freq,
            })

        scores.sort(key=lambda x: x["ll"], reverse=True)
        results["critic_vs_reference"] = {
            "note": "비평 vs 신문 — 비평 장르 특유 어휘",
            "keywords": scores[:top_n],
        }

    return results


def analyze_collocation(corpus: Corpus,
                        target_words: List[str] = None,
                        window: int = COLLOCATION_WINDOW,
                        min_freq: int = MIN_FREQ_COLLOCATE,
                        top_n: int = TOP_N_COLLOCATES) -> Dict:
    """③ 공기어 분석 (MI) — 텍스트 경계 보존"""
    target_words = target_words or COLLOCATION_TARGETS
    results: Dict = {}

    for target_word in target_words:
        results[target_word] = {}
        for critic in corpus.critics():
            critic_texts = corpus.critic_texts_separately(critic)
            co_occur: Counter = Counter()
            target_freq = 0
            word_freq: Counter = Counter()
            total_tokens = 0

            for tokens in critic_texts:
                total_tokens += len(tokens)
                word_freq.update(tokens)
                target_indices = [i for i, w in enumerate(tokens) if w == target_word]
                target_freq += len(target_indices)
                for i in target_indices:
                    start = max(0, i - window)
                    end = min(len(tokens), i + window + 1)
                    for j in range(start, end):
                        if j != i:
                            co_occur[tokens[j]] += 1

            if target_freq == 0:
                results[target_word][critic] = {
                    "display_name": corpus.display_name(critic),
                    "target_freq": 0,
                    "collocates": [],
                    "note": f"'{target_word}' 출현 없음 — 분석 불가",
                }
                continue

            N = total_tokens
            scores = []
            for collocate, co_freq in co_occur.items():
                if co_freq < min_freq or collocate == target_word:
                    continue
                wf = word_freq.get(collocate, 0)
                if wf == 0:
                    continue
                mi = math.log2((co_freq * N) / (target_freq * wf))
                scores.append({
                    "word": collocate,
                    "mi": round(mi, 2),
                    "co_freq": co_freq,
                    "word_freq": wf,
                })

            scores.sort(key=lambda x: x["mi"], reverse=True)
            results[target_word][critic] = {
                "display_name": corpus.display_name(critic),
                "target_freq": target_freq,
                "collocates": scores[:top_n],
                "note": "MI 결과는 KWIC 정성 검증과 함께 해석할 것",
            }

    return results


def _count_marker(tokens: List[str], raw_text: str, marker: str) -> int:
    if " " in marker or len(marker) >= 4:
        return raw_text.count(marker)
    return tokens.count(marker)


def analyze_connectives(corpus: Corpus, markers: Dict = None) -> Dict:
    """④ 접속 표지 분석 (NF per category)"""
    markers = markers or CONNECTIVES
    results: Dict = {}

    for critic in corpus.critics():
        tokens = corpus.critic_tokens(critic)
        raw_text = corpus.critic_raw_text(critic)
        eojeols = corpus.critic_eojeols(critic)

        category_data = {}
        for category, marker_list in markers.items():
            count = 0
            marker_detail = {}
            for m in marker_list:
                c = _count_marker(tokens, raw_text, m)
                if c > 0:
                    marker_detail[m] = c
                count += c
            nf = round((count / eojeols) * 1000, 2) if eojeols > 0 else 0.0
            category_data[category] = {
                "count": count,
                "nf": nf,
                "marker_detail": marker_detail,
            }

        results[critic] = {
            "display_name": corpus.display_name(critic),
            "total_eojeols": eojeols,
            "categories": category_data,
        }

    return results


def _interpret_bhr(bhr: Optional[float]) -> str:
    if bhr is None:
        return "완화 표지 0 — BHR 계산 불가"
    if bhr > 1.5:
        return "단언적·확신적 자세"
    if bhr > 1.0:
        return "약한 단언적 자세"
    if bhr > 0.7:
        return "균형 (약한 유보)"
    return "유보적·신중한 자세"


def analyze_bhr(corpus: Corpus,
                boosters: List[str] = None,
                hedges: List[str] = None) -> Dict:
    """⑤ BHR (Booster-Hedge Ratio) + 장르별 분리 분석"""
    boosters = boosters or BOOSTERS
    hedges = hedges or HEDGES
    results: Dict = {}

    for critic in corpus.critics():
        tokens = corpus.critic_tokens(critic)
        raw_text = corpus.critic_raw_text(critic)
        eojeols = corpus.critic_eojeols(critic)

        b_count, b_detail = 0, {}
        for m in boosters:
            c = _count_marker(tokens, raw_text, m)
            if c > 0:
                b_detail[m] = c
            b_count += c

        h_count, h_detail = 0, {}
        for m in hedges:
            c = _count_marker(tokens, raw_text, m)
            if c > 0:
                h_detail[m] = c
            h_count += c

        b_nf = round((b_count / eojeols) * 1000, 2) if eojeols > 0 else 0.0
        h_nf = round((h_count / eojeols) * 1000, 2) if eojeols > 0 else 0.0
        bhr = round(b_nf / h_nf, 3) if h_nf > 0 else None

        # 장르별 분리
        genre_bhr = _compute_genre_bhr(corpus, critic, boosters, hedges)

        results[critic] = {
            "display_name": corpus.display_name(critic),
            "booster_count": b_count,
            "hedge_count": h_count,
            "booster_nf": b_nf,
            "hedge_nf": h_nf,
            "bhr": bhr,
            "interpretation": _interpret_bhr(bhr),
            "booster_detail": b_detail,
            "hedge_detail": h_detail,
            "genre_bhr": genre_bhr,
            "note": "BHR은 장르(신문연재/잡지평론) 혼합 영향 있음 — genre_bhr 참고",
        }

    return results


def _compute_genre_bhr(corpus: Corpus, critic: str,
                       boosters: List[str], hedges: List[str]) -> Dict:
    """장르(매체 유형)별 BHR 계산"""
    genre_data: Dict[str, Dict] = defaultdict(
        lambda: {"tokens": [], "raw": "", "eojeols": 0, "texts": 0}
    )

    for k, tokens in corpus.texts.items():
        if k[0] != critic:
            continue
        ftype = FILE_TYPE_MAP.get(k, "불명")
        genre_data[ftype]["tokens"].extend(tokens)
        genre_data[ftype]["raw"] += corpus.raw_texts[k] + "\n"
        genre_data[ftype]["eojeols"] += corpus.eojeol_counts[k]
        genre_data[ftype]["texts"] += 1

    out: Dict = {}
    for genre, d in genre_data.items():
        tokens = d["tokens"]
        raw = d["raw"]
        eojeols = d["eojeols"]

        b_count = sum(_count_marker(tokens, raw, m) for m in boosters)
        h_count = sum(_count_marker(tokens, raw, m) for m in hedges)

        b_nf = round((b_count / eojeols) * 1000, 2) if eojeols > 0 else 0.0
        h_nf = round((h_count / eojeols) * 1000, 2) if eojeols > 0 else 0.0
        bhr = round(b_nf / h_nf, 3) if h_nf > 0 else None

        out[genre] = {
            "texts": d["texts"],
            "eojeols": eojeols,
            "booster_nf": b_nf,
            "hedge_nf": h_nf,
            "bhr": bhr,
            "interpretation": _interpret_bhr(bhr),
        }

    return out


# ============================================================
# 시계열 분석 도구 ─ 4개 (신규)
# ============================================================

def _flag_cell(eojeols: int, text_count: int,
               min_eojeols: int = MIN_CELL_EOJEOLS) -> str:
    """셀 신뢰성 플래그 반환"""
    if eojeols == 0:
        return "[없음]"
    flags = []
    if eojeols < min_eojeols:
        flags.append("소규모-참고용")
    if text_count < 2:
        flags.append("단일텍스트")
    return f"[{'/'.join(flags)}]" if flags else ""


def analyze_term_trajectory(corpus: Corpus,
                            terms: List[str] = None,
                            periods: List[str] = None) -> Dict:
    """시기별 핵심 용어 NF 궤적 분석

    기교→기술 전환, 형식/내용 대립, 낭만/현실 축 이동을 추적.
    셀 신뢰성 플래그 포함.
    """
    terms = terms or TRAJECTORY_TERMS
    periods = periods or PERIODS
    results: Dict = {}

    for critic in corpus.critics():
        results[critic] = {
            "display_name": corpus.display_name(critic),
            "periods": {},
        }

        for period in periods:
            tokens = corpus.period_tokens(critic, period)
            eojeols = corpus.period_eojeols(critic, period)
            text_count = corpus.period_text_count(critic, period)
            counter = Counter(tokens)
            flag = _flag_cell(eojeols, text_count)

            term_nfs: Dict[str, float] = {}
            for term in terms:
                count = counter.get(term, 0)
                nf = round((count / eojeols) * 1000, 2) if eojeols > 0 else 0.0
                term_nfs[term] = nf

            results[critic]["periods"][period] = {
                "eojeols": eojeols,
                "text_count": text_count,
                "flag": flag,
                "term_nfs": term_nfs,
                "date_range": PERIOD_DATES.get(period, ""),
            }

    return results


def analyze_period_bhr(corpus: Corpus,
                       boosters: List[str] = None,
                       hedges: List[str] = None,
                       periods: List[str] = None) -> Dict:
    """시기별 BHR — 논쟁 전개에 따른 담화 자세 변화 추적"""
    boosters = boosters or BOOSTERS
    hedges = hedges or HEDGES
    periods = periods or PERIODS
    results: Dict = {}

    for critic in corpus.critics():
        results[critic] = {
            "display_name": corpus.display_name(critic),
            "periods": {},
        }

        for period in periods:
            tokens = corpus.period_tokens(critic, period)
            raw = corpus.period_raw_text(critic, period)
            eojeols = corpus.period_eojeols(critic, period)
            text_count = corpus.period_text_count(critic, period)
            flag = _flag_cell(eojeols, text_count)

            b_count = sum(_count_marker(tokens, raw, m) for m in boosters)
            h_count = sum(_count_marker(tokens, raw, m) for m in hedges)

            b_nf = round((b_count / eojeols) * 1000, 2) if eojeols > 0 else 0.0
            h_nf = round((h_count / eojeols) * 1000, 2) if eojeols > 0 else 0.0
            bhr = round(b_nf / h_nf, 3) if h_nf > 0 else None

            results[critic]["periods"][period] = {
                "eojeols": eojeols,
                "text_count": text_count,
                "flag": flag,
                "booster_nf": b_nf,
                "hedge_nf": h_nf,
                "bhr": bhr,
                "interpretation": _interpret_bhr(bhr),
            }

    return results


def analyze_period_connectives(corpus: Corpus,
                               markers: Dict = None,
                               periods: List[str] = None) -> Dict:
    """시기별 접속 표지 NF — 논증 구조의 시기별 변화 추적"""
    markers = markers or CONNECTIVES
    periods = periods or PERIODS
    results: Dict = {}

    for critic in corpus.critics():
        results[critic] = {
            "display_name": corpus.display_name(critic),
            "periods": {},
        }

        for period in periods:
            tokens = corpus.period_tokens(critic, period)
            raw = corpus.period_raw_text(critic, period)
            eojeols = corpus.period_eojeols(critic, period)
            text_count = corpus.period_text_count(critic, period)
            flag = _flag_cell(eojeols, text_count)

            category_data: Dict = {}
            for category, marker_list in markers.items():
                count = sum(_count_marker(tokens, raw, m) for m in marker_list)
                nf = round((count / eojeols) * 1000, 2) if eojeols > 0 else 0.0
                category_data[category] = {"count": count, "nf": nf}

            results[critic]["periods"][period] = {
                "eojeols": eojeols,
                "text_count": text_count,
                "flag": flag,
                "categories": category_data,
            }

    return results


def analyze_split2_nf(corpus: Corpus,
                      key_terms: List[str] = None) -> Dict:
    """보수적 2분할(전기 vs 논쟁기) NF 비교

    코퍼스 규모 제약이 심할 때(특히 박용철) 시기별 4분할보다 신뢰성 높음.
    """
    key_terms = key_terms or TRAJECTORY_TERMS
    results: Dict = {}

    for critic in corpus.critics():
        results[critic] = {
            "display_name": corpus.display_name(critic),
            "splits": {},
        }

        for split_name, period_list in SPLIT_2.items():
            tokens = corpus.split2_tokens(critic, split_name)
            eojeols = corpus.split2_eojeols(critic, split_name)

            # 포함 텍스트 수
            text_count = sum(
                corpus.period_text_count(critic, p) for p in period_list
            )
            flag = _flag_cell(eojeols, text_count)
            counter = Counter(tokens)

            term_nfs: Dict[str, float] = {}
            for term in key_terms:
                count = counter.get(term, 0)
                nf = round((count / eojeols) * 1000, 2) if eojeols > 0 else 0.0
                term_nfs[term] = nf

            results[critic]["splits"][split_name] = {
                "eojeols": eojeols,
                "text_count": text_count,
                "flag": flag,
                "periods_included": period_list,
                "term_nfs": term_nfs,
            }

    return results


# ============================================================
# 보조 함수
# ============================================================

def load_reference(path: str, tokenizer: KoreanTokenizer) -> Tuple[Counter, int]:
    p = Path(path)
    tokens: List[str] = []
    if p.is_file():
        text = p.read_text(encoding="utf-8")
        tokens = tokenizer.tokenize(text, content_only=True)
    elif p.is_dir():
        for f in p.glob("**/*.txt"):
            text = f.read_text(encoding="utf-8")
            tokens.extend(tokenizer.tokenize(text, content_only=True))
    else:
        raise FileNotFoundError(f"참조 코퍼스 없음: {path}")
    return Counter(tokens), len(tokens)


def _classify_content_identity(term_nfs: Dict[str, float]) -> str:
    form_group = sum(term_nfs.get(t, 0) for t in
                     ["형식", "방법", "지성", "현대", "주지"])
    content_group = sum(term_nfs.get(t, 0) for t in
                        ["내용", "사상", "계급", "현실", "반영"])
    spirit_group = sum(term_nfs.get(t, 0) for t in
                       ["영감", "변용", "감정", "개성", "천재"])
    groups = [
        ("형식 우선", form_group),
        ("내용 우선", content_group),
        ("영감 우선", spirit_group),
    ]
    return max(groups, key=lambda x: x[1])[0]


def save_json(results: Dict, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "results.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    return path


# ============================================================
# 보고서 생성
# ============================================================

def generate_report(results: Dict, output_dir: Path) -> Path:
    lines: List[str] = []
    sep = "=" * 72
    sub = "-" * 72

    lines.append(sep)
    lines.append("  1930년대 기교주의 논쟁 분석 결과 — 텍스트 요약")
    lines.append(sep)
    lines.append("  [방법론 주의사항]")
    lines.append("  · 본 분석은 탐색적(exploratory)이며 소규모 코퍼스 제약이 있음")
    lines.append("  · KEY_TERMS: 사전 설정 어휘(순환성 위험) — LL 귀납 결과와 병행 해석")
    lines.append("  · BHR: 신문연재/잡지평론 장르 혼합 영향 있음 — genre_bhr 참고")
    lines.append("  · [소규모-참고용]: 500 어절 미만 셀 — 통계적 신뢰성 제한")
    lines.append("  · [단일텍스트]: 텍스트 1편만 포함 — 개인 텍스트 특성에 종속될 수 있음")
    lines.append(sep)

    # 코퍼스 통계
    if "corpus_stats" in results:
        lines.append("\n[코퍼스 개요]")
        lines.append(sub)
        for critic, s in results["corpus_stats"].items():
            name = CRITIC_NAMES.get(critic, critic)
            lines.append(
                f"  {name:<6}  {s['texts']:>3}편  |  {s['eojeols']:>7,} 어절"
                f"  |  내용어 {s['tokens']:>6,}"
            )

    # 1. 빈도
    if "frequency" in results:
        lines.append("\n\n[1] 빈도 분석 (NF: 천 어절당) — 사전 설정 KEY_TERMS 기반")
        lines.append(sub)
        for critic, data in results["frequency"].items():
            name = data["display_name"]
            lines.append(f"\n  >> {name} (총 {data['total_eojeols']:,} 어절)")
            sorted_terms = sorted(
                data["terms"].items(),
                key=lambda x: x[1]["nf"], reverse=True
            )[:12]
            for term, td in sorted_terms:
                if td["count"] > 0:
                    lines.append(
                        f"     {term:<10} NF {td['nf']:>7.2f}    (raw {td['count']:>3})"
                    )

    # 2. 핵심어
    if "keywords" in results:
        lines.append("\n\n[2] 핵심어 분석 (LL · %DIFF) — 귀납적 추출 (사전 설정과 독립)")
        lines.append(sub)
        cvc = results["keywords"].get("critic_vs_critic", {})
        for critic, data in cvc.items():
            name = data["display_name"]
            lines.append(f"\n  >> {name} 특유 어휘 상위 12개")
            lines.append(f"     ({data['note']})")
            for s in data["keywords"][:12]:
                pdiff_s = f"{s['effect_size_pct']:>+7.1f}%" if s.get("effect_size_pct") is not None else "    inf"
                lines.append(
                    f"     {s['word']:<10} LL {s['ll']:>7.2f}  | %DIFF {pdiff_s}  | "
                    f"target {s['target_freq']:>3} · other {s['reference_freq']:>3}"
                )

        cvr = results["keywords"].get("critic_vs_reference")
        if cvr:
            lines.append(f"\n  >> 비평 전체 vs 참조 코퍼스 — 비평 장르 특유 어휘 (상위 12)")
            for s in cvr["keywords"][:12]:
                lines.append(
                    f"     {s['word']:<10} LL {s['ll']:>7.2f}  | "
                    f"target {s['target_freq']:>4} · ref {s['reference_freq']:>5}"
                )

    # 3. 공기어
    if "collocations" in results:
        lines.append("\n\n[3] 공기어 분석 (MI)")
        lines.append(sub)
        for target, critic_data in results["collocations"].items():
            lines.append(f"\n  >> 대상 어휘: '{target}'")
            for critic, data in critic_data.items():
                name = data["display_name"]
                tf = data.get("target_freq", 0)
                lines.append(f"     [{name}] '{target}' 출현 {tf}회")
                cols = data.get("collocates", [])
                if not cols:
                    lines.append("       (공기어 추출 불가 — 빈도 임계값 미달)")
                    continue
                for s in cols[:8]:
                    lines.append(
                        f"       {s['word']:<10} MI {s['mi']:>5.2f}  "
                        f"(공기 {s['co_freq']:>2}회 / 총빈도 {s['word_freq']:>3})"
                    )

    # 4. 접속 표지
    if "connectives" in results:
        lines.append("\n\n[4] 접속 표지 분석 (NF: 천 어절당)")
        lines.append(sub)
        for critic, data in results["connectives"].items():
            name = data["display_name"]
            lines.append(f"\n  >> {name}")
            for cat, d in data["categories"].items():
                lines.append(f"     {cat:<10}  NF {d['nf']:>7.2f}  (raw {d['count']})")

    # 5. BHR + 장르별
    if "bhr" in results:
        lines.append("\n\n[5] BHR (강조-완화 비율)")
        lines.append(sub)
        lines.append(f"  {'비평가':<8} {'강조 NF':>10} {'완화 NF':>10} {'BHR':>8}    해석")
        for critic, d in results["bhr"].items():
            name = d["display_name"]
            bhr_str = f"{d['bhr']:.3f}" if d["bhr"] is not None else "∞"
            lines.append(
                f"  {name:<8} {d['booster_nf']:>10.2f} {d['hedge_nf']:>10.2f} "
                f"{bhr_str:>8}    {d['interpretation']}"
            )
        lines.append("\n  [장르별 BHR — 장르 효과 보정]")
        lines.append("  주의: 신문연재/잡지평론 간 BHR 차이는 장르 관습 반영일 수 있음")
        for critic, d in results["bhr"].items():
            name = d["display_name"]
            lines.append(f"\n  >> {name}")
            for genre, gd in d.get("genre_bhr", {}).items():
                bhr_g = f"{gd['bhr']:.3f}" if gd["bhr"] is not None else "∞"
                lines.append(
                    f"     {genre:<10}  {gd['texts']}편/{gd['eojeols']:,}어절  "
                    f"강조NF {gd['booster_nf']:.2f} / 완화NF {gd['hedge_nf']:.2f}  "
                    f"BHR {bhr_g}  ({gd['interpretation']})"
                )

    # 6. 통합 좌표
    if "bhr" in results and "frequency" in results:
        lines.append("\n\n[6] 통합 좌표 — 내용 차원 × 자세 차원")
        lines.append(sub)
        for critic in sorted(results["bhr"].keys()):
            name = results["bhr"][critic]["display_name"]
            bhr = results["bhr"][critic]["bhr"]
            term_nfs = {t: d["nf"] for t, d in results["frequency"][critic]["terms"].items()}
            content_id = _classify_content_identity(term_nfs)
            bhr_str = f"{bhr:.3f}" if bhr is not None else "∞"
            lines.append(
                f"  {name:<8}  내용 정체성: {content_id:<10}  |  자세 BHR {bhr_str}"
            )

    # ──── 시계열 분석 섹션 ────────────────────────────────────

    # 7. 용어 궤적
    if "term_trajectory" in results:
        lines.append("\n\n[7] 용어 NF 궤적 — 시기별 변화 (탐색적)")
        lines.append(sub)
        lines.append("  * [소규모-참고용]=500어절 미만 / [단일텍스트]=1편만 포함")
        lines.append("  * 범위밖(1939~) 셀은 비교 참조용으로만 해석할 것\n")

        traj = results["term_trajectory"]
        active_periods = ["전사이전", "전사", "발단", "전개", "여파"]

        for critic, cdata in traj.items():
            name = cdata["display_name"]
            lines.append(f"  >> {name}")

            # 헤더
            hdr = f"  {'용어':<8}"
            for p in active_periods:
                date = PERIOD_DATES.get(p, "")
                hdr += f"  {p}({date})"
            lines.append(hdr)
            lines.append("  " + "-" * (len(hdr) - 2))

            # 셀 정보 행
            cell_info = f"  {'[셀정보]':<8}"
            for p in active_periods:
                pd_data = cdata["periods"].get(p, {})
                ej = pd_data.get("eojeols", 0)
                tc = pd_data.get("text_count", 0)
                flag = pd_data.get("flag", "")
                cell_info += f"  {tc}편/{ej:,}어절{flag}"
            lines.append(cell_info)

            for term in TRAJECTORY_TERMS:
                row = f"  {term:<8}"
                for p in active_periods:
                    pd_data = cdata["periods"].get(p, {})
                    nf = pd_data.get("term_nfs", {}).get(term, 0.0)
                    eojeols = pd_data.get("eojeols", 0)
                    if eojeols == 0:
                        row += f"  {'—':>12}"
                    else:
                        row += f"  {nf:>12.2f}"
                lines.append(row)
            lines.append("")

        # 기교→기술 전환 요약
        lines.append("  [기교↔기술 전환 분석 — 핵심 관찰]")
        for critic, cdata in traj.items():
            name = cdata["display_name"]
            rows = []
            for p in active_periods:
                pd_data = cdata["periods"].get(p, {})
                nf_g = pd_data.get("term_nfs", {}).get("기교", 0.0)
                nf_s = pd_data.get("term_nfs", {}).get("기술", 0.0)
                ej = pd_data.get("eojeols", 0)
                if ej > 0:
                    rows.append(f"{p}: 기교{nf_g:.2f}/기술{nf_s:.2f}")
            lines.append(f"  {name:<6}  " + "  →  ".join(rows))

    # 8. 시기별 BHR
    if "period_bhr" in results:
        lines.append("\n\n[8] 시기별 BHR — 논쟁 전개에 따른 담화 자세 변화")
        lines.append(sub)
        lines.append("  * 소규모 셀은 참고용으로만 해석\n")
        pbhr = results["period_bhr"]
        active_periods = ["전사이전", "전사", "발단", "전개", "여파"]

        for critic, cdata in pbhr.items():
            name = cdata["display_name"]
            lines.append(f"  >> {name}")
            lines.append(f"  {'시기':<10} {'어절':>8} {'강조NF':>8} {'완화NF':>8} {'BHR':>7}  해석")
            for p in active_periods:
                pd_data = cdata["periods"].get(p, {})
                ej = pd_data.get("eojeols", 0)
                if ej == 0:
                    lines.append(f"  {p:<10} {'—':>8}")
                    continue
                flag = pd_data.get("flag", "")
                b_nf = pd_data.get("booster_nf", 0.0)
                h_nf = pd_data.get("hedge_nf", 0.0)
                bhr = pd_data.get("bhr")
                bhr_s = f"{bhr:.3f}" if bhr is not None else "∞"
                interp = pd_data.get("interpretation", "")
                lines.append(
                    f"  {p:<10} {ej:>8,} {b_nf:>8.2f} {h_nf:>8.2f} {bhr_s:>7}  {interp}{flag}"
                )
            lines.append("")

    # 9. 시기별 접속 표지
    if "period_connectives" in results:
        lines.append("\n\n[9] 시기별 접속 표지 NF — 논증 구조 변화")
        lines.append(sub)
        pconn = results["period_connectives"]
        active_periods = ["전사이전", "전사", "발단", "전개", "여파"]
        cat_names = list(CONNECTIVES.keys())

        for critic, cdata in pconn.items():
            name = cdata["display_name"]
            lines.append(f"\n  >> {name}")
            hdr = f"  {'시기':<10}"
            for cat in cat_names:
                hdr += f"  {cat:>10}"
            lines.append(hdr)
            for p in active_periods:
                pd_data = cdata["periods"].get(p, {})
                ej = pd_data.get("eojeols", 0)
                flag = pd_data.get("flag", "")
                if ej == 0:
                    lines.append(f"  {p:<10}  —")
                    continue
                row = f"  {p:<10}"
                for cat in cat_names:
                    nf = pd_data.get("categories", {}).get(cat, {}).get("nf", 0.0)
                    row += f"  {nf:>10.2f}"
                lines.append(row + f"  {flag}")

    # 10. 2분할 NF
    if "split2_nf" in results:
        lines.append("\n\n[10] 2분할 NF 비교 (전기 vs 논쟁기) — 보수적 시계열")
        lines.append(sub)
        lines.append("  전기 = 전사이전+전사+발단 / 논쟁기 = 전개+여파")
        lines.append("  * 박용철 전기 텍스트는 논쟁 전사이전 작품 포함 — 해석 시 주의\n")
        s2 = results["split2_nf"]

        for critic, cdata in s2.items():
            name = cdata["display_name"]
            lines.append(f"  >> {name}")
            lines.append(
                f"  {'용어':<8}  {'전기 NF':>10}  {'논쟁기 NF':>10}  {'증감':>8}"
            )
            for term in TRAJECTORY_TERMS:
                early_nf = cdata["splits"]["전기"]["term_nfs"].get(term, 0.0)
                debate_nf = cdata["splits"]["논쟁기"]["term_nfs"].get(term, 0.0)
                diff = debate_nf - early_nf
                diff_str = f"{diff:>+8.2f}"
                lines.append(
                    f"  {term:<8}  {early_nf:>10.2f}  {debate_nf:>10.2f}  {diff_str}"
                )

            e_ej = cdata["splits"]["전기"]["eojeols"]
            e_tc = cdata["splits"]["전기"]["text_count"]
            d_ej = cdata["splits"]["논쟁기"]["eojeols"]
            d_tc = cdata["splits"]["논쟁기"]["text_count"]
            e_flag = cdata["splits"]["전기"]["flag"]
            d_flag = cdata["splits"]["논쟁기"]["flag"]
            lines.append(
                f"  [전기 {e_tc}편/{e_ej:,}어절{e_flag} | 논쟁기 {d_tc}편/{d_ej:,}어절{d_flag}]"
            )
            lines.append("")

    lines.append("\n" + sep)
    lines.append("  [종합 방법론 검토]")
    lines.append("  1. [순환성] KEY_TERMS 기반 빈도([1])는 사전 설정 어휘 편향 있음.")
    lines.append("     → LL 귀납 추출([2])과 교차 검증하여 독립적 근거 확보 필요.")
    lines.append("  2. [소규모] 박용철 코퍼스(3편/논쟁기)는 셀 신뢰성 매우 낮음.")
    lines.append("     → [소규모-참고용] 플래그 셀은 정성 해석 보완 필수.")
    lines.append("  3. [장르] BHR은 신문연재(연속기고)/잡지평론 장르 관습 혼재.")
    lines.append("     → genre_bhr로 장르 효과 분리 후 해석 권고.")
    lines.append("  4. [도구-객체 불일치] Kiwi는 1930년대 국한문혼용체에 최적화 안 됨.")
    lines.append("     → 탐색적 패턴 포착에 한정; ModernKoreanSubword 검증 병행 권고.")
    lines.append("  5. [시계열 셀 희소] 전개·여파 박용철 셀은 각 2~3편 수준.")
    lines.append("     → 4분할보다 2분할([10]) 결과의 신뢰성이 더 높음.")
    lines.append(sep)

    report = "\n".join(lines)
    path = output_dir / "report.txt"
    path.write_text(report, encoding="utf-8")
    return path


def generate_dashboard(results: Dict, output_dir: Path, template_path: str) -> Optional[Path]:
    tpath = Path(template_path)
    if not tpath.exists():
        return None

    html = tpath.read_text(encoding="utf-8")
    data_script = (
        "\n<script>\n"
        "// === 실제 분석 결과 (gigyo_analysis.py 주입) ===\n"
        f"window.REAL_ANALYSIS_DATA = {json.dumps(results, ensure_ascii=False, default=str)};\n"
        "console.log('실제 분석 결과 로드됨. window.REAL_ANALYSIS_DATA로 확인');\n"
        "console.warn('차트는 모의 데이터. 실제 값은 results.json / report.txt 참조.');\n"
        "</script>\n"
    )
    html = html.replace("</body>", data_script + "</body>")
    out = output_dir / "dashboard_with_data.html"
    out.write_text(html, encoding="utf-8")
    return out


# ============================================================
# 메인
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="1930년대 기교주의 논쟁 분석 파이프라인 (5도구 + 시계열)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--corpus", default=".",
                        help="코퍼스 폴더 (기본: 현재 폴더)")
    parser.add_argument("--output", default="output",
                        help="출력 폴더 (기본: output)")
    parser.add_argument("--reference",
                        help="참조 코퍼스 경로 — .txt 파일 또는 폴더 (선택)")
    parser.add_argument("--template",
                        help="HTML 대시보드 템플릿 경로 (선택)")
    parser.add_argument("--sw-tokenizer",
                        help="ModernKoreanSubword 모델 경로 (생략 시 자동 탐색)")
    parser.add_argument("--vocab-size", choices=["32000", "48000", "64000"], default="32000",
                        help="vocab 크기 선택 (기본: 32000)")
    parser.add_argument("--skip-timeseries", action="store_true",
                        help="시계열 분석 건너뜀 (빠른 기본 분석만)")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    print("=" * 72)
    print("  기교주의 논쟁 분석 파이프라인 (시계열 확장판)")
    print("=" * 72)

    # 1. 토크나이저
    print("\n[Step 1] 토크나이저 초기화")
    sw_path = args.sw_tokenizer
    if not sw_path:
        script_dir = Path(__file__).parent
        candidate = script_dir / f"241112_vo{args.vocab_size}_tokenizer.json"
        if candidate.exists():
            sw_path = str(candidate)
            print(f"  ✓ SwTokenizer 자동 감지: {candidate.name}")
        else:
            print(f"  ℹ SwTokenizer 없음 ({candidate.name} 미발견) — 기본 Kiwi 사용")

    tokenizer = KoreanTokenizer(sw_model_path=sw_path)

    # 2. 코퍼스
    print(f"\n[Step 2] 코퍼스 로드: {args.corpus}")
    try:
        corpus = Corpus(args.corpus, tokenizer).load()
    except (FileNotFoundError, ValueError) as e:
        print(f"\n❌ {e}", file=sys.stderr)
        sys.exit(1)

    stats = corpus.stats()
    for critic, s in stats.items():
        name = CRITIC_NAMES.get(critic, critic)
        print(f"  · {name}: {s['texts']}편 | {s['eojeols']:,} 어절 | 내용어 {s['tokens']:,}개")

    # 시기별 코퍼스 개요 출력
    print("\n  [시기별 텍스트 분포]")
    for period in PERIODS:
        row_parts = []
        for critic in corpus.critics():
            tc = corpus.period_text_count(critic, period)
            ej = corpus.period_eojeols(critic, period)
            name = CRITIC_NAMES.get(critic, critic)
            if tc > 0:
                row_parts.append(f"{name} {tc}편/{ej:,}어절")
        if row_parts:
            date = PERIOD_DATES.get(period, "")
            print(f"  {period}({date}): {' | '.join(row_parts)}")

    # 3. 참조 코퍼스
    ref_counter, ref_size = None, None
    if args.reference:
        print(f"\n[Step 3] 참조 코퍼스 로드: {args.reference}")
        try:
            ref_counter, ref_size = load_reference(args.reference, tokenizer)
            print(f"  · {ref_size:,} 어절")
        except FileNotFoundError as e:
            print(f"  ⚠ {e} — 참조 코퍼스 분석 건너뜀")

    # 4. 기본 분석
    print("\n[Step 4] 기본 분석 실행")
    results: Dict = {"corpus_stats": stats}

    print("  · 빈도 분석 (NF) ...", end=" ", flush=True)
    results["frequency"] = analyze_frequency(corpus)
    print("✓")

    print("  · 핵심어 분석 (LL) ...", end=" ", flush=True)
    results["keywords"] = analyze_keywords(
        corpus,
        reference_counter=ref_counter,
        reference_size=ref_size,
    )
    print("✓")

    print("  · 공기어 분석 (MI) ...", end=" ", flush=True)
    results["collocations"] = analyze_collocation(corpus)
    print("✓")

    print("  · 접속 표지 분석 ...", end=" ", flush=True)
    results["connectives"] = analyze_connectives(corpus)
    print("✓")

    print("  · BHR 분석 (장르별 포함) ...", end=" ", flush=True)
    results["bhr"] = analyze_bhr(corpus)
    print("✓")

    # 5. 시계열 분석
    if not args.skip_timeseries:
        print("\n[Step 5] 시계열 분석 실행")

        print("  · 용어 궤적 분석 ...", end=" ", flush=True)
        results["term_trajectory"] = analyze_term_trajectory(corpus)
        print("✓")

        print("  · 시기별 BHR ...", end=" ", flush=True)
        results["period_bhr"] = analyze_period_bhr(corpus)
        print("✓")

        print("  · 시기별 접속 표지 ...", end=" ", flush=True)
        results["period_connectives"] = analyze_period_connectives(corpus)
        print("✓")

        print("  · 2분할 NF 비교 ...", end=" ", flush=True)
        results["split2_nf"] = analyze_split2_nf(corpus)
        print("✓")

    # 6. 저장
    print(f"\n[Step 6] 결과 저장: {args.output}")
    output_dir = Path(args.output)

    json_path = save_json(results, output_dir)
    print(f"  ✓ JSON: {json_path}")

    report_path = generate_report(results, output_dir)
    print(f"  ✓ Report: {report_path}")

    if args.template:
        dash = generate_dashboard(results, output_dir, args.template)
        if dash:
            print(f"  ✓ Dashboard: {dash}")
        else:
            print(f"  ⚠ 템플릿 없음: {args.template}")

    print()
    print(report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
