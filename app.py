"""
WorkBench — Enterprise Workflow Platform
Run:  streamlit run app.py   (requires streamlit >= 1.36)
Data: flowdesk.db is created automatically on first run.
      database.py must be in the same folder as app.py.
"""
import streamlit as st
from datetime import datetime, timedelta
import uuid, json

from database import (
    init_db, needs_seed,
    get_users,      upsert_user,
    get_groups,     upsert_group,
    get_workflows,  upsert_workflow,
    get_tasks,      upsert_task,
    add_history,
    get_notifications, add_notification, clear_notifications,
    increment_task_counter,
    get_settings,   save_settings,
)

# Email notifications (skipped silently if email_service.py is missing)
try:
    from email_service import (
        notify_task_assigned, notify_task_advanced,
        notify_task_blocked, notify_task_completed,
        email_is_configured, test_connection,
    )
    _EMAIL_AVAILABLE = True
except ImportError:
    _EMAIL_AVAILABLE = False
    def notify_task_assigned(*a, **k): return False, "email_service not found"
    def notify_task_advanced(*a, **k): return False, "email_service not found"
    def notify_task_blocked(*a, **k):  return False, "email_service not found"
    def notify_task_completed(*a, **k):return False, "email_service not found"
    def email_is_configured():         return False
    def test_connection():             return False, "email_service not found"


st.set_page_config(
    page_title="FlowDesk",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;500;600;700&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html,body,[data-testid="stAppViewContainer"]{background:#0a0d14!important;color:#e2e8f0!important;font-family:'IBM Plex Sans',sans-serif!important}
[data-testid="stSidebar"]{background:#0d1117!important;border-right:1px solid #1e2736!important;display:block!important;visibility:visible!important}
[data-testid="stSidebar"] *{color:#94a3b8!important}
#MainMenu,footer,header{visibility:hidden}
[data-testid="collapsedControl"]{display:none!important}
button[data-testid="baseButton-headerNoPadding"]{display:none!important}
[data-testid="stSidebarCollapseButton"]{display:none!important}
span[data-testid="stIconMaterial"]{display:none!important}
.block-container{padding:1.5rem 2rem 2rem!important;max-width:100%!important}
[data-testid="stDialog"]>div>div{background:#0f1623!important;border:1px solid #1e2d42!important;border-radius:12px!important;box-shadow:0 24px 80px rgba(0,0,0,.85)!important;max-width:780px!important;width:96vw!important}
.step-item{flex:1;text-align:center;padding:10px 6px;font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#475569;border-bottom:3px solid transparent}
.step-item.active{color:#60a5fa;border-bottom-color:#3b82f6}.step-item.done{color:#34d399;border-bottom-color:#10b981}
.metric-card{background:#111827;border:1px solid #1e2736;border-radius:8px;padding:20px 24px;position:relative;overflow:hidden;margin-bottom:4px}
.metric-card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px}
.metric-card.blue::before{background:#3b82f6}.metric-card.amber::before{background:#f59e0b}
.metric-card.green::before{background:#10b981}.metric-card.red::before{background:#ef4444}
.metric-label{font-size:11px;font-weight:600;letter-spacing:.12em;text-transform:uppercase;color:#64748b;margin-bottom:8px}
.metric-value{font-family:'IBM Plex Mono',monospace;font-size:28px;font-weight:600;color:#f1f5f9;line-height:1}
.task-row{background:#111827;border:1px solid #1e2736;border-radius:8px;padding:14px 18px;margin-bottom:8px;display:flex;align-items:center;gap:14px}
.task-row:hover{border-color:#3b82f6}
.badge{display:inline-block;padding:3px 10px;border-radius:4px;font-size:11px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;font-family:'IBM Plex Mono',monospace}
.badge-new{background:#1e3a5f;color:#60a5fa;border:1px solid #2563eb44}
.badge-inprogress{background:#451a03;color:#fb923c;border:1px solid #ea580c44}
.badge-review{background:#312e81;color:#a78bfa;border:1px solid #7c3aed44}
.badge-done{background:#052e16;color:#34d399;border:1px solid #05966944}
.badge-blocked{background:#450a0a;color:#f87171;border:1px solid #dc262644}
.badge-group{background:#1a2a1a;color:#86efac;border:1px solid #16a34a44}
.badge-admin{background:#2e1a4a;color:#c4b5fd;border:1px solid #7c3aed44}
.prio{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.prio-critical{background:#ef4444;box-shadow:0 0 6px #ef444488}
.prio-high{background:#f59e0b}.prio-medium{background:#3b82f6}.prio-low{background:#64748b}
.section-header{display:flex;align-items:center;gap:10px;margin-bottom:18px;padding-bottom:12px;border-bottom:1px solid #1e2736}
.section-header h2{font-size:13px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#64748b}
.notif{background:#111827;border-left:3px solid #3b82f6;border-radius:0 6px 6px 0;padding:12px 16px;margin-bottom:8px;font-size:13px}
.notif.warn{border-left-color:#f59e0b}.notif.error{border-left-color:#ef4444}.notif.ok{border-left-color:#10b981}
.notif-time{font-family:'IBM Plex Mono',monospace;font-size:11px;color:#64748b;margin-top:4px}
.prog-wrap{background:#1e2736;border-radius:4px;height:5px;overflow:hidden;margin-top:6px}
.prog-fill{height:100%;border-radius:4px}
.timeline-item{display:flex;gap:14px;margin-bottom:14px}
.tl-dot{width:9px;height:9px;border-radius:50%;background:#3b82f6;flex-shrink:0;margin-top:4px}
.tl-text{font-size:13px;color:#94a3b8}.tl-time{font-family:'IBM Plex Mono',monospace;font-size:11px;color:#475569;margin-top:2px}
.stage-rail{display:flex;align-items:center;margin:16px 0}
.stage-step{display:flex;flex-direction:column;align-items:center}
.stage-bubble{display:inline-flex;width:32px;height:32px;border-radius:50%;align-items:center;justify-content:center;font-size:12px;font-weight:700;font-family:'IBM Plex Mono',monospace}
.stage-done{background:#10b981;color:#fff}.stage-active{background:#3b82f6;color:#fff;box-shadow:0 0 0 3px #3b82f633}.stage-pending{background:#1e2736;color:#64748b}
.stage-connector{height:2px;flex:1;background:#1e2736;min-width:20px}.stage-connector.done{background:#10b981}
.stage-label{font-size:10px;color:#64748b;margin-top:4px;text-transform:uppercase;letter-spacing:.06em;max-width:70px;text-align:center;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.lock-notice{background:#1a1208;border:1px solid #78350f55;border-radius:6px;padding:10px 14px;font-size:12px;color:#fbbf24;margin:8px 0}
.group-chip{display:inline-block;background:#1e2736;border:1px solid #334155;border-radius:12px;padding:3px 10px;font-size:11px;color:#94a3b8;margin:2px;font-family:'IBM Plex Mono',monospace}
.stButton>button{background:#1e3a5f!important;color:#60a5fa!important;border:1px solid #2563eb44!important;border-radius:6px!important;font-family:'IBM Plex Mono',monospace!important;font-size:12px!important;font-weight:600!important;letter-spacing:.06em!important;transition:background .2s!important}
.stButton>button:hover{background:#2563eb!important;color:#fff!important;border-color:#3b82f6!important}
.stButton>button[kind="primary"]{background:#2563eb!important;color:#fff!important;border-color:#3b82f6!important}
.stSelectbox>div>div,.stTextInput>div>div>input,.stTextArea textarea,.stMultiSelect>div>div{background:#111827!important;border-color:#1e2736!important;color:#e2e8f0!important}
.stTabs [data-baseweb="tab-list"]{background:transparent!important;border-bottom:1px solid #1e2736!important;gap:4px}
.stTabs [data-baseweb="tab"]{background:transparent!important;color:#64748b!important;border-radius:6px 6px 0 0!important;font-size:13px!important}
.stTabs [aria-selected="true"]{background:#111827!important;color:#60a5fa!important;border-bottom:2px solid #3b82f6!important}
.stTabs [data-baseweb="tab-panel"]{padding-top:20px!important}
.logo-bar{display:flex;align-items:center;gap:10px;padding:16px 0 22px;border-bottom:1px solid #1e2736;margin-bottom:20px}
.logo-name{font-family:'IBM Plex Mono',monospace;font-size:17px;font-weight:600;color:#f1f5f9}
.logo-version{font-size:10px;color:#475569;font-family:'IBM Plex Mono',monospace;margin-top:2px}
.avatar{width:28px;height:28px;border-radius:50%;background:linear-gradient(135deg,#2563eb,#7c3aed);display:inline-flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:#fff;font-family:'IBM Plex Mono',monospace;flex-shrink:0}
.avatar-lg{width:40px;height:40px;border-radius:50%;background:linear-gradient(135deg,#2563eb,#7c3aed);display:inline-flex;align-items:center;justify-content:center;font-size:14px;font-weight:700;color:#fff;font-family:'IBM Plex Mono',monospace;flex-shrink:0}
.page-title{font-size:22px;font-weight:600;color:#f1f5f9;margin-bottom:4px}
.page-sub{font-size:13px;color:#64748b;margin-bottom:22px}
.sla-ok{color:#34d399;font-family:'IBM Plex Mono',monospace;font-size:11px}
.sla-warning{color:#fbbf24;font-family:'IBM Plex Mono',monospace;font-size:11px}
.sla-breach{color:#f87171;font-family:'IBM Plex Mono',monospace;font-size:11px}
hr.divider{border:none;border-top:1px solid #1e2736;margin:8px 0}
.rv-block{background:#111827;border:1px solid #1e2736;border-radius:8px;overflow:hidden;margin-bottom:12px}
.rv-head{padding:12px 16px;background:#0d1117;border-bottom:1px solid #1e2736;display:flex;align-items:center;gap:10px}
.rv-row{display:flex;padding:7px 16px;border-bottom:1px solid #161f2e;font-size:13px}
.rv-row:last-child{border-bottom:none}
.rv-lbl{color:#64748b;width:40%;font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.06em}
.rv-val{color:#e2e8f0;flex:1}
</style>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  SEED DATA
# ══════════════════════════════════════════════════════════════════════════════
def _now(): return datetime.now().strftime("%Y-%m-%d %H:%M")

def _default_groups():
    return [
        {"id":"grp-eng",  "name":"Engineering",         "description":"Software development and infrastructure","color":"#3b82f6","members":[],"created":_now()},
        {"id":"grp-fin",  "name":"Finance & Accounting", "description":"Expense review, budget approvals, and audit","color":"#10b981","members":[],"created":_now()},
        {"id":"grp-legal","name":"Legal & Compliance",   "description":"Contract review, regulatory compliance","color":"#8b5cf6","members":[],"created":_now()},
        {"id":"grp-ops",  "name":"Operations",           "description":"Day-to-day operational tasks","color":"#f59e0b","members":[],"created":_now()},
        {"id":"grp-hr",   "name":"Human Resources",      "description":"Onboarding, offboarding, employee relations","color":"#ec4899","members":[],"created":_now()},
        {"id":"grp-exec", "name":"Executive",            "description":"Senior leadership approvals","color":"#ef4444","members":[],"created":_now()},
    ]

def _default_workflows():
    return [
        {"id":"wf-contract","name":"Contract Approval","description":"Multi-stage contract review and approval","icon":"📄","sla_hours":72,"active":True,
         "stages":[{"name":"Draft Review","group_id":"grp-legal","description":"Legal reviews draft"},
                   {"name":"Financial Sign-off","group_id":"grp-fin","description":"Finance approves terms"},
                   {"name":"Executive Approval","group_id":"grp-exec","description":"Executive signs off"}],
         "custom_fields":[
             {"id":"counterparty","label":"Counterparty / Company","type":"text","placeholder":"e.g. Acme Corp","options":[],"required":True},
             {"id":"contract_value","label":"Contract Value (USD)","type":"number","placeholder":"e.g. 50000","options":[],"required":True},
             {"id":"contract_type","label":"Contract Type","type":"select","placeholder":"","options":["NDA","MSA","SOW","SLA","Licensing","Other"],"required":True},
             {"id":"effective_date","label":"Effective Date","type":"date","placeholder":"","options":[],"required":True},
             {"id":"legal_contact","label":"Legal Contact Email","type":"email","placeholder":"lawyer@company.com","options":[],"required":False},
             {"id":"notes","label":"Special Terms / Notes","type":"textarea","placeholder":"Any unusual clauses...","options":[],"required":False},
         ]},
        {"id":"wf-expense","name":"Expense Claim","description":"Employee expense reimbursement workflow","icon":"💳","sla_hours":48,"active":True,
         "stages":[{"name":"Manager Review","group_id":"grp-ops","description":"Manager approves"},
                   {"name":"Finance Audit","group_id":"grp-fin","description":"Finance verifies"},
                   {"name":"Payment Release","group_id":"grp-fin","description":"Finance pays"}],
         "custom_fields":[
             {"id":"amount","label":"Claim Amount (USD)","type":"number","placeholder":"e.g. 420.00","options":[],"required":True},
             {"id":"category","label":"Expense Category","type":"select","placeholder":"","options":["Travel","Meals","Software","Hardware","Training","Marketing","Other"],"required":True},
             {"id":"expense_date","label":"Date of Expense","type":"date","placeholder":"","options":[],"required":True},
             {"id":"vendor","label":"Vendor / Merchant","type":"text","placeholder":"e.g. Delta Airlines","options":[],"required":True},
             {"id":"cost_centre","label":"Cost Centre / Project Code","type":"text","placeholder":"e.g. CC-ENG-042","options":[],"required":False},
             {"id":"justification","label":"Business Justification","type":"textarea","placeholder":"Why was this expense necessary?","options":[],"required":True},
         ]},
        {"id":"wf-onboard","name":"Employee Onboarding","description":"New hire setup and orientation","icon":"🧑\u200d💼","sla_hours":120,"active":True,
         "stages":[{"name":"HR Intake","group_id":"grp-hr","description":"HR collects documents"},
                   {"name":"IT Provisioning","group_id":"grp-eng","description":"Engineering sets up accounts"},
                   {"name":"Manager Induction","group_id":"grp-ops","description":"Manager completes orientation"}],
         "custom_fields":[
             {"id":"employee_name","label":"New Employee Full Name","type":"text","placeholder":"e.g. Jordan Smith","options":[],"required":True},
             {"id":"employee_email","label":"Employee Email","type":"email","placeholder":"jordan@company.com","options":[],"required":True},
             {"id":"start_date","label":"Start Date","type":"date","placeholder":"","options":[],"required":True},
             {"id":"job_title","label":"Job Title","type":"text","placeholder":"e.g. Senior Engineer","options":[],"required":True},
             {"id":"manager","label":"Reporting Manager","type":"text","placeholder":"e.g. Alex Kim","options":[],"required":True},
             {"id":"equipment","label":"Equipment Needed","type":"select","placeholder":"","options":["MacBook Pro","MacBook Air","Dell Laptop","Windows Desktop","No Equipment"],"required":True},
             {"id":"access_level","label":"System Access Level","type":"select","placeholder":"","options":["Read Only","Standard","Elevated","Admin"],"required":True},
         ]},
        {"id":"wf-change","name":"Change Request","description":"System or process change management","icon":"🔧","sla_hours":96,"active":True,
         "stages":[{"name":"Impact Assessment","group_id":"grp-eng","description":"Engineering assesses risk"},
                   {"name":"Ops Approval","group_id":"grp-ops","description":"Operations approves"},
                   {"name":"Executive Sign-off","group_id":"grp-exec","description":"Executive authorises"}],
         "custom_fields":[
             {"id":"system","label":"System / Service Affected","type":"text","placeholder":"e.g. Payment API","options":[],"required":True},
             {"id":"change_type","label":"Change Type","type":"select","placeholder":"","options":["Standard","Emergency","Major Release","Configuration","Rollback"],"required":True},
             {"id":"risk_level","label":"Risk Level","type":"select","placeholder":"","options":["Low","Medium","High","Critical"],"required":True},
             {"id":"planned_date","label":"Planned Implementation Date","type":"date","placeholder":"","options":[],"required":True},
             {"id":"downtime","label":"Expected Downtime (minutes)","type":"number","placeholder":"0 if none","options":[],"required":True},
             {"id":"rollback_plan","label":"Rollback Plan","type":"textarea","placeholder":"Describe how to revert...","options":[],"required":True},
         ]},
        {"id":"wf-incident","name":"Incident Report","description":"Operational incident triage and resolution","icon":"🚨","sla_hours":24,"active":True,
         "stages":[{"name":"Triage","group_id":"grp-eng","description":"Engineering triages"},
                   {"name":"Resolution","group_id":"grp-eng","description":"Engineering resolves"},
                   {"name":"Post-mortem","group_id":"grp-ops","description":"Ops documents learnings"}],
         "custom_fields":[
             {"id":"severity","label":"Severity Level","type":"select","placeholder":"","options":["SEV-1 (Critical)","SEV-2 (Major)","SEV-3 (Minor)","SEV-4 (Low)"],"required":True},
             {"id":"affected_system","label":"Affected System / Service","type":"text","placeholder":"e.g. Auth Service","options":[],"required":True},
             {"id":"impact","label":"User / Business Impact","type":"select","placeholder":"","options":["All users down","Partial outage","Degraded performance","Data issue","No user impact"],"required":True},
             {"id":"symptoms","label":"Symptoms / Error Description","type":"textarea","placeholder":"What is broken?","options":[],"required":True},
             {"id":"incident_lead","label":"Incident Lead","type":"text","placeholder":"Person managing the incident","options":[],"required":True},
         ]},
        {"id":"wf-vendor","name":"Vendor Approval","description":"New vendor onboarding and approval","icon":"🤝","sla_hours":120,"active":True,
         "stages":[{"name":"Vendor Vetting","group_id":"grp-legal","description":"Legal verifies credentials"},
                   {"name":"Budget Review","group_id":"grp-fin","description":"Finance approves spend"},
                   {"name":"Ops Sign-off","group_id":"grp-ops","description":"Operations finalises"}],
         "custom_fields":[
             {"id":"vendor_name","label":"Vendor Company Name","type":"text","placeholder":"e.g. Stripe Inc.","options":[],"required":True},
             {"id":"vendor_contact","label":"Vendor Contact Email","type":"email","placeholder":"contact@vendor.com","options":[],"required":True},
             {"id":"service_type","label":"Service / Product Type","type":"select","placeholder":"","options":["Software / SaaS","Professional Services","Hardware","Cloud Infrastructure","Consulting","Other"],"required":True},
             {"id":"annual_value","label":"Estimated Annual Value (USD)","type":"number","placeholder":"e.g. 25000","options":[],"required":True},
             {"id":"data_access","label":"Requires Access to Company Data?","type":"select","placeholder":"","options":["Yes - PII","Yes - Financial","Yes - Internal only","No data access"],"required":True},
             {"id":"business_case","label":"Business Case / Justification","type":"textarea","placeholder":"Why is this vendor needed?","options":[],"required":True},
         ]},
    ]

# ══════════════════════════════════════════════════════════════════════════════
#  DB INIT + SESSION LOAD
# ══════════════════════════════════════════════════════════════════════════════
init_db()

if needs_seed():
    upsert_user({"id":"user-admin","name":"Admin","email":"admin@flowdesk.io",
                 "role":"admin","groups":[],"active":True,"created":_now()})
    for g in _default_groups():    upsert_group(g)
    for w in _default_workflows(): upsert_workflow(w)

if "db_loaded" not in st.session_state:
    st.session_state.users         = get_users()
    st.session_state.groups        = get_groups()
    st.session_state.workflows     = get_workflows()
    st.session_state.tasks         = get_tasks()
    st.session_state.notifications = get_notifications()
    st.session_state.settings      = get_settings()
    st.session_state.db_loaded       = True
    st.session_state.current_user_id = "user-admin"
    st.session_state.modal_step      = 1
    st.session_state.modal_wf_id     = None

# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def get_user(uid):    return next((u for u in st.session_state.users    if u["id"]==uid), None)
def get_group(gid):   return next((g for g in st.session_state.groups   if g["id"]==gid), None)
def get_wf(wid):      return next((w for w in st.session_state.workflows if w["id"]==wid), None)
def current_user():   return get_user(st.session_state.current_user_id)
def is_admin():       u=current_user(); return bool(u and u["role"]=="admin")
def user_groups(uid): u=get_user(uid); return u["groups"] if u else []
def group_name(gid):  g=get_group(gid); return g["name"] if g else gid
def initials(name):   p=name.strip().split(); return (p[0][0]+(p[-1][0] if len(p)>1 else "")).upper()

def db_add_notif(ntype, msg):
    add_notification(ntype, msg)
    st.session_state.notifications = get_notifications()

def group_email(gid: str) -> str:
    """Return the email address for a group, or empty string if none set."""
    g = get_group(gid)
    return g.get("email", "") if g else ""


def can_advance(task):
    if is_admin(): return True
    wf = get_wf(task["workflow_id"])
    if not wf: return False
    idx = task["stage_index"]
    if idx >= len(wf["stages"]): return False
    return wf["stages"][idx]["group_id"] in user_groups(st.session_state.current_user_id)

def advance_task(tid):
    task = next((t for t in st.session_state.tasks if t["id"]==tid), None)
    if not task: return
    wf = get_wf(task["workflow_id"])
    if not wf or task["status"]=="Done": return
    cu = current_user()
    by = cu["name"] if cu else "System"
    si = task["stage_index"]
    sn = wf["stages"][si]["name"] if si < len(wf["stages"]) else "?"
    add_history(tid, f"Stage '{sn}' completed", by)
    ni = si + 1
    if ni >= len(wf["stages"]):
        task.update({"status":"Done","stage_index":ni,"progress":100,"closed_at":_now()})
        upsert_task(task)
        add_history(tid, "Workflow completed and closed", "System")
        db_add_notif("ok", f"{tid} completed and closed.")
        # Email the group that actioned the final stage
        gemail = group_email(wf["stages"][si]["group_id"])
        gname  = group_name(wf["stages"][si]["group_id"])
        notify_task_completed(
            group_email=gemail, group_name=gname,
            task_id=tid, task_title=task["title"], workflow=wf["name"],
            priority=task["priority"], completed_by=by)
    else:
        ns = wf["stages"][ni]
        task.update({"stage_index":ni,"status":"In Progress","progress":int((ni/len(wf["stages"]))*100)})
        upsert_task(task)
        add_history(tid, f"Moved to '{ns['name']}' - awaiting {group_name(ns['group_id'])}", "System")
        db_add_notif("info", f"{tid} advanced to '{ns['name']}' - needs {group_name(ns['group_id'])}.")
        # Email the group that now owns the new stage
        gemail = group_email(ns["group_id"])
        gname  = group_name(ns["group_id"])
        notify_task_advanced(
            group_email=gemail, group_name=gname,
            task_id=tid, task_title=task["title"], workflow=wf["name"],
            stage=ns["name"], priority=task["priority"], due=task.get("due",""),
            advanced_by=by)
    st.session_state.tasks = get_tasks()

STATUS_CSS = {"New":"badge-new","In Progress":"badge-inprogress","In Review":"badge-review","Done":"badge-done","Blocked":"badge-blocked"}
PRIO_CSS   = {"critical":"prio-critical","high":"prio-high","medium":"prio-medium","low":"prio-low"}
def sbadge(s): return f'<span class="badge {STATUS_CSS.get(s,"badge-new")}">{s}</span>'
def pdot(p):   return f'<div class="prio {PRIO_CSS.get(p,"prio-low")}"></div>'
def pbar(pct, c="#3b82f6"): return f'<div class="prog-wrap"><div class="prog-fill" style="width:{pct}%;background:{c}"></div></div>'

def sla_lbl(t):
    if t["status"] == "Done": return '<span class="sla-ok">CLOSED</span>'
    due = t.get("due", "")
    if due:
        try:
            h = (datetime.strptime(due, "%Y-%m-%d %H:%M") - datetime.now()).total_seconds() / 3600
            if h < 0:  return '<span class="sla-breach">BREACHED</span>'
            if h < 4:  return f'<span class="sla-warning">{int(h)}h left</span>'
        except Exception: pass
    return '<span class="sla-ok">ON TRACK</span>'

def stage_rail(task):
    wf = get_wf(task["workflow_id"])
    if not wf: return ""
    stages = wf["stages"]; idx = task["stage_index"]
    h = '<div class="stage-rail">'
    for i, s in enumerate(stages):
        if i > 0: h += f'<div class="stage-connector {"done" if i<=idx else ""}"></div>'
        if i < idx or task["status"] == "Done": cls, lbl = "stage-done", "✓"
        elif i == idx:                           cls, lbl = "stage-active", str(i+1)
        else:                                    cls, lbl = "stage-pending", str(i+1)
        h += (f'<div class="stage-step"><div class="stage-bubble {cls}">{lbl}</div>'
              f'<div class="stage-label">{s["name"]}</div></div>')
    return h + "</div>"

def render_custom_field(f, prefix):
    ftype = f["type"]; label = f["label"] + (" *" if f.get("required") else ""); k = f"{prefix}_{f['id']}"
    if ftype == "textarea":  return st.text_area(label, placeholder=f.get("placeholder",""), key=k, height=80)
    elif ftype == "select":
        opts = f.get("options", [])
        return st.selectbox(label, opts, key=k) if opts else st.text_input(label, key=k)
    elif ftype == "date":    return str(st.date_input(label, key=k))
    elif ftype == "number":  return str(st.number_input(label, min_value=0.0, step=1.0, key=k))
    elif ftype == "email":   return st.text_input(label, placeholder=f.get("placeholder",""), key=k)
    else:                    return st.text_input(label, placeholder=f.get("placeholder",""), key=k)

@st.dialog("New Workflow Instance", width="large")
def new_workflow_modal():
    active_wfs = [w for w in st.session_state.workflows if w["active"]]
    if not active_wfs:
        st.warning("No active workflow templates. An admin must create one first.")
        if st.button("Close"): st.rerun()
        return

    step = st.session_state.get("modal_step", 1)

    # Step bar
    cols_s = st.columns(3)
    for i, (col, lbl) in enumerate(zip(cols_s, ["1 - Choose Type","2 - Fill Details","3 - Review"]), 1):
        cls = "done" if i < step else ("active" if i == step else "")
        col.markdown(f'<div class="step-item {cls}">{lbl}</div>', unsafe_allow_html=True)
    st.markdown("<hr class='divider'>", unsafe_allow_html=True)

    # ── Step 1 ────────────────────────────────────────────────────────────────
    if step == 1:
        st.markdown("#### Select a workflow type")
        display_labels = [f"{w.get('icon','📋')}  {w['name']}" for w in active_wfs]
        wf_ids = [w["id"] for w in active_wfs]
        cur_idx = wf_ids.index(st.session_state.modal_wf_id) \
                  if st.session_state.modal_wf_id in wf_ids else 0
        chosen_label = st.selectbox("", display_labels, index=cur_idx,
                                    key="s1_wf_select", label_visibility="collapsed")
        chosen_wf = active_wfs[display_labels.index(chosen_label)]

        st.markdown(
            f'<div style="background:#111f33;border:2px solid #3b82f6;border-radius:8px;'
            f'padding:16px 18px;margin:12px 0">'
            f'<div style="font-size:24px;margin-bottom:8px">{chosen_wf.get("icon","📋")}</div>'
            f'<div style="font-size:14px;font-weight:600;color:#e2e8f0;margin-bottom:4px">{chosen_wf["name"]}</div>'
            f'<div style="font-size:12px;color:#64748b;line-height:1.5;margin-bottom:8px">{chosen_wf.get("description","")}</div>'
            f'<div style="font-size:10px;color:#475569;font-family:IBM Plex Mono,monospace">'
            f'SLA: {chosen_wf["sla_hours"]}h - {len(chosen_wf["stages"])} stages'
            f' - {len(chosen_wf.get("custom_fields",[]))} custom fields</div></div>',
            unsafe_allow_html=True)

        st.markdown("**Approval stages:**")
        for i, s in enumerate(chosen_wf["stages"]):
            gn = group_name(s["group_id"])
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:10px;padding:7px 12px;'
                f'background:#111827;border-radius:6px;margin-bottom:6px;border:1px solid #1e2736">'
                f'<div style="width:20px;height:20px;border-radius:50%;background:#1e2736;'
                f'display:inline-flex;align-items:center;justify-content:center;font-size:9px;'
                f'font-weight:700;color:#64748b;font-family:IBM Plex Mono,monospace;flex-shrink:0">{i+1}</div>'
                f'<div style="flex:1;font-size:13px;color:#94a3b8">{s["name"]}</div>'
                f'<div style="font-size:11px;color:#475569;font-family:IBM Plex Mono,monospace">{gn}</div>'
                f'</div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        ca, _, cn = st.columns([1, 3, 1])
        with ca:
            if st.button("Cancel", key="s1_cancel"):
                st.session_state.modal_step = 1
                st.session_state.modal_wf_id = None
                st.rerun()
        with cn:
            if st.button("Next", key="s1_next", type="primary"):
                st.session_state.modal_wf_id = chosen_wf["id"]
                st.session_state.modal_step = 2   # no rerun — dialog stays open

    # ── Step 2 ────────────────────────────────────────────────────────────────
    elif step == 2:
        wf = get_wf(st.session_state.modal_wf_id)
        st.markdown(f"#### {wf.get('icon','📋')} {wf['name']} - Details")
        st.markdown("**Common Details**")
        cc1, cc2 = st.columns(2)
        with cc1: title    = st.text_input("Title *", placeholder="Short descriptive title...", key="m_title")
        with cc2: priority = st.selectbox("Priority", ["medium","high","critical","low"], key="m_priority")
        cd1, cd2 = st.columns(2)
        with cd1: due_date = st.date_input("Due Date *", value=datetime.now()+timedelta(days=3), key="m_due_date")
        with cd2: due_time = st.text_input("Due Time", value="17:00", key="m_due_time")
        description = st.text_area("Description", placeholder="Optional overview or context...",
                                   height=70, key="m_desc")

        custom_fields = wf.get("custom_fields", [])
        custom_values = {}
        if custom_fields:
            st.markdown("---")
            st.markdown(f"**{wf['name']} - Required Information**")
            i = 0
            while i < len(custom_fields):
                f = custom_fields[i]
                short = f["type"] not in ("textarea",)
                if short and i+1 < len(custom_fields) and custom_fields[i+1]["type"] not in ("textarea",):
                    col1, col2 = st.columns(2)
                    with col1: custom_values[f["id"]] = render_custom_field(f, "cf2")
                    with col2: custom_values[custom_fields[i+1]["id"]] = render_custom_field(custom_fields[i+1], "cf2")
                    i += 2
                else:
                    custom_values[f["id"]] = render_custom_field(f, "cf2")
                    i += 1

        st.markdown("<br>", unsafe_allow_html=True)
        cb1, _, cb2, cb3 = st.columns([1, 2, 1, 1])
        with cb1:
            if st.button("Back", key="s2_back"):
                st.session_state.modal_step = 1   # no rerun
        with cb2:
            if st.button("Cancel", key="s2_cancel"):
                st.session_state.modal_step = 1
                st.session_state.modal_wf_id = None
                st.rerun()
        with cb3:
            if st.button("Review", key="s2_next", type="primary"):
                errors = []
                if not title.strip(): errors.append("Title is required.")
                for f in custom_fields:
                    if f.get("required"):
                        v = custom_values.get(f["id"], "")
                        if not str(v).strip() or v in ("0.0", "0"):
                            errors.append(f"'{f['label']}' is required.")
                if errors:
                    for e in errors: st.error(e)
                else:
                    st.session_state["m_data"] = {
                        "title": title, "priority": priority,
                        "due": f"{due_date} {due_time}",
                        "description": description, "custom": custom_values,
                    }
                    st.session_state.modal_step = 3   # no rerun

    # ── Step 3 ────────────────────────────────────────────────────────────────
    elif step == 3:
        wf   = get_wf(st.session_state.modal_wf_id)
        data = st.session_state.get("m_data", {})
        cu   = current_user()
        st.markdown(f"#### Review - {wf.get('icon','📋')} {wf['name']}")

        desc_row = (f'<div class="rv-row"><div class="rv-lbl">Description</div>'
                    f'<div class="rv-val">{data.get("description","")}</div></div>'
                    if data.get("description") else "")
        st.markdown(
            f'<div class="rv-block">'
            f'<div class="rv-head"><span style="font-size:22px">{wf.get("icon","📋")}</span>'
            f'<div><div style="font-size:15px;font-weight:600;color:#f1f5f9">{data.get("title","")}</div>'
            f'<div style="font-size:11px;color:#64748b;margin-top:2px">{wf["name"]} - '
            f'<span style="color:#60a5fa">{data.get("priority","medium")}</span> priority</div></div></div>'
            f'<div class="rv-row"><div class="rv-lbl">Due</div><div class="rv-val">{data.get("due","")}</div></div>'
            f'{desc_row}</div>', unsafe_allow_html=True)

        custom = data.get("custom", {})
        rows = "".join(
            f'<div class="rv-row"><div class="rv-lbl">{f["label"]}</div>'
            f'<div class="rv-val">{custom.get(f["id"],"")}</div></div>'
            for f in wf.get("custom_fields", [])
            if custom.get(f["id"]) and str(custom.get(f["id"],"")).strip()
        )
        if rows: st.markdown(f'<div class="rv-block">{rows}</div>', unsafe_allow_html=True)

        st.markdown("**Workflow stages:**")
        for i, s in enumerate(wf["stages"]):
            gn = group_name(s["group_id"])
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:10px;padding:7px 12px;'
                f'background:#111827;border-radius:6px;margin-bottom:6px;border:1px solid #1e2736">'
                f'<div style="width:20px;height:20px;border-radius:50%;background:#1e2736;'
                f'display:inline-flex;align-items:center;justify-content:center;font-size:9px;'
                f'font-weight:700;color:#64748b;font-family:IBM Plex Mono,monospace;flex-shrink:0">{i+1}</div>'
                f'<div style="flex:1;font-size:13px;color:#94a3b8">{s["name"]}</div>'
                f'<div style="font-size:11px;color:#475569;font-family:IBM Plex Mono,monospace">{gn}</div>'
                f'</div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        cr1, _, cr2, cr3 = st.columns([1, 2, 1, 1])
        with cr1:
            if st.button("Back", key="s3_back"):
                st.session_state.modal_step = 2   # no rerun
        with cr2:
            if st.button("Cancel", key="s3_cancel"):
                st.session_state.modal_step = 1
                st.session_state.modal_wf_id = None
                st.session_state.pop("m_data", None)
                st.rerun()
        with cr3:
            if st.button("Create", key="s3_create", type="primary"):
                # Build combined description
                clines = [
                    f"{f['label']}: {custom.get(f['id'],'')}"
                    for f in wf.get("custom_fields", [])
                    if custom.get(f["id"]) and str(custom.get(f["id"],"")).strip()
                ]
                full_desc = (
                    data.get("description", "")
                    + ("\n\n" if data.get("description") and clines else "")
                    + "\n".join(clines)
                ).strip()

                # Get unique ID from DB counter
                new_counter = increment_task_counter()
                nid = f"WF-{new_counter}"

                new_task = {
                    "id": nid, "title": data["title"], "description": full_desc,
                    "workflow_id": wf["id"], "status": "New", "priority": data["priority"],
                    "stage_index": 0, "progress": 0, "created": _now(),
                    "created_by": cu["name"] if cu else "System",
                    "due": data["due"], "closed_at": None, "custom_fields": custom,
                }
                # Persist task + history to DB
                upsert_task(new_task)
                add_history(nid, "Workflow instance created", cu["name"] if cu else "System")
                add_history(nid,
                    f"Stage '{wf['stages'][0]['name']}' started - "
                    f"awaiting {group_name(wf['stages'][0]['group_id'])}", "System")
                db_add_notif("info", f"{nid} '{data['title']}' created via {wf['name']}.")
                # Email the group that owns stage 1
                _s0 = wf["stages"][0]
                notify_task_assigned(
                    group_email=group_email(_s0["group_id"]),
                    group_name=group_name(_s0["group_id"]),
                    task_id=nid, task_title=data["title"], workflow=wf["name"],
                    stage=_s0["name"], priority=data["priority"],
                    due=data["due"], created_by=cu["name"] if cu else "System")

                # Refresh session cache from DB
                st.session_state.tasks = get_tasks()
                st.session_state.modal_step = 1
                st.session_state.modal_wf_id = None
                st.session_state.pop("m_data", None)
                st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
#  MODAL: Workflow Template Editor
# ══════════════════════════════════════════════════════════════════════════════
@st.dialog("Workflow Template Editor", width="large")
def workflow_template_modal(wf_id=None):
    is_edit = wf_id is not None
    wf = get_wf(wf_id) if is_edit else None
    groups = st.session_state.groups
    gnames = [g["name"] for g in groups]

    st.markdown(f"#### {'Edit' if is_edit else 'New'} Workflow Template")
    tab_info, tab_stages, tab_fields = st.tabs(["📋 Basic Info", "🔗 Stages", "📝 Custom Fields"])

    with tab_info:
        t1, t2 = st.columns(2)
        wf_name   = t1.text_input("Template Name *", value=wf["name"] if wf else "")
        wf_sla    = t2.number_input("SLA Hours", min_value=1, value=wf["sla_hours"] if wf else 72)
        icon_opts = ["📄","💳","🧑‍💼","🔧","🚨","🤝","📊","🏗","💼","📦","🔍","⚡","🛡","🎯","📮"]
        cur_icon  = wf.get("icon","📋") if wf else "📋"
        wf_icon   = st.selectbox("Icon", icon_opts,
                                 index=icon_opts.index(cur_icon) if cur_icon in icon_opts else 0)
        wf_desc   = st.text_area("Description", value=wf.get("description","") if wf else "", height=80)
        wf_active = st.checkbox("Active", value=wf.get("active", True) if wf else True)

    with tab_stages:
        st.caption("Define stages in order. Each stage is owned by a group — only that group can advance past it.")
        existing_s = wf["stages"] if wf else []
        num_s = st.number_input("Number of stages", min_value=1, max_value=8,
                                value=max(len(existing_s), 1), step=1, key="ns_wf")
        new_stages = []
        for i in range(int(num_s)):
            st.markdown(f"**Stage {i+1}**")
            ex = existing_s[i] if i < len(existing_s) else {}
            sc1, sc2 = st.columns(2)
            sname = sc1.text_input("Stage Name *", value=ex.get("name",""),
                                   key=f"sn_{wf_id}_{i}", placeholder="e.g. Legal Review")
            cur_gn = group_name(ex.get("group_id","")) if ex.get("group_id") else (gnames[0] if gnames else "")
            gi  = gnames.index(cur_gn) if cur_gn in gnames else 0
            sgrp = sc2.selectbox("Assigned Group *", gnames, index=gi, key=f"sg_{wf_id}_{i}") if gnames else ""
            sdesc = st.text_input("Stage Description", value=ex.get("description",""),
                                  key=f"sd_{wf_id}_{i}", placeholder="What does this stage do?")
            if i < int(num_s)-1: st.markdown("<hr class='divider'>", unsafe_allow_html=True)
            gid = next((g["id"] for g in groups if g["name"]==sgrp), "") if sgrp else ""
            new_stages.append({"name": sname, "group_id": gid, "description": sdesc})

    with tab_fields:
        st.caption("Custom fields appear in the creation form. They collect the information needed to process this workflow.")
        existing_f = wf.get("custom_fields", []) if wf else []
        num_f = st.number_input("Number of custom fields", min_value=0, max_value=15,
                                value=len(existing_f), step=1, key="nf_wf")
        field_types = ["text","number","email","date","select","textarea"]
        new_fields = []
        for i in range(int(num_f)):
            ex = existing_f[i] if i < len(existing_f) else {}
            with st.expander(f"Field {i+1}: {ex.get('label','New Field')}",
                             expanded=(i < 2 or not ex.get("label"))):
                ff1, ff2, ff3 = st.columns([3, 2, 1])
                flabel = ff1.text_input("Field Label *", value=ex.get("label",""),
                                        key=f"fl_{wf_id}_{i}", placeholder="e.g. Contract Value")
                ftype_idx = field_types.index(ex.get("type","text")) \
                            if ex.get("type","text") in field_types else 0
                ftype = ff2.selectbox("Type", field_types, index=ftype_idx, key=f"ft_{wf_id}_{i}")
                freq  = ff3.checkbox("Required", value=ex.get("required", False), key=f"fr_{wf_id}_{i}")
                fp1, fp2 = st.columns(2)
                fplaceholder = fp1.text_input("Placeholder", value=ex.get("placeholder",""),
                                              key=f"fp_{wf_id}_{i}")
                fopts = []
                if ftype == "select":
                    raw = fp2.text_input("Options (comma-separated)",
                                         value=", ".join(ex.get("options",[])),
                                         key=f"fo_{wf_id}_{i}", placeholder="Option A, Option B")
                    fopts = [o.strip() for o in raw.split(",") if o.strip()]
                fid = ex.get("id") or f"f{i}_{str(uuid.uuid4())[:4]}"
                new_fields.append({"id":fid,"label":flabel,"type":ftype,
                                   "placeholder":fplaceholder,"options":fopts,"required":freq})

    st.markdown("<br>", unsafe_allow_html=True)
    fc1, _, fc3 = st.columns([1, 3, 1])
    with fc1:
        if st.button("Cancel", key="tpl_cancel"): st.rerun()
    with fc3:
        if st.button("Save Changes" if is_edit else "Create Template", key="tpl_save", type="primary"):
            errors = []
            if not wf_name.strip(): errors.append("Template name is required.")
            valid_s = [s for s in new_stages if s["name"].strip() and s["group_id"]]
            if not valid_s: errors.append("At least one complete stage (name + group) is required.")
            if errors:
                for e in errors: st.error(e)
            else:
                valid_f = [f for f in new_fields if f["label"].strip()]
                record = {
                    "id":           wf_id if is_edit else f"wf-{str(uuid.uuid4())[:8]}",
                    "name":         wf_name,
                    "description":  wf_desc,
                    "icon":         wf_icon,
                    "sla_hours":    int(wf_sla),
                    "active":       wf_active,
                    "stages":       valid_s,
                    "custom_fields": valid_f,
                }
                upsert_workflow(record)
                st.session_state.workflows = get_workflows()
                db_add_notif("ok" if not is_edit else "info",
                             f"Template '{wf_name}' {'created' if not is_edit else 'updated'}.")
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR  (permanent — always visible, no toggle)
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(
        '<div class="logo-bar">'
        '<div style="font-size:20px">⬡</div>'
        '<div>'
        '<div class="logo-name">WorkBench</div>'
        '<div class="logo-version">v3.2 · SQLite</div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True)

    au = [u for u in st.session_state.users if u["active"]]
    un = [u["name"] for u in au]
    ui = [u["id"]   for u in au]
    ci = ui.index(st.session_state.current_user_id) if st.session_state.current_user_id in ui else 0
    ch = st.selectbox("Logged in as", un, index=ci)
    st.session_state.current_user_id = ui[un.index(ch)]

    cu = current_user()
    gl = " · ".join([group_name(g) for g in cu["groups"]]) if cu["groups"] else "No groups assigned"
    rb = "badge-admin" if cu["role"] == "admin" else "badge-group"
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:10px;padding:8px 0 14px">'
        f'<div class="avatar">{initials(cu["name"])}</div>'
        f'<div style="font-size:12px;color:#94a3b8;line-height:1.6">'
        f'<span class="badge {rb}" style="font-size:10px">{cu["role"].upper()}</span><br>'
        f'<span style="color:#64748b;font-size:11px">{gl}</span>'
        f'</div></div>',
        unsafe_allow_html=True)

    st.markdown("---")

    nav_opts = ["⬡  Dashboard","📋  My Tasks","🗂  All Workflows","📊  Analytics","🔔  Notifications"]
    if is_admin(): nav_opts.append("⚙️  Admin")
    nav  = st.radio("", nav_opts, label_visibility="collapsed")
    page = nav.split("  ")[1]

    st.markdown("---")

    tasks = st.session_state.tasks
    done  = sum(1 for t in tasks if t["status"] == "Done")
    st.markdown(
        f'<div style="font-size:11px;color:#475569;font-family:IBM Plex Mono,monospace;line-height:2">'
        f'<div>Completed: <span style="color:#34d399">{done}</span></div>'
        f'<div>Total: <span style="color:#94a3b8">{len(tasks)}</span></div>'
        f'</div>',
        unsafe_allow_html=True)

cu    = current_user()
tasks = st.session_state.tasks

# ══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
if page == "Dashboard":
    st.markdown('<div class="page-title">Operations Dashboard</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="page-sub">{datetime.now().strftime("%A, %d %B %Y")} - {cu["name"]}</div>',
                unsafe_allow_html=True)

    tt = len(tasks)
    dt = sum(1 for t in tasks if t["status"]=="Done")
    at = sum(1 for t in tasks if t["status"]=="In Progress")
    bt = sum(1 for t in tasks if t["status"]=="Blocked")

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="metric-card blue"><div class="metric-label">Total Workflows</div><div class="metric-value">{tt}</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="metric-card green"><div class="metric-label">Completed</div><div class="metric-value">{dt}</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="metric-card amber"><div class="metric-label">In Progress</div><div class="metric-value">{at}</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="metric-card red"><div class="metric-label">Blocked</div><div class="metric-value">{bt}</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    left, right = st.columns([2, 1])

    with left:
        st.markdown('<div class="section-header"><h2>Active Queue</h2></div>', unsafe_allow_html=True)
        aq = sorted([t for t in tasks if t["status"]!="Done"],
                    key=lambda x: ["critical","high","medium","low"].index(x["priority"]))
        if not aq:
            st.markdown('<div style="padding:40px;text-align:center;color:#475569;font-size:14px">'
                        'No active workflows. Create one in All Workflows.</div>', unsafe_allow_html=True)
        for t in aq[:8]:
            wf  = get_wf(t["workflow_id"])
            can = can_advance(t)
            sn  = sg = ""
            if wf and t["stage_index"] < len(wf["stages"]):
                cs = wf["stages"][t["stage_index"]]
                sn = cs["name"]; sg = group_name(cs["group_id"])
            ct, cb = st.columns([6, 1])
            with ct:
                st.markdown(
                    f'<div class="task-row">{pdot(t["priority"])}'
                    f'<div style="flex:1;min-width:0">'
                    f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;flex-wrap:wrap">'
                    f'<span style="font-family:IBM Plex Mono,monospace;font-size:11px;color:#475569">{t["id"]}</span>'
                    f'{sbadge(t["status"])} {sla_lbl(t)}</div>'
                    f'<div style="font-size:13px;color:#e2e8f0;font-weight:500">{t["title"]}</div>'
                    f'<div style="font-size:11px;color:#64748b;margin-top:3px;font-family:IBM Plex Mono,monospace">'
                    f'{wf["name"] if wf else "?"} - {sn} - awaiting {sg}</div>'
                    f'{pbar(t["progress"])}</div></div>', unsafe_allow_html=True)
            with cb:
                st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
                if t["status"] != "Done":
                    if can:
                        if st.button("->", key=f"da_{t['id']}"):
                            advance_task(t["id"]); st.rerun()
                    else:
                        st.markdown('<div style="font-size:20px;text-align:center" title="Not your group">🔒</div>',
                                    unsafe_allow_html=True)

    with right:
        st.markdown('<div class="section-header"><h2>Live Feed</h2></div>', unsafe_allow_html=True)
        notifs = st.session_state.notifications
        if not notifs:
            st.markdown('<div style="color:#475569;font-size:13px">No notifications yet.</div>',
                        unsafe_allow_html=True)
        for n in notifs[:6]:
            cls  = {"info":"","warn":"warn","error":"error","ok":"ok"}.get(n["type"],"")
            icon = {"info":"i","warn":"!","error":"x","ok":"✓"}.get(n["type"],"·")
            st.markdown(
                f'<div class="notif {cls}">'
                f'<div style="font-size:13px;color:#cbd5e1">{icon} {n["msg"]}</div>'
                f'<div class="notif-time">{n["time"]}</div></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="section-header"><h2>By Status</h2></div>', unsafe_allow_html=True)
        for s, c in [("New","#3b82f6"),("In Progress","#f59e0b"),("In Review","#8b5cf6"),
                     ("Done","#10b981"),("Blocked","#ef4444")]:
            cnt = sum(1 for t in tasks if t["status"]==s)
            pct = int(cnt / max(tt, 1) * 100)
            st.markdown(
                f'<div style="margin-bottom:10px">'
                f'<div style="display:flex;justify-content:space-between;font-size:12px;'
                f'color:#94a3b8;margin-bottom:3px">'
                f'<span>{s}</span>'
                f'<span style="font-family:IBM Plex Mono,monospace">{cnt}</span></div>'
                f'{pbar(pct, c)}</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  MY TASKS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "My Tasks":
    st.markdown('<div class="page-title">My Tasks</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="page-sub">Tasks where your group is the current stage owner - {cu["name"]}</div>',
                unsafe_allow_html=True)

    my_gids = set(cu["groups"])

    def needs_me(t):
        if t["status"] == "Done": return False
        wf = get_wf(t["workflow_id"])
        if not wf or t["stage_index"] >= len(wf["stages"]): return False
        return wf["stages"][t["stage_index"]]["group_id"] in my_gids

    my_tasks = ([t for t in tasks if t["status"]!="Done"] if is_admin()
                else [t for t in tasks if needs_me(t)])

    tab_act, tab_done = st.tabs([f"Action Required ({len(my_tasks)})", "Completed"])

    def render_task(t, show_actions=True):
        wf  = get_wf(t["workflow_id"])
        can = can_advance(t)
        sn  = sg = ""
        if wf and t["stage_index"] < len(wf["stages"]):
            cs = wf["stages"][t["stage_index"]]
            sn = cs["name"]; sg = group_name(cs["group_id"])
        elif t["status"] == "Done":
            sn = "Complete"

        with st.expander(f"**{t['id']}** - {t['title']} - {sn}", expanded=False):
            st.markdown(stage_rail(t), unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            c1.metric("Priority", t["priority"].capitalize())
            c2.metric("Progress", f"{t['progress']}%")
            c3.metric("Stage", f"{t['stage_index']}/{len(wf['stages']) if wf else '?'}")

            st.markdown(
                f'<div style="font-size:13px;color:#94a3b8;line-height:2;margin:12px 0">'
                f'<b style="color:#64748b">Workflow</b>&nbsp;&nbsp;{wf["name"] if wf else "?"}<br>'
                f'<b style="color:#64748b">Current stage</b>&nbsp;&nbsp;{sn}<br>'
                f'<b style="color:#64748b">Assigned group</b>&nbsp;&nbsp;{sg}<br>'
                f'<b style="color:#64748b">Due</b>&nbsp;&nbsp;{t.get("due","—")}<br>'
                f'<b style="color:#64748b">Created</b>&nbsp;&nbsp;{t["created"]} by {t["created_by"]}</div>',
                unsafe_allow_html=True)

            cf     = t.get("custom_fields", {})
            wf_cf  = wf.get("custom_fields", []) if wf else []
            if cf and wf_cf:
                with st.expander("Submission Details"):
                    for f in wf_cf:
                        v = cf.get(f["id"], "")
                        if v: st.markdown(f"**{f['label']}:** {v}")

            if t.get("description"):
                st.markdown(f"**Description:** {t['description']}")

            st.markdown("**Activity History**")
            for h in reversed(t["history"]):
                st.markdown(
                    f'<div class="timeline-item"><div class="tl-dot"></div>'
                    f'<div><div class="tl-text">{h["action"]} '
                    f'<span style="color:#475569">— {h["by"]}</span></div>'
                    f'<div class="tl-time">{h["time"]}</div></div></div>',
                    unsafe_allow_html=True)

            if show_actions and t["status"] != "Done":
                st.markdown("---")
                b1, b2, b3 = st.columns(3)
                with b1:
                    if can:
                        if st.button("Advance Stage", key=f"adv_{t['id']}", type="primary"):
                            advance_task(t["id"]); st.rerun()
                    else:
                        st.markdown(
                            f'<div class="lock-notice">Awaiting <b>{sg}</b> — not your group</div>',
                            unsafe_allow_html=True)
                with b2:
                    if t["status"] != "Blocked":
                        if st.button("Mark Blocked", key=f"blk_{t['id']}"):
                            t["status"] = "Blocked"
                            upsert_task(t)
                            add_history(t["id"], "Marked as Blocked", cu["name"])
                            db_add_notif("error", f"{t['id']} marked Blocked by {cu['name']}.")
                            # Email the group that owns the blocked stage
                            _bwf = get_wf(t["workflow_id"])
                            if _bwf and t["stage_index"] < len(_bwf["stages"]):
                                _bstage = _bwf["stages"][t["stage_index"]]
                                notify_task_blocked(
                                    group_email=group_email(_bstage["group_id"]),
                                    group_name=group_name(_bstage["group_id"]),
                                    task_id=t["id"], task_title=t["title"],
                                    workflow=_bwf["name"], stage=_bstage["name"],
                                    priority=t["priority"], due=t.get("due",""),
                                    blocked_by=cu["name"])
                            st.session_state.tasks = get_tasks(); st.rerun()
                    else:
                        if st.button("Unblock", key=f"unblk_{t['id']}"):
                            t["status"] = "In Progress"
                            upsert_task(t)
                            add_history(t["id"], "Unblocked", cu["name"])
                            st.session_state.tasks = get_tasks(); st.rerun()
                with b3:
                    cmt = st.text_input("", placeholder="Add comment...",
                                        key=f"ci_{t['id']}", label_visibility="collapsed")
                    if st.button("Post Comment", key=f"cb_{t['id']}") and cmt:
                        add_history(t["id"], f"Comment: {cmt}", cu["name"])
                        st.session_state.tasks = get_tasks(); st.rerun()

    with tab_act:
        if not my_tasks:
            st.markdown('<div style="padding:40px;text-align:center;color:#475569;font-size:14px">'
                        'No tasks require your attention right now.</div>', unsafe_allow_html=True)
        for t in my_tasks: render_task(t)

    with tab_done:
        dt_list = [t for t in tasks if t["status"]=="Done"]
        if not dt_list:
            st.markdown('<div style="padding:40px;text-align:center;color:#475569;font-size:14px">'
                        'No completed tasks yet.</div>', unsafe_allow_html=True)
        for t in dt_list: render_task(t, show_actions=False)

# ══════════════════════════════════════════════════════════════════════════════
#  ALL WORKFLOWS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "All Workflows":
    st.markdown('<div class="page-title">All Workflows</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="page-sub">{len(tasks)} total instances</div>', unsafe_allow_html=True)

    col_new, col_s, col_f1, col_f2 = st.columns([1.2, 2.5, 1.5, 1.5])
    with col_new:
        if st.button("New Workflow", type="primary"):
            st.session_state.modal_step  = 1
            st.session_state.modal_wf_id = None
            new_workflow_modal()
    with col_s:
        search = st.text_input("", placeholder="Search by title or ID...", label_visibility="collapsed")
    with col_f1:
        wfn = ["All"] + [w["name"] for w in st.session_state.workflows if w["active"]]
        fwf = st.selectbox("Workflow", wfn, label_visibility="collapsed")
    with col_f2:
        fstatus = st.selectbox("Status", ["All","New","In Progress","Blocked","Done"],
                               label_visibility="collapsed")

    filtered = tasks
    if search:
        filtered = [t for t in filtered
                    if search.lower() in t["title"].lower() or search.lower() in t["id"].lower()]
    if fwf != "All":
        wo = next((w for w in st.session_state.workflows if w["name"]==fwf), None)
        if wo: filtered = [t for t in filtered if t["workflow_id"]==wo["id"]]
    if fstatus != "All":
        filtered = [t for t in filtered if t["status"]==fstatus]

    st.markdown(
        f'<div style="font-size:12px;color:#475569;margin:10px 0;font-family:IBM Plex Mono,monospace">'
        f'{len(filtered)} result(s)</div>', unsafe_allow_html=True)

    hcols = st.columns([0.4, 0.8, 2.5, 1.2, 0.9, 1.6, 1.2, 0.9, 0.8])
    for lbl, col in zip(["","ID","Title","Workflow","Status","Stage - Group","SLA","Priority",""], hcols):
        col.markdown(
            f"<span style='font-size:10px;font-weight:700;letter-spacing:.1em;"
            f"text-transform:uppercase;color:#475569;font-family:IBM Plex Mono,monospace'>{lbl}</span>",
            unsafe_allow_html=True)

    if not filtered:
        st.markdown('<div style="padding:40px;text-align:center;color:#475569;font-size:14px">'
                    'No workflows found. Click New Workflow to get started.</div>', unsafe_allow_html=True)

    for t in filtered:
        wf  = get_wf(t["workflow_id"])
        can = can_advance(t)
        sn  = sg = ""
        if wf and t["stage_index"] < len(wf["stages"]):
            cs = wf["stages"][t["stage_index"]]
            sn = cs["name"]; sg = group_name(cs["group_id"])
        elif t["status"] == "Done":
            sn = "Complete"

        c0,c1,c2,c3,c4,c5,c6,c7,c8 = st.columns([0.4,0.8,2.5,1.2,0.9,1.6,1.2,0.9,0.8])
        c0.markdown(pdot(t["priority"]), unsafe_allow_html=True)
        c1.markdown(f"<span style='font-family:IBM Plex Mono,monospace;font-size:12px;color:#60a5fa'>{t['id']}</span>",
                    unsafe_allow_html=True)
        c2.markdown(f"<span style='font-size:13px;color:#e2e8f0'>{t['title'][:36]}{'...' if len(t['title'])>36 else ''}</span>",
                    unsafe_allow_html=True)
        c3.markdown(f"<span style='font-size:12px;color:#94a3b8'>{wf['name'] if wf else '?'}</span>",
                    unsafe_allow_html=True)
        c4.markdown(sbadge(t["status"]), unsafe_allow_html=True)
        c5.markdown(
            f"<span style='font-size:12px;color:#64748b'>{sn}<br>"
            f"<span style='font-size:10px;color:#475569;font-family:IBM Plex Mono,monospace'>{sg}</span></span>",
            unsafe_allow_html=True)
        c6.markdown(sla_lbl(t), unsafe_allow_html=True)
        c7.markdown(f"<span style='font-size:12px;color:#94a3b8'>{t['priority']}</span>",
                    unsafe_allow_html=True)
        with c8:
            if t["status"] != "Done":
                if can:
                    if st.button("->", key=f"aa_{t['id']}"): advance_task(t["id"]); st.rerun()
                else:
                    st.markdown("🔒")
        st.markdown("<hr class='divider'>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  ANALYTICS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Analytics":
    st.markdown('<div class="page-title">Analytics</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Live operational intelligence</div>', unsafe_allow_html=True)

    tab_a, tab_b, tab_c = st.tabs(["Throughput","Team Performance","Kanban"])

    with tab_a:
        if not tasks:
            st.info("No workflow data yet.")
        else:
            wc = {}
            for t in tasks:
                w = get_wf(t["workflow_id"])
                n = w["name"] if w else "Unknown"
                wc[n] = wc.get(n, 0) + 1
            st.markdown("**Instances by Workflow Type**")
            st.bar_chart(wc)
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Status Distribution**")
                sc = {}
                for t in tasks: sc[t["status"]] = sc.get(t["status"], 0) + 1
                st.bar_chart(sc)
            with c2:
                st.markdown("**Priority Breakdown**")
                pc = {}
                for t in tasks: pc[t["priority"]] = pc.get(t["priority"], 0) + 1
                st.bar_chart(pc)

    with tab_b:
        st.markdown("**Workflow Stages per Group**")
        gc = {}
        for g in st.session_state.groups:
            gc[g["name"]] = sum(
                1 for t in tasks
                for w in [get_wf(t["workflow_id"])] if w
                for s in w["stages"] if s["group_id"]==g["id"]
            )
        if any(v > 0 for v in gc.values()):
            st.bar_chart(gc)
        else:
            st.info("No task data yet.")
        st.markdown("<br>**User Roster**", unsafe_allow_html=True)
        for u in st.session_state.users:
            gs = ", ".join([group_name(g) for g in u["groups"]]) or "No groups"
            rb = "badge-admin" if u["role"]=="admin" else "badge-group"
            st.markdown(
                f'<div class="task-row" style="padding:12px 16px">'
                f'<div class="avatar">{initials(u["name"])}</div>'
                f'<div style="flex:1;font-size:13px;font-weight:500;color:#e2e8f0">{u["name"]}</div>'
                f'<div style="font-size:12px;color:#64748b;flex:1">{gs}</div>'
                f'<span class="badge {rb}">{u["role"]}</span></div>',
                unsafe_allow_html=True)

    with tab_c:
        st.markdown("**Kanban Board**")
        kc = st.columns(4)
        kcolors = {"New":"#3b82f6","In Progress":"#f59e0b","Blocked":"#ef4444","Done":"#10b981"}
        for col, s in zip(kc, ["New","In Progress","Blocked","Done"]):
            ct    = [t for t in tasks if t["status"]==s]
            color = kcolors[s]
            col.markdown(
                f'<div style="background:#111827;border:1px solid #1e2736;'
                f'border-top:3px solid {color};border-radius:8px;padding:12px;min-height:220px">'
                f'<div style="font-size:11px;font-weight:700;letter-spacing:.1em;'
                f'text-transform:uppercase;color:{color};margin-bottom:10px">{s} - {len(ct)}</div>',
                unsafe_allow_html=True)
            for t in ct[:5]:
                w = get_wf(t["workflow_id"])
                col.markdown(
                    f'<div style="background:#0d1117;border:1px solid #1e2736;border-radius:6px;'
                    f'padding:10px;margin-bottom:8px">'
                    f'<div style="font-family:IBM Plex Mono,monospace;font-size:10px;color:#475569">{t["id"]}</div>'
                    f'<div style="font-size:12px;color:#cbd5e1;font-weight:500;margin:4px 0">'
                    f'{t["title"][:26]}{"..." if len(t["title"])>26 else ""}</div>'
                    f'<div style="font-size:11px;color:#64748b">'
                    f'{w["name"] if w else "?"} - {t["priority"]}</div></div>',
                    unsafe_allow_html=True)
            if len(ct) > 5:
                col.markdown(
                    f'<div style="font-size:11px;color:#475569;text-align:center">+{len(ct)-5} more</div>',
                    unsafe_allow_html=True)
            col.markdown("</div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  NOTIFICATIONS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Notifications":
    notifs = st.session_state.notifications
    st.markdown('<div class="page-title">Notifications</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="page-sub">{len(notifs)} system alerts</div>', unsafe_allow_html=True)

    cc, _ = st.columns([1, 4])
    with cc:
        if st.button("Clear All"):
            clear_notifications()
            st.session_state.notifications = []
            st.rerun()

    if not notifs:
        st.markdown(
            '<div style="text-align:center;padding:60px 0;color:#475569">'
            '<div style="font-size:40px">🔔</div>'
            '<div style="font-size:14px;margin-top:12px">No notifications</div></div>',
            unsafe_allow_html=True)

    for n in notifs:
        cls  = {"info":"","warn":"warn","error":"error","ok":"ok"}.get(n["type"],"")
        icon = {"info":"i","warn":"!","error":"x","ok":"✓"}.get(n["type"],"·")
        lbl  = {"info":"INFO","warn":"WARNING","error":"ERROR","ok":"SUCCESS"}.get(n["type"],"")
        clr  = {"info":"#60a5fa","warn":"#fbbf24","error":"#f87171","ok":"#34d399"}.get(n["type"],"#60a5fa")
        st.markdown(
            f'<div class="notif {cls}" style="padding:16px 20px;margin-bottom:10px">'
            f'<div style="font-family:IBM Plex Mono,monospace;font-size:10px;font-weight:700;'
            f'color:{clr};letter-spacing:.1em;margin-bottom:6px">{lbl}</div>'
            f'<div style="font-size:14px;color:#e2e8f0">{icon} {n["msg"]}</div>'
            f'<div class="notif-time">{n["time"]}</div></div>',
            unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  ADMIN
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Admin":
    if not is_admin():
        st.error("Access denied — admin only.")
        st.stop()

    st.markdown('<div class="page-title">Administration</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Users, groups, workflow templates, and system settings</div>',
                unsafe_allow_html=True)

    tab_u, tab_g, tab_w, tab_s = st.tabs(["👤 Users","👥 Groups","⚙ Workflow Templates","🔧 Settings"])

    # ── USERS ─────────────────────────────────────────────────────────────────
    with tab_u:
        ch2, cb2 = st.columns([3, 1])
        ch2.markdown('<div class="section-header"><h2>User Management</h2></div>', unsafe_allow_html=True)
        with cb2:
            if st.button("Add User", type="primary", key="btn_au"):
                st.session_state["show_au"] = not st.session_state.get("show_au", False)

        if st.session_state.get("show_au"):
            with st.form("form_au"):
                st.markdown("**New User**")
                a1, a2 = st.columns(2)
                nn = a1.text_input("Full Name *")
                ne = a2.text_input("Email *")
                a3, a4 = st.columns(2)
                nr = a3.selectbox("Role", ["member","admin"])
                ng = a4.multiselect("Assign to Groups", [g["name"] for g in st.session_state.groups])
                if st.form_submit_button("Create User", type="primary"):
                    if not nn or not ne:
                        st.error("Name and email are required.")
                    elif any(u["email"]==ne for u in st.session_state.users):
                        st.error("A user with that email already exists.")
                    else:
                        gids = [g["id"] for g in st.session_state.groups if g["name"] in ng]
                        uid  = f"user-{str(uuid.uuid4())[:8]}"
                        new_u = {"id":uid,"name":nn,"email":ne,"role":nr,
                                 "groups":gids,"active":True,"created":_now()}
                        upsert_user(new_u)
                        # Sync group member lists
                        for g in st.session_state.groups:
                            if g["id"] in gids and uid not in g["members"]:
                                g["members"].append(uid)
                                upsert_group(g)
                        db_add_notif("ok", f"User '{nn}' created as {nr}.")
                        st.session_state.users  = get_users()
                        st.session_state.groups = get_groups()
                        st.session_state["show_au"] = False
                        st.rerun()

        for u in st.session_state.users:
            ini = initials(u["name"])
            gh  = " ".join([f'<span class="group-chip">{group_name(g)}</span>' for g in u["groups"]]) \
                  or '<span style="color:#475569;font-size:12px">No groups</span>'
            rb  = "badge-admin" if u["role"]=="admin" else "badge-group"
            ab  = "badge-done"  if u["active"] else "badge-blocked"
            cu2, ce2 = st.columns([6, 1])
            with cu2:
                st.markdown(
                    f'<div class="task-row" style="padding:14px 18px;align-items:flex-start">'
                    f'<div class="avatar-lg">{ini}</div>'
                    f'<div style="flex:1">'
                    f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">'
                    f'<span style="font-size:14px;font-weight:600;color:#e2e8f0">{u["name"]}</span>'
                    f'<span class="badge {rb}">{u["role"]}</span>'
                    f'<span class="badge {ab}">{"Active" if u["active"] else "Inactive"}</span></div>'
                    f'<div style="font-size:12px;color:#64748b;font-family:IBM Plex Mono,monospace;margin-bottom:6px">{u["email"]}</div>'
                    f'<div>{gh}</div></div></div>',
                    unsafe_allow_html=True)
            with ce2:
                if u["id"] != "user-admin":
                    with st.expander("Edit"):
                        agn     = [g["name"] for g in st.session_state.groups]
                        cgn     = [group_name(g) for g in u["groups"]]
                        ug      = st.multiselect("Groups", agn, default=cgn, key=f"ug_{u['id']}")
                        ur      = st.selectbox("Role", ["member","admin"],
                                               index=0 if u["role"]=="member" else 1, key=f"ur_{u['id']}")
                        if st.button("Save", key=f"su_{u['id']}", type="primary"):
                            ng2 = [g["id"] for g in st.session_state.groups if g["name"] in ug]
                            for g in st.session_state.groups:
                                changed = False
                                if u["id"] in g["members"] and g["id"] not in ng2:
                                    g["members"].remove(u["id"]); changed = True
                                if g["id"] in ng2 and u["id"] not in g["members"]:
                                    g["members"].append(u["id"]); changed = True
                                if changed: upsert_group(g)
                            u["groups"] = ng2; u["role"] = ur
                            upsert_user(u)
                            db_add_notif("info", f"User '{u['name']}' updated.")
                            st.session_state.users  = get_users()
                            st.session_state.groups = get_groups()
                            st.rerun()
                        toggle = "Deactivate" if u["active"] else "Reactivate"
                        if st.button(toggle, key=f"dt_{u['id']}"):
                            u["active"] = not u["active"]
                            upsert_user(u)
                            st.session_state.users = get_users()
                            st.rerun()

    # ── GROUPS ────────────────────────────────────────────────────────────────
    with tab_g:
        cgh, cgb = st.columns([3, 1])
        cgh.markdown('<div class="section-header"><h2>Group Management</h2></div>', unsafe_allow_html=True)
        with cgb:
            if st.button("Add Group", type="primary", key="btn_ag"):
                st.session_state["show_ag"] = not st.session_state.get("show_ag", False)

        if st.session_state.get("show_ag"):
            with st.form("form_ag"):
                st.markdown("**New Group**")
                g1, g2 = st.columns(2)
                gn = g1.text_input("Group Name *")
                gc = g2.selectbox("Accent Color",
                                   ["#3b82f6","#10b981","#8b5cf6","#f59e0b","#ec4899","#ef4444","#06b6d4"])
                gd = st.text_input("Description")
                ge = st.text_input("Group Email Address",
                                   placeholder="e.g. engineering@company.com",
                                   help="Workflow notifications will be sent to this address")
                if st.form_submit_button("Create Group", type="primary"):
                    if not gn:
                        st.error("Name required.")
                    elif any(g["name"].lower()==gn.lower() for g in st.session_state.groups):
                        st.error("Group name already exists.")
                    else:
                        new_g = {"id":f"grp-{str(uuid.uuid4())[:8]}","name":gn,
                                 "description":gd,"color":gc,"email":ge,
                                 "members":[],"created":_now()}
                        upsert_group(new_g)
                        db_add_notif("ok", f"Group '{gn}' created.")
                        st.session_state.groups = get_groups()
                        st.session_state["show_ag"] = False
                        st.rerun()

        for g in st.session_state.groups:
            mn = [get_user(m)["name"] if get_user(m) else m for m in g["members"]]
            mh = " ".join([f'<span class="group-chip">{n}</span>' for n in mn]) \
                 or '<span style="color:#475569;font-size:12px">No members yet</span>'
            cg2, cge = st.columns([6, 1])
            with cg2:
                _gemail_display = (f'<span style="font-size:11px;color:#475569;'  
                    f'font-family:IBM Plex Mono,monospace">✉ {g["email"]}</span>')\
                    if g.get("email") else \
                    '<span style="font-size:11px;color:#475569;font-style:italic">No email set</span>'
                st.markdown(
                    f'<div class="task-row" style="padding:14px 18px;align-items:flex-start">'
                    f'<div style="width:12px;height:40px;border-radius:3px;background:{g["color"]};flex-shrink:0"></div>'
                    f'<div style="flex:1">'
                    f'<div style="font-size:14px;font-weight:600;color:#e2e8f0;margin-bottom:3px">{g["name"]}</div>'
                    f'<div style="font-size:12px;color:#64748b;margin-bottom:4px">{g.get("description","")}</div>'
                    f'<div style="margin-bottom:6px">{_gemail_display}</div>'
                    f'<div>{mh}</div></div>'
                    f'<div style="font-family:IBM Plex Mono,monospace;font-size:12px;color:#64748b;flex-shrink:0">'
                    f'{len(g["members"])} member(s)</div></div>',
                    unsafe_allow_html=True)
            with cge:
                with st.expander("Edit"):
                    nd  = st.text_input("Description", value=g.get("description",""), key=f"gd_{g['id']}")
                    ne  = st.text_input("Group Email Address", value=g.get("email",""),
                                        key=f"ge_{g['id']}",
                                        placeholder="e.g. engineering@company.com",
                                        help="Workflow notifications sent to this address")
                    aun = [u["name"] for u in st.session_state.users if u["active"]]
                    cun = [get_user(m)["name"] for m in g["members"] if get_user(m)]
                    nm  = st.multiselect("Members", aun, default=cun, key=f"gm_{g['id']}")
                    if st.button("Save", key=f"sg_{g['id']}", type="primary"):
                        nm2 = [u["id"] for u in st.session_state.users if u["name"] in nm]
                        for u in st.session_state.users:
                            changed = False
                            if u["id"] in nm2 and g["id"] not in u["groups"]:
                                u["groups"].append(g["id"]); changed = True
                            elif u["id"] not in nm2 and g["id"] in u["groups"]:
                                u["groups"].remove(g["id"]); changed = True
                            if changed: upsert_user(u)
                        g["members"] = nm2; g["description"] = nd; g["email"] = ne
                        upsert_group(g)
                        db_add_notif("info", f"Group '{g['name']}' updated.")
                        st.session_state.groups = get_groups()
                        st.session_state.users  = get_users()
                        st.rerun()

    # ── WORKFLOW TEMPLATES ────────────────────────────────────────────────────
    with tab_w:
        cwh, cwb = st.columns([3, 1])
        cwh.markdown('<div class="section-header"><h2>Workflow Templates</h2></div>', unsafe_allow_html=True)
        with cwb:
            if st.button("New Template", type="primary", key="btn_nt"):
                workflow_template_modal(wf_id=None)

        for wf in st.session_state.workflows:
            ic = sum(1 for t in tasks if t["workflow_id"]==wf["id"])
            ab = "badge-done" if wf["active"] else "badge-blocked"
            ss = " -> ".join([
                f'{s["name"]} <span style="font-size:10px;color:#475569">({group_name(s["group_id"])})</span>'
                for s in wf["stages"]])
            nf = len(wf.get("custom_fields", []))
            cwf2, cwe = st.columns([6, 1])
            with cwf2:
                st.markdown(
                    f'<div class="task-row" style="padding:14px 18px;align-items:flex-start">'
                    f'<div style="font-size:24px;margin-right:4px;flex-shrink:0">{wf.get("icon","📋")}</div>'
                    f'<div style="flex:1">'
                    f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">'
                    f'<span style="font-size:14px;font-weight:600;color:#e2e8f0">{wf["name"]}</span>'
                    f'<span class="badge {ab}">{"Active" if wf["active"] else "Inactive"}</span>'
                    f'<span style="font-family:IBM Plex Mono,monospace;font-size:11px;color:#475569">SLA {wf["sla_hours"]}h</span></div>'
                    f'<div style="font-size:12px;color:#64748b;margin-bottom:6px">{wf.get("description","")}</div>'
                    f'<div style="font-size:12px;color:#94a3b8">{ss}</div>'
                    f'<div style="font-size:11px;color:#475569;margin-top:4px;font-family:IBM Plex Mono,monospace">'
                    f'{nf} custom field(s)</div></div>'
                    f'<div style="font-family:IBM Plex Mono,monospace;font-size:12px;color:#64748b;flex-shrink:0">'
                    f'{ic} instance(s)</div></div>',
                    unsafe_allow_html=True)
            with cwe:
                if st.button("Edit", key=f"ewf_{wf['id']}"):
                    workflow_template_modal(wf_id=wf["id"])

    # ── SETTINGS ──────────────────────────────────────────────────────────────
    with tab_s:
        st.markdown('<div class="section-header"><h2>System Settings</h2></div>', unsafe_allow_html=True)
        cfg = st.session_state.settings
        c1, c2 = st.columns(2)
        with c1:
            cfg["sla_warn_hours"] = st.slider(
                "SLA Warning Threshold (hours)", 1, 24, int(cfg.get("sla_warn_hours", 4)))
            cfg["auto_escalate"] = st.checkbox(
                "Auto-escalate on SLA breach", value=bool(cfg.get("auto_escalate", True)))
        with c2:
            strats = ["Manual","Round Robin","Load Balanced"]
            cfg["default_strategy"] = st.selectbox(
                "Default Assignment Strategy", strats,
                index=strats.index(cfg.get("default_strategy","Manual")))

        if st.button("Save Settings", type="primary"):
            save_settings(cfg)
            st.session_state.settings = get_settings()
            st.success("Settings saved to database.")
            db_add_notif("ok", "System settings updated.")

    st.markdown("---")
    st.markdown('<div class="section-header"><h2>Email Notifications</h2></div>',
                unsafe_allow_html=True)
    if email_is_configured():
        st.success("Email is configured and enabled.")
        if st.button("Send Test Email", key="test_email"):
            ok, err = test_connection()
            if ok:
                st.success("Test email sent successfully! Check your inbox.")
            else:
                st.error(f"Failed to send: {err}")
    else:
        st.warning("Email notifications are not configured.")
        st.markdown('''**To enable email notifications:**
1. Add your SMTP credentials to `.streamlit/secrets.toml`
2. Set a **Group Email Address** on each group in the Groups tab
3. WorkBench will automatically email the group when tasks are assigned, advanced, blocked, or completed

```toml
[email]
smtp_host     = "smtp.gmail.com"
smtp_port     = 587
smtp_user     = "gabetb13@gmail.com"
smtp_password = "Popcornpop51!"
from_name     = "WorkBench"
enabled       = true
```''')
