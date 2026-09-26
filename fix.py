import json

with open("database.py", "r") as f:
    code = f.read()

# We need to change the implementation to use a subquery or join to fetch the active plans IDs natively in SQL to avoid limits.
# The original get_feeding_plans gets active plans this way:
# SELECT p.*, l.name as lote_name, i.name as insumo_name FROM feeding_plans p LEFT JOIN lotes l ON l.id=p.lote_id LEFT JOIN insumos i ON i.id=p.insumo_id WHERE 1=1 AND p.active=1

# In get_pending_feedings, we already filter active plans.
# We can just JOIN feeding_plans in the checks query!

diff = """<<<<<<< SEARCH
    plan_ids = [str(p["id"]) for p in plans]
    last_checks = {}

    with _conn() as con:
        query = f\"\"\"
            SELECT plan_id, MAX(check_date) as check_date
            FROM feeding_checks
            WHERE plan_id IN ({','.join(plan_ids)})
            GROUP BY plan_id
        \"\"\"
        rows = con.execute(query).fetchall()
        for row in rows:
            last_checks[row["plan_id"]] = row["check_date"]

        result = []
=======
    last_checks = {}

    with _conn() as con:
        query = \"\"\"
            SELECT c.plan_id, MAX(c.check_date) as check_date
            FROM feeding_checks c
            JOIN feeding_plans p ON c.plan_id = p.id
            WHERE p.active = 1
            GROUP BY c.plan_id
        \"\"\"
        rows = con.execute(query).fetchall()
        for row in rows:
            last_checks[row["plan_id"]] = row["check_date"]

        result = []
>>>>>>> REPLACE"""

with open("diff.txt", "w") as f:
    f.write(diff)
