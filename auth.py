import uuid
import hashlib
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_connection


def generate_voter_id(roll_number, department):
    """Generate a unique voter ID based on roll number and department."""
    raw = f"{roll_number}-{department}-{uuid.uuid4().hex[:8]}"
    return "VID-" + hashlib.sha256(raw.encode()).hexdigest()[:12].upper()


def register_voter(full_name, email, password, date_of_birth, department, year_of_study, roll_number):
    """Register a new voter with unique identity."""
    connection = get_connection()
    try:
        voter_id = generate_voter_id(roll_number, department)
        password_hash = generate_password_hash(password)
        connection.execute(
            """INSERT INTO voters 
               (voter_id, full_name, email, password_hash, date_of_birth, department, year_of_study, roll_number, is_verified)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (voter_id, full_name, email, password_hash, date_of_birth, department, year_of_study, roll_number)
        )
        connection.commit()
        return voter_id
    except Exception as e:
        print(f"Registration error: {e}")
        return None
    finally:
        connection.close()


def login_voter(email, password):
    """Authenticate a voter by email and password."""
    connection = get_connection()
    try:
        voter = connection.execute(
            "SELECT * FROM voters WHERE email = ?", (email,)
        ).fetchone()
        if voter and check_password_hash(voter["password_hash"], password):
            return dict(voter)
        return None
    finally:
        connection.close()


def login_admin(username, password):
    """Authenticate an admin user."""
    connection = get_connection()
    try:
        admin = connection.execute(
            "SELECT * FROM admins WHERE username = ?", (username,)
        ).fetchone()
        if admin and check_password_hash(admin["password_hash"], password):
            return dict(admin)
        return None
    finally:
        connection.close()


def get_voter_by_id(voter_db_id):
    """Get voter information by database ID."""
    connection = get_connection()
    try:
        voter = connection.execute(
            "SELECT * FROM voters WHERE id = ?", (voter_db_id,)
        ).fetchone()
        return dict(voter) if voter else None
    finally:
        connection.close()


def has_voter_voted(voter_db_id, position_id):
    """Check if a voter has already voted for a specific position."""
    connection = get_connection()
    try:
        vote = connection.execute(
            "SELECT id FROM votes WHERE voter_id = ? AND position_id = ?",
            (voter_db_id, position_id)
        ).fetchone()
        return vote is not None
    finally:
        connection.close()


def mark_voter_as_voted(voter_db_id):
    """Mark that a voter has completed voting."""
    connection = get_connection()
    try:
        connection.execute(
            "UPDATE voters SET has_voted = 1 WHERE id = ?", (voter_db_id,)
        )
        connection.commit()
    finally:
        connection.close()


def log_audit(action, user_type, user_id, details, ip_address):
    """Log an action to the audit trail."""
    connection = get_connection()
    try:
        connection.execute(
            "INSERT INTO audit_log (action, user_type, user_id, details, ip_address) VALUES (?, ?, ?, ?, ?)",
            (action, user_type, user_id, details, ip_address)
        )
        connection.commit()
    finally:
        connection.close()
