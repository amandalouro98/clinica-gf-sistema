-- Gabi passa a ter o mesmo acesso do admin
UPDATE usuarios
SET perfil = 'admin'
WHERE lower(nome) LIKE '%gabi%'
   OR lower(coalesce(email, '')) LIKE '%gabi%';

-- Nenhum usuario pode ficar sem perfil (perfil vazio some com itens do menu)
UPDATE usuarios
SET perfil = 'recepcao'
WHERE perfil IS NULL OR btrim(perfil) = '';

-- Normaliza maiusculas/espacos para as comparacoes de perfil funcionarem
UPDATE usuarios
SET perfil = lower(btrim(perfil))
WHERE perfil <> lower(btrim(perfil));

-- Agendamento sem profissional preenchido quebrava o filtro da agenda
UPDATE agenda
SET profissional = 'Sem profissional'
WHERE profissional IS NULL OR btrim(profissional) = '';

-- Conferencia
SELECT id, nome, email, perfil, ativo FROM usuarios ORDER BY perfil, nome;
