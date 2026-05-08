# =========================================
#  GUIA DE DEPLOY VPS - Gabriela Franco
# =========================================
# Servidor: VPS Locaweb (Ubuntu 22.04)
# Domínio: gabrifrancosaude.com.br
# Acesso: https://gabrifrancosaude.com.br

## ETAPA 1: CONTRATAR VPS LOCAWEB

1. Acesse: https://www.locaweb.com.br/vps/
2. Escolha o plano: **VPS 1** (R$ 29,90/mês) ou **VPS 2** (R$ 59,90/mês)
3. Sistema Operacional: **Ubuntu 22.04 LTS**
4. Complete o pagamento com cartão de crédito
5. Você receberá por e-mail:
   - IP do servidor (ex: 177.x.x.x)
   - Usuário: root
   - Senha inicial

## ETAPA 2: CONFIGURAR DNS (DOMÍNIO)

1. Acesse onde comprou o domínio (provavelmente Registro.br ou Locaweb)
2. Vá em gerenciamento de DNS
3. Crie ou edite os registros:

   Registro Tipo A:
   - Nome: @
   - Valor: IP_DO_VPS (ex: 177.x.x.x)
   - TTL: 3600

   Registro Tipo A (www):
   - Nome: www
   - Valor: IP_DO_VPS (ex: 177.x.x.x)
   - TTL: 3600

4. Aguarde propagação (15 minutos a 2 horas)

## ETAPA 3: ACESSAR VPS VIA SSH

No Windows, use PuTTY ou terminal PowerShell:

```bash
ssh root@IP_DO_VPS
```

Quando perguntar sobre fingerprint, digite: yes
Digite a senha fornecida por e-mail

## ETAPA 4: EXECUTAR SETUP AUTOMÁTICO

1. Envie os arquivos para o servidor:
```bash
# No seu computador Windows, abra PowerShell e execute:
scp -r C:\caminho\para\sistema-gf root@IP_DO_VPS:/opt/
```

2. No servidor VPS, execute:
```bash
cd /opt/sistema-gf/deploy
chmod +x setup-vps.sh
./setup-vps.sh
```

Aguarde a instalação (10-15 minutos)

## ETAPA 5: CONFIGURAR VARIÁVEIS DE AMBIENTE

1. Crie o arquivo .env:
```bash
cd /opt/sistema-gf
nano .env
```

2. Cole o conteúdo (substitua a senha):
```
DB_URL=postgresql://postgres:SUA_SENHA_SEGURA@db:5432/clinica
POSTGRES_PASSWORD=SUA_SENHA_SEGURA
GOOGLE_CREDENTIALS_PATH=/app/service_account.json
GOOGLE_FORM_LINK=https://forms.gle/mBuxyP37Ysk5KtMHA
```

3. Salve: Ctrl+O, Enter, Ctrl+X

## ETAPA 6: COPIAR CREDENCIAIS DO GOOGLE

1. Envie o arquivo service_account.json:
```bash
# No PowerShell do seu computador:
scp C:\Users\joaoz\Desktop\sistema GF\service_account.json root@IP_DO_VPS:/opt/sistema-gf/
```

## ETAPA 7: INICIAR SISTEMA

No VPS:
```bash
cd /opt/sistema-gf
docker-compose up -d
```

Aguarde 2-3 minutos para todos containers iniciarem

## ETAPA 8: CONFIGURAR SSL (HTTPS)

1. Obter certificado:
```bash
cd /opt/sistema-gf
docker-compose run --rm certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  -d gabrifrancosaude.com.br \
  -d www.gabrifrancosaude.com.br \
  --agree-tos \
  --email amandalouromo@gmail.com
```

2. Reiniciar nginx:
```bash
docker-compose restart nginx
```

## ETAPA 9: CONFIGURAR BACKUP AUTOMÁTICO

1. Configure o cron:
```bash
crontab -e
```

2. Adicione esta linha (backup diário às 2h da manhã):
```
0 2 * * * /opt/sistema-gf/deploy/backup.sh >> /var/log/backup-clinica.log 2>&1
```

3. Salve e saia

## ETAPA 10: MIGRAR DADOS (SE HOUVER)

Se quiser migrar dados do SQLite atual:

1. No seu computador, exporte os dados:
```bash
cd "C:\Users\joaoz\Desktop\sistema GF"
.venv\Scripts\activate
python migrate_to_postgres.py
# Quando pedir URL, use:
# postgresql://postgres:SUA_SENHA_SEGURA@IP_DO_VPS:5432/clinica
```

## COMANDOS ÚTEIS

Ver logs:
```bash
cd /opt/sistema-gf
docker-compose logs -f
```

Reiniciar sistema:
```bash
cd /opt/sistema-gf
docker-compose restart
```

Atualizar após mudanças no código:
```bash
cd /opt/sistema-gf
docker-compose down
docker-compose up -d --build
```

Verificar status:
```bash
docker-compose ps
```

## ACESSO AO SISTEMA

Após configurar tudo, acesse:
- **URL**: https://gabrifrancosaude.com.br
- **Login**: admin@clinica.com
- **Senha**: Admin@123 (altere no primeiro acesso)

## SUPORTE

Em caso de problemas:
1. Verifique logs: `docker-compose logs`
2. Verifique se containers estão rodando: `docker-compose ps`
3. Reinicie: `docker-compose restart`
4. Contate suporte Locaweb se VPS estiver inacessível
