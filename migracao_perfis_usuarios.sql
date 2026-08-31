-- ============================================================
-- 1) CONFERENCIA: veja quem esta cadastrado e com qual perfil
-- ============================================================
SELECT id, nome, email, perfil, ativo FROM usuarios ORDER BY id;

-- ============================================================
-- 2) HIGIENE (seguro para todos): ninguem pode ficar sem perfil,
--    e o perfil precisa estar em minusculas sem espacos.
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
-- 3) PERFIS: rode DEPOIS de ver a lista do passo 1.
--    Troque os IDs pelos reais. Nao use nome, para nao confundir
--    as duas Gabis.
-- ============================================================
-- UPDATE usuarios SET perfil = 'admin'        WHERE id = 1;  -- Amanda
-- UPDATE usuarios SET perfil = 'admin'        WHERE id = 2;  -- Gabriela Franco
-- UPDATE usuarios SET perfil = 'profissional' WHERE id = 3;  -- Ju
-- UPDATE usuarios SET perfil = 'recepcao'     WHERE id = 4;  -- Gabi (recepcao)
-- UPDATE usuarios SET perfil = 'recepcao'     WHERE id = 5;  -- Marina

-- Conferencia final
SELECT id, nome, email, perfil, ativo FROM usuarios ORDER BY perfil, nome;
