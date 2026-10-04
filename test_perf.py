import time
import app
import database as db
import os
import sqlite3
import uuid
import datetime
import random

if os.path.exists('agrotop.db'):
    os.remove('agrotop.db')

db.init_db(forcar=True)

con = sqlite3.connect('agrotop.db')
cur = con.cursor()

for i in range(20):
    db.add_lote(db.LoteData(
        lote_id=f"TEST{i}",
        name=f"Test Lote {i}",
        area_ha=10.0,
        capacity_ua=500.0,
        notes=""
    ))
    for j in range(200):
        aid_uuid = str(uuid.uuid4())
        cur.execute(
            """INSERT INTO animals (id, uuid, breed, sex, current_weight, status, lote_id, property_id, entry_date, entry_weight)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (f"TEST_A{i}_{j}", aid_uuid, "Nelore", "M", 200.0, "ativo", f"TEST{i}", "1", "2024-01-01", 100.0)
        )

        # add 2 weighings
        for k in range(2):
            w_date = (datetime.date.today() - datetime.timedelta(days=30 * (2-k))).isoformat()
            cur.execute(
                """INSERT INTO weighings (animal_uuid, weight, weigh_date)
                   VALUES (?, ?, ?)""",
                (aid_uuid, 200.0 + k * 10.0 + random.random() * 5.0, w_date)
            )
        con.commit()

lotes = db.get_all_lotes()

start = time.time()
db.clear_cache()

# Simulate the old N+1 query logic
for l in lotes:
    anilist=db.get_all_animals(lote_id=l["id"])
    if anilist:
        a_ids = [a["id"] for a in anilist]
        gmd_batch = db.calculate_gmd_bulk(a_ids)

end = time.time()
print(f"Time taken baseline N+1: {end - start:.4f} seconds")
