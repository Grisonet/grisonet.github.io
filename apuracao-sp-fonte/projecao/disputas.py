"""Disputas do 2º turno de 2026 acompanhadas pelo painel.

Candidato "a" = 1º colocado no 1º turno; "b" = 2º colocado. A base do 1º turno de cada
disputa sai de build_base.py (ver README). No ensaio, as eleições do 1º turno substituem
as do 2º (6257/6259) e o painel compara o 1º turno com ele mesmo.
"""
AZUL, VERMELHO = "#0B57D0", "#C5221F"
GOV_A, GOV_B = "#0F766E", "#7C3AED"      # governadores: par neutro, sem conotação partidária


def _c(nome, completo, numero, cor):
    return {"nome": nome, "completo": completo, "numero": numero, "cor": cor}


DISPUTAS = [
    {"id": "presidente", "titulo": "Presidente", "abrangencia": "Brasil", "eleicao": 6258, "eleicao_1t": 6257,
     "cargo": 1, "ufs": None, "base": "2026_t1.json", "saida": "",
     "candidatos": {"a": _c("Flávio", "Flávio Bolsonaro (PL)", 22, AZUL), "b": _c("Lula", "Lula (PT)", 13, VERMELHO)}},
    {"id": "gov-ac", "titulo": "Governador", "abrangencia": "Acre", "eleicao": 6260, "eleicao_1t": 6259,
     "cargo": 3, "ufs": ["AC"], "base": "gov_ac_2026_t1.json", "saida": "governador/ac/",
     "candidatos": {"a": _c("Mailza", "Mailza Assis (PP)", 11, GOV_A), "b": _c("Alan Rick", "Alan Rick (Republicanos)", 10, GOV_B)}},
    {"id": "gov-am", "titulo": "Governador", "abrangencia": "Amazonas", "eleicao": 6260, "eleicao_1t": 6259,
     "cargo": 3, "ufs": ["AM"], "base": "gov_am_2026_t1.json", "saida": "governador/am/",
     "candidatos": {"a": _c("Omar Aziz", "Omar Aziz (PSD)", 55, GOV_A), "b": _c("Maria do Carmo", "Professora Maria do Carmo (PL)", 22, GOV_B)}},
    {"id": "gov-df", "titulo": "Governador", "abrangencia": "Distrito Federal", "eleicao": 6260, "eleicao_1t": 6259,
     "cargo": 3, "ufs": ["DF"], "base": "gov_df_2026_t1.json", "saida": "governador/df/",
     "candidatos": {"a": _c("Celina Leão", "Celina Leão (PP)", 11, GOV_A), "b": _c("Leandro Grass", "Leandro Grass (PT)", 13, GOV_B)}},
    {"id": "gov-es", "titulo": "Governador", "abrangencia": "Espírito Santo", "eleicao": 6260, "eleicao_1t": 6259,
     "cargo": 3, "ufs": ["ES"], "base": "gov_es_2026_t1.json", "saida": "governador/es/",
     "candidatos": {"a": _c("Pazolini", "Lorenzo Pazolini (Republicanos)", 10, GOV_A), "b": _c("Ferraço", "Ricardo Ferraço (MDB)", 15, GOV_B)}},
    {"id": "gov-rn", "titulo": "Governador", "abrangencia": "Rio Grande do Norte", "eleicao": 6260, "eleicao_1t": 6259,
     "cargo": 3, "ufs": ["RN"], "base": "gov_rn_2026_t1.json", "saida": "governador/rn/",
     "candidatos": {"a": _c("Allyson", "Allyson (União)", 44, GOV_A), "b": _c("Cadu de Lula", "Cadu de Lula (PT)", 13, GOV_B)}},
    {"id": "gov-to", "titulo": "Governador", "abrangencia": "Tocantins", "eleicao": 6260, "eleicao_1t": 6259,
     "cargo": 3, "ufs": ["TO"], "base": "gov_to_2026_t1.json", "saida": "governador/to/",
     "candidatos": {"a": _c("Dorinha", "Professora Dorinha (União)", 44, GOV_A), "b": _c("Vicentinho", "Vicentinho Júnior (PSDB)", 45, GOV_B)}},
]
