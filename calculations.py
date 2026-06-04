import logging
from ortools.linear_solver import pywraplp
import pandas as pd
import datetime
from models import Fabrica, Armazem, Rota, MovimentacaoDiaria, PrevisaoFabrica, PrevisaoArmazem, ResumoMensalFabrica, ResumoMensalArmazem, SafraUnidade
from sqlalchemy.orm import Session
from sqlalchemy import func, text

# Configuração de logging básico
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def esta_na_safra(session: Session, entidade_tipo, entidade_id, data, cenario_id):
    """Verifica se uma data específica está dentro da janela de safra de uma unidade."""
    safra = session.query(SafraUnidade).filter(
        SafraUnidade.cenario_id == cenario_id,
        SafraUnidade.entidade_tipo == entidade_tipo,
        SafraUnidade.entidade_id == entidade_id
    ).first()
    
    if safra:
        return safra.data_inicio <= data <= safra.data_fim
    
    # Fallback: Se não houver configuração de safra, usamos um período padrão (15/01 a 15/04)
    ano = data.year
    default_ini = datetime.date(ano, 1, 15)
    default_fim = datetime.date(ano, 4, 15)
    return default_ini <= data <= default_fim

def otimizar_dia(session: Session, data, estoques_atuais, estrategia='Econômico', cenario_id=None):
    """
    Otimiza a movimentação de soja para um dia específico.
    """
    solver = pywraplp.Solver.CreateSolver('SCIP')
    if not solver:
        solver = pywraplp.Solver.CreateSolver('GLOP')
    
    if not solver:
        logger.error("Nenhum solver (SCIP ou GLOP) disponível no OR-Tools.")
        return None

    fabricas = session.query(Fabrica).filter(Fabrica.cenario_id == cenario_id).all()
    armazens = session.query(Armazem).filter(Armazem.cenario_id == cenario_id).all()
    rotas = session.query(Rota).filter(Rota.cenario_id == cenario_id).all()

    if not rotas:
        return []

    # Variáveis de decisão
    v_mov = {}
    for r in rotas:
        v_mov[(r.armazem_id, r.fabrica_id)] = solver.NumVar(0, solver.infinity(), f'mov_{r.armazem_id}_{r.fabrica_id}')

    # 1. Capacidade de expedição dos armazéns
    for a in armazens:
        movs_saindo = [v_mov[(a.id, f.id)] for f in fabricas if (a.id, f.id) in v_mov]
        if movs_saindo:
            solver.Add(solver.Sum(movs_saindo) <= a.capacidade_expedicao_diaria)
            solver.Add(solver.Sum(movs_saindo) <= max(0, estoques_atuais.get(f'A_{a.id}', 0)))

    # 2. Capacidade de recebimento das fábricas (LIMITES OPERACIONAIS)
    for f in fabricas:
        movs_entrando = [v_mov[(a.id, f.id)] for a in armazens if (a.id, f.id) in v_mov]
        if not movs_entrando: continue
            
        recebimento_transbordo = solver.Sum(movs_entrando)
        
        # MANTEMOS: Limites físicos de descarga (Moega / Caminhões)
        solver.Add(recebimento_transbordo <= f.capacidade_recebimento_diaria)
        solver.Add(recebimento_transbordo <= f.limite_caminhoes * f.carga_media_caminhao)
        
        # REMOVIDO: Restrição de Capacidade Estática. 
        # O cliente deseja que a soja seja enviada para o local mais próximo mesmo que estoure a capacidade,
        # para evidenciar a necessidade de novos silos (Excedente).
        # espaco_disponivel = max(0, f.capacidade_estatica - estoques_atuais.get(f'F_{f.id}', 0) + f.capacidade_esmagamento_diaria)
        # solver.Add(recebimento_transbordo <= espaco_disponivel)

    # Variáveis para atendimento de demanda (slack variables)
    v_atendimento = {}
    for f in fabricas:
        demanda = max(0, f.capacidade_esmagamento_diaria - max(0, estoques_atuais.get(f'F_{f.id}', 0)))
        if demanda > 0:
            v_atendimento[f.id] = solver.NumVar(0, demanda, f'atend_{f.id}')
            movs_entrando = [v_mov[(a.id, f.id)] for a in armazens if (a.id, f.id) in v_mov]
            if movs_entrando:
                solver.Add(solver.Sum(movs_entrando) >= v_atendimento[f.id])

    # Pesos da Estratégia
    p_atendimento = 10000000 # Prioridade absoluta: não deixar a fábrica parar
    recompensa_base = 10000
    if estrategia == 'Econômico':
        recompensa_base = 100 # Reduzimos a recompensa base para o frete mandar na escolha do destino
    elif estrategia == 'Expedição':
        recompensa_base = 50000 # Força a saída do armazém a qualquer custo
    elif estrategia == 'Segurança':
        p_atendimento = 50000000

    objetivo = solver.Objective()
    for f_id, var in v_atendimento.items():
        objetivo.SetCoefficient(var, p_atendimento)
    
    for r in rotas:
        # Recupera as datas de safra para esta unidade
        safra = session.query(SafraUnidade).filter(
            SafraUnidade.cenario_id == cenario_id,
            SafraUnidade.entidade_tipo == 'Armazém',
            SafraUnidade.entidade_id == r.armazem_id
        ).first()
        
        d_ini = safra.data_inicio if safra else datetime.date(data.year, 1, 15)
        d_fim = safra.data_fim if safra else datetime.date(data.year, 4, 15)

        # Bloqueio total ANTES da safra começar (armazéns vazios)
        if data < d_ini:
            solver.Add(v_mov[(r.armazem_id, r.fabrica_id)] == 0)
            continue 

        # Define se é safra para custo e incentivo
        na_safra = (d_ini <= data <= d_fim)
        custo_ton = r.custo_frete_ton if na_safra else r.custo_frete_entressafra
        
        # Incentivo para movimentar: base + bônus de safra
        # O coeficiente agora é (Incentivo - Custo). Como queremos o mais próximo, 
        # o custo de frete tem peso real na escolha.
        incentivo_movimentar = recompensa_base + (1000 if na_safra else 0)
        
        # Coeficiente = Incentivo - Custo (Maximizar)
        objetivo.SetCoefficient(v_mov[(r.armazem_id, r.fabrica_id)], incentivo_movimentar - custo_ton)
    
    objetivo.SetMaximization()
    status = solver.Solve()

    if status == pywraplp.Solver.OPTIMAL or status == pywraplp.Solver.FEASIBLE:
        resultados = []
        for r in rotas:
            qtd = v_mov[(r.armazem_id, r.fabrica_id)].solution_value()
            if qtd > 0.001:
                # Determina o custo real usado para este dia no log
                safra = session.query(SafraUnidade).filter(SafraUnidade.cenario_id == cenario_id, SafraUnidade.entidade_tipo == 'Armazém', SafraUnidade.entidade_id == r.armazem_id).first()
                d_ini = safra.data_inicio if safra else datetime.date(data.year, 1, 15)
                d_fim = safra.data_fim if safra else datetime.date(data.year, 4, 15)
                na_safra_real = (d_ini <= data <= d_fim)
                custo_ton_real = r.custo_frete_ton if na_safra_real else r.custo_frete_entressafra
                
                resultados.append({
                    'armazem_id': r.armazem_id,
                    'fabrica_id': r.fabrica_id,
                    'quantidade_ton': qtd,
                    'custo_total': qtd * custo_ton_real
                })
        return resultados
    return None

def simular_periodo(session: Session, data_inicio, data_fim_previsao, cenario_id=None, estrategia='Econômico'):
    c_id = int(cenario_id) if cenario_id is not None else None

    # REQUISITO: Limpeza Absoluta via ORM para evitar rastro de dados (ghost data)
    session.query(MovimentacaoDiaria).filter(MovimentacaoDiaria.cenario_id == c_id).delete(synchronize_session=False)
    session.query(ResumoMensalFabrica).filter(ResumoMensalFabrica.cenario_id == c_id).delete(synchronize_session=False)
    session.query(ResumoMensalArmazem).filter(ResumoMensalArmazem.cenario_id == c_id).delete(synchronize_session=False)
    session.commit()

    # Ajuste data_inicio para o dia 1 do mês para capturar o volume total.
    data_inicio_ajustada = pd.to_datetime(data_inicio).date().replace(day=1)
    
    # Carregar estoques iniciais
    fabricas = session.query(Fabrica).filter(Fabrica.cenario_id == c_id).all()
    armazens = session.query(Armazem).filter(Armazem.cenario_id == c_id).all()
    
    estoques_atuais = {}
    for f in fabricas: estoques_atuais[f'F_{f.id}'] = f.estoque_inicial
    for a in armazens: estoques_atuais[f'A_{a.id}'] = a.estoque_inicial

    data_atual = data_inicio_ajustada
    d_fim_p = pd.to_datetime(data_fim_previsao).date()
    
    resumos_fab = {}
    resumos_arm = {}
    dias_executados = 0
    max_dias = 730

    while True:
        mes_str = data_atual.strftime('%Y-%m')
        
        if mes_str not in resumos_fab:
            resumos_fab[mes_str] = {f.id: {'rec_produtor': 0, 'rec_transbordo': 0, 'esmagado': 0, 'cap_estatica': f.capacidade_estatica} for f in fabricas}
        if mes_str not in resumos_arm:
            resumos_arm[mes_str] = {a.id: {'rec_produtor': 0, 'envio_transbordo': 0, 'vendas': 0, 'cap_estatica': a.capacidade_estatica} for a in armazens}

        mes_atual_date = datetime.date(data_atual.year, data_atual.month, 1)
        dias_no_mes = pd.Period(data_atual.strftime('%Y-%m-%d')).days_in_month

        # 1. Processar Previsões
        for f in fabricas:
            prev = session.query(PrevisaoFabrica).filter_by(fabrica_id=f.id, mes_referencia=mes_atual_date).first()
            if prev:
                rec_diario = (prev.recebimento_produtor or 0) / dias_no_mes
                vend_diario = (prev.vendas or 0) / dias_no_mes
                estoques_atuais[f'F_{f.id}'] += (rec_diario - vend_diario)
                resumos_fab[mes_str][f.id]['rec_produtor'] += rec_diario

        for a in armazens:
            prev = session.query(PrevisaoArmazem).filter_by(armazem_id=a.id, mes_referencia=mes_atual_date).first()
            if prev:
                rec_diario = (prev.recebimento_produtor or 0) / dias_no_mes
                vend_diario = (prev.vendas or 0) / dias_no_mes
                estoques_atuais[f'A_{a.id}'] += (rec_diario - vend_diario)
                resumos_arm[mes_str][a.id]['rec_produtor'] += rec_diario
                resumos_arm[mes_str][a.id]['vendas'] += vend_diario
        
        # 2. Otimizar transbordo
        movimentacoes = otimizar_dia(session, data_atual, estoques_atuais, estrategia=estrategia, cenario_id=c_id)
        
        if movimentacoes:
            for mov in movimentacoes:
                session.add(MovimentacaoDiaria(
                    cenario_id=c_id,
                    data=data_atual,
                    armazem_id=mov['armazem_id'],
                    fabrica_id=mov['fabrica_id'],
                    quantidade_ton=mov['quantidade_ton'],
                    custo_total=mov['custo_total']
                ))
                estoques_atuais[f'A_{mov["armazem_id"]}'] -= mov['quantidade_ton']
                estoques_atuais[f'F_{mov["fabrica_id"]}'] += mov['quantidade_ton']
                resumos_arm[mes_str][mov['armazem_id']]['envio_transbordo'] += mov['quantidade_ton']
                resumos_fab[mes_str][mov['fabrica_id']]['rec_transbordo'] += mov['quantidade_ton']
        
        # 3. Processar consumo diário (esmagamento)
        for f in fabricas:
            esmagado_real = min(max(0, estoques_atuais[f'F_{f.id}']), f.capacidade_esmagamento_diaria)
            estoques_atuais[f'F_{f.id}'] -= esmagado_real
            resumos_fab[mes_str][f.id]['esmagado'] += esmagado_real
            
        # 4. Verificar Condição de Parada
        total_estoque_arm = sum(max(0, estoques_atuais[f'A_{a.id}']) for a in armazens)
        acabaram_previsoes = data_atual >= d_fim_p
        armazens_vazios = total_estoque_arm < 1.0 
        
        eh_ultimo_dia_simulacao = (acabaram_previsoes and armazens_vazios) or dias_executados >= max_dias
        eh_ultimo_dia_mes = (data_atual + datetime.timedelta(days=1)).month != data_atual.month

        if eh_ultimo_dia_mes or eh_ultimo_dia_simulacao:
            for f in fabricas:
                resumos_fab[mes_str][f.id]['saldo_estoque'] = estoques_atuais[f'F_{f.id}']
                resumos_fab[mes_str][f.id]['excedente'] = max(0, estoques_atuais[f'F_{f.id}'] - resumos_fab[mes_str][f.id]['cap_estatica'])
            for a in armazens:
                resumos_arm[mes_str][a.id]['saldo_estoque'] = estoques_atuais[f'A_{a.id}']
                resumos_arm[mes_str][a.id]['excedente'] = max(0, estoques_atuais[f'A_{a.id}'] - resumos_arm[mes_str][a.id]['cap_estatica'])

        if eh_ultimo_dia_simulacao:
            break
            
        data_atual += datetime.timedelta(days=1)
        dias_executados += 1

    # Salvar Resumos Mensais
    for mes, fab_dict in resumos_fab.items():
        for f_id, dados in fab_dict.items():
            session.add(ResumoMensalFabrica(
                cenario_id=c_id, mes=mes, fabrica_id=f_id,
                rec_produtor=dados['rec_produtor'], rec_transbordo=dados['rec_transbordo'],
                esmagado=dados['esmagado'], saldo_estoque=dados.get('saldo_estoque', 0),
                capacidade_estatica=dados['cap_estatica'], excedente=dados.get('excedente', 0)
            ))
            
    for mes, arm_dict in resumos_arm.items():
        for a_id, dados in arm_dict.items():
            session.add(ResumoMensalArmazem(
                cenario_id=c_id, mes=mes, armazem_id=a_id,
                rec_produtor=dados['rec_produtor'], envio_transbordo=dados['envio_transbordo'],
                vendas=dados['vendas'], saldo_estoque=dados.get('saldo_estoque', 0),
                capacidade_estatica=dados['cap_estatica'], excedente=dados.get('excedente', 0)
            ))

    session.commit()

def obter_range_previsoes(session: Session, cenario_id=None):
    min_f = session.query(func.min(PrevisaoFabrica.mes_referencia)).join(Fabrica).filter(Fabrica.cenario_id == cenario_id).scalar()
    max_f = session.query(func.max(PrevisaoFabrica.mes_referencia)).join(Fabrica).filter(Fabrica.cenario_id == cenario_id).scalar()
    min_a = session.query(func.min(PrevisaoArmazem.mes_referencia)).join(Armazem).filter(Armazem.cenario_id == cenario_id).scalar()
    max_a = session.query(func.max(PrevisaoArmazem.mes_referencia)).join(Armazem).filter(Armazem.cenario_id == cenario_id).scalar()
    
    dates = [d for d in [min_f, max_f, min_a, max_a] if d is not None]
    if not dates:
        return None, None
        
    start_date = min(dates)
    end_date_start_month = max(dates)
    end_date = (pd.Timestamp(end_date_start_month) + pd.offsets.MonthEnd(0)).date()
    
    return start_date, end_date
