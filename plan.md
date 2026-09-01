1.  **Analyze the Optimization Opportunity**
    - File: `repositories/movimentacoes.py` around line 237.
    - Issue: Currently, `faltantes` uses a `for` loop executing an `UPDATE` command for each animal in the `faltantes` list separately.
      ```python
      faltantes = [u for u in uuids if recebidos is not None and u not in recebidos]
      for u in faltantes:
          con.execute(
              "UPDATE movimentacao_animais SET divergencia='nao_recebido' "
              "WHERE movimentacao_id=? AND animal_uuid=?", (movimentacao_id, u))
      ```
    - Since we have an N+1 issue, we can optimize this loop using `con.executemany` over a list of parameters, which is a bulk operation and much faster in SQLite.

2.  **Make the Code Changes**
    - Replace the `for` loop with:
      ```python
      if faltantes:
          params = [(movimentacao_id, u) for u in faltantes]
          con.executemany(
              "UPDATE movimentacao_animais SET divergencia='nao_recebido' "
              "WHERE movimentacao_id=? AND animal_uuid=?", params)
      ```
    - Wait, let's also check if there are other N+1 queries. Look slightly below:
      ```python
        destino = mov["propriedade_destino_id"]
        chegaram = [u for u in uuids if u not in faltantes]
        for u in chegaram:
            if destino:
                con.execute("UPDATE animals SET property_id=? WHERE uuid=?",
                            (destino, u))
            eventos.registrar_em(
                con, u, "chegada_confirmada", ocorrido_em=data,
                usuario_registro=usuario, propriedade_id=destino,
                observacoes=f"movimentação {movimentacao_id[:8]}")
        for u in faltantes:
            eventos.registrar_em(
                con, u, "recusa_recepcao", ocorrido_em=data,
                usuario_registro=usuario,
                observacoes="declarado na movimentação e não recebido")
      ```
    - The instructions explicitly mention `N+1 Query in receber_movimentacao` and `"UPDATE movimentacao_animais SET divergencia='nao_recebido' WHERE movimentacao_id=? AND animal_uuid=?"`. So I'll definitely optimize that. I should also check if `eventos.registrar_em` does DB calls. The problem explicitly pointed to this part:
      ```python
        faltantes = [u for u in uuids if recebidos is not None and u not in recebidos]
        for u in faltantes:
            con.execute(
                "UPDATE movimentacao_animais SET divergencia='nao_recebido' "
                "WHERE movimentacao_id=? AND animal_uuid=?", (movimentacao_id, u))
      ```
    - Wait, the `UPDATE animals` is also an N+1 query. We could optimize it with `executemany` too. Let's do that for the `UPDATE animals` as well!
      ```python
      if destino and chegaram:
          con.executemany("UPDATE animals SET property_id=? WHERE uuid=?", [(destino, u) for u in chegaram])
      ```
      The `eventos.registrar_em` might be harder to batch because it might contain complex logic, but I will check it.

3.  **Run tests and verify**
    - The test `python3 -m unittest test_perf.py` measures performance before optimization (currently 1.5s for 10,000 animals).
    - After the change, it should be faster.
    - Run the entire test suite `python3 -m unittest discover tests/` to ensure everything works correctly.

4.  **Complete pre-commit steps**
    - Call `pre_commit_instructions` and follow its instructions to "Complete pre commit steps to make sure proper testing, verifications, reviews and reflections are done."

5.  **Submit**
    - Branch: `perf/optimize-confirmacao-chegada`
    - Commit message: "perf: optimize confirmacao_chegada with executemany"
