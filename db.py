import os
import hashlib
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

def get_db_url():
    url = os.environ.get("DATABASE_URL", "")
    # Render provides postgres:// but psycopg2 needs postgresql://
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


def get_conn():
    conn = psycopg2.connect(get_db_url())
    return conn


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'admin',
            agent_id INTEGER,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            id SERIAL PRIMARY KEY,
            agent_number TEXT UNIQUE,
            full_name TEXT NOT NULL,
            national_id TEXT,
            date_of_birth TEXT,
            address TEXT,
            mobile TEXT,
            email TEXT,
            occupation TEXT,
            bank_details TEXT,
            status TEXT DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT NOW(),
            approved_at TIMESTAMP,
            notes TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS buyers (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            company_name TEXT,
            contact_details TEXT,
            address TEXT,
            industry TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id SERIAL PRIMARY KEY,
            lead_number TEXT UNIQUE NOT NULL,
            agent_id INTEGER NOT NULL REFERENCES agents(id),
            buyer_id INTEGER NOT NULL REFERENCES buyers(id),
            product_description TEXT,
            quantity TEXT,
            specifications TEXT,
            delivery_requirements TEXT,
            delivery_location TEXT,
            budget TEXT,
            timeframe TEXT,
            status TEXT DEFAULT 'NEW',
            submitted_at TIMESTAMP DEFAULT NOW(),
            reviewed_at TIMESTAMP,
            notes TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS commissions (
            id SERIAL PRIMARY KEY,
            commission_ref TEXT UNIQUE NOT NULL,
            lead_id INTEGER NOT NULL REFERENCES leads(id),
            agent_id INTEGER NOT NULL REFERENCES agents(id),
            transaction_amount NUMERIC(15,2) NOT NULL,
            commission_rate NUMERIC(5,2) NOT NULL,
            gross_commission NUMERIC(15,2),
            deductions NUMERIC(15,2) DEFAULT 0,
            net_commission NUMERIC(15,2),
            status TEXT DEFAULT 'PENDING',
            calculated_at TIMESTAMP DEFAULT NOW(),
            approved_at TIMESTAMP,
            paid_at TIMESTAMP,
            payment_method TEXT,
            notes TEXT
        )
    """)

    # Seed default admin
    c.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
    if c.fetchone()[0] == 0:
        c.execute("""
            INSERT INTO users (username, password_hash, full_name, role)
            VALUES (%s, %s, %s, 'admin')
        """, ("admin", hash_password("admin123"), "PSC Administrator"))

    conn.commit()
    c.close()
    conn.close()


def _serialize(row):
    """Convert datetime objects to ISO strings so templates can use [:10] slicing."""
    from datetime import datetime, date
    result = {}
    for k, v in row.items():
        if isinstance(v, datetime):
            result[k] = v.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(v, date):
            result[k] = v.strftime("%Y-%m-%d")
        else:
            result[k] = v
    return result


def fetchall(sql, params=()):
    conn = get_conn()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute(sql, params)
    rows = c.fetchall()
    c.close()
    conn.close()
    return [_serialize(dict(r)) for r in rows]


def fetchone(sql, params=()):
    conn = get_conn()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute(sql, params)
    row = c.fetchone()
    c.close()
    conn.close()
    return _serialize(dict(row)) if row else None


def execute(sql, params=()):
    conn = get_conn()
    c = conn.cursor()
    c.execute(sql, params)
    conn.commit()
    c.close()
    conn.close()


def execute_returning(sql, params=()):
    conn = get_conn()
    c = conn.cursor()
    c.execute(sql, params)
    row = c.fetchone()
    conn.commit()
    c.close()
    conn.close()
    return row[0] if row else None


# ── Auth ───────────────────────────────────────────────────────────────────────

def authenticate(username, password):
    return fetchone(
        "SELECT * FROM users WHERE username=%s AND password_hash=%s AND is_active=TRUE",
        (username, hash_password(password))
    )


# ── Users ──────────────────────────────────────────────────────────────────────

def get_all_users():
    return fetchall("SELECT * FROM users ORDER BY role, full_name")


def get_user(user_id):
    return fetchone("SELECT * FROM users WHERE id=%s", (user_id,))


def create_user(data):
    return execute_returning("""
        INSERT INTO users (username, password_hash, full_name, role, agent_id)
        VALUES (%s, %s, %s, %s, %s) RETURNING id
    """, (data["username"], hash_password(data["password"]),
          data["full_name"], data["role"], data.get("agent_id")))


def update_user(user_id, data):
    if data.get("password"):
        execute("""
            UPDATE users SET full_name=%s, role=%s, is_active=%s, password_hash=%s
            WHERE id=%s
        """, (data["full_name"], data["role"], data.get("is_active", True),
              hash_password(data["password"]), user_id))
    else:
        execute("""
            UPDATE users SET full_name=%s, role=%s, is_active=%s WHERE id=%s
        """, (data["full_name"], data["role"], data.get("is_active", True), user_id))


def delete_user(user_id):
    execute("UPDATE users SET is_active=FALSE WHERE id=%s", (user_id,))


# ── Agents ─────────────────────────────────────────────────────────────────────

def get_all_agents(status=None):
    if status:
        return fetchall("SELECT * FROM agents WHERE status=%s ORDER BY created_at DESC", (status,))
    return fetchall("SELECT * FROM agents ORDER BY created_at DESC")


def get_agent(agent_id):
    return fetchone("SELECT * FROM agents WHERE id=%s", (agent_id,))


def create_agent(data):
    return execute_returning("""
        INSERT INTO agents (full_name, national_id, date_of_birth, address,
            mobile, email, occupation, bank_details, notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
    """, (data["full_name"], data.get("national_id"), data.get("date_of_birth"),
          data.get("address"), data.get("mobile"), data.get("email"),
          data.get("occupation"), data.get("bank_details"), data.get("notes")))


def approve_agent(agent_id):
    count = fetchone("SELECT COUNT(*) AS cnt FROM agents")["cnt"]
    agent_number = f"PSC-AGT-{int(count):04d}"
    execute("""
        UPDATE agents SET status='ACTIVE', agent_number=%s, approved_at=NOW()
        WHERE id=%s
    """, (agent_number, agent_id))
    return agent_number


def reject_agent(agent_id, notes=""):
    execute("UPDATE agents SET status='REJECTED', notes=%s WHERE id=%s", (notes, agent_id))


def update_agent(agent_id, data):
    execute("""
        UPDATE agents SET full_name=%s, national_id=%s, date_of_birth=%s,
            address=%s, mobile=%s, email=%s, occupation=%s,
            bank_details=%s, notes=%s WHERE id=%s
    """, (data["full_name"], data.get("national_id"), data.get("date_of_birth"),
          data.get("address"), data.get("mobile"), data.get("email"),
          data.get("occupation"), data.get("bank_details"), data.get("notes"), agent_id))


def agent_self_register(data):
    return create_agent(data)


# ── Buyers ─────────────────────────────────────────────────────────────────────

def get_all_buyers():
    return fetchall("SELECT * FROM buyers ORDER BY name")


def create_buyer(data):
    return execute_returning("""
        INSERT INTO buyers (name, company_name, contact_details, address, industry)
        VALUES (%s,%s,%s,%s,%s) RETURNING id
    """, (data["name"], data.get("company_name"), data.get("contact_details"),
          data.get("address"), data.get("industry")))


# ── Leads ──────────────────────────────────────────────────────────────────────

def get_all_leads(status=None, agent_id=None):
    base = """
        SELECT l.*, a.full_name AS agent_name, a.agent_number,
               b.name AS buyer_name, b.company_name
        FROM leads l
        JOIN agents a ON l.agent_id=a.id
        JOIN buyers b ON l.buyer_id=b.id
    """
    conditions = []
    params = []
    if status:
        conditions.append("l.status=%s")
        params.append(status)
    if agent_id:
        conditions.append("l.agent_id=%s")
        params.append(agent_id)
    if conditions:
        base += " WHERE " + " AND ".join(conditions)
    base += " ORDER BY l.submitted_at DESC"
    return fetchall(base, params)


def get_lead(lead_id):
    return fetchone("""
        SELECT l.*, a.full_name AS agent_name, a.agent_number, a.mobile AS agent_mobile,
               b.name AS buyer_name, b.company_name, b.contact_details AS buyer_contact
        FROM leads l
        JOIN agents a ON l.agent_id=a.id
        JOIN buyers b ON l.buyer_id=b.id
        WHERE l.id=%s
    """, (lead_id,))


def create_lead(data):
    count = fetchone("SELECT COUNT(*) AS cnt FROM leads")["cnt"]
    lead_number = f"PSC-LED-{int(count)+1:05d}"
    lead_id = execute_returning("""
        INSERT INTO leads (lead_number, agent_id, buyer_id, product_description,
            quantity, specifications, delivery_requirements, delivery_location,
            budget, timeframe, notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
    """, (lead_number, data["agent_id"], data["buyer_id"],
          data.get("product_description"), data.get("quantity"),
          data.get("specifications"), data.get("delivery_requirements"),
          data.get("delivery_location"), data.get("budget"),
          data.get("timeframe"), data.get("notes")))
    return lead_id, lead_number


def update_lead_status(lead_id, status):
    if status == "UNDER REVIEW":
        execute("UPDATE leads SET status=%s, reviewed_at=NOW() WHERE id=%s", (status, lead_id))
    else:
        execute("UPDATE leads SET status=%s WHERE id=%s", (status, lead_id))


def get_leads_for_agent(agent_id):
    return fetchall("""
        SELECT l.*, b.name AS buyer_name FROM leads l
        JOIN buyers b ON l.buyer_id=b.id
        WHERE l.agent_id=%s ORDER BY l.submitted_at DESC
    """, (agent_id,))


# ── Commissions ────────────────────────────────────────────────────────────────

def get_all_commissions(status=None, agent_id=None):
    base = """
        SELECT cm.*, a.full_name AS agent_name, a.agent_number, a.bank_details,
               l.lead_number, b.name AS buyer_name
        FROM commissions cm
        JOIN agents a ON cm.agent_id=a.id
        JOIN leads l ON cm.lead_id=l.id
        JOIN buyers b ON l.buyer_id=b.id
    """
    conditions = []
    params = []
    if status:
        conditions.append("cm.status=%s")
        params.append(status)
    if agent_id:
        conditions.append("cm.agent_id=%s")
        params.append(agent_id)
    if conditions:
        base += " WHERE " + " AND ".join(conditions)
    base += " ORDER BY cm.calculated_at DESC"
    return fetchall(base, params)


def get_commission(commission_id):
    return fetchone("""
        SELECT cm.*, a.full_name AS agent_name, a.agent_number, a.bank_details,
               l.lead_number, b.name AS buyer_name
        FROM commissions cm
        JOIN agents a ON cm.agent_id=a.id
        JOIN leads l ON cm.lead_id=l.id
        JOIN buyers b ON l.buyer_id=b.id
        WHERE cm.id=%s
    """, (commission_id,))


def create_commission(data):
    count = fetchone("SELECT COUNT(*) AS cnt FROM commissions")["cnt"]
    ref = f"PSC-COM-{int(count)+1:05d}"
    gross = float(data["transaction_amount"]) * (float(data["commission_rate"]) / 100)
    net = gross - float(data.get("deductions", 0))
    com_id = execute_returning("""
        INSERT INTO commissions (commission_ref, lead_id, agent_id, transaction_amount,
            commission_rate, gross_commission, deductions, net_commission, notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
    """, (ref, data["lead_id"], data["agent_id"], data["transaction_amount"],
          data["commission_rate"], gross, data.get("deductions", 0), net, data.get("notes", "")))
    return com_id, ref


def approve_commission(commission_id):
    execute("UPDATE commissions SET status='APPROVED', approved_at=NOW() WHERE id=%s",
            (commission_id,))


def pay_commission(commission_id, method):
    execute("UPDATE commissions SET status='PAID', paid_at=NOW(), payment_method=%s WHERE id=%s",
            (method, commission_id))


# ── Dashboard stats ────────────────────────────────────────────────────────────

def get_dashboard_stats(agent_id=None):
    def count(sql, params=()):
        return fetchone(sql, params)

    if agent_id:
        return {
            "my_leads": count("SELECT COUNT(*) AS cnt FROM leads WHERE agent_id=%s", (agent_id,))["cnt"],
            "my_new_leads": count("SELECT COUNT(*) AS cnt FROM leads WHERE agent_id=%s AND status='NEW'", (agent_id,))["cnt"],
            "my_completed": count("SELECT COUNT(*) AS cnt FROM leads WHERE agent_id=%s AND status='COMPLETED'", (agent_id,))["cnt"],
            "my_pending_commissions": count("SELECT COUNT(*) AS cnt FROM commissions WHERE agent_id=%s AND status='PENDING'", (agent_id,))["cnt"],
            "my_approved_commissions": count("SELECT COUNT(*) AS cnt FROM commissions WHERE agent_id=%s AND status='APPROVED'", (agent_id,))["cnt"],
            "my_total_earned": count("SELECT COALESCE(SUM(net_commission),0) AS cnt FROM commissions WHERE agent_id=%s AND status='PAID'", (agent_id,))["cnt"],
        }

    return {
        "pending_agents": count("SELECT COUNT(*) AS cnt FROM agents WHERE status='PENDING'")["cnt"],
        "active_agents": count("SELECT COUNT(*) AS cnt FROM agents WHERE status='ACTIVE'")["cnt"],
        "rejected_agents": count("SELECT COUNT(*) AS cnt FROM agents WHERE status='REJECTED'")["cnt"],
        "new_leads": count("SELECT COUNT(*) AS cnt FROM leads WHERE status='NEW'")["cnt"],
        "review_leads": count("SELECT COUNT(*) AS cnt FROM leads WHERE status='UNDER REVIEW'")["cnt"],
        "total_leads": count("SELECT COUNT(*) AS cnt FROM leads")["cnt"],
        "pending_commissions": count("SELECT COUNT(*) AS cnt FROM commissions WHERE status='PENDING'")["cnt"],
        "approved_commissions": count("SELECT COUNT(*) AS cnt FROM commissions WHERE status='APPROVED'")["cnt"],
        "total_paid": count("SELECT COALESCE(SUM(net_commission),0) AS cnt FROM commissions WHERE status='PAID'")["cnt"],
        "total_users": count("SELECT COUNT(*) AS cnt FROM users WHERE is_active=TRUE")["cnt"],
    }
