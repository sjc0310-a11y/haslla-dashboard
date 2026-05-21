# -*- coding: utf-8 -*-
"""1on1 대시보드의 HTML 템플릿.

PAGE_TEMPLATE   — 한의원 PC 전용 편집 화면 (평문 데이터 인라인, READONLY=false)
PUBLIC_TEMPLATE — GitHub Pages 공개 페이지 (잠금 화면 + 비번 → 복호화 → 동일 렌더, READONLY=true)

두 템플릿이 같은 RENDER_JS 모듈을 공유한다. READONLY 플래그로 편집 핸들러를 켜고 끔.
"""

# ─────────────────────────────────────────────────────────
# 공통 CSS
# ─────────────────────────────────────────────────────────
COMMON_CSS = r"""
:root {
  --bg:#0f172a; --panel:#1e293b; --panel2:#273449; --panel3:#334155;
  --border:#334155; --border2:#475569;
  --text:#e2e8f0; --muted:#94a3b8;
  --accent:#38bdf8; --good:#22c55e; --warn:#f59e0b; --bad:#ef4444;
}
* { box-sizing:border-box; }
body { margin:0; font-family:'Pretendard','Apple SD Gothic Neo',sans-serif;
       background:var(--bg); color:var(--text); }

header { padding:18px 24px; border-bottom:1px solid var(--border);
         display:flex; align-items:center; gap:16px; flex-wrap:wrap; }
header h1 { margin:0; font-size:20px; font-weight:700; }
.meta { color:var(--muted); font-size:13px; }
.save-status { margin-left:auto; padding:6px 12px; border-radius:6px;
               font-size:12px; background:var(--panel); color:var(--muted); }
.save-status.ok { background:#064e3b; color:#86efac; }
.save-status.err { background:#7f1d1d; color:#fecaca; }
.save-status.dirty { background:#78350f; color:#fed7aa; }
.ro-badge { margin-left:auto; padding:6px 12px; border-radius:6px;
            font-size:12px; background:#1e293b; color:var(--muted); }

.tabs { padding:0 24px; display:flex; gap:4px; border-bottom:1px solid var(--border);
        background:var(--bg); position:sticky; top:0; z-index:10; }
.tab { padding:12px 22px; cursor:pointer; border-bottom:3px solid transparent;
       color:var(--muted); font-weight:600; font-size:15px;
       transition:all .15s; }
.tab:hover { color:var(--text); }
.tab.active { color:var(--text); border-bottom-color:var(--doc-color, var(--accent)); }

main { padding:24px; max-width:1400px; margin:0 auto; }
.doc-page { display:none; }
.doc-page.active { display:block; }

/* 섹션 */
.section { background:var(--panel); border:1px solid var(--border);
           border-radius:12px; padding:20px; margin-bottom:20px; }
.section h2 { margin:0 0 14px; font-size:16px; font-weight:700;
              display:flex; align-items:center; gap:10px;
              padding-bottom:10px; border-bottom:1px solid var(--border); }
.section h2 .badge { font-size:11px; padding:2px 8px; border-radius:10px;
                     background:var(--panel2); color:var(--muted);
                     font-weight:500; }
.section h2 .hint { font-size:11px; font-weight:400; color:var(--muted); margin-left:auto; }

/* KPI */
.kpi-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
            gap:12px; margin-bottom:14px; }
.kpi { background:var(--panel2); border-radius:8px; padding:14px;
       border-left:3px solid var(--doc-color,var(--accent)); }
.kpi .label { color:var(--muted); font-size:12px; }
.kpi .value { font-size:24px; font-weight:700; margin-top:4px; }
.kpi .delta { font-size:12px; margin-top:4px; }
.kpi .delta.up { color:var(--good); }
.kpi .delta.down { color:var(--bad); }
.kpi .delta.flat { color:var(--muted); }
.chart-row { display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr));
             gap:12px; margin-top:14px; }
.chart-box { background:var(--panel2); border-radius:8px; padding:12px; }
.chart-box .title { color:var(--muted); font-size:12px; margin-bottom:6px; }
.chart-box canvas { width:100%!important; height:140px!important; }

/* 미팅 바 */
.meeting-bar { display:flex; gap:10px; align-items:center; flex-wrap:wrap;
                margin-bottom:18px; padding:12px; background:var(--panel2);
                border-radius:8px; }
.meeting-bar select, .meeting-bar input[type=date] {
  background:var(--panel3); color:var(--text);
  border:1px solid var(--border2); padding:7px 10px;
  border-radius:6px; font-size:14px; }
.meeting-bar label { font-size:13px; color:var(--muted); display:flex; align-items:center; gap:6px; }
.new-meeting-btn { background:var(--accent); color:#0f172a; border:none;
                    padding:7px 16px; border-radius:6px; font-weight:700;
                    cursor:pointer; font-size:13px; }
.new-meeting-btn:hover { opacity:.85; }

/* Conversation Topic */
.topic-section { margin-bottom:18px; }
.topic-picker { display:flex; flex-wrap:wrap; gap:8px; margin:10px 0 14px; }
.chip { background:var(--panel3); color:var(--muted); border:1px solid var(--border2);
        padding:6px 14px; border-radius:18px; font-size:13px; cursor:pointer;
        transition:all .15s; font-weight:500; }
.chip:hover { color:var(--text); border-color:var(--accent); }
.chip.active { background:var(--accent); color:#0f172a; border-color:var(--accent); font-weight:700; }
.chip.done { opacity:.5; text-decoration:line-through; }
.chip-empty { font-size:13px; color:var(--muted); padding:6px 0; }

/* Topic Cards (선택된 프로젝트 인라인) */
.topic-cards { display:flex; flex-direction:column; gap:14px; }
.topic-card { background:var(--panel2); border:1px solid var(--border2);
               border-left:4px solid var(--doc-color,var(--accent));
               border-radius:8px; padding:14px 16px; }
.topic-card-header { display:flex; align-items:center; gap:10px; flex-wrap:wrap;
                      padding-bottom:10px; border-bottom:1px solid var(--border);
                      margin-bottom:12px; }
.topic-card-header .proj-name { font-size:15px; font-weight:700; flex:1; min-width:200px; }
.topic-card-header select { background:var(--panel3); color:var(--text);
                              border:1px solid var(--border2); padding:4px 8px;
                              border-radius:4px; font-size:12px; }
.topic-card-header input[type=text] { background:transparent; color:var(--text);
                                        border:none; outline:none; font-size:15px;
                                        font-weight:700; flex:1; min-width:200px; padding:2px; }
.topic-card-header input[type=text]:focus { background:var(--panel3); border-radius:4px; padding:4px; }
.topic-card-body { display:grid; grid-template-columns:1fr 1fr; gap:18px; }
@media (max-width:900px) { .topic-card-body { grid-template-columns:1fr; } }
.sub-label { color:var(--muted); font-size:12px; font-weight:600;
              margin-bottom:8px; display:flex; align-items:center; gap:6px; }
.learnings-list { list-style:none; padding:0; margin:0; max-height:240px; overflow-y:auto; }
.learnings-list li { padding:6px 0; border-bottom:1px dashed var(--border);
                      font-size:13px; display:flex; gap:8px; align-items:flex-start; }
.learnings-list li:last-child { border-bottom:none; }
.learning-date { color:var(--muted); font-size:11px; min-width:62px; padding-top:2px; }
.learning-text { flex:1; line-height:1.45; }
.learning-meta { font-size:10px; color:var(--muted); }
.del-mini { background:transparent; color:var(--bad); border:none; cursor:pointer;
             font-size:13px; padding:0 4px; opacity:.6; }
.del-mini:hover { opacity:1; }
.add-learning, .add-support-input { width:100%; background:var(--panel3);
  color:var(--text); border:1px solid var(--border2); border-radius:6px;
  padding:7px 10px; font-size:13px; margin-top:8px; }
.add-learning:focus, .add-support-input:focus { outline:1px solid var(--accent); border-color:var(--accent); }

.proj-supports { list-style:none; padding:0; margin:0; }
.proj-supports li { display:flex; align-items:flex-start; gap:8px;
                     padding:6px 0; border-bottom:1px dashed var(--border);
                     font-size:13px; }
.proj-supports li:last-child { border-bottom:none; }
.proj-supports input[type=text] { flex:1; background:transparent; color:var(--text);
                                    border:none; outline:none; font-size:13px; padding:2px; }
.proj-supports input[type=text]:focus { background:var(--panel3); border-radius:4px; padding:4px; }
.proj-supports input[type=checkbox] { margin-top:4px; }
.type-select { background:var(--panel3); color:var(--text);
                border:1px solid var(--border2); border-radius:4px;
                padding:2px 6px; font-size:11px; }

/* Work / Career */
.agenda-grid { display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-top:18px; }
@media (max-width:900px) { .agenda-grid { grid-template-columns:1fr; } }
.agenda-label { color:var(--muted); font-size:13px; margin-bottom:6px;
                 display:flex; justify-content:space-between; align-items:center; }
.agenda-label .hint { font-size:11px; color:var(--muted); font-weight:400; }
textarea.agenda { width:100%; min-height:120px; background:var(--panel2);
                  color:var(--text); border:1px solid var(--border);
                  border-radius:6px; padding:10px; font-size:14px;
                  font-family:inherit; resize:vertical; line-height:1.6; }
textarea.agenda:focus { outline:1px solid var(--accent); border-color:var(--accent); }
.agenda-readonly { background:var(--panel2); border:1px solid var(--border);
                    border-radius:6px; padding:12px; white-space:pre-wrap;
                    line-height:1.6; font-size:14px; min-height:60px; }

/* 일반 Support */
.support-section { margin-top:18px; }
.support-list { list-style:none; padding:0; margin:0; }
.support-list li { display:flex; align-items:flex-start; gap:10px;
                    padding:8px; border-bottom:1px solid var(--border); }
.support-list li:last-child { border-bottom:none; }
.support-list input[type=text] { flex:1; background:transparent; color:var(--text);
                                  border:none; outline:none; font-size:14px; padding:2px; }
.support-list input[type=text]:focus { background:var(--panel3); border-radius:4px; padding:4px; }
.support-list input[type=checkbox] { margin-top:4px; cursor:pointer; }

/* Kanban Board */
.kanban { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }
@media (max-width:900px) { .kanban { grid-template-columns:1fr; } }
.kanban-col { background:var(--panel2); border-radius:8px; padding:12px; min-height:200px; }
.kanban-col-header { font-weight:700; font-size:13px; color:var(--muted);
                      margin-bottom:10px; display:flex; justify-content:space-between;
                      padding-bottom:8px; border-bottom:1px solid var(--border); }
.kanban-col-header.inbox  { color:#94a3b8; }
.kanban-col-header.prog   { color:#bfdbfe; }
.kanban-col-header.done   { color:#86efac; }
.kanban-cards { display:flex; flex-direction:column; gap:8px; }
.kanban-card { background:var(--panel3); border-radius:6px; padding:10px;
                cursor:pointer; border-left:3px solid transparent;
                transition:all .15s; }
.kanban-card:hover { background:#3f4d63; border-left-color:var(--accent); }
.kanban-card.priority-high { border-left-color:var(--bad); }
.kanban-card.priority-mid  { border-left-color:var(--warn); }
.kanban-card.priority-low  { border-left-color:#64748b; }
.kanban-card .name { font-weight:600; font-size:14px; margin-bottom:6px; }
.kanban-card .meta { font-size:11px; color:var(--muted); display:flex; gap:8px; align-items:center; }
.kanban-card .recent { margin-top:8px; padding:6px 8px; background:rgba(0,0,0,.2);
                        border-radius:4px; font-size:11px; color:var(--muted);
                        white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.add-card-btn { width:100%; background:transparent; color:var(--muted);
                  border:1px dashed var(--border2); border-radius:6px;
                  padding:8px; font-size:12px; cursor:pointer; margin-top:8px; }
.add-card-btn:hover { color:var(--accent); border-color:var(--accent); }
.kanban-empty { font-size:12px; color:var(--muted); padding:8px 4px; }

/* Pills */
.pill { display:inline-block; padding:2px 8px; border-radius:10px; font-size:11px; font-weight:600; }
.pill.high { background:#7f1d1d; color:#fecaca; }
.pill.mid  { background:#78350f; color:#fed7aa; }
.pill.low  { background:#1e3a8a; color:#bfdbfe; }
.pill.done { background:#064e3b; color:#86efac; }
.pill.inprogress { background:#1e3a8a; color:#bfdbfe; }
.pill.inbox { background:#374151; color:#d1d5db; }

/* Modal — Project History */
.modal-bg { position:fixed; inset:0; background:rgba(0,0,0,.65);
            display:flex; align-items:center; justify-content:center;
            z-index:50; padding:20px; }
.modal-bg[hidden] { display:none; }
.modal-content { background:var(--panel); border:1px solid var(--border2);
                  border-radius:12px; padding:24px; width:100%; max-width:760px;
                  max-height:85vh; overflow-y:auto; position:relative; }
.modal-close { position:absolute; top:14px; right:14px; background:transparent;
                color:var(--muted); border:none; font-size:24px; cursor:pointer; }
.modal-close:hover { color:var(--text); }
.modal-title { font-size:22px; font-weight:700; margin:0 24px 12px 0; }
.modal-meta { display:flex; gap:10px; flex-wrap:wrap; margin-bottom:18px; font-size:12px;
              color:var(--muted); }
.modal-section { margin-bottom:22px; }
.modal-section h3 { font-size:14px; color:var(--accent); margin:0 0 10px;
                     padding-bottom:6px; border-bottom:1px solid var(--border); }

/* Follow-up & History */
.item-list { list-style:none; padding:0; margin:0; }
.item-list li { padding:10px; border-bottom:1px solid var(--border); font-size:13px;
                 display:flex; gap:10px; align-items:flex-start; }
.item-list li:last-child { border-bottom:none; }
.history details { border:1px solid var(--border); border-radius:6px;
                    padding:8px 12px; margin-bottom:6px; background:var(--panel2);
                    font-size:13px; }
.history summary { cursor:pointer; color:var(--muted); }
.history summary strong { color:var(--text); }
.history summary .topic-tags { margin-left:8px; font-size:11px; }
.history summary .topic-tag { display:inline-block; padding:1px 6px; margin-right:4px;
                                background:var(--panel3); border-radius:8px;
                                color:var(--accent); }
.history .body { margin-top:8px; }
.history .body .heading { color:var(--accent); font-weight:600;
                            margin-top:12px; display:block; }
.history .body p { white-space:pre-wrap; line-height:1.6; margin:4px 0 0; }

/* 일반 버튼 */
.add-btn { background:transparent; color:var(--accent); border:1px dashed var(--border2);
            padding:8px 14px; border-radius:6px; cursor:pointer;
            font-size:13px; margin-top:8px; }
.add-btn:hover { background:var(--panel2); }
.del-btn { background:transparent; color:var(--bad); border:none; cursor:pointer;
            font-size:14px; padding:4px 8px; }
.del-btn:hover { color:var(--text); }
"""


# ─────────────────────────────────────────────────────────
# 공통 RENDER JS — PAGE/PUBLIC 둘 다 동일 사용. READONLY로 분기.
# ─────────────────────────────────────────────────────────
RENDER_JS = r"""
// ───── 전역 ─────
let VICE_DOCTORS, DOC_COLORS, METRICS, STATE;
let activeDoc = null;
const currentIdx = {};   // doc -> meeting index
const charts = {};

// ───── 유틸 ─────
const todayStr = () => new Date().toISOString().slice(0,10);
const currentMonth = () => {
  const t = new Date();
  return `${t.getFullYear()}-${String(t.getMonth()+1).padStart(2,"0")}`;
};
const monthLabel = (mk) => mk.replace("-",".");
const fmt = (n) => (n >= 100000) ? (Math.round(n/10000)).toLocaleString() + "만" :
                   (n >= 10000)  ? (n/10000).toFixed(1) + "만" :
                   n.toLocaleString();
const fmtPct = (v) => (v == null) ? "-" : v.toFixed(1) + "%";
function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, c =>
    ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"})[c]);
}
function genId(prefix) {
  return prefix + "_" + Math.random().toString(16).slice(2,10);
}
function statusPillClass(s) {
  if (s === "Done") return "done";
  if (s === "In Progress") return "inprogress";
  return "inbox";
}
function priorityClass(p) {
  return "priority-" + (p||"mid").toLowerCase();
}

// ───── State 접근 ─────
function getProjects(doc) { return STATE.projects[doc] || (STATE.projects[doc] = []); }
function getNotes(doc)    { return STATE.notes[doc]    || (STATE.notes[doc]    = []); }
function getProject(doc, pid) { return getProjects(doc).find(p => p.id === pid); }
function currentMeeting(doc) {
  const notes = getNotes(doc);
  if (notes.length === 0) {
    if (READONLY) return null;
    notes.push(newMeeting());
  }
  let idx = currentIdx[doc];
  if (idx == null || idx >= notes.length) idx = notes.length - 1;
  currentIdx[doc] = idx;
  return notes[idx];
}
function newMeeting() {
  return {
    id: genId("m"),
    date: todayStr(),
    month: currentMonth(),
    done: false,
    mood: "",
    work: "",
    career: "",
    topic_projects: [],
    support: [],
  };
}
function newProject() {
  return {
    id: genId("p"),
    name: "",
    priority: "Mid",
    status: "Inbox",
    mood: "",
    created: todayStr(),
    memo: "",
    learnings: [],
  };
}
function newSupport(projectId) {
  return { id: genId("s"), type:"Help", need:"", reviewed:false, project_id: projectId || null };
}

// ───── 자동 저장 (편집 모드만) ─────
let saveTimer = null;
let saveDirty = false;
function markDirty() {
  if (READONLY) return;
  saveDirty = true;
  const $s = document.getElementById("saveStatus");
  if ($s) { $s.textContent = "저장 중…"; $s.className = "save-status dirty"; }
  clearTimeout(saveTimer);
  saveTimer = setTimeout(doSave, 600);
}
async function doSave() {
  if (READONLY) return;
  const $s = document.getElementById("saveStatus");
  try {
    const res = await fetch("/save", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify(STATE),
    });
    if (!res.ok) throw new Error(res.status);
    saveDirty = false;
    const t = new Date();
    if ($s) {
      $s.textContent = `저장됨 ${String(t.getHours()).padStart(2,"0")}:${String(t.getMinutes()).padStart(2,"0")}:${String(t.getSeconds()).padStart(2,"0")}`;
      $s.className = "save-status ok";
    }
  } catch(e) {
    if ($s) {
      $s.textContent = "저장 실패 — JSON 다운로드로 대체";
      $s.className = "save-status err";
    }
    const blob = new Blob([JSON.stringify(STATE, null, 2)], {type:"application/json"});
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = "1on1.json"; a.click();
  }
}
window.addEventListener("beforeunload", (e) => {
  if (!READONLY && saveDirty) { e.preventDefault(); e.returnValue = ""; }
});

// ───── 부트 ─────
function boot(payload) {
  METRICS      = payload.metrics;
  STATE        = payload.state;
  VICE_DOCTORS = payload.vice_doctors;
  DOC_COLORS   = payload.doc_colors;
  // 스키마 보강 (구버전 호환)
  VICE_DOCTORS.forEach(doc => {
    STATE.notes[doc]    = (STATE.notes[doc]    || []).map(migrateNote);
    STATE.projects[doc] = (STATE.projects[doc] || []).map(migrateProject);
  });
  renderTabs();
  renderPages();
  setupModal();
}
function migrateNote(n) {
  if (!n.id) n.id = genId("m");
  if (!n.mood) n.mood = "";
  if (!n.topic_projects) n.topic_projects = [];
  (n.support||[]).forEach(s => { if(!s.id) s.id = genId("s"); if(s.project_id===undefined) s.project_id = null; });
  return n;
}
function migrateProject(p) {
  if (!p.id) p.id = genId("p");
  if (!p.learnings) p.learnings = [];
  if (!p.created) p.created = "";
  if (!p.memo) p.memo = "";
  return p;
}

function renderTabs() {
  const $t = document.getElementById("tabs");
  $t.innerHTML = "";
  VICE_DOCTORS.forEach((doc,i) => {
    const el = document.createElement("div");
    el.className = "tab" + (i===0 ? " active" : "");
    el.textContent = doc + " 원장";
    el.style.setProperty("--doc-color", DOC_COLORS[doc] || DOC_COLORS._default);
    el.dataset.doc = doc;
    el.onclick = () => switchTab(doc);
    $t.appendChild(el);
  });
  activeDoc = VICE_DOCTORS[0];
}
function switchTab(doc) {
  activeDoc = doc;
  document.querySelectorAll(".tab").forEach(el =>
    el.classList.toggle("active", el.dataset.doc === doc));
  document.querySelectorAll(".doc-page").forEach(el =>
    el.classList.toggle("active", el.dataset.doc === doc));
  renderCharts(doc);
}

function renderPages() {
  const $m = document.getElementById("main");
  $m.innerHTML = "";
  VICE_DOCTORS.forEach((doc,i) => {
    const page = document.createElement("div");
    page.className = "doc-page" + (i===0 ? " active" : "");
    page.dataset.doc = doc;
    page.style.setProperty("--doc-color", DOC_COLORS[doc] || DOC_COLORS._default);
    page.innerHTML = renderDocShell(doc);
    $m.appendChild(page);
    renderDocPage(doc);
  });
}

function renderDocShell(doc) {
  return `
    <section class="section" id="metrics-${doc}"></section>
    <section class="section" id="meeting-${doc}"></section>
    <section class="section" id="board-${doc}"></section>
    <section class="section" id="followup-${doc}"></section>
    <section class="section history" id="history-${doc}"></section>
  `;
}

function renderDocPage(doc) {
  renderMetrics(doc);
  renderMeeting(doc);
  renderBoard(doc);
  renderFollowup(doc);
  renderHistory(doc);
  renderCharts(doc);
}

// ───── Section A: 객관 지표 ─────
function renderMetrics(doc) {
  const months = METRICS.months || [];
  const rows = METRICS.by_doc[doc] || [];
  const curIdx = rows.length - 1;
  const cur = rows[curIdx] || null;
  const prev = curIdx > 0 ? rows[curIdx-1] : null;

  const $sec = document.getElementById(`metrics-${doc}`);
  $sec.innerHTML = `
    <h2>📊 객관 지표 <span class="badge">${months[curIdx] ? monthLabel(months[curIdx]) : "이번 달"}</span>
      <span class="hint">CSV에서 자동 집계 · 매주 갱신</span></h2>
    ${cur ? renderKPIs(cur, prev) : '<div class="meta">데이터 없음</div>'}
    <div class="chart-row">
      <div class="chart-box"><div class="title">월별 매출 추이 (만원)</div><canvas id="ch-rev-${doc}"></canvas></div>
      <div class="chart-box"><div class="title">월별 초진·재초진</div><canvas id="ch-first-${doc}"></canvas></div>
      <div class="chart-box"><div class="title">월별 재진율·삼진율 (%)</div><canvas id="ch-ret-${doc}"></canvas></div>
      <div class="chart-box"><div class="title">월별 건보추나 (건)</div><canvas id="ch-chuna-${doc}"></canvas></div>
    </div>
  `;
}
function renderKPIs(cur, prev) {
  const items = [
    { label:"총 매출", value: fmt(cur.revenue.total) + "원",
      delta: deltaPct(cur.revenue.total, prev?.revenue?.total),
      sub: `건보 ${fmt(cur.revenue["건보"])} · 자보 ${fmt(cur.revenue["자보"])} · 비급 ${fmt(cur.revenue["비급여"])}` },
    { label:"재진율", value: fmtPct(cur.retention.revisit_rate),
      delta: deltaPP(cur.retention.revisit_rate, prev?.retention?.revisit_rate),
      sub: `삼진율 ${fmtPct(cur.retention.third_rate)}` },
    { label:"초진 (TA+건보)", value: cur.first["초진합계"] + "명",
      delta: deltaPct(cur.first["초진합계"], prev?.first?.["초진합계"]),
      sub: `TA ${cur.first.ta} · 건보 ${cur.first.kbo} · 재초진 ${cur.first.follow}` },
    { label:"건보추나", value: cur.chuna["건보"] + "건",
      delta: deltaPct(cur.chuna["건보"], prev?.chuna?.["건보"]),
      sub: `TA추나 ${cur.chuna.TA}건` },
    { label:"출근일", value: cur.work_days + "일",
      delta: prev ? deltaRaw(cur.work_days, prev.work_days, "일") : { html:"-", cls:"flat" },
      sub: `진료 합계 ${cur.first["전체"]}회` },
  ];
  return `<div class="kpi-grid">` + items.map(it => `
    <div class="kpi">
      <div class="label">${it.label}</div>
      <div class="value">${it.value}</div>
      <div class="delta ${it.delta.cls}">${it.delta.html}</div>
      <div class="meta" style="font-size:11px; margin-top:4px;">${it.sub}</div>
    </div>`).join("") + `</div>`;
}
function deltaPct(cur, prev) {
  if (prev == null || prev === 0) return { html:"전월 데이터 없음", cls:"flat" };
  const d = (cur - prev) / prev * 100;
  const arrow = d > 0 ? "▲" : d < 0 ? "▼" : "—";
  const cls = Math.abs(d) < 1 ? "flat" : (d > 0 ? "up" : "down");
  return { html: `${arrow} ${Math.abs(d).toFixed(1)}% vs 전월`, cls };
}
function deltaPP(cur, prev) {
  if (prev == null) return { html:"전월 데이터 없음", cls:"flat" };
  const d = cur - prev;
  const arrow = d > 0 ? "▲" : d < 0 ? "▼" : "—";
  const cls = Math.abs(d) < 0.5 ? "flat" : (d > 0 ? "up" : "down");
  return { html: `${arrow} ${Math.abs(d).toFixed(1)}p vs 전월`, cls };
}
function deltaRaw(cur, prev, unit) {
  const d = cur - prev;
  const arrow = d > 0 ? "▲" : d < 0 ? "▼" : "—";
  const cls = d === 0 ? "flat" : (d > 0 ? "up" : "down");
  return { html: `${arrow} ${Math.abs(d)}${unit} vs 전월`, cls };
}

function destroyIf(key) { if (charts[key]) { charts[key].destroy(); delete charts[key]; } }
function renderCharts(doc) {
  if (!document.getElementById(`ch-rev-${doc}`)) return;
  const rows = METRICS.by_doc[doc] || [];
  const labels = rows.map(r => monthLabel(r.month));
  const color = DOC_COLORS[doc] || DOC_COLORS._default;
  const baseOpts = {
    responsive:true, maintainAspectRatio:false,
    plugins:{ legend:{ labels:{ color:"#cbd5e1", font:{size:11} } } },
    scales:{
      x:{ ticks:{ color:"#94a3b8", font:{size:10} }, grid:{color:"#1e293b"} },
      y:{ ticks:{ color:"#94a3b8", font:{size:10} }, grid:{color:"#1e293b"}, beginAtZero:true },
    },
  };
  destroyIf(`rev-${doc}`);
  charts[`rev-${doc}`] = new Chart(document.getElementById(`ch-rev-${doc}`), {
    type:"bar",
    data:{ labels, datasets:[
      { label:"건보", data: rows.map(r=>Math.round(r.revenue["건보"]/10000)), backgroundColor: color+"99" },
      { label:"자보", data: rows.map(r=>Math.round(r.revenue["자보"]/10000)), backgroundColor: color+"66" },
      { label:"비급여", data: rows.map(r=>Math.round(r.revenue["비급여"]/10000)), backgroundColor: color+"33" },
    ]},
    options:{ ...baseOpts, scales:{ ...baseOpts.scales,
      x:{...baseOpts.scales.x, stacked:true}, y:{...baseOpts.scales.y, stacked:true} } },
  });
  destroyIf(`first-${doc}`);
  charts[`first-${doc}`] = new Chart(document.getElementById(`ch-first-${doc}`), {
    type:"bar",
    data:{ labels, datasets:[
      { label:"TA초진", data: rows.map(r=>r.first.ta), backgroundColor: color },
      { label:"건보초진", data: rows.map(r=>r.first.kbo), backgroundColor: color+"99" },
      { label:"재초진", data: rows.map(r=>r.first.follow), backgroundColor: color+"55" },
    ]}, options: baseOpts,
  });
  destroyIf(`ret-${doc}`);
  charts[`ret-${doc}`] = new Chart(document.getElementById(`ch-ret-${doc}`), {
    type:"line",
    data:{ labels, datasets:[
      { label:"재진율", data: rows.map(r=>r.retention.revisit_rate), borderColor:color, backgroundColor:color+"33", tension:.3, fill:false },
      { label:"삼진율", data: rows.map(r=>r.retention.third_rate), borderColor:"#94a3b8", borderDash:[4,4], tension:.3, fill:false },
    ]}, options:{ ...baseOpts, scales:{ ...baseOpts.scales, y:{...baseOpts.scales.y, max:100} } },
  });
  destroyIf(`chuna-${doc}`);
  charts[`chuna-${doc}`] = new Chart(document.getElementById(`ch-chuna-${doc}`), {
    type:"bar",
    data:{ labels, datasets:[
      { label:"건보추나", data: rows.map(r=>r.chuna["건보"]), backgroundColor: color },
      { label:"TA추나",   data: rows.map(r=>r.chuna.TA),       backgroundColor: color+"55" },
    ]}, options: baseOpts,
  });
}

// ───── Section B: 이번 면담 (Conversation Topic 중심) ─────
function renderMeeting(doc) {
  const notes = getNotes(doc);
  const projects = getProjects(doc);
  const $sec = document.getElementById(`meeting-${doc}`);

  if (notes.length === 0 && READONLY) {
    $sec.innerHTML = `<h2>🗓️ 면담 회차</h2><div class="meta">아직 면담 기록 없음.</div>`;
    return;
  }
  if (notes.length === 0 && !READONLY) {
    notes.push(newMeeting());
    currentIdx[doc] = 0;
  }
  const idx = currentIdx[doc] ?? (notes.length - 1);
  currentIdx[doc] = idx;
  const m = notes[idx];

  // 셀렉터 옵션
  const optsHtml = notes.map((n,i) => `<option value="${i}" ${i===idx?"selected":""}>${n.date} ${n.done?"✅":"📝"}${n.mood?(" "+n.mood):""}</option>`).join("");

  $sec.innerHTML = `
    <h2>🗓️ 이번 면담 <span class="badge">${notes.length}회</span>
      <span class="hint">${m.date}${m.mood?(" · "+m.mood):""}${m.done?" · 완료":""}</span></h2>

    <div class="meeting-bar">
      <select id="meetSel-${doc}">${optsHtml}</select>
      ${READONLY ? '' : `
        <input type="date" id="meetDate-${doc}" value="${m.date}">
        <label>Mood
          <select id="meetMood-${doc}">
            <option value="" ${!m.mood?"selected":""}>—</option>
            <option value="😎" ${m.mood==="😎"?"selected":""}>😎 좋음</option>
            <option value="😀" ${m.mood==="😀"?"selected":""}>😀 보통</option>
            <option value="😇" ${m.mood==="😇"?"selected":""}>😇 어려움</option>
          </select>
        </label>
        <label><input type="checkbox" id="meetDone-${doc}" ${m.done?"checked":""}> 완료</label>
        <button class="new-meeting-btn" data-action="new-meeting">+ 새 면담</button>
        <button class="del-btn" data-action="del-meeting" title="현재 면담 삭제">🗑</button>
      `}
    </div>

    <div class="topic-section">
      <div class="agenda-label">🎯 Conversation Topic
        <span class="hint">이번 면담에서 다룰 프로젝트를 고르세요 (재클릭으로 해제)</span></div>
      <div class="topic-picker" id="topicPicker-${doc}">${renderTopicPicker(doc, m)}</div>
      <div class="topic-cards" id="topicCards-${doc}">${renderTopicCards(doc, m)}</div>
    </div>

    <div class="agenda-grid">
      <div>
        <div class="agenda-label">💼 Work Session
          <span class="hint">업무 진행·이슈·R&R</span></div>
        ${READONLY
          ? `<div class="agenda-readonly">${escapeHtml(m.work||"(작성 안 됨)")}</div>`
          : `<textarea class="agenda" id="work-${doc}" placeholder="• 이번 달 주요 업무\n• 어려움·걸림돌\n• 협업 이슈">${escapeHtml(m.work||"")}</textarea>`}
      </div>
      <div>
        <div class="agenda-label">🌱 Career Session
          <span class="hint">성장·학습·중장기 목표</span></div>
        ${READONLY
          ? `<div class="agenda-readonly">${escapeHtml(m.career||"(작성 안 됨)")}</div>`
          : `<textarea class="agenda" id="career-${doc}" placeholder="• 성장 포인트\n• 학습·스터디\n• 커리어 목표">${escapeHtml(m.career||"")}</textarea>`}
      </div>
    </div>

    <div class="support-section">
      <div class="agenda-label">🤝 일반 Support 요청
        <span class="hint">특정 프로젝트에 묶이지 않는 지원 요청</span></div>
      <ul class="support-list" id="generalSupport-${doc}">${renderGeneralSupports(doc, m)}</ul>
      ${READONLY ? '' : '<button class="add-btn" data-action="add-general-support">+ 일반 Support 추가</button>'}
    </div>
  `;

  // 이벤트
  document.getElementById(`meetSel-${doc}`).addEventListener("change", e => {
    currentIdx[doc] = parseInt(e.target.value);
    renderMeeting(doc); renderFollowup(doc); renderHistory(doc);
  });
  if (!READONLY) {
    document.getElementById(`meetDate-${doc}`).addEventListener("change", e => {
      m.date = e.target.value; m.month = e.target.value.slice(0,7); markDirty(); renderMeeting(doc);
    });
    document.getElementById(`meetMood-${doc}`).addEventListener("change", e => {
      m.mood = e.target.value; markDirty(); renderMeeting(doc);
    });
    document.getElementById(`meetDone-${doc}`).addEventListener("change", e => {
      m.done = e.target.checked; markDirty(); renderMeeting(doc);
    });
    document.getElementById(`work-${doc}`).addEventListener("input", e => {
      m.work = e.target.value; markDirty();
    });
    document.getElementById(`career-${doc}`).addEventListener("input", e => {
      m.career = e.target.value; markDirty();
    });
    $sec.querySelectorAll("[data-action]").forEach(btn => {
      btn.addEventListener("click", () => handleSectionAction(doc, btn.dataset.action));
    });
    wireTopicPicker(doc);
    wireTopicCards(doc);
    wireGeneralSupports(doc);
  }
}

function renderTopicPicker(doc, m) {
  const projects = getProjects(doc);
  if (projects.length === 0) {
    return `<div class="chip-empty">아직 등록된 프로젝트 없음 — 아래 보드에서 추가하세요.</div>`;
  }
  // 활성 + 보관 분리 (Done 은 흐리게)
  const sorted = [...projects].sort((a,b) => {
    const order = { "In Progress":0, "Inbox":1, "Done":2 };
    return (order[a.status]??1) - (order[b.status]??1);
  });
  return sorted.map(p => {
    const sel = m.topic_projects.includes(p.id);
    const cls = "chip" + (sel?" active":"") + (p.status==="Done"?" done":"");
    return `<button class="${cls}" data-pid="${p.id}">${escapeHtml(p.name||"(이름 없음)")}</button>`;
  }).join("");
}

function renderTopicCards(doc, m) {
  if (m.topic_projects.length === 0) {
    return `<div class="chip-empty">위에서 프로젝트를 선택하면 카드가 펼쳐집니다.</div>`;
  }
  return m.topic_projects.map(pid => {
    const p = getProject(doc, pid);
    if (!p) return "";
    return renderTopicCard(doc, m, p);
  }).join("");
}

function renderTopicCard(doc, m, p) {
  const learningsHtml = (p.learnings||[]).slice().reverse().map((l,i) => {
    const origIdx = p.learnings.length - 1 - i;
    return `<li>
      <span class="learning-date">${l.date}</span>
      <span class="learning-text">${escapeHtml(l.text||"")}</span>
      ${READONLY ? '' : `<button class="del-mini" data-act="del-learning" data-pid="${p.id}" data-i="${origIdx}">✕</button>`}
    </li>`;
  }).join("") || `<li class="meta" style="border:none;">아직 누적된 Learning 없음</li>`;

  const projSups = (m.support||[]).filter(s => s.project_id === p.id);
  const supsHtml = projSups.map(s => renderSupportLi(doc, m, s, p.id)).join("")
    || `<li class="meta" style="border:none;">이번 면담 관련 Support 없음</li>`;

  const statusOpts = ["Inbox","In Progress","Done"].map(v =>
    `<option value="${v}" ${p.status===v?"selected":""}>${v}</option>`).join("");
  const prioOpts   = ["High","Mid","Low"].map(v =>
    `<option value="${v}" ${p.priority===v?"selected":""}>${v}</option>`).join("");
  const moodOpts   = [["","—"],["😎","😎"],["😀","😀"],["😇","😇"]].map(([v,t]) =>
    `<option value="${v}" ${p.mood===v?"selected":""}>${t}</option>`).join("");

  return `
    <div class="topic-card" data-pid="${p.id}">
      <div class="topic-card-header">
        ${READONLY
          ? `<span class="proj-name">${escapeHtml(p.name||"(이름 없음)")}</span>`
          : `<input type="text" data-act="proj-name" data-pid="${p.id}" value="${escapeHtml(p.name||"")}" placeholder="프로젝트명">`}
        ${READONLY
          ? `<span class="pill ${statusPillClass(p.status)}">${p.status}</span>
             <span class="pill ${(p.priority||"mid").toLowerCase()}">${p.priority}</span>
             ${p.mood ? `<span>${p.mood}</span>` : ''}`
          : `<select data-act="proj-status" data-pid="${p.id}">${statusOpts}</select>
             <select data-act="proj-prio" data-pid="${p.id}">${prioOpts}</select>
             <select data-act="proj-mood" data-pid="${p.id}">${moodOpts}</select>
             <button class="del-btn" data-act="proj-detach" data-pid="${p.id}" title="이번 면담 토픽에서 제외">−</button>`}
      </div>
      <div class="topic-card-body">
        <div>
          <div class="sub-label">📚 누적 Learning <span style="font-weight:400; color:var(--muted);">(${(p.learnings||[]).length})</span></div>
          <ul class="learnings-list">${learningsHtml}</ul>
          ${READONLY ? '' : `<input class="add-learning" data-act="add-learning" data-pid="${p.id}" placeholder="이번 면담에서 배운 점 (Enter)">`}
        </div>
        <div>
          <div class="sub-label">🤝 Support 요청 <span style="font-weight:400; color:var(--muted);">(이번 면담)</span></div>
          <ul class="proj-supports">${supsHtml}</ul>
          ${READONLY ? '' : `<button class="add-btn" data-act="add-proj-support" data-pid="${p.id}" style="margin-top:6px;">+ Support 추가</button>`}
        </div>
      </div>
    </div>`;
}

function renderSupportLi(doc, m, s, projectId) {
  const typeOpts = ["Alignment","Decision","Help"].map(v =>
    `<option value="${v}" ${s.type===v?"selected":""}>${v}</option>`).join("");
  if (READONLY) {
    return `<li>
      ${s.reviewed?"✅":"⬜"}
      <span class="pill ${s.type?.toLowerCase()||""}" style="background:var(--panel3); color:var(--text);">${s.type||"-"}</span>
      <span style="flex:1;">${escapeHtml(s.need||"")}</span>
    </li>`;
  }
  return `<li>
    <input type="checkbox" ${s.reviewed?"checked":""} data-act="sup-rev" data-sid="${s.id}">
    <select class="type-select" data-act="sup-type" data-sid="${s.id}">${typeOpts}</select>
    <input type="text" value="${escapeHtml(s.need||"")}" placeholder="필요한 지원 사항" data-act="sup-need" data-sid="${s.id}">
    <button class="del-mini" data-act="sup-del" data-sid="${s.id}">✕</button>
  </li>`;
}

function renderGeneralSupports(doc, m) {
  const list = (m.support||[]).filter(s => !s.project_id);
  if (list.length === 0) return `<li class="meta" style="border:none;">일반 Support 없음</li>`;
  return list.map(s => renderSupportLi(doc, m, s, null)).join("");
}

function wireTopicPicker(doc) {
  const $p = document.getElementById(`topicPicker-${doc}`);
  $p.querySelectorAll(".chip").forEach(btn => {
    btn.addEventListener("click", () => {
      const m = currentMeeting(doc);
      const pid = btn.dataset.pid;
      const i = m.topic_projects.indexOf(pid);
      if (i >= 0) m.topic_projects.splice(i, 1);
      else m.topic_projects.push(pid);
      markDirty();
      // 부분 다시 렌더 — 토픽 카드만
      document.getElementById(`topicPicker-${doc}`).innerHTML = renderTopicPicker(doc, m);
      document.getElementById(`topicCards-${doc}`).innerHTML = renderTopicCards(doc, m);
      wireTopicPicker(doc); wireTopicCards(doc);
    });
  });
}

function wireTopicCards(doc) {
  if (READONLY) return;
  const $c = document.getElementById(`topicCards-${doc}`);
  $c.querySelectorAll("[data-act]").forEach(el => {
    const evt = (el.tagName === "INPUT" && el.type === "text") ? "input"
              : (el.tagName === "INPUT" && el.type === "checkbox") ? "change"
              : (el.tagName === "SELECT") ? "change"
              : "click";
    el.addEventListener(evt, ev => {
      const m = currentMeeting(doc);
      const pid = el.dataset.pid;
      const sid = el.dataset.sid;
      const act = el.dataset.act;
      const p = pid ? getProject(doc, pid) : null;
      if (act === "proj-name")   { p.name = el.value; markDirty(); }
      else if (act === "proj-status") { p.status = el.value; markDirty(); renderBoard(doc); document.getElementById(`topicPicker-${doc}`).innerHTML = renderTopicPicker(doc, m); wireTopicPicker(doc); }
      else if (act === "proj-prio")   { p.priority = el.value; markDirty(); renderBoard(doc); }
      else if (act === "proj-mood")   { p.mood = el.value; markDirty(); renderBoard(doc); }
      else if (act === "proj-detach") {
        const i = m.topic_projects.indexOf(pid);
        if (i>=0) m.topic_projects.splice(i,1);
        markDirty();
        document.getElementById(`topicPicker-${doc}`).innerHTML = renderTopicPicker(doc, m);
        document.getElementById(`topicCards-${doc}`).innerHTML = renderTopicCards(doc, m);
        wireTopicPicker(doc); wireTopicCards(doc);
      }
      else if (act === "add-learning") {
        if (ev.type === "keydown" || (ev.key === "Enter") || ev.type === "blur") return; // wait Enter
        // handled below by 'keydown' listener
      }
      else if (act === "del-learning") {
        const i = parseInt(el.dataset.i);
        p.learnings.splice(i, 1);
        markDirty();
        document.getElementById(`topicCards-${doc}`).innerHTML = renderTopicCards(doc, m);
        wireTopicCards(doc);
      }
      else if (act === "add-proj-support") {
        m.support = m.support || [];
        m.support.push(newSupport(pid));
        markDirty();
        document.getElementById(`topicCards-${doc}`).innerHTML = renderTopicCards(doc, m);
        wireTopicCards(doc);
      }
      else if (act === "sup-rev")  { const s = m.support.find(s => s.id === sid); if(s){ s.reviewed = el.checked; markDirty(); } }
      else if (act === "sup-type") { const s = m.support.find(s => s.id === sid); if(s){ s.type = el.value; markDirty(); } }
      else if (act === "sup-need") { const s = m.support.find(s => s.id === sid); if(s){ s.need = el.value; markDirty(); } }
      else if (act === "sup-del")  {
        m.support = (m.support||[]).filter(s => s.id !== sid);
        markDirty();
        document.getElementById(`topicCards-${doc}`).innerHTML = renderTopicCards(doc, m);
        wireTopicCards(doc);
      }
    });
  });
  // add-learning Enter 처리
  $c.querySelectorAll("[data-act=add-learning]").forEach(inp => {
    inp.addEventListener("keydown", ev => {
      if (ev.key !== "Enter") return;
      const v = inp.value.trim();
      if (!v) return;
      const m = currentMeeting(doc);
      const pid = inp.dataset.pid;
      const p = getProject(doc, pid);
      p.learnings.push({ date: todayStr(), text: v, meeting_id: m.id });
      inp.value = "";
      markDirty();
      document.getElementById(`topicCards-${doc}`).innerHTML = renderTopicCards(doc, m);
      wireTopicCards(doc);
    });
  });
}

function wireGeneralSupports(doc) {
  if (READONLY) return;
  const $u = document.getElementById(`generalSupport-${doc}`);
  $u.querySelectorAll("[data-act]").forEach(el => {
    const evt = (el.tagName === "INPUT" && el.type === "text") ? "input"
              : (el.tagName === "INPUT" && el.type === "checkbox") ? "change"
              : (el.tagName === "SELECT") ? "change"
              : "click";
    el.addEventListener(evt, () => {
      const m = currentMeeting(doc);
      const sid = el.dataset.sid;
      const act = el.dataset.act;
      const s = (m.support||[]).find(s => s.id === sid);
      if (!s) return;
      if (act === "sup-rev")  s.reviewed = el.checked;
      else if (act === "sup-type") s.type = el.value;
      else if (act === "sup-need") s.need = el.value;
      else if (act === "sup-del") {
        m.support = (m.support||[]).filter(x => x.id !== sid);
        markDirty();
        document.getElementById(`generalSupport-${doc}`).innerHTML = renderGeneralSupports(doc, m);
        wireGeneralSupports(doc); return;
      }
      markDirty();
    });
  });
}

function handleSectionAction(doc, act) {
  const notes = getNotes(doc);
  if (act === "new-meeting") {
    notes.push(newMeeting());
    currentIdx[doc] = notes.length - 1;
    markDirty();
    renderMeeting(doc); renderFollowup(doc); renderHistory(doc);
  } else if (act === "del-meeting") {
    if (!confirm("현재 면담 회차를 삭제할까요?")) return;
    const i = currentIdx[doc] ?? notes.length-1;
    notes.splice(i,1);
    if (notes.length === 0) notes.push(newMeeting());
    currentIdx[doc] = notes.length-1;
    markDirty();
    renderMeeting(doc); renderFollowup(doc); renderHistory(doc);
  } else if (act === "add-general-support") {
    const m = currentMeeting(doc);
    m.support = m.support || [];
    m.support.push(newSupport(null));
    markDirty();
    document.getElementById(`generalSupport-${doc}`).innerHTML = renderGeneralSupports(doc, m);
    wireGeneralSupports(doc);
  } else if (act === "add-project") {
    const projects = getProjects(doc);
    const p = newProject();
    p.status = "Inbox";
    projects.push(p);
    markDirty();
    renderBoard(doc); renderMeeting(doc);
  }
}

// ───── Section C: Project Board (Kanban) ─────
function renderBoard(doc) {
  const projects = getProjects(doc);
  const cols = { "Inbox": [], "In Progress": [], "Done": [] };
  projects.forEach(p => {
    (cols[p.status] || cols["Inbox"]).push(p);
  });

  const $sec = document.getElementById(`board-${doc}`);
  $sec.innerHTML = `
    <h2>📋 프로젝트 보드 <span class="badge">${projects.length}건</span>
      <span class="hint">카드 클릭으로 전체 history 보기</span></h2>
    <div class="kanban">
      ${renderKanbanCol(doc, "Inbox", "📥 Inbox", "inbox", cols["Inbox"])}
      ${renderKanbanCol(doc, "In Progress", "🚀 In Progress", "prog", cols["In Progress"])}
      ${renderKanbanCol(doc, "Done", "✅ Done", "done", cols["Done"])}
    </div>
  `;
  $sec.querySelectorAll(".kanban-card").forEach(card => {
    card.addEventListener("click", () => openProjectModal(doc, card.dataset.pid));
  });
  if (!READONLY) {
    $sec.querySelectorAll(".add-card-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const projects = getProjects(doc);
        const p = newProject();
        p.status = btn.dataset.status;
        projects.push(p);
        markDirty();
        renderBoard(doc); renderMeeting(doc);
        // 새 카드 모달로 바로
        openProjectModal(doc, p.id);
      });
    });
  }
}

function renderKanbanCol(doc, status, title, cls, projects) {
  const cards = projects.length === 0
    ? `<div class="kanban-empty">— 없음 —</div>`
    : projects.map(p => renderKanbanCard(doc, p)).join("");
  const addBtn = READONLY ? '' :
    `<button class="add-card-btn" data-status="${status}">+ 새 프로젝트</button>`;
  return `
    <div class="kanban-col">
      <div class="kanban-col-header ${cls}">${title} <span>${projects.length}</span></div>
      <div class="kanban-cards">${cards}</div>
      ${addBtn}
    </div>`;
}

function renderKanbanCard(doc, p) {
  const recent = (p.learnings||[]).slice(-1)[0];
  const recentHtml = recent
    ? `<div class="recent">📚 ${escapeHtml(recent.text)}</div>` : "";
  return `
    <div class="kanban-card ${priorityClass(p.priority)}" data-pid="${p.id}">
      <div class="name">${escapeHtml(p.name || "(이름 없음)")}</div>
      <div class="meta">
        <span class="pill ${(p.priority||"mid").toLowerCase()}">${p.priority||"Mid"}</span>
        ${p.mood ? `<span>${p.mood}</span>` : ''}
        <span style="margin-left:auto;">L ${(p.learnings||[]).length} · S ${countSupportsForProject(doc, p.id)}</span>
      </div>
      ${recentHtml}
    </div>`;
}

function countSupportsForProject(doc, pid) {
  let n = 0;
  getNotes(doc).forEach(m => (m.support||[]).forEach(s => { if (s.project_id === pid) n++; }));
  return n;
}

// ───── Project History Modal ─────
function setupModal() {
  if (document.getElementById("modal")) return;
  const div = document.createElement("div");
  div.id = "modal";
  div.className = "modal-bg";
  div.hidden = true;
  div.innerHTML = `
    <div class="modal-content">
      <button class="modal-close">✕</button>
      <h2 class="modal-title" id="modalTitle"></h2>
      <div class="modal-meta" id="modalMeta"></div>
      <div id="modalBody"></div>
    </div>`;
  document.body.appendChild(div);
  div.addEventListener("click", e => { if (e.target === div) closeModal(); });
  div.querySelector(".modal-close").addEventListener("click", closeModal);
  document.addEventListener("keydown", e => { if (e.key === "Escape") closeModal(); });
}
function closeModal() { document.getElementById("modal").hidden = true; }

function openProjectModal(doc, pid) {
  const p = getProject(doc, pid);
  if (!p) return;
  const notes = getNotes(doc);
  const allSupports = [];
  const touchingMeetings = [];
  notes.forEach(m => {
    if (m.topic_projects?.includes(pid)) touchingMeetings.push(m);
    (m.support||[]).forEach(s => { if (s.project_id === pid) allSupports.push({...s, _meetingDate: m.date, _meetingId: m.id}); });
  });

  const learnings = (p.learnings||[]).slice().sort((a,b) => (a.date||"").localeCompare(b.date||""));
  const learningsHtml = learnings.length === 0
    ? `<div class="meta">아직 누적된 Learning 없음.</div>`
    : `<ul class="learnings-list">${learnings.map(l => `
        <li><span class="learning-date">${l.date}</span>
        <span class="learning-text">${escapeHtml(l.text||"")}</span></li>`).join("")}</ul>`;
  const supsHtml = allSupports.length === 0
    ? `<div class="meta">관련 Support 없음.</div>`
    : `<ul class="item-list">${allSupports.map(s => `
        <li>
          ${s.reviewed?"✅":"⬜"}
          <span class="meta" style="min-width:90px;">${s._meetingDate}</span>
          <span class="pill ${(s.type||"").toLowerCase()}" style="background:var(--panel3); color:var(--text);">${s.type||""}</span>
          <span style="flex:1;">${escapeHtml(s.need||"")}</span>
        </li>`).join("")}</ul>`;
  const meetingsHtml = touchingMeetings.length === 0
    ? `<div class="meta">이 프로젝트를 다룬 면담 없음.</div>`
    : `<ul class="item-list">${touchingMeetings.map(m => `
        <li>
          <span class="meta" style="min-width:90px;">${m.date}</span>
          ${m.mood ? `<span>${m.mood}</span>` : ''}
          <span style="flex:1; color:var(--muted);">${m.done?"✅ 완료":"📝 진행"}${(m.work||"").length>0?" · Work 작성됨":""}${(m.career||"").length>0?" · Career 작성됨":""}</span>
        </li>`).join("")}</ul>`;

  const $m = document.getElementById("modal");
  document.getElementById("modalTitle").innerHTML = escapeHtml(p.name || "(이름 없음)");
  document.getElementById("modalMeta").innerHTML = `
    <span class="pill ${statusPillClass(p.status)}">${p.status}</span>
    <span class="pill ${(p.priority||"mid").toLowerCase()}">${p.priority||"Mid"}</span>
    ${p.mood ? `<span>${p.mood}</span>` : ''}
    ${p.created ? `<span>· 생성 ${p.created}</span>` : ''}
    <span>· Learning ${(p.learnings||[]).length} · Support ${allSupports.length} · 면담 ${touchingMeetings.length}회</span>
    ${READONLY ? '' : `<button class="del-btn" data-pid="${p.id}" id="modalDeleteBtn" style="margin-left:auto;">🗑 프로젝트 삭제</button>`}
  `;
  document.getElementById("modalBody").innerHTML = `
    <div class="modal-section">
      <h3>📚 모든 Learning</h3>
      ${learningsHtml}
    </div>
    <div class="modal-section">
      <h3>🤝 이 프로젝트에 걸린 Support (전체 면담)</h3>
      ${supsHtml}
    </div>
    <div class="modal-section">
      <h3>🗓️ 다뤄진 면담</h3>
      ${meetingsHtml}
    </div>
  `;
  if (!READONLY) {
    const delBtn = document.getElementById("modalDeleteBtn");
    if (delBtn) delBtn.addEventListener("click", () => {
      if (!confirm(`프로젝트 "${p.name}" 를 삭제할까요? 관련 Learning·Support 도 함께 삭제됩니다.`)) return;
      const arr = getProjects(doc);
      const i = arr.findIndex(x => x.id === pid);
      if (i >= 0) arr.splice(i, 1);
      // 면담에서 reference 제거
      notes.forEach(m => {
        if (m.topic_projects) m.topic_projects = m.topic_projects.filter(x => x !== pid);
        if (m.support) m.support.forEach(s => { if (s.project_id === pid) s.project_id = null; });
      });
      markDirty();
      closeModal();
      renderBoard(doc); renderMeeting(doc);
    });
  }
  $m.hidden = false;
}

// ───── Section D: Follow-up ─────
function renderFollowup(doc) {
  const notes = getNotes(doc);
  const $sec = document.getElementById(`followup-${doc}`);
  const idx = currentIdx[doc] ?? (notes.length-1);
  const prev = idx > 0 ? notes[idx-1] : null;
  const items = [];
  if (prev) {
    (prev.support||[]).forEach(s => {
      if (!s.reviewed) items.push({s, meeting: prev});
    });
  }
  $sec.innerHTML = `
    <h2>↩️ 지난 면담 Follow-up <span class="badge">직전 1회 미해결</span></h2>
    ${items.length === 0
      ? `<div class="meta" style="padding:8px;">지난 면담 메모가 없거나 모두 완료됨.</div>`
      : `<ul class="item-list">${items.map(({s, meeting}) => {
          const p = s.project_id ? getProject(doc, s.project_id) : null;
          return `<li>
            ${READONLY
              ? `${s.reviewed?"✅":"⬜"}`
              : `<input type="checkbox" data-act="fu-rev" data-mid="${meeting.id}" data-sid="${s.id}">`}
            <span class="meta" style="min-width:90px;">${meeting.date} · ${s.type||"-"}</span>
            ${p ? `<span class="pill" style="background:var(--panel3); color:var(--accent);">📌 ${escapeHtml(p.name||"")}</span>` : ''}
            <span style="flex:1;">${escapeHtml(s.need || "(내용 없음)")}</span>
          </li>`;
        }).join("")}</ul>`}
  `;
  if (!READONLY) {
    $sec.querySelectorAll("[data-act=fu-rev]").forEach(el => {
      el.addEventListener("change", () => {
        const mid = el.dataset.mid;
        const sid = el.dataset.sid;
        const note = notes.find(n => n.id === mid);
        if (note) {
          const sup = (note.support||[]).find(s => s.id === sid);
          if (sup) sup.reviewed = el.checked;
        }
        markDirty(); renderFollowup(doc);
      });
    });
  }
}

// ───── Section E: 과거 면담 기록 ─────
function renderHistory(doc) {
  const notes = getNotes(doc);
  const idx = currentIdx[doc] ?? (notes.length-1);
  const past = notes.slice(0, idx).reverse();
  const $sec = document.getElementById(`history-${doc}`);
  $sec.innerHTML = `
    <h2>📚 과거 면담 기록 <span class="badge">${past.length}회</span></h2>
    ${past.length === 0
      ? `<div class="meta">아직 과거 면담 기록 없음.</div>`
      : past.map(n => {
          const topics = (n.topic_projects||[]).map(pid => {
            const p = getProject(doc, pid);
            return p ? `<span class="topic-tag">${escapeHtml(p.name)}</span>` : '';
          }).join("");
          const supList = (n.support||[]).map(s => {
            const p = s.project_id ? getProject(doc, s.project_id) : null;
            return `&nbsp;&nbsp;[${s.reviewed?"✅":"⬜"} ${s.type}] ${p?`<i style="color:var(--accent);">📌${escapeHtml(p.name||"")}</i> · `:""}${escapeHtml(s.need||"")}`;
          }).join("<br>") || "(없음)";
          return `<details>
            <summary>
              <strong>${n.date}</strong> ${n.done?"✅":"📝"} ${n.mood||""}
              <span class="topic-tags">${topics}</span>
              &nbsp;<span class="meta">(work ${(n.work||"").length}자 · career ${(n.career||"").length}자 · support ${(n.support||[]).length}건)</span>
            </summary>
            <div class="body">
              <span class="heading">💼 Work</span>
              <p>${escapeHtml(n.work||"(없음)")}</p>
              <span class="heading">🌱 Career</span>
              <p>${escapeHtml(n.career||"(없음)")}</p>
              <span class="heading">🤝 Support</span>
              <p>${supList}</p>
            </div>
          </details>`;
        }).join("")}
  `;
}
"""


# ─────────────────────────────────────────────────────────
# PAGE_TEMPLATE — 한의원 PC 전용 편집 화면
# ─────────────────────────────────────────────────────────
PAGE_TEMPLATE = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>부원장 1:1 면담 대시보드</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>__COMMON_CSS__</style>
</head>
<body>

<header>
  <h1>📋 부원장 1:1 면담 대시보드</h1>
  <span class="meta">__GEN_TIME__ 기준</span>
  <span id="saveStatus" class="save-status">대기</span>
</header>

<div class="tabs" id="tabs"></div>
<main id="main"></main>

<script>
const READONLY = __READONLY__;
__RENDER_JS__
boot({
  metrics: __METRICS__,
  state: __STATE__,
  vice_doctors: __VICE_DOCTORS__,
  doc_colors: __DOC_COLORS__,
});
</script>
</body>
</html>
""".replace("__COMMON_CSS__", COMMON_CSS).replace("__RENDER_JS__", RENDER_JS)


# ─────────────────────────────────────────────────────────
# PUBLIC_TEMPLATE — 잠금 화면 + 비번 → 복호화 → 동일 렌더
# ─────────────────────────────────────────────────────────
LOCK_CSS = r"""
#lock { position:fixed; inset:0; display:flex; flex-direction:column;
        align-items:center; justify-content:center; background:var(--bg); z-index:100; }
#lock h1 { font-size:24px; margin:0 0 6px; }
#lock .sub { color:var(--muted); margin-bottom:24px; font-size:14px; }
#lock form { display:flex; gap:8px; }
#lock input { background:var(--panel); color:var(--text);
              border:1px solid var(--border); border-radius:6px;
              padding:10px 14px; font-size:15px; min-width:240px; }
#lock input:focus { outline:1px solid var(--accent); border-color:var(--accent); }
#lock button { background:var(--accent); color:#0f172a; border:none;
                padding:10px 20px; border-radius:6px; font-weight:700;
                cursor:pointer; font-size:15px; }
#lock .err { color:var(--bad); margin-top:14px; min-height:18px; font-size:13px; }
#lock .hint { color:var(--muted); font-size:12px; margin-top:24px; max-width:380px; text-align:center; }
"""

PUBLIC_TEMPLATE = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>부원장 1:1 면담</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>__COMMON_CSS____LOCK_CSS__</style>
</head>
<body>

<div id="lock">
  <h1>🔒 1:1 면담</h1>
  <div class="sub">비밀번호를 입력하세요</div>
  <form id="lockForm" onsubmit="return false;">
    <input type="password" id="pw" autocomplete="current-password" placeholder="비밀번호" autofocus>
    <button id="unlockBtn">열기</button>
  </form>
  <div class="err" id="lockErr"></div>
  <div class="hint">이 페이지는 부원장 1:1 면담 기록입니다.<br>환자·외부인 열람 금지.</div>
</div>

<div id="app" style="display:none;">
  <header>
    <h1>📋 부원장 1:1 면담 (읽기 전용)</h1>
    <span class="meta" id="genTime"></span>
    <span class="ro-badge">읽기 전용 · 편집은 한의원 PC에서</span>
  </header>
  <div class="tabs" id="tabs"></div>
  <main id="main"></main>
</div>

<script>
const READONLY = true;
__RENDER_JS__

const ENC_URL = "1on1.enc.json";
let ENC_BLOB = null;
const $lock = document.getElementById("lock");
const $err  = document.getElementById("lockErr");
const $pw   = document.getElementById("pw");
const $app  = document.getElementById("app");

document.getElementById("unlockBtn").addEventListener("click", unlock);
$pw.addEventListener("keydown", e => { if (e.key === "Enter") unlock(); });

async function fetchBlob() {
  if (ENC_BLOB) return ENC_BLOB;
  const res = await fetch(ENC_URL + "?_=" + Date.now(), {cache:"no-store"});
  if (!res.ok) throw new Error(`enc 다운로드 실패: ${res.status}`);
  ENC_BLOB = await res.json();
  return ENC_BLOB;
}
async function deriveKey(pw, salt, iter) {
  const enc = new TextEncoder();
  const km = await crypto.subtle.importKey("raw", enc.encode(pw), "PBKDF2", false, ["deriveKey"]);
  return crypto.subtle.deriveKey(
    { name:"PBKDF2", salt, iterations:iter, hash:"SHA-256" },
    km, { name:"AES-GCM", length:256 }, false, ["decrypt"]);
}
function b64(s) { return Uint8Array.from(atob(s), c => c.charCodeAt(0)); }

async function unlock() {
  $err.textContent = "";
  const pw = $pw.value;
  if (!pw) { $err.textContent = "비밀번호를 입력하세요."; return; }
  try {
    const blob = await fetchBlob();
    const key  = await deriveKey(pw, b64(blob.salt), blob.iterations);
    const ptBuf = await crypto.subtle.decrypt({name:"AES-GCM", iv: b64(blob.iv)}, key, b64(blob.data));
    const payload = JSON.parse(new TextDecoder().decode(ptBuf));
    document.getElementById("genTime").textContent = blob.generated + " 생성";
    $lock.style.display = "none";
    $app.style.display  = "block";
    boot(payload);
  } catch (e) {
    console.warn(e);
    $err.textContent = "비밀번호가 틀렸거나 데이터를 가져오지 못했습니다.";
    $pw.select();
  }
}
</script>
</body>
</html>
""".replace("__COMMON_CSS__", COMMON_CSS).replace("__LOCK_CSS__", LOCK_CSS).replace("__RENDER_JS__", RENDER_JS)
