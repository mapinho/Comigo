# Plano de Implementação: MCP Server e Documentação

## 1. Objetivo
Criar um servidor Model Context Protocol (MCP) para expor as análises e lógicas do Dashboard do sistema Comigo aos LLMs (Gemini, Claude, etc.), permitindo interações ricas e complexas.

## 2. Arquitetura e Bibliotecas
- **Framework:** `fastmcp` (SDK oficial, limpo, baseado em decoradores e tipagem do Python).
- **Abordagem de Banco:** Reutilização do `init_db()` do `data_loader.py` para criar instâncias isoladas de `Session` por chamada, assegurando robustez no acesso aos dados do SQLAlchemy.
- **Formato de Resposta:** Dados brutos (`list[dict]`), facilmente serializáveis para JSON. Isso maximiza o poder de análise do LLM cliente.

## 3. Ferramentas Projetadas (MCP Tools)
O arquivo `mcp_server.py` registrará as seguintes ferramentas:
1. `list_scenarios()`: Retorna os cenários disponíveis (ID, nome e status oficial).
2. `get_daily_movements(scenario_id, start_date, end_date, ...)`: Busca movimentações diárias (filtra por origem/destino).
3. `get_monthly_summary(scenario_id, ...)`: Agrupa as movimentações por mês.
4. `get_factories_summary(scenario_id)`: Retorna recebimentos, esmagamento, capacidade, saldos e excedentes de fábricas mensais.
5. `get_warehouses_summary(scenario_id)`: Retorna saldos, expedições e capacidades de armazéns.
6. `compare_factories(scenario_id)`: Totaliza e calcula métricas de pico de estoque e gargalos de cada fábrica no cenário.
7. `compare_warehouses(scenario_id)`: Idem para armazéns.
8. `get_stock_excesses_report(scenario_id)`: Varre todas as entidades e meses alertando sobre qualquer `excedente > 0`.

## 4. Atualização de Especificações
- `requirements.txt`: Inclusão da dependência `fastmcp`.
- `Especificacao_Sistema_Transbordo_Atualizada.md`: Adição de uma seção dedicada descrevendo o "Assistente de Dados via MCP".
- `GEMINI.md`: Atualização sobre as capacidades do MCP.
- `INSTRUCOES_MCP.md`: Criação de um manual contendo as instruções para configurar e utilizar o servidor MCP no Claude Desktop e ecossistema Gemini.

## 5. Testes e Validação
- Compilação via `python -m py_compile mcp_server.py`.
- Instalação das dependências para validação de sintaxe do `fastmcp`.
- (Opcional) Executar servidor para teste de inicialização.