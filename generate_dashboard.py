import pandas as pd
import json
from datetime import datetime, timedelta
from pathlib import Path

# ─── 경로 설정 ────────────────────────────────────────────
DATA_DIR  = Path(r"C:\Users\하슬라한의원\AppData\Local\Programs\migrator\resources\data")
LOCAL_DIR = Path(r"C:\Users\하슬라한의원\한의원지표\data")
OUT_HTML  = Path(r"C:\Users\하슬라한의원\한의원지표\index.html")

SEP = "'!@#%'"
DOCTORS = ["노왕식", "이문환", "방민준"]
KBO_CODES = {"W","V","1","T","C","M","L","3","4","5","7"}

DOC_COLORS = {
    "노왕식": "#3b82f6",
    "이문환": "#10b981",
    "방민준": "#f59e0b",
    "배용빈": "#f472b6",
    "김한중": "#38bdf8",
}

# ─── 데이터 로드 ──────────────────────────────────────────
def load_receipt():
    rows = []
    with open(DATA_DIR / "receipt.txt", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(SEP)
            if len(parts) < 7:
                continue
            try:
                rows.append({
                    "patient": parts[1],
                    "date":    pd.to_datetime(parts[2]),
                    "code":    parts[3],
                    "copay":   int(parts[4]) if parts[4].strip().lstrip('-').isdigit() else 0,
                    "claim":   int(parts[5]) if parts[5].strip().lstrip('-').isdigit() else 0,
                    "nonins":  int(parts[6]) if parts[6].strip().lstrip('-').isdigit() else 0,
                })
            except:
                pass
    return pd.DataFrame(rows)

def load_detail():
    rows = []
    with open(DATA_DIR / "detail.txt", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(SEP)
            if len(parts) < 10:
                continue
            try:
                rows.append({
                    "visit":     parts[1],
                    "patient":   parts[2],
                    "date":      pd.to_datetime(parts[3]),
                    "category":  parts[4],
                    "treatment": parts[7],
                    "insured":   parts[8],
                    "fee":       int(parts[9]) if parts[9].strip().lstrip('-').isdigit() else 0,
                })
            except:
                pass
    return pd.DataFrame(rows)

def load_customer():
    rows = []
    with open(DATA_DIR / "customer.txt", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(SEP)
            if len(parts) < 4:
                continue
            try:
                rows.append({
                    "patient": parts[1],
                    "date":    pd.to_datetime(parts[2]),
                    "route":   parts[3],
                })
            except:
                pass
    return pd.DataFrame(rows)

def load_chuna():
    path = LOCAL_DIR / "추나현황.csv"
    if not path.exists():
        return pd.DataFrame(columns=["날짜","원장명","건보추나","TA추나"])
    df = pd.read_csv(path, encoding="utf-8-sig")
    df["날짜"] = pd.to_datetime(df["날짜"])
    df["건보추나"] = pd.to_numeric(df["건보추나"], errors="coerce").fillna(0).astype(int)
    df["TA추나"]   = pd.to_numeric(df["TA추나"],   errors="coerce").fillna(0).astype(int)
    return df

def load_okchart_revenue():
    """원장별현황.csv (read_okchart.py 가 생성)"""
    path = LOCAL_DIR / "원장별현황.csv"
    if not path.exists():
        return pd.DataFrame(columns=["날짜","원장명","건보매출","자보매출","비급여매출","린다이어트","초진","재진"])
    df = pd.read_csv(path, encoding="utf-8-sig")
    df["날짜"] = pd.to_datetime(df["날짜"])
    for col in ["건보매출","자보매출","비급여매출","린다이어트","초진","재진"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    return df


def load_retention():
    """retention.csv (read_retention.py 가 생성)"""
    path = LOCAL_DIR / "retention.csv"
    if not path.exists():
        return pd.DataFrame(columns=["날짜","원장명","코호트","재진","삼진","재진률","삼진률"])
    df = pd.read_csv(path, encoding="utf-8-sig")
    df["날짜"] = pd.to_datetime(df["날짜"])
    for col in ["코호트","재진","삼진"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    for col in ["재진률","삼진률"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(float)
    return df

# ─── 지표 계산 ────────────────────────────────────────────
def calc_all_weeks_data(df_receipt, df_detail, df_customer, df_chuna, df_doc, df_ret):
    """전체 기간 주별 모든 지표 (매출/재진율/신환/추나/원장별/재진삼진률)"""
    df_r = df_receipt.copy()
    df_r["ws"] = df_r["date"].dt.to_period("W").apply(lambda p: p.start_time)
    df_d = df_detail.copy()
    df_d["ws"] = df_d["date"].dt.to_period("W").apply(lambda p: p.start_time)
    df_c = df_customer.copy()
    df_c["ws"] = df_c["date"].dt.to_period("W").apply(lambda p: p.start_time)

    if not df_chuna.empty:
        df_ch = df_chuna.copy()
        df_ch["ws"] = df_ch["날짜"].dt.to_period("W").apply(lambda p: p.start_time)
    else:
        df_ch = pd.DataFrame(columns=["날짜","원장명","건보추나","TA추나","ws"])

    if not df_doc.empty:
        df_dv = df_doc.copy()
        df_dv["ws"] = df_dv["날짜"].dt.to_period("W").apply(lambda p: p.start_time)
    else:
        df_dv = pd.DataFrame(columns=["날짜","원장명","건보매출","자보매출","비급여매출","린다이어트","초진","재진","ws"])

    if not df_ret.empty:
        df_rv = df_ret.copy()
        df_rv["ws"] = df_rv["날짜"]  # retention.csv 날짜 = 해당 주 월요일
    else:
        df_rv = pd.DataFrame(columns=["날짜","원장명","코호트","재진","삼진","재진률","삼진률","ws"])

    all_week_starts = sorted(df_r["ws"].unique())
    result = []

    for ws in all_week_starts:
        we = ws + timedelta(days=6)

        # 전체 매출
        r_w = df_r[df_r["ws"] == ws]
        k   = r_w[r_w["code"].isin(KBO_CODES)]
        j   = r_w[r_w["code"] == "B"]
        kbo  = int((k["copay"]+k["claim"]).sum())
        jbo  = int((j["copay"]+j["claim"]).sum())
        nins = int(r_w["nonins"].sum())

        # 린다이어트
        d_w   = df_d[df_d["ws"] == ws]
        linda = int(d_w[d_w["treatment"].str.contains("린다이어트|린프리미엄|린 ", na=False)]["fee"].sum())

        # 재진율
        total_v = int(d_w[d_w["treatment"].str.contains("진찰료", na=False)]["visit"].nunique())
        re_v    = int(d_w[d_w["treatment"].str.contains("재진", na=False)]["visit"].nunique())
        revisit_rate = round(re_v / total_v * 100, 1) if total_v > 0 else 0

        # 신환
        new_patients = int(df_c[df_c["ws"] == ws].shape[0])

        # 추나
        chuna_stats = {}
        chuna_daily = []
        c_w = df_ch[df_ch["ws"] == ws] if not df_ch.empty else df_ch
        for doc in DOCTORS:
            doc_df = c_w[c_w["원장명"] == doc]
            chuna_stats[doc] = {
                "건보추나": int(doc_df["건보추나"].sum()),
                "TA추나":   int(doc_df["TA추나"].sum()),
            }
        for _, row in c_w.sort_values(["날짜","원장명"]).iterrows():
            chuna_daily.append({
                "날짜":     row["날짜"].strftime("%Y-%m-%d"),
                "원장명":   row["원장명"],
                "건보추나": int(row["건보추나"]),
                "TA추나":   int(row["TA추나"]),
            })

        # 원장별 매출
        doc_revenue = {}
        if not df_dv.empty:
            dv_w = df_dv[df_dv["ws"] == ws]
            for doc in dv_w["원장명"].unique():
                ddv = dv_w[dv_w["원장명"] == doc]
                doc_revenue[doc] = {
                    "건보":    int(ddv["건보매출"].sum()),
                    "자보":    int(ddv["자보매출"].sum()),
                    "비급여":  int(ddv["비급여매출"].sum()),
                    "린다이어트": int(ddv["린다이어트"].sum()),
                    "초진":    int(ddv["초진"].sum()),
                }

        # 원장별 재진/삼진률 (이 주의 월요일 = 기준일)
        retention = {}
        if not df_rv.empty:
            rv_w = df_rv[df_rv["ws"] == ws]
            for _, row in rv_w.iterrows():
                retention[row["원장명"]] = {
                    "cohort":       int(row["코호트"]),
                    "revisit":      int(row["재진"]),
                    "third":        int(row["삼진"]),
                    "revisit_rate": float(row["재진률"]),
                    "third_rate":   float(row["삼진률"]),
                }

        result.append({
            "label":         str(ws.date()),
            "label_display": f"{ws.strftime('%m/%d')}(월)~{we.strftime('%m/%d')}(일)",
            "kbo":           kbo,
            "jbo":           jbo,
            "nins":          nins,
            "linda":         linda,
            "revisit_rate":  revisit_rate,
            "new_patients":  new_patients,
            "chuna":         chuna_stats,
            "chuna_daily":   chuna_daily,
            "doc_revenue":   doc_revenue,
            "retention":     retention,
        })

    return result


def calc_chuna_monthly_by_doc(df_chuna):
    if df_chuna.empty:
        return {"labels": []}
    df = df_chuna.copy()
    df["month"] = df["날짜"].dt.to_period("M").apply(lambda p: p.start_time)
    months = sorted(df["month"].unique())[-3:]
    result = {"labels": [m.strftime("%Y.%m") for m in months]}
    for doc in DOCTORS:
        doc_df = df[df["원장명"] == doc]
        result[doc] = [int(doc_df[doc_df["month"]==m]["건보추나"].sum()) for m in months]
    return result


def calc_doc_monthly(df_doc):
    """최근 3개월 원장별 매출 집계 (고정 차트용)"""
    if df_doc.empty:
        return {"labels": [], "docs": [], "data": {}}
    df = df_doc.copy()
    df["month"] = df["날짜"].dt.to_period("M").apply(lambda p: p.start_time)
    months = sorted(df["month"].unique())[-3:]
    all_docs = sorted(d for d in df["원장명"].unique() if d != "선주천")
    result = {
        "labels": [m.strftime("%Y.%m") for m in months],
        "docs":   all_docs,
        "data":   {},
    }
    for doc in all_docs:
        ddf = df[df["원장명"] == doc]
        result["data"][doc] = {
            "건보":    [int(ddf[ddf["month"]==m]["건보매출"].sum()) for m in months],
            "자보":    [int(ddf[ddf["month"]==m]["자보매출"].sum()) for m in months],
            "비급여":  [int(ddf[ddf["month"]==m]["비급여매출"].sum()) for m in months],
        }
    return result


def calc_monthly_revenue(df_receipt):
    df = df_receipt.copy()
    df["month"] = df["date"].dt.to_period("M").apply(lambda p: p.start_time)
    months = sorted(df["month"].unique())[-6:]
    labels, kbo, jbo, nins = [], [], [], []
    for m in months:
        d = df[df["month"] == m]
        k = d[d["code"].isin(KBO_CODES)]
        labels.append(m.strftime("%Y.%m"))
        kbo.append(int((k["copay"]+k["claim"]).sum()))
        j = d[d["code"] == "B"]
        jbo.append(int((j["copay"]+j["claim"]).sum()))
        nins.append(int(d["nonins"].sum()))
    return labels, kbo, jbo, nins


def calc_new_patients_monthly(df_cust):
    df = df_cust.copy()
    df["month"] = df["date"].dt.to_period("M").apply(lambda p: p.start_time)
    months = sorted(df["month"].unique())[-6:]
    labels = [m.strftime("%Y.%m") for m in months]
    counts = [int(df[df["month"]==m].shape[0]) for m in months]
    return labels, counts


# ─── HTML 생성 ────────────────────────────────────────────
def fmt(n):
    return f"{n//10000:,}만원"


def build_html(data):
    d = data
    now_str = datetime.now().strftime("%Y년 %m월 %d일 %H:%M 기준")

    colors = {"노왕식":"#3b82f6","이문환":"#10b981","방민준":"#f59e0b"}

    # ── 추나 월별 테이블 ──────────────────────────────────
    cm        = d["chuna_monthly"]
    cm_labels = cm.get("labels", [])
    monthly_chuna_header = (
        "".join(f'<th class="num">{lb}</th>' for lb in cm_labels)
        + '<th class="num">합계</th>'
    )
    # colgroup: 원장 14%, 각 월 (100-14-12)/(n월) %, 합계 12%
    n_month_cols = len(cm_labels)
    month_col_w  = round((100 - 14 - 12) / n_month_cols, 1) if n_month_cols else 12
    monthly_chuna_colgroup = (
        '<col style="width:14%">'
        + "".join(f'<col style="width:{month_col_w}%">' for _ in cm_labels)
        + '<col style="width:12%">'
    )
    monthly_chuna_rows = ""
    col_totals = [0]*len(cm_labels)
    for doc in DOCTORS:
        series    = cm.get(doc, [0]*len(cm_labels))
        doc_total = sum(series)
        monthly_chuna_rows += f'<tr><td class="doc-name">{doc}</td>'
        for i, v in enumerate(series):
            monthly_chuna_rows += f'<td class="num">{v}</td>'
            col_totals[i] += v
        monthly_chuna_rows += f'<td class="num bold">{doc_total}</td></tr>'
    grand_chuna_total = sum(col_totals)
    monthly_chuna_totals_html = (
        "".join(f'<td class="num">{v}</td>' for v in col_totals)
        + f'<td class="num bold">{grand_chuna_total}</td>'
    )

    # ── 추나 최근 12주 바차트 ─────────────────────────────
    all_weeks     = d["all_weeks"]
    recent_12     = all_weeks[-12:] if len(all_weeks) >= 12 else all_weeks
    weekly_labels = json.dumps([w["label"] for w in recent_12])
    weekly_datasets = json.dumps([
        {"label": doc,
         "data": [w["chuna"].get(doc, {"건보추나":0})["건보추나"] for w in recent_12],
         "backgroundColor": colors[doc]+"80",
         "borderColor": colors[doc],
         "borderWidth": 1}
        for doc in DOCTORS
    ], ensure_ascii=False)

    # ── 추나 월별 차트 ────────────────────────────────────
    monthly_chuna_datasets = json.dumps([
        {"label": doc,
         "data": cm.get(doc, [0]*len(cm_labels)),
         "backgroundColor": colors[doc]+"80",
         "borderColor": colors[doc],
         "borderWidth": 1}
        for doc in DOCTORS
    ], ensure_ascii=False)
    monthly_chuna_labels_json = json.dumps(cm_labels)

    # ── 원장별 월별 매출 차트 (고정) ─────────────────────
    dm = d["doc_monthly"]
    dm_labels_json = json.dumps(dm.get("labels", []))
    dm_docs        = dm.get("docs", [])
    # 원장별 총매출(건보+자보+비급여) 데이터셋
    dm_datasets = json.dumps([
        {"label": doc,
         "data": [
             (dm["data"][doc]["건보"][i] + dm["data"][doc]["자보"][i] + dm["data"][doc]["비급여"][i])
             for i in range(len(dm.get("labels",[])))
         ],
         "backgroundColor": (DOC_COLORS.get(doc, "#94a3b8"))+"80",
         "borderColor":     DOC_COLORS.get(doc, "#94a3b8"),
         "borderWidth": 1}
        for doc in dm_docs
        if doc in dm.get("data", {})
    ], ensure_ascii=False)
    doc_colors_json = json.dumps(DOC_COLORS, ensure_ascii=False)

    # ── 6개월 트렌드 ──────────────────────────────────────
    monthly_labels = json.dumps(d["monthly_labels"])
    monthly_kbo    = json.dumps(d["monthly_kbo"])
    monthly_jbo    = json.dumps(d["monthly_jbo"])
    monthly_nins   = json.dumps(d["monthly_nins"])
    np_labels      = json.dumps(d["np_labels"])
    np_counts      = json.dumps(d["np_counts"])

    # ── 전체 주간 JSON ────────────────────────────────────
    all_weeks_json = json.dumps(all_weeks, ensure_ascii=False)

    # ── 노션 회고 JSON ────────────────────────────────────
    retros_json = json.dumps(d.get("retros", []), ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>하슬라한의원 경영 대시보드</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Apple SD Gothic Neo',Arial,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh}}
  .header{{background:#1e293b;padding:14px 32px;border-bottom:1px solid #334155;
           display:grid;grid-template-columns:1fr auto 1fr;align-items:center;
           position:sticky;top:0;z-index:200}}
  .header h1{{font-size:1.2rem;font-weight:700;color:#f8fafc}}
  .header .updated{{font-size:0.7rem;color:#64748b;text-align:right}}
  .week-nav{{display:flex;align-items:center;gap:14px;justify-content:center}}
  .week-nav button{{background:#334155;border:none;color:#e2e8f0;padding:7px 16px;
                    border-radius:6px;cursor:pointer;font-size:0.82rem}}
  .week-nav button:hover{{background:#475569}}
  .week-nav button:disabled{{opacity:0.3;cursor:default}}
  .week-nav span{{font-size:0.92rem;color:#f1f5f9;font-weight:600;white-space:nowrap}}
  .container{{padding:24px 32px;max-width:1400px;margin:0 auto}}
  .section-title{{font-size:0.78rem;font-weight:600;color:#94a3b8;text-transform:uppercase;
                  letter-spacing:1px;margin-bottom:12px;margin-top:28px}}
  .cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px;margin-bottom:8px}}
  .card{{background:#1e293b;border-radius:12px;padding:18px 20px;border:1px solid #334155}}
  .card .label{{font-size:0.72rem;color:#64748b;margin-bottom:6px}}
  .card .value{{font-size:1.45rem;font-weight:700;color:#f1f5f9}}
  .card .sub{{font-size:0.72rem;color:#94a3b8;margin-top:4px}}
  .card.highlight .value{{color:#3b82f6}}
  .card.green .value{{color:#10b981}}
  .card.yellow .value{{color:#f59e0b}}
  .card.purple .value{{color:#a78bfa}}
  .card.pink .value{{color:#f472b6}}
  .grid2{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
  .grid3{{display:grid;grid-template-columns:2fr 1fr;gap:16px}}
  .chart-box{{background:#1e293b;border-radius:12px;padding:20px;border:1px solid #334155}}
  .chart-box h3{{font-size:0.83rem;font-weight:600;color:#cbd5e1;margin-bottom:14px}}
  .chuna-table{{width:100%;border-collapse:collapse;font-size:0.84rem;table-layout:fixed}}
  .chuna-table th{{text-align:left;color:#64748b;font-weight:500;font-size:0.73rem;
                   padding:7px 10px;border-bottom:1px solid #334155;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
  .chuna-table td{{padding:8px 10px;border-bottom:1px solid #1e293b;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
  .chuna-table tr:last-child td{{border-bottom:none;font-weight:700;color:#f1f5f9;background:#0f172a}}
  .num{{text-align:right}}
  .chuna-table th.num{{text-align:right}}
  .doc-name{{color:#e2e8f0}}
  .bold{{color:#3b82f6!important}}
  .total-row td{{background:#0f172a;color:#f1f5f9;font-weight:700}}
  .overflow-x{{overflow-x:auto}}
  .fixed-badge{{font-size:0.68rem;color:#475569;margin-left:8px;font-weight:400;
                background:#1e293b;padding:2px 6px;border-radius:4px;border:1px solid #334155}}
  /* ── 주간 회고 ── */
  .retro-tabs{{display:flex;gap:8px;margin-bottom:18px;flex-wrap:wrap}}
  .retro-tab{{background:#334155;border:none;color:#94a3b8;padding:8px 22px;
              border-radius:6px;cursor:pointer;font-size:0.82rem;transition:all 0.15s}}
  .retro-tab.active{{background:#3b82f6;color:#fff}}
  .retro-tab:hover:not(.active){{background:#475569;color:#e2e8f0}}
  .retro-tab .has-data{{font-size:0.65rem;margin-left:4px;color:#10b981}}
  .retro-field{{margin-bottom:16px}}
  .retro-field label{{display:block;font-size:0.73rem;color:#94a3b8;margin-bottom:7px;
                      font-weight:600;letter-spacing:0.5px;text-transform:uppercase}}
  .retro-hint{{font-size:0.71rem;color:#475569;font-style:italic;margin-top:5px}}
  .retro-textarea{{width:100%;background:#0f172a;border:1px solid #334155;border-radius:8px;
                   color:#e2e8f0;padding:10px 13px;font-size:0.84rem;resize:vertical;
                   font-family:'Apple SD Gothic Neo',Arial,sans-serif;min-height:72px;line-height:1.6}}
  .retro-textarea:focus{{outline:none;border-color:#3b82f6}}
  .retro-actions{{display:flex;align-items:center;gap:12px;margin-top:6px}}
  .retro-save-btn{{background:#3b82f6;border:none;color:#fff;padding:8px 22px;
                   border-radius:6px;cursor:pointer;font-size:0.84rem;font-weight:600}}
  .retro-save-btn:hover{{background:#2563eb}}
  .retro-saved{{color:#10b981;font-size:0.78rem;display:none}}
  .retro-text{{white-space:pre-wrap;color:#e2e8f0;font-size:0.86rem;line-height:1.65;
               padding:11px 14px;background:#0f172a;border-radius:8px;border:1px solid #334155;margin-top:4px}}
  /* ── 이름 선택 오버레이 ── */
  #selectScreen{{position:fixed;inset:0;background:#0f172a;z-index:9999;
                display:flex;flex-direction:column;align-items:center;justify-content:center;gap:28px}}
  #selectScreen h2{{font-size:1.5rem;color:#f1f5f9;font-weight:700}}
  #selectScreen p{{color:#64748b;font-size:0.92rem}}
  .select-btns{{display:flex;flex-wrap:wrap;gap:14px;justify-content:center;max-width:600px}}
  .select-doc-btn{{background:#1e293b;border:2px solid #334155;color:#e2e8f0;
                   padding:18px 44px;border-radius:12px;cursor:pointer;font-size:1.05rem;
                   font-weight:600;min-width:160px;transition:all 0.15s}}
  .select-doc-btn:hover{{border-color:#3b82f6;color:#3b82f6}}
  /* ── 개인 KPI 배너 ── */
  #myKpiSection{{display:none}}
  #myKpiBanner{{background:linear-gradient(135deg,#1e3a5f 0%,#1e293b 100%);
                border:1px solid #3b82f6;border-radius:12px;padding:16px 20px;
                margin-bottom:8px;display:flex;align-items:center;gap:12px;flex-wrap:wrap}}
  #myKpiBanner .my-name{{font-size:1rem;font-weight:700;color:#60a5fa;min-width:130px}}
  .my-kpi-card{{background:#0f172a;border-radius:8px;padding:9px 14px;min-width:100px;text-align:center}}
  .my-kpi-card .mk-label{{font-size:0.67rem;color:#64748b;margin-bottom:3px}}
  .my-kpi-card .mk-value{{font-size:1rem;font-weight:700;color:#f1f5f9}}
  .change-btn{{background:none;border:1px solid #334155;color:#64748b;padding:5px 12px;
               border-radius:6px;cursor:pointer;font-size:0.75rem;margin-left:auto;white-space:nowrap}}
  .change-btn:hover{{border-color:#94a3b8;color:#94a3b8}}
  .home-btn{{background:#3b82f6;border:none;color:#fff;padding:7px 14px;
             border-radius:8px;cursor:pointer;font-size:0.82rem;font-weight:600;
             white-space:nowrap;transition:all 0.15s}}
  .home-btn:hover{{background:#2563eb}}
  @media(max-width:900px){{
    .header{{grid-template-columns:1fr;gap:8px}}
    .header .updated{{text-align:left}}
    .grid2,.grid3{{grid-template-columns:1fr}}
    .container{{padding:16px}}
  }}
</style>
</head>
<body>

<!-- ══ 홈 화면 (이름 선택) ══════════════════════════════════ -->
<div id="selectScreen">
  <div style="font-size:2.2rem;margin-bottom:8px">🏥</div>
  <h2>하슬라한의원 원장팀 대시보드</h2>
  <p>본인의 대시보드를 선택하세요</p>
  <div class="select-btns">
    <button class="select-doc-btn" onclick="selectDoctor('노왕식')">노왕식 원장</button>
    <button class="select-doc-btn" onclick="selectDoctor('이문환')">이문환 원장</button>
    <button class="select-doc-btn" onclick="selectDoctor('방민준')">방민준 원장</button>
    <button class="select-doc-btn" onclick="selectDoctor('배용빈')">배용빈 원장</button>
    <button class="select-doc-btn" onclick="selectDoctor('김한중')">김한중 원장</button>
  </div>
  <p style="margin-top:20px;font-size:0.78rem;color:#475569">선택한 원장의 개인뷰가 표시됩니다. 언제든 홈 버튼으로 돌아올 수 있습니다.</p>
</div>

<div class="header">
  <div style="display:flex;align-items:center;gap:10px">
    <button class="home-btn" onclick="goHome()" title="홈으로">🏠 홈</button>
    <h1>🏥 하슬라한의원 경영 대시보드</h1>
  </div>
  <div class="week-nav">
    <button id="prevWeek" onclick="changeWeek(-1)">← 이전 주</button>
    <span id="weekLabel">로딩 중...</span>
    <button id="nextWeek" onclick="changeWeek(1)">다음 주 →</button>
  </div>
  <div style="text-align:right">
    <span class="updated">{now_str}</span><br>
    <span id="headerDoc" style="font-size:0.8rem;color:#60a5fa;font-weight:600"></span>
  </div>
</div>

<div class="container">

  <!-- ═══ 개인 KPI 배너 (동적) ════════════════════════════ -->
  <div id="myKpiSection">
    <div class="section-title" style="margin-top:4px">내 현황</div>
    <div id="myKpiBanner">
      <span class="my-name" id="myName">—</span>
      <div class="my-kpi-card"><div class="mk-label">건보매출</div><div class="mk-value" id="my-kbo">—</div></div>
      <div class="my-kpi-card"><div class="mk-label">자보매출</div><div class="mk-value" id="my-jbo">—</div></div>
      <div class="my-kpi-card"><div class="mk-label">비급여매출</div><div class="mk-value" id="my-nins">—</div></div>
      <div class="my-kpi-card"><div class="mk-label">린다이어트</div><div class="mk-value" id="my-linda">—</div></div>
      <div class="my-kpi-card"><div class="mk-label">재진률</div><div class="mk-value" id="my-revisit">—</div></div>
      <div class="my-kpi-card"><div class="mk-label">삼진률</div><div class="mk-value" id="my-third">—</div></div>
      <div class="my-kpi-card"><div class="mk-label">건보추나</div><div class="mk-value" id="my-chuna">—</div></div>
      <button class="change-btn" onclick="goHome()">🏠 홈으로</button>
    </div>
  </div>

  <!-- ═══ 주간 전체 지표 (홈 화면에서만 표시) ════════════ -->
  <div id="weekTotalSection" style="display:none">
    <div class="section-title" id="weekSectionTitle">주간 현황</div>
    <div class="cards">
      <div class="card highlight">
        <div class="label">건보 매출</div>
        <div class="value" id="card-kbo">—</div>
        <div class="sub">본인부담 + 공단청구</div>
      </div>
      <div class="card green">
        <div class="label">자보 매출</div>
        <div class="value" id="card-jbo">—</div>
        <div class="sub">자동차보험 청구</div>
      </div>
      <div class="card yellow">
        <div class="label">비급여 매출</div>
        <div class="value" id="card-nins">—</div>
        <div class="sub">현금·카드 비급여</div>
      </div>
      <div class="card purple">
        <div class="label">린다이어트 매출</div>
        <div class="value" id="card-linda">—</div>
        <div class="sub">린다이어트 관련 합계</div>
      </div>
      <div class="card">
        <div class="label">재진율</div>
        <div class="value" id="card-revisit">—</div>
        <div class="sub">전체 내원 중 재진 비율</div>
      </div>
      <div class="card pink">
        <div class="label">신환</div>
        <div class="value" id="card-newpat">—</div>
        <div class="sub">신규 환자 수</div>
      </div>
    </div>
  </div>

  <!-- ═══ 원장별 매출 현황 (동적) ════════════════════════ -->
  <div class="section-title" id="docRevSectionTitle">원장별 매출 현황</div>
  <div class="grid3">
    <div class="chart-box overflow-x">
      <h3>원장별 매출 집계</h3>
      <div id="docRevTableContainer">
        <p style="color:#475569;font-size:0.82rem;padding:12px">로딩 중...</p>
      </div>
    </div>
    <div class="chart-box">
      <h3>원장별 매출 비율</h3>
      <canvas id="docRevPie" height="200"></canvas>
    </div>
  </div>

  <!-- ═══ 재진/삼진률 (동적) ════════════════════════════════ -->
  <div class="section-title" id="retSectionTitle">원장별 재진/삼진률</div>
  <div class="chart-box overflow-x">
    <h3 id="retTableTitle">재진/삼진률 — 3주 전 초진 코호트 기준</h3>
    <div id="retTableContainer">
      <p style="color:#475569;font-size:0.82rem;padding:12px">로딩 중...</p>
    </div>
  </div>

  <!-- ═══ 추나 현황 (동적) ════════════════════════════════ -->
  <div class="section-title" id="chunaSectionTitle">원장별 추나 현황</div>
  <div class="grid3">
    <div class="chart-box">
      <h3>추나 집계</h3>
      <table class="chuna-table">
        <colgroup><col style="width:60%"><col style="width:40%"></colgroup>
        <thead>
          <tr><th>원장</th><th class="num">건보추나<br><span style="color:#475569;font-size:0.67rem;font-weight:400">목표 50건/주</span></th></tr>
        </thead>
        <tbody id="chunaSummaryBody">
          <tr><td colspan="2" style="color:#475569;text-align:center">로딩 중...</td></tr>
        </tbody>
      </table>
      <div style="margin-top:12px;padding:10px 13px;background:#0f172a;border-radius:8px;border:1px solid #334155">
        <div style="color:#cbd5e1;font-size:0.78rem;font-weight:600;margin-bottom:6px">📊 신호등 기준</div>
        <div style="color:#e2e8f0;font-size:0.78rem;line-height:1.6">
          <span style="color:#10b981;font-weight:700">●</span> ≥50건 &nbsp;·&nbsp;
          <span style="color:#f59e0b;font-weight:700">●</span> 35~49건 &nbsp;·&nbsp;
          <span style="color:#ef4444;font-weight:700">●</span> &lt;35건 &nbsp;<span style="color:#94a3b8">(목표 50건/주)</span>
        </div>
      </div>
    </div>
    <div class="chart-box">
      <h3>추나 비율</h3>
      <canvas id="chunaPie" height="180"></canvas>
    </div>
  </div>

  <!-- ═══ 추나 일별 상세 (동적) ══════════════════════════ -->
  <div class="chart-box" style="margin-top:16px">
    <h3 id="weekDetailTitle">주간 일별 상세</h3>
    <div id="weekDetailContainer" class="overflow-x"></div>
  </div>

  <!-- ═══ 주간 건보추나 트렌드 (고정) ════════════════════ -->
  <div class="section-title">주간 건보추나 트렌드 (최근 12주)<span class="fixed-badge">고정</span></div>
  <div class="chart-box">
    <h3>원장별 건보추나 주간 합계</h3>
    <canvas id="chunaBar" height="80"></canvas>
  </div>

  <!-- ═══ 월별 건보추나 인센티브 (고정) ══════════════════ -->
  <div class="section-title">월별 건보추나 현황 (인센티브 기준)<span class="fixed-badge">고정</span></div>
  <div class="grid3">
    <div class="chart-box overflow-x">
      <h3>원장별 월별 건보추나</h3>
      <table class="chuna-table" style="font-size:0.78rem">
        <colgroup>{monthly_chuna_colgroup}</colgroup>
        <thead><tr><th>원장</th>{monthly_chuna_header}</tr></thead>
        <tbody>
          {monthly_chuna_rows}
          <tr class="total-row"><td>합계</td>{monthly_chuna_totals_html}</tr>
        </tbody>
      </table>
    </div>
    <div class="chart-box">
      <h3>월별 건보추나 추이</h3>
      <canvas id="chunaMonthBar" height="220"></canvas>
    </div>
  </div>

  <!-- ═══ 월별 원장별 매출 (고정) ════════════════════════ -->
  <div class="section-title">월별 원장별 매출 추이 (최근 3개월)<span class="fixed-badge">고정</span></div>
  <div class="chart-box">
    <h3>원장별 총매출 (건보+자보+비급여)</h3>
    <canvas id="docMonthBar" height="80"></canvas>
  </div>

  <!-- ═══ 전체 매출 트렌드 (고정) ════════════════════════ -->
  <div class="section-title">전체 매출 트렌드 (최근 6개월)<span class="fixed-badge">고정</span></div>
  <div class="chart-box">
    <h3>월별 건보 / 자보 / 비급여 매출</h3>
    <canvas id="revBar" height="80"></canvas>
  </div>

  <!-- ═══ 신환 현황 (고정) ════════════════════════════════ -->
  <div class="section-title">신환 현황 (최근 6개월)<span class="fixed-badge">고정</span></div>
  <div class="chart-box">
    <h3>월별 신환 수</h3>
    <canvas id="newPat" height="80"></canvas>
  </div>

  <!-- ═══ 주간 회고 (노션 DB → 매일 자동 동기화) ══════════ -->
  <div class="section-title" id="retroSectionTitle">📗 주간 회고</div>
  <div class="chart-box" id="retroBox">
    <div class="retro-tabs" id="retroTabs"></div>
    <div id="retroContent"></div>
    <div style="text-align:center;margin-top:16px;padding-top:14px;border-top:1px solid #334155">
      <a href="https://www.notion.so/a59dc6c66fe94b31b78fee7770dc12aa" target="_blank" rel="noopener" style="display:inline-block;background:#3b82f6;color:#fff;padding:9px 22px;border-radius:8px;text-decoration:none;font-size:0.84rem;font-weight:600">📝 노션에서 작성·수정하기 →</a>
      <p style="font-size:0.7rem;color:#475569;margin-top:7px">노션에서 변경한 내용은 매일 자동 동기화됩니다 (최대 24h 지연)</p>
    </div>
  </div>

</div>

<script>
var allWeeks   = {all_weeks_json};
var currentIdx = allWeeks.length > 0 ? allWeeks.length - 1 : 0;

// URL hash로 주차 지정 가능 (#week=YYYY-MM-DD) — 노션 회고에서 그 주 대시보드로 점프
(function() {{
  var m = window.location.hash.match(/week=(\d{{4}}-\d{{2}}-\d{{2}})/);
  if (!m) return;
  for (var i=0; i<allWeeks.length; i++) {{
    if (allWeeks[i].label === m[1]) {{ currentIdx = i; break; }}
  }}
}})();
var chunaDoctors  = {json.dumps(DOCTORS, ensure_ascii=False)};
var docColorMap   = {doc_colors_json};
var myDoc      = localStorage.getItem('haslla_myDoc') || null;
var retroDoc   = myDoc || chunaDoctors[0] || '노왕식';
var retros     = {retros_json};
var retroSelectedDoc = null;

// ── 원장 선택 / 개인뷰 ────────────────────────────────────
function selectDoctor(name) {{
  myDoc = name;
  retroDoc = name;
  localStorage.setItem('haslla_myDoc', name);
  document.getElementById('selectScreen').style.display = 'none';
  document.getElementById('myKpiSection').style.display = 'block';
  var wts = document.getElementById('weekTotalSection');
  if (wts) wts.style.display = 'none';
  document.getElementById('myName').textContent = name + ' 원장님 👋';
  var hd = document.getElementById('headerDoc');
  if (hd) hd.textContent = name + ' 원장';
  renderWeek(currentIdx);
}}

function changeDoctor() {{
  document.getElementById('selectScreen').style.display = 'flex';
  window.scrollTo({{top:0, behavior:'instant'}});
}}

function goHome() {{
  document.getElementById('selectScreen').style.display = 'flex';
  var wts = document.getElementById('weekTotalSection');
  if (wts) wts.style.display = '';
  window.scrollTo({{top:0, behavior:'instant'}});
}}

function updateMyKpi(idx) {{
  if (!myDoc) return;
  var week = allWeeks[idx];
  var dr  = week.doc_revenue || {{}};
  var rev = dr[myDoc] || {{}};
  document.getElementById('my-kbo').textContent   = fmtWon(rev['건보']   || 0);
  document.getElementById('my-jbo').textContent   = fmtWon(rev['자보']   || 0);
  document.getElementById('my-nins').textContent  = fmtWon(rev['비급여'] || 0);
  document.getElementById('my-linda').textContent = fmtWon(rev['린다이어트'] || 0);
  var rt   = week.retention || {{}};
  var myRt = rt[myDoc]    || {{}};
  document.getElementById('my-revisit').textContent = myRt.revisit_rate != null ? myRt.revisit_rate + '%' : '—';
  document.getElementById('my-third').textContent   = myRt.third_rate   != null ? myRt.third_rate   + '%' : '—';
  var ch   = week.chuna   || {{}};
  var myCh = ch[myDoc]   || {{'건보추나':0,'TA추나':0}};
  document.getElementById('my-chuna').textContent = myCh['건보추나'];
}}

function fmtWon(n) {{
  return Math.floor(n / 10000).toLocaleString() + '만원';
}}
function color(doc) {{
  return docColorMap[doc] || '#94a3b8';
}}

// ── 파이차트 (원장별 매출) ────────────────────────────────
var docRevPieChart = new Chart(document.getElementById('docRevPie'), {{
  type: 'doughnut',
  data: {{ labels: [], datasets: [{{ data: [], backgroundColor: [], borderWidth: 0 }}] }},
  options: {{
    plugins: {{
      legend: {{
        labels: {{
          color:'#e2e8f0', font:{{size:12, weight:'600'}},
          generateLabels: function(chart) {{
            var ds = chart.data.datasets[0];
            var total = (ds.data || []).reduce(function(a,b) {{ return a + (b||0); }}, 0);
            return (chart.data.labels || []).map(function(label, i) {{
              var v = ds.data[i] || 0;
              var pct = total > 0 ? ((v/total)*100).toFixed(1) : '0.0';
              return {{
                text: label + ' ' + pct + '%',
                fillStyle: ds.backgroundColor[i],
                strokeStyle: ds.backgroundColor[i],
                fontColor: '#e2e8f0',
                lineWidth: 0, hidden: false, index: i
              }};
            }});
          }}
        }}
      }},
      tooltip: {{
        callbacks: {{
          label: function(ctx) {{
            var ds = ctx.dataset;
            var total = ds.data.reduce(function(a,b) {{ return a + (b||0); }}, 0);
            var v = ctx.parsed;
            var pct = total > 0 ? ((v/total)*100).toFixed(1) : '0.0';
            return ctx.label + ': ' + Math.floor(v/10000).toLocaleString() + '만원 (' + pct + '%)';
          }}
        }}
      }}
    }},
    cutout: '60%'
  }}
}});

// ── 파이차트 (추나 비율) ──────────────────────────────────
var chunaPieChart = new Chart(document.getElementById('chunaPie'), {{
  type: 'doughnut',
  data: {{
    labels: chunaDoctors,
    datasets: [{{ data: [0,0,0], backgroundColor: ['#3b82f6','#10b981','#f59e0b'], borderWidth:0 }}]
  }},
  options: {{
    plugins: {{
      legend: {{
        labels: {{
          color:'#94a3b8', font:{{size:12}},
          generateLabels: function(chart) {{
            var ds = chart.data.datasets[0];
            var total = (ds.data || []).reduce(function(a,b) {{ return a + (b||0); }}, 0);
            return (chart.data.labels || []).map(function(label, i) {{
              var v = ds.data[i] || 0;
              var pct = total > 0 ? ((v/total)*100).toFixed(1) : '0.0';
              return {{
                text: label + ' ' + pct + '%',
                fillStyle: ds.backgroundColor[i],
                strokeStyle: ds.backgroundColor[i],
                fontColor: '#e2e8f0',
                lineWidth: 0, hidden: false, index: i
              }};
            }});
          }}
        }}
      }},
      tooltip: {{
        callbacks: {{
          label: function(ctx) {{
            var ds = ctx.dataset;
            var total = ds.data.reduce(function(a,b) {{ return a + (b||0); }}, 0);
            var v = ctx.parsed;
            var pct = total > 0 ? ((v/total)*100).toFixed(1) : '0.0';
            return ctx.label + ': ' + v + '건 (' + pct + '%)';
          }}
        }}
      }}
    }},
    cutout: '60%'
  }}
}});

// ── 주간 전체 렌더링 ──────────────────────────────────────
function renderWeek(idx) {{
  if (allWeeks.length === 0) return;
  var week = allWeeks[idx];

  // 헤더
  document.getElementById('weekLabel').textContent          = week.label_display;
  document.getElementById('weekSectionTitle').textContent   = '주간 현황 — ' + week.label_display;
  document.getElementById('docRevSectionTitle').textContent = '원장별 매출 현황 — ' + week.label_display;
  document.getElementById('chunaSectionTitle').textContent  = '원장별 추나 현황 — ' + week.label_display;
  document.getElementById('weekDetailTitle').textContent    = week.label_display + ' 일별 추나 상세';

  // KPI 카드
  document.getElementById('card-kbo').textContent     = fmtWon(week.kbo);
  document.getElementById('card-jbo').textContent     = fmtWon(week.jbo);
  document.getElementById('card-nins').textContent    = fmtWon(week.nins);
  document.getElementById('card-linda').textContent   = fmtWon(week.linda);
  document.getElementById('card-revisit').textContent = week.revisit_rate + '%';
  document.getElementById('card-newpat').textContent  = week.new_patients + '명';

  // ── 원장별 매출 테이블 ──────────────────────────────────
  var dr = week.doc_revenue || {{}};
  var drDocs = Object.keys(dr).sort(function(a,b) {{
    var order = ['노왕식','이문환','방민준','배용빈','김한중'];
    return (order.indexOf(a)+1||99) - (order.indexOf(b)+1||99);
  }});

  if (drDocs.length > 0) {{
    var tKbo=0, tJbo=0, tNins=0, tLinda=0;
    var drtbl = '<table class="chuna-table" style="width:100%;table-layout:fixed">' +
      '<colgroup>' +
      '<col style="width:14%"><col style="width:14%"><col style="width:14%">' +
      '<col style="width:15%"><col style="width:13%"><col style="width:14%"><col style="width:16%">' +
      '</colgroup>' +
      '<thead><tr>' +
      '<th style="padding-left:11px">원장</th>' +
      '<th class="num">건보매출</th><th class="num">자보매출</th>' +
      '<th class="num">비급여매출</th><th class="num">린다이어트</th>' +
      '<th class="num">신환</th><th class="num bold">합계</th>' +
      '</tr></thead><tbody>';
    var tCho = 0;
    for (var i=0; i<drDocs.length; i++) {{
      var r  = dr[drDocs[i]];
      var k  = r['건보']||0, j = r['자보']||0, n = r['비급여']||0, l = r['린다이어트']||0, cho = r['초진']||0;
      var tot = k+j+n+l;
      tKbo+=k; tJbo+=j; tNins+=n; tLinda+=l; tCho+=cho;
      drtbl += '<tr>' +
        '<td class="doc-name" style="border-left:3px solid ' + color(drDocs[i]) + ';padding-left:8px">' + drDocs[i] + '</td>' +
        '<td class="num">' + fmtWon(k) + '</td>' +
        '<td class="num">' + fmtWon(j) + '</td>' +
        '<td class="num">' + fmtWon(n) + '</td>' +
        '<td class="num">' + fmtWon(l) + '</td>' +
        '<td class="num">' + cho + '명</td>' +
        '<td class="num bold">' + fmtWon(tot) + '</td></tr>';
    }}
    drtbl += '<tr class="total-row"><td style="padding-left:11px">합계</td>' +
      '<td class="num">' + fmtWon(tKbo)   + '</td>' +
      '<td class="num">' + fmtWon(tJbo)   + '</td>' +
      '<td class="num">' + fmtWon(tNins)  + '</td>' +
      '<td class="num">' + fmtWon(tLinda) + '</td>' +
      '<td class="num">' + tCho + '명</td>' +
      '<td class="num bold">' + fmtWon(tKbo+tJbo+tNins+tLinda) + '</td></tr>';
    drtbl += '</tbody></table>';
    document.getElementById('docRevTableContainer').innerHTML = drtbl;

    // 매출 파이차트
    docRevPieChart.data.labels = drDocs;
    docRevPieChart.data.datasets[0].data = drDocs.map(function(d) {{
      var r = dr[d]; return (r['건보']||0)+(r['자보']||0)+(r['비급여']||0)+(r['린다이어트']||0);
    }});
    docRevPieChart.data.datasets[0].backgroundColor = drDocs.map(color);
    docRevPieChart.update();
  }} else {{
    document.getElementById('docRevTableContainer').innerHTML =
      '<p style="color:#475569;font-size:0.82rem;padding:12px">이 주에는 원장별 매출 데이터가 없습니다.</p>';
  }}

  // ── 재진/삼진률 테이블 ──────────────────────────────────
  var cohortWeekStart = new Date(week.label);
  cohortWeekStart.setDate(cohortWeekStart.getDate() - 21);
  var cohortWeekEnd = new Date(cohortWeekStart);
  cohortWeekEnd.setDate(cohortWeekEnd.getDate() + 6);
  var fmt2 = function(d) {{ return (d.getMonth()+1) + '/' + d.getDate(); }};
  document.getElementById('retSectionTitle').textContent  =
    '원장별 재진/삼진률 — ' + week.label_display;
  document.getElementById('retTableTitle').textContent =
    '코호트: ' + fmt2(cohortWeekStart) + '(월)~' + fmt2(cohortWeekEnd) + '(일) 초진/재초진 환자';

  var rt = week.retention || {{}};
  var rtDocs = Object.keys(rt).sort(function(a,b) {{
    var order = ['노왕식','이문환','방민준','배용빈','김한중'];
    return (order.indexOf(a)+1||99) - (order.indexOf(b)+1||99);
  }});

  if (rtDocs.length > 0) {{
    var rttbl =
      '<table class="chuna-table" style="width:100%;table-layout:fixed">' +
      '<colgroup>' +
      '<col style="width:16%"><col style="width:14%"><col style="width:14%">' +
      '<col style="width:14%"><col style="width:14%"><col style="width:14%"><col style="width:14%">' +
      '</colgroup>' +
      '<thead><tr>' +
      '<th style="padding-left:11px">원장</th>' +
      '<th class="num">코호트</th>' +
      '<th class="num">재진 수</th><th class="num">재진률<br><span style="color:#475569;font-size:0.67rem;font-weight:400">목표 80%</span></th>' +
      '<th class="num">삼진 수</th><th class="num">삼진률<br><span style="color:#475569;font-size:0.67rem;font-weight:400">목표 70%</span></th>' +
      '<th class="num">비고</th>' +
      '</tr></thead><tbody>';
    for (var i=0; i<rtDocs.length; i++) {{
      var r = rt[rtDocs[i]];
      var revColor = r.revisit_rate >= 70 ? '#10b981' : r.revisit_rate >= 55 ? '#f59e0b' : '#ef4444';
      var thiColor = r.third_rate  >= 60 ? '#10b981' : r.third_rate  >= 45 ? '#f59e0b' : '#ef4444';
      rttbl += '<tr>' +
        '<td class="doc-name" style="border-left:3px solid ' + color(rtDocs[i]) + ';padding-left:8px">' + rtDocs[i] + '</td>' +
        '<td class="num">' + r.cohort + '명</td>' +
        '<td class="num">' + r.revisit + '명</td>' +
        '<td class="num" style="color:' + revColor + ';font-weight:700">' + r.revisit_rate + '%</td>' +
        '<td class="num">' + r.third + '명</td>' +
        '<td class="num" style="color:' + thiColor + ';font-weight:700">' + r.third_rate + '%</td>' +
        '<td class="num" style="color:#475569;font-size:0.75rem">n=' + r.cohort + '</td>' +
        '</tr>';
    }}
    rttbl += '</tbody></table>' +
      '<div style="margin-top:12px;padding:10px 13px;background:#0f172a;border-radius:8px;border:1px solid #334155">' +
      '<div style="color:#cbd5e1;font-size:0.78rem;font-weight:600;margin-bottom:6px">📊 신호등 기준</div>' +
      '<div style="color:#e2e8f0;font-size:0.78rem;line-height:1.7">' +
      '<span style="color:#10b981;font-weight:700">●</span> <b>재진율</b> ≥70% &nbsp;·&nbsp; ' +
      '<span style="color:#f59e0b;font-weight:700">●</span> 55~69% &nbsp;·&nbsp; ' +
      '<span style="color:#ef4444;font-weight:700">●</span> &lt;55% &nbsp;<span style="color:#94a3b8">(목표 80%)</span><br>' +
      '<span style="color:#10b981;font-weight:700">●</span> <b>삼진율</b> ≥60% &nbsp;·&nbsp; ' +
      '<span style="color:#f59e0b;font-weight:700">●</span> 45~59% &nbsp;·&nbsp; ' +
      '<span style="color:#ef4444;font-weight:700">●</span> &lt;45% &nbsp;<span style="color:#94a3b8">(목표 70%)</span>' +
      '</div>' +
      '<div style="color:#64748b;font-size:0.7rem;margin-top:6px">* 초진 담당 원장 기준 · 클리닉 전체 재방문 카운트</div>' +
      '</div>';
    document.getElementById('retTableContainer').innerHTML = rttbl;
  }} else {{
    document.getElementById('retTableContainer').innerHTML =
      '<p style="color:#475569;font-size:0.82rem;padding:12px">이 주에는 재진/삼진률 데이터가 없습니다.<br>' +
      '<span style="font-size:0.75rem">read_retention.py를 실행하면 데이터가 채워집니다.</span></p>';
  }}

  // ── 추나 합계 테이블 (건보추나만, 50건/주 목표 신호등) ───
  var tG=0;
  var ctbody = '';
  for (var i=0; i<chunaDoctors.length; i++) {{
    var c = week.chuna[chunaDoctors[i]] || {{'건보추나':0}};
    var v = c['건보추나'] || 0;
    tG += v;
    var chColor = v >= 50 ? '#10b981' : v >= 35 ? '#f59e0b' : '#ef4444';
    ctbody += '<tr><td class="doc-name">' + chunaDoctors[i] + '</td>' +
      '<td class="num" style="color:' + chColor + ';font-weight:700">' + v + '</td></tr>';
  }}
  ctbody += '<tr class="total-row"><td>합계</td>' +
    '<td class="num bold">' + tG + '</td></tr>';
  document.getElementById('chunaSummaryBody').innerHTML = ctbody;

  chunaPieChart.data.datasets[0].data = chunaDoctors.map(function(d) {{
    var c = week.chuna[d]||{{'건보추나':0}};
    return c['건보추나'] || 0;
  }});
  chunaPieChart.update();

  // ── 추나 일별 상세 (건보추나만) ─────────────────────────
  var dateMap = {{}};
  for (var i=0; i<week.chuna_daily.length; i++) dateMap[week.chuna_daily[i]['날짜']] = true;
  var dates = Object.keys(dateMap).sort();
  var dthtml = '';
  if (dates.length === 0) {{
    dthtml = '<p style="color:#475569;font-size:0.82rem;padding:12px">이 주에는 추나 데이터가 없습니다.</p>';
  }} else {{
    var dColW = Math.floor(90 / chunaDoctors.length);
    dthtml = '<table class="chuna-table">' +
      '<colgroup><col style="width:10%">';
    for (var ci=0; ci<chunaDoctors.length; ci++) dthtml += '<col style="width:' + dColW + '%">';
    dthtml += '</colgroup><thead><tr><th>날짜</th>';
    for (var i=0; i<chunaDoctors.length; i++) dthtml += '<th class="num">' + chunaDoctors[i] + '</th>';
    dthtml += '</tr></thead><tbody>';
    for (var di=0; di<dates.length; di++) {{
      dthtml += '<tr><td>' + dates[di].slice(5) + '</td>';
      for (var dj=0; dj<chunaDoctors.length; dj++) {{
        var entry=null;
        for (var k=0; k<week.chuna_daily.length; k++) {{
          if (week.chuna_daily[k]['날짜']===dates[di] && week.chuna_daily[k]['원장명']===chunaDoctors[dj]) {{
            entry=week.chuna_daily[k]; break;
          }}
        }}
        dthtml += entry
          ? '<td class="num">'+entry['건보추나']+'</td>'
          : '<td class="num">-</td>';
      }}
      dthtml += '</tr>';
    }}
    dthtml += '<tr class="total-row"><td>합계</td>';
    for (var i=0; i<chunaDoctors.length; i++) {{
      var t = week.chuna[chunaDoctors[i]]||{{'건보추나':0}};
      dthtml += '<td class="num">'+(t['건보추나']||0)+'</td>';
    }}
    dthtml += '</tr></tbody></table>';
  }}
  document.getElementById('weekDetailContainer').innerHTML = dthtml;

  document.getElementById('prevWeek').disabled = (idx===0);
  document.getElementById('nextWeek').disabled = (idx===allWeeks.length-1);

  // ── 주간 회고 (노션 동기화 데이터 렌더링) ────
  document.getElementById('retroSectionTitle').textContent = '📗 주간 회고 — ' + koreanWeekRange(week.label);
  renderRetroBox(week.label);

  // ── 개인 KPI 배너 업데이트 ───────────────────────────────
  updateMyKpi(idx);
}}

function changeWeek(dir) {{
  currentIdx = Math.max(0, Math.min(allWeeks.length-1, currentIdx+dir));
  renderWeek(currentIdx);
  if (allWeeks[currentIdx]) {{
    history.replaceState(null, '', '#week=' + allWeeks[currentIdx].label);
  }}
  window.scrollTo({{top:0, behavior:'smooth'}});
}}

// ── 주간 회고 함수 (노션 동기화 단방향 읽기) ──────────────
function escHtml(s) {{
  return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}}

function koreanWeekRange(label) {{
  var parts = (label||'').split('-');
  if (parts.length !== 3) return label;
  var y = parseInt(parts[0], 10), m = parseInt(parts[1], 10), d = parseInt(parts[2], 10);
  var end = new Date(y, m - 1, d);
  end.setDate(end.getDate() + 6);
  var em = end.getMonth() + 1, ed = end.getDate();
  if (m === em) return m + '월 ' + d + '일 ~ ' + ed + '일';
  return m + '월 ' + d + '일 ~ ' + em + '월 ' + ed + '일';
}}

function findRetro(weekLabel, doc) {{
  for (var i=0; i<retros.length; i++) {{
    if (retros[i].week_label === weekLabel && retros[i].doctor === doc) return retros[i];
  }}
  return null;
}}

function renderRetroBox(weekLabel) {{
  if (!retroSelectedDoc) retroSelectedDoc = myDoc || chunaDoctors[0] || '노왕식';

  // 탭
  var tabsHtml = '';
  for (var i=0; i<chunaDoctors.length; i++) {{
    var doc = chunaDoctors[i];
    var has = !!findRetro(weekLabel, doc);
    tabsHtml +=
      '<button class="retro-tab' + (doc===retroSelectedDoc?' active':'') + '" ' +
      'onclick="selectRetroDoc(\\'' + doc + '\\')">' +
      doc + (has ? '<span class="has-data">&#10003;</span>' : '') +
      '</button>';
  }}
  document.getElementById('retroTabs').innerHTML = tabsHtml;

  // 내용
  var r = findRetro(weekLabel, retroSelectedDoc);
  var content;
  if (r) {{
    var link = r.page_url
      ? '<div style="text-align:right;margin-bottom:8px"><a href="' + r.page_url + '" target="_blank" rel="noopener" style="color:#60a5fa;font-size:0.72rem;text-decoration:none">노션에서 열기 →</a></div>'
      : '';
    content = link +
      '<div class="retro-field"><label>✅ 잘한 점</label><div class="retro-text">' + (escHtml(r.good) || '<span style="color:#475569">(비어있음)</span>') + '</div></div>' +
      '<div class="retro-field"><label>🔶 아쉬웠던 점</label><div class="retro-text">' + (escHtml(r.bad) || '<span style="color:#475569">(비어있음)</span>') + '</div></div>' +
      '<div class="retro-field"><label>📌 다음 주 실행 계획</label><div class="retro-text">' + (escHtml(r.plan) || '<span style="color:#475569">(비어있음)</span>') + '</div></div>';
  }} else {{
    content = '<p style="color:#64748b;text-align:center;padding:32px 12px;font-size:0.85rem;line-height:1.65">' +
      '이 주의 <strong style="color:#cbd5e1">' + retroSelectedDoc + ' 원장</strong> 회고가 아직 없습니다.<br>' +
      '<span style="font-size:0.74rem;color:#475569">아래 버튼에서 노션에 추가하면 다음 동기화 때 표시됩니다.</span></p>';
  }}
  document.getElementById('retroContent').innerHTML = content;
}}

function selectRetroDoc(doc) {{
  retroSelectedDoc = doc;
  renderRetroBox(allWeeks[currentIdx].label);
}}

// ── 고정 차트들 ───────────────────────────────────────────

// 주간 건보추나 바차트
new Chart(document.getElementById('chunaBar'), {{
  type: 'bar',
  data: {{ labels:{weekly_labels}, datasets:{weekly_datasets} }},
  options: {{
    responsive:true,
    plugins:{{ legend:{{ labels:{{ color:'#94a3b8' }} }} }},
    scales:{{
      x:{{ ticks:{{ color:'#64748b', maxRotation:45 }}, grid:{{ color:'#1e293b' }} }},
      y:{{ ticks:{{ color:'#64748b' }}, grid:{{ color:'#334155' }}, beginAtZero:true }}
    }}
  }}
}});

// 월별 건보추나 바차트
new Chart(document.getElementById('chunaMonthBar'), {{
  type: 'bar',
  data: {{ labels:{monthly_chuna_labels_json}, datasets:{monthly_chuna_datasets} }},
  options: {{
    responsive:true,
    plugins:{{ legend:{{ labels:{{ color:'#94a3b8' }} }} }},
    scales:{{
      x:{{ ticks:{{ color:'#64748b' }}, grid:{{ color:'#1e293b' }} }},
      y:{{ ticks:{{ color:'#64748b' }}, grid:{{ color:'#334155' }}, beginAtZero:true }}
    }}
  }}
}});

// 월별 원장별 총매출 바차트
new Chart(document.getElementById('docMonthBar'), {{
  type: 'bar',
  data: {{ labels:{dm_labels_json}, datasets:{dm_datasets} }},
  options: {{
    responsive:true,
    plugins:{{ legend:{{ labels:{{ color:'#94a3b8' }} }} }},
    scales:{{
      x:{{ ticks:{{ color:'#64748b' }}, grid:{{ color:'#1e293b' }} }},
      y:{{ ticks:{{ color:'#64748b', callback:function(v){{ return (v/10000).toFixed(0)+'만'; }} }},
           grid:{{ color:'#334155' }}, beginAtZero:true }}
    }}
  }}
}});

// 전체 매출 바차트
new Chart(document.getElementById('revBar'), {{
  type: 'bar',
  data: {{
    labels:{monthly_labels},
    datasets:[
      {{ label:'건보매출', data:{monthly_kbo},  backgroundColor:'#3b82f680', borderColor:'#3b82f6', borderWidth:1 }},
      {{ label:'자보매출', data:{monthly_jbo},  backgroundColor:'#10b98180', borderColor:'#10b981', borderWidth:1 }},
      {{ label:'비급여',   data:{monthly_nins}, backgroundColor:'#f59e0b80', borderColor:'#f59e0b', borderWidth:1 }}
    ]
  }},
  options:{{
    responsive:true,
    plugins:{{ legend:{{ labels:{{ color:'#94a3b8' }} }} }},
    scales:{{
      x:{{ ticks:{{ color:'#64748b' }}, grid:{{ color:'#1e293b' }} }},
      y:{{ ticks:{{ color:'#64748b', callback:function(v){{ return (v/10000).toFixed(0)+'만'; }} }},
           grid:{{ color:'#334155' }}, beginAtZero:true }}
    }}
  }}
}});

// 신환 바차트
new Chart(document.getElementById('newPat'), {{
  type:'bar',
  data:{{
    labels:{np_labels},
    datasets:[{{ label:'신환 수', data:{np_counts},
                 backgroundColor:'#a78bfa80', borderColor:'#a78bfa', borderWidth:1 }}]
  }},
  options:{{
    responsive:true,
    plugins:{{ legend:{{ labels:{{ color:'#94a3b8' }} }} }},
    scales:{{
      x:{{ ticks:{{ color:'#64748b' }}, grid:{{ color:'#1e293b' }} }},
      y:{{ ticks:{{ color:'#64748b' }}, grid:{{ color:'#334155' }}, beginAtZero:true }}
    }}
  }}
}});

// 초기 렌더
if (allWeeks.length > 0) {{
  if (myDoc) {{
    document.getElementById('selectScreen').style.display = 'none';
    document.getElementById('myKpiSection').style.display = 'block';
    document.getElementById('myName').textContent = myDoc + ' 원장님 👋';
    var hd = document.getElementById('headerDoc');
    if (hd) hd.textContent = myDoc + ' 원장';
  }} else {{
    var wts0 = document.getElementById('weekTotalSection');
    if (wts0) wts0.style.display = '';
  }}
  renderWeek(currentIdx);
}}
</script>
</body>
</html>"""


# ─── 메인 ─────────────────────────────────────────────────
def main():
    print("데이터 로딩 중...")
    df_receipt  = load_receipt()
    df_detail   = load_detail()
    df_customer = load_customer()
    df_chuna    = load_chuna()
    df_doc      = load_okchart_revenue()

    df_ret        = load_retention()

    # 선주천 제외 (모든 원장별 데이터에서)
    if not df_doc.empty:
        df_doc = df_doc[df_doc["원장명"] != "선주천"].reset_index(drop=True)
    if not df_ret.empty:
        df_ret = df_ret[df_ret["원장명"] != "선주천"].reset_index(drop=True)
    if not df_chuna.empty:
        df_chuna = df_chuna[df_chuna["원장명"] != "선주천"].reset_index(drop=True)

    print("지표 계산 중...")
    all_weeks     = calc_all_weeks_data(df_receipt, df_detail, df_customer, df_chuna, df_doc, df_ret)
    chuna_monthly = calc_chuna_monthly_by_doc(df_chuna)
    doc_monthly   = calc_doc_monthly(df_doc)
    ml, mkbo, mjbo, mnins = calc_monthly_revenue(df_receipt)
    npl, npc = calc_new_patients_monthly(df_customer)
    print(f"  총 {len(all_weeks)}주 데이터 계산 완료")

    # 노션 회고 동기화 결과 로드 (없으면 빈 배열)
    retro_path = LOCAL_DIR / "retro.json"
    retros = []
    if retro_path.exists():
        try:
            retros = json.loads(retro_path.read_text(encoding="utf-8"))
            print(f"  회고 {len(retros)}건 로드")
        except Exception as e:
            print(f"  회고 로드 실패 (빈 배열로 진행): {e}")

    data = {
        "all_weeks":     all_weeks,
        "chuna_monthly": chuna_monthly,
        "doc_monthly":   doc_monthly,
        "monthly_labels": ml,
        "monthly_kbo":   mkbo,
        "monthly_jbo":   mjbo,
        "monthly_nins":  mnins,
        "np_labels":     npl,
        "np_counts":     npc,
        "retros":        retros,
    }

    print("HTML 생성 중...")
    html = build_html(data)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"완료: {OUT_HTML}")


if __name__ == "__main__":
    main()
