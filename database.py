import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voting.db")


def get_connection():
    """Get a database connection with Row factory for dict-like access."""
    connection = sqlite3.connect(DB_PATH, timeout=30.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def create_tables():
    """Create all database tables if they don't exist."""
    connection = get_connection()
    cursor = connection.cursor()

    # Voters table - unique identity for each voter
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS voters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            voter_id TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            date_of_birth TEXT NOT NULL,
            department TEXT NOT NULL,
            year_of_study INTEGER NOT NULL,
            roll_number TEXT UNIQUE NOT NULL,
            is_verified INTEGER DEFAULT 0,
            has_voted INTEGER DEFAULT 0,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Elections table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS elections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            start_date TIMESTAMP NOT NULL,
            end_date TIMESTAMP NOT NULL,
            is_active INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Positions table (e.g., President, Vice President, Secretary)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            election_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            max_votes INTEGER DEFAULT 1,
            FOREIGN KEY (election_id) REFERENCES elections(id)
        )
    """)

    # Candidates table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            position_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            department TEXT,
            manifesto TEXT,
            photo_url TEXT,
            FOREIGN KEY (position_id) REFERENCES positions(id)
        )
    """)

    # Votes table - encrypted votes with audit trail
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            voter_id INTEGER NOT NULL,
            position_id INTEGER NOT NULL,
            encrypted_vote BLOB NOT NULL,
            vote_hash TEXT NOT NULL,
            voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (voter_id) REFERENCES voters(id),
            FOREIGN KEY (position_id) REFERENCES positions(id),
            UNIQUE(voter_id, position_id)
        )
    """)

    # Admin table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Audit log table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            user_type TEXT NOT NULL,
            user_id INTEGER,
            details TEXT,
            ip_address TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.commit()
    connection.close()


def seed_data():
    """Seed initial data for demonstration."""
    connection = get_connection()
    cursor = connection.cursor()

    # Check if admin already exists
    admin = cursor.execute("SELECT id FROM admins WHERE username = 'admin'").fetchone()
    if not admin:
        from werkzeug.security import generate_password_hash
        cursor.execute(
            "INSERT INTO admins (username, password_hash, full_name) VALUES (?, ?, ?)",
            ("admin", generate_password_hash("admin123"), "System Administrator")
        )

    # Check if demo election exists
    election = cursor.execute("SELECT id FROM elections LIMIT 1").fetchone()
    if not election:
        cursor.execute("""
            INSERT INTO elections (title, description, start_date, end_date, is_active)
            VALUES (?, ?, datetime('now'), datetime('now', '+7 days'), 1)
        """, (
            "Student Council Election 2026",
            "Annual student council election for the academic year 2026-2027. Vote for your preferred candidates across all positions."
        ))
        election_id = cursor.lastrowid

        # Create positions
        positions = [
            ("President", "Head of the Student Council, responsible for overall leadership and representation."),
            ("Vice President", "Assists the President and leads specific initiatives."),
            ("General Secretary", "Manages council records, meetings, and communications."),
            ("Cultural Secretary", "Organizes cultural events, fests, and artistic activities."),
            ("Sports Secretary", "Oversees sports events, teams, and athletic programs.")
        ]
        for title, desc in positions:
            cursor.execute(
                "INSERT INTO positions (election_id, title, description) VALUES (?, ?, ?)",
                (election_id, title, desc)
            )

        # Create candidates for each position
        candidates_data = {
            "President": [
                ("Aarav Sharma", "Computer Science", "Committed to digital transformation of campus services, 24/7 library access, and transparent student governance."),
                ("Priya Patel", "Electronics", "Focused on improving lab facilities, industry partnerships, and creating a mentorship program."),
                ("Rahul Verma", "Mechanical", "Pledges to enhance placement support, establish startup incubation center, and improve hostel facilities.")
            ],
            "Vice President": [
                ("Sneha Gupta", "Information Technology", "Plans to introduce skill development workshops and improve campus Wi-Fi infrastructure."),
                ("Karan Singh", "Civil Engineering", "Aims to improve campus infrastructure, green spaces, and sustainable development practices."),
            ],
            "General Secretary": [
                ("Ananya Reddy", "Computer Science", "Will digitize all council processes and improve communication between students and administration."),
                ("Vikram Kumar", "Electrical", "Focused on creating an inclusive environment with regular town halls and feedback systems."),
            ],
            "Cultural Secretary": [
                ("Meera Joshi", "Arts & Humanities", "Plans to introduce monthly cultural festivals, art exhibitions, and inter-college competitions."),
                ("Arjun Nair", "Computer Science", "Will establish a college band, drama club, and organize national-level cultural fest."),
                ("Divya Menon", "Design", "Aims to create a creative hub, film club, and showcase diverse cultural traditions.")
            ],
            "Sports Secretary": [
                ("Rohit Desai", "Physical Education", "Plans to upgrade sports facilities, organize inter-department tournaments, and promote fitness culture."),
                ("Kavya Iyer", "Biotechnology", "Focused on women's sports development, yoga/meditation programs, and adventure sports club.")
            ]
        }

        positions_rows = cursor.execute(
            "SELECT id, title FROM positions WHERE election_id = ?", (election_id,)
        ).fetchall()

        for pos in positions_rows:
            if pos["title"] in candidates_data:
                for name, dept, manifesto in candidates_data[pos["title"]]:
                    cursor.execute(
                        "INSERT INTO candidates (position_id, name, department, manifesto) VALUES (?, ?, ?, ?)",
                        (pos["id"], name, dept, manifesto)
                    )

    connection.commit()
    connection.close()


if __name__ == "__main__":
    create_tables()
    seed_data()
    print("Database created and seeded successfully!")
