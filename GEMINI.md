# GEMINI.md - Comigo (Transbordo de Soja)

## 1. Visão Geral do Projeto
O sistema **Comigo** é uma ferramenta de simulação e otimização logística para transbordo de soja. Ele permite planejar a movimentação de grãos entre Armazéns (origens) e Fábricas (destinos), visando minimizar custos de frete e garantir o suprimento contínuo das unidades de esmagamento.

## 2. Pilha Tecnológica
- **Linguagem:** Python 3.13+
- **Frontend:** Streamlit
- **Persistência:** SQLAlchemy (SQLite/PostgreSQL)
- **Processamento de Dados:** Pandas
- **Motor de Otimização:** Google OR-Tools (Programação Linear)

## 3. Convenções de Interface (UI/UX)

### 3.1. Formatação de Dados (Padrão Brasileiro)
Todas as exibições de tabelas devem utilizar a função `format_dataframe(df)` em `utils.py`, que garante:
- **Separador de Milhar:** Ponto (`.`)
- **Separador Decimal:** Vírgula (`,`)
- **Moeda:** Prefixo `R$` e 2 casas decimais.
- **Volume (Ton):** 1 casa decimal.
- **IDs:** Devem ser exibidos como **inteiros** (sem casas decimais).

### 3.2. Exibição de Tabelas
- Utilize `st.dataframe(format_dataframe(df), hide_index=True)` para visualização amigável.
- Para adicionar totais, use `append_totals_row(df)` antes da formatação.
- Colunas de ID devem ter a detecção automática habilitada em `utils.py` (via regex/substring 'id') para evitar formatação como float.

### 3.3. Edição de Dados (`st.data_editor`)
- Utilize `get_model_column_config(ModelClass)` para gerar automaticamente a configuração de colunas do Streamlit baseada nos metadados do SQLAlchemy (`info`).

## 4. Arquitetura de Dados

### 4.1. Modelos Principais
- `Cenario`: Agrupador de simulações. O ID `NULL` ou `is_oficial=True` representa o Plano Oficial.
- `Fabrica` / `Armazem`: Entidades logísticas.
- `Rota`: Conexão entre armazém e fábrica com custos de frete (Safra/Entressafra).
- `PrevisaoFabrica` / `PrevisaoArmazem`: Dados mensais de recebimento e vendas.
- `MovimentacaoDiaria`: Resultado da otimização.

### 4.2. Metadados do Modelo (`info`)
Os campos no `models.py` utilizam o parâmetro `info` para guiar a UI:
- `label`: Nome amigável da coluna.
- `type`: 'number', 'date', 'text'.
- `format`: '%d' para inteiros, 'localized' para padrão brasileiro.
- `hidden`: Se `True`, a coluna é omitida na UI.

## 5. Regras de Negócio Críticas
- **Deep Copy de Cenários:** Ao criar um novo cenário, todos os dados vinculados (fábricas, armazéns, rotas, previsões) devem ser duplicados.
- **Balanço de Massa:** `Estoque Final = Estoque Inicial + Entradas - Saídas`.
- **Prioridade de Otimização:** 1. Garantir esmagamento (evitar ruptura) > 2. Minimizar Custo de Frete > 3. Escoar Armazéns em Safra.

## 6. Fluxo de Trabalho (Workflows)
1. **Carga de Dados:** `data_loader.py` gerencia a conexão e clonagem.
2. **Cálculos:** `calculations.py` contém o motor de otimização diário.
3. **Exportação:** Todas as tabelas devem ter opção de exportação para Excel via `export_to_excel`.
