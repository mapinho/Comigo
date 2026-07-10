from fastmcp import FastMCP
import logistics_services

# Inicializa o MCP Server
mcp = FastMCP(
    "Comigo Logistica MCP Server",
    instructions="Servidor MCP para consulta e analise de simulacoes e movimentacoes logisticas de soja da Comigo."
)

@mcp.tool()
def list_scenarios() -> list[dict]:
    """
    Lista todos os cenarios de simulacao cadastrados no sistema,
    indicando qual e o cenario oficial e o seu ID correspondente.
    """
    return logistics_services.list_scenarios()

@mcp.tool()
def get_daily_movements(
    scenario_id: int,
    start_date: str = None,
    end_date: str = None,
    origin_id: int = None,
    destination_id: int = None,
    limit: int = 150
) -> list[dict]:
    """
    Retorna a lista detalhada de movimentacoes diarias de soja para um cenario especifico.
    Permite filtrar por intervalo de datas (AAAA-MM-DD), ID do armazem de origem (origin_id),
    ID da fabrica de destino (destination_id). Retorna o volume em Ton, Sc (sacas) e Custo Financeiro.
    """
    return logistics_services.get_daily_movements(
        scenario_id=scenario_id,
        start_date=start_date,
        end_date=end_date,
        origin_id=origin_id,
        destination_id=destination_id,
        limit=limit
    )

@mcp.tool()
def get_monthly_summary(
    scenario_id: int,
    start_date: str = None,
    end_date: str = None
) -> dict:
    """
    Retorna o resumo consolidado por mes (e detalhamento por rota) das movimentacoes.
    Util para analise mensal do volume movimentado em toneladas, sacas e o custo total de frete.
    Intervalos de data opcionais no formato AAAA-MM-DD.
    """
    return logistics_services.get_monthly_summary(
        scenario_id=scenario_id,
        start_date=start_date,
        end_date=end_date
    )

@mcp.tool()
def get_factories_summary(scenario_id: int) -> list[dict]:
    """
    Exibe o resumo mensal de operacoes de todas as fabricas (unidades de esmagamento)
    cadastradas no cenario especificado. Inclui dados de recebimento do produtor,
    recebimento via transbordo, volume esmagado, saldo de estoque final no mes, 
    capacidade estatica maxima e volume excedente armazenado fora da capacidade.
    """
    return logistics_services.get_factories_summary(scenario_id=scenario_id)

@mcp.tool()
def get_warehouses_summary(scenario_id: int) -> list[dict]:
    """
    Exibe o resumo mensal de operacoes de todos os armazens (origens) cadastrados
    no cenario especificado. Inclui dados de recebimento de produtor local, 
    envio via transbordo para fabricas, vendas locais efetuadas, saldo de estoque
    final no mes, capacidade estatica e volume excedente (transbordado/fora da capacidade).
    """
    return logistics_services.get_warehouses_summary(scenario_id=scenario_id)

@mcp.tool()
def compare_factories(scenario_id: int) -> list[dict]:
    """
    Agrega as metricas de desempenho e gargalos para todas as fabricas no cenario.
    Permite ao LLM comparar facilmente quais fabricas tiveram maior esmagamento total,
    picos de estoque maximos registrados ao longo do cenario, volume total de recebimento,
    e a quantidade total acumulada de excedentes (risco de ruptura/armazenamento incorreto).
    """
    return logistics_services.compare_factories(scenario_id=scenario_id)

@mcp.tool()
def compare_warehouses(scenario_id: int) -> list[dict]:
    """
    Agrega as metricas de desempenho e escoamento para todos os armazens no cenario.
    Permite comparar quais armazens receberam mais soja direta do produtor, quais
    escoaram o maior volume via transbordo, as vendas totais acumuladas e os maiores
    picos de estoque (gargalos de estocagem) e excedentes gerados no cenario.
    """
    return logistics_services.compare_warehouses(scenario_id=scenario_id)

@mcp.tool()
def get_stock_excesses_report(scenario_id: int) -> list[dict]:
    """
    Gera um relatorio analitico contendo todos os alertas de estouro de capacidade estatica 
    (excedentes de estoque > 0) para armazens e fabricas ao longo dos meses do cenario.
    Identifica com precisao quais meses e locais sofreram com sobrecarga de estocagem.
    """
    return logistics_services.get_stock_excesses_report(scenario_id=scenario_id)

if __name__ == "__main__":
    mcp.run(transport="stdio")
