import logging
from ortools.linear_solver import pywraplp
import pandas as pd
import datetime
from models import Fabrica, Armazem, Rota, MovimentacaoDiaria, PrevisaoFabrica, PrevisaoArmazem, ResumoMensalFabrica, ResumoMensalArmazem
from sqlalchemy.orm import Session
from sqlalchemy import func

# Configuração de logging básico
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def otimizar_dia(session: Session, data, estoques_atuais, eh_safra_armazens):
    """
    Otimiza a movimentação de soja para um dia específico.
    estoques_atuais: dicionário com o estoque de cada armazém e fábrica no início do dia.
    eh_safra_armazens: dicionário {armazem_id: bool} indicando se está em safra.
    """
    # Tenta usar SCIP, se não disponível tenta GLOP
    solver = pywraplp.Solver.CreateSolver('SCIP')
    if not solver:
        solver = pywraplp.Solver.CreateSolver('GLOP')
    
    if not solver:
        logger.error("Nenhum solver (SCIP ou GLOP) disponível no OR-Tools.")
        return None

    fabricas = session.query(Fabrica).all()
    armazens = session.query(Armazem).all()
    rotas = session.query(Rota).all()

    if not rotas:
        logger.warning(f"Sem rotas cadastradas para o dia {data}")
        return []

    # Variáveis de decisão: volume enviado do armazém i para a fábrica j
    v_mov = {}
    for r in rotas:
        v_mov[(r.armazem_id, r.fabrica_id)] = solver.NumVar(0, solver.infinity(), f'mov_{r.armazem_id}_{r.fabrica_id}')

    # Restrições
    
    # 1. Capacidade de expedição dos armazéns
    for a in armazens:
        movs_saindo = [v_mov[(a.id, f.id)] for f in fabricas if (a.id, f.id) in v_mov]
        if movs_saindo:
            solver.Add(solver.Sum(movs_saindo) <= a.capacidade_expedicao_diaria)
            # Não pode enviar mais do que tem no estoque
            solver.Add(solver.Sum(movs_saindo) <= max(0, estoques_atuais.get(f'A_{a.id}', 0)))

    # 2. Capacidade de recebimento das fábricas
    for f in fabricas:
        movs_entrando = [v_mov[(a.id, f.id)] for a in armazens if (a.id, f.id) in v_mov]
        if not movs_entrando:
            continue
            
        recebimento_transbordo = solver.Sum(movs_entrando)
        
        # Limite de recebimento diário
        solver.Add(recebimento_transbordo <= f.capacidade_recebimento_diaria)
        
        # Limite de caminhões
        solver.Add(recebimento_transbordo <= f.limite_caminhoes * f.carga_media_caminhao)
        
        # Restrição de Capacidade Estática:
        # A fábrica só pode receber transbordo até o limite de sua capacidade estática.
        # Desconta o estoque atual e soma a capacidade de esmagamento diário (que libera espaço).
        espaco_disponivel = max(0, f.capacidade_estatica - estoques_atuais.get(f'F_{f.id}', 0) + f.capacidade_esmagamento_diaria)
        solver.Add(recebimento_transbordo <= espaco_disponivel)

    # Variáveis para atendimento de demanda (slack variables)
    v_atendimento = {}
    for f in fabricas:
        demanda = max(0, f.capacidade_esmagamento_diaria - max(0, estoques_atuais.get(f'F_{f.id}', 0)))
        if demanda > 0:
            # Volume de demanda que conseguiremos atender
            v_atendimento[f.id] = solver.NumVar(0, demanda, f'atend_{f.id}')
            movs_entrando = [v_mov[(a.id, f.id)] for a in armazens if (a.id, f.id) in v_mov]
            if movs_entrando:
                solver.Add(solver.Sum(movs_entrando) >= v_atendimento[f.id])

    # Objetivo: Maximizar Atendimento da Demanda e Minimizar Custo de Frete
    # Atendimento tem um peso muito alto para ser prioridade
    objetivo = solver.Objective()
    for f_id, var in v_atendimento.items():
        objetivo.SetCoefficient(var, 1000000) # Prioridade máxima: atender esmagamento
    
    for r in rotas:
        # Requisito: Priorizar os armazéns com os menores custos de transporte antes e deixar os maiores para o final.
        # Para forçar o otimizador a sempre querer enviar soja (até encher a fábrica), 
        # damos uma recompensa base alta (maior que qualquer frete).
        # Subtraindo o frete, ele sempre escolherá a rota mais barata primeiro para maximizar o lucro.
        recompensa_base = 10000
        
        # Incentivo extra para movimentar na safra (Requisito 3.2)
        incentivo_safra = 1000 if eh_safra_armazens.get(r.armazem_id) else 0
        
        # Coeficiente = Recompensa + Incentivo - Custo (Maximizar)
        objetivo.SetCoefficient(v_mov[(r.armazem_id, r.fabrica_id)], recompensa_base + incentivo_safra - r.custo_frete_ton)
    
    objetivo.SetMaximization()

    status = solver.Solve()

    if status == pywraplp.Solver.OPTIMAL or status == pywraplp.Solver.FEASIBLE:
        resultados = []
        for r in rotas:
            qtd = v_mov[(r.armazem_id, r.fabrica_id)].solution_value()
            if qtd > 0.001: # Pequena tolerância para float
                resultados.append({
                    'armazem_id': r.armazem_id,
                    'fabrica_id': r.fabrica_id,
                    'quantidade_ton': qtd,
                    'custo_total': qtd * r.custo_frete_ton
                })
        return resultados
    else:
        logger.warning(f"Infeasivel para o dia {data}. Status: {status}")
        return None

def simular_periodo(session: Session, data_inicio, data_fim):
    # Limpar movimentações existentes no período para evitar duplicidade
    session.query(MovimentacaoDiaria).filter(MovimentacaoDiaria.data.between(data_inicio, data_fim)).delete()
    session.query(ResumoMensalFabrica).delete()
    session.query(ResumoMensalArmazem).delete()
    session.commit()

    # Carregar estoques iniciais
    fabricas = session.query(Fabrica).all()
    armazens = session.query(Armazem).all()
    
    estoques_atuais = {}
    for f in fabricas: estoques_atuais[f'F_{f.id}'] = f.estoque_inicial
    for a in armazens: estoques_atuais[f'A_{a.id}'] = a.estoque_inicial

    datas = pd.date_range(data_inicio, data_fim)
    
    resumos_fab = {}
    resumos_arm = {}

    for data in datas:
        data_date = data.date()
        mes_str = data_date.strftime('%Y-%m')
        
        if mes_str not in resumos_fab:
            resumos_fab[mes_str] = {f.id: {'rec_produtor': 0, 'rec_transbordo': 0, 'esmagado': 0, 'cap_estatica': f.capacidade_estatica} for f in fabricas}
        if mes_str not in resumos_arm:
            resumos_arm[mes_str] = {a.id: {'rec_produtor': 0, 'envio_transbordo': 0, 'vendas': 0, 'cap_estatica': a.capacidade_estatica} for a in armazens}

        mes_atual = datetime.date(data_date.year, data_date.month, 1)
        dias_no_mes = pd.Period(data_date.strftime('%Y-%m-%d')).days_in_month

        eh_safra_armazens = {}
        for f in fabricas:
            prev = session.query(PrevisaoFabrica).filter_by(fabrica_id=f.id, mes_referencia=mes_atual).first()
            if prev:
                rec_diario = (prev.recebimento_produtor or 0) / dias_no_mes
                vend_diario = (prev.vendas or 0) / dias_no_mes
                estoques_atuais[f'F_{f.id}'] += (rec_diario - vend_diario)
                resumos_fab[mes_str][f.id]['rec_produtor'] += rec_diario

        for a in armazens:
            prev = session.query(PrevisaoArmazem).filter_by(armazem_id=a.id, mes_referencia=mes_atual).first()
            if prev:
                rec_diario = (prev.recebimento_produtor or 0) / dias_no_mes
                vend_diario = (prev.vendas or 0) / dias_no_mes
                estoques_atuais[f'A_{a.id}'] += (rec_diario - vend_diario)
                resumos_arm[mes_str][a.id]['rec_produtor'] += rec_diario
                resumos_arm[mes_str][a.id]['vendas'] += vend_diario
                eh_safra_armazens[a.id] = (prev.eh_safra == 1)
            else:
                eh_safra_armazens[a.id] = False
        
        # 2. Otimizar transbordo
        movimentacoes = otimizar_dia(session, data_date, estoques_atuais, eh_safra_armazens)
        
        if movimentacoes:
            for mov in movimentacoes:
                # Salvar no banco
                m = MovimentacaoDiaria(
                    data=data_date,
                    armazem_id=mov['armazem_id'],
                    fabrica_id=mov['fabrica_id'],
                    quantidade_ton=mov['quantidade_ton'],
                    custo_total=mov['custo_total']
                )
                session.add(m)
                
                # Atualizar estoques e resumos
                estoques_atuais[f'A_{mov["armazem_id"]}'] -= mov['quantidade_ton']
                estoques_atuais[f'F_{mov["fabrica_id"]}'] += mov['quantidade_ton']
                resumos_arm[mes_str][mov['armazem_id']]['envio_transbordo'] += mov['quantidade_ton']
                resumos_fab[mes_str][mov['fabrica_id']]['rec_transbordo'] += mov['quantidade_ton']
        
        # 3. Processar consumo diário (esmagamento)
        for f in fabricas:
            esmagado_real = min(estoques_atuais[f'F_{f.id}'], f.capacidade_esmagamento_diaria)
            estoques_atuais[f'F_{f.id}'] -= esmagado_real
            resumos_fab[mes_str][f.id]['esmagado'] += esmagado_real
            
        # Verificar se é o último dia do mês ou o último dia da simulação para salvar o saldo
        is_last_day_of_month = (data_date + datetime.timedelta(days=1)).month != data_date.month
        is_last_day_of_sim = data_date == data_fim
        if is_last_day_of_month or is_last_day_of_sim:
            for f in fabricas:
                resumos_fab[mes_str][f.id]['saldo_estoque'] = estoques_atuais[f'F_{f.id}']
                resumos_fab[mes_str][f.id]['excedente'] = max(0, estoques_atuais[f'F_{f.id}'] - resumos_fab[mes_str][f.id]['cap_estatica'])
            for a in armazens:
                resumos_arm[mes_str][a.id]['saldo_estoque'] = estoques_atuais[f'A_{a.id}']
                resumos_arm[mes_str][a.id]['excedente'] = max(0, estoques_atuais[f'A_{a.id}'] - resumos_arm[mes_str][a.id]['cap_estatica'])

    # Salvar resumos no banco
    for mes, fab_dict in resumos_fab.items():
        for f_id, dados in fab_dict.items():
            rf = ResumoMensalFabrica(
                mes=mes, fabrica_id=f_id,
                rec_produtor=dados['rec_produtor'],
                rec_transbordo=dados['rec_transbordo'],
                esmagado=dados['esmagado'],
                saldo_estoque=dados.get('saldo_estoque', 0),
                capacidade_estatica=dados['cap_estatica'],
                excedente=dados.get('excedente', 0)
            )
            session.add(rf)
            
    for mes, arm_dict in resumos_arm.items():
        for a_id, dados in arm_dict.items():
            ra = ResumoMensalArmazem(
                mes=mes, armazem_id=a_id,
                rec_produtor=dados['rec_produtor'],
                envio_transbordo=dados['envio_transbordo'],
                vendas=dados['vendas'],
                saldo_estoque=dados.get('saldo_estoque', 0),
                capacidade_estatica=dados['cap_estatica'],
                excedente=dados.get('excedente', 0)
            )
            session.add(ra)

    session.commit()

def obter_range_previsoes(session: Session):
    min_f = session.query(func.min(PrevisaoFabrica.mes_referencia)).scalar()
    max_f = session.query(func.max(PrevisaoFabrica.mes_referencia)).scalar()
    min_a = session.query(func.min(PrevisaoArmazem.mes_referencia)).scalar()
    max_a = session.query(func.max(PrevisaoArmazem.mes_referencia)).scalar()
    
    dates = [d for d in [min_f, max_f, min_a, max_a] if d is not None]
    if not dates:
        return None, None
        
    start_date = min(dates)
    # End date is the last day of the month of max(dates)
    end_date_start_month = max(dates)
    end_date = (end_date_start_month + pd.offsets.MonthEnd(0)).date()
    
    return start_date, end_date
