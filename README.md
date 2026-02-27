# Sistema de Gestão de Transbordo de Soja

Este sistema web foi desenvolvido utilizando Python e Streamlit para gerenciar a logística e estoques de fábricas de esmagamento de soja e armazéns.

## Funcionalidades
- Dashboard para acompanhamento de movimentação de cargas, previsões de estoque e caminhões em espera.
- Comparativo entre o previsto e realizado (estoques e caminhões).
- Carga de dados iniciais e atualizações de estoques reais via planilhas `.xlsx`.
- Algoritmo de simulação diária que calcula transferências dos armazéns para as fábricas otimizando pelo menor custo de frete.
- Utilização de banco de dados PostgreSQL.

## Configuração do Ambiente

1. Certifique-se de ter Docker, Docker Compose e Python 3.10+ instalados.
2. Inicie o banco de dados via Docker:
   ```bash
   docker-compose up -d
   ```
3. Crie e ative um ambiente virtual:
   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # Linux/Mac
   source .venv/bin/activate
   ```
4. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
5. Rode a aplicação Streamlit:
   ```bash
   streamlit run app.py
   ```

O sistema criará automaticamente as tabelas no banco de dados e os templates do Excel necessários na primeira execução.

## Estrutura do Projeto
- `app.py`: Interface do dashboard Streamlit.
- `models.py`: Modelos SQLAlchemy (Fábricas, Armazéns, Históricos e Rotas).
- `data_loader.py`: Lógica para ler e inserir dados das planilhas para o DB.
- `calculations.py`: Motor de simulação diária das restrições e transferências.
- `generate_templates.py`: Script gerador de modelos Excel.
- `docker-compose.yml`: Configuração do banco Postgres.
