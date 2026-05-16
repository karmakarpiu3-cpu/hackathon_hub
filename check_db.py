import sqlite3
import time
import os

def show_data():
    conn = sqlite3.connect('hackathon.db')
    conn.row_factory = sqlite3.Row

    print("\n" + "="*40)
    print(f"🕐 Last updated: {time.strftime('%H:%M:%S')}")
    
    print("\n=== USERS ===")
    users = conn.execute("SELECT * FROM users").fetchall()
    for u in users:
        print(dict(u))

    print("\n=== SUBMISSIONS ===")
    subs = conn.execute("SELECT * FROM submissions").fetchall()
    for s in subs:
        print(dict(s))

    conn.close()

# Har 5 second mein refresh
while True:
    os.system('cls' if os.name == 'nt' else 'clear')  # Screen clear
    show_data()
    print("\n⏳ Refreshing in 5 seconds... (Ctrl+C to stop)")
    time.sleep(5)