# =========================================
#  DEPLOY VPS - RESUMO RÁPIDO
# =========================================

## 1. CONTRATAR VPS
- Site: https://www.locaweb.com.br/vps/
- Plano: VPS 1 (R$ 29,90/mês)
- SO: Ubuntu 22.04 LTS
- Anote: IP, usuário root, senha

## 2. CONFIGURAR DNS
- Acesse onde comprou gabrifrancosaude.com.br
- Aponte @ e www para o IP do VPS
- Aguarde 15 min a 2h

## 3. ENVIAR ARQUIVOS AO VPS
Use PowerShell no seu computador:

```powershell
# Compactar pasta do sistema
Compress-Archive -Path "C:\Users\joaoz\Desktop\sistema GF\*" -DestinationPath "C:\Users\joaoz\Desktop\clinica-gf-vps.zip" -Force

# Enviar ao VPS (substitua IP_DO_VPS)
scp "C:\Users\joaoz\Desktop\clinica-gf-vps.zip" root@IP_DO_VPS:/opt/
```

## 4. CONFIGURAR VPS

Conecte via SSH:
```bash
ssh root@IP_DO_VPS
```

No VPS, execute:
```bash
# Extrair arquivos
cd /opt
unzip clinica-gf-vps.zip -d clinica-gf
cd clinica-gf

# Executar setup
chmod +x deploy/setup-vps.sh
./deploy/setup-vps.sh

# Configurar ambiente
cp .env.example .env
nano .env  # Edite as variáveis (senha do DB, etc)

# Iniciar sistema
docker-compose up -d
```

## 5. CONFIGURAR SSL (HTTPS)

```bash
cd /opt/clinica-gf
docker-compose run --rm certbot certonly \
  --webroot --webroot-path=/var/www/certbot \
  -d gabrifrancosaude.com.br \
  -d www.gabrifrancosaude.com.br \
  --agree-tos --email amandalouromo@gmail.com

docker-compose restart nginx
```

## 6. PRONTO!

Acesse: https://gabrifrancosaude.com.br

## COMANDOS ÚTEIS

Verificar status:
```bash
docker-compose ps
docker-compose logs -f
```

Reiniciar:
```bash
docker-compose restart
```

Backup manual:
```bash
./deploy/backup.sh
```

Atualizar após alterações:
```bash
docker-compose down
docker-compose up -d --build
```

## SUPORTE

- Locaweb: 4003-1000
- Documentação completa: deploy/GUIA-DEPLOY.md
