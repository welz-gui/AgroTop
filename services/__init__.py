"""Camada de regra de negócio do AgroTop.

Contrato destes módulos (ROADMAP.md R8/R9):

- **sem SQL** — quem fala com o banco é `repositories/` (e, na transição, `database.py`);
- **sem Streamlit** — nada de `st.` nem import no topo do módulo;
- **regra de negócio existe aqui e em nenhum outro lugar.**

É o que permite que a mesma regra sirva ao web, à API, ao app mobile e a jobs
agendados sem ser reescrita — o erro que já produziu três cópias da
`simular_terminacao` no projeto.

Durante a Fase A2, `database.py` reexporta estes nomes para não quebrar os
chamadores existentes.
"""
