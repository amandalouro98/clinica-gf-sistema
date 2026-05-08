# =========================================
#  GUIA COMPLETO: GitHub + VPS
#  Passo a passo detalhado
# =========================================

## ETAPA 1: CRIAR CONTA NO GITHUB

### 1.1 Acesse
- Site: https://github.com/signup

### 1.2 Preencha cadastro
- Email: amandalouromo@gmail.com
- Senha: crie uma senha forte (anote!)
- Username: escolha um nome (ex: amandalouro)
- Verifique email

### 1.3 Criar repositório
1. Clique no botão verde "+" (topo direito)
2. "New repository"
3. Repository name: `clinica-gf-sistema`
4. Description: `Sistema de gestão da Clínica Gabriela Franco`
5. **IMPORTANTE:** Marque "Private" (privado)
6. NÃO marque "Add a README"
7. NÃO marque "Add .gitignore"
8. Clique "Create repository"

---

## ETAPA 2: PREPARAR ARQUIVOS LOCAIS

### 2.1 Verificar arquivos necessários
Na pasta `C:\Users\joaoz\Desktop\sistema GF\` deve ter:
- ✅ app.py
- ✅ Dockerfile
- ✅ docker-compose.yml
- ✅ nginx.conf
- ✅ requirements.txt
- ✅ Pasta models/
- ✅ Pasta utils/
- ✅ Pasta services/
- ✅ Pasta deploy/
- ✅ .gitignore (acabei de criar)
- ✅ env_example.txt

### 2.2 Arquivos que NÃO devem estar (já estão no .gitignore):
- ❌ .env (com senhas)
- ❌ database.db (banco local)
- ❌ service_account.json (credenciais)
- ❌ __pycache__/ (cache Python)
- ❌ .venv/ (ambiente virtual)

---

## ETAPA 3: INSTALAR GIT NO WINDOWS

### 3.1 Download
- https://git-scm.com/download/win
- Baixe e instale com opções padrão

### 3.2 Verificar instalação
Abra CMD e digite:
```cmd
git --version
```
Deve aparecer: `git version 2.x.x`

---

## ETAPA 4: CONFIGURAR GIT (PRIMEIRA VEZ)

No CMD:
```cmd
git config --global user.name "Seu Nome"
git config --global user.email "amandalouromo@gmail.com"
```

---

## ETAPA 5: ENVIAR CÓDIGO PARA GITHUB

### 5.1 Abrir CMD na pasta do sistema
```cmd
cd "C:\Users\joaoz\Desktop\sistema GF"
```

### 5.2 Inicializar repositório Git
```cmd
git init
```

### 5.3 Adicionar arquivos
```cmd
git add .
```

### 5.4 Criar primeiro commit
```cmd
git commit -m "Primeira versao do sistema - Clinica GF"
```

### 5.5 Conectar com GitHub
```cmd
git remote add origin https://github.com/SEU_USERNAME/clinica-gf-sistema.git
```

**Substitua SEU_USERNAME pelo seu nome de usuário do GitHub!**

### 5.6 Enviar para GitHub
```cmd
git push -u origin main
```

Digite seu usuário e senha do GitHub quando pedir.

---

## ETAPA 6: CONFIGURAR SECRETS NO GITHUB (SEGURANÇA)

### 6.1 Acessar Settings
1. No repositório GitHub, clique em "Settings" (aba superior)
2. No menu lateral esquerdo, clique em "Secrets and variables"
3. Clique em "Actions"
4. Clique "New repository secret"

### 6.2 Adicionar secrets um por um:

| Nome | Valor |
|------|-------|
| `VPS_HOST` | IP do VPS (ex: 177.100.200.50) |
| `VPS_USERNAME` | root |
| `VPS_PASSWORD` | Senha do root do VPS |
| `DB_PASSWORD` | Senha do banco de dados |
| `GOOGLE_FORM_LINK` | https://forms.gle/mBuxyP37Ysk5KtMHA |

**Para o service_account.json:**
- Abra o arquivo no Bloco de Notas
- Copie TODO o conteúdo
- Crie secret: `GOOGLE_CREDENTIALS`
- Cole o conteúdo completo

---

## ETAPA 7: CONTRATAR VPS LOCAWEB

### 7.1 Acesse
- https://www.locaweb.com.br/vps/

### 7.2 Escolha
- Plano: VPS 1 (R$ 29,90/mês)
- Sistema: Ubuntu 22.04 LTS

### 7.3 Anote
Você receberá por email:
- IP do servidor
- Usuário: root
- Senha

---

## ETAPA 8: CONFIGURAR DNS

### 8.1 Acesse onde comprou o domínio
- gabrifrancosaude.com.br

### 8.2 Crie registros DNS:

| Tipo | Nome | Valor |
|------|------|-------|
| A | @ | IP_DO_VPS |
| A | www | IP_DO_VPS |

---

## ETAPA 9: CONFIGURAR VPS

### 9.1 Conectar via SSH
Use PuTTY ou PowerShell:
```powershell
ssh root@IP_DO_VPS
```

### 9.2 Instalar dependências
```bash
apt update && apt upgrade -y
apt install -y git docker.io docker-compose
```

### 9.3 Clonar do GitHub
```bash
cd /opt
git clone https://github.com/SEU_USERNAME/clinica-gf-sistema.git clinica-gf
cd clinica-gf
```

### 9.4 Criar arquivo .env
```bash
cp env_example.txt .env
nano .env
```

Edite:
```
DB_URL=postgresql://postgres:SUA_SENHA@db:5432/clinica
POSTGRES_PASSWORD=SUA_SENHA
```

Salve: Ctrl+O, Enter, Ctrl+X

### 9.5 Enviar service_account.json
Do seu computador Windows:
```powershell
scp "C:\Users\joaoz\Desktop\sistema GF\service_account.json" root@IP_DO_VPS:/opt/clinica-gf/
```

### 9.6 Iniciar sistema
```bash
docker-compose up -d
```

---

## ETAPA 10: CONFIGURAR SSL (HTTPS)

```bash
cd /opt/clinica-gf
docker-compose run --rm certbot certonly --webroot --webroot-path=/var/www/certbot -d gabrifrancosaude.com.br -d www.gabrifrancosaude.com.br --agree-tos --email amandalouromo@gmail.com

docker-compose restart nginx
```

---

## ✅ PRONTO!

Acesse: https://gabrifrancosaude.com.br

---

## 🔄 COMO FAZER MODIFICAÇÕES FUTURAS

### Situação: Você quer alterar algo no código

### PASSO 1: Alterar no seu computador
1. Edite os arquivos em `C:\Users\joaoz\Desktop\sistema GF\`
2. Teste localmente: `streamlit run app.py`

### PASSO 2: Enviar para GitHub
```cmd
cd "C:\Users\joaoz\Desktop\sistema GF"
git add .
git commit -m "Descricao da alteracao"
git push
```

### PASSO 3: Atualizar VPS (AUTOMÁTICO!)
Se configurou o workflow do GitHub Actions, o deploy é automático!

Ou manualmente no VPS:
```bash
cd /opt/clinica-gf
git pull
docker-compose down
docker-compose up -d --build
```

---

## 📋 COMANDOS RÁPIDOS DE REFERÊNCIA

### No seu computador (Windows):
```cmd
# Ver status
git status

# Ver histórico
git log --oneline

# Desfazer alterações
git checkout -- nome-do-arquivo

# Voltar para versão anterior
git revert HASH_DO_COMMIT
```

### No VPS (Linux):
```bash
# Ver logs
docker-compose logs -f

# Ver status
docker-compose ps

# Reiniciar
docker-compose restart

# Backup manual
./deploy/backup.sh

# Atualizar do GitHub
git pull && docker-compose up -d --build
```

---

## 🆘 PROBLEMAS COMUNS

### "git push" pede senha toda vez
```cmd
git config --global credential.helper cache
```

### Esqueci de adicionar arquivo no .gitignore
```cmd
git rm --cached nome-do-arquivo
git commit -m "Remove arquivo sensivel"
git push
```

### Quero voltar para versão anterior
```cmd
git log --oneline  # Veja o hash
git revert HASH
```

---

## ✅ CHECKLIST FINAL

- [ ] Conta GitHub criada
- [ ] Repositório privado criado
- [ ] Git instalado no Windows
- [ ] Código enviado para GitHub
- [ ] Secrets configurados no GitHub
- [ ] VPS contratado na Locaweb
- [ ] DNS configurado
- [ ] Sistema rodando no VPS
- [ ] SSL/HTTPS funcionando
- [ ] Backup configurado

---

## 📞 SUPORTE

**GitHub:** https://support.github.com
**Locaweb:** 4003-1000
**Documentação:** https://docs.github.com/pt
