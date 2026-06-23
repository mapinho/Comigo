import datetime
import pandas as pd
from fastmcp import FastMCP
from data_loader import init_db
from models import (
    Cenario, Fabrica, Armazem, Rota, PrevisaoFabrica, PrevisaoArmazem, 
    MovimentacaoDiaria, ResumoMensalFabrica, ResumoMensalArmazem, SafraUnidade
)
from sqlalchemy import func

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
    session = init_db()
    try:
        scenarios_list = session.query(Cenario).order_by(Cenario.is_oficial.desc(), Cenario.nome).all()
        return [
            {
                "id": c.id,
                "nome": c.nome,
                "is_oficial": bool(c.is_oficial),
                "data_criacao": c.data_criacao.strftime("%Y-%m-%d %H:%M:%S") if c.data_criacao else None
            }
            for c in scenarios_list
        ]
    finally:
        session.close()

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
    session = init_db()
    try:
        query = session.query(MovimentacaoDiaria).filter(MovimentacaoDiaria.cenario_id == scenario_id)
        
        if start_date:
            d_ini = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
            query = query.filter(MovimentacaoDiaria.data >= d_ini)
        if end_date:
            d_fim = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
            query = query.filter(MovimentacaoDiaria.data <= d_fim)
        if origin_id:
            query = query.filter(MovimentacaoDiaria.armazem_id == origin_id)
        if destination_id:
            query = query.filter(MovimentacaoDiaria.fabrica_id == destination_id)
            
        movements = query.order_by(MovimentacaoDiaria.data).limit(limit).all()
        
        # Mapeamento para nomes amigaveis das entidades
        results = []
        for m in movements:
            arm = session.get(Armazem, m.armazem_id)
            fab = session.get(Fabrica, m.fabrica_id)
            results.append({
                "id": m.id,
                "data": m.data.strftime("%Y-%m-%d"),
                "origem_id": m.armazem_id,
                "origem": arm.nome if arm else "N/A",
                "destino_id": m.fabrica_id,
                "destino": fab.nome if fab else "N/A",
                "quantidade_ton": m.quantidade_ton,
                "quantidade_sc": m.quantidade_ton * 1000 / 60,
                "custo_total_r$": m.custo_total
            })
        return results
    finally:
        session.close()

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
    session = init_db()
    try:
        query = session.query(MovimentacaoDiaria).filter(MovimentacaoDiaria.cenario_id == scenario_id)
        if start_date:
            d_ini = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
            query = query.filter(MovimentacaoDiaria.data >= d_ini)
        if end_date:
            d_fim = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
            query = query.filter(MovimentacaoDiaria.data <= d_fim)
            
        movements = query.all()
        if not movements:
            return {"meses": [], "rotas": []}
            
        df = pd.DataFrame([{
            "data": m.data,
            "origem": session.get(Armazem, m.armazem_id).nome if session.get(Armazem, m.armazem_id) else "N/A",
            "destino": session.get(Fabrica, m.fabrica_id).nome if session.get(Fabrica, m.fabrica_id) else "N/A",
            "quantidade_ton": m.quantidade_ton,
            "quantidade_sc": m.quantidade_ton * 1000 / 60,
            "custo_total": m.custo_total
        } for m in movements])
        
        df["mes"] = pd.to_datetime(df["data"]).dt.strftime("%Y-%m")
        
        # Agrupamento Mensal Total
        df_mes = df.groupby("mes").agg({
            "quantidade_ton": "sum",
            "quantidade_sc": "sum",
            "custo_total": "sum"
        }).reset_index()
        
        # Agrupamento por Rota
        df_rotas = df.groupby(["mes", "origem", "destino"]).agg({
            "quantidade_ton": "sum",
            "quantidade_sc": "sum",
            "custo_total": "sum"
        }).reset_index()
        
        return {
            "resumo_mensal": df_mes.to_dict(orient="records"),
            "detalhe_rotas": df_rotas.to_dict(orient="records")
        }
    finally:
        session.close()

@mcp.tool()
def get_factories_summary(scenario_id: int) -> list[dict]:
    """
    Exibe o resumo mensal de operacoes de todas as fabricas (unidades de esmagamento)
    cadastradas no cenario especificado. Inclui dados de recebimento do produtor,
    recebimento via transbordo, volume esmagado, saldo de estoque final no mes, 
    capacidade estatica maxima e volume excedente armazenado fora da capacidade.
    """
    session = init_db()
    try:
        resumos = session.query(ResumoMensalFabrica).filter(ResumoMensalFabrica.cenario_id == scenario_id).all()
        results = []
        for r in resumos:
            fab = session.get(Fabrica, r.fabrica_id)
            results.append({
                "mes": r.mes,
                "fabrica_id": r.fabrica_id,
                "fabrica": fab.nome if fab else "N/A",
                "recebimento_produtor_ton": r.rec_produtor,
                "recebimento_transbordo_ton": r.rec_transbordo,
                "esmagado_ton": r.esmagado,
                "saldo_estoque_ton": r.saldo_estoque,
                "capacidade_estatica_ton": r.capacidade_estatica,
                "excedente_estoque_ton": r.excedente
            })
        return sorted(results, key=lambda x: (x["mes"], x["fabrica"]))
    finally:
        session.close()

@mcp.tool()
def get_warehouses_summary(scenario_id: int) -> list[dict]:
    """
    Exibe o resumo mensal de operacoes de todos os armazens (origens) cadastrados
    no cenario especificado. Inclui dados de recebimento de produtor local, 
    envio via transbordo para fabricas, vendas locais efetuadas, saldo de estoque
    final no mes, capacidade estatica e volume excedente (transbordado/fora da capacidade).
    """
    session = init_db()
    try:
        resumos = session.query(ResumoMensalArmazem).filter(ResumoMensalArmazem.cenario_id == scenario_id).all()
        results = []
        for r in resumos:
            arm = session.get(Armazem, r.armazem_id)
            results.append({
                "mes": r.mes,
                "armazem_id": r.armazem_id,
                "armazem": arm.nome if arm else "N/A",
                "recebimento_produtor_ton": r.rec_produtor,
                "envio_transbordo_ton": r.envio_transbordo,
                "vendas_ton": r.vendas,
                "saldo_estoque_ton": r.saldo_estoque,
                "capacidade_estatica_ton": r.capacidade_estatica,
                "excedente_estoque_ton": r.excedente
            })
        return sorted(results, key=lambda x: (x["mes"], x["armazem"]))
    finally:
        session.close()

@mcp.tool()
def compare_factories(scenario_id: int) -> list[dict]:
    """
    Agrega as metricas de desempenho e gargalos para todas as fabricas no cenario.
    Permite ao LLM comparar facilmente quais fabricas tiveram maior esmagamento total,
    picos de estoque maximos registrados ao longo do cenario, volume total de recebimento,
    e a quantidade total acumulada de excedentes (risco de ruptura/armazenamento incorreto).
    """
    session = init_db()
    try:
        resumos = session.query(ResumoMensalFabrica).filter(ResumoMensalFabrica.cenario_id == scenario_id).all()
        if not resumos:
            return []
            
        df = pd.DataFrame([{
            "fabrica_id": r.fabrica_id,
            "fabrica": session.get(Fabrica, r.fabrica_id).nome if session.get(Fabrica, r.fabrica_id) else "N/A",
            "rec_produtor": r.rec_produtor,
            "rec_transbordo": r.rec_transbordo,
            "esmagado": r.esmagado,
            "saldo_estoque": r.saldo_estoque,
            "excedente": r.excedente
        } for r in resumos])
        
        # Agrupa para consolidar o cenario
        comp = df.groupby(["fabrica_id", "fabrica"]).agg({
            "rec_produtor": "sum",
            "rec_transbordo": "sum",
            "esmagado": "sum",
            "saldo_estoque": "max",  # Pico de estoque
            "excedente": "sum"       # Total acumulado de excedente
        }).reset_index()
        
        comp.rename(columns={
            "rec_produtor": "recebimento_produtor_total_ton",
            "rec_transbordo": "recebimento_transbordo_total_ton",
            "esmagado": "esmagado_total_ton",
            "saldo_estoque": "pico_estoque_mensal_ton",
            "excedente": "excedente_total_acumulado_ton"
        }, inplace=True)
        
        return comp.to_dict(orient="records")
    finally:
        session.close()

@mcp.tool()
def compare_warehouses(scenario_id: int) -> list[dict]:
    """
    Agrega as metricas de desempenho e escoamento para todos os armazens no cenario.
    Permite comparar quais armazens receberam mais soja direta do produtor, quais
    escoaram o maior volume via transbordo, as vendas totais acumuladas e os maiores
    picos de estoque (gargalos de estocagem) e excedentes gerados no cenario.
    """
    session = init_db()
    try:
        resumos = session.query(ResumoMensalArmazem).filter(ResumoMensalArmazem.cenario_id == scenario_id).all()
        if not resumos:
            return []
            
        df = pd.DataFrame([{
            "armazem_id": r.armazem_id,
            "armazem": session.get(Armazem, r.armazem_id).nome if session.get(Armazem, r.armazem_id) else "N/A",
            "rec_produtor": r.rec_produtor,
            "envio_transbordo": r.envio_transbordo,
            "vendas": r.vendas,
            "saldo_estoque": r.saldo_estoque,
            "excedente": r.excedente
        } for r in resumos])
        
        comp = df.groupby(["armazem_id", "armazem"]).agg({
            "rec_produtor": "sum",
            "envio_transbordo": "sum",
            "vendas": "sum",
            "saldo_estoque": "max",  # Pico de estoque
            "excedente": "sum"       # Total acumulado de excedente
        }).reset_index()
        
        comp.rename(columns={
            "rec_produtor": "recebimento_produtor_total_ton",
            "envio_transbordo": "envio_transbordo_total_ton",
            "vendas": "vendas_total_ton",
            "saldo_estoque": "pico_estoque_mensal_ton",
            "excedente": "excedente_total_acumulado_ton"
        }, inplace=True)
        
        return comp.to_dict(orient="records")
    finally:
        session.close()

@mcp.tool()
def get_stock_excesses_report(scenario_id: int) -> list[dict]:
    """
    Gera um relatorio analitico contendo todos os alertas de estouro de capacidade estatica 
    (excedentes de estoque > 0) para armazens e fabricas ao longo dos meses do cenario.
    Identifica com precisao quais meses e locais sofreram com sobrecarga de estocagem.
    """
    session = init_db()
    try:
        alertas = []
        
        # 1. Varre Fábricas
        res_fab = session.query(ResumoMensalFabrica).filter(
            ResumoMensalFabrica.cenario_id == scenario_id,
            ResumoMensalFabrica.excedente > 0
        ).all()
        for r in res_fab:
            fab = session.get(Fabrica, r.fabrica_id)
            alertas.append({
                "mes": r.mes,
                "entidade_tipo": "Fabrica",
                "entidade_id": r.fabrica_id,
                "entidade_nome": fab.nome if fab else "N/A",
                "estoque_final_ton": r.saldo_estoque,
                "capacidade_estatica_ton": r.capacidade_estatica,
                "excedente_estouro_ton": r.excedente
            })
            
        # 2. Varre Armazéns
        res_arm = session.query(ResumoMensalArmazem).filter(
            ResumoMensalArmazem.cenario_id == scenario_id,
            ResumoMensalArmazem.excedente > 0
        ).all()
        for r in res_arm:
            arm = session.get(Armazem, r.armazem_id)
            alertas.append({
                "mes": r.mes,
                "entidade_tipo": "Armazem",
                "entidade_id": r.armazem_id,
                "entidade_nome": arm.nome if arm else "N/A",
                "estoque_final_ton": r.saldo_estoque,
                "capacidade_estatica_ton": r.capacidade_estatica,
                "excedente_estouro_ton": r.excedente
            })
            
        return sorted(alertas, key=lambda x: (x["mes"], x["entidade_tipo"], x["entidade_nome"]))
    finally:
        session.close()

if __name__ == "__main__":
    mcp.run(transport="stdio")
