# ✂️ Sistema de Agendamento - Danilo Barbearia

## 📋 Resumo das Correções Implementadas

✅ **Visual Modernizado** - CSS completamente reformulado com paleta mais elegante
✅ **Configuração Local** - Arquivo `.env` criado para rodar sem depender do Railway
✅ **Script de Banco** - SQL pronto para criar todas as tabelas necessárias
✅ **Documentação Completa** - Guia passo a passo de configuração

---

## 🚀 Configuração Rápida

### 1. Configure o Banco de Dados

Abra o **MySQL Workbench** e execute o arquivo `setup_database.sql`:

```sql
-- O script criará automaticamente:
-- ✓ Banco de dados: barbearia_db
-- ✓ Tabelas: agendamentos e admins
-- ✓ Administrador padrão para login
```

### 2. Configure o Arquivo .env

O arquivo `.env` já foi criado. Edite apenas a senha do MySQL:

```env
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=SUA_SENHA_AQUI  ← ALTERE AQUI
DB_NAME=barbearia_db
DB_PORT=3306

SECRET_KEY=dev-secret-key-change-in-production
FLASK_DEBUG=true
PORT=8080
```

### 3. Execute o Sistema

```bash
# Ative o ambiente virtual
.venv\Scripts\activate

# Instale as dependências (se necessário)
pip install -r requirements.txt

# Rode o sistema
python app.py
```

Acesse: **http://localhost:8080**

---

## 🔐 Credenciais de Acesso Admin

Após executar o script SQL, use:

- **Usuário:** `adm`
- **Senha:** `123`
- **Telefone:** `(99) 99999-9999`

⚠️ **IMPORTANTE**: No primeiro login, você será solicitado a atualizar seus dados!

---

## 🔧 Solução de Problemas

### Problema: Login não funciona

**Causa comum:** Formato do telefone incorreto no banco de dados.

**Solução:** Execute no Workbench:

```sql
-- Verificar formato atual
SELECT id, username, phone FROM admins;

-- Se o telefone não estiver como +5599999999999, corrija:
UPDATE admins SET phone = '+5599999999999' WHERE username = 'adm';
```

### Problema: Erro de conexão com banco

- ✓ Verifique se o MySQL está rodando
- ✓ Confirme a senha no arquivo `.env`
- ✓ Teste a conexão no Workbench primeiro

### Problema: Sistema não abre no navegador

- ✓ Verifique se a porta 8080 não está em uso
- ✓ Tente mudar a porta no `.env`
- ✓ Confirme que não há erros no terminal

---

## 🎨 Melhorias Visuais Implementadas

### O que mudou no CSS:

- **Paleta modernizada:** Tons mais elegantes (#0a0e14, #e8b968)
- **Background gradiente:** Efeitos radiais para profundidade visual
- **Botões redesenhados:** Efeitos hover com elevação suave
- **Cards melhorados:** Borda superior colorida ao hover
- **Hero section:** Título com gradiente e melhor hierarquia
- **Header aprimorado:** Blur effect e contraste melhorados

---

## 📁 Estrutura do Projeto

```
DaniloBarbearia/
├── app.py                    # Aplicação Flask principal
├── conexao.py                # Configuração do banco
├── .env                      # Configurações locais (CRIADO)
├── .env.example              # Exemplo de configuração
├── setup_database.sql        # Script SQL (CRIADO)
├── requirements.txt          # Dependências
├── static/
│   ├── styles/style.css      # CSS modernizado (ATUALIZADO)
│   ├── js/main.js
│   └── images/               # SVGs dos serviços
└── templates/                # Templates HTML
    ├── index.html
    ├── admin_login.html
    ├── admin_agendas.html
    └── ...
```

---

## 💡 Próximos Passos Recomendados

1. ✅ **Configure o banco** - Execute o `setup_database.sql`
2. ✅ **Ajuste o .env** - Coloque sua senha do MySQL
3. ✅ **Rode o sistema** - `python app.py`
4. ✅ **Teste o login** - Use as credenciais padrão
5. 🔄 **Altere a senha** - No primeiro acesso
6. 🎨 **Personalize** - Ajuste preços e informações de contato

---

## 📝 Notas Importantes

### Sobre o Login do Administrador

O sistema valida três informações:
1. **Usuário** (username)
2. **Senha** (password)
3. **Telefone** (phone)

O telefone é normalizado automaticamente para o formato `+55XXXXXXXXXXX`. Se o login falhar, verifique se o telefone no banco está neste formato.

### Primeiro Login

No primeiro acesso, o sistema detectará que é o primeiro login (`first_login = 0`) e pedirá para você:
- Atualizar seu nome
- Confirmar/atualizar telefone
- Definir nova senha

Após isso, o campo `first_login` será marcado como `1` e você terá acesso normal ao painel administrativo.

### Funcionamento Local vs Railway

O sistema agora está configurado para rodar **localmente**. As variáveis de ambiente no `.env` apontam para `localhost`. Para voltar a usar o Railway, você precisaria:
- Alterar o `.env` para usar as credenciais do Railway
- Ou criar um `.env.production` separado

---

## 🛠️ Comandos Úteis

```bash
# Ativar ambiente virtual
.venv\Scripts\activate

# Verificar dependências instaladas
pip list

# Reinstalar todas as dependências
pip install -r requirements.txt --force-reinstall

# Rodar o sistema
python app.py

# Verificar versão do Python
python --version
```

---

## 📞 Checklist Final

Antes de considerar tudo funcionando, verifique:

- [ ] MySQL rodando localmente
- [ ] Banco `barbearia_db` criado
- [ ] Tabelas `admins` e `agendamentos` existem
- [ ] Arquivo `.env` com senha correta
- [ ] Sistema iniciou sem erros
- [ ] Página abre em `http://localhost:8080`
- [ ] Login admin funciona
- [ ] Visual está modernizado

---

**Desenvolvido com ❤️ por Claude**

*Última atualização: 2026-09-01*
