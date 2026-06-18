#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_html_report.py — results.json을 상세 HTML 리포트로 변환.

사용:  python build_html_report.py --results ../../output/results.json --out ../../output/analysis_report.html
"""
import argparse, json, sys, html
from pathlib import Path

CRITIC_ORDER = ["김기림", "임화", "박용철"]
CRITIC_COLOR = {"김기림": "#2563eb", "임화": "#dc2626", "박용철": "#059669"}
PERIODS_ACTIVE = ["전사이전", "전사", "발단", "전개", "여파"]


def esc(x):
    return html.escape(str(x))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="../../output/results.json")
    ap.add_argument("--out", default="../../output/analysis_report.html")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    d = json.load(open(a.results, encoding="utf-8"))
    P = []  # HTML 조각

    def add(s): P.append(s)

    # ── 헤더/스타일 ───────────────────────────────────────────
    add("""<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>기교주의 논쟁 — 상세 분석 리포트</title>
<style>
:root{--bg:#f8fafc;--card:#fff;--ink:#0f172a;--mut:#64748b;--line:#e2e8f0;--kim:#2563eb;--im:#dc2626;--park:#059669}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,'Segoe UI','Malgun Gothic',sans-serif;line-height:1.65}
.wrap{max-width:1040px;margin:0 auto;padding:32px 20px 80px}
h1{font-size:26px;margin:0 0 4px}
.sub{color:var(--mut);margin:0 0 24px}
h2{font-size:20px;margin:40px 0 6px;padding-bottom:8px;border-bottom:2px solid var(--line)}
h3{font-size:15px;margin:18px 0 8px;color:var(--mut)}
.desc{color:var(--mut);font-size:14px;margin:2px 0 14px}
table{border-collapse:collapse;width:100%;background:var(--card);font-size:14px;margin:8px 0;border:1px solid var(--line);border-radius:8px;overflow:hidden}
th,td{padding:8px 12px;text-align:left;border-bottom:1px solid var(--line)}
th{background:#f1f5f9;font-weight:600;font-size:13px}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
tr:last-child td{border-bottom:none}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:10px 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}
.card h4{margin:0 0 10px;font-size:15px;padding-bottom:6px;border-bottom:2px solid}
.kw{display:flex;justify-content:space-between;padding:3px 0;font-size:13.5px;border-bottom:1px dashed var(--line)}
.kw:last-child{border:none}
.kw b{font-variant-numeric:tabular-nums;color:var(--mut);font-weight:600}
.chip{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12px;font-weight:600;color:#fff}
.warn{background:#fef3c7;border:1px solid #f59e0b;border-radius:10px;padding:14px 16px;margin:12px 0;font-size:14px}
.warn b{color:#b45309}
.ok{background:#ecfdf5;border:1px solid #10b981;border-radius:10px;padding:12px 16px;margin:12px 0;font-size:14px}
.mut{color:var(--mut)}
.small{font-size:12.5px;color:var(--mut)}
.bar{height:8px;border-radius:4px;background:#e2e8f0;overflow:hidden;display:inline-block;width:120px;vertical-align:middle}
.bar>span{display:block;height:100%}
code{background:#f1f5f9;padding:1px 5px;border-radius:4px;font-size:13px}
.foot{margin-top:50px;color:var(--mut);font-size:12.5px;border-top:1px solid var(--line);padding-top:16px}
@media(max-width:760px){.cards{grid-template-columns:1fr}}
</style></head><body><div class="wrap">""")

    add('<h1>1930년대 기교주의 논쟁 — 상세 분석 리포트</h1>')
    add('<p class="sub">김기림 · 임화 · 박용철 비평 텍스트 29편 / 텍스트마이닝 + 텍스트언어학 · 교정 파이프라인(gigyo_release) 산출</p>')

    def critic_chip(c):
        return f'<span class="chip" style="background:{CRITIC_COLOR[c]}">{esc(c)}</span>'

    # ── 1. 코퍼스 개요 ────────────────────────────────────────
    add('<h2>1. 코퍼스 개요</h2>')
    cs = d.get("corpus_stats", {})
    add('<table><tr><th>비평가</th><th class="num">편수</th><th class="num">어절</th><th class="num">내용어 토큰</th></tr>')
    te = tt = tx = 0
    for c in CRITIC_ORDER:
        s = cs.get(c, {})
        te += s.get("eojeols", 0); tt += s.get("tokens", 0); tx += s.get("texts", 0)
        add(f'<tr><td>{critic_chip(c)}</td><td class="num">{s.get("texts",0)}</td>'
            f'<td class="num">{s.get("eojeols",0):,}</td><td class="num">{s.get("tokens",0):,}</td></tr>')
    add(f'<tr><th>합계</th><th class="num">{tx}</th><th class="num">{te:,}</th><th class="num">{tt:,}</th></tr>')
    add('</table>')

    # ── 2. LL 핵심어 ──────────────────────────────────────────
    add('<h2>2. 비평가별 핵심 어휘 (로그우도비 LL)</h2>')
    add('<p class="desc">자주 쓰인 어휘가 아니라, 다른 두 비평가와 비교해 <b>해당 비평가에게만 특이하게 집중된</b> 변별 어휘. (비평가 vs 나머지 합)</p>')
    kw = d.get("keywords", {}).get("critic_vs_critic", {})
    add('<div class="cards">')
    for c in CRITIC_ORDER:
        data = kw.get(c, {})
        add(f'<div class="card"><h4 style="border-color:{CRITIC_COLOR[c]}">{esc(c)}</h4>')
        for s in data.get("keywords", [])[:10]:
            add(f'<div class="kw"><span>{esc(s["word"])}</span><b>LL {s["ll"]:.1f} · {s["target_freq"]}/{s["reference_freq"]}</b></div>')
        add('</div>')
    add('</div><p class="small">표기: LL 값 · (대상 비평가 빈도 / 나머지 비평가 빈도)</p>')

    # ── 3. 핵심 개념어 NF ─────────────────────────────────────
    add('<h2>3. 핵심 개념어 정규화 빈도 (NF · 천 어절당)</h2>')
    add('<p class="desc">논쟁 핵심어가 각 비평가 담론에서 차지하는 비중.</p>')
    focus = ["기교", "기술", "형식", "내용", "영감", "현실", "사상", "낭만", "리얼리즘", "언어", "비평", "과학"]
    freq = d.get("frequency", {})
    add('<table><tr><th>개념어</th>' + ''.join(f'<th class="num">{esc(c)}</th>' for c in CRITIC_ORDER) + '</tr>')
    for term in focus:
        row = f'<tr><td><b>{esc(term)}</b></td>'
        for c in CRITIC_ORDER:
            nf = freq.get(c, {}).get("terms", {}).get(term, {}).get("nf", 0.0)
            row += f'<td class="num">{nf:.2f}</td>'
        add(row + '</tr>')
    add('</table>')

    # ── 4. 공기어 MI ──────────────────────────────────────────
    add('<h2>4. 공기어 분석 (상호정보량 MI · 윈도±5 정규화)</h2>')
    add('<p class="desc">대상 어휘와 우연 이상으로 긴밀히 결합하는 어휘. 괄호는 공기 실측 횟수.</p>')
    col = d.get("collocations", {})
    for tgt in ["기교", "기술", "형식", "내용", "영감"]:
        if tgt not in col:
            continue
        add(f'<h3>대상어 「{esc(tgt)}」</h3><div class="cards">')
        for c in CRITIC_ORDER:
            cd = col[tgt].get(c, {})
            add(f'<div class="card"><h4 style="border-color:{CRITIC_COLOR[c]}">{esc(c)} · {esc(tgt)} {cd.get("target_freq",0)}회</h4>')
            cols = cd.get("collocates", [])
            if not cols:
                add('<div class="small">출현/공기 부족 — 산출 불가</div>')
            for s in cols[:6]:
                add(f'<div class="kw"><span>{esc(s["word"])}</span><b>MI {s["mi"]:.2f} (공기 {s["co_freq"]})</b></div>')
            add('</div>')
        add('</div>')

    # ── 5. 접속 표지 NF ──────────────────────────────────────
    add('<h2>5. 접속 표지 분포 (NF) — 논증 구조</h2>')
    conn = d.get("connectives", {})
    cats = ["대조", "원인-결과", "첨가", "예시·환언", "요약·결론"]
    add('<table><tr><th>비평가</th>' + ''.join(f'<th class="num">{esc(x)}</th>' for x in cats) + '</tr>')
    for c in CRITIC_ORDER:
        cc = conn.get(c, {}).get("categories", {})
        row = f'<tr><td>{critic_chip(c)}</td>'
        for cat in cats:
            row += f'<td class="num">{cc.get(cat,{}).get("nf",0.0):.2f}</td>'
        add(row + '</tr>')
    add('</table>')
    # 마커 상세
    add('<h3>실제 사용 표지 내역 (raw 빈도)</h3>')
    for c in CRITIC_ORDER:
        cc = conn.get(c, {}).get("categories", {})
        parts = []
        for cat in cats:
            det = cc.get(cat, {}).get("marker_detail", {})
            if det:
                top = ", ".join(f"{esc(k)}{v}" for k, v in sorted(det.items(), key=lambda x: -x[1])[:5])
                parts.append(f'<b>{esc(cat)}</b> {top}')
        add(f'<p class="small">{critic_chip(c)} ' + ' · '.join(parts) + '</p>')

    # ── 6. BHR (경고 포함) ───────────────────────────────────
    add('<h2>6. 담화 자세 — 강화·완충 비율 (BHR)</h2>')
    bhr = d.get("bhr", {})
    # 수 있다 비중 계산
    add('<div class="warn"><b>⚠️ 측정 유의</b> — 이 BHR은 완화 표지를 형태소 구문 패턴으로 잡은 <b>교정본</b>입니다(구버전은 완화를 과소 집계). '
        '다만 완화의 상당부분이 <code>ㄹ 수 있다</code> 구문에서 나오는데, 이는 <b>가능성</b>(완화)과 <b>능력</b>(완화 아님)이 섞여 있어 '
        'BHR이 과소평가됐을 수 있습니다. 아래 내역의 <code>ㄹ 수 있다</code> 비중을 함께 보세요. <b>확정 결론 전 KWIC 검증 권장.</b></div>')
    add('<table><tr><th>비평가</th><th class="num">강조NF</th><th class="num">완충NF</th><th class="num">BHR</th>'
        '<th class="num">완화 중 「ㄹ 수 있다」</th><th>해석</th></tr>')
    for c in CRITIC_ORDER:
        b = bhr.get(c, {})
        hd = b.get("hedge_detail", {})
        su = hd.get("ㄹ 수 있다", 0)
        tot = b.get("hedge_count", 0) or 1
        share = su / tot * 100
        bv = b.get("bhr")
        bvs = f'{bv:.3f}' if bv is not None else '∞'
        add(f'<tr><td>{critic_chip(c)}</td><td class="num">{b.get("booster_nf",0):.2f}</td>'
            f'<td class="num">{b.get("hedge_nf",0):.2f}</td><td class="num"><b>{bvs}</b></td>'
            f'<td class="num">{su}/{b.get("hedge_count",0)} ({share:.0f}%)</td><td>{esc(b.get("interpretation",""))}</td></tr>')
    add('</table>')
    # 강조/완화 내역
    add('<h3>강조·완화 표지 내역</h3>')
    for c in CRITIC_ORDER:
        b = bhr.get(c, {})
        bd = ", ".join(f"{esc(k)} {v}" for k, v in sorted(b.get("booster_detail", {}).items(), key=lambda x: -x[1]))
        hd = ", ".join(f"{esc(k)} {v}" for k, v in sorted(b.get("hedge_detail", {}).items(), key=lambda x: -x[1]))
        add(f'<p class="small">{critic_chip(c)} <b>강조</b> {bd}<br><span style="margin-left:0"><b>완화</b> {hd}</span></p>')

    # ── 7. 시기별 BHR ────────────────────────────────────────
    add('<h2>7. 시기별 BHR — 담화 자세의 통시적 변화</h2>')
    pb = d.get("period_bhr", {})
    add('<table><tr><th>비평가</th>' + ''.join(f'<th class="num">{esc(p)}</th>' for p in PERIODS_ACTIVE) + '</tr>')
    for c in CRITIC_ORDER:
        per = pb.get(c, {}).get("periods", {})
        row = f'<tr><td>{critic_chip(c)}</td>'
        for p in PERIODS_ACTIVE:
            v = per.get(p, {})
            bv = v.get("bhr")
            row += f'<td class="num">{(f"{bv:.3f}" if bv is not None else "—")}</td>'
        add(row + '</tr>')
    add('</table><p class="small">셀은 강조NF/완충NF 비율. 소규모 시기 셀은 참고용.</p>')

    # ── 8. 기교/기술 시기별 NF ───────────────────────────────
    add('<h2>8. 기교 · 기술의 시기별 NF 추이</h2>')
    tr = d.get("term_trajectory", {})
    for term in ["기교", "기술"]:
        add(f'<h3>「{esc(term)}」</h3><table><tr><th>비평가</th>' + ''.join(f'<th class="num">{esc(p)}</th>' for p in PERIODS_ACTIVE) + '</tr>')
        for c in CRITIC_ORDER:
            per = tr.get(c, {}).get("periods", {})
            row = f'<tr><td>{critic_chip(c)}</td>'
            for p in PERIODS_ACTIVE:
                v = per.get(p, {})
                ej = v.get("eojeols", 0)
                nf = v.get("term_nfs", {}).get(term, 0.0)
                row += f'<td class="num">{("—" if ej==0 else f"{nf:.2f}")}</td>'
            add(row + '</tr>')
        add('</table>')

    # ── 9. 내용축 × 자세 ─────────────────────────────────────
    add('<h2>9. 내용축 어휘 우위 × 발화 자세</h2>')
    add('<table><tr><th>비평가</th><th class="num">내용</th><th class="num">형식</th><th class="num">영감</th><th>우위</th><th class="num">BHR</th></tr>')
    for c in CRITIC_ORDER:
        t = freq.get(c, {}).get("terms", {})
        nfs = {k: t.get(k, {}).get("nf", 0.0) for k in ["내용", "형식", "영감"]}
        form = sum(t.get(k, {}).get("nf", 0.0) for k in ["형식", "방법", "지성", "현대", "주지"])
        content = sum(t.get(k, {}).get("nf", 0.0) for k in ["내용", "사상", "계급", "현실", "반영"])
        spirit = sum(t.get(k, {}).get("nf", 0.0) for k in ["영감", "변용", "감정", "개성", "천재"])
        win = max([("형식 우선", form), ("내용 우선", content), ("영감 우선", spirit)], key=lambda x: x[1])[0]
        bv = bhr.get(c, {}).get("bhr")
        add(f'<tr><td>{critic_chip(c)}</td><td class="num">{nfs["내용"]:.2f}</td><td class="num">{nfs["형식"]:.2f}</td>'
            f'<td class="num">{nfs["영감"]:.2f}</td><td>{esc(win)}</td><td class="num">{(f"{bv:.3f}" if bv is not None else "—")}</td></tr>')
    add('</table>')

    # ── 10. 토크나이저 커버리지 ──────────────────────────────
    cov = d.get("tokenizer_coverage", {})
    if cov:
        add('<h2>10. 토크나이저 커버리지 (ModernKoreanSubword 진단)</h2>')
        add(f'<p class="desc">서브워드 모델 로드: <b>{cov.get("subword_model_loaded")}</b></p>')
        add('<table><tr><th>비평가</th><th class="num">형태소 수</th><th class="num">한자 비율</th><th class="num">UNK율</th><th class="num">분해비율</th></tr>')
        for c in CRITIC_ORDER:
            v = cov.get("critics", {}).get(c, {})
            add(f'<tr><td>{critic_chip(c)}</td><td class="num">{v.get("kiwi_total_morphs",0):,}</td>'
                f'<td class="num">{v.get("kiwi_hanja_ratio","—")}</td><td class="num">{v.get("subword_unk_rate","—")}</td>'
                f'<td class="num">{v.get("subword_decomposition_ratio","—")}</td></tr>')
        add('</table>')

    add('<div class="foot">생성: gigyo_release 파이프라인 · 데이터 출처 <code>output/results.json</code><br>'
        '※ BHR 및 시기별 BHR은 완화 표지 측정 정의가 확정되기 전까지 잠정값입니다.</div>')
    add('</div></body></html>')

    out = Path(a.out)
    out.write_text("".join(P), encoding="utf-8")
    print(f"✓ HTML 리포트 생성: {out}  ({out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
