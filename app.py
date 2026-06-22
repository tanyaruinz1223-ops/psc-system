import os
from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, abort)
from functools import wraps
from datetime import datetime
import db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "psc-dev-secret-2024")

# Initialize database tables on startup (runs under both gunicorn and python)
with app.app_context():
    db.init_db()

STATUS_FLOW = [
    "NEW", "UNDER REVIEW", "SOURCING", "QUOTATION", "BUYER APPROVED",
    "ORDER FULFILLED", "PAYMENT RECEIVED", "COMPLETED", "CANCELLED",
]

ROLES = {
    "admin":       "PSC Administrator",
    "finance":     "PSC Finance",
    "procurement": "PSC Procurement",
    "agent":       "Agent",
}


# ── Access control ─────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            if session.get("role") not in roles:
                flash("You do not have permission to access that page.", "error")
                return redirect(url_for("home"))
            return f(*args, **kwargs)
        return decorated
    return decorator


# ── Home redirect ──────────────────────────────────────────────────────────────

@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))
    role = session.get("role")
    if role == "agent":
        return redirect(url_for("portal_dashboard"))
    return redirect(url_for("dashboard"))


# ── Auth ───────────────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("home"))
    error = None
    if request.method == "POST":
        user = db.authenticate(request.form["username"], request.form["password"])
        if user:
            session["user_id"]   = user["id"]
            session["user_name"] = user["full_name"]
            session["role"]      = user["role"]
            session["agent_id"]  = user.get("agent_id")
            return redirect(url_for("home"))
        error = "Invalid username or password."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/apply", methods=["GET", "POST"])
def apply():
    """Public agent self-registration page."""
    if request.method == "POST":
        data = {k: request.form.get(k, "").strip() for k in [
            "full_name", "national_id", "date_of_birth", "address",
            "mobile", "email", "occupation", "bank_details", "notes"
        ]}
        if not data["full_name"] or not data["mobile"]:
            flash("Full Name and Mobile are required.", "error")
            return render_template("apply.html")
        db.create_agent(data)
        flash("Application submitted! PSC will review and contact you.", "success")
        return redirect(url_for("login"))
    return render_template("apply.html")


# ── Dashboard ──────────────────────────────────────────────────────────────────

@app.route("/dashboard")
@role_required("admin", "finance", "procurement")
def dashboard():
    stats = db.get_dashboard_stats()
    now = datetime.now().strftime("%A, %d %B %Y")
    return render_template("dashboard.html", stats=stats, now=now)


# ── Users (Admin only) ─────────────────────────────────────────────────────────

@app.route("/users")
@role_required("admin")
def users():
    user_list = db.get_all_users()
    return render_template("users/index.html", users=user_list)


@app.route("/users/new", methods=["GET", "POST"])
@role_required("admin")
def user_new():
    agents = db.get_all_agents("ACTIVE")
    if request.method == "POST":
        data = {
            "username":  request.form.get("username", "").strip(),
            "password":  request.form.get("password", "").strip(),
            "full_name": request.form.get("full_name", "").strip(),
            "role":      request.form.get("role", "finance"),
            "agent_id":  request.form.get("agent_id") or None,
        }
        if not data["username"] or not data["password"] or not data["full_name"]:
            flash("Username, password and full name are required.", "error")
            return render_template("users/form.html", user=None, agents=agents)
        try:
            db.create_user(data)
            flash(f"User '{data['username']}' created successfully.", "success")
            return redirect(url_for("users"))
        except Exception as e:
            flash("Username already exists. Choose another.", "error")
    return render_template("users/form.html", user=None, agents=agents)


@app.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def user_edit(user_id):
    user = db.get_user(user_id)
    agents = db.get_all_agents("ACTIVE")
    if not user:
        return redirect(url_for("users"))
    if request.method == "POST":
        data = {
            "full_name": request.form.get("full_name", "").strip(),
            "role":      request.form.get("role", "finance"),
            "is_active": request.form.get("is_active") == "on",
            "password":  request.form.get("password", "").strip(),
            "agent_id":  request.form.get("agent_id") or None,
        }
        db.update_user(user_id, data)
        flash("User updated successfully.", "success")
        return redirect(url_for("users"))
    return render_template("users/form.html", user=user, agents=agents)


@app.route("/users/<int:user_id>/deactivate", methods=["POST"])
@role_required("admin")
def user_deactivate(user_id):
    db.delete_user(user_id)
    flash("User deactivated.", "success")
    return redirect(url_for("users"))


# ── Agents ─────────────────────────────────────────────────────────────────────

@app.route("/agents")
@role_required("admin", "finance", "procurement")
def agents():
    status = request.args.get("status", "ALL")
    agent_list = db.get_all_agents(None if status == "ALL" else status)
    return render_template("agents/index.html", agents=agent_list, current_filter=status)


@app.route("/agents/new", methods=["GET", "POST"])
@role_required("admin")
def agent_new():
    if request.method == "POST":
        data = {k: request.form.get(k, "").strip() for k in [
            "full_name", "national_id", "date_of_birth", "address",
            "mobile", "email", "occupation", "bank_details", "notes"
        ]}
        if not data["full_name"]:
            flash("Full Name is required.", "error")
            return render_template("agents/form.html", agent=None)
        db.create_agent(data)
        flash("Agent registered successfully.", "success")
        return redirect(url_for("agents"))
    return render_template("agents/form.html", agent=None)


@app.route("/agents/<int:agent_id>")
@role_required("admin", "finance", "procurement")
def agent_detail(agent_id):
    agent = db.get_agent(agent_id)
    if not agent:
        flash("Agent not found.", "error")
        return redirect(url_for("agents"))
    leads = db.get_leads_for_agent(agent_id)
    return render_template("agents/detail.html", agent=agent, leads=leads)


@app.route("/agents/<int:agent_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def agent_edit(agent_id):
    agent = db.get_agent(agent_id)
    if not agent:
        return redirect(url_for("agents"))
    if request.method == "POST":
        data = {k: request.form.get(k, "").strip() for k in [
            "full_name", "national_id", "date_of_birth", "address",
            "mobile", "email", "occupation", "bank_details", "notes"
        ]}
        db.update_agent(agent_id, data)
        flash("Agent updated.", "success")
        return redirect(url_for("agent_detail", agent_id=agent_id))
    return render_template("agents/form.html", agent=agent)


@app.route("/agents/<int:agent_id>/approve", methods=["POST"])
@role_required("admin")
def agent_approve(agent_id):
    num, username, default_password = db.approve_agent(agent_id)
    if username:
        flash(f"Agent approved! Number: {num} | Login: {username} | Password: {default_password} — share this with the agent.", "success")
    else:
        flash(f"Agent approved! Agent Number: {num} (portal login already exists)", "success")
    return redirect(url_for("agent_detail", agent_id=agent_id))


@app.route("/agents/<int:agent_id>/reject", methods=["POST"])
@role_required("admin")
def agent_reject(agent_id):
    notes = request.form.get("notes", "").strip()
    db.reject_agent(agent_id, notes)
    flash("Agent application rejected.", "success")
    return redirect(url_for("agent_detail", agent_id=agent_id))


# ── Buyers ─────────────────────────────────────────────────────────────────────

@app.route("/buyers/new", methods=["GET", "POST"])
@role_required("admin", "procurement")
def buyer_new():
    saved = False
    if request.method == "POST":
        data = {k: request.form.get(k, "").strip() for k in [
            "name", "company_name", "contact_details", "address", "industry"
        ]}
        if not data["name"]:
            flash("Buyer name is required.", "error")
        else:
            db.create_buyer(data)
            flash("Buyer added.", "success")
            saved = True
    return render_template("leads/buyer_form.html", saved=saved)


# ── Leads ──────────────────────────────────────────────────────────────────────

@app.route("/leads")
@role_required("admin", "finance", "procurement")
def leads():
    status = request.args.get("status", "ALL")
    lead_list = db.get_all_leads(None if status == "ALL" else status)
    return render_template("leads/index.html", leads=lead_list, current_filter=status)


@app.route("/leads/new", methods=["GET", "POST"])
@role_required("admin", "procurement")
def lead_new():
    active_agents = db.get_all_agents("ACTIVE")
    buyers = db.get_all_buyers()
    if request.method == "POST":
        try:
            agent_id = int(request.form["agent_id"])
            buyer_id = int(request.form["buyer_id"])
        except (ValueError, KeyError):
            flash("Please select an agent and buyer.", "error")
            return render_template("leads/form.html", agents=active_agents, buyers=buyers)
        data = {k: request.form.get(k, "").strip() for k in [
            "product_description", "quantity", "specifications",
            "delivery_requirements", "delivery_location", "budget", "timeframe", "notes"
        ]}
        if not data["product_description"]:
            flash("Product description is required.", "error")
            return render_template("leads/form.html", agents=active_agents, buyers=buyers)
        data["agent_id"] = agent_id
        data["buyer_id"] = buyer_id
        lead_id, lead_number = db.create_lead(data)
        flash(f"Lead submitted: {lead_number}", "success")
        return redirect(url_for("lead_detail", lead_id=lead_id))
    return render_template("leads/form.html", agents=active_agents, buyers=buyers)


@app.route("/leads/<int:lead_id>")
@role_required("admin", "finance", "procurement")
def lead_detail(lead_id):
    lead = db.get_lead(lead_id)
    if not lead:
        flash("Lead not found.", "error")
        return redirect(url_for("leads"))
    return render_template("leads/detail.html", lead=lead, statuses=STATUS_FLOW)


@app.route("/leads/<int:lead_id>/status", methods=["POST"])
@role_required("admin", "procurement")
def lead_update_status(lead_id):
    status = request.form.get("status", "")
    if status in STATUS_FLOW:
        db.update_lead_status(lead_id, status)
        flash(f"Status updated to: {status}", "success")
    return redirect(url_for("lead_detail", lead_id=lead_id))


# ── Commissions ────────────────────────────────────────────────────────────────

@app.route("/commissions")
@role_required("admin", "finance")
def commissions():
    status = request.args.get("status", "ALL")
    commission_list = db.get_all_commissions(None if status == "ALL" else status)
    return render_template("commissions/index.html",
                           commissions=commission_list, current_filter=status)


@app.route("/commissions/new", methods=["GET", "POST"])
@role_required("admin", "finance")
def commission_new():
    all_leads = db.get_all_leads()
    if request.method == "POST":
        try:
            lead_id           = int(request.form["lead_id"])
            transaction_amount = float(request.form["transaction_amount"])
            commission_rate   = float(request.form["commission_rate"])
            deductions        = float(request.form.get("deductions") or 0)
        except (ValueError, KeyError):
            flash("Please fill in all required fields.", "error")
            return render_template("commissions/form.html", leads=all_leads)
        lead = db.get_lead(lead_id)
        if not lead:
            flash("Lead not found.", "error")
            return render_template("commissions/form.html", leads=all_leads)
        data = {
            "lead_id": lead_id,
            "agent_id": lead["agent_id"],
            "transaction_amount": transaction_amount,
            "commission_rate": commission_rate,
            "deductions": deductions,
            "notes": request.form.get("notes", "").strip(),
        }
        com_id, ref = db.create_commission(data)
        flash(f"Commission created: {ref}", "success")
        return redirect(url_for("commission_detail", commission_id=com_id))
    return render_template("commissions/form.html", leads=all_leads)


@app.route("/commissions/<int:commission_id>")
@role_required("admin", "finance")
def commission_detail(commission_id):
    c = db.get_commission(commission_id)
    if not c:
        flash("Commission not found.", "error")
        return redirect(url_for("commissions"))
    return render_template("commissions/detail.html", c=c)


@app.route("/commissions/<int:commission_id>/approve", methods=["POST"])
@role_required("admin", "finance")
def commission_approve(commission_id):
    db.approve_commission(commission_id)
    flash("Commission approved.", "success")
    return redirect(url_for("commission_detail", commission_id=commission_id))


@app.route("/commissions/<int:commission_id>/pay", methods=["POST"])
@role_required("admin", "finance")
def commission_pay(commission_id):
    method = request.form.get("payment_method", "Bank Transfer")
    db.pay_commission(commission_id, method)
    flash(f"Commission marked as paid via {method}.", "success")
    return redirect(url_for("commission_detail", commission_id=commission_id))


# ── Agent Portal ───────────────────────────────────────────────────────────────

@app.route("/portal")
@role_required("agent")
def portal_dashboard():
    agent_id = session.get("agent_id")
    if agent_id:
        stats = db.get_dashboard_stats(agent_id=agent_id)
    else:
        stats = {
            "my_leads": 0, "my_new_leads": 0, "my_completed": 0,
            "my_pending_commissions": 0, "my_approved_commissions": 0,
            "my_total_earned": 0,
        }
    agent = db.get_agent(agent_id) if agent_id else None
    return render_template("portal/dashboard.html", stats=stats, agent=agent)


@app.route("/portal/leads")
@role_required("agent")
def portal_leads():
    agent_id = session.get("agent_id")
    status = request.args.get("status", "ALL")
    lead_list = db.get_all_leads(
        None if status == "ALL" else status,
        agent_id=agent_id
    )
    return render_template("portal/leads.html", leads=lead_list, current_filter=status)


@app.route("/portal/leads/new", methods=["GET", "POST"])
@role_required("agent")
def portal_lead_new():
    agent_id = session.get("agent_id")
    buyers = db.get_all_buyers()
    if request.method == "POST":
        try:
            buyer_id = int(request.form["buyer_id"])
        except (ValueError, KeyError):
            flash("Please select a buyer.", "error")
            return render_template("portal/lead_form.html", buyers=buyers)
        data = {k: request.form.get(k, "").strip() for k in [
            "product_description", "quantity", "specifications",
            "delivery_requirements", "delivery_location", "budget", "timeframe", "notes"
        ]}
        if not data["product_description"]:
            flash("Product description is required.", "error")
            return render_template("portal/lead_form.html", buyers=buyers)
        data["agent_id"] = agent_id
        data["buyer_id"] = buyer_id
        lead_id, lead_number = db.create_lead(data)
        flash(f"Lead submitted: {lead_number}", "success")
        return redirect(url_for("portal_leads"))
    return render_template("portal/lead_form.html", buyers=buyers)


@app.route("/portal/buyers/new", methods=["GET", "POST"])
@role_required("agent")
def portal_buyer_new():
    saved = False
    if request.method == "POST":
        data = {k: request.form.get(k, "").strip() for k in [
            "name", "company_name", "contact_details", "address", "industry"
        ]}
        if not data["name"]:
            flash("Buyer name is required.", "error")
        else:
            db.create_buyer(data)
            flash("Buyer added.", "success")
            saved = True
    return render_template("leads/buyer_form.html", saved=saved)


@app.route("/portal/commissions")
@role_required("agent")
def portal_commissions():
    agent_id = session.get("agent_id")
    status = request.args.get("status", "ALL")
    commission_list = db.get_all_commissions(
        None if status == "ALL" else status,
        agent_id=agent_id
    )
    return render_template("portal/commissions.html",
                           commissions=commission_list, current_filter=status)


# ── Profile ────────────────────────────────────────────────────────────────────

@app.route("/profile")
@login_required
def profile():
    user = db.get_user(session["user_id"])
    return render_template("profile.html", user=user)


@app.route("/profile/name", methods=["POST"])
@login_required
def profile_update_name():
    full_name = request.form.get("full_name", "").strip()
    if full_name:
        db.execute("UPDATE users SET full_name=%s WHERE id=%s",
                   (full_name, session["user_id"]))
        session["user_name"] = full_name
        flash("Name updated successfully.", "success")
    return redirect(url_for("profile"))


@app.route("/profile/password", methods=["POST"])
@login_required
def profile_change_password():
    current = request.form.get("current_password", "")
    new_pw  = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")

    user = db.authenticate(session.get("username", ""), current)
    # Verify current password manually
    import hashlib
    current_hash = hashlib.sha256(current.encode()).hexdigest()
    db_user = db.fetchone("SELECT * FROM users WHERE id=%s AND password_hash=%s",
                          (session["user_id"], current_hash))
    if not db_user:
        flash("Current password is incorrect.", "error")
        return redirect(url_for("profile"))
    if new_pw != confirm:
        flash("New passwords do not match.", "error")
        return redirect(url_for("profile"))
    if len(new_pw) < 6:
        flash("Password must be at least 6 characters.", "error")
        return redirect(url_for("profile"))

    new_hash = hashlib.sha256(new_pw.encode()).hexdigest()
    db.execute("UPDATE users SET password_hash=%s WHERE id=%s",
               (new_hash, session["user_id"]))
    flash("Password changed successfully.", "success")
    return redirect(url_for("profile"))


if __name__ == "__main__":
    db.init_db()
    app.run(debug=True)
