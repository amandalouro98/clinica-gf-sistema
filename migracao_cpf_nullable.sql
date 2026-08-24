-- Migração: permite clientes sem CPF (sincronia com Google Forms)
ALTER TABLE clientes ALTER COLUMN cpf DROP NOT NULL;
