# Robô de Conversão de Prospectos - Versão Limpa

Automatiza a conversão de prospectos em clientes no sistema Hubsoft com integração direta ao PostgreSQL.

## 🚀 Funcionalidades

- ✅ Login automático no Hubsoft
- ✅ Localização e conversão de prospectos
- ✅ Registro de status no banco PostgreSQL
- ✅ Screenshots apenas para erros
- ✅ Logs simplificados no terminal
- ✅ Limpeza automática de arquivos temporários

## 📋 Requisitos

- Python 3.8+
- Google Chrome
- Acesso ao banco PostgreSQL

## 🔧 Instalação

1. **Instalar dependências:**
```bash
pip install -r requirements.txt
```

2. **Configurar credenciais no `.env`:**
```bash
USUARIO=seu_email@exemplo.com
SENHA=sua_senha
HEADLESS=false
```

## 🎯 Uso

### Execução normal:
```bash
python3 main_refatorado.py
```

### Execução em modo headless:
```bash
python3 main_refatorado.py --headless
```

### Se houver erro de Chrome em uso:
```bash
python3 kill_chrome.py
python3 main_refatorado.py
```

## 🏗️ Estrutura do Banco

A tabela `prospectos` registra:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | SERIAL | ID único |
| `nome_prospecto` | VARCHAR(255) | Nome do prospecto |
| `id_prospecto_hubsoft` | VARCHAR(100) | ID no Hubsoft |
| `status` | VARCHAR(20) | `aguardando`, `processando`, `finalizado`, `erro` |
| `data_criacao` | TIMESTAMP | Data de criação |
| `data_atualizacao` | TIMESTAMP | Última atualização |
| `data_processamento` | TIMESTAMP | Último processamento |
| `tentativas_processamento` | INTEGER | Número de tentativas |
| `erro_processamento` | TEXT | Detalhes do erro |
| `tempo_processamento` | INTEGER | Tempo em segundos |
| `resultado_processamento` | TEXT | `sucesso` ou `falha` |

## 📊 Monitoramento

```sql
-- Ver status atual
SELECT status, COUNT(*) FROM prospectos GROUP BY status;

-- Ver erros recentes
SELECT * FROM prospectos WHERE status = 'erro' 
ORDER BY data_processamento DESC LIMIT 10;

-- Ver sucessos de hoje
SELECT * FROM prospectos 
WHERE status = 'finalizado' 
AND data_processamento >= CURRENT_DATE;
```

## 🔄 Processamento

O robô executa as seguintes etapas:

1. **🔐 Login** - Acesso ao sistema
2. **🧭 Navegação** - Acesso à seção de prospectos  
3. **🔍 Localização** - Busca do prospecto específico
4. **⚙️ Ações** - Abertura do menu de ações
5. **🔄 Conversão** - Início do wizard de conversão
6. **📋 Wizard (1/4)** - Primeira tela do wizard
7. **📝 Wizard (2/4)** - Preenchimento de seleções
8. **📋 Wizard (3/4)** - Segunda tela do wizard
9. **💾 Finalização** - Salvamento do cliente

## ⚠️ Tratamento de Erros

- Screenshots automáticos apenas em caso de erro
- Logs detalhados no banco de dados
- Limpeza automática de arquivos temporários
- Contagem de tentativas de processamento

## 🛠️ Configuração dos Prospectos

Para alterar o prospecto processado, edite a última linha do `main_refatorado.py`:

```python
if __name__ == "__main__":
    main("NOME_DO_PROSPECTO", "ID_DO_PROSPECTO")
```

## 🐛 Resolução de Problemas

### Erro "user data directory already in use"
```bash
python3 kill_chrome.py
```

### Chrome não fecha corretamente
O script limpa automaticamente os diretórios temporários

### Erro de conexão com banco
Verifique se as credenciais estão corretas no código 