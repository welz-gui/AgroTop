"""Isolamento da suíte de testes: nunca tocar o banco de PRODUÇÃO.

O `unittest discover` importa este pacote antes de qualquer módulo de teste, então
é aqui que a variável de ambiente precisa ser definida — `database.py` resolve
`DATABASE_URL` no momento do import, e depois é tarde.

Por que isso existe: com `.streamlit/secrets.toml` presente na máquina do
desenvolvedor, `_database_url()` cai no `st.secrets` e o backend passa a ser o
Postgres de produção. Um teste que chamasse `init_db()` gravaria lá — foi o que
aconteceu por acidente durante o desenvolvimento (nada foi perdido porque os
`_seed_*` têm guard, mas foi sorte, não projeto).

Confiar em cada teste lembrar de setar `db.USE_PG = False` é frágil: basta um
esquecimento. Aqui a proteção é do pacote inteiro e vale para subprocessos, que
herdam o ambiente.

O teste `tests/test_isolamento.py` verifica que este arquivo continua fazendo efeito.
"""

import os

os.environ["AGROTOP_FORCE_SQLITE"] = "1"
