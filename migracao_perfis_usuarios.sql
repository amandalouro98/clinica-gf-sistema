-- ============================================================
-- 1) HIGIENE (seguro para todos)
-- ============================================================
UPDATE usuarios
SET perfil = lower(btrim(perfil))
WHERE perfil IS NOT NULL AND perfil <> lower(btrim(perfil));

UPDATE usuarios
SET perfil = 'recepcao'
WHERE perfil IS NULL OR btrim(perfil) = '';

-- Agendamento sem profissional preenchido quebrava o filtro da agenda
UPDATE agenda
SET profissional = 'Sem profissional'
WHERE profissional IS NULL OR btrim(profissional) = '';

-- ============================================================
-- 2) PERFIS
--    Casamento pelo SOBRENOME, para nao confundir as duas Gabrielas.
-- ============================================================

-- Gabriela Franco -> admin
UPDATE usuarios
SET perfil = 'admin'
WHERE lower(nome) LIKE '%franco%';

-- Gabriela Souza -> recepcao
UPDATE usuarios
SET perfil = 'recepcao'
WHERE lower(nome) LIKE '%souza%';

-- Marina -> recepcao
UPDATE usuarios
SET perfil = 'recepcao'
WHERE lower(nome) LIKE '%marina%';

-- Ju / Juliana -> profissional
UPDATE usuarios
SET perfil = 'profissional'
WHERE lower(nome) LIKE '%juliana%' OR lower(nome) LIKE 'ju %' OR lower(btrim(nome)) = 'ju';

-- ============================================================
-- 3) CONFERENCIA
-- ============================================================
SELECT id, nome, email, perfil, ativo FROM usuarios ORDER BY perfil, nome;
