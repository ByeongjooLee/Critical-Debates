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

각 runner는 공통 코어(`gigyo/`)를 불러 쓰는 얇은 진입점이며 `--corpus`, `--sw-tokenizer` 인자를 받는다.

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
test_smoke.py
sample_corpus/
```

## 방법론 주의 (논문 본문에 반영 권장)

1. **계량은 패턴 가시화**: 소규모 코퍼스이므로 통계적 일반화가 아니라 패턴 탐색이며, 정규화 빈도·2분할·셀 플래그로 불안정성을 통제한다.
2. **강조/완화 대칭 집계**: BHR의 강조·완화를 모두 형태소 패턴으로 잡는다(완화의 띄어쓰기·활용형 누락 교정). raw 부분문자열 방식 대비 완화 집계가 크게 늘 수 있으므로 BHR 수치는 재산출값을 사용한다.
3. **MI 윈도 정규화**: `log2(co_freq·N / (f_target·f_collocate·span))`, `span=2·window`. 공기 실측치(co_freq)를 함께 보고한다.
4. **토크나이저**: 개념어 계산은 Kiwi 형태소 분석. ModernKoreanSubword는 한자 복합어 분해·OOV 커버리지 진단에 사용(서브워드는 개념어를 조각내므로 본체로 쓰지 않음).
5. **한자 표기 점검**: 국한문혼용체에서 개념어가 한자로 표기된 경우 한글 기준 매칭이 놓칠 수 있다. 커버리지의 한자 비율로 가늠하고, 필요시 `config.py`의 개념어 목록에 한자형을 추가한다.

## 참고

김병준 (2024). 근대 국한문혼용체 자료 서브워드 기반 형태소 분석기의 설계와 적용. 디지털인문학, 1(2), 68-76.
