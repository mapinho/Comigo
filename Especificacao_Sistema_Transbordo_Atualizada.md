# Especificação do Sistema de Planejamento de Transbordo de Soja

## 1. Visão Geral
O sistema tem como objetivo otimizar o planejamento logístico de movimentação (transbordo) de soja entre Armazéns (origens) e Fábricas de Esmagamento (destinos). A principal meta é garantir que as fábricas não fiquem sem matéria-prima para o esmagamento diário, respeitando capacidades logísticas, físicas e priorizando a liberação de espaço nos armazéns durante o período de safra, tudo isso com o menor custo de frete possível. Adicionalmente, permite a criação de cenários de simulação para análise de impacto ("What-if").

---

## 2. Entidades e Modelos de Dados (Data Architecture)

### 2.1. Cenário
*   **Nome:** Identificador único do cenário.
*   **Data de Criação:** Registro temporal da instância.
*   *Nota:* O sistema utiliza um cenário mestre implícito chamado **Oficial (Planejado)**, identificado por `cenario_id = NULL`.

### 2.2. Fábrica (Destino)
*   **Cenário:** Vínculo com o cenário correspondente.
*   **Nome:** Identificador textual da fábrica.
*   **Capacidade Estática (Ton):** Volume máximo que o silo da fábrica suporta armazenar.
*   **Capacidade de Esmagamento Diário (Ton):** Volume que a fábrica consome por dia.
*   **Capacidade de Recebimento Diário (Ton):** Volume máximo físico que a moega da fábrica consegue receber por dia (produtor + transbordo).
*   **Limite de Caminhões:** Quantidade máxima de veículos que o pátio consegue receber por dia.
*   **Carga Média por Caminhão (Ton):** Usado em conjunto com o limite de caminhões para gerar uma restrição de recebimento secundária.
*   **Estoque Inicial (Ton):** Estoque no dia zero da simulação.

### 2.3. Armazém (Origem)
*   **Cenário:** Vínculo com o cenário correspondente.
*   **Nome:** Identificador textual do armazém.
*   **Capacidade Estática (Ton):** Volume máximo de armazenamento.
*   **Capacidade de Expedição Diária (Ton):** O máximo que o armazém consegue embarcar em caminhões por dia para transbordo.
*   **Estoque Inicial (Ton):** Estoque no dia zero da simulação.

### 2.4. Rota
*   **Cenário:** Vínculo com o cenário correspondente.
*   **Armazém (Origem) e Fábrica (Destino).**
*   **Distância (km):** Distância da viagem.
*   **Custo de Frete (R$/Ton):** Valor pago para transportar 1 tonelada nesta rota. Usado como peso principal de minimização na função objetivo.

### 2.5. Previsão Mensal (Fábrica ou Armazém)
*   **Entidade:** Vínculo com a Fábrica ou Armazém específica do cenário.
*   **Mês de Referência:** Data normalizada sempre para o dia 1º de cada mês.
*   **Recebimento do Produtor (Ton/Mês):** Total esperado de entrega direta pelos agricultores na entidade ao longo do mês.
*   **Vendas (Ton/Mês):** Total de saídas não relacionadas a esmagamento ou transbordo (comercialização direta).
*   **É Safra (Booleano):** Flag (`1` ou `0`) indicando se aquele mês é considerado período de safra para aquela entidade.

### 2.6. Movimentação Diária (Resultado)
*   Tabela gerada automaticamente pelo Motor de Otimização.
*   **Cenário:** Identificação de qual simulação este resultado pertence.
*   **Data:** Dia específico da simulação.
*   **Origem:** Armazém que despachou.
*   **Destino:** Fábrica que recebeu.
*   **Quantidade (Ton) e (Sc):** Onde Sc (Sacas) = `Ton * 1000 / 60`.
*   **Custo Total (R$):** `Quantidade (Ton) * Custo Frete (R$/Ton)`.

### 2.7. Resumo Mensal Fábrica (Agregado)
*   **Cenário:** Vínculo com o cenário correspondente.
*   **Mês:** Ano e mês (`AAAA-MM`).
*   **Fábrica:** Identificador do destino.
*   **Recebimento Produtor:** Total recebido de agricultores no mês.
*   **Recebimento Transbordo:** Total recebido dos armazéns no mês.
*   **Esmagado:** Total consumido/processado no mês.
*   **Saldo Estoque:** Posição do estoque no último dia computado do mês.
*   **Excedente:** Volume de estoque que ultrapassou a capacidade estática.

### 2.8. Resumo Mensal Armazém (Agregado)
*   **Cenário:** Vínculo com o cenário correspondente.
*   **Mês:** Ano e mês (`AAAA-MM`).
*   **Armazém:** Identificador da origem.
*   **Recebimento Produtor:** Total recebido de agricultores no mês.
*   **Envio Transbordo:** Total despachado para as fábricas no mês.
*   **Vendas:** Total vendido diretamente do armazém.
*   **Saldo Estoque:** Posição do estoque no último dia computado do mês.
*   **Excedente:** Volume de estoque que ultrapassou a capacidade estática.

---

## 3. Regras de Negócio e Cálculos Base

### 3.1. Tratamento de Tempo
*   Os dados de **Previsão Mensal** devem ser rateados igualmente para cada dia do mês. 
*   **Fórmula:** `Volume Diário = Volume Mensal / Dias do Mês` (ex: em Janeiro divide-se por 31, em Fevereiro normal por 28).

### 3.2. Balanço Diário de Massa (Estoque)
A cada iteração de um dia (D), o estoque de cada entidade no fim do dia é o saldo para o dia D+1:
*   **Armazém:** `Estoque Final = Estoque Inicial D + (Recebimento Produtor Diário) - (Vendas Diárias) - (Transbordo Expedido)`
*   **Fábrica:** `Estoque Final = Estoque Inicial D + (Recebimento Produtor Diário) - (Vendas Diárias) + (Transbordo Recebido) - (Esmagamento Diário)`
*   **Nota de Limite Físico:** Se as entregas diretas do produtor fizerem a Fábrica exceder a *Capacidade Estática*, a fábrica trava o recebimento de *Transbordo* até que o esmagamento abra novo espaço.

### 3.3. Gestão de Cenários (Clonagem)
*   A criação de um cenário executa uma **Cópia Profunda** (Deep Copy) dos dados do Baseline (NULL).
*   Todas as fábricas, armazéns, rotas e previsões são duplicadas e vinculadas ao novo `cenario_id`.
*   A alteração de parâmetros em um cenário (ex: custo de rota ou capacidade) é isolada e não afeta o Planejado oficial.

---

## 4. Motor de Otimização (Programação Linear)

A otimização roda num laço (`loop`) dia a dia para calcular os transbordos, tendo o estado inicial de D como input. 
Deve utilizar solvers de Programação Linear Mista/Inteira (ex: SCIP, GLOP).

### 4.1. Variáveis de Decisão
*   $X_{i,j}$ = Quantidade despachada do armazém $i$ para a fábrica $j$.
*   $Slack_{j}$ = Variável de folga para o atendimento do esmagamento da fábrica $j$. Varia de $0$ até a (Demanda de Esmagamento não coberta pelo estoque local).

### 4.2. Restrições do Sistema
1.  **Limite de Estoque Origem:** O somatório de saídas $X_{i,j}$ de um armazém não pode exceder o saldo de estoque físico disponível nele no início do dia.
2.  **Capacidade de Expedição:** O somatório de saídas $X_{i,j}$ de um armazém não pode exceder sua `Capacidade de Expedição Diária`.
3.  **Capacidade Diária de Recebimento:** O somatório de chegadas na fábrica $j$ não pode exceder a `Capacidade de Recebimento Diária` da moega.
4.  **Limite de Caminhões:** O somatório de chegadas na fábrica $j$ não pode exceder a `(Limite de Caminhões * Carga Média)`.
5.  **Capacidade Estática (Dinâmica):** O volume de transbordo recebido na fábrica $j$ não pode ultrapassar o espaço disponível no silo.
    *   *Espaço = Max(0, Capacidade Estática - Estoque Atual + Esmagamento Diário)*.
    *   Se o estoque atual estiver maior que a capacidade estática (devido ao recebimento forçado de produtores), o transbordo para esta fábrica será rigorosamente $0$.
6.  **Garantia de Esmagamento:** O volume transbordado para a fábrica $j$ precisa ser maior ou igual à variável de folga $Slack_j$.

### 4.3. Função Objetivo (Maximização)
A função objetivo pondera prioridades logísticas:
1.  **Prioridade Máxima (Evitar parada de fábrica):** A variável $Slack_j$ tem um coeficiente altíssimo (ex: `1.000.000`). Isso obriga o modelo a priorizar a entrega para fábricas que não têm soja suficiente para rodar naquele dia.
2.  **Incentivo de Transporte:** Cada tonelada transportada recebe uma recompensa base (ex: `10.000`). Isso garante que o sistema sempre tente realizar o transbordo para encher as fábricas e liberar armazéns, em vez de ficar inativo.
3.  **Incentivo de Safra:** Se o armazém $i$ estiver no mês de "Safra" (`eh_safra == 1`), o modelo concede um coeficiente positivo extra (ex: `+1.000`).
4.  **Minimização de Custos:** O coeficiente do fluxo é reduzido pelo valor do Frete da rota ($-Custo Frete$).
*   *Função Final:* Maximizar a soma de `(+1.000.000 * Slack) + (X * (10.000 + (1.000 se Safra) - CustoFrete))` para todas as rotas.

---

## 5. Requisitos de UI / UX e Relatórios

### 5.1. Dashboard de Comparação
*   **Seletor de Cenário:** Permite alternar entre o Planejado e qualquer Simulação criada.
*   **KPIs com Delta:** Ao visualizar uma Simulação, os cartões de indicadores (Custo Total e Volume Total) devem exibir a variação absoluta e percentual em relação ao Planejado Baseline.
*   **Visão Diária e Mensal:** Tabelas e gráficos detalhados por cenário.
*   **Formatação Padrão Brasileiro:** Milhares com ponto (`.`) e decimais com vírgula (`,`).

### 5.2. Editor de Cenário (Simulation Data Entry)
*   Interface em grade (planilha) para alteração de parâmetros.
*   Suporte para inserção de **Armazéns Fictícios** via adição de linhas dinâmicas.
*   Edição de Previsões Mensais (Recebimento/Vendas) por cenário.

### 5.3. Exportação Nativa
*   **TODAS as exibições em tabela** devem possuir um botão para **Exportação para XLSX**.
*   O XLSX deve expor os números reais brutos para permitir cálculos externos.

### 5.4. Gestão do Banco de Dados
*   **Cascade Delete:** A exclusão de um cenário deve remover automaticamente todas as fábricas, armazéns, rotas, previsões e resultados vinculados a ele.
*   **Hard Reset:** Função para limpar integralmente o banco de dados e reiniciar sequências de identidade.

---

## 6. Assistente de Dados via Model Context Protocol (MCP)
Para estender os recursos de análise de dados e permitir tomadas de decisão guiadas por inteligência artificial (LLMs), o sistema fornece um **MCP Server** baseado no framework `fastmcp`.

### 6.1. Ferramentas Disponibilizadas (MCP Tools)
O servidor MCP expõe as seguintes funções como ferramentas para consumo via LLM:
1.  `list_scenarios`: Lista todos os cenários, identificando o cenário oficial e simulações.
2.  `get_daily_movements`: Retorna transbordos diários detalhados com filtros de data e rota.
3.  `get_monthly_summary`: Agrupa volumes (Ton/Sc) e custos de frete consolidados por mês.
4.  `get_factories_summary`: Relatório mensal de recebimento, esmagamento, saldo e excedentes de silos das fábricas.
5.  `get_warehouses_summary`: Relatório mensal de expedição, vendas, saldo e excedentes dos armazéns.
6.  `compare_factories`: Agrega dados de capacidade e aponta picos e gargalos de esmagamento nas fábricas.
7.  `compare_warehouses`: Agrega dados de expedição e aponta picos de gargalo de escoamento nos armazéns.
8.  `get_stock_excesses_report`: Varre todas as unidades e meses disparando alertas quando há estouro de capacidade estática (`excedente > 0`).

### 6.2. Arquitetura de Comunicação
O servidor MCP se comunica utilizando o protocolo JSON-RPC sobre transporte STDIO (para integrações de desktop locais como Claude Desktop) ou transporte HTTP/SSE (para integrações remotas e extensões de editores de código). Os dados de retorno são sempre estruturados em JSON bruto para dar liberdade ao LLM cliente de tabular, processar ou analisar as informações.
