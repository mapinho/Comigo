# Native AI Assistant in Comigo Streamlit

## Objective
Integrate a native AI Assistant directly into the Comigo Streamlit application to allow users to intuitively query scenarios, logistics data, and optimization metrics using natural language.

## Architecture & Tech Stack
- **AI SDK**: `google-genai` (Latest Official Google Gemini SDK).
- **Integration Strategy**: Function Calling natively via Python logic.
- **Design Pattern**: Native Shared Services. Data querying logic will be extracted to a shared service module (`logistics_services.py`) to be used by both `mcp_server.py` and the new Streamlit Chat Assistant, enforcing DRY (Don't Repeat Yourself) principles.
- **API Key Management**: The application will strictly rely on the `GEMINI_API_KEY` environment variable. 

## Implementation Steps

### 1. Dependency Update
- Add `google-genai` to `requirements.txt`.
- Install `google-genai` within the active python virtual environment (`.venv`).

### 2. Refactor Shared Services (`logistics_services.py`)
- Extract the core database query logic currently housed inside `mcp_server.py`.
- Create a new file `logistics_services.py` containing standard Python functions for:
  - `list_scenarios`
  - `get_daily_movements`
  - `get_monthly_summary`
  - `get_factories_summary`
  - `get_warehouses_summary`
  - `compare_factories`
  - `compare_warehouses`
  - `get_stock_excesses_report`
- These functions will utilize the existing `init_db()` and SQLAlchemy models, remaining completely agnostic to FastMCP or Streamlit.

### 3. Update MCP Server (`mcp_server.py`)
- Refactor `mcp_server.py` to import the functions from `logistics_services.py` and apply the `@mcp.tool()` decorators. 
- This ensures the MCP protocol behavior remains 100% untouched and functional while cleaning up the codebase.

### 4. Develop AI Assistant Logic (`ai_assistant.py`)
- Create `ai_assistant.py` to encapsulate the Google GenAI client initialization and session management.
- Define a system prompt instructing the model on its logistics analysis persona and strict reliance on the provided tools.
- Map the functions from `logistics_services.py` as `tools` for the Gemini model.
- Implement the conversation loop that manages the chat history, invokes tools via Function Calling, and yields the final response back to the Streamlit UI.

### 5. Streamlit UI Integration (`app.py`)
- Add a new "Assistente de IA" page to the Streamlit sidebar menu in `app.py`.
- Implement a modern chat interface utilizing Streamlit's `st.chat_message` and `st.chat_input`.
- Enforce an environment check for `GEMINI_API_KEY` before rendering the chat interface. If missing, a clear `st.warning` or `st.error` will be displayed to the user explaining that the environment variable is required.

### 6. Testing and Verification
- Run the Streamlit application and verify the Chat tab renders successfully.
- Test the integration by asking natural language questions about the logistics scenarios (e.g., "Quais os gargalos no cenário oficial?") to confirm Function Calling successfully triggers the database services and returns accurate insights.
