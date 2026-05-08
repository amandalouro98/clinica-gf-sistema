#!/bin/bash

# Script de backup automático do sistema
# Adicionar ao crontab: 0 2 * * * /opt/clinica-gf/backup.sh

BACKUP_DIR="/opt/clinica-gf/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="clinica"
RETENTION_DAYS=7

# Criar diretório se não existir
mkdir -p "$BACKUP_DIR"

# Backup do banco de dados PostgreSQL
echo "[$DATE] Iniciando backup do banco de dados..."
docker-compose -f /opt/clinica-gf/docker-compose.yml exec -T db pg_dump -U postgres "$DB_NAME" > "$BACKUP_DIR/backup_$DATE.sql"

# Compactar backup
if [ -f "$BACKUP_DIR/backup_$DATE.sql" ]; then
    gzip "$BACKUP_DIR/backup_$DATE.sql"
    echo "[$DATE] Backup criado: backup_$DATE.sql.gz"
else
    echo "[$DATE] ERRO: Falha ao criar backup"
    exit 1
fi

# Remover backups antigos (mais de $RETENTION_DIAS dias)
find "$BACKUP_DIR" -name "backup_*.sql.gz" -type f -mtime +$RETENTION_DAYS -delete
echo "[$DATE] Backups antigos removidos (mais de $RETENTION_DIAS dias)"

# Listar backups atuais
echo "[$DATE] Backups disponíveis:"
ls -lh "$BACKUP_DIR"

echo "[$DATE] Backup concluído com sucesso!"
