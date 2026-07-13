"""
Corrige duplicatas de produtos no banco:
- Renomeia produto antigo (com histórico) para o nome correto da planilha
- Migra lotes do produto novo (import) para o produto antigo
- Deleta o produto novo (duplicata sem histórico)

Uso:
  docker exec -e DATABASE_URL="postgresql://postgres:ClinicaGF2024%21@db:5432/clinica" \
    clinica-gf-app python corrigir_produtos.py
"""

import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:ClinicaGF2024!@db:5432/clinica"
)
engine = create_engine(DATABASE_URL)

# (id_antigo_manter, id_novo_deletar, nome_correto)
# id_antigo = produto original com histórico de atendimentos/movimentos
# id_novo   = produto criado pelo import (só tem lotes, sem histórico)
MERGE_E_RENOMEAR = [
    (51,  112, "atp 20mg"),
    (44,  114, "bcaa 30mg"),
    (57,  115, "cafeina 100mg"),
    (62,  118, "d-ribose 750mg"),
    (76,  119, "glicose + lidocaina"),
    (64,  120, "glicose"),
    (50,  123, "hmb 50mg"),
    (53,  124, "htp 10mg"),
    (56,  125, "l fenilalanina 50mg"),
    (75,  126, "l gluthation 1g"),
    (55,  127, "l theanina 50mg"),
    (45,  128, "l carnitina 600mg"),
    (52,  132, "pqq 5mg"),
    (61,  133, "silicio 20mg"),
    (83,  136, "vit c (ac ascorbico) 1G"),
    (47,  138, "acido alfa lipoico 300mg"),
    (100, 113, "azul de metileno 2ml"),
    (37,  108, "Seringa 5ml"),
    (19,  109, "Soro de 100ml"),
    (20,  110, "Soro de 250ml"),
    (21,  111, "Soro de 500ml"),
    (34,  107, "Nano XR"),
    (22,  104, "Creme de massagem REDUXCELL"),
    (8,   105, "Descarpak 7l"),
    (11,  106, "Gel condutor 1kg"),
    (87,  130, "pool capilar 130mg"),
    (60,  131, "pool de aminoacidos farmatec"),
]

# Produtos antigos sem par novo — apenas deletar (são duplicatas de produtos
# que já têm nome correto no banco)
# (id_deletar, id_manter_correto, descricao)
DELETAR_ANTIGOS = [
    (96,  40, "selenio 2ml        → já existe id 40 'selenio 80mcg'"),
    (92,  82, "sulfato de zinco 2 ml  → já existe id 82 'sulfato de zinco 20mg'"),
    (97,  82, "sulfato dezinco 2ml   → já existe id 82 'sulfato de zinco 20mg'"),
    (98,  88, "tirzepatida 2,5       → já existe id 88 'Tirzepatida 2,5mg'"),
    (63, 137, "vitamina c 50ml       → vai para id 137 'vitamina c'"),
    (95, 137, "vitamina c 5ml        → vai para id 137 'vitamina c'"),
]

# Produtos que ficam sem alteração (não estão na planilha — manter para análise)
MANTER_SEM_ALTERAR = [
    (80,  "5 - OH - TRIPTOFANO    — não está na planilha, manter"),
    (77,  "ADEK 2ml               — não está na planilha, manter"),
    (39,  "ácido fólico 10mg      — não está na planilha, manter"),
    (48,  "glutamina 2ml          — ambíguo (120mg ou 150mg?), manter"),
    (41,  "complexo B 2 ml        — ambíguo (B ou B sem b1?), manter"),
    (43,  "pool capilar farmatec 2ml — ambíguo, manter"),
    (46,  "picolinato de cromo 2ml — ambíguo (100 ou 200mcg?), manter"),
    (59,  "sulfato de magnesio 10ml — ambíguo (1G ou 500mg?), manter"),
    (94,  "sulfato de magnesio 5ml  — ambíguo (1G ou 500mg?), manter"),
]


def main():
    with engine.begin() as conn:
        print("=== MERGE E RENOMEAR ===")
        for old_id, new_id, nome_correto in MERGE_E_RENOMEAR:
            # 1. Migra lotes do novo para o antigo
            res = conn.execute(
                text("UPDATE estoque SET produto_id = :old WHERE produto_id = :new"),
                {"old": old_id, "new": new_id}
            )
            lotes_migrados = res.rowcount

            # 2. Migra movimentos do novo para o antigo (se houver)
            conn.execute(
                text("UPDATE movimentacoes_estoque SET produto_id = :old WHERE produto_id = :new"),
                {"old": old_id, "new": new_id}
            )

            # 3. Migra materiais de atendimento do novo para o antigo
            try:
                conn.execute(
                    text("UPDATE atendimento_materiais SET produto_id = :old WHERE produto_id = :new"),
                    {"old": old_id, "new": new_id}
                )
            except Exception:
                pass  # tabela pode ter nome diferente

            # 4. Renomeia o produto antigo
            conn.execute(
                text("UPDATE produtos SET nome = :nome WHERE id = :id"),
                {"nome": nome_correto, "id": old_id}
            )

            # 5. Deleta o produto novo (duplicata)
            try:
                conn.execute(
                    text("DELETE FROM produtos WHERE id = :id"),
                    {"id": new_id}
                )
                print(f"  [OK] id={old_id} renomeado para '{nome_correto}' | {lotes_migrados} lote(s) migrado(s) | id={new_id} deletado")
            except Exception as e:
                print(f"  [AVISO] id={new_id} não pôde ser deletado: {e}")

        print("\n=== DELETAR ANTIGOS (migrar para produto correto) ===")
        for del_id, keep_id, descricao in DELETAR_ANTIGOS:
            # Migra lotes e movimentos para o produto correto
            conn.execute(
                text("UPDATE estoque SET produto_id = :keep WHERE produto_id = :del"),
                {"keep": keep_id, "del": del_id}
            )
            conn.execute(
                text("UPDATE movimentacoes_estoque SET produto_id = :keep WHERE produto_id = :del"),
                {"keep": keep_id, "del": del_id}
            )
            try:
                conn.execute(
                    text("UPDATE atendimento_materiais SET produto_id = :keep WHERE produto_id = :del"),
                    {"keep": keep_id, "del": del_id}
                )
            except Exception:
                pass
            try:
                conn.execute(
                    text("DELETE FROM produtos WHERE id = :id"),
                    {"id": del_id}
                )
                print(f"  [OK] id={del_id} deletado — {descricao}")
            except Exception as e:
                print(f"  [AVISO] id={del_id} não pôde ser deletado: {e} | {descricao}")

    print("\n=== PRODUTOS MANTIDOS SEM ALTERAÇÃO (verificar manualmente) ===")
    for pid, desc in MANTER_SEM_ALTERAR:
        print(f"  [MANTER] id={pid} — {desc}")

    # Contagem final
    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM produtos")).scalar()
        print(f"\nTotal final de produtos no banco: {total}")


if __name__ == "__main__":
    main()
