from typing import List, Dict, Any, Optional
from schemas.schemas import SimulacaoTerminacaoRequest, SimulacaoTerminacaoResponse, ResultadoCenario, TerminacaoCenario

CARCASS_YIELD = 0.54
KG_PER_ARROBA = 15.0

DEFAULT_CENARIOS = [
    {"nome": "Pasto Adubado", "gmd": 0.65, "custo_dia": 3.50, "rendimento": 0.52},
    {"nome": "Semiconfinamento (1% PV)", "gmd": 1.10, "custo_dia": 8.50, "rendimento": 0.54},
    {"nome": "Confinamento (Grão Inteiro)", "gmd": 1.45, "custo_dia": 14.00, "rendimento": 0.555},
]

def processar_simulacao_terminacao(req: SimulacaoTerminacaoRequest) -> SimulacaoTerminacaoResponse:
    peso_atual = req.peso_atual
    peso_meta = req.peso_meta
    preco_arroba = req.preco_arroba
    custo_boi_magro = req.custo_boi_magro
    
    cenarios_input = req.cenarios
    if not cenarios_input:
        cenarios_dict = DEFAULT_CENARIOS
    else:
        cenarios_dict = [c.model_dump() for c in cenarios_input]
        
    ganho_kg = round(peso_meta - peso_atual, 1)
    resultados = []
    
    for c in cenarios_dict:
        nome = c.get("nome", "Estratégia")
        gmd = float(c.get("gmd") or 0)
        cd = float(c.get("custo_dia") or 0)
        rend = float(c.get("rendimento") or CARCASS_YIELD)
        
        if ganho_kg <= 0 or gmd <= 0:
            dias = 0
            custo_alim = 0.0
            arrobas_prod = 0.0
            receita = 0.0
            lucro = 0.0
            lpd = 0.0
            cpa = 0.0
            margem = 0.0
            viavel = False
        else:
            dias = int(round(ganho_kg / gmd))
            custo_alim = round(dias * cd, 2)
            arrobas_prod = round(ganho_kg * rend / KG_PER_ARROBA, 2)
            receita = round(peso_meta * rend / KG_PER_ARROBA * preco_arroba, 2)
            lucro = round(receita - custo_alim - custo_boi_magro, 2)
            lpd = round(lucro / dias, 2) if dias > 0 else 0.0
            cpa = round(custo_alim / arrobas_prod, 2) if arrobas_prod > 0 else 0.0
            margem = round((lucro / receita) * 100, 1) if receita > 0 else 0.0
            viavel = lucro > 0
            
        resultados.append(ResultadoCenario(
            nome=nome,
            dias=dias,
            arrobas_produzidas=arrobas_prod,
            custo_alimentar=custo_alim,
            custo_por_arroba=cpa,
            receita=receita,
            lucro=lucro,
            lucro_por_dia=lpd,
            margem_pct=margem,
            viavel=viavel
        ))
        
    # Ordenar por maior lucro
    resultados.sort(key=lambda r: r.lucro, reverse=True)
    melhor_estratégia = resultados[0].nome if resultados and resultados[0].viavel else None
    
    return SimulacaoTerminacaoResponse(
        peso_atual=peso_atual,
        peso_meta=peso_meta,
        preco_arroba=preco_arroba,
        ganho_necessario_kg=ganho_kg,
        melhor_estratégia=melhor_estratégia,
        cenarios=resultados
    )
