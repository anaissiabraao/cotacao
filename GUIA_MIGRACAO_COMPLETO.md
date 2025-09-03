# 🚀 Guia Completo: Migração PostgreSQL 17 → Neon → Render

## 📋 Resumo do Processo

1. **PostgreSQL 17 local** → **Neon PostgreSQL** → **Render**
2. Migrar todas as 10 tabelas existentes
3. Alimentar memórias de cálculo
4. Configurar Render para usar Neon

## 🔧 Pré-requisitos

### 1. Instalar dependências
```bash
pip install sqlalchemy pandas psycopg2-binary
```

### 2. Verificar conexões
- ✅ PostgreSQL 17 local rodando
- ✅ pgAdmin 4 conectado ao Neon
- ✅ String de conexão Neon válida

## 📊 Tabelas a Migrar

Baseado nas imagens do pgAdmin, você tem 10 tabelas:

1. `agentes`
2. `agentes_transportadora`
3. `base_unificada` ⭐ (principal)
4. `configuracoes_agente`
5. `formulas_calculo_frete`
6. `historico_calculos`
7. `logs_sistema`
8. `memorias_calculo_agent`
9. `tipos_calculo_frete`
10. `usuarios`

## 🚀 Executar Migração

### Opção 1: Script Interativo (Recomendado)
```bash
python migrar_interativo.py
```

**Vantagens:**
- ✅ Configuração segura da senha
- ✅ Confirmação antes de migrar
- ✅ Tratamento de erros
- ✅ Verificação automática

### Opção 2: Script Direto
```bash
python migrar_postgres_local_para_neon.py
```

**Observação:** Edite a linha 12 com sua senha do PostgreSQL local.

## 🔍 Verificar Migração

### 1. No pgAdmin Neon
- Conecte ao banco `neondb`
- Verifique as 10 tabelas migradas
- Confirme os dados em `base_unificada`

### 2. Via Script
```bash
python verificar_migracao.py
```

## ⚙️ Configurar Render

### 1. Variável de Ambiente
No painel do Render, adicione:

**Nome:** `DATABASE_URL`
**Valor:** `postgresql://neondb_owner:npg_P8uAds7tHvUF@ep-bold-poetry-adeue94a-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require`

### 2. Deploy
```bash
git add .
git commit -m "Migração para Neon PostgreSQL"
git push origin main
```

## 🧠 Memórias de Cálculo

O script automaticamente cria:

### PTX - Porto Express
- **Tipo:** Faixa de peso
- **Serviço:** Fracionado
- **Faixas:** 0-10kg, 10-20kg, 20-30kg, 30-50kg

### SOL - Soluções Logísticas
- **Tipo:** Valor por kg
- **Serviço:** Dedicado
- **Valor:** R$ 0,65/kg
- **GRIS:** 0,30%

## 🔧 Solução de Problemas

### Erro de Conexão Local
```
❌ Erro ao conectar aos bancos: connection refused
```
**Solução:**
1. Verificar se PostgreSQL está rodando
2. Confirmar porta 5432
3. Verificar senha do usuário postgres

### Erro de Conexão Neon
```
❌ Erro ao conectar aos bancos: SSL connection required
```
**Solução:**
1. Verificar string de conexão
2. Confirmar `sslmode=require`
3. Verificar credenciais Neon

### Tabela não encontrada
```
❌ Erro ao migrar tabela: relation "tabela" does not exist
```
**Solução:**
1. Verificar nome da tabela no pgAdmin
2. Confirmar schema 'public'
3. Verificar permissões do usuário

## 📞 Suporte

### Logs de Erro
Se houver problemas, verifique:
1. Logs do script de migração
2. Logs do PostgreSQL local
3. Logs do Neon (dashboard)

### Backup
Antes da migração, faça backup:
```bash
pg_dump -h localhost -U postgres -d base_unificada > backup_local.sql
```

## ✅ Checklist Final

- [ ] PostgreSQL 17 local rodando
- [ ] pgAdmin conectado ao Neon
- [ ] Script de migração executado
- [ ] 10 tabelas migradas com sucesso
- [ ] Dados em `base_unificada` verificados
- [ ] `DATABASE_URL` configurado no Render
- [ ] Deploy realizado
- [ ] Aplicação funcionando no Render

## 🎯 Próximos Passos

1. **Testar aplicação** no Render
2. **Verificar cálculos** de frete
3. **Configurar memórias** específicas
4. **Monitorar performance** do Neon

---

**💡 Dica:** Mantenha o PostgreSQL local como backup até confirmar que tudo está funcionando no Render.
