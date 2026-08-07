1.  **Analyze the Optimization Opportunity**:
    *   Currently, multiple views and calculations in `app.py` iterate over `animals` (or a subset of them) and call `db.get_total_cost(a["id"])` for each one.
    *   `db.get_total_cost` internally calls `_costs_by_animal()`, which performs a database query returning the total costs for *all* animals, and caches the result (using `streamlit.cache_data` via `_cache`).
    *   However, even with caching, calling `db.get_total_cost(a["id"])` in a Python loop incurs overhead for each animal. If there are hundreds or thousands of animals, the repeated function calls (and especially the `streamlit.cache_data` overhead on *every* call if it wraps `get_total_cost`, but here it wraps `_costs_by_animal`) can still be slow. Wait, `_costs_by_animal()` is cached. So `db.get_total_cost(animal_id)` just looks up in the dictionary. But if there are multiple loops, it's repeatedly looking up `_costs_by_animal()` for each animal, and if `_costs_by_animal()` is decorated with `@_cache` (which it is), the Streamlit cache check is triggered on *every iteration of the loop*. This is the N+1 problem: N cache hits for N loop iterations, which is surprisingly slow due to Streamlit's cache verification overhead.
    *   By fetching the entire costs dictionary *once* outside the loop using `costs = db._costs_by_animal()` and doing the dictionary lookup inside the loop (`costs.get(a["id"], 0.0)`), we avoid N cache checks and just do N simple Python dictionary lookups, which is vectorized/much faster.

2.  **Establish a Baseline**:
    *   Write a script that creates a mock database with e.g. 5,000 animals and some costs, and measures the time it takes to iterate over them and calculate costs.
    *   Compare the time taken by calling `get_total_cost(a_id)` in the loop versus doing `costs = _costs_by_animal()` once outside the loop and looking up in the loop.
    *   This script was already created and showed:
        *   Time to get costs for 1000 animals one by one: ~7.6 seconds (likely due to Streamlit caching overhead mocking, but it shows the Python side difference).
        *   Time to get costs for 1000 animals with pre-fetch: ~0.0068 seconds.

3.  **Implement**:
    *   In `app.py`, search for all occurrences of loops iterating over animals where `db.get_total_cost` is called.
    *   Replace `db.get_total_cost(a["id"])` inside the loops with:
        *   `costs = db._costs_by_animal()` outside the loop.
        *   `tc = costs.get(a["id"], 0.0)` inside the loop.
    *   Specifically, update the following occurrences:
        *   `_fin_venda(animals)` line ~1549 (Wait, this might not be in a loop. I will check).
        *   `page_financeiro()` line ~2132 (loop for `rows_f`)
        *   `page_financeiro()` line ~2314 (loop for `sim_rows`)
        *   `page_financeiro()` line ~2371 (loop for `be_rows`)
        *   `_custo_medio_arroba()` line ~2616 (loop for `custo += ...`)
        *   `page_relatorios()` line ~2899 (loop for `rows_fin`)
    *   Let's check `_fin_venda` and other places.

4.  **Verify**:
    *   Run test suite.
    *   Run linting/formatting.
    *   Measure the impact again.

5.  **Submit**:
    *   Create PR with the speedup details.
