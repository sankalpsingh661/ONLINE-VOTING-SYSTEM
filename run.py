"""
Convenient runner script for College Voting System.
Automatically checks dependencies, opens the web browser, and starts Flask.
"""

import os
import sys
import time
import webbrowser
import subprocess

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_DIR)

def main():
    print("=" * 55)
    print("         College Online Voting System Runner")
    print("=" * 55)
    print(f"Working directory: {PROJECT_DIR}")
    
    # 1. Install / verify dependencies
    print("\n[1/3] Checking dependencies...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--quiet"]
        )
        print("  ✓ Dependencies verified.")
    except Exception as e:
        print(f"  ! Warning: dependency check note: {e}")

    # 2. Check database
    print("\n[2/3] Checking database...")
    try:
        from database import create_tables, seed_data
        create_tables()
        seed_data()
        print("  ✓ Database initialized and ready.")
    except Exception as e:
        print(f"  ! Database initialization note: {e}")

    # 3. Open browser after slight delay
    def open_browser():
        time.sleep(1.5)
        print("\nOpening http://127.0.0.1:5000 in your web browser...")
        webbrowser.open("http://127.0.0.1:5000")

    import threading
    threading.Thread(target=open_browser, daemon=True).start()

    # 4. Start Flask server
    print("\n[3/3] Starting web server on http://127.0.0.1:5000 ...")
    print("Press CTRL+C in this terminal to stop the server.\n")
    from app import app
    app.run(host="127.0.0.1", port=5000, debug=True)

if __name__ == "__main__":
    main()
