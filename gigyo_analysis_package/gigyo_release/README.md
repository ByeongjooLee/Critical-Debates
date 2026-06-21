# 1930년대 기교주의 논쟁 텍스트마이닝 분석

김기림·임화·박용철 비평 텍스트에 대한 코퍼스 분석 파이프라인. 텍스트마이닝(빈도·로그우도비·상호정보량·강화완화비율·접속 표지)으로 계량 지표를 산출하고, 텍스트언어학(응결성·메타담화) 틀로 해석한다.

> 연구 배경·이론적 틀·분석 결과 해석은 저장소 최상위 [README](../../README.md) 참고. 이 문서는 분석 패키지의 설치·실행에 집중한다.

## 설치

```bash
pip install -r requirements.txt   # kiwipiepy==0.23.2
```

형태소 분석기 버전을 고정한다(버전이 바뀌면 태그 체계가 달라져 표지 패턴이 흔들릴 수 있음).

## 토크나이저 모델 (ModernKoreanSubword)

국한문혼용체 OOV 진단·교차검증에 ByungjunKim/ModernKoreanSubword(김병준 2024)를 사용한다. 첫 실행 시 `tokenizer/241112_vo32000_tokenizer.json`이 없으면 GitHub(raw)에서 자동으로 내려받는다. 수동 지정도 가능:

```bash
python run_all.py --sw-tokenizer tokenizer/241112_vo32000_tokenizer.json
```

네트워크가 막혀 모델이 없으면 Kiwi 단독으로 동작한다(커버리지 진단만 생략).

## 코퍼스 폴더 구조

```
my_corpus/
  김기림/*.txt
  임화/*.txt
  박용철/*.txt
```

파일명(확장자 제외)은 `gigyo/config.py`의 `FILE_PERIOD_MAP`·`FILE_TYPE_MAP` 키와 일치해야 시기·매체 분석이 작동한다. `sample_corpus/`에 동작 확인용 예시(저작권 없는 자작 텍스트)가 들어 있다.

## 빠른 시작

```bash
python test_smoke.py                 # 설치/동작 확인 (ALL PASS 확인)
python run_all.py --corpus sample_corpus --output output
```

## 표 ↔ 스크립트 대응 (재현성)

| 논문 표 | 스크립트 | 산출 |
|---|---|---|
| 표 1-3 | `python run_keyness.py` | 비평가별 LL 상위 어휘(keyness) |
| 표 1-4 · 1-8 | `python run_bhr.py` | 강화완화비율(BHR) · 내용축×자세 |
| 표 1-5 | `python run_connectives.py` | 접속 표지 유형별 NF |
| MI | `python run_collocation.py` | 공기어 상호정보량(윈도 정규화) |
| 전체 | `python run_all.py` | 위 전부 + 시기별 + 커버리지 → `output/` |
| 안정성 검정 | `python run_robustness.py` | 핵심 결론의 LOO·부트스트랩 안정성(아래 참고) |

각 runner는 공통 코어(`gigyo/`)를 불러 쓰는 얇은 진입점이며 `--corpus`, `--sw-tokenizer` 인자를 받는다.

## 안정성 검정 (LOO · 부트스트랩)

`run_robustness.py`는 코퍼스가 작다는 약점을 **전수 검증이 가능한 조건으로 뒤집어**, 핵심 결론이 개별 텍스트에 의존하는지를 정량적으로 측정한다.

> **추가 경위.** 이 검정은 이전 투고본에 대한 심사 과정에서 제기된 지적 — *소규모 코퍼스(29편)에서 도출한 결론을 어떻게 신뢰할 수 있는가* — 에 대한 응답으로 추가되었다. "코퍼스가 충분한가?"라는 물음을 검정 가능한 형태로 바꾸어, 결론이 텍스트를 빼고도 보존되면 그 규모가 그 결론에는 충분하다는 직접 증거가 되도록 설계하였다. 동시에 단일 텍스트에 의존하는 셀은 [불안정]으로 명시 분리하여, 신뢰도를 결론별로 차등화한다.

두 가지 방식을 병행한다.

- **Leave-One-Out (LOO, 29편 전수)**: 텍스트를 한 편씩 제거하고 결론을 재계산한다. 보존율이 높을수록 어떤 단일 텍스트에도 좌우되지 않음을 뜻한다.
- **부트스트랩 (기본 2,000회)**: 비평가 내부에서 텍스트를 복원추출하여 표본 변동에 대한 결론의 안정성과 95% 신뢰구간을 추정한다(시드 고정 → 완전 재현).

모든 지표는 본 분석과 **동일한 `gigyo` 엔진·공식·상수**를 재사용하며(재토큰화 없이 텍스트별 1차량만 한 번 계산), BHR·MI·접속 표지는 정정([../../논문정정표.md](../../논문정정표.md)) 반영 후 값을 기준으로 한다.

```bash
python run_robustness.py                      # 실제 코퍼스(레포 루트) 자동 인식
python run_robustness.py --boot 2000 --topn 5 # 부트스트랩 횟수·LL 상위 N 조정
# → output/robustness_report.txt , output/robustness.json
```

검정 대상과 결과 등급(요약):

| | 검정 결론 | 판정 |
|---|---|---|
| C1 | 박용철 = 완화 밀도 최고 / 상대 서열(임>김>박) | 🟢 텍스트 교란엔 견고 |
| C1 | "셋 다 BHR<1 수렴" · 절대 자세 라벨(유보/단언) | 🔴 마커 코딩 의존 — 의미구분 시 임화>1, 수렴 깨짐(아래 주의) |
| C1 | 임화>김기림 BHR 미세 우위 | 🔴 불안정 (Boot 60%, 95%CI가 0 포함) |
| C2 | 임화 변별어(낭만주의·언어·리얼리즘) | 🟢 견고 |
| C3 | 임화 기교 일시 동원·기술 저빈도 | 🟢 견고 (Boot 96%) |
| C3 | 김기림 기교/기술 역전 · 박용철 전시기 기술 우위 | 🟡 조건부 (LOO 견고, Boot 중간 — 단일 텍스트 의존) |
| C4 | 임화 원인-결과형 최고(정정 역전) | 🟢 견고 (LOO 29/29) |
| C4 | 임화 첨가형 "최고" | 🔴 불안정 (박용철과 초접전) |
| C5 | 내용↔형식 공기 MI 임화 유일 최고 | 🟢 견고 (Boot 99%, 95%CI[2.74, 4.08]) |

> ⚠️ **BHR 절대 해석 주의** — 위 C1의 "수렴"·"유보/단언" 라벨은 LOO·부트스트랩(텍스트 교란)엔 견고하나 **완화 마커 코딩에 의존**한다. KWIC 검토 결과 완화 1위 `ㄹ 수 있다`는 이 비평 레지스터에서 대부분 제시적·관찰적 용법(비완화)이고, 강조 1위 `물론`은 양보 표지였다. 의미를 구분해 재집계하면 임화 BHR>1로 "수렴"은 성립하지 않으므로, 코딩-불변 결론(상대 서열·정성 기술)만 신뢰한다. 재집계·민감도: `run_bhr_sense.py`·`run_bhr_formrule.py`·`run_stance_profile.py`. **수작업 교차검증**: 40개 표본을 사람이 직접 코딩 → 형태규칙과 40/40 일치, 그리고 제2 코더(현대문학 박사수료)의 **블라인드 독립 코딩과도 40/40 일치(Cohen's κ=1.00)**. 단 비완화 95% 편중으로 κ가 불안정하고 두 코더가 동일 분과 배경이라는 한계 — `validation/` 참고.

해석 기준: 보존율 ≥95% → 본문에 그대로 주장 / 80–95% → 교란 텍스트를 각주로 명시 / <80% → 톤다운·셀 분리. 전체 항목은 `output/robustness_report.txt` 참고.

## 다른 코퍼스에 적용하기

원칙적으로 `gigyo/config.py`만 수정한다.
- `KEY_TERMS`, `TRAJECTORY_TERMS`: 추적할 개념어
- `CONNECTIVES_INV`, `BOOSTERS_INV`, `HEDGES_INV`: 표지 사전(어휘/구문/표면)
- `FILE_PERIOD_MAP`, `FILE_TYPE_MAP`: 파일→시기/매체
- 임계값: `COLLOCATION_WINDOW`, `MIN_FREQ_*`, `MIN_CELL_EOJEOLS`

표지 목록(부록용)은 코드에서 추출 가능:
```python
from gigyo.core import export_marker_inventory
export_marker_inventory()
```

## 구조

```
gigyo/
  config.py     # 데이터·설정 (수정 지점)
  core.py       # 토크나이저 · 마커 엔진 · 코퍼스 · 계산식
  analyses.py   # 분석 함수 + 보고서
run_all.py / run_bhr.py / run_keyness.py / run_connectives.py / run_collocation.py
run_robustness.py   # 핵심 결론의 LOO·부트스트랩 안정성 검정
run_bhr_sense.py / run_bhr_formrule.py   # 'ㄹ 수 있다' 의미 구분 BHR 민감도·형태규칙 재집계 + 수작업 교차검증
run_stance_profile.py   # 강조·완화·제시 3원 양태 프로파일(BHR 비율의 대안)
make_coding_sheet.py / make_sample_coding.py   # '수 있다' 수작업 코딩 워크시트(xlsx) 생성
test_smoke.py
sample_corpus/
```

## 방법론 주의 

1. **계량은 패턴 가시화**: 소규모 코퍼스이므로 통계적 일반화가 아니라 패턴 탐색이며, 정규화 빈도·2분할·셀 플래그로 불안정성을 통제한다.
2. **강조/완화 대칭 집계**: BHR의 강조·완화를 모두 형태소 패턴으로 잡는다(완화의 띄어쓰기·활용형 누락 교정). raw 부분문자열 방식 대비 완화 집계가 크게 늘 수 있으므로 BHR 수치는 재산출값을 사용한다.
3. **MI 윈도 정규화**: `log2(co_freq·N / (f_target·f_collocate·span))`, `span=2·window`. 공기 실측치(co_freq)를 함께 보고한다.
4. **토크나이저**: 개념어 계산은 Kiwi 형태소 분석. ModernKoreanSubword는 한자 복합어 분해·OOV 커버리지 진단에 사용(서브워드는 개념어를 조각내므로 본체로 쓰지 않음).
5. **한자 표기 점검**: 국한문혼용체에서 개념어가 한자로 표기된 경우 한글 기준 매칭이 놓칠 수 있다. 커버리지의 한자 비율로 가늠하고, 필요시 `config.py`의 개념어 목록에 한자형을 추가한다.
6. **결론별 신뢰도 차등**: 1번의 '패턴 탐색' 원칙은 `run_robustness.py`의 LOO·부트스트랩으로 실증한다. 결론마다 보존율을 부여해, 견고한 결론과 단일 텍스트 의존 결론을 구분해 보고한다(위 [안정성 검정](#안정성-검정-loo--부트스트랩) 참고).

## 참고

김병준 (2024). 근대 국한문혼용체 자료 서브워드 기반 형태소 분석기의 설계와 적용. 디지털인문학, 1(2), 68-76.
