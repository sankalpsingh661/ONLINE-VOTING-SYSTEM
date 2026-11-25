import os
import secrets
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from database import create_tables, get_connection, seed_data
from auth import (
    register_voter, login_voter, login_admin, get_voter_by_id,
    has_voter_voted, mark_voter_as_voted, log_audit
)
from encryption import encrypt_vote, decrypt_vote, hash_vote
from functools import wraps

app = Flask(__name__)
app.config["SECRET_KEY"] = secrets.token_hex(32)

# Initialize database
create_tables()
seed_data()


# ─── Decorators ───────────────────────────────────────────────

def voter_required(f):
    """Decorator to require voter login."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "voter_id" not in session:
            flash("Please login to continue.", "warning")
            return redirect(url_for("voter_login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Decorator to require admin login."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "admin_id" not in session:
            flash("Admin access required.", "warning")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated


# ─── Public Routes ────────────────────────────────────────────

@app.route("/")
def home():
    """Landing page."""
    return render_template("index.html")


# ─── Voter Registration ──────────────────────────────────────

@app.route("/register", methods=["GET", "POST"])
def register():
    """Voter registration page."""
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        dob = request.form.get("date_of_birth", "")
        department = request.form.get("department", "")
        year = request.form.get("year_of_study", "")
        roll_number = request.form.get("roll_number", "").strip()

        # Validation
        errors = []
        if not all([full_name, email, password, dob, department, year, roll_number]):
            errors.append("All fields are required.")
        if password != confirm_password:
            errors.append("Passwords do not match.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")

        if errors:
            for err in errors:
                flash(err, "danger")
            return render_template("register.html")

        voter_id = register_voter(full_name, email, password, dob, department, int(year), roll_number)
        if voter_id:
            log_audit("REGISTER", "voter", None, f"New voter registered: {email}", request.remote_addr)
            flash(f"Registration successful! Your Voter ID is: {voter_id}. Please save it for your records.", "success")
            return redirect(url_for("voter_login"))
        else:
            flash("Registration failed. Email or Roll Number may already be registered.", "danger")

    return render_template("register.html")


# ─── Voter Login ──────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def voter_login():
    """Voter login page."""
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        voter = login_voter(email, password)
        if voter:
            session["voter_id"] = voter["id"]
            session["voter_name"] = voter["full_name"]
            session["voter_uid"] = voter["voter_id"]
            session["user_type"] = "voter"
            log_audit("LOGIN", "voter", voter["id"], "Voter logged in", request.remote_addr)
            flash(f"Welcome, {voter['full_name']}!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password.", "danger")

    return render_template("login.html")


# ─── Voter Dashboard ─────────────────────────────────────────

@app.route("/dashboard")
@voter_required
def dashboard():
    """Voter dashboard - shows active elections."""
    connection = get_connection()
    try:
        elections = connection.execute(
            "SELECT * FROM elections WHERE is_active = 1"
        ).fetchall()
        voter = get_voter_by_id(session["voter_id"])
        return render_template("dashboard.html", elections=elections, voter=voter)
    finally:
        connection.close()


# ─── Voting Booth ─────────────────────────────────────────────

@app.route("/vote/<int:election_id>")
@voter_required
def vote_booth(election_id):
    """Display the voting booth for an election."""
    voter = get_voter_by_id(session["voter_id"])
    if voter["has_voted"]:
        flash("You have already cast your vote in this election.", "info")
        return redirect(url_for("dashboard"))

    connection = get_connection()
    try:
        election = connection.execute(
            "SELECT * FROM elections WHERE id = ? AND is_active = 1", (election_id,)
        ).fetchone()

        if not election:
            flash("Election not found or has ended.", "danger")
            return redirect(url_for("dashboard"))

        positions = connection.execute(
            "SELECT * FROM positions WHERE election_id = ?", (election_id,)
        ).fetchall()

        candidates_by_position = {}
        for pos in positions:
            candidates = connection.execute(
                "SELECT * FROM candidates WHERE position_id = ?", (pos["id"],)
            ).fetchall()
            candidates_by_position[pos["id"]] = [dict(c) for c in candidates]

        return render_template(
            "vote.html",
            election=election,
            positions=positions,
            candidates=candidates_by_position,
            voter=voter
        )
    finally:
        connection.close()


@app.route("/cast-vote", methods=["POST"])
@voter_required
def cast_vote():
    """Process the vote submission."""
    voter = get_voter_by_id(session["voter_id"])
    if voter["has_voted"]:
        flash("You have already cast your vote.", "warning")
        return redirect(url_for("dashboard"))

    connection = get_connection()
    try:
        # Get all positions for the active election
        election = connection.execute(
            "SELECT * FROM elections WHERE is_active = 1"
        ).fetchone()

        if not election:
            flash("No active election found.", "danger")
            return redirect(url_for("dashboard"))

        positions = connection.execute(
            "SELECT * FROM positions WHERE election_id = ?", (election["id"],)
        ).fetchall()

        votes_cast = 0
        for pos in positions:
            candidate_id = request.form.get(f"position_{pos['id']}")
            if candidate_id:
                # Validate candidate belongs to this position
                valid_candidate = connection.execute(
                    "SELECT id FROM candidates WHERE id = ? AND position_id = ?",
                    (candidate_id, pos["id"])
                ).fetchone()

                if not valid_candidate:
                    flash("Invalid candidate selection detected.", "danger")
                    return redirect(url_for("vote_booth", election_id=election["id"]))

                # Check if already voted for this position using active connection
                already_voted = connection.execute(
                    "SELECT id FROM votes WHERE voter_id = ? AND position_id = ?",
                    (session["voter_id"], pos["id"])
                ).fetchone()
                if already_voted:
                    continue

                # Encrypt the vote
                vote_text = f"{candidate_id}"
                encrypted = encrypt_vote(vote_text)
                vote_hash_val = hash_vote(session["voter_id"], candidate_id, pos["id"])

                connection.execute(
                    "INSERT INTO votes (voter_id, position_id, encrypted_vote, vote_hash) VALUES (?, ?, ?, ?)",
                    (session["voter_id"], pos["id"], encrypted, vote_hash_val)
                )
                votes_cast += 1

        if votes_cast > 0:
            connection.execute(
                "UPDATE voters SET has_voted = 1 WHERE id = ?", (session["voter_id"],)
            )
            connection.commit()
            log_audit("VOTE", "voter", session["voter_id"], f"Cast {votes_cast} votes", request.remote_addr)
            flash("Your vote has been cast successfully! Thank you for participating.", "success")
        else:
            flash("No votes were recorded. Please select at least one candidate.", "warning")
            return redirect(url_for("vote_booth", election_id=election["id"]))

        return redirect(url_for("vote_confirmation"))
    except Exception as e:
        connection.rollback()
        import traceback
        traceback.print_exc()
        flash(f"An error occurred while processing your vote: {e}", "danger")
        return redirect(url_for("dashboard"))
    finally:
        connection.close()


@app.route("/confirmation")
@voter_required
def vote_confirmation():
    """Vote confirmation page."""
    voter = get_voter_by_id(session["voter_id"])
    return render_template("confirmation.html", voter=voter)


# ─── Admin Routes ─────────────────────────────────────────────

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    """Admin login page."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        admin = login_admin(username, password)
        if admin:
            session["admin_id"] = admin["id"]
            session["admin_name"] = admin["full_name"]
            session["user_type"] = "admin"
            log_audit("LOGIN", "admin", admin["id"], "Admin logged in", request.remote_addr)
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid admin credentials.", "danger")

    return render_template("admin_login.html")


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    """Admin dashboard with election overview."""
    connection = get_connection()
    try:
        elections = connection.execute("SELECT * FROM elections").fetchall()
        total_voters = connection.execute("SELECT COUNT(*) as c FROM voters").fetchone()["c"]
        total_voted = connection.execute("SELECT COUNT(*) as c FROM voters WHERE has_voted = 1").fetchone()["c"]
        turnout = round((total_voted / total_voters * 100), 1) if total_voters > 0 else 0

        return render_template("admin_dashboard.html",
                               elections=elections,
                               total_voters=total_voters,
                               total_voted=total_voted,
                               turnout=turnout)
    finally:
        connection.close()


@app.route("/admin/results/<int:election_id>")
@admin_required
def admin_results(election_id):
    """View election results (admin only)."""
    connection = get_connection()
    try:
        election = connection.execute(
            "SELECT * FROM elections WHERE id = ?", (election_id,)
        ).fetchone()

        positions = connection.execute(
            "SELECT * FROM positions WHERE election_id = ?", (election_id,)
        ).fetchall()

        results = {}
        for pos in positions:
            candidates = connection.execute("""
                SELECT c.id, c.name, c.department, c.manifesto,
                       COUNT(v.id) as vote_count
                FROM candidates c
                LEFT JOIN votes v ON v.position_id = c.position_id
                    AND v.encrypted_vote IS NOT NULL
                WHERE c.position_id = ?
                GROUP BY c.id
                ORDER BY vote_count DESC
            """, (pos["id"],)).fetchall()

            # We need to count votes properly by decrypting
            candidate_votes = {}
            votes = connection.execute(
                "SELECT encrypted_vote FROM votes WHERE position_id = ?", (pos["id"],)
            ).fetchall()

            for v in votes:
                try:
                    decrypted = decrypt_vote(v["encrypted_vote"])
                    cid = int(decrypted)
                    candidate_votes[cid] = candidate_votes.get(cid, 0) + 1
                except Exception:
                    pass

            result_list = []
            for c in candidates:
                result_list.append({
                    "id": c["id"],
                    "name": c["name"],
                    "department": c["department"],
                    "vote_count": candidate_votes.get(c["id"], 0)
                })
            result_list.sort(key=lambda x: x["vote_count"], reverse=True)
            results[pos["id"]] = {
                "position": dict(pos),
                "candidates": result_list,
                "total_votes": sum(r["vote_count"] for r in result_list)
            }

        total_voters = connection.execute("SELECT COUNT(*) as c FROM voters WHERE is_verified = 1").fetchone()["c"]
        total_voted = connection.execute("SELECT COUNT(*) as c FROM voters WHERE has_voted = 1").fetchone()["c"]

        return render_template("admin_results.html",
                               election=election,
                               results=results,
                               total_voters=total_voters,
                               total_voted=total_voted)
    finally:
        connection.close()


@app.route("/admin/voters")
@admin_required
def admin_voters():
    """View registered voters list."""
    connection = get_connection()
    try:
        voters = connection.execute(
            "SELECT id, voter_id, full_name, email, department, year_of_study, roll_number, is_verified, has_voted, registered_at FROM voters ORDER BY registered_at DESC"
        ).fetchall()
        return render_template("admin_voters.html", voters=voters)
    finally:
        connection.close()


@app.route("/admin/audit")
@admin_required
def admin_audit():
    """View audit log."""
    connection = get_connection()
    try:
        logs = connection.execute(
            "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 100"
        ).fetchall()
        return render_template("admin_audit.html", logs=logs)
    finally:
        connection.close()


# ─── API Routes for Live Results ──────────────────────────────

@app.route("/api/results/<int:election_id>")
def api_results(election_id):
    """API endpoint for live results data (used by admin dashboard charts)."""
    if "admin_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    connection = get_connection()
    try:
        positions = connection.execute(
            "SELECT * FROM positions WHERE election_id = ?", (election_id,)
        ).fetchall()

        data = {}
        for pos in positions:
            candidates = connection.execute(
                "SELECT * FROM candidates WHERE position_id = ?", (pos["id"],)
            ).fetchall()

            votes = connection.execute(
                "SELECT encrypted_vote FROM votes WHERE position_id = ?", (pos["id"],)
            ).fetchall()

            candidate_votes = {}
            for v in votes:
                try:
                    decrypted = decrypt_vote(v["encrypted_vote"])
                    cid = int(decrypted)
                    candidate_votes[cid] = candidate_votes.get(cid, 0) + 1
                except Exception:
                    pass

            data[pos["title"]] = {
                "candidates": [
                    {"name": c["name"], "votes": candidate_votes.get(c["id"], 0)}
                    for c in candidates
                ]
            }

        return jsonify(data)
    finally:
        connection.close()


# ─── Logout ───────────────────────────────────────────────────

@app.route("/logout")
def logout():
    """Clear session and logout."""
    user_type = session.get("user_type", "unknown")
    user_id = session.get("voter_id") or session.get("admin_id")
    log_audit("LOGOUT", user_type, user_id, "User logged out", request.remote_addr)
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("home"))


# ─── Error Handlers ───────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", error="Page not found", code=404), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("error.html", error="Internal server error", code=500), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
