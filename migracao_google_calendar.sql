-- Migração: integração com o Google Calendar
-- Adiciona a coluna do calendário do Google em profissionais e salas
-- e já vincula os calendários conhecidos da clínica.
-- Executar no servidor:
--   docker exec -i clinica-gf-db psql -U postgres -d clinica < migracao_google_calendar.sql

ALTER TABLE profissionais ADD COLUMN IF NOT EXISTS google_calendar_id VARCHAR;
ALTER TABLE salas ADD COLUMN IF NOT EXISTS google_calendar_id VARCHAR;

UPDATE profissionais
SET google_calendar_id = 'gabi.saudeintegrativa@gmail.com'
WHERE google_calendar_id IS NULL AND nome ILIKE 'gabi%';

UPDATE profissionais
SET google_calendar_id = 'Juliana_0e026846c4a899706dbdeabd973e4969f714394baf5b6a78873dec1777794e7f@group.calendar.google.com'
WHERE google_calendar_id IS NULL AND nome ILIKE 'juliana%';

UPDATE profissionais
SET google_calendar_id = 'Kawani_d59448d95d0fe1d949549a8d913bef8d73ec3f6e4155150c7c6584dc54ab314d@group.calendar.google.com'
WHERE google_calendar_id IS NULL AND (nome ILIKE 'kau%' OR nome ILIKE 'kawani%');

UPDATE salas
SET google_calendar_id = 'Sala 2_a8f26dd5e2ca582b7a08958e3f6a6d60efe5a509b8c6c2b7ed1db167c43abe34@group.calendar.google.com'
WHERE google_calendar_id IS NULL AND nome ILIKE 'sala 2%';

UPDATE salas
SET google_calendar_id = 'Sala 3_10b8e8a0a49526cbf69f59417a42e3df5136921a08368a37335e583770037cf7@group.calendar.google.com'
WHERE google_calendar_id IS NULL AND nome ILIKE 'sala 3%';

UPDATE salas
SET google_calendar_id = 'Sala 4_f46fab6fd1fb43e3dc9f14cc22e7508de754ba5777796999ba9f7a6ce0201547@group.calendar.google.com'
WHERE google_calendar_id IS NULL AND nome ILIKE 'sala 4%';
