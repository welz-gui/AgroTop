"""Constantes de domínio do AgroTop.

Ficam na base da árvore de dependências: qualquer módulo pode importar daqui, e
este arquivo não importa nada do projeto.

⚠️ Alterar qualquer valor abaixo muda TODO o histórico já calculado (arrobas
produzidas, lotação, categorias). Ver ROADMAP.md seção 3 — "deve ser mantido".
"""

CARCASS_YIELD = 0.52    # rendimento de carcaça padrão (52 %)
KG_PER_ARROBA = 15.0    # kg por arroba
UA_WEIGHT     = 450.0   # kg por Unidade Animal padrão

AGE_BANDS = ["Até 12 meses", "13 a 24 meses", "25 a 36 meses", "+ de 36 meses"]
