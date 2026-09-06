import sqlite3
import time

def setup_db():
    con = sqlite3.connect(":memory:")
    con.execute("""
        CREATE TABLE animals (
            id TEXT PRIMARY KEY,
            current_weight REAL,
            entry_weight REAL,
            status TEXT
        )
    """)
    animals = [(f"A{i}", 300.0 + (i%50), 200.0, "ativo" if i % 2 == 0 else "inativo") for i in range(10000)]
    con.executemany("INSERT INTO animals (id, current_weight, entry_weight, status) VALUES (?, ?, ?, ?)", animals)
    return con

con = setup_db()

def test_python_sum():
    start = time.time()
    for _ in range(100):
        rows = con.execute("SELECT current_weight, entry_weight FROM animals WHERE status='ativo'").fetchall()
        val = sum(r[0] - r[1] for r in rows)
    print(f"Python sum: {time.time() - start:.4f}s. Val: {val}")

def test_sql_sum():
    start = time.time()
    for _ in range(100):
        val = con.execute("SELECT SUM(current_weight - entry_weight) FROM animals WHERE status='ativo'").fetchone()[0]
    print(f"SQL sum: {time.time() - start:.4f}s. Val: {val}")

test_python_sum()
test_sql_sum()
