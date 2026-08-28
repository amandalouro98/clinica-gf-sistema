-- Adiciona colunas de data de início e término aos pacotes (venda_itens)
ALTER TABLE venda_itens ADD COLUMN IF NOT EXISTS data_inicio DATE;
ALTER TABLE venda_itens ADD COLUMN IF NOT EXISTS data_termino DATE;

-- Preenche data_inicio dos pacotes existentes com a data da venda
UPDATE venda_itens
SET data_inicio = vendas.data_venda
FROM vendas
WHERE venda_itens.sale_id = vendas.id
  AND venda_itens.tipo = 'pacote'
  AND venda_itens.data_inicio IS NULL;
