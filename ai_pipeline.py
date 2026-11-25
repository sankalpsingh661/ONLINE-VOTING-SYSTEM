import csv
from pathlib import Path
from database import get_connection
from encryption import decrypt_vote


def load_data(filename):
    """Load data from a CSV file for analysis."""
    path = Path(filename)
    if not path.exists():
        print("Dataset not found.")
        return []
    with path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def export_results_csv(election_id, filename="election_results.csv"):
    """Export election results to CSV (anonymized - no voter info)."""
    connection = get_connection()
    try:
        results = connection.execute("""
            SELECT p.title as position, c.name as candidate, c.department,
                   COUNT(v.id) as vote_count
            FROM positions p
            JOIN candidates c ON c.position_id = p.id
            LEFT JOIN votes v ON v.position_id = p.id
            WHERE p.election_id = ?
            GROUP BY p.id, c.id
            ORDER BY p.id, vote_count DESC
        """, (election_id,)).fetchall()

        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Position", "Candidate", "Department", "Votes"])
            for row in results:
                writer.writerow([row["position"], row["candidate"], row["department"], row["vote_count"]])

        print(f"Results exported to {filename}")
        return True
    finally:
        connection.close()


def get_election_statistics(election_id):
    """Get overall election statistics."""
    connection = get_connection()
    try:
        total_voters = connection.execute("SELECT COUNT(*) as count FROM voters WHERE is_verified = 1").fetchone()["count"]
        voted_count = connection.execute("SELECT COUNT(*) as count FROM voters WHERE has_voted = 1").fetchone()["count"]

        stats = {
            "total_registered": total_voters,
            "total_voted": voted_count,
            "turnout_percentage": round((voted_count / total_voters * 100), 2) if total_voters > 0 else 0
        }
        return stats
    finally:
        connection.close()


if __name__ == "__main__":
    rows = load_data("sample_data.csv")
    print("Records loaded:", len(rows))
