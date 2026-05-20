# Sistema de Planejamento de Transbordo - Comigo

Este sistema otimiza a distribuição diária de soja entre armazéns e fábricas para minimizar o custo total de frete, respeitando limites de estoque e esmagamento.

## Tecnologias Utilizadas
- **Python 3.10+**
- **Streamlit** (Interface do Usuário)
- **Google OR-Tools** (Motor de Otimização)
- **SQLAlchemy** (ORM)
- **PostgreSQL** (Banco de Dados)
- **Pandas/Plotly** (Processamento e Visualização)

## Como Rodar

1.  **Configurar o Banco de Dados:**
    Crie um arquivo `.env` na raiz do projeto com as seguintes variáveis:
    ```env
    DB_USER=seu_usuario
    DB_PASSWORD=sua_senha
    DB_HOST=localhost
    DB_PORT=5432
    DB_NAME=comigo
    ```

2.  **Instalar Dependências:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Gerar Templates (Opcional):**
    ```bash
    python generate_templates.py
    ```

4.  **Executar o Sistema:**
    ```bash
    streamlit run app.py
    ```

## Estrutura de Arquivos
- `app.py`: Interface Streamlit.
- `models.py`: Definições das tabelas em português (SQLAlchemy).
- `calculations.py`: Lógica de otimização com OR-Tools.
- `data_loader.py`: Carregamento de dados XLSX para o Postgres.
- `templates/`: Modelos de arquivos Excel para carga de dados.
