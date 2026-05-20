# Especificação do Sistema de Planejamento de Transbordo de Soja

## 1. Visão Geral
O sistema tem como objetivo otimizar o planejamento logístico de movimentação (transbordo) de soja entre Armazéns (origens) e Fábricas de Esmagamento (destinos). A principal meta é garantir que as fábricas não fiquem sem matéria-prima para o esmagamento diário, respeitando capacidades logísticas, físicas e priorizando a liberação de espaço nos armazéns durante o período de safra, tudo isso com o menor custo de frete possível.

---

## 2. Entidades e Modelos de Dados (Data Architecture)

### 2.1. Fábrica (Destino)
*   **Nome:** Identificador textual da fábrica.
*   **Capacidade Estática (Ton):** Volume máximo que o silo da fábrica suporta armazenar.
*   **Capacidade de Esmagamento Diário (Ton):** Volume que a fábrica consome por dia.
*   **Capacidade de Recebimento Diário (Ton):** Volume máximo físico que a moega da fábrica consegue receber por dia (produtor + transbordo).
*   **Limite de Caminhões:** Quantidade máxima de veículos que o pátio consegue receber por dia.
*   **Carga Média por Caminhão (Ton):** Usado em conjunto com o limite de caminhões para gerar uma restrição de recebimento secundária.
*   **Estoque Inicial (Ton):** Estoque no dia zero da simulação.

### 2.2. Armazém (Origem)
*   **Nome:** Identificador textual do armazém.
*   **Capacidade Estática (Ton):** Volume máximo de armazenamento.
*   **Capacidade de Expedição Diária (Ton):** O máximo que o armazém consegue embarcar em caminhões por dia para transbordo.
*   **Estoque Inicial (Ton):** Estoque no dia zero da simulação.

### 2.3. Rota
*   **Armazém (Origem) e Fábrica (Destino).**
*   **Distância (km):** Distância da viagem.
*   **Custo de Frete (R$/Ton):** Valor pago para transportar 1 tonelada nesta rota. Usado como peso principal de minimização na função objetivo.

### 2.4. Previsão Mensal (Fábrica ou Armazém)
*   **Entidade:** Vínculo com a Fábrica ou Armazém.
*   **Mês de Referência:** Data normalizada sempre para o dia 1º de cada mês.
*   **Recebimento do Produtor (Ton/Mês):** Total esperado de entrega direta pelos agricultores na entidade ao longo do mês.
*   **Vendas (Ton/Mês):** Total de saídas não relacionadas a esmagamento ou transbordo (comercialização direta).
*   **É Safra (Booleano):** Flag (`1` ou `0`) indicando se aquele mês é considerado período de safra para aquela entidade.

### 2.5. Movimentação Diária (Resultado)
*   Tabela gerada automaticamente pelo Motor de Otimização.
*   **Data:** Dia específico da simulação.
*   **Origem:** Armazém que despachou.
*   **Destino:** Fábrica que recebeu.
*   **Quantidade (Ton) e (Sc):** Onde Sc (Sacas) = `Ton * 1000 / 60`.
*   **Custo Total (R$):** `Quantidade (Ton) * Custo Frete (R$/Ton)`.

### 2.6. Resumo Mensal Fábrica (Agregado)
*   **Mês:** Ano e mês (`AAAA-MM`).
*   **Fábrica:** Identificador do destino.
*   **Recebimento Produtor:** Total recebido de agricultores no mês.
*   **Recebimento Transbordo:** Total recebido dos armazéns no mês.
*   **Esmagado:** Total consumido/processado no mês.
*   **Saldo Estoque:** Posição do estoque no último dia computado do mês.
*   **Excedente:** Volume de estoque que ultrapassou a capacidade estática.

### 2.7. Resumo Mensal Armazém (Agregado)
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
1.  **Prioridade Máxima (Evitar parada de fábrica):** A variável $Slack_j$ tem um coeficiente altíssimo (ex: `1.000.000`). Isso obriga o modelo a priorizar a entrega para fábricas que não têm soja suficiente para rodar naquele dia, mesmo que o frete seja caro.
2.  **Incentivo de Safra:** Se o armazém $i$ estiver no mês de "Safra" (`eh_safra == 1`), o modelo concede um coeficiente positivo (ex: `+1000`). Isso incentiva esvaziar prioritariamente armazéns que estão na época de colheita.
3.  **Minimização de Custos:** O coeficiente do fluxo é subtraído pelo valor do Frete da rota ($-Custo Frete$).
*   *Função Final:* Maximizar a soma de `(+1000000 * Slack) + (+1000 se Safra * X) - (CustoFrete * X)` para todas as rotas.

---

## 5. Requisitos de UI / UX e Relatórios

### 5.1. Dashboard Interativo
*   O sistema deve processar o resultado gravado no banco de dados e exibir filtros de **Data de Início e Fim**.
*   **Visão Diária:** Tabela detalhada de movimentos por dia, contendo colunas: Data, Origem, Destino, Quantidade (Ton), Quantidade (Sc), Custo (R$).
*   **Visão Mensal (Agregada):** Dados sumarizados pelo mês `AAAA-MM`, exibindo os resultados aglutinados por Rota ou por Total da Companhia.
*   **Conversão Fundamental:** Sempre que exibir Toneladas, o sistema deve ter ou uma coluna correspondente, ou um indicador em **Sacas (Sc)**, usando o cálculo `Ton * 1000 / 60`.
*   **Indicadores Globais:** Exibição imediata de volume em Ton, volume em Sc e Valor Financeiro Total movimentado no período.
*   **Gráficos:** Volume por Destino, Custo por Origem.

### 5.2. Formatação Padrão Brasileiro
Onde houver relatórios na tela principal do dashboard e do visualizador:
*   **Números de Volume/Distância:** Separador de milhares com ponto (`.`) e sem casas decimais (Ex: `1.234.567`).
*   **Números Financeiros:** Separador de milhares com ponto (`.`) e decimais com vírgula (`,`) (Ex: `1.234.567,89`).

### 5.3. Exportação Nativa
*   **TODAS as exibições em tabela** (Seja no Dashboard diário, mensal ou na tela de visualizar o banco de dados) devem possuir um botão para **Exportação para XLSX**.
*   O XLSX deve expor os números reais brutos, sem formatação de texto (string), para viabilizar contas matemáticas nativas dentro do Excel pelos usuários finais.

### 5.4. Gestão do Banco de Dados
*   **Limpeza Automática no Upload:** A carga de dados via planilhas (Fábricas, Armazéns, Rotas, Previsões) deve excluir os dados velhos daquela entidade antes de carregar os novos, evitando acumulação artificial ao longo do tempo.
*   **Hard Reset (Botão do Pânico):** Deve existir um botão protegido para o Administrador "Limpar Banco de Dados". Ele deve executar scripts puros de `TRUNCATE TABLE ... RESTART IDENTITY CASCADE` para limpar todo o banco e resetar as PKs auto-incrementais, trazendo o banco de volta ao estado vazio original.
