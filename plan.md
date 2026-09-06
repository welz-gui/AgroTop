1. **Analyze the performance issue**: The codebase currently fetches the entire list of active animals using `db.get_all_animals(status="ativo")` and then loops over the result to extract IDs, creating a set: `ativos = {a["id"] for a in db.get_all_animals(status="ativo")}`. This returns a lot of unnecessary data when only IDs are needed.
2. **Establish a baseline**: Created `benchmark.py` and `test_perf.py`. The old approach took ~0.17s for 100 iterations, whereas simply fetching the IDs directly from the database using a new function took ~0.13s (a ~20% improvement).
3. **Implement optimized SQL query**: Created `get_all_animal_ids(status: str = "ativo") -> set[str]` in `repositories/animais.py` to directly fetch only the `id` column.
4. **Export new function in `database.py`**: Added `get_all_animal_ids` to the re-exports in `database.py`.
5. **Update callers**: Updated `app.py:1405`, `backend_api/main.py:393`, and relevant test files (`tests/test_backend_api.py`, `tests/test_integracao_estados_importacao.py`) to use `db.get_all_animal_ids(status="ativo")` instead of the less efficient set comprehension.
6. **Complete pre-commit steps to ensure proper testing, verification, review, and reflection are done.**
7. **Submit the PR**: Describe the optimization, the baseline, and the improvement.
