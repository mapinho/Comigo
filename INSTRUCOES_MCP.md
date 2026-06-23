# Manual de Utilização: MCP Server (Comigo Logística)

Este servidor Model Context Protocol (MCP) foi desenvolvido para expor as lógicas, tabelas e relatórios do Dashboard do sistema de transbordo **Comigo** diretamente para assistentes de inteligência artificial baseados em LLMs (como Claude, Gemini, etc.).

---

## 🚀 Requisitos Prévios
Antes de começar, certifique-se de que o ambiente virtual do projeto está ativo e as dependências (especialmente o `fastmcp`) estão instaladas.

1.  Ative o ambiente virtual:
    *   **Windows:** `.venv\Scripts\activate`
    *   **Linux/macOS:** `source .venv/bin/activate`
2.  Instale o `fastmcp` (se ainda não o fez):
    ```bash
    pip install fastmcp
    ```

---

## 🛠️ 1. Como Usar no Claude Desktop

O Claude Desktop suporta nativamente servidores MCP que rodam sob o protocolo STDIO (entrada/saída padrão).

### Passo 1: Localizar o Arquivo de Configuração
Abra o arquivo de configuração do Claude Desktop (`claude_desktop_config.json`) em seu sistema:
*   **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
*   **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

### Passo 2: Adicionar o MCP Server
Insira a configuração do servidor apontando para o seu interpretador Python no ambiente virtual e o arquivo `mcp_server.py`. Substitua os caminhos absolutos conforme o seu diretório:

```json
{
  "mcpServers": {
    "comigo-logistica": {
      "command": "C:\\Users\\mario\\OneDrive\\Documents\\Projects\\Comigo\\.venv\\Scripts\\python.exe",
      "args": [
        "C:\\Users\\mario\\OneDrive\\Documents\\Projects\\Comigo\\mcp_server.py"
      ]
    }
  }
}
```

*Nota: Em sistemas Linux/macOS, use caminhos no formato UNIX (ex: `/home/user/Comigo/.venv/bin/python` e `/home/user/Comigo/mcp_server.py`).*

### Passo 3: Reiniciar o Claude Desktop
Feche totalmente e reabra o Claude Desktop. Um ícone de **"martelo/ferramenta"** aparecerá na caixa de chat, indicando que as seguintes ferramentas estão conectadas e prontas para uso:
*   `list_scenarios`
*   `get_daily_movements`
*   `get_monthly_summary`
*   `get_factories_summary`
*   `get_warehouses_summary`
*   `compare_factories`
*   `compare_warehouses`
*   `get_stock_excesses_report`

---

## 🧪 2. Como Usar com Modelos Gemini (Gemini Pro e Ambientes Corporativos/Dev)

Embora a interface pública e web de consumo comum (gemini.google.com) seja totalmente baseada na nuvem e, por motivos de segurança e isolamento, não consiga enxergar um processo rodando localmente na sua máquina corporativa por `stdio`, o **Gemini Pro** suporta o Model Context Protocol de forma robusta e oficial através de canais de desenvolvimento e infraestrutura corporativa.

Abaixo estão as três principais alternativas para plugar o Gemini Pro neste MCP Server:

---

### Alternativa A: Gemini CLI (Ferramenta Oficial da Google)
A Google desenvolveu o **Gemini CLI**, um cliente MCP oficial de linha de comando que consome diretamente os modelos do Gemini Pro / Flash e se comunica localmente por `stdio` com o nosso servidor.

1.  **Instale o Gemini CLI** globalmente via npm:
    ```bash
    npm install -g @google/gemini-cli
    ```
2.  **Adicione este servidor MCP** local às configurações do Gemini CLI:
    ```bash
    gemini mcp add comigo-logistica -- C:\Users\mario\OneDrive\Documents\Projects\Comigo\.venv\Scripts\python.exe C:\Users\mario\OneDrive\Documents\Projects\Comigo\mcp_server.py
    ```
3.  **Inicie o chat** interativo com o Gemini Pro consumindo as ferramentas diretamente do terminal:
    ```bash
    gemini chat --model gemini-2.5-pro
    ```
    *Agora você pode perguntar diretamente no terminal: "O modelo otimizou as rotas para o cenário oficial?" e o Gemini Pro chamará as ferramentas do `mcp_server.py`.*

---

### Alternativa B: Vertex AI Agent Builder & Gemini Enterprise (Solução de Produção / Nuvem)
Para implantar e disponibilizar a solução para clientes e outros consultores em escala de produção corporativa, o servidor foi arquitetado para rodar sob **Docker Compose** e roteado pelo **Apache com SSL**:

1.  **Arquitetura Docker Compose (`docker-compose.yml`):**
    O serviço `mcp` roda em paralelo com o Streamlit em um contêiner Python 3.11 isolado na porta interna `8000`:
    ```yaml
    mcp:
      image: python:3.11-slim
      container_name: comigo_mcp
      restart: unless-stopped
      ports:
        - "8000:8000"
      command: mcp run mcp_server.py --transport sse --host 0.0.0.0 --port 8000
    ```
2.  **Roteamento e SSL no Apache (`comigo-le-ssl.conf`):**
    O Apache está configurado para atuar como proxy reverso seguro. Todas as requisições destinadas ao caminho `/mcp/` são encaminhadas internamente para o contêiner do MCP na porta `8000`, protegendo a transmissão com criptografia HTTPS TLS:
    ```apache
    ProxyPass /mcp/ http://127.0.0.1:8000/
    ProxyPassReverse /mcp/ http://127.0.0.1:8000/
    ```
3.  **Endpoint Público do MCP:**
    O endereço público do servidor MCP para integração externa será:
    ```text
    https://comigo.vectorconsulting.com.br/mcp/sse
    ```
4.  **Registro no Vertex AI / Gemini Enterprise:**
    No painel do Google Cloud Platform (Vertex AI Agent Builder), crie um novo agente ou extensão do tipo **MCP** e aponte o endpoint para a URL pública segura acima. O Gemini Pro no ambiente corporativo se comunicará nativamente e em tempo real com os dados de transbordo de soja da Comigo.

---

### Alternativa C: Extensões de Desenvolvedor (Cursor / Cline com Gemini Pro API Key)
Se você ou a equipe de desenvolvimento da sua empresa utilizam editores de código modernos com chaves de API empresariais do Google AI Studio (Gemini Pro), você pode integrar o servidor local instantaneamente:

1.  **No Cline (extensão do VS Code):**
    *   Vá em **Configurações > MCP Servers** e crie uma nova entrada:
        *   **Name:** `comigo-logistica`
        *   **Type:** `stdio`
        *   **Command:** `C:\Users\mario\OneDrive\Documents\Projects\Comigo\.venv\Scripts\python.exe`
        *   **Args:** `C:\Users\mario\OneDrive\Documents\Projects\Comigo\mcp_server.py`
2.  **No Cursor Editor:**
    *   Acesse **Settings > Features > MCP**.
    *   Adicione um novo MCP Server com tipo `stdio`, apontando o comando para o executável Python do seu `.venv` e o argumento para `mcp_server.py`.
3.  Defina o modelo de chat principal do editor para **Gemini Pro / Flash** e comece a analisar o código e os dados de transbordo cooperativamente.

---

## 📊 3. Exemplos de Perguntas para Fazer ao Assistente (LLM)

Uma vez que o MCP Server esteja ativo, você pode fazer perguntas analíticas de alto nível. O LLM escolherá de forma inteligente as ferramentas adequadas, lerá os dados em JSON, fará os cálculos e gerará respostas ricas.

*   *"Quais cenários de transbordo temos cadastrados no sistema atualmente? Qual deles é o oficial?"*
*   *"No cenário oficial, houve algum estouro de capacidade estática (estoque excedente) nos armazéns ou fábricas ao longo dos meses? Liste para mim."*
*   *"Faça uma comparação completa de desempenho e eficiência entre todas as fábricas do cenário oficial. Qual delas teve o maior volume esmagado acumulado?"*
*   *"Analise as movimentações diárias do mês de Março de 2026 para o cenário oficial e me diga se há alguma rota que concentra mais de 50% dos custos totais de frete."*
