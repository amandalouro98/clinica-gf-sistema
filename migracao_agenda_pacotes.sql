-- Datas de início/término dos pacotes (venda_itens)
ALTER TABLE venda_itens ADD COLUMN IF NOT EXISTS data_inicio DATE;
ALTER TABLE venda_itens ADD COLUMN IF NOT EXISTS data_termino DATE;

UPDATE venda_itens
SET data_inicio = vendas.data_venda
FROM vendas
WHERE venda_itens.sale_id = vendas.id
  AND venda_itens.tipo = 'pacote'
  AND venda_itens.data_inicio IS NULL;

-- Liga o agendamento ao pacote e marca pré-agendamentos
ALTER TABLE agenda ADD COLUMN IF NOT EXISTS sale_item_id INTEGER;
ALTER TABLE agenda ADD COLUMN IF NOT EXISTS pre_agendamento BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS ix_agenda_sale_item_id ON agenda (sale_item_id);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'agenda_sale_item_id_fkey'
    ) THEN
        ALTER TABLE agenda
            ADD CONSTRAINT agenda_sale_item_id_fkey
            FOREIGN KEY (sale_item_id) REFERENCES venda_itens (id) ON DELETE SET NULL;
    END IF;
END $$;

-- CPF opcional (sincronização com o Forms)
ALTER TABLE clientes ALTER COLUMN cpf DROP NOT NULL;
