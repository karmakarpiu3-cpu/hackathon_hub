import sqlite3

conn = sqlite3.connect('hackathon.db')
conn.row_factory = sqlite3.Row

print("\n=== USERS ===")
users = conn.execute("SELECT * FROM users").fetchall()
for u in users:
    print(dict(u))

print("\n=== SUBMISSIONS ===")
subs = conn.execute("SELECT * FROM submissions").fetchall()
for s in subs:
    print(dict(s))

conn.close()