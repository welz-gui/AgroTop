import time
import os
import random
import uuid
from database import _conn

def setup_data():
    if os.path.exists('agrotop.db'):
        os.remove('agrotop.db')

    with _conn() as con:
        con.executescript("""
            CREATE TABLE animals (
                id TEXT PRIMARY KEY,
                uuid TEXT UNIQUE,
                entry_weight REAL,
                current_weight REAL
            );
            CREATE TABLE animal_costs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                animal_uuid TEXT,
                amount REAL
            );
        """)

        # Insert 1000 animals
        animals = []
        for i in range(1000):
            aid = f"A{i}"
            auuid = str(uuid.uuid4())
            animals.append((aid, auuid, 100, 200))
            con.execute("INSERT INTO animals (id, uuid, entry_weight, current_weight) VALUES (?, ?, ?, ?)", (aid, auuid, 100, 200))

            # Insert 5 costs per animal
            for _ in range(5):
                con.execute("INSERT INTO animal_costs (animal_uuid, amount) VALUES (?, ?)", (auuid, random.uniform(10, 50)))

def run_baseline():
    from repositories.financeiro import get_total_cost

    with _conn() as con:
        animals = con.execute("SELECT id FROM animals").fetchall()

    start_time = time.time()
    for a in animals:
        get_total_cost(a["id"])
    end_time = time.time()
    print(f"Time to get costs for {len(animals)} animals one by one: {end_time - start_time:.4f} seconds")

def run_optimized():
    from repositories.financeiro import _costs_by_animal

    with _conn() as con:
        animals = con.execute("SELECT id FROM animals").fetchall()

    start_time = time.time()
    costs = _costs_by_animal()
    for a in animals:
        _ = costs.get(a["id"], 0.0)
    end_time = time.time()
    print(f"Time to get costs for {len(animals)} animals with pre-fetch: {end_time - start_time:.4f} seconds")

if __name__ == '__main__':
    setup_data()
    run_baseline()
    run_optimized()
