import os
import streamlit as st
from google import genai
from google.genai import types
import logistics_services

# System Prompt para guiar o comportamento do assistente logístico
SYSTEM_PROMPT = """Você é o Assistente de Inteligência Logística da COMIGO, especializado na otimização e simulação de transbordo de soja.
Sua missão é ajudar planejadores e analistas logísticos a compreenderem os dados do sistema, avaliar cenários de simulação, identificar gargalos e planejar movimentações para minimizar custos e evitar rupturas de estoque nas fábricas.

Diretrizes de Comportamento:
1. **Persona de Especialista**: Seu tom deve ser altamente profissional, preciso, consultivo e técnico. Você é um parceiro de planejamento estratégico.
2. **Uso de Ferramentas (Function Calling)**: Sempre utilize as ferramentas fornecidas para buscar as informações mais atualizadas do banco de dados de cenários e simulações. Nunca invente dados. Se não houver dados, informe educadamente que não há registros correspondentes para a consulta.
3. **Análise de Gargalos e Estoques**:
   - Destaque picos de estoque e volumes excedentes (alertas gerados por `get_stock_excesses_report` ou comparativos) como gargalos críticos de capacidade estática.
   - Explique o impacto de um estouro de capacidade (por exemplo, custos extras de armazenamento externo ou risco de armazenamento inadequado) e a importância de escoar o excedente.
4. **Análise de Custos**:
   - Sempre consulte as rotas e resumos de movimentações para avaliar o impacto financeiro.
   - Apresente custos formatados no padrão de moeda brasileiro: prefixo 'R$' com duas casas decimais e separadores de milhar (ex: R$ 1.250.300,50).
5. **Formatação e Legibilidade**:
   - Apresente dados tabulares usando tabelas Markdown claras e organizadas.
   - Use bullet points para conclusões e recomendações acionáveis.
   - Apresente volumes em Toneladas (Ton) com separador de milhar (ponto) e uma casa decimal, ou em Sacas (Sc).
6. **Gerenciamento de Cenários**:
   - Se o usuário não especificar qual cenário deseja analisar, use `list_scenarios` para identificar quais cenários existem, informe que está usando o cenário Oficial (is_oficial=True) por padrão e convide o usuário a escolher outro cenário se preferir.
   - Refira-se aos cenários pelo seu nome legível e forneça o ID quando útil para clareza técnica.
"""

# Wrappers de ferramentas com notificação Streamlit (st.toast) para excelente UX
def list_scenarios() -> list[dict]:
    """
    Lista todos os cenários de simulação cadastrados no sistema,
    indicando qual é o cenário oficial e o seu ID correspondente.
    """
    st.toast("📊 Consultando cenários de simulação no banco...", icon="🔍")
    return logistics_services.list_scenarios()

def get_daily_movements(
    scenario_id: int,
    start_date: str = None,
    end_date: str = None,
    origin_id: int = None,
    destination_id: int = None,
    limit: int = 150
) -> list[dict]:
    """
    Retorna a lista detalhada de movimentações diárias de soja para um cenário específico.
    Permite filtrar por intervalo de datas (AAAA-MM-DD), ID do armazém de origem (origin_id),
    ID da fábrica de destino (destination_id). Retorna o volume em Ton, Sc (sacas) e Custo Financeiro.
    """
    st.toast(f"🚚 Buscando movimentações diárias do cenário ID {scenario_id}...", icon="🔍")
    return logistics_services.get_daily_movements(
        scenario_id=scenario_id,
        start_date=start_date,
        end_date=end_date,
        origin_id=origin_id,
        destination_id=destination_id,
        limit=limit
    )

def get_monthly_summary(
    scenario_id: int,
    start_date: str = None,
    end_date: str = None
) -> dict:
    """
    Retorna o resumo consolidado por mês (e detalhamento por rota) das movimentações do cenário.
    Útil para análise mensal do volume movimentado em toneladas, sacas e o custo total de frete.
    Intervalos de data opcionais no formato AAAA-MM-DD.
    """
    st.toast(f"📅 Consolidando resumo mensal do cenário ID {scenario_id}...", icon="🔍")
    return logistics_services.get_monthly_summary(
        scenario_id=scenario_id,
        start_date=start_date,
        end_date=end_date
    )

def get_factories_summary(scenario_id: int) -> list[dict]:
    """
    Exibe o resumo mensal de operações de todas as fábricas (unidades de esmagamento)
    cadastradas no cenário especificado. Inclui dados de recebimento do produtor,
    recebimento via transbordo, volume esmagado, saldo de estoque final no mês, 
    capacidade estática máxima e volume excedente armazenado fora da capacidade.
    """
    st.toast(f"🏭 Carregando desempenho das fábricas no cenário ID {scenario_id}...", icon="🔍")
    return logistics_services.get_factories_summary(scenario_id=scenario_id)

def get_warehouses_summary(scenario_id: int) -> list[dict]:
    """
    Exibe o resumo mensal de operações de todos os armazéns (origens) cadastrados
    no cenário especificado. Inclui dados de recebimento de produtor local, 
    envio via transbordo para fábricas, vendas locais efetuadas, saldo de estoque
    final no mês, capacidade estática e volume excedente (transbordado/fora da capacidade).
    """
    st.toast(f"🌾 Carregando desempenho dos armazéns no cenário ID {scenario_id}...", icon="🔍")
    return logistics_services.get_warehouses_summary(scenario_id=scenario_id)

def compare_factories(scenario_id: int) -> list[dict]:
    """
    Agrega as métricas de desempenho e gargalos para todas as fábricas no cenário.
    Permite ao LLM comparar facilmente quais fábricas tiveram maior esmagamento total,
    picos de estoque máximos registrados ao longo do cenário, volume total de recebimento,
    e a quantidade total acumulada de excedentes (risco de ruptura/armazenamento incorreto).
    """
    st.toast(f"⚖️ Processando comparativo de gargalos das fábricas no cenário ID {scenario_id}...", icon="🔍")
    return logistics_services.compare_factories(scenario_id=scenario_id)

def compare_warehouses(scenario_id: int) -> list[dict]:
    """
    Agrega as métricas de desempenho e escoamento para todos os armazéns no cenário.
    Permite comparar quais armazéns receberam mais soja direta do produtor, quais
    escoaram o maior volume via transbordo, as vendas totais acumuladas e os maiores
    picos de estoque (gargalos de estocagem) e excedentes gerados no cenário.
    """
    st.toast(f"⚖️ Processando comparativo de escoamento dos armazéns no cenário ID {scenario_id}...", icon="🔍")
    return logistics_services.compare_warehouses(scenario_id=scenario_id)

def get_stock_excesses_report(scenario_id: int) -> list[dict]:
    """
    Gera um relatório analítico contendo todos os alertas de estouro de capacidade estática 
    (excedentes de estoque > 0) para armazéns e fábricas ao longo dos meses do cenário.
    Identifica com precisão quais meses e locais sofreram com sobrecarga de estocagem.
    """
    st.toast(f"🚨 Analisando alertas de estouro de capacidade no cenário ID {scenario_id}...", icon="⚠️")
    return logistics_services.get_stock_excesses_report(scenario_id=scenario_id)


# Lista de ferramentas que serão fornecidas ao modelo do Gemini
TOOLS = [
    list_scenarios,
    get_daily_movements,
    get_monthly_summary,
    get_factories_summary,
    get_warehouses_summary,
    compare_factories,
    compare_warehouses,
    get_stock_excesses_report
]

def check_api_key() -> bool:
    """Verifica se a chave da API do Gemini está disponível no ambiente."""
    return bool(os.getenv("GEMINI_API_KEY"))

def get_gemini_client() -> genai.Client:
    """Instancia o cliente do Gemini usando a chave do ambiente."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Chave de API do Gemini não configurada no ambiente. Verifique o arquivo .env.")
    return genai.Client(api_key=api_key)

def init_chat_session() -> bool:
    """
    Inicializa a sessão de chat do Gemini e guarda no st.session_state do Streamlit.
    Retorna True se inicializado com sucesso, False se houver algum erro de API ou configuração.
    """
    if "gemini_chat" in st.session_state and st.session_state.gemini_chat is not None:
        return True
        
    if not check_api_key():
        return False

    try:
        # Mantém o cliente vivo na sessão do Streamlit para evitar que seja garbage-collected
        if "gemini_client" not in st.session_state or st.session_state.gemini_client is None:
            st.session_state.gemini_client = get_gemini_client()
            
        client = st.session_state.gemini_client
        # Inicializa o chat nativo do SDK google-genai com Auto-Function Calling
        chat = client.chats.create(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=TOOLS,
                temperature=0.2
            )
        )
        st.session_state.gemini_chat = chat
        return True
    except Exception as e:
        st.error(f"Erro ao inicializar o assistente de IA: {str(e)}")
        st.session_state.gemini_chat = None
        return False

def send_message_to_assistant(message: str) -> str:
    """
    Envia uma mensagem para o chat do Gemini em execução automática de ferramentas.
    Retorna o texto da resposta final do assistente.
    """
    if "gemini_chat" not in st.session_state or st.session_state.gemini_chat is None:
        if not init_chat_session():
            return "Ocorreu um erro: o Assistente de IA não pôde ser inicializado. Verifique a configuração da GEMINI_API_KEY."

    try:
        chat = st.session_state.gemini_chat
        response = chat.send_message(message)
        return response.text
    except Exception as e:
        return f"Ocorreu um erro durante a conversação com a inteligência artificial: {str(e)}"

def clear_chat_session():
    """Limpa o histórico de conversação local e reinicia o assistente."""
    if "gemini_chat" in st.session_state:
        st.session_state.gemini_chat = None
    if "gemini_client" in st.session_state:
        st.session_state.gemini_client = None
    if "messages" in st.session_state:
        st.session_state.messages = []
