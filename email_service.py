"""
email_service.py — WorkBench email notification service

Sends HTML emails to group inboxes when workflow tasks are assigned,
advanced, blocked, or completed.  Always sends to a GROUP email address —
never to individual users.

SMTP configuration lives in .streamlit/secrets.toml:

    [email]
    smtp_host     = "smtp.gmail.com"
    smtp_port     = 587
    smtp_user     = "WorkBench@yourcompany.com"
    smtp_password = "your-app-password"
    from_name     = "WorkBench"
    enabled       = true

Or via environment variables (useful for Docker / Railway):
    EMAIL_SMTP_HOST, EMAIL_SMTP_PORT, EMAIL_SMTP_USER,
    EMAIL_SMTP_PASSWORD, EMAIL_FROM_NAME, EMAIL_ENABLED

If no config is found, or enabled=false, all send calls are silently
skipped — the app works perfectly without email configured.

Gmail note: use an App Password, not your account password.
  https://myaccount.google.com/apppasswords
"""

import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime


# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════════════════

def _get_email_config() -> dict | None:
    """
    Returns email config dict, or None if email is disabled / not configured.
    """
    try:
        import streamlit as st
        cfg = st.secrets.get("email", {})
        if not cfg or not cfg.get("enabled", True):
            return None
        return {
            "host":      cfg.get("smtp_host",     "smtp.gmail.com"),
            "port":      int(cfg.get("smtp_port", 587)),
            "user":      cfg.get("smtp_user",     ""),
            "password":  cfg.get("smtp_password", ""),
            "from_name": cfg.get("from_name",     "WorkBench"),
            "enabled":   bool(cfg.get("enabled",  True)),
        }
    except Exception:
        pass

    # Fall back to environment variables
    host     = os.getenv("EMAIL_SMTP_HOST",     "")
    user     = os.getenv("EMAIL_SMTP_USER",     "")
    password = os.getenv("EMAIL_SMTP_PASSWORD", "")
    enabled  = os.getenv("EMAIL_ENABLED",       "true").lower() == "true"

    if not host or not user or not password or not enabled:
        return None

    return {
        "host":      host,
        "port":      int(os.getenv("EMAIL_SMTP_PORT", 587)),
        "user":      user,
        "password":  password,
        "from_name": os.getenv("EMAIL_FROM_NAME", "WorkBench"),
        "enabled":   True,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  CORE SEND FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def _send(to_email: str, subject: str, html_body: str) -> tuple[bool, str]:
    """
    Low-level send. Returns (success: bool, error_message: str).
    Uses STARTTLS on port 587, or SSL on port 465.
    """
    cfg = _get_email_config()
    if not cfg:
        return False, "Email not configured or disabled."

    from_addr = f"{cfg['from_name']} <{cfg['user']}>"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = from_addr
    msg["To"]      = to_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        if cfg["port"] == 465:
            with smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=10) as s:
                s.login(cfg["user"], cfg["password"])
                s.sendmail(cfg["user"], [to_email], msg.as_string())
        else:
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=10) as s:
                s.ehlo()
                s.starttls()
                s.login(cfg["user"], cfg["password"])
                s.sendmail(cfg["user"], [to_email], msg.as_string())
        return True, ""
    except Exception as e:
        return False, str(e)


# ══════════════════════════════════════════════════════════════════════════════
#  HTML EMAIL TEMPLATE
# ══════════════════════════════════════════════════════════════════════════════

def _build_email(
    task_id:    str,
    task_title: str,
    workflow:   str,
    stage:      str,
    group_name: str,
    priority:   str,
    due:        str,
    action:     str,
    detail:     str,
    task_url:   str = "",
) -> tuple[str, str]:
    """Returns (subject, html_body)."""

    priority_color = {
        "critical": "#ef4444",
        "high":     "#f59e0b",
        "medium":   "#3b82f6",
        "low":      "#64748b",
    }.get(priority.lower(), "#3b82f6")

    action_color = {
        "assigned":   "#3b82f6",
        "advanced":   "#10b981",
        "blocked":    "#ef4444",
        "completed":  "#10b981",
        "unblocked":  "#f59e0b",
    }.get(action.lower(), "#3b82f6")

    subject = f"[WorkBench] {action.capitalize()}: {task_id} — {task_title}"

    cta = (f'<a href="{task_url}" style="display:inline-block;margin-top:20px;'
           f'padding:12px 24px;background:#2563eb;color:#ffffff;text-decoration:none;'
           f'border-radius:6px;font-weight:600;font-size:14px;">View Task in WorkBench</a>'
           if task_url else "")

    html = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body style="margin:0;padding:0;background:#0a0d14;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0d14;padding:32px 16px;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0"
               style="background:#111827;border-radius:12px;overflow:hidden;
                      border:1px solid #1e2736;max-width:600px;width:100%;">

          <!-- Header -->
          <tr>
            <td style="background:#0d1117;padding:20px 32px;border-bottom:1px solid #1e2736;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td>
                    <span style="font-size:22px;font-weight:700;color:#f1f5f9;
                                 font-family:'Courier New',monospace;">⬡ WorkBench</span>
                  </td>
                  <td align="right">
                    <span style="display:inline-block;padding:4px 12px;
                                 background:{action_color}22;color:{action_color};
                                 border:1px solid {action_color}44;border-radius:4px;
                                 font-size:11px;font-weight:700;text-transform:uppercase;
                                 letter-spacing:.08em;">{action.upper()}</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:28px 32px;">

              <p style="margin:0 0 4px;font-size:13px;color:#64748b;
                        text-transform:uppercase;letter-spacing:.1em;font-weight:600;">
                Action Required
              </p>
              <h1 style="margin:0 0 20px;font-size:20px;font-weight:700;color:#f1f5f9;
                          line-height:1.3;">
                {task_title}
              </h1>

              <!-- Task details card -->
              <table width="100%" cellpadding="0" cellspacing="0"
                     style="background:#0d1117;border-radius:8px;overflow:hidden;
                            border:1px solid #1e2736;margin-bottom:24px;">
                <tr>
                  <td style="padding:14px 18px;border-bottom:1px solid #1e2736;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                      <tr>
                        <td style="font-size:11px;font-weight:700;color:#64748b;
                                   text-transform:uppercase;letter-spacing:.08em;width:120px;">
                          Task ID
                        </td>
                        <td style="font-size:13px;color:#60a5fa;
                                   font-family:'Courier New',monospace;">
                          {task_id}
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
                <tr>
                  <td style="padding:14px 18px;border-bottom:1px solid #1e2736;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                      <tr>
                        <td style="font-size:11px;font-weight:700;color:#64748b;
                                   text-transform:uppercase;letter-spacing:.08em;width:120px;">
                          Workflow
                        </td>
                        <td style="font-size:13px;color:#e2e8f0;">{workflow}</td>
                      </tr>
                    </table>
                  </td>
                </tr>
                <tr>
                  <td style="padding:14px 18px;border-bottom:1px solid #1e2736;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                      <tr>
                        <td style="font-size:11px;font-weight:700;color:#64748b;
                                   text-transform:uppercase;letter-spacing:.08em;width:120px;">
                          Current Stage
                        </td>
                        <td style="font-size:13px;color:#e2e8f0;">{stage}</td>
                      </tr>
                    </table>
                  </td>
                </tr>
                <tr>
                  <td style="padding:14px 18px;border-bottom:1px solid #1e2736;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                      <tr>
                        <td style="font-size:11px;font-weight:700;color:#64748b;
                                   text-transform:uppercase;letter-spacing:.08em;width:120px;">
                          Assigned To
                        </td>
                        <td style="font-size:13px;color:#e2e8f0;">{group_name}</td>
                      </tr>
                    </table>
                  </td>
                </tr>
                <tr>
                  <td style="padding:14px 18px;border-bottom:1px solid #1e2736;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                      <tr>
                        <td style="font-size:11px;font-weight:700;color:#64748b;
                                   text-transform:uppercase;letter-spacing:.08em;width:120px;">
                          Priority
                        </td>
                        <td>
                          <span style="display:inline-block;padding:2px 10px;
                                       background:{priority_color}22;color:{priority_color};
                                       border:1px solid {priority_color}44;border-radius:4px;
                                       font-size:11px;font-weight:700;text-transform:uppercase;">
                            {priority.upper()}
                          </span>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
                <tr>
                  <td style="padding:14px 18px;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                      <tr>
                        <td style="font-size:11px;font-weight:700;color:#64748b;
                                   text-transform:uppercase;letter-spacing:.08em;width:120px;">
                          Due
                        </td>
                        <td style="font-size:13px;color:#e2e8f0;">
                          {due if due else "Not set"}
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>

              <!-- Action detail -->
              <div style="background:#1e2736;border-left:3px solid {action_color};
                          border-radius:0 6px 6px 0;padding:14px 18px;margin-bottom:24px;">
                <p style="margin:0;font-size:13px;color:#cbd5e1;line-height:1.6;">
                  {detail}
                </p>
              </div>

              {cta}

            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:16px 32px;background:#0d1117;border-top:1px solid #1e2736;">
              <p style="margin:0;font-size:11px;color:#475569;text-align:center;">
                This is an automated notification from WorkBench.
                Sent {datetime.now().strftime("%d %b %Y at %H:%M")}.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""
    return subject, html


# ══════════════════════════════════════════════════════════════════════════════
#  PUBLIC API  —  called from app.py
# ══════════════════════════════════════════════════════════════════════════════

def notify_task_assigned(
    group_email: str,
    group_name:  str,
    task_id:     str,
    task_title:  str,
    workflow:    str,
    stage:       str,
    priority:    str,
    due:         str,
    created_by:  str,
    task_url:    str = "",
) -> tuple[bool, str]:
    """
    Send when a new workflow instance is created.
    Email goes to the group that owns Stage 1.
    """
    if not group_email:
        return False, "No group email configured."

    detail = (f"A new <strong>{workflow}</strong> workflow has been created by "
              f"<strong>{created_by}</strong> and assigned to your team for the "
              f"<strong>{stage}</strong> stage. Please review and action this task.")

    subject, html = _build_email(
        task_id=task_id, task_title=task_title, workflow=workflow,
        stage=stage, group_name=group_name, priority=priority,
        due=due, action="assigned", detail=detail, task_url=task_url)

    return _send(group_email, subject, html)


def notify_task_advanced(
    group_email: str,
    group_name:  str,
    task_id:     str,
    task_title:  str,
    workflow:    str,
    stage:       str,
    priority:    str,
    due:         str,
    advanced_by: str,
    task_url:    str = "",
) -> tuple[bool, str]:
    """
    Send when a task advances to a new stage.
    Email goes to the group that owns the NEW stage.
    """
    if not group_email:
        return False, "No group email configured."

    detail = (f"The <strong>{workflow}</strong> workflow has advanced and is now in the "
              f"<strong>{stage}</strong> stage, which requires action from your team. "
              f"Advanced by <strong>{advanced_by}</strong>.")

    subject, html = _build_email(
        task_id=task_id, task_title=task_title, workflow=workflow,
        stage=stage, group_name=group_name, priority=priority,
        due=due, action="advanced", detail=detail, task_url=task_url)

    return _send(group_email, subject, html)


def notify_task_blocked(
    group_email: str,
    group_name:  str,
    task_id:     str,
    task_title:  str,
    workflow:    str,
    stage:       str,
    priority:    str,
    due:         str,
    blocked_by:  str,
    task_url:    str = "",
) -> tuple[bool, str]:
    """
    Send when a task is marked blocked.
    Email goes to the group that currently owns the blocked stage.
    """
    if not group_email:
        return False, "No group email configured."

    detail = (f"The <strong>{workflow}</strong> workflow has been marked as "
              f"<strong style='color:#ef4444'>BLOCKED</strong> at the "
              f"<strong>{stage}</strong> stage by <strong>{blocked_by}</strong>. "
              f"Your team's attention is required to resolve the blocker.")

    subject, html = _build_email(
        task_id=task_id, task_title=task_title, workflow=workflow,
        stage=stage, group_name=group_name, priority=priority,
        due=due, action="blocked", detail=detail, task_url=task_url)

    return _send(group_email, subject, html)


def notify_task_completed(
    group_email:  str,
    group_name:   str,
    task_id:      str,
    task_title:   str,
    workflow:     str,
    priority:     str,
    completed_by: str,
    task_url:     str = "",
) -> tuple[bool, str]:
    """
    Send when a workflow is fully completed.
    Email goes to the group that actioned the final stage.
    """
    if not group_email:
        return False, "No group email configured."

    detail = (f"The <strong>{workflow}</strong> workflow has been "
              f"<strong style='color:#10b981'>COMPLETED</strong> and closed by "
              f"<strong>{completed_by}</strong>. No further action is required.")

    subject, html = _build_email(
        task_id=task_id, task_title=task_title, workflow=workflow,
        stage="Complete", group_name=group_name, priority=priority,
        due="", action="completed", detail=detail, task_url=task_url)

    return _send(group_email, subject, html)


# ══════════════════════════════════════════════════════════════════════════════
#  UTILITY
# ══════════════════════════════════════════════════════════════════════════════

def email_is_configured() -> bool:
    """Returns True if email sending is set up and enabled."""
    return _get_email_config() is not None


def test_connection() -> tuple[bool, str]:
    """
    Send a test email to the configured smtp_user address.
    Useful for verifying credentials from the Admin > Settings page.
    """
    cfg = _get_email_config()
    if not cfg:
        return False, "Email not configured or disabled."

    subject = "[WorkBench] Test Email — Connection Successful"
    html    = """
<div style="font-family:Arial,sans-serif;padding:32px;background:#111827;color:#e2e8f0;
            border-radius:8px;max-width:500px;">
  <h2 style="color:#60a5fa;margin:0 0 16px;">⬡ WorkBench — Test Email</h2>
  <p style="color:#94a3b8;">Your SMTP configuration is working correctly.
  WorkBench will send group notification emails to the addresses
  configured on each group.</p>
</div>
"""
    return _send(cfg["user"], subject, html)
