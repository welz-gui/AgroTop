"""Camada de acesso a dados do AgroTop.

Contrato (ROADMAP.md R1/R9):

- **aqui mora o SQL** — e só aqui;
- **sem regra de negócio** — cálculo e decisão ficam em `services/`;
- **sem Streamlit** no topo do módulo.

`conexao.py` é a base: escolha do backend, adaptação de dialeto SQLite↔Postgres,
`_conn()` (ponto único de acesso ao banco) e o cache.

Durante a Fase A2, `database.py` reexporta estes nomes para não quebrar os
chamadores existentes.
"""
