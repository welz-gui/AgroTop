"""Impede que a suíte atravesse a meia-noite no CI.

Os testes fixam "hoje" na coleta (`HOJE = date.today()`), enquanto o código lê a data na
hora em que roda. Se a execução cruzar 00:00, as duas datas divergem e dezenas de testes
falham sem motivo (CI de 08/11: começou às 23:58 UTC e deu 19 falhas). No CI, quem começa
perto da meia-noite espera ela passar. Fora do CI não espera (quem roda na máquina vê).
"""

import os
import time
from datetime import datetime, timedelta

# A suíte leva ~5 min no CI; a margem cobre uma rodada lenta.
MARGEM = timedelta(minutes=8)


def segundos_ate_passar_a_meia_noite(agora: datetime, margem: timedelta = MARGEM) -> float:
    """0 se a execução cabe antes da meia-noite; senão, quanto esperar para ela passar."""
    meia_noite = (agora + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    falta = meia_noite - agora
    return falta.total_seconds() + 5 if falta < margem else 0.0


def pytest_configure(config):
    if not os.environ.get("CI"):
        return
    espera = segundos_ate_passar_a_meia_noite(datetime.now())
    if espera:
        print(f"\n[conftest] perto da meia-noite: esperando {espera:.0f}s para a data não mudar no meio da suíte")
        time.sleep(espera)
