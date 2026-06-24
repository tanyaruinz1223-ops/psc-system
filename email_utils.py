import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

SENDER_EMAIL = "tanyaruinz1223@gmail.com"
SENDER_NAME  = "ProcureLink"
APP_URL      = "https://psc-system.onrender.com"


def _send(to_email, subject, html_content):
    if not to_email:
        return
    try:
        sg = SendGridAPIClient(os.environ.get("SENDGRID_API_KEY"))
        msg = Mail(
            from_email=(SENDER_EMAIL, SENDER_NAME),
            to_emails=to_email,
            subject=subject,
            html_content=html_content
        )
        sg.send(msg)
    except Exception as e:
        print(f"[Email error] {e}")


def send_agent_approved(agent, username, default_password):
    if not agent.get("email"):
        return
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto">
      <div style="background:#0d1b3e;padding:24px;text-align:center">
        <h1 style="color:#60a5fa;margin:0">ProcureLink</h1>
        <p style="color:#93c5fd;margin:4px 0 0">Your Procurement Companion</p>
      </div>
      <div style="padding:32px;background:#f8fafc">
        <h2 style="color:#0d1b3e">Congratulations, {agent['full_name']}!</h2>
        <p>Your ProcureLink agent application has been <strong style="color:#16a34a">approved</strong>.</p>
        <p>Your agent number is: <strong>{agent.get('agent_number','')}</strong></p>

        <div style="background:white;border-radius:8px;padding:20px;margin:20px 0;border-left:4px solid #2563eb">
          <p style="margin:0 0 8px"><strong>Your Login Credentials:</strong></p>
          <p style="margin:0">Username: <code style="background:#f1f5f9;padding:2px 6px;border-radius:4px">{username}</code></p>
          <p style="margin:8px 0 0">Password: <code style="background:#f1f5f9;padding:2px 6px;border-radius:4px">{default_password}</code></p>
        </div>

        <p>Please change your password after your first login.</p>

        <a href="{APP_URL}" style="display:inline-block;background:#2563eb;color:white;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:bold;margin-top:8px">
          Login to Your Portal
        </a>

        <p style="color:#64748b;font-size:0.85rem;margin-top:24px">
          If you have any questions, contact your ProcureLink administrator.
        </p>
      </div>
    </div>
    """
    _send(agent["email"], "ProcureLink — Your Application is Approved!", html)


def send_agent_rejected(agent, reason=""):
    if not agent.get("email"):
        return
    reason_text = f"<p><strong>Reason:</strong> {reason}</p>" if reason else ""
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto">
      <div style="background:#0d1b3e;padding:24px;text-align:center">
        <h1 style="color:#60a5fa;margin:0">ProcureLink</h1>
        <p style="color:#93c5fd;margin:4px 0 0">Your Procurement Companion</p>
      </div>
      <div style="padding:32px;background:#f8fafc">
        <h2 style="color:#0d1b3e">Application Update</h2>
        <p>Dear {agent['full_name']},</p>
        <p>Thank you for your interest in becoming a ProcureLink agent.</p>
        <p>After reviewing your application, we regret to inform you that we are <strong style="color:#dc2626">unable to approve</strong> your application at this time.</p>
        {reason_text}
        <p>You are welcome to reapply in the future. If you believe this is an error, please contact us.</p>
        <p style="color:#64748b;font-size:0.85rem;margin-top:24px">The ProcureLink Team</p>
      </div>
    </div>
    """
    _send(agent["email"], "ProcureLink — Application Status Update", html)


def send_lead_status_update(agent_email, agent_name, lead_number, new_status):
    if not agent_email:
        return
    status_color = {
        "NEW": "#2563eb", "UNDER REVIEW": "#7c3aed", "COMPLETED": "#16a34a",
        "REJECTED": "#dc2626", "SOURCING": "#d97706", "QUOTATION": "#d97706",
    }.get(new_status, "#0d1b3e")
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto">
      <div style="background:#0d1b3e;padding:24px;text-align:center">
        <h1 style="color:#60a5fa;margin:0">ProcureLink</h1>
        <p style="color:#93c5fd;margin:4px 0 0">Your Procurement Companion</p>
      </div>
      <div style="padding:32px;background:#f8fafc">
        <h2 style="color:#0d1b3e">Lead Status Update</h2>
        <p>Dear {agent_name},</p>
        <p>Your lead <strong>{lead_number}</strong> has been updated.</p>
        <div style="background:white;border-radius:8px;padding:20px;margin:20px 0;text-align:center">
          <p style="margin:0;color:#64748b">New Status</p>
          <p style="margin:8px 0 0;font-size:1.4rem;font-weight:bold;color:{status_color}">{new_status}</p>
        </div>
        <a href="{APP_URL}/portal/leads" style="display:inline-block;background:#2563eb;color:white;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:bold">
          View My Leads
        </a>
      </div>
    </div>
    """
    _send(agent_email, f"ProcureLink — Lead {lead_number} Status Update", html)


def send_commission_approved(agent_email, agent_name, commission_ref, amount):
    if not agent_email:
        return
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto">
      <div style="background:#0d1b3e;padding:24px;text-align:center">
        <h1 style="color:#60a5fa;margin:0">ProcureLink</h1>
        <p style="color:#93c5fd;margin:4px 0 0">Your Procurement Companion</p>
      </div>
      <div style="padding:32px;background:#f8fafc">
        <h2 style="color:#0d1b3e">Commission Approved</h2>
        <p>Dear {agent_name},</p>
        <p>Great news! Your commission <strong>{commission_ref}</strong> has been <strong style="color:#16a34a">approved</strong>.</p>
        <div style="background:white;border-radius:8px;padding:20px;margin:20px 0;text-align:center;border-top:4px solid #16a34a">
          <p style="margin:0;color:#64748b">Approved Amount</p>
          <p style="margin:8px 0 0;font-size:2rem;font-weight:bold;color:#16a34a">${amount:,.2f}</p>
        </div>
        <p>Payment will be processed shortly. You will receive another notification when payment is made.</p>
        <a href="{APP_URL}/portal/commissions" style="display:inline-block;background:#2563eb;color:white;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:bold">
          View My Commissions
        </a>
      </div>
    </div>
    """
    _send(agent_email, f"ProcureLink — Commission {commission_ref} Approved", html)


def send_commission_paid(agent_email, agent_name, commission_ref, amount, payment_method):
    if not agent_email:
        return
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto">
      <div style="background:#0d1b3e;padding:24px;text-align:center">
        <h1 style="color:#60a5fa;margin:0">ProcureLink</h1>
        <p style="color:#93c5fd;margin:4px 0 0">Your Procurement Companion</p>
      </div>
      <div style="padding:32px;background:#f8fafc">
        <h2 style="color:#0d1b3e">Payment Processed!</h2>
        <p>Dear {agent_name},</p>
        <p>Your commission payment <strong>{commission_ref}</strong> has been <strong style="color:#2563eb">paid</strong>.</p>
        <div style="background:white;border-radius:8px;padding:20px;margin:20px 0;text-align:center;border-top:4px solid #2563eb">
          <p style="margin:0;color:#64748b">Amount Paid</p>
          <p style="margin:8px 0 0;font-size:2rem;font-weight:bold;color:#2563eb">${amount:,.2f}</p>
          <p style="margin:8px 0 0;color:#64748b">via {payment_method}</p>
        </div>
        <a href="{APP_URL}/portal/commissions" style="display:inline-block;background:#2563eb;color:white;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:bold">
          View My Commissions
        </a>
        <p style="color:#64748b;font-size:0.85rem;margin-top:24px">Thank you for being a valued ProcureLink agent.</p>
      </div>
    </div>
    """
    _send(agent_email, f"ProcureLink — Payment Received for {commission_ref}", html)
