import time
import os
import uuid
os.environ["AGROTOP_FORCE_SQLITE"] = "1"
import database as db

# Create some mock data
def setup():
    with db._conn() as con:
        con.execute("PRAGMA foreign_keys = OFF")
        con.execute("DELETE FROM weighings")
        con.execute("DELETE FROM animals")
        con.execute("DELETE FROM lotes")
        con.execute("DELETE FROM properties")
        con.execute("DELETE FROM users")
        con.execute("PRAGMA foreign_keys = ON")

        con.execute("INSERT INTO users (id, username, password_hash, name, role) VALUES (1, 'u1', 'hash', 'User 1', 'admin')")
        con.execute("INSERT INTO properties (id, produtor_id, nome) VALUES ('P1', 1, 'Prop 1')")
        con.execute("INSERT INTO lotes (id, property_id, name, status) VALUES ('Lote1', 'P1', 'Lote 1', 'ativo')")
        for i in range(500):
            u = str(uuid.uuid4())
            con.execute("INSERT INTO animals (id, uuid, lote_id, property_id, entry_date, breed, entry_weight, current_weight) VALUES (?, ?, 'Lote1', 'P1', '2023-01-01', 'Nelore', 100, 100)", (f"A{i}", u))
            for j in range(5):
                con.execute("INSERT INTO weighings (animal_uuid, weight, weigh_date, method) VALUES (?, ?, ?, 'pesado')", (u, 100 + j * 10, f"2023-01-0{j+1}"))
        con.commit()

setup()

def bench_n1():
    t0 = time.time()
    hist = {}
    for i in range(500):
        a_id = f"A{i}"
        hist[a_id] = [{"peso": w["weight"], "data": w["weigh_date"]}
                      for w in db.get_weighings(a_id)]
    t1 = time.time()
    return t1 - t0

def bench_batch():
    t0 = time.time()
    a_ids = {f"A{i}" for i in range(500)}

    all_weighings = db.get_weighings_batch(a_ids)
    hist = {}
    for a_id in a_ids:
        hist[a_id] = [{"peso": w["weight"], "data": w["weigh_date"]}
                      for w in all_weighings.get(a_id, [])]
    t1 = time.time()
    return t1 - t0

# warm up
bench_n1()
bench_batch()

t_n1 = bench_n1()
t_batch = bench_batch()

print(f"N+1 time: {t_n1:.4f}s")
print(f"Batch time: {t_batch:.4f}s")
print(f"Speedup: {t_n1 / t_batch:.2f}x")
