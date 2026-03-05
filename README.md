# Critical-Debates: 한국문학 비평논쟁의 텍스트마이닝 기반 담론분석

## 연구 목적

한국문학 비평논쟁 텍스트를 코퍼스 언어학(Corpus Linguistics)과 텍스트마이닝(Text Mining)으로 계량 분석하고, 이를 비판적 담론분석(Critical Discourse Analysis) 및 논증 마이닝(Argument Mining)과 결합하여 담론 네트워크(Discourse Network)를 구축한다.

**파일럿 사례**: 1930년대 기교주의 논쟁 (김기림 · 임화 · 박용철)

---

## 이론적 틀 (Theoretical Frameworks)

본 연구는 네 권의 방법론 저작을 이론적 기반으로 삼는다.

### 1. 코퍼스 기반 담론분석 — Baker (2006)

> Paul Baker, *Using Corpora in Discourse Analysis* (Continuum, 2006)

| 개념 | 설명 |
|------|------|
| **빈도 분석 (Frequency)** | 코퍼스 내 단어·개념의 출현 빈도를 계량하여 담론의 중심 주제를 파악 |
| **핵심어 분석 (Keyness)** | 대상 코퍼스의 단어 빈도를 참조 코퍼스와 비교하여 통계적으로 유의미한 특징어 추출 |
| **연어 분석 (Collocation)** | 특정 단어 주변에 통계적으로 유의미하게 동반 출현하는 단어쌍 발견 |
| **용례 분석 (Concordance / KWIC)** | 핵심어를 문맥(Key Word In Context) 속에서 질적으로 검토 |
| **담론의 점증적 효과 (Incremental Effect)** | 단일 텍스트가 아니라 반복 패턴의 누적이 담론을 형성한다는 관점 |
| **삼각검증 (Triangulation)** | 양적 코퍼스 증거와 질적 해석을 교차 검증 |

**본 연구에의 적용**: 비평가별 코퍼스에서 빈도·핵심어·연어를 추출하고, 용례 분석으로 질적 맥락을 확인하여 각 비평가의 담론적 특성을 객관화한다.

### 2. CDA + 코퍼스 언어학 순환적 통합 — Baker, Gabrielatos & McEnery (2013)

> Paul Baker, Costas Gabrielatos, Tony McEnery, *Discourse Analysis and Media Attitudes: The Representation of Islam in the British Press* (Cambridge UP, 2013)

**9단계 순환적 프레임워크**:

```
[1단계] 연구 질문 수립 및 코퍼스 설계
    ↓
[2단계] 코퍼스 구축 · 전처리
    ↓
[3단계] 양적 코퍼스 분석 (빈도, 핵심어, 연어, 클러스터)
    ↓
[4단계] 질적 CDA 분석 (용례 정독, 담론 전략 식별)
    ↓
[5단계] 양적 결과와 질적 해석의 교차 검증
    ↓
[6단계] 새로운 양적 질문 도출 → 3단계로 순환
    ↓
[7단계] 담론 패턴 유형화
    ↓
[8단계] 사회·역사적 맥락과 연결
    ↓
[9단계] 종합 해석 및 이론적 논의
```

- 양적(코퍼스)↔질적(CDA) 분석을 반복 순환하며 점진적으로 심화
- 하향식(이론 주도) + 상향식(데이터 주도) 병행

**본 연구에의 적용**: 1930년대 기교주의 논쟁 코퍼스를 대상으로, 먼저 양적 패턴을 추출한 뒤 비평 원문의 질적 독해와 순환적으로 교차 검증한다.

### 3. 논증 마이닝 — Saint-Dizier & Janier (2019)

> Patrick Saint-Dizier, Mathilde Janier, *Argument Mining: Linguistic Foundations* (ISTE/Wiley, 2019)

| 개념 | 설명 |
|------|------|
| **논증 구조 (Argument Structure)** | 주장(Claim) — 지지(Support) — 공격(Attack)의 삼원 구조 |
| **Toulmin 모델** | 주장(Claim), 근거(Data), 보증(Warrant), 뒷받침(Backing), 한정어(Qualifier), 반박(Rebuttal) |
| **논증 도식 (Argument Schemes)** | 유추, 인과, 권위에의 호소 등 반복적 논증 패턴 |
| **수사 구조 이론 (RST)** | 텍스트 내 담론 관계(정교화, 대조, 조건 등)의 계층적 분석 |
| **담론 표지 (Discourse Markers)** | 논증 관계를 신호하는 언어적 단서 (그러므로, 그러나, 왜냐하면 등) |

**본 연구에의 적용**: 비평 텍스트에서 논증 구조를 추출하여 비평가 간 논쟁의 공격-지지 관계를 체계적으로 매핑한다. 한국어 담론 표지 목록을 구축하여 자동/반자동 논증 탐지에 활용한다.

### 4. 텍스트마이닝-질적 분석 통합 — Wiedemann (2016)

> Gregor Wiedemann, *Text Mining for Qualitative Data Analysis in the Social Sciences* (Springer, 2016)

**V-TM(Validation of Text Mining) 프레임워크 — 3단계**:

```
[Phase 1] 문서 검색 (Document Retrieval)
  → 대규모 텍스트에서 관련 문서를 자동 필터링
  → 검증: 적합성(Precision) · 재현율(Recall) 확인

[Phase 2] 코퍼스 탐색 (Corpus Exploration)
  → 토픽 모델링(LDA), 클러스터링, 공기어 네트워크 등으로 잠재 구조 탐색
  → 검증: 연구자의 질적 판단과 대조

[Phase 3] 반자동 코딩 (Semi-automatic Coding)
  → 텍스트마이닝 결과를 질적 코딩의 출발점으로 활용
  → 검증: 코더 간 신뢰도(Inter-coder reliability) 확인
```

- 텍스트마이닝은 질적 분석을 **대체**하는 것이 아니라 **보조**하는 도구
- 혼합 방법론(Mixed Methods): 양적 탐색 → 질적 심화 → 양적 재검증

**본 연구에의 적용**: 텍스트마이닝으로 비평 텍스트의 잠재 토픽과 담론 클러스터를 탐색한 뒤, 이를 질적 담론분석의 코딩 프레임으로 활용한다.

---

## 통합 연구 방법론: 5단계 프레임워크

네 이론을 종합하여 다음과 같은 5단계 연구 절차를 설계한다.

### Phase 1. 코퍼스 구축 및 전처리

- **1차 텍스트**: 비평가 원문 (신문·잡지 연재 비평, 시론, 논쟁문)
- **2차 텍스트**: 선행연구 (학위논문, 학술논문)
- 전처리: 형태소 분석(KoNLPy/Okt), 불용어 제거, 정규화
- 메타데이터: 저자, 발표일, 매체, 논쟁 국면

### Phase 2. 양적 코퍼스 분석 (Baker 2006)

| 분석 기법 | 목적 | 도구 |
|-----------|------|------|
| 빈도 분석 | 비평가별 핵심 개념 분포 | Python (pandas, collections) |
| 핵심어 분석 (Keyness) | 비평가별 특징적 어휘 추출 | 상대빈도비(Relative Frequency Ratio) |
| 연어 분석 | 개념 간 결합 관계 | PMI, MI, t-score |
| 용례 분석 (KWIC) | 핵심어의 문맥적 의미 확인 | Python concordancer |

### Phase 3. 담론 구조 및 논증 분석 (Saint-Dizier 2019 + Baker et al. 2013)

- 비평 텍스트의 논증 구조 추출 (주장-근거-반박)
- 담론 표지 기반 논증 관계 탐지
- 비평가 간 논쟁 흐름의 시간적 매핑
- 양적 결과 ↔ 질적 CDA 순환 검증 (Baker et al. 9단계 모델)

### Phase 4. 토픽 모델링 및 클러스터링 (Wiedemann 2016)

| 분석 기법 | 목적 |
|-----------|------|
| LDA 토픽 모델링 | 잠재적 담론 주제 발견 |
| 문서 클러스터링 | 비평 텍스트의 담론적 유사성 그룹화 |
| 공기어 네트워크 | 개념 간 연결 구조 시각화 |
| 반자동 코딩 | TM 결과를 질적 코딩 프레임으로 전환 |

### Phase 5. 담론 네트워크 분석 (DNA)

- **행위자-개념 매핑**: 어떤 비평가가 어떤 개념을 사용/지지/공격하는지 네트워크로 시각화
- **담론 네트워크 구축**: Discourse Network Analyzer(DNA)로 행위자-개념 이원 네트워크(two-mode network) 구성
- **네트워크 내보내기**: Gephi 등에서 시각화 및 중심성(centrality) 분석
- **담론 연합(Discourse Coalition) 식별**: 개념 공유 패턴으로 비평가 간 연합/대립 구조 도출

---

## 코퍼스 구조

```
corpus/
├── 1차텍스트/           # 비평가 원문 (primary sources)
│   ├── 김기림_*.txt
│   ├── 임화_*.txt
│   └── 박용철_*.txt
└── 2차텍스트/           # 선행연구 (secondary sources)
    └── (학위논문, 학술논문에서 추출한 텍스트)
```

### 파일명 규칙

`{저자}_{제목약칭}_{발표연도}.txt`

예: `김기림_시의기술인식현실등제문제_1931.txt`

---

## 기술 스택

| 구분 | 도구 |
|------|------|
| 형태소 분석 | KoNLPy (Okt) |
| 텍스트마이닝 | Python (pandas, scikit-learn, gensim) |
| 시각화 | matplotlib, wordcloud |
| 담론 네트워크 | Discourse Network Analyzer (DNA) |
| 네트워크 시각화 | Gephi |
| PDF 텍스트 추출 | PyMuPDF (fitz) |
| 버전 관리 | Git / GitHub |

---

## 파일럿 분석 대상: 기교주의 논쟁 (1930년대)

### 주요 행위자

| 비평가 | 입장 | 핵심 키워드 (Keyness 분석 결과) |
|--------|------|-------------------------------|
| **김기림** | 모더니즘 · 주지주의 | 문명, 군중, 기계, 기하학, 시대정신 |
| **임화** | 사회주의 리얼리즘 | 변증법, 당파, 대중화, 사회주의, 전형 |
| **박용철** | 순수시론 · 유기체론 | 변용, 유기체, 체험, 생리, 영감 |

### 논쟁 구도

```
       김기림 (모더니즘/주지주의)
        ↕ 기교의 의미를 둘러싼 대립
       임화 (리얼리즘/유물론)
        ↕ 시의 본질론을 둘러싼 대립
       박용철 (순수시/유기체론)
        ↕
    세 비평가의 삼각 논쟁 구조
```

---

## 참고문헌

- Baker, P. (2006). *Using Corpora in Discourse Analysis*. Continuum.
- Baker, P., Gabrielatos, C., & McEnery, T. (2013). *Discourse Analysis and Media Attitudes: The Representation of Islam in the British Press*. Cambridge University Press.
- Saint-Dizier, P., & Janier, M. (2019). *Argument Mining: Linguistic Foundations*. ISTE/Wiley.
- Wiedemann, G. (2016). *Text Mining for Qualitative Data Analysis in the Social Sciences: A Study on Democratic Discourse*. Springer.
- Leifeld, P. (2017). Discourse Network Analyzer (DNA). [https://github.com/leifeld/dna](https://github.com/leifeld/dna)
