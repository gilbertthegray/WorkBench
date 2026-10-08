"""
WorkBench - Workflow management
Run:  streamlit run app.py   (requires streamlit >= 1.37)
Needs database.py (and optionally email_service.py) in the same folder.
Put theme settings in .streamlit/config.toml (provided) for a fully light UI.
"""
import streamlit as st
from datetime import datetime, timedelta
from html import escape as esc
import uuid

from database import (
    init_db, needs_seed, get_users, upsert_user, get_groups, upsert_group,
    get_workflows, upsert_workflow, get_tasks, upsert_task, add_history,
    get_notifications, add_notification, clear_notifications,
    increment_task_counter, get_settings, save_settings,
)

try:
    from email_service import (notify_task_assigned, notify_task_advanced,
        notify_task_blocked, notify_task_completed, email_is_configured, test_connection)
except ImportError:
    def _no(*a, **k): return False, "email_service not found"
    notify_task_assigned = notify_task_advanced = notify_task_blocked = notify_task_completed = _no
    def email_is_configured(): return False
    def test_connection(): return False, "email_service not found"

st.set_page_config(page_title="WorkBench", layout="wide", initial_sidebar_state="expanded")

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
:root{--bg:#f5f6f8;--surface:#fff;--line:#e4e7ec;--line2:#eef0f3;--text:#14181f;--muted:#667085;
--faint:#98a2b3;--accent:#2b50d6;--accent-soft:#eaefff}
html,body,[data-testid="stAppViewContainer"],.stApp{background:var(--bg)!important;color:var(--text)!important;font-family:'Inter',sans-serif!important}
#MainMenu,footer,[data-testid="stToolbar"],[data-testid="stHeader"]{visibility:hidden;height:0}
[data-testid="stSidebarCollapseButton"],[data-testid="collapsedControl"]{display:none!important}
.block-container{padding:2rem 2.5rem 3rem!important;max-width:1280px!important}
[data-testid="stSidebar"]{background:var(--surface)!important;border-right:1px solid var(--line)!important}
[data-testid="stSidebar"] .block-container{padding:1.5rem 1rem!important}
h1,h2,h3,h4{font-family:'Inter',sans-serif!important;color:var(--text)!important;letter-spacing:-.01em}
hr{border-color:var(--line)!important;margin:1rem 0!important}
.brand{font-size:18px;font-weight:700;letter-spacing:-.02em;padding:2px 0 18px}
.brand span{color:var(--accent)}
.page-title{font-size:26px;font-weight:650;letter-spacing:-.02em;margin-bottom:2px}
.page-sub{font-size:14px;color:var(--muted);margin-bottom:24px}
.sec{font-size:14px;font-weight:600;margin:4px 0 12px;color:var(--text)}
.card{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin-bottom:10px}
.card.hover:hover{border-color:#c5cdf5}
.stat{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:16px 18px}
.stat .l{font-size:13px;color:var(--muted);margin-bottom:6px}
.stat .v{font-size:28px;font-weight:650;letter-spacing:-.02em}
.stat.alert .v{color:#c0392b}
.row{display:flex;align-items:center;gap:12px}
.grow{flex:1;min-width:0}
.t-title{font-size:14px;font-weight:550}
.t-meta{font-size:12.5px;color:var(--muted);margin-top:3px}
.id{font-size:12px;color:var(--faint);font-variant-numeric:tabular-nums}
.badge{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:550;white-space:nowrap}
.b-new{background:#eaefff;color:#2b50d6}.b-prog{background:#fff4e0;color:#a35d00}
.b-done{background:#e5f6ec;color:#1b7a43}.b-block{background:#fdeaea;color:#b42318}
.b-gray{background:#eef0f3;color:#475467}.b-admin{background:#f1ecff;color:#6941c6}
.dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.p-critical{background:#d92d20}.p-high{background:#f79009}.p-medium{background:#2b50d6}.p-low{background:#98a2b3}
.bar{background:var(--line2);border-radius:4px;height:5px;overflow:hidden;margin-top:8px}
.bar>div{height:100%;background:var(--accent);border-radius:4px}
.sla-ok{color:#1b7a43;font-size:12px}.sla-warning{color:#a35d00;font-size:12px}.sla-breach{color:#b42318;font-size:12px;font-weight:600}
.notif{background:var(--surface);border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:8px;padding:11px 14px;margin-bottom:8px;font-size:13.5px}
.notif.warn{border-left-color:#f79009}.notif.error{border-left-color:#d92d20}.notif.ok{border-left-color:#12b76a}
.notif .tm{font-size:12px;color:var(--faint);margin-top:3px}
.tl{display:flex;gap:12px;margin-bottom:12px}.tl i{width:8px;height:8px;border-radius:50%;background:#c5cdf5;margin-top:6px;flex-shrink:0}
.tl .tx{font-size:13.5px}.tl .tm{font-size:12px;color:var(--faint)}
.rail{display:flex;align-items:flex-start;margin:14px 0 18px}
.rs{display:flex;flex-direction:column;align-items:center;width:84px}
.rb{width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:600}
.rb.done{background:#12b76a;color:#fff}.rb.act{background:var(--accent);color:#fff;box-shadow:0 0 0 4px var(--accent-soft)}.rb.pend{background:var(--line2);color:var(--faint)}
.rl{font-size:12px;color:var(--muted);margin-top:6px;text-align:center}
.rc{height:2px;flex:1;background:var(--line);margin-top:12px}.rc.done{background:#12b76a}
.lock{background:#fffaeb;border:1px solid #fedf89;border-radius:8px;padding:9px 12px;font-size:13px;color:#93370d}
.chip{display:inline-block;background:var(--line2);border-radius:6px;padding:2px 8px;font-size:12px;color:#475467;margin:2px 4px 2px 0}
.avatar{width:32px;height:32px;border-radius:50%;background:var(--accent-soft);color:var(--accent);display:inline-flex;align-items:center;justify-content:center;font-size:12px;font-weight:650;flex-shrink:0}
.kv{display:flex;padding:8px 0;border-bottom:1px solid var(--line2);font-size:13.5px}.kv:last-child{border:none}
.kv .k{width:38%;color:var(--muted)}.kv .v{flex:1}
.th{font-size:12px;font-weight:600;color:var(--muted)}
.empty{padding:44px 0;text-align:center;color:var(--muted);font-size:14px}
.stButton>button{border-radius:8px!important;font-weight:550!important;font-size:13.5px!important;border:1px solid var(--line)!important;background:#fff!important;color:var(--text)!important}
.stButton>button:hover{border-color:var(--accent)!important;color:var(--accent)!important}
.stButton>button[kind="primary"]{background:var(--accent)!important;border-color:var(--accent)!important;color:#fff!important}
.stButton>button[kind="primary"]:hover{background:#2243b8!important;color:#fff!important}
[data-baseweb="input"],[data-baseweb="select"]>div,[data-baseweb="textarea"]{background:#fff!important;border-radius:8px!important}
.stTabs [data-baseweb="tab-list"]{gap:6px;border-bottom:1px solid var(--line)}
.stTabs [data-baseweb="tab"]{font-weight:550;color:var(--muted)}
.stTabs [aria-selected="true"]{color:var(--accent)!important}
[data-testid="stExpander"]{background:#fff;border:1px solid var(--line)!important;border-radius:10px!important}
[data-testid="stSidebar"] [role="radiogroup"]{gap:2px}
[data-testid="stSidebar"] [role="radiogroup"] label{padding:7px 10px;border-radius:8px;width:100%}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked){background:var(--accent-soft);color:var(--accent);font-weight:600}
[data-testid="stSidebar"] [role="radiogroup"] label>div:first-child{display:none}
</style>""", unsafe_allow_html=True)

# ───────────────────────── seed data ─────────────────────────
def _now(): return datetime.now().strftime("%Y-%m-%d %H:%M")

def _f(id, label, type="text", ph="", opts=None, req=True):
    return {"id": id, "label": label, "type": type, "placeholder": ph, "options": opts or [], "required": req}

def _wf(id, name, desc, sla, stages, fields):
    return {"id": id, "name": name, "description": desc, "icon": "", "sla_hours": sla, "active": True,
            "stages": [{"name": n, "group_id": g, "description": d} for n, g, d in stages], "custom_fields": fields}

def _default_groups():
    rows = [("grp-eng","Engineering","Software development and infrastructure","#3b82f6"),
            ("grp-fin","Finance & Accounting","Expense review, budget approvals, audit","#10b981"),
            ("grp-legal","Legal & Compliance","Contract review, regulatory compliance","#8b5cf6"),
            ("grp-ops","Operations","Day-to-day operational tasks","#f59e0b"),
            ("grp-hr","Human Resources","Onboarding, offboarding, employee relations","#ec4899"),
            ("grp-exec","Executive","Senior leadership approvals","#ef4444")]
    return [{"id":i,"name":n,"description":d,"color":c,"members":[],"created":_now()} for i,n,d,c in rows]

def _default_workflows():
    return [
        _wf("wf-contract","Contract Approval","Multi-stage contract review and approval",72,
            [("Draft Review","grp-legal","Legal reviews draft"),("Financial Sign-off","grp-fin","Finance approves terms"),("Executive Approval","grp-exec","Executive signs off")],
            [_f("counterparty","Counterparty / Company",ph="e.g. Acme Corp"),_f("contract_value","Contract Value (USD)","number"),
             _f("contract_type","Contract Type","select",opts=["NDA","MSA","SOW","SLA","Licensing","Other"]),
             _f("effective_date","Effective Date","date"),_f("legal_contact","Legal Contact Email","email",req=False),
             _f("notes","Special Terms / Notes","textarea",req=False)]),
        _wf("wf-expense","Expense Claim","Employee expense reimbursement",48,
            [("Manager Review","grp-ops","Manager approves"),("Finance Audit","grp-fin","Finance verifies"),("Payment Release","grp-fin","Finance pays")],
            [_f("amount","Claim Amount (USD)","number"),
             _f("category","Expense Category","select",opts=["Travel","Meals","Software","Hardware","Training","Marketing","Other"]),
             _f("expense_date","Date of Expense","date"),_f("vendor","Vendor / Merchant",ph="e.g. Delta Airlines"),
             _f("cost_centre","Cost Centre / Project Code",req=False),_f("justification","Business Justification","textarea")]),
        _wf("wf-onboard","Employee Onboarding","New hire setup and orientation",120,
            [("HR Intake","grp-hr","HR collects documents"),("IT Provisioning","grp-eng","Engineering sets up accounts"),("Manager Induction","grp-ops","Manager completes orientation")],
            [_f("employee_name","New Employee Full Name"),_f("employee_email","Employee Email","email"),_f("start_date","Start Date","date"),
             _f("job_title","Job Title"),_f("manager","Reporting Manager"),
             _f("equipment","Equipment Needed","select",opts=["MacBook Pro","MacBook Air","Dell Laptop","Windows Desktop","No Equipment"]),
             _f("access_level","System Access Level","select",opts=["Read Only","Standard","Elevated","Admin"])]),
        _wf("wf-change","Change Request","System or process change management",96,
            [("Impact Assessment","grp-eng","Engineering assesses risk"),("Ops Approval","grp-ops","Operations approves"),("Executive Sign-off","grp-exec","Executive authorises")],
            [_f("system","System / Service Affected"),_f("change_type","Change Type","select",opts=["Standard","Emergency","Major Release","Configuration","Rollback"]),
             _f("risk_level","Risk Level","select",opts=["Low","Medium","High","Critical"]),_f("planned_date","Planned Implementation Date","date"),
             _f("downtime","Expected Downtime (minutes)","number"),_f("rollback_plan","Rollback Plan","textarea")]),
        _wf("wf-incident","Incident Report","Operational incident triage and resolution",24,
            [("Triage","grp-eng","Engineering triages"),("Resolution","grp-eng","Engineering resolves"),("Post-mortem","grp-ops","Ops documents learnings")],
            [_f("severity","Severity Level","select",opts=["SEV-1 (Critical)","SEV-2 (Major)","SEV-3 (Minor)","SEV-4 (Low)"]),
             _f("affected_system","Affected System / Service"),
             _f("impact","User / Business Impact","select",opts=["All users down","Partial outage","Degraded performance","Data issue","No user impact"]),
             _f("symptoms","Symptoms / Error Description","textarea"),_f("incident_lead","Incident Lead")]),
        _wf("wf-vendor","Vendor Approval","New vendor onboarding and approval",120,
            [("Vendor Vetting","grp-legal","Legal verifies credentials"),("Budget Review","grp-fin","Finance approves spend"),("Ops Sign-off","grp-ops","Operations finalises")],
            [_f("vendor_name","Vendor Company Name"),_f("vendor_contact","Vendor Contact Email","email"),
             _f("service_type","Service / Product Type","select",opts=["Software / SaaS","Professional Services","Hardware","Cloud Infrastructure","Consulting","Other"]),
             _f("annual_value","Estimated Annual Value (USD)","number"),
             _f("data_access","Requires Access to Company Data?","select",opts=["Yes - PII","Yes - Financial","Yes - Internal only","No data access"]),
             _f("business_case","Business Case / Justification","textarea")]),
    ]

# ───────────────────────── init ─────────────────────────
init_db()
if needs_seed():
    upsert_user({"id":"user-admin","name":"Admin","email":"admin@flowdesk.io","role":"admin","groups":[],"active":True,"created":_now()})
    for g in _default_groups(): upsert_group(g)
    for w in _default_workflows(): upsert_workflow(w)

ss = st.session_state
if "db_loaded" not in ss:
    ss.users, ss.groups, ss.workflows = get_users(), get_groups(), get_workflows()
    ss.tasks, ss.notifications, ss.settings = get_tasks(), get_notifications(), get_settings()
    ss.db_loaded, ss.current_user_id, ss.modal_step, ss.modal_wf_id = True, "user-admin", 1, None

# ───────────────────────── helpers ─────────────────────────
def get_user(uid):  return next((u for u in ss.users if u["id"] == uid), None)
def get_group(gid): return next((g for g in ss.groups if g["id"] == gid), None)
def get_wf(wid):    return next((w for w in ss.workflows if w["id"] == wid), None)
def current_user(): return get_user(ss.current_user_id)
def is_admin():     u = current_user(); return bool(u and u["role"] == "admin")
def group_name(gid):
    g = get_group(gid); return g["name"] if g else gid
def group_email(gid):
    g = get_group(gid); return g.get("email", "") if g else ""
def initials(n):
    p = n.strip().split(); return (p[0][0] + (p[-1][0] if len(p) > 1 else "")).upper()
def refresh(*keys):
    loaders = {"users":get_users,"groups":get_groups,"workflows":get_workflows,"tasks":get_tasks,"notifications":get_notifications,"settings":get_settings}
    for k in keys: ss[k] = loaders[k]()
def notify(kind, msg):
    add_notification(kind, msg); refresh("notifications")

def can_advance(t):
    if is_admin(): return True
    wf = get_wf(t["workflow_id"])
    if not wf or t["stage_index"] >= len(wf["stages"]): return False
    return wf["stages"][t["stage_index"]]["group_id"] in current_user()["groups"]

def cur_stage(t):
    wf = get_wf(t["workflow_id"])
    if wf and t["stage_index"] < len(wf["stages"]):
        s = wf["stages"][t["stage_index"]]; return s["name"], group_name(s["group_id"])
    return ("Complete" if t["status"] == "Done" else ""), ""

def advance_task(tid):
    t = next((x for x in ss.tasks if x["id"] == tid), None)
    wf = get_wf(t["workflow_id"]) if t else None
    if not t or not wf or t["status"] == "Done": return
    by = current_user()["name"] if current_user() else "System"
    si = t["stage_index"]; stages = wf["stages"]
    add_history(tid, f"Stage '{stages[si]['name']}' completed", by)
    ni = si + 1
    if ni >= len(stages):
        t.update({"status":"Done","stage_index":ni,"progress":100,"closed_at":_now()}); upsert_task(t)
        add_history(tid, "Workflow completed and closed", "System")
        notify("ok", f"{tid} completed and closed.")
        g = stages[si]["group_id"]
        notify_task_completed(group_email=group_email(g), group_name=group_name(g), task_id=tid,
            task_title=t["title"], workflow=wf["name"], priority=t["priority"], completed_by=by)
    else:
        ns = stages[ni]
        t.update({"stage_index":ni,"status":"In Progress","progress":int(ni / len(stages) * 100)}); upsert_task(t)
        add_history(tid, f"Moved to '{ns['name']}', awaiting {group_name(ns['group_id'])}", "System")
        notify("info", f"{tid} advanced to '{ns['name']}', needs {group_name(ns['group_id'])}.")
        notify_task_advanced(group_email=group_email(ns["group_id"]), group_name=group_name(ns["group_id"]),
            task_id=tid, task_title=t["title"], workflow=wf["name"], stage=ns["name"],
            priority=t["priority"], due=t.get("due", ""), advanced_by=by)
    refresh("tasks")
    st.toast(f"{tid} updated")

STATUS_CSS = {"New":"b-new","In Progress":"b-prog","In Review":"b-new","Done":"b-done","Blocked":"b-block"}
def badge(text, cls): return f'<span class="badge {cls}">{esc(str(text))}</span>'
def sbadge(s): return badge(s, STATUS_CSS.get(s, "b-gray"))
def pdot(p): return f'<span class="dot p-{esc(p)}" title="{esc(p)} priority"></span>'
def pbar(p): return f'<div class="bar"><div style="width:{int(p)}%"></div></div>'
def title(t, sub): st.markdown(f'<div class="page-title">{t}</div><div class="page-sub">{sub}</div>', unsafe_allow_html=True)
def empty(msg): st.markdown(f'<div class="empty">{msg}</div>', unsafe_allow_html=True)
def section(t): st.markdown(f'<div class="sec">{t}</div>', unsafe_allow_html=True)

def sla_lbl(t):
    if t["status"] == "Done": return '<span class="sla-ok">Closed</span>'
    try:
        h = (datetime.strptime(t.get("due", ""), "%Y-%m-%d %H:%M") - datetime.now()).total_seconds() / 3600
        if h < 0: return '<span class="sla-breach">Overdue</span>'
        if h < ss.settings.get("sla_warn_hours", 4): return f'<span class="sla-warning">{int(h)}h left</span>'
    except Exception: pass
    return '<span class="sla-ok">On track</span>'

def stage_rail(t):
    wf = get_wf(t["workflow_id"])
    if not wf: return ""
    h = '<div class="rail">'
    for i, s in enumerate(wf["stages"]):
        if i: h += f'<div class="rc {"done" if i <= t["stage_index"] else ""}"></div>'
        if i < t["stage_index"] or t["status"] == "Done": c, l = "done", "✓"
        elif i == t["stage_index"]: c, l = "act", i + 1
        else: c, l = "pend", i + 1
        h += f'<div class="rs"><div class="rb {c}">{l}</div><div class="rl">{esc(s["name"])}</div></div>'
    return h + "</div>"

def stage_list(wf):
    for i, s in enumerate(wf["stages"], 1):
        st.markdown(f'<div class="card" style="padding:10px 14px;margin-bottom:6px"><div class="row">'
                    f'<span class="id">{i}</span><div class="grow t-title" style="font-weight:500">{esc(s["name"])}</div>'
                    f'<span class="t-meta" style="margin:0">{esc(group_name(s["group_id"]))}</span></div></div>', unsafe_allow_html=True)

def render_field(f, prefix):
    k = f"{prefix}_{f['id']}"; lbl = f["label"] + (" *" if f.get("required") else ""); ph = f.get("placeholder", "")
    t = f["type"]
    if t == "textarea": return st.text_area(lbl, placeholder=ph, key=k, height=80)
    if t == "select":   return st.selectbox(lbl, f["options"], key=k) if f.get("options") else st.text_input(lbl, key=k)
    if t == "date":     return str(st.date_input(lbl, key=k))
    if t == "number":   return str(st.number_input(lbl, min_value=0.0, step=1.0, key=k))
    return st.text_input(lbl, placeholder=ph, key=k)

def reset_modal():
    ss.modal_step, ss.modal_wf_id = 1, None; ss.pop("m_data", None)

# ───────────────────────── dialogs ─────────────────────────
@st.dialog("New workflow", width="large")
def new_workflow_modal():
    active = [w for w in ss.workflows if w["active"]]
    if not active:
        st.warning("No active workflow templates. An admin needs to create one first."); return
    step = ss.modal_step
    st.caption(f"Step {step} of 3 · " + ["Choose a type", "Fill in details", "Review and create"][step - 1])
    st.progress(step / 3)

    if step == 1:
        ids = [w["id"] for w in active]
        idx = ids.index(ss.modal_wf_id) if ss.modal_wf_id in ids else 0
        wf = active[ids.index(st.selectbox("Workflow type", ids, index=idx, format_func=lambda i: get_wf(i)["name"]))]
        st.markdown(f'<div class="card"><div class="t-title">{esc(wf["name"])}</div>'
                    f'<div class="t-meta">{esc(wf.get("description",""))}</div>'
                    f'<div class="t-meta">{wf["sla_hours"]}h SLA · {len(wf["stages"])} stages · {len(wf.get("custom_fields",[]))} fields</div></div>',
                    unsafe_allow_html=True)
        section("Approval stages"); stage_list(wf)
        c1, _, c2 = st.columns([1, 3, 1])
        if c1.button("Cancel", key="s1c"): reset_modal(); st.rerun()
        if c2.button("Next", key="s1n", type="primary"):
            ss.modal_wf_id, ss.modal_step = wf["id"], 2; st.rerun(scope="fragment")

    elif step == 2:
        wf = get_wf(ss.modal_wf_id)
        section(esc(wf["name"]))
        a, b = st.columns(2)
        ttl = a.text_input("Title *", placeholder="Short, descriptive title", key="m_title")
        prio = b.selectbox("Priority", ["medium", "high", "critical", "low"], key="m_priority")
        a, b = st.columns(2)
        dd = a.date_input("Due date *", value=datetime.now() + timedelta(days=3), key="m_due_date")
        dtm = b.text_input("Due time (HH:MM)", value="17:00", key="m_due_time")
        desc = st.text_area("Description", placeholder="Optional context", height=70, key="m_desc")
        cfs, vals = wf.get("custom_fields", []), {}
        if cfs:
            st.divider(); section("Required information")
            i = 0
            while i < len(cfs):
                f = cfs[i]
                if f["type"] != "textarea" and i + 1 < len(cfs) and cfs[i + 1]["type"] != "textarea":
                    c1, c2 = st.columns(2)
                    with c1: vals[f["id"]] = render_field(f, "cf2")
                    with c2: vals[cfs[i+1]["id"]] = render_field(cfs[i+1], "cf2")
                    i += 2
                else:
                    vals[f["id"]] = render_field(f, "cf2"); i += 1
        b1, _, b2, b3 = st.columns([1, 2, 1, 1])
        if b1.button("Back", key="s2b"): ss.modal_step = 1; st.rerun(scope="fragment")
        if b2.button("Cancel", key="s2c"): reset_modal(); st.rerun()
        if b3.button("Review", key="s2n", type="primary"):
            errs = []
            if not ttl.strip(): errs.append("Title is required.")
            try: datetime.strptime(dtm, "%H:%M")
            except ValueError: errs.append("Due time must look like 17:00.")
            for f in cfs:
                v = str(vals.get(f["id"], "")).strip()
                if f.get("required") and (not v or v in ("0.0", "0")): errs.append(f"'{f['label']}' is required.")
            if errs:
                for e in errs: st.error(e)
            else:
                ss.m_data = {"title": ttl, "priority": prio, "due": f"{dd} {dtm}", "description": desc, "custom": vals}
                ss.modal_step = 3; st.rerun(scope="fragment")

    else:
        wf, d, cu = get_wf(ss.modal_wf_id), ss.get("m_data", {}), current_user()
        cust = d.get("custom", {})
        rows = [("Workflow", wf["name"]), ("Priority", d.get("priority", "").capitalize()), ("Due", d.get("due", ""))]
        if d.get("description"): rows.append(("Description", d["description"]))
        rows += [(f["label"], cust[f["id"]]) for f in wf.get("custom_fields", []) if str(cust.get(f["id"], "")).strip()]
        st.markdown(f'<div class="card"><div class="t-title" style="font-size:16px;margin-bottom:8px">{esc(d.get("title",""))}</div>'
                    + "".join(f'<div class="kv"><div class="k">{esc(k)}</div><div class="v">{esc(str(v))}</div></div>' for k, v in rows)
                    + '</div>', unsafe_allow_html=True)
        section("Stages"); stage_list(wf)
        b1, _, b2, b3 = st.columns([1, 2, 1, 1])
        if b1.button("Back", key="s3b"): ss.modal_step = 2; st.rerun(scope="fragment")
        if b2.button("Cancel", key="s3c"): reset_modal(); st.rerun()
        if b3.button("Create", key="s3k", type="primary"):
            lines = [f"{f['label']}: {cust[f['id']]}" for f in wf.get("custom_fields", []) if str(cust.get(f["id"], "")).strip()]
            full = (d.get("description", "") + ("\n\n" if d.get("description") and lines else "") + "\n".join(lines)).strip()
            nid = f"WF-{increment_task_counter()}"; by = cu["name"] if cu else "System"; s0 = wf["stages"][0]
            upsert_task({"id":nid,"title":d["title"],"description":full,"workflow_id":wf["id"],"status":"New","priority":d["priority"],
                         "stage_index":0,"progress":0,"created":_now(),"created_by":by,"due":d["due"],"closed_at":None,"custom_fields":cust})
            add_history(nid, "Workflow instance created", by)
            add_history(nid, f"Stage '{s0['name']}' started, awaiting {group_name(s0['group_id'])}", "System")
            notify("info", f"{nid} '{d['title']}' created via {wf['name']}.")
            notify_task_assigned(group_email=group_email(s0["group_id"]), group_name=group_name(s0["group_id"]), task_id=nid,
                task_title=d["title"], workflow=wf["name"], stage=s0["name"], priority=d["priority"], due=d["due"], created_by=by)
            refresh("tasks"); reset_modal(); st.toast(f"{nid} created"); st.rerun()

@st.dialog("Workflow template", width="large")
def workflow_template_modal(wf_id=None):
    edit = wf_id is not None
    wf = get_wf(wf_id) if edit else None
    groups = ss.groups; gnames = [g["name"] for g in groups]
    tab_i, tab_s, tab_f = st.tabs(["Basics", "Stages", "Custom fields"])
    with tab_i:
        c1, c2 = st.columns(2)
        name = c1.text_input("Template name *", value=wf["name"] if wf else "")
        sla = c2.number_input("SLA (hours)", min_value=1, value=wf["sla_hours"] if wf else 72)
        desc = st.text_area("Description", value=wf.get("description", "") if wf else "", height=80)
        active = st.checkbox("Active", value=wf.get("active", True) if wf else True)
    with tab_s:
        st.caption("Stages run in order. Only members of the assigned group can advance a stage.")
        ex_s = wf["stages"] if wf else []
        n = int(st.number_input("Number of stages", 1, 8, max(len(ex_s), 1), key="ns_wf"))
        stages = []
        for i in range(n):
            ex = ex_s[i] if i < len(ex_s) else {}
            c1, c2 = st.columns(2)
            sn = c1.text_input(f"Stage {i+1} name *", value=ex.get("name", ""), key=f"sn_{wf_id}_{i}")
            cg = group_name(ex["group_id"]) if ex.get("group_id") else ""
            sg = c2.selectbox("Assigned group *", gnames, index=gnames.index(cg) if cg in gnames else 0, key=f"sg_{wf_id}_{i}")
            sd = st.text_input("Description", value=ex.get("description", ""), key=f"sd_{wf_id}_{i}")
            stages.append({"name": sn, "group_id": next(g["id"] for g in groups if g["name"] == sg), "description": sd})
    with tab_f:
        st.caption("Custom fields appear on the creation form.")
        ex_f = wf.get("custom_fields", []) if wf else []
        n = int(st.number_input("Number of fields", 0, 15, len(ex_f), key="nf_wf"))
        types = ["text", "number", "email", "date", "select", "textarea"]; fields = []
        for i in range(n):
            ex = ex_f[i] if i < len(ex_f) else {}
            with st.expander(f"Field {i+1}: {ex.get('label') or 'New field'}", expanded=not ex.get("label")):
                c1, c2, c3 = st.columns([3, 2, 1])
                fl = c1.text_input("Label *", value=ex.get("label", ""), key=f"fl_{wf_id}_{i}")
                ft = c2.selectbox("Type", types, index=types.index(ex.get("type", "text")), key=f"ft_{wf_id}_{i}")
                fr = c3.checkbox("Required", value=ex.get("required", False), key=f"fr_{wf_id}_{i}")
                c1, c2 = st.columns(2)
                fp = c1.text_input("Placeholder", value=ex.get("placeholder", ""), key=f"fp_{wf_id}_{i}")
                fo = []
                if ft == "select":
                    raw = c2.text_input("Options (comma-separated)", value=", ".join(ex.get("options", [])), key=f"fo_{wf_id}_{i}")
                    fo = [o.strip() for o in raw.split(",") if o.strip()]
                fields.append({"id": ex.get("id") or f"f{i}_{uuid.uuid4().hex[:4]}", "label": fl, "type": ft,
                               "placeholder": fp, "options": fo, "required": fr})
    c1, _, c2 = st.columns([1, 3, 1])
    if c1.button("Cancel", key="tpl_cancel"): st.rerun()
    if c2.button("Save changes" if edit else "Create template", key="tpl_save", type="primary"):
        valid_s = [s for s in stages if s["name"].strip()]
        if not name.strip(): st.error("Template name is required.")
        elif not valid_s: st.error("Add at least one stage with a name.")
        else:
            upsert_workflow({"id": wf_id if edit else f"wf-{uuid.uuid4().hex[:8]}", "name": name, "description": desc,
                             "icon": "", "sla_hours": int(sla), "active": active, "stages": valid_s,
                             "custom_fields": [f for f in fields if f["label"].strip()]})
            refresh("workflows"); notify("ok", f"Template '{name}' {'updated' if edit else 'created'}."); st.rerun()

# ───────────────────────── sidebar ─────────────────────────
with st.sidebar:
    st.markdown('<div class="brand">Work<span>Bench</span></div>', unsafe_allow_html=True)
    au = [u for u in ss.users if u["active"]]
    ids = [u["id"] for u in au]
    ss.current_user_id = st.selectbox("Signed in as", ids, index=ids.index(ss.current_user_id) if ss.current_user_id in ids else 0,
                                      format_func=lambda i: get_user(i)["name"])
    cu = current_user()
    groups_txt = ", ".join(group_name(g) for g in cu["groups"]) or "No groups"
    st.markdown(f'<div class="row" style="margin:6px 0 16px"><div class="avatar">{esc(initials(cu["name"]))}</div>'
                f'<div><div class="t-meta" style="margin:0">{esc(groups_txt)}</div>'
                f'<div style="margin-top:3px">{badge(cu["role"].capitalize(), "b-admin" if cu["role"]=="admin" else "b-gray")}</div></div></div>',
                unsafe_allow_html=True)
    pages = ["Dashboard", "My tasks", "All workflows", "Analytics", "Notifications"] + (["Admin"] if is_admin() else [])
    page = st.radio("Navigate", pages, label_visibility="collapsed")
    st.divider()
    open_n = sum(1 for t in ss.tasks if t["status"] != "Done")
    st.markdown(f'<div class="t-meta">{open_n} open · {len(ss.tasks) - open_n} completed</div>', unsafe_allow_html=True)

cu, tasks = current_user(), ss.tasks

# ───────────────────────── pages ─────────────────────────
if page == "Dashboard":
    title("Dashboard", f'{datetime.now().strftime("%A, %d %B %Y")}')
    overdue = sum(1 for t in tasks if "Overdue" in sla_lbl(t))
    stats = [("Total workflows", len(tasks), ""), ("Completed", sum(t["status"] == "Done" for t in tasks), ""),
             ("In progress", sum(t["status"] == "In Progress" for t in tasks), ""), ("Blocked", sum(t["status"] == "Blocked" for t in tasks), "alert" if any(t["status"]=="Blocked" for t in tasks) else "")]
    for col, (l, v, c) in zip(st.columns(4), stats):
        col.markdown(f'<div class="stat {c}"><div class="l">{l}</div><div class="v">{v}</div></div>', unsafe_allow_html=True)
    st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)
    left, right = st.columns([2.2, 1])
    with left:
        section("Active queue")
        q = sorted([t for t in tasks if t["status"] != "Done"], key=lambda x: ["critical", "high", "medium", "low"].index(x["priority"]))
        if not q: empty("Nothing in the queue. Create a workflow from All workflows.")
        for t in q[:8]:
            wf = get_wf(t["workflow_id"]); sn, sg = cur_stage(t)
            c1, c2 = st.columns([8, 1])
            c1.markdown(f'<div class="card hover"><div class="row">{pdot(t["priority"])}<div class="grow">'
                        f'<div class="row" style="gap:8px;flex-wrap:wrap"><span class="id">{esc(t["id"])}</span>{sbadge(t["status"])}{sla_lbl(t)}</div>'
                        f'<div class="t-title" style="margin-top:4px">{esc(t["title"])}</div>'
                        f'<div class="t-meta">{esc(wf["name"] if wf else "?")} · {esc(sn)} · awaiting {esc(sg)}</div>{pbar(t["progress"])}</div></div></div>',
                        unsafe_allow_html=True)
            with c2:
                st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)
                if can_advance(t):
                    if st.button("Advance", key=f"da_{t['id']}"): advance_task(t["id"]); st.rerun()
                else: st.caption("Other team")
    with right:
        section("Recent activity")
        if not ss.notifications: empty("No activity yet.")
        for n in ss.notifications[:6]:
            cls = {"warn": "warn", "error": "error", "ok": "ok"}.get(n["type"], "")
            st.markdown(f'<div class="notif {cls}">{esc(n["msg"])}<div class="tm">{esc(n["time"])}</div></div>', unsafe_allow_html=True)
        section("By status")
        for s in ["New", "In Progress", "Blocked", "Done"]:
            c = sum(t["status"] == s for t in tasks)
            st.markdown(f'<div style="margin-bottom:10px"><div class="row" style="font-size:13px"><span class="grow">{s}</span><span>{c}</span></div>'
                        f'{pbar(c / max(len(tasks), 1) * 100)}</div>', unsafe_allow_html=True)

elif page == "My tasks":
    title("My tasks", "Tasks waiting on your groups")
    mine = set(cu["groups"])
    def needs_me(t):
        wf = get_wf(t["workflow_id"])
        return t["status"] != "Done" and wf and t["stage_index"] < len(wf["stages"]) and wf["stages"][t["stage_index"]]["group_id"] in mine
    my = [t for t in tasks if t["status"] != "Done"] if is_admin() else [t for t in tasks if needs_me(t)]

    def render_task(t, actions=True):
        wf = get_wf(t["workflow_id"]); sn, sg = cur_stage(t)
        with st.expander(f"{t['id']} · {t['title']} · {sn}"):
            st.markdown(stage_rail(t), unsafe_allow_html=True)
            rows = [("Workflow", wf["name"] if wf else "?"), ("Current stage", sn), ("Assigned group", sg or "-"),
                    ("Priority", t["priority"].capitalize()), ("Progress", f'{t["progress"]}%'),
                    ("Due", t.get("due") or "-"), ("Created", f'{t["created"]} by {t["created_by"]}')]
            st.markdown('<div class="card">' + "".join(f'<div class="kv"><div class="k">{k}</div><div class="v">{esc(str(v))}</div></div>' for k, v in rows) + '</div>', unsafe_allow_html=True)
            cf, wcf = t.get("custom_fields", {}), (wf.get("custom_fields", []) if wf else [])
            shown = [(f["label"], cf.get(f["id"])) for f in wcf if cf.get(f["id"])]
            if shown:
                section("Submission details")
                st.markdown('<div class="card">' + "".join(f'<div class="kv"><div class="k">{esc(k)}</div><div class="v">{esc(str(v))}</div></div>' for k, v in shown) + '</div>', unsafe_allow_html=True)
            section("Activity")
            for h in reversed(t.get("history", [])):
                st.markdown(f'<div class="tl"><i></i><div><div class="tx">{esc(h["action"])} <span style="color:var(--faint)">· {esc(h["by"])}</span></div><div class="tm">{esc(h["time"])}</div></div></div>', unsafe_allow_html=True)
            if actions and t["status"] != "Done":
                st.divider()
                b1, b2, b3 = st.columns(3)
                with b1:
                    if can_advance(t):
                        if st.button("Advance stage", key=f"adv_{t['id']}", type="primary"): advance_task(t["id"]); st.rerun()
                    else: st.markdown(f'<div class="lock">Waiting on {esc(sg)}</div>', unsafe_allow_html=True)
                with b2:
                    if t["status"] != "Blocked":
                        if st.button("Mark blocked", key=f"blk_{t['id']}"):
                            t["status"] = "Blocked"; upsert_task(t); add_history(t["id"], "Marked as blocked", cu["name"])
                            notify("error", f"{t['id']} marked blocked by {cu['name']}.")
                            if wf and t["stage_index"] < len(wf["stages"]):
                                bs = wf["stages"][t["stage_index"]]
                                notify_task_blocked(group_email=group_email(bs["group_id"]), group_name=group_name(bs["group_id"]), task_id=t["id"],
                                    task_title=t["title"], workflow=wf["name"], stage=bs["name"], priority=t["priority"], due=t.get("due", ""), blocked_by=cu["name"])
                            refresh("tasks"); st.rerun()
                    elif st.button("Unblock", key=f"unblk_{t['id']}"):
                        t["status"] = "In Progress"; upsert_task(t); add_history(t["id"], "Unblocked", cu["name"]); refresh("tasks"); st.rerun()
                with b3:
                    cmt = st.text_input("Comment", placeholder="Add a comment", key=f"ci_{t['id']}", label_visibility="collapsed")
                    if st.button("Post comment", key=f"cb_{t['id']}") and cmt.strip():
                        add_history(t["id"], f"Comment: {cmt}", cu["name"]); refresh("tasks"); st.rerun()

    tab_a, tab_d = st.tabs([f"Needs action ({len(my)})", "Completed"])
    with tab_a:
        if not my: empty("You're all caught up.")
        for t in my: render_task(t)
    with tab_d:
        done = [t for t in tasks if t["status"] == "Done"]
        if not done: empty("No completed tasks yet.")
        for t in done: render_task(t, False)

elif page == "All workflows":
    title("All workflows", f"{len(tasks)} instances")
    c0, c1, c2, c3 = st.columns([1.2, 2.5, 1.5, 1.5])
    if c0.button("New workflow", type="primary"): reset_modal(); new_workflow_modal()
    search = c1.text_input("Search", placeholder="Search by title or ID", label_visibility="collapsed")
    fwf = c2.selectbox("Workflow", ["All workflows"] + [w["name"] for w in ss.workflows if w["active"]], label_visibility="collapsed")
    fst = c3.selectbox("Status", ["All statuses", "New", "In Progress", "Blocked", "Done"], label_visibility="collapsed")
    rows = [t for t in tasks if search.lower() in (t["title"] + t["id"]).lower()]
    if fwf != "All workflows": rows = [t for t in rows if (get_wf(t["workflow_id"]) or {}).get("name") == fwf]
    if fst != "All statuses": rows = [t for t in rows if t["status"] == fst]
    W = [0.3, 0.8, 2.6, 1.3, 1, 1.7, 1, 0.9]
    for col, l in zip(st.columns(W), ["", "ID", "Title", "Workflow", "Status", "Stage", "SLA", ""]):
        col.markdown(f'<span class="th">{l}</span>', unsafe_allow_html=True)
    st.divider()
    if not rows: empty("No workflows match. Adjust the filters or create a new one.")
    for t in rows:
        wf = get_wf(t["workflow_id"]); sn, sg = cur_stage(t)
        c = st.columns(W)
        c[0].markdown(pdot(t["priority"]), unsafe_allow_html=True)
        c[1].markdown(f'<span class="id">{esc(t["id"])}</span>', unsafe_allow_html=True)
        c[2].markdown(f'<span class="t-title">{esc(t["title"][:40])}{"…" if len(t["title"]) > 40 else ""}</span>', unsafe_allow_html=True)
        c[3].markdown(f'<span class="t-meta">{esc(wf["name"] if wf else "?")}</span>', unsafe_allow_html=True)
        c[4].markdown(sbadge(t["status"]), unsafe_allow_html=True)
        c[5].markdown(f'<span style="font-size:13px">{esc(sn)}</span><br><span class="t-meta">{esc(sg)}</span>', unsafe_allow_html=True)
        c[6].markdown(sla_lbl(t), unsafe_allow_html=True)
        if t["status"] != "Done" and can_advance(t):
            if c[7].button("Advance", key=f"aa_{t['id']}"): advance_task(t["id"]); st.rerun()
        st.markdown("<hr style='margin:4px 0!important'>", unsafe_allow_html=True)

elif page == "Analytics":
    title("Analytics", "Throughput and team load")
    tab_a, tab_b, tab_c = st.tabs(["Throughput", "Teams", "Board"])
    def count(fn):
        d = {}
        for t in tasks: k = fn(t); d[k] = d.get(k, 0) + 1
        return d
    with tab_a:
        if not tasks: empty("No data yet.")
        else:
            section("Instances by workflow"); st.bar_chart(count(lambda t: (get_wf(t["workflow_id"]) or {}).get("name", "Unknown")), color="#2b50d6")
            c1, c2 = st.columns(2)
            with c1: section("By status"); st.bar_chart(count(lambda t: t["status"]), color="#2b50d6")
            with c2: section("By priority"); st.bar_chart(count(lambda t: t["priority"]), color="#2b50d6")
    with tab_b:
        section("Open tasks waiting on each group")
        load = {g["name"]: 0 for g in ss.groups}
        for t in tasks:
            wf = get_wf(t["workflow_id"])
            if t["status"] != "Done" and wf and t["stage_index"] < len(wf["stages"]):
                load[group_name(wf["stages"][t["stage_index"]]["group_id"])] = load.get(group_name(wf["stages"][t["stage_index"]]["group_id"]), 0) + 1
        if any(load.values()): st.bar_chart(load, color="#2b50d6")
        else: empty("No open tasks.")
        section("People")
        for u in ss.users:
            gs = ", ".join(group_name(g) for g in u["groups"]) or "No groups"
            st.markdown(f'<div class="card"><div class="row"><div class="avatar">{esc(initials(u["name"]))}</div><div class="grow t-title">{esc(u["name"])}</div>'
                        f'<div class="t-meta" style="margin:0">{esc(gs)}</div>{badge(u["role"].capitalize(), "b-admin" if u["role"]=="admin" else "b-gray")}</div></div>', unsafe_allow_html=True)
    with tab_c:
        for col, s in zip(st.columns(4), ["New", "In Progress", "Blocked", "Done"]):
            items = [t for t in tasks if t["status"] == s]
            html = f'<div class="sec">{s} <span style="color:var(--faint);font-weight:500">{len(items)}</span></div>'
            for t in items[:5]:
                html += (f'<div class="card" style="padding:10px 12px"><div class="id">{esc(t["id"])}</div><div class="t-title">{esc(t["title"][:28])}</div>'
                         f'<div class="t-meta">{esc((get_wf(t["workflow_id"]) or {}).get("name","?"))} · {esc(t["priority"])}</div></div>')
            if len(items) > 5: html += f'<div class="t-meta">+{len(items) - 5} more</div>'
            col.markdown(html, unsafe_allow_html=True)

elif page == "Notifications":
    title("Notifications", f"{len(ss.notifications)} alerts")
    if ss.notifications and st.button("Clear all"):
        clear_notifications(); ss.notifications = []; st.rerun()
    if not ss.notifications: empty("No notifications.")
    for n in ss.notifications:
        cls = {"warn": "warn", "error": "error", "ok": "ok"}.get(n["type"], "")
        st.markdown(f'<div class="notif {cls}">{esc(n["msg"])}<div class="tm">{esc(n["time"])}</div></div>', unsafe_allow_html=True)

elif page == "Admin":
    if not is_admin(): st.error("Access denied. Admins only."); st.stop()
    title("Administration", "Users, groups, workflow templates and settings")
    tab_u, tab_g, tab_w, tab_s = st.tabs(["Users", "Groups", "Workflow templates", "Settings"])

    with tab_u:
        c1, c2 = st.columns([4, 1])
        c1.markdown('<div class="sec">Users</div>', unsafe_allow_html=True)
        if c2.button("Add user", type="primary", key="btn_au"): ss.show_au = not ss.get("show_au", False)
        if ss.get("show_au"):
            with st.form("form_au"):
                a, b = st.columns(2); nn = a.text_input("Full name *"); ne = b.text_input("Email *")
                a, b = st.columns(2); nr = a.selectbox("Role", ["member", "admin"]); ng = b.multiselect("Groups", [g["name"] for g in ss.groups])
                if st.form_submit_button("Create user", type="primary"):
                    if not nn.strip() or not ne.strip(): st.error("Name and email are required.")
                    elif any(u["email"].lower() == ne.lower() for u in ss.users): st.error("A user with that email already exists.")
                    else:
                        gids = [g["id"] for g in ss.groups if g["name"] in ng]; uid = f"user-{uuid.uuid4().hex[:8]}"
                        upsert_user({"id": uid, "name": nn, "email": ne, "role": nr, "groups": gids, "active": True, "created": _now()})
                        for g in ss.groups:
                            if g["id"] in gids: g["members"].append(uid); upsert_group(g)
                        notify("ok", f"User '{nn}' created as {nr}."); refresh("users", "groups"); ss.show_au = False; st.rerun()
        for u in ss.users:
            chips = "".join(f'<span class="chip">{esc(group_name(g))}</span>' for g in u["groups"]) or '<span class="t-meta">No groups</span>'
            c1, c2 = st.columns([6, 1])
            c1.markdown(f'<div class="card"><div class="row"><div class="avatar">{esc(initials(u["name"]))}</div><div class="grow">'
                        f'<div class="row" style="gap:8px"><span class="t-title">{esc(u["name"])}</span>{badge(u["role"].capitalize(), "b-admin" if u["role"]=="admin" else "b-gray")}'
                        f'{badge("Active" if u["active"] else "Inactive", "b-done" if u["active"] else "b-block")}</div>'
                        f'<div class="t-meta">{esc(u["email"])}</div><div style="margin-top:6px">{chips}</div></div></div></div>', unsafe_allow_html=True)
            if u["id"] != "user-admin":
                with c2.expander("Edit"):
                    names = [g["name"] for g in ss.groups]
                    ug = st.multiselect("Groups", names, default=[group_name(g) for g in u["groups"]], key=f"ug_{u['id']}")
                    ur = st.selectbox("Role", ["member", "admin"], index=0 if u["role"] == "member" else 1, key=f"ur_{u['id']}")
                    if st.button("Save", key=f"su_{u['id']}", type="primary"):
                        ng2 = [g["id"] for g in ss.groups if g["name"] in ug]
                        for g in ss.groups:
                            ch = False
                            if u["id"] in g["members"] and g["id"] not in ng2: g["members"].remove(u["id"]); ch = True
                            if g["id"] in ng2 and u["id"] not in g["members"]: g["members"].append(u["id"]); ch = True
                            if ch: upsert_group(g)
                        u["groups"], u["role"] = ng2, ur; upsert_user(u)
                        notify("info", f"User '{u['name']}' updated."); refresh("users", "groups"); st.rerun()
                    if st.button("Deactivate" if u["active"] else "Reactivate", key=f"dt_{u['id']}"):
                        u["active"] = not u["active"]; upsert_user(u); refresh("users"); st.rerun()

    with tab_g:
        c1, c2 = st.columns([4, 1])
        c1.markdown('<div class="sec">Groups</div>', unsafe_allow_html=True)
        if c2.button("Add group", type="primary", key="btn_ag"): ss.show_ag = not ss.get("show_ag", False)
        if ss.get("show_ag"):
            with st.form("form_ag"):
                a, b = st.columns(2); gn = a.text_input("Group name *")
                gc = b.selectbox("Accent colour", ["#3b82f6", "#10b981", "#8b5cf6", "#f59e0b", "#ec4899", "#ef4444", "#06b6d4"])
                gd = st.text_input("Description")
                ge = st.text_input("Group email", placeholder="engineering@company.com", help="Workflow notifications are sent here")
                if st.form_submit_button("Create group", type="primary"):
                    if not gn.strip(): st.error("Name is required.")
                    elif any(g["name"].lower() == gn.lower() for g in ss.groups): st.error("A group with that name already exists.")
                    else:
                        upsert_group({"id": f"grp-{uuid.uuid4().hex[:8]}", "name": gn, "description": gd, "color": gc, "email": ge, "members": [], "created": _now()})
                        notify("ok", f"Group '{gn}' created."); refresh("groups"); ss.show_ag = False; st.rerun()
        for g in ss.groups:
            members = [get_user(m)["name"] for m in g["members"] if get_user(m)]
            chips = "".join(f'<span class="chip">{esc(m)}</span>' for m in members) or '<span class="t-meta">No members yet</span>'
            mail = esc(g["email"]) if g.get("email") else "No email set"
            c1, c2 = st.columns([6, 1])
            c1.markdown(f'<div class="card"><div class="row" style="align-items:flex-start"><div style="width:4px;height:44px;border-radius:2px;background:{esc(g["color"])}"></div>'
                        f'<div class="grow"><div class="t-title">{esc(g["name"])}</div><div class="t-meta">{esc(g.get("description",""))}</div>'
                        f'<div class="t-meta">{mail}</div><div style="margin-top:6px">{chips}</div></div><div class="t-meta">{len(members)} members</div></div></div>', unsafe_allow_html=True)
            with c2.expander("Edit"):
                nd = st.text_input("Description", value=g.get("description", ""), key=f"gd_{g['id']}")
                ne = st.text_input("Group email", value=g.get("email", ""), key=f"ge_{g['id']}")
                act = [u["name"] for u in ss.users if u["active"]]
                nm = st.multiselect("Members", act, default=[n for n in members if n in act], key=f"gm_{g['id']}")
                if st.button("Save", key=f"sg_{g['id']}", type="primary"):
                    nm2 = [u["id"] for u in ss.users if u["name"] in nm]
                    for u in ss.users:
                        ch = False
                        if u["id"] in nm2 and g["id"] not in u["groups"]: u["groups"].append(g["id"]); ch = True
                        elif u["id"] not in nm2 and g["id"] in u["groups"]: u["groups"].remove(g["id"]); ch = True
                        if ch: upsert_user(u)
                    g.update({"members": nm2, "description": nd, "email": ne}); upsert_group(g)
                    notify("info", f"Group '{g['name']}' updated."); refresh("groups", "users"); st.rerun()

    with tab_w:
        c1, c2 = st.columns([4, 1])
        c1.markdown('<div class="sec">Workflow templates</div>', unsafe_allow_html=True)
        if c2.button("New template", type="primary", key="btn_nt"): workflow_template_modal()
        for wf in ss.workflows:
            n = sum(t["workflow_id"] == wf["id"] for t in tasks)
            flow = " → ".join(f'{esc(s["name"])} <span style="color:var(--faint)">({esc(group_name(s["group_id"]))})</span>' for s in wf["stages"])
            c1, c2 = st.columns([6, 1])
            c1.markdown(f'<div class="card"><div class="row" style="align-items:flex-start"><div class="grow"><div class="row" style="gap:8px">'
                        f'<span class="t-title">{esc(wf["name"])}</span>{badge("Active" if wf["active"] else "Inactive", "b-done" if wf["active"] else "b-block")}'
                        f'<span class="t-meta" style="margin:0">{wf["sla_hours"]}h SLA</span></div><div class="t-meta">{esc(wf.get("description",""))}</div>'
                        f'<div style="font-size:13px;margin-top:6px">{flow}</div><div class="t-meta">{len(wf.get("custom_fields", []))} custom fields</div></div>'
                        f'<div class="t-meta">{n} instances</div></div></div>', unsafe_allow_html=True)
            if c2.button("Edit", key=f"ewf_{wf['id']}"): workflow_template_modal(wf_id=wf["id"])

    with tab_s:
        section("System settings")
        cfg = ss.settings; c1, c2 = st.columns(2)
        cfg["sla_warn_hours"] = c1.slider("SLA warning threshold (hours)", 1, 24, int(cfg.get("sla_warn_hours", 4)))
        cfg["auto_escalate"] = c1.checkbox("Auto-escalate on SLA breach", value=bool(cfg.get("auto_escalate", True)))
        strats = ["Manual", "Round Robin", "Load Balanced"]
        cfg["default_strategy"] = c2.selectbox("Default assignment strategy", strats, index=strats.index(cfg.get("default_strategy", "Manual")))
        if st.button("Save settings", type="primary"):
            save_settings(cfg); refresh("settings"); notify("ok", "System settings updated."); st.success("Settings saved.")
        st.divider(); section("Email notifications")
        if email_is_configured():
            st.success("Email is configured.")
            if st.button("Send test email", key="test_email"):
                ok, err = test_connection()
                st.success("Test email sent. Check your inbox.") if ok else st.error(f"Failed to send: {err}")
        else:
            st.warning("Email notifications are not configured.")
            st.markdown("Add SMTP credentials to `.streamlit/secrets.toml`, then set a **Group email** on each group. "
                        "WorkBench emails the owning group when a task is assigned, advanced, blocked or completed.")
            st.code('[email]\nsmtp_host     = "smtp.example.com"\nsmtp_port     = 587\nsmtp_user     = "you@example.com"\nsmtp_password = "your-app-password"\nfrom_name     = "WorkBench"\nenabled       = true', language="toml")
