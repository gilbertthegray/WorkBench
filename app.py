"""
WorkBench - approval workflows for teams
Run:  streamlit run app.py      (Streamlit >= 1.37)
Needs database.py next to this file; email_service.py is optional.
"""
import csv, io, re, uuid
from datetime import datetime, time, timedelta
from html import escape as esc
from pathlib import Path

import streamlit as st

from database import (
    init_db, needs_seed, get_users, upsert_user, get_groups, upsert_group,
    get_workflows, upsert_workflow, get_tasks, upsert_task, add_history,
    get_notifications, add_notification, clear_notifications,
    increment_task_counter, get_settings, save_settings,
)

try:
    from email_service import (notify_task_assigned, notify_task_advanced, notify_task_blocked,
                               notify_task_completed, email_is_configured, test_connection)
except ImportError:
    def _no(*a, **k): return False, "email_service not found"
    notify_task_assigned = notify_task_advanced = notify_task_blocked = notify_task_completed = _no
    def email_is_configured(): return False
    def test_connection(): return False, "email_service not found"

# Streamlit reads its theme only at startup, so write a light-theme config if none exists.
try:
    _cfg = Path(".streamlit/config.toml")
    if not _cfg.exists():
        _cfg.parent.mkdir(exist_ok=True)
        _cfg.write_text('[theme]\nbase = "light"\nprimaryColor = "#2563eb"\nbackgroundColor = "#ffffff"\n'
                        'secondaryBackgroundColor = "#f8fafc"\ntextColor = "#0f172a"\n')
except OSError:
    pass

st.set_page_config(page_title="WorkBench", layout="wide", initial_sidebar_state="expanded")

# ───────────────────────────── styling ─────────────────────────────
_GLOBAL = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
:root{--blue:#2563eb;--ink:#0f172a;--mute:#475569;--line:#e2e8f0;--tint:#eff6ff;color-scheme:light}
html,body,.stApp,[data-testid="stAppViewContainer"],[data-testid="stSidebar"],[data-testid="stDialog"] div[role="dialog"],
[data-testid="stToast"],[data-baseweb="popover"]>div,[data-baseweb="menu"],[data-baseweb="calendar"]{background:#fff!important}
.stApp *,[data-testid="stDialog"] *,[data-baseweb="popover"] *,[data-testid="stToast"] *{color:var(--ink)!important}
"""
_COMPONENTS = """
html,body,.stApp{font-family:'Inter',sans-serif}
#MainMenu,footer,[data-testid="stToolbar"],[data-testid="stHeader"]{visibility:hidden;height:0}
[data-testid="stSidebarCollapseButton"],[data-testid="collapsedControl"]{display:none}
.block-container{padding:2rem 2.5rem 3rem;max-width:1320px}
[data-testid="stSidebar"]{border-right:1px solid var(--line)}
[data-testid="stSidebar"] .block-container{padding:1.5rem 1rem}
hr{border-color:var(--line);margin:1rem 0}
.brand{font-size:19px;font-weight:700;letter-spacing:-.02em;padding:4px 0 20px}.brand span{color:var(--blue)}
.page-title{font-size:26px;font-weight:650;letter-spacing:-.02em}
.page-sub{font-size:14px;color:var(--mute);margin:2px 0 22px}
.sec{font-size:15px;font-weight:650;margin:6px 0 12px}
.muted{color:var(--mute);font-size:12.5px}
.id{color:var(--mute);font-size:12.5px;font-variant-numeric:tabular-nums}
.th{font-size:12px;font-weight:600;color:var(--mute)}
.card{background:#fff;border:1px solid var(--line);border-radius:10px;padding:14px 18px;margin-bottom:10px}
.stat{background:#fff;border:1px solid var(--line);border-radius:10px;padding:16px 18px}
.stat .l{font-size:13px;color:var(--mute);margin-bottom:6px}.stat .v{font-size:28px;font-weight:650;letter-spacing:-.02em}
.pill{display:inline-flex;align-items:center;gap:6px;background:#f1f5f9;border-radius:999px;padding:2px 10px;font-size:12.5px;font-weight:550;white-space:nowrap}
.pill i,.dot{width:7px;height:7px;border-radius:50%;display:inline-block;flex-shrink:0}
.p-critical{background:#dc2626}.p-high{background:#f59e0b}.p-medium{background:#2563eb}.p-low{background:#94a3b8}
.due-late{color:#b91c1c;font-weight:600;font-size:13px}.due-soon{color:#b45309;font-weight:600;font-size:13px}.due-ok,.due-closed{color:var(--mute);font-size:13px}
.title{font-size:14px;font-weight:600}
.kv{display:flex;padding:8px 0;border-bottom:1px solid #f1f5f9;font-size:13.5px}.kv:last-child{border:none}
.kv .k{width:40%;color:var(--mute)}.kv .v{flex:1}
.tl{display:flex;gap:12px;margin-bottom:12px}.tl i{width:8px;height:8px;border-radius:50%;background:#93c5fd;margin-top:6px;flex-shrink:0}
.tl .tx{font-size:13.5px}.tl .tm{font-size:12px;color:var(--mute)}
.rail{display:flex;align-items:flex-start;margin:12px 0 18px}.rs{display:flex;flex-direction:column;align-items:center;width:96px}
.rb{width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:600;background:#f1f5f9;color:var(--mute)}
.rb.done{background:#2563eb;color:#fff}.rb.act{background:var(--tint);color:#1d4ed8;box-shadow:0 0 0 2px #2563eb inset}
.rl{font-size:12px;color:var(--mute);margin-top:6px;text-align:center}.rc{height:2px;flex:1;background:var(--line);margin-top:12px}.rc.done{background:#2563eb}
.chip{display:inline-block;background:#f1f5f9;border-radius:6px;padding:2px 8px;font-size:12px;margin:2px 4px 2px 0}
.hb{display:flex;align-items:center;gap:10px;margin-bottom:10px;font-size:13px}.hb-l{width:34%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.hb-t{flex:1;background:#f1f5f9;border-radius:4px;height:8px;overflow:hidden}.hb-t div{height:100%;background:#2563eb;border-radius:4px}
.hb-v{width:52px;text-align:right;font-variant-numeric:tabular-nums}
.empty{padding:36px 0;text-align:center;color:var(--mute);font-size:14px}
.notif{border:1px solid var(--line);border-left:3px solid #2563eb;border-radius:8px;padding:10px 14px;margin-bottom:8px;font-size:13.5px}
.notif.warn{border-left-color:#f59e0b}.notif.error{border-left-color:#dc2626}.notif.ok{border-left-color:#16a34a}.notif .tm{font-size:12px;color:var(--mute);margin-top:2px}
.lock{background:#f8fafc;border:1px solid var(--line);border-radius:8px;padding:9px 12px;font-size:13px}
.avatar{width:30px;height:30px;border-radius:50%;background:var(--tint);color:#1d4ed8;display:inline-flex;align-items:center;justify-content:center;font-size:12px;font-weight:650}
/* buttons: white, blue text */
.stButton>button,.stDownloadButton>button,[data-testid="stFormSubmitButton"]>button{background:#fff!important;border:1px solid #bfdbfe!important;border-radius:8px;font-weight:600;box-shadow:none}
.stButton>button *,.stDownloadButton>button *,[data-testid="stFormSubmitButton"]>button *{color:var(--blue)}
.stButton>button:hover,.stDownloadButton>button:hover,[data-testid="stFormSubmitButton"]>button:hover{background:var(--tint)!important;border-color:var(--blue)!important}
.stButton>button[kind="primary"],[data-testid="stFormSubmitButton"]>button[kind="primary"]{border:1.5px solid var(--blue)!important;background:var(--tint)!important}
.stButton>button:disabled *{color:#94a3b8}
/* dropdowns: blue */
[data-baseweb="select"]>div{background:#fff!important;border:1px solid #bfdbfe!important;border-radius:8px!important}
[data-baseweb="select"] *,[data-baseweb="menu"] *{color:var(--blue)}
[data-baseweb="select"] svg,[data-baseweb="menu"] svg{fill:var(--blue)}
[data-baseweb="menu"] li:hover,[data-baseweb="menu"] li[aria-selected="true"]{background:var(--tint)!important}
[data-baseweb="tag"]{background:var(--tint)!important;border-radius:6px!important}
/* inputs */
.stApp input,.stApp textarea{background:#fff!important;-webkit-text-fill-color:var(--ink)!important;caret-color:var(--ink)}
.stApp ::placeholder{-webkit-text-fill-color:#94a3b8!important;opacity:1}
[data-baseweb="base-input"],[data-baseweb="input"],[data-baseweb="textarea"]{background:#fff!important;border:1px solid var(--line)!important;border-radius:8px!important}
[data-baseweb="base-input"]:focus-within,[data-baseweb="textarea"]:focus-within{border-color:var(--blue)!important}
[data-testid="stNumberInput"] button{background:#fff!important}
[data-testid="stExpander"],[data-testid="stForm"]{background:#fff;border:1px solid var(--line);border-radius:10px}
[data-testid="stCode"] pre,code{background:#f8fafc!important}
[data-baseweb="calendar"] [aria-selected="true"]{background:var(--blue)!important}[data-baseweb="calendar"] [aria-selected="true"] *{color:#fff!important}
[data-testid="stDialog"] div[role="dialog"]{border:1px solid var(--line)}
/* tabs, sidebar nav */
.stTabs [data-baseweb="tab-list"]{gap:6px;border-bottom:1px solid var(--line)}.stTabs [data-baseweb="tab"] p{font-weight:600}
.stTabs [aria-selected="true"] *{color:var(--blue)}.stTabs [data-baseweb="tab-highlight"]{background:var(--blue)!important}
[data-testid="stSidebar"] [role="radiogroup"]{gap:2px}
[data-testid="stSidebar"] [role="radiogroup"] label{padding:7px 10px;border-radius:8px;width:100%}
[data-testid="stSidebar"] [role="radiogroup"] label>div:first-child{display:none}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked){background:var(--tint)}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) *{color:#1d4ed8;font-weight:650}
"""
# Component colours must beat the global "dark text" rule, so mark them !important.
_COMPONENTS = re.sub(r'(?<![-\w])(color:[^;}!]+)(?=[;}])', r'\1!important', _COMPONENTS)
st.markdown(f"<style>{_GLOBAL}{_COMPONENTS}</style>", unsafe_allow_html=True)

# ───────────────────────────── seed data ─────────────────────────────
def now(): return datetime.now().strftime("%Y-%m-%d %H:%M")

def _f(id, label, type="text", ph="", opts=None, req=True):
    return {"id": id, "label": label, "type": type, "placeholder": ph, "options": opts or [], "required": req}

def _wf(id, name, desc, sla, stages, fields):
    return {"id": id, "name": name, "description": desc, "icon": "", "sla_hours": sla, "active": True,
            "stages": [{"name": n, "group_id": g, "description": d} for n, g, d in stages], "custom_fields": fields}

def _seed_groups():
    rows = [("grp-eng", "Engineering", "Software development and infrastructure", "#3b82f6"),
            ("grp-fin", "Finance & Accounting", "Expense review, budget approvals, audit", "#10b981"),
            ("grp-legal", "Legal & Compliance", "Contract review, regulatory compliance", "#8b5cf6"),
            ("grp-ops", "Operations", "Day-to-day operational tasks", "#f59e0b"),
            ("grp-hr", "Human Resources", "Onboarding, offboarding, employee relations", "#ec4899"),
            ("grp-exec", "Executive", "Senior leadership approvals", "#ef4444")]
    return [{"id": i, "name": n, "description": d, "color": c, "members": [], "created": now()} for i, n, d, c in rows]

def _seed_workflows():
    return [
        _wf("wf-contract", "Contract Approval", "Multi-stage contract review and approval", 72,
            [("Draft Review", "grp-legal", "Legal reviews draft"), ("Financial Sign-off", "grp-fin", "Finance approves terms"), ("Executive Approval", "grp-exec", "Executive signs off")],
            [_f("counterparty", "Counterparty / Company", ph="e.g. Acme Corp"), _f("contract_value", "Contract Value (USD)", "number"),
             _f("contract_type", "Contract Type", "select", opts=["NDA", "MSA", "SOW", "SLA", "Licensing", "Other"]),
             _f("effective_date", "Effective Date", "date"), _f("legal_contact", "Legal Contact Email", "email", req=False),
             _f("notes", "Special Terms / Notes", "textarea", req=False)]),
        _wf("wf-expense", "Expense Claim", "Employee expense reimbursement", 48,
            [("Manager Review", "grp-ops", "Manager approves"), ("Finance Audit", "grp-fin", "Finance verifies"), ("Payment Release", "grp-fin", "Finance pays")],
            [_f("amount", "Claim Amount (USD)", "number"),
             _f("category", "Expense Category", "select", opts=["Travel", "Meals", "Software", "Hardware", "Training", "Marketing", "Other"]),
             _f("expense_date", "Date of Expense", "date"), _f("vendor", "Vendor / Merchant", ph="e.g. Delta Airlines"),
             _f("cost_centre", "Cost Centre / Project Code", req=False), _f("justification", "Business Justification", "textarea")]),
        _wf("wf-onboard", "Employee Onboarding", "New hire setup and orientation", 120,
            [("HR Intake", "grp-hr", "HR collects documents"), ("IT Provisioning", "grp-eng", "Engineering sets up accounts"), ("Manager Induction", "grp-ops", "Manager completes orientation")],
            [_f("employee_name", "New Employee Full Name"), _f("employee_email", "Employee Email", "email"), _f("start_date", "Start Date", "date"),
             _f("job_title", "Job Title"), _f("manager", "Reporting Manager"),
             _f("equipment", "Equipment Needed", "select", opts=["MacBook Pro", "MacBook Air", "Dell Laptop", "Windows Desktop", "No Equipment"]),
             _f("access_level", "System Access Level", "select", opts=["Read Only", "Standard", "Elevated", "Admin"])]),
        _wf("wf-change", "Change Request", "System or process change management", 96,
            [("Impact Assessment", "grp-eng", "Engineering assesses risk"), ("Ops Approval", "grp-ops", "Operations approves"), ("Executive Sign-off", "grp-exec", "Executive authorises")],
            [_f("system", "System / Service Affected"), _f("change_type", "Change Type", "select", opts=["Standard", "Emergency", "Major Release", "Configuration", "Rollback"]),
             _f("risk_level", "Risk Level", "select", opts=["Low", "Medium", "High", "Critical"]), _f("planned_date", "Planned Implementation Date", "date"),
             _f("downtime", "Expected Downtime (minutes)", "number"), _f("rollback_plan", "Rollback Plan", "textarea")]),
        _wf("wf-incident", "Incident Report", "Operational incident triage and resolution", 24,
            [("Triage", "grp-eng", "Engineering triages"), ("Resolution", "grp-eng", "Engineering resolves"), ("Post-mortem", "grp-ops", "Ops documents learnings")],
            [_f("severity", "Severity Level", "select", opts=["SEV-1 (Critical)", "SEV-2 (Major)", "SEV-3 (Minor)", "SEV-4 (Low)"]),
             _f("affected_system", "Affected System / Service"),
             _f("impact", "User / Business Impact", "select", opts=["All users down", "Partial outage", "Degraded performance", "Data issue", "No user impact"]),
             _f("symptoms", "Symptoms / Error Description", "textarea"), _f("incident_lead", "Incident Lead")]),
        _wf("wf-vendor", "Vendor Approval", "New vendor onboarding and approval", 120,
            [("Vendor Vetting", "grp-legal", "Legal verifies credentials"), ("Budget Review", "grp-fin", "Finance approves spend"), ("Ops Sign-off", "grp-ops", "Operations finalises")],
            [_f("vendor_name", "Vendor Company Name"), _f("vendor_contact", "Vendor Contact Email", "email"),
             _f("service_type", "Service / Product Type", "select", opts=["Software / SaaS", "Professional Services", "Hardware", "Cloud Infrastructure", "Consulting", "Other"]),
             _f("annual_value", "Estimated Annual Value (USD)", "number"),
             _f("data_access", "Requires Access to Company Data?", "select", opts=["Yes - PII", "Yes - Financial", "Yes - Internal only", "No data access"]),
             _f("business_case", "Business Case / Justification", "textarea")]),
    ]

init_db()
if needs_seed():
    upsert_user({"id": "user-admin", "name": "Admin", "email": "admin@flowdesk.io", "role": "admin", "groups": [], "active": True, "created": now()})
    for g in _seed_groups(): upsert_group(g)
    for w in _seed_workflows(): upsert_workflow(w)

ss = st.session_state
LOADERS = {"users": get_users, "groups": get_groups, "workflows": get_workflows, "tasks": get_tasks,
           "notifications": get_notifications, "settings": get_settings}
def refresh(*keys):
    for k in keys: ss[k] = LOADERS[k]()
if "ready" not in ss:
    refresh(*LOADERS)
    ss.ready, ss.uid, ss.limit = True, "user-admin", 25

# ───────────────────────────── helpers ─────────────────────────────
PRIO = ["critical", "high", "medium", "low"]
STATUS_DOT = {"New": "#2563eb", "In Progress": "#d97706", "In Review": "#7c3aed", "Blocked": "#dc2626", "Done": "#16a34a"}

def get_user(i):  return next((u for u in ss.users if u["id"] == i), None)
def get_group(i): return next((g for g in ss.groups if g["id"] == i), None)
def get_wf(i):    return next((w for w in ss.workflows if w["id"] == i), None)
def me():         return get_user(ss.uid)
def is_admin():   return me()["role"] == "admin"
def gname(i):     g = get_group(i); return g["name"] if g else i
def gemail(i):    g = get_group(i); return g.get("email", "") if g else ""
def initials(n):  p = n.split(); return (p[0][0] + (p[-1][0] if len(p) > 1 else "")).upper() if p else "?"
def log(kind, msg): add_notification(kind, msg); refresh("notifications")
def parse(s):
    try: return datetime.strptime(s, "%Y-%m-%d %H:%M")
    except (TypeError, ValueError): return None
def span(h): return f"{int(h)}h" if h < 48 else f"{int(h // 24)}d"

def stage_info(t):
    wf = get_wf(t["workflow_id"])
    if wf and t["stage_index"] < len(wf["stages"]):
        s = wf["stages"][t["stage_index"]]; return s["name"], gname(s["group_id"])
    return ("Complete" if t["status"] == "Done" else "-"), ""

def can_act(t):
    if t["status"] == "Done": return False
    if is_admin(): return True
    wf = get_wf(t["workflow_id"])
    return bool(wf and t["stage_index"] < len(wf["stages"]) and wf["stages"][t["stage_index"]]["group_id"] in me()["groups"])

def due_state(t):
    if t["status"] == "Done": return "closed", "Closed"
    d = parse(t.get("due"))
    if not d: return "ok", "No due date"
    h = (d - datetime.now()).total_seconds() / 3600
    if h < 0: return "late", f"Overdue {span(-h)}"
    if h < ss.settings.get("sla_warn_hours", 4): return "soon", f"{int(h)}h left" if h >= 1 else "Under 1h left"
    return "ok", d.strftime("%b %d, %H:%M")

def open_tasks(): return [t for t in ss.tasks if t["status"] != "Done"]
def by_priority(rows): return sorted(rows, key=lambda t: (PRIO.index(t["priority"]) if t["priority"] in PRIO else 9, t.get("due") or "9"))

# ── workflow actions ──
def advance(tid):
    t = next((x for x in ss.tasks if x["id"] == tid), None); wf = get_wf(t["workflow_id"]) if t else None
    if not t or not wf or t["status"] in ("Done", "Blocked"): return
    by, i, stages = me()["name"], t["stage_index"], wf["stages"]
    add_history(tid, f"Stage '{stages[i]['name']}' completed", by)
    if i + 1 >= len(stages):
        t.update(status="Done", stage_index=i + 1, progress=100, closed_at=now()); upsert_task(t)
        add_history(tid, "Request completed and closed", "System"); log("ok", f"{tid} completed.")
        g = stages[i]["group_id"]
        notify_task_completed(group_email=gemail(g), group_name=gname(g), task_id=tid, task_title=t["title"],
                              workflow=wf["name"], priority=t["priority"], completed_by=by)
    else:
        ns = stages[i + 1]
        t.update(stage_index=i + 1, status="In Progress", progress=int((i + 1) / len(stages) * 100)); upsert_task(t)
        add_history(tid, f"Moved to '{ns['name']}', awaiting {gname(ns['group_id'])}", "System")
        log("info", f"{tid} moved to '{ns['name']}' ({gname(ns['group_id'])}).")
        notify_task_advanced(group_email=gemail(ns["group_id"]), group_name=gname(ns["group_id"]), task_id=tid,
                             task_title=t["title"], workflow=wf["name"], stage=ns["name"], priority=t["priority"],
                             due=t.get("due", ""), advanced_by=by)
    refresh("tasks"); st.toast(f"{tid} updated")

def send_back(t, reason):
    wf = get_wf(t["workflow_id"]); by = me()["name"]; i = t["stage_index"] - 1; ns = wf["stages"][i]
    t.update(stage_index=i, status="In Progress", progress=int(i / len(wf["stages"]) * 100)); upsert_task(t)
    add_history(t["id"], f"Sent back to '{ns['name']}': {reason}", by)
    log("warn", f"{t['id']} sent back to '{ns['name']}' by {by}.")
    notify_task_assigned(group_email=gemail(ns["group_id"]), group_name=gname(ns["group_id"]), task_id=t["id"],
                         task_title=t["title"], workflow=wf["name"], stage=ns["name"], priority=t["priority"],
                         due=t.get("due", ""), created_by=by)
    refresh("tasks")

def set_blocked(t, flag):
    wf = get_wf(t["workflow_id"]); by = me()["name"]
    t["status"] = "Blocked" if flag else "In Progress"; upsert_task(t)
    add_history(t["id"], "Marked as blocked" if flag else "Unblocked", by)
    if flag:
        log("error", f"{t['id']} blocked by {by}.")
        if wf and t["stage_index"] < len(wf["stages"]):
            s = wf["stages"][t["stage_index"]]
            notify_task_blocked(group_email=gemail(s["group_id"]), group_name=gname(s["group_id"]), task_id=t["id"],
                                task_title=t["title"], workflow=wf["name"], stage=s["name"], priority=t["priority"],
                                due=t.get("due", ""), blocked_by=by)
    refresh("tasks")

def set_memberships(uid, gids):
    u = get_user(uid); u["groups"] = gids; upsert_user(u)
    for g in ss.groups:
        has, want = uid in g["members"], g["id"] in gids
        if want and not has: g["members"].append(uid); upsert_group(g)
        elif has and not want: g["members"].remove(uid); upsert_group(g)
    refresh("users", "groups")

# ── small html components ──
def md(html): st.markdown(html, unsafe_allow_html=True)
def empty(msg): md(f'<div class="empty">{esc(msg)}</div>')
def section(t): md(f'<div class="sec">{esc(t)}</div>')
def pill(s): return f'<span class="pill"><i style="background:{STATUS_DOT.get(s, "#64748b")}"></i>{esc(s)}</span>'
def prio_pill(p): return f'<span class="pill"><i class="p-{esc(p)}"></i>{esc(p.capitalize())}</span>'
def kv(rows):
    return '<div class="card">' + "".join(
        f'<div class="kv"><div class="k">{esc(str(k))}</div><div class="v">{esc(str(v))}</div></div>' for k, v in rows) + "</div>"

def hbars(d, fmt=str):
    if not d: return empty("No data yet.")
    m = max(d.values()) or 1
    md("".join(f'<div class="hb"><div class="hb-l">{esc(k)}</div><div class="hb-t"><div style="width:{v / m * 100:.0f}%"></div></div>'
               f'<div class="hb-v">{esc(fmt(v))}</div></div>' for k, v in d.items()))

def stage_rail(t):
    wf = get_wf(t["workflow_id"]); out = '<div class="rail">'
    for i, s in enumerate(wf["stages"] if wf else []):
        if i: out += f'<div class="rc {"done" if i <= t["stage_index"] else ""}"></div>'
        done = i < t["stage_index"] or t["status"] == "Done"
        cls, lbl = ("done", "✓") if done else (("act", i + 1) if i == t["stage_index"] else ("", i + 1))
        out += f'<div class="rs"><div class="rb {cls}">{lbl}</div><div class="rl">{esc(s["name"])}</div></div>'
    return out + "</div>"

def header(title, sub="", new=False):
    a, b = st.columns([5, 1], vertical_alignment="center")
    a.markdown(f'<div class="page-title">{esc(title)}</div><div class="page-sub">{esc(sub)}</div>', unsafe_allow_html=True)
    if new and b.button("New request", type="primary", use_container_width=True, key=f"new_{title}"): new_request_dialog()

COLS = [0.9, 3, 1, 1.1, 1.8, 1.3, 0.8]
def task_table(rows, key, msg="Nothing here yet."):
    if not rows: return empty(msg)
    for c, l in zip(st.columns(COLS), ["Request", "Title", "Priority", "Status", "Current stage", "Due", ""]):
        c.markdown(f'<span class="th">{l}</span>', unsafe_allow_html=True)
    st.markdown("<hr style='margin:4px 0 2px'>", unsafe_allow_html=True)
    for t in rows:
        wf = get_wf(t["workflow_id"]); sn, own = stage_info(t); ds, dl = due_state(t)
        c = st.columns(COLS, vertical_alignment="center")
        c[0].markdown(f'<span class="id">{esc(t["id"])}</span>', unsafe_allow_html=True)
        c[1].markdown(f'<div class="title">{esc(t["title"])}</div><div class="muted">{esc(wf["name"] if wf else "?")}</div>', unsafe_allow_html=True)
        c[2].markdown(prio_pill(t["priority"]), unsafe_allow_html=True)
        c[3].markdown(pill(t["status"]), unsafe_allow_html=True)
        c[4].markdown(f'<div style="font-size:13.5px">{esc(sn)}</div><div class="muted">{esc(own)}</div>', unsafe_allow_html=True)
        c[5].markdown(f'<span class="due-{ds}">{esc(dl)}</span>', unsafe_allow_html=True)
        if c[6].button("Open", key=f"{key}_{t['id']}"): task_dialog(t["id"])
        st.markdown("<hr style='margin:2px 0'>", unsafe_allow_html=True)

def to_csv(rows):
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["ID", "Title", "Type", "Status", "Priority", "Stage", "Owner", "Created", "Created by", "Due", "Closed"])
    for t in rows:
        sn, own = stage_info(t); wf = get_wf(t["workflow_id"])
        w.writerow([t["id"], t["title"], wf["name"] if wf else "", t["status"], t["priority"], sn, own,
                    t["created"], t["created_by"], t.get("due", ""), t.get("closed_at") or ""])
    return buf.getvalue()

def render_field(f, prefix):
    k, lbl, ph, t = f"{prefix}_{f['id']}", f["label"] + (" *" if f.get("required") else ""), f.get("placeholder", ""), f["type"]
    if t == "textarea": return st.text_area(lbl, placeholder=ph, key=k, height=80)
    if t == "select":   return st.selectbox(lbl, f["options"], key=k) if f.get("options") else st.text_input(lbl, key=k)
    if t == "date":     return str(st.date_input(lbl, key=k))
    if t == "number":   return f"{st.number_input(lbl, min_value=0.0, step=1.0, key=k):,.2f}".rstrip("0").rstrip(".")
    return st.text_input(lbl, placeholder=ph, key=k)

# ───────────────────────────── dialogs ─────────────────────────────
@st.dialog("Request details", width="large")
def task_dialog(tid):
    t = next((x for x in ss.tasks if x["id"] == tid), None)
    if not t: return st.error("This request no longer exists.")
    wf = get_wf(t["workflow_id"]); sn, own = stage_info(t); ds, dl = due_state(t)
    md(f'<div class="id">{esc(t["id"])} &nbsp;{esc(wf["name"] if wf else "")}</div>'
       f'<div style="font-size:20px;font-weight:650;margin:2px 0 8px">{esc(t["title"])}</div>'
       f'<div class="row">{pill(t["status"])} {prio_pill(t["priority"])} <span class="due-{ds}" style="margin-left:6px">{esc(dl)}</span></div>')
    md(stage_rail(t))

    left, right = st.columns([3, 2])
    with left:
        section("Details")
        md(kv([("Current stage", sn), ("Owner", own or "-"), ("Progress", f'{t["progress"]}%'), ("Due", t.get("due") or "-"),
               ("Created", f'{t["created"]} by {t["created_by"]}')]))
        cf = t.get("custom_fields") or {}
        shown = [(f["label"], cf[f["id"]]) for f in (wf.get("custom_fields", []) if wf else []) if str(cf.get(f["id"], "")).strip()]
        if shown: section("Submission"); md(kv(shown))
        if t.get("description") and not shown: section("Description"); st.write(t["description"])
    with right:
        section("Activity")
        for h in reversed(t.get("history", [])):
            md(f'<div class="tl"><i></i><div><div class="tx">{esc(h["action"])} <span class="muted">{esc(h["by"])}</span></div>'
               f'<div class="tm">{esc(h["time"])}</div></div></div>')

    if t["status"] != "Done":
        st.divider()
        if can_act(t):
            a, b, c = st.columns(3)
            if a.button("Advance stage", type="primary", use_container_width=True, disabled=t["status"] == "Blocked", key="d_adv"):
                advance(tid); st.rerun()
            blocked = t["status"] == "Blocked"
            if b.button("Unblock" if blocked else "Mark blocked", use_container_width=True, key="d_blk"):
                set_blocked(t, not blocked); st.rerun()
            c.caption("Unblock to continue." if blocked else "")
        else:
            md(f'<div class="lock">Waiting on <b>{esc(own)}</b>. Only that group can advance this stage.</div>')
        with st.form(f"note_{tid}", clear_on_submit=True):
            note = st.text_input("Add a note", placeholder="Write a comment, or the reason for sending back")
            n1, n2, _ = st.columns([1, 1, 3])
            post = n1.form_submit_button("Post note")
            back = n2.form_submit_button("Send back", disabled=not (can_act(t) and t["stage_index"] > 0))
            if post and note.strip():
                add_history(tid, f"Note: {note.strip()}", me()["name"]); refresh("tasks"); st.rerun(scope="fragment")
            if back:
                if not note.strip(): st.error("Add a reason before sending the request back.")
                else: send_back(t, note.strip()); st.rerun()

@st.dialog("New request", width="large")
def new_request_dialog():
    active = [w for w in ss.workflows if w["active"]]
    if not active: return st.warning("No active workflow templates. An admin needs to create one first.")
    ids = [w["id"] for w in active]
    wf = get_wf(st.selectbox("Request type", ids, format_func=lambda i: get_wf(i)["name"]))
    md(f'<div class="muted" style="margin-bottom:6px">{esc(wf.get("description", ""))} &nbsp;|&nbsp; {wf["sla_hours"]}h SLA</div>'
       f'<div class="card" style="padding:10px 14px"><span class="th">Approval path</span><br>'
       + " &rarr; ".join(f'<b>{esc(s["name"])}</b> <span class="muted">({esc(gname(s["group_id"]))})</span>' for s in wf["stages"]) + "</div>")
    a, b = st.columns(2)
    title = a.text_input("Title *", placeholder="Short, descriptive title", key="nr_title")
    prio = b.selectbox("Priority", PRIO, index=2, format_func=str.capitalize, key="nr_prio")
    a, b = st.columns(2)
    due_d = a.date_input("Due date *", value=datetime.now() + timedelta(days=3), key="nr_date")
    due_t = b.time_input("Due time", value=time(17, 0), key="nr_time")
    desc = st.text_area("Description", placeholder="Optional context for reviewers", height=70, key="nr_desc")
    cfs, vals = wf.get("custom_fields", []), {}
    if cfs:
        st.divider(); section("Request information")
        for i in range(0, len(cfs), 2):
            pair = cfs[i:i + 2]
            if len(pair) == 2 and all(f["type"] != "textarea" for f in pair):
                for col, f in zip(st.columns(2), pair):
                    with col: vals[f["id"]] = render_field(f, f"nf_{wf['id']}")
            else:
                for f in pair: vals[f["id"]] = render_field(f, f"nf_{wf['id']}")
    if st.button("Create request", type="primary", key="nr_create"):
        errs = [] if title.strip() else ["Title is required."]
        errs += [f"'{f['label']}' is required." for f in cfs if f.get("required") and f["type"] != "number" and not str(vals.get(f["id"], "")).strip()]
        if errs:
            for e in errs: st.error(e)
            return
        by, s0, due = me()["name"], wf["stages"][0], f"{due_d} {due_t.strftime('%H:%M')}"
        lines = [f"{f['label']}: {vals[f['id']]}" for f in cfs if str(vals.get(f["id"], "")).strip()]
        full = (desc.strip() + ("\n\n" if desc.strip() and lines else "") + "\n".join(lines)).strip()
        nid = f"WF-{increment_task_counter()}"
        upsert_task({"id": nid, "title": title.strip(), "description": full, "workflow_id": wf["id"], "status": "New", "priority": prio,
                     "stage_index": 0, "progress": 0, "created": now(), "created_by": by, "due": due, "closed_at": None, "custom_fields": vals})
        add_history(nid, "Request created", by)
        add_history(nid, f"Stage '{s0['name']}' started, awaiting {gname(s0['group_id'])}", "System")
        log("info", f"{nid} '{title.strip()}' created ({wf['name']}).")
        notify_task_assigned(group_email=gemail(s0["group_id"]), group_name=gname(s0["group_id"]), task_id=nid, task_title=title.strip(),
                             workflow=wf["name"], stage=s0["name"], priority=prio, due=due, created_by=by)
        refresh("tasks"); st.toast(f"{nid} created"); st.rerun()

@st.dialog("Workflow template", width="large")
def template_dialog(wf_id=None):
    edit = wf_id is not None; wf = get_wf(wf_id) if edit else None
    gnames = [g["name"] for g in ss.groups]
    t_basic, t_stages, t_fields = st.tabs(["Basics", "Stages", "Custom fields"])
    with t_basic:
        a, b = st.columns(2)
        name = a.text_input("Template name *", value=wf["name"] if wf else "")
        sla = b.number_input("SLA (hours)", min_value=1, value=wf["sla_hours"] if wf else 72)
        desc = st.text_area("Description", value=wf.get("description", "") if wf else "", height=80)
        active = st.checkbox("Active", value=wf.get("active", True) if wf else True)
    with t_stages:
        st.caption("Stages run in order. Only members of the assigned group can advance a stage.")
        ex_s = wf["stages"] if wf else []
        n = int(st.number_input("Number of stages", 1, 8, max(len(ex_s), 1), key="ns_wf")); stages = []
        for i in range(n):
            ex = ex_s[i] if i < len(ex_s) else {}
            a, b = st.columns(2)
            sn = a.text_input(f"Stage {i + 1} name *", value=ex.get("name", ""), key=f"sn_{wf_id}_{i}")
            cg = gname(ex["group_id"]) if ex.get("group_id") else ""
            sg = b.selectbox("Assigned group *", gnames, index=gnames.index(cg) if cg in gnames else 0, key=f"sg_{wf_id}_{i}")
            sd = st.text_input("Description", value=ex.get("description", ""), key=f"sd_{wf_id}_{i}")
            stages.append({"name": sn, "group_id": next(g["id"] for g in ss.groups if g["name"] == sg), "description": sd})
    with t_fields:
        st.caption("Custom fields appear on the new request form.")
        ex_f = wf.get("custom_fields", []) if wf else []
        n = int(st.number_input("Number of fields", 0, 15, len(ex_f), key="nf_wf"))
        types = ["text", "number", "email", "date", "select", "textarea"]; fields = []
        for i in range(n):
            ex = ex_f[i] if i < len(ex_f) else {}
            with st.expander(f"Field {i + 1}: {ex.get('label') or 'New field'}", expanded=not ex.get("label")):
                a, b, c = st.columns([3, 2, 1])
                fl = a.text_input("Label *", value=ex.get("label", ""), key=f"fl_{wf_id}_{i}")
                ft = b.selectbox("Type", types, index=types.index(ex.get("type", "text")), key=f"ft_{wf_id}_{i}")
                fr = c.checkbox("Required", value=ex.get("required", False), key=f"fr_{wf_id}_{i}")
                a, b = st.columns(2)
                fp = a.text_input("Placeholder", value=ex.get("placeholder", ""), key=f"fp_{wf_id}_{i}")
                fo = []
                if ft == "select":
                    raw = b.text_input("Options (comma-separated)", value=", ".join(ex.get("options", [])), key=f"fo_{wf_id}_{i}")
                    fo = [o.strip() for o in raw.split(",") if o.strip()]
                fields.append({"id": ex.get("id") or f"f{i}_{uuid.uuid4().hex[:4]}", "label": fl, "type": ft,
                               "placeholder": fp, "options": fo, "required": fr})
    if st.button("Save changes" if edit else "Create template", type="primary", key="tpl_save"):
        valid = [s for s in stages if s["name"].strip()]
        if not name.strip(): st.error("Template name is required.")
        elif not valid: st.error("Add at least one stage with a name.")
        else:
            upsert_workflow({"id": wf_id if edit else f"wf-{uuid.uuid4().hex[:8]}", "name": name.strip(), "description": desc, "icon": "",
                             "sla_hours": int(sla), "active": active, "stages": valid, "custom_fields": [f for f in fields if f["label"].strip()]})
            refresh("workflows"); log("ok", f"Template '{name.strip()}' {'updated' if edit else 'created'}."); st.rerun()

# ───────────────────────────── pages ─────────────────────────────
def page_overview():
    header("Overview", datetime.now().strftime("%A, %d %B %Y"), new=True)
    op = open_tasks(); mine = [t for t in op if can_act(t)]
    late = [t for t in op if due_state(t)[0] == "late"]
    stats = [("Open requests", len(op)), ("Awaiting your action", len(mine)), ("Overdue", len(late)),
             ("Completed", len(ss.tasks) - len(op))]
    for col, (l, v) in zip(st.columns(4), stats):
        col.markdown(f'<div class="stat"><div class="l">{l}</div><div class="v">{v}</div></div>', unsafe_allow_html=True)
    md("<div style='height:24px'></div>")
    section("Needs your attention")
    task_table(by_priority(mine)[:6], "ov", "You're all caught up.")
    md("<div style='height:18px'></div>")
    c1, c2, c3 = st.columns(3)
    with c1:
        section("Recent activity")
        if not ss.notifications: empty("No activity yet.")
        for n in ss.notifications[:5]:
            cls = {"warn": "warn", "error": "error", "ok": "ok"}.get(n["type"], "")
            md(f'<div class="notif {cls}">{esc(n["msg"])}<div class="tm">{esc(n["time"])}</div></div>')
    with c2:
        section("Open requests by owner")
        d = {}
        for t in op:
            o = stage_info(t)[1]; d[o] = d.get(o, 0) + 1
        hbars(dict(sorted(d.items(), key=lambda x: -x[1])))
    with c3:
        section("Requests by status")
        hbars({s: n for s in ["New", "In Progress", "Blocked", "Done"] if (n := sum(t["status"] == s for t in ss.tasks))})

def page_queue():
    header("My queue", "Requests that need you, and ones you started", new=True)
    mine = by_priority([t for t in open_tasks() if can_act(t)])
    started = [t for t in ss.tasks if t["created_by"] == me()["name"]]
    done = [t for t in ss.tasks if t["status"] == "Done"]
    a, b, c = st.tabs([f"Awaiting me ({len(mine)})", f"Created by me ({len(started)})", f"Completed ({len(done)})"])
    with a: task_table(mine, "q1", "Nothing is waiting on you.")
    with b: task_table(started[::-1], "q2", "You haven't created any requests yet.")
    with c: task_table(done[::-1], "q3", "No completed requests yet.")

def page_requests():
    header("Requests", f"{len(ss.tasks)} total", new=True)
    c = st.columns([2.4, 1.5, 1.3, 1.3, 1.3])
    q = c[0].text_input("Search", placeholder="Search by title or ID", label_visibility="collapsed")
    wfs = ["All types"] + [w["name"] for w in ss.workflows if w["active"]]
    f_wf = c[1].selectbox("Type", wfs, label_visibility="collapsed")
    f_st = c[2].selectbox("Status", ["All statuses", "New", "In Progress", "Blocked", "Done"], label_visibility="collapsed")
    f_pr = c[3].selectbox("Priority", ["All priorities"] + [p.capitalize() for p in PRIO], label_visibility="collapsed")
    f_so = c[4].selectbox("Sort", ["Priority", "Due date", "Newest"], label_visibility="collapsed")
    rows = [t for t in ss.tasks if q.lower() in (t["title"] + t["id"]).lower()]
    if f_wf != "All types": rows = [t for t in rows if (get_wf(t["workflow_id"]) or {}).get("name") == f_wf]
    if f_st != "All statuses": rows = [t for t in rows if t["status"] == f_st]
    if f_pr != "All priorities": rows = [t for t in rows if t["priority"] == f_pr.lower()]
    rows = by_priority(rows) if f_so == "Priority" else sorted(rows, key=lambda t: t.get("due") or "9") if f_so == "Due date" else sorted(rows, key=lambda t: t["created"], reverse=True)
    a, b = st.columns([5, 1], vertical_alignment="center")
    a.caption(f"{len(rows)} result(s)")
    b.download_button("Export CSV", to_csv(rows), "requests.csv", "text/csv", use_container_width=True)
    task_table(rows[:ss.limit], "rq", "No requests match these filters.")
    if len(rows) > ss.limit and st.button(f"Show more ({len(rows) - ss.limit} remaining)", key="more"):
        ss.limit += 25; st.rerun()

def page_reports():
    header("Reports", "Volume, turnaround and workload")
    tv, tt, tw = st.tabs(["Volume", "Turnaround", "Workload"])
    def count(fn):
        d = {}
        for t in ss.tasks: k = fn(t); d[k] = d.get(k, 0) + 1
        return dict(sorted(d.items(), key=lambda x: -x[1]))
    with tv:
        if not ss.tasks: return empty("No data yet.")
        a, b, c = st.columns(3)
        with a: section("By request type"); hbars(count(lambda t: (get_wf(t["workflow_id"]) or {}).get("name", "Unknown")))
        with b: section("By status"); hbars(count(lambda t: t["status"]))
        with c: section("By priority"); hbars(count(lambda t: t["priority"].capitalize()))
    with tt:
        done = [t for t in ss.tasks if t["status"] == "Done" and parse(t.get("closed_at")) and parse(t["created"])]
        if not done: empty("Completed requests will appear here.")
        else:
            hrs = lambda t: (parse(t["closed_at"]) - parse(t["created"])).total_seconds() / 3600
            on_time = [t for t in done if parse(t.get("due")) and parse(t["closed_at"]) <= parse(t["due"])]
            for col, (l, v) in zip(st.columns(3), [("Completed", len(done)), ("On-time rate", f"{len(on_time) / len(done):.0%}"),
                                                    ("Average turnaround", span(sum(map(hrs, done)) / len(done)))]):
                col.markdown(f'<div class="stat"><div class="l">{l}</div><div class="v">{v}</div></div>', unsafe_allow_html=True)
            md("<div style='height:18px'></div>"); section("Average turnaround by type (hours)")
            d = {}
            for t in done: d.setdefault((get_wf(t["workflow_id"]) or {}).get("name", "Unknown"), []).append(hrs(t))
            hbars({k: sum(v) / len(v) for k, v in d.items()}, fmt=lambda v: f"{v:.1f}h")
    with tw:
        section("Open requests waiting on each group")
        d = {g["name"]: 0 for g in ss.groups}
        for t in open_tasks():
            o = stage_info(t)[1]; d[o] = d.get(o, 0) + 1
        hbars(dict(sorted(d.items(), key=lambda x: -x[1])))

def page_activity():
    n = ss.notifications
    header("Activity", f"{len(n)} event(s)")
    if n and st.button("Clear all"): clear_notifications(); ss.notifications = []; st.rerun()
    if not n: empty("No activity yet.")
    for x in n:
        cls = {"warn": "warn", "error": "error", "ok": "ok"}.get(x["type"], "")
        md(f'<div class="notif {cls}">{esc(x["msg"])}<div class="tm">{esc(x["time"])}</div></div>')

def admin_users():
    with st.expander("Add user"), st.form("add_user", clear_on_submit=True):
        a, b = st.columns(2); nn = a.text_input("Full name *"); ne = b.text_input("Email *")
        a, b = st.columns(2); nr = a.selectbox("Role", ["member", "admin"]); ng = b.multiselect("Groups", [g["name"] for g in ss.groups])
        if st.form_submit_button("Create user", type="primary"):
            if not nn.strip() or "@" not in ne: st.error("Enter a name and a valid email.")
            elif any(u["email"].lower() == ne.strip().lower() for u in ss.users): st.error("A user with that email already exists.")
            else:
                uid = f"user-{uuid.uuid4().hex[:8]}"
                upsert_user({"id": uid, "name": nn.strip(), "email": ne.strip(), "role": nr, "groups": [], "active": True, "created": now()})
                refresh("users"); set_memberships(uid, [g["id"] for g in ss.groups if g["name"] in ng])
                log("ok", f"User '{nn.strip()}' created as {nr}."); st.rerun()
    for u in ss.users:
        with st.expander(f"{u['name']}  ({u['email']})  -  {u['role']}{'' if u['active'] else ', inactive'}"):
            md("".join(f'<span class="chip">{esc(gname(g))}</span>' for g in u["groups"]) or '<span class="muted">No groups</span>')
            if u["id"] == "user-admin": continue
            names = [g["name"] for g in ss.groups]
            a, b = st.columns(2)
            ug = a.multiselect("Groups", names, default=[gname(g) for g in u["groups"]], key=f"ug_{u['id']}")
            ur = b.selectbox("Role", ["member", "admin"], index=0 if u["role"] == "member" else 1, key=f"ur_{u['id']}")
            s1, s2, _ = st.columns([1, 1, 4])
            if s1.button("Save", key=f"su_{u['id']}", type="primary"):
                u["role"] = ur; upsert_user(u); set_memberships(u["id"], [g["id"] for g in ss.groups if g["name"] in ug])
                log("info", f"User '{u['name']}' updated."); st.rerun()
            if s2.button("Deactivate" if u["active"] else "Reactivate", key=f"dt_{u['id']}"):
                u["active"] = not u["active"]; upsert_user(u); refresh("users"); st.rerun()

def admin_groups():
    with st.expander("Add group"), st.form("add_group", clear_on_submit=True):
        a, b = st.columns(2); gn = a.text_input("Group name *"); ge = b.text_input("Group email", help="Workflow notifications are sent here")
        gd = st.text_input("Description")
        if st.form_submit_button("Create group", type="primary"):
            if not gn.strip(): st.error("A group name is required.")
            elif any(g["name"].lower() == gn.strip().lower() for g in ss.groups): st.error("A group with that name already exists.")
            else:
                upsert_group({"id": f"grp-{uuid.uuid4().hex[:8]}", "name": gn.strip(), "description": gd, "color": "#3b82f6",
                              "email": ge.strip(), "members": [], "created": now()})
                refresh("groups"); log("ok", f"Group '{gn.strip()}' created."); st.rerun()
    for g in ss.groups:
        members = [get_user(m)["name"] for m in g["members"] if get_user(m)]
        with st.expander(f"{g['name']}  -  {len(members)} member(s)"):
            md(f'<div class="muted">{esc(g.get("description", ""))}</div>')
            a, b = st.columns(2)
            nd = a.text_input("Description", value=g.get("description", ""), key=f"gd_{g['id']}")
            ne = b.text_input("Group email", value=g.get("email", ""), key=f"ge_{g['id']}")
            act = [u["name"] for u in ss.users if u["active"]]
            nm = st.multiselect("Members", act, default=[m for m in members if m in act], key=f"gm_{g['id']}")
            if st.button("Save", key=f"sg_{g['id']}", type="primary"):
                g.update(description=nd, email=ne.strip()); upsert_group(g); gid = g["id"]
                for u in list(ss.users):
                    cur = get_user(u["id"])["groups"]; want = u["name"] in nm
                    if want and gid not in cur: set_memberships(u["id"], cur + [gid])
                    elif not want and gid in cur and u["active"]: set_memberships(u["id"], [x for x in cur if x != gid])
                log("info", f"Group '{g['name']}' updated."); st.rerun()

def admin_templates():
    if st.button("New template", type="primary", key="btn_nt"): template_dialog()
    for wf in ss.workflows:
        n = sum(t["workflow_id"] == wf["id"] for t in ss.tasks)
        flow = " &rarr; ".join(f'{esc(s["name"])} <span class="muted">({esc(gname(s["group_id"]))})</span>' for s in wf["stages"])
        a, b = st.columns([6, 1], vertical_alignment="center")
        a.markdown(f'<div class="card" style="margin:0"><div class="row"><span class="title">{esc(wf["name"])}</span> '
                   f'<span class="pill">{"Active" if wf["active"] else "Inactive"}</span> <span class="muted">{wf["sla_hours"]}h SLA, {n} request(s)</span></div>'
                   f'<div class="muted" style="margin:4px 0 6px">{esc(wf.get("description", ""))}</div><div style="font-size:13px">{flow}</div></div>', unsafe_allow_html=True)
        if b.button("Edit", key=f"ewf_{wf['id']}", use_container_width=True): template_dialog(wf["id"])
        md("<div style='height:8px'></div>")

def admin_settings():
    cfg = ss.settings; a, b = st.columns(2)
    cfg["sla_warn_hours"] = a.slider("Show 'due soon' warning when under (hours)", 1, 24, int(cfg.get("sla_warn_hours", 4)))
    cfg["auto_escalate"] = a.checkbox("Auto-escalate on SLA breach", value=bool(cfg.get("auto_escalate", True)))
    strategies = ["Manual", "Round Robin", "Load Balanced"]
    cfg["default_strategy"] = b.selectbox("Default assignment strategy", strategies, index=strategies.index(cfg.get("default_strategy", "Manual")))
    if st.button("Save settings", type="primary"):
        save_settings(cfg); refresh("settings"); log("ok", "System settings updated."); st.success("Settings saved.")
    st.divider(); section("Email notifications")
    if email_is_configured():
        st.success("Email is configured.")
        if st.button("Send test email"):
            ok, err = test_connection()
            st.success("Test email sent.") if ok else st.error(f"Could not send: {err}")
    else:
        st.warning("Email notifications are not configured.")
        st.write("Add SMTP details to `.streamlit/secrets.toml`, then set a **Group email** on each group. "
                 "The owning group is emailed when a request is assigned, advanced, blocked or completed.")
        st.code('[email]\nsmtp_host     = "smtp.example.com"\nsmtp_port     = 587\nsmtp_user     = "you@example.com"\nsmtp_password = "your-app-password"\nfrom_name     = "WorkBench"\nenabled       = true', language="toml")

def page_admin():
    if not is_admin(): return st.error("Access denied. Admins only.")
    header("Administration", "People, groups, templates and settings")
    tabs = st.tabs(["Users", "Groups", "Templates", "Settings"])
    for tab, fn in zip(tabs, [admin_users, admin_groups, admin_templates, admin_settings]):
        with tab: fn()

# ───────────────────────────── shell ─────────────────────────────
with st.sidebar:
    md('<div class="brand">Work<span>Bench</span></div>')
    admin_now = me()["role"] == "admin"
    pages = ["Overview", "My queue", "Requests", "Reports", "Activity"] + (["Admin"] if admin_now else [])
    n_mine = sum(can_act(t) for t in open_tasks())
    page = st.radio("Navigate", pages, label_visibility="collapsed",
                    format_func=lambda p: f"My queue  ({n_mine})" if p == "My queue" and n_mine else p)
    st.divider()
    active = [u["id"] for u in ss.users if u["active"]]
    ss.uid = st.selectbox("Signed in as", active, index=active.index(ss.uid) if ss.uid in active else 0, format_func=lambda i: get_user(i)["name"])
    u = me()
    md(f'<div class="row" style="display:flex;gap:10px;align-items:center"><span class="avatar">{esc(initials(u["name"]))}</span>'
       f'<div><div style="font-size:13px;font-weight:600">{esc(u["name"])}</div>'
       f'<div class="muted">{esc(", ".join(gname(g) for g in u["groups"]) or u["role"].capitalize())}</div></div></div>')

{"Overview": page_overview, "My queue": page_queue, "Requests": page_requests, "Reports": page_reports,
 "Activity": page_activity, "Admin": page_admin}[page]()
