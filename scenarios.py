from models import Cenario, Fabrica, Armazem, Rota, PrevisaoFabrica, PrevisaoArmazem, SafraUnidade
from sqlalchemy.orm import Session

def clone_scenario(session: Session, scenario_name: str, source_scenario_id: int):
    """Clona um cenário existente para um novo cenário."""
    # 0. Busca o Cenário de Origem
    source_scenario = session.get(Cenario, source_scenario_id)
    if not source_scenario:
        raise Exception(f"Cenário de origem ID {source_scenario_id} não encontrado.")
    
    # 1. Criar o Novo Cenário
    new_scenario = Cenario(nome=scenario_name, is_oficial=False)
    session.add(new_scenario)
    session.commit()
    
    new_id = new_scenario.id
    
    # Mapas para manter integridade referencial (ID Antigo -> ID Novo)
    fabrica_map = {}
    armazem_map = {}
    
    # 2. Clonar Fábricas
    source_fabricas = session.query(Fabrica).filter_by(cenario_id=source_scenario_id).all()
    for f in source_fabricas:
        new_f = Fabrica(
            cenario_id=new_id,
            nome=f.nome,
            capacidade_estatica=f.capacidade_estatica,
            capacidade_esmagamento_diaria=f.capacidade_esmagamento_diaria,
            capacidade_recebimento_diaria=f.capacidade_recebimento_diaria,
            limite_caminhoes=f.limite_caminhoes,
            carga_media_caminhao=f.carga_media_caminhao,
            estoque_inicial=f.estoque_inicial
        )
        session.add(new_f)
        session.flush() 
        fabrica_map[f.id] = new_f.id
        
    # 3. Clonar Armazéns
    source_armazens = session.query(Armazem).filter_by(cenario_id=source_scenario_id).all()
    for a in source_armazens:
        new_a = Armazem(
            cenario_id=new_id,
            nome=a.nome,
            capacidade_estatica=a.capacidade_estatica,
            capacidade_expedicao_diaria=a.capacidade_expedicao_diaria,
            estoque_inicial=a.estoque_inicial
        )
        session.add(new_a)
        session.flush()
        armazem_map[a.id] = new_a.id
        
    # 4. Clonar Rotas
    source_rotas = session.query(Rota).filter_by(cenario_id=source_scenario_id).all()
    for r in source_rotas:
        if r.armazem_id in armazem_map and r.fabrica_id in fabrica_map:
            new_r = Rota(
                cenario_id=new_id,
                armazem_id=armazem_map[r.armazem_id],
                fabrica_id=fabrica_map[r.fabrica_id],
                distancia_km=r.distancia_km,
                custo_frete_ton=r.custo_frete_ton,
                custo_frete_entressafra=r.custo_frete_entressafra
            )
            session.add(new_r)
            
    # 5. Clonar Previsões
    for old_id, n_id in fabrica_map.items():
        preds = session.query(PrevisaoFabrica).filter_by(fabrica_id=old_id).all()
        for p in preds:
            session.add(PrevisaoFabrica(
                fabrica_id=n_id,
                mes_referencia=p.mes_referencia,
                recebimento_produtor=p.recebimento_produtor,
                vendas=p.vendas
            ))
            
    for old_id, n_id in armazem_map.items():
        preds = session.query(PrevisaoArmazem).filter_by(armazem_id=old_id).all()
        for p in preds:
            session.add(PrevisaoArmazem(
                armazem_id=n_id,
                mes_referencia=p.mes_referencia,
                recebimento_produtor=p.recebimento_produtor,
                vendas=p.vendas
            ))

    # 6. Clonar Datas de Safra
    source_safras = session.query(SafraUnidade).filter_by(cenario_id=source_scenario_id).all()
    for s_unit in source_safras:
        target_ent_id = fabrica_map.get(s_unit.entidade_id) if s_unit.entidade_tipo == 'Fábrica' else armazem_map.get(s_unit.entidade_id)
        if target_ent_id:
            session.add(SafraUnidade(
                cenario_id=new_id,
                entidade_tipo=s_unit.entidade_tipo,
                entidade_id=target_ent_id,
                data_inicio=s_unit.data_inicio,
                data_fim=s_unit.data_fim
            ))
            
    session.commit()
    return new_id

def clone_baseline_to_scenario(session: Session, scenario_name: str):
    """Mantido para compatibilidade, clona o oficial."""
    oficial = session.query(Cenario).filter_by(is_oficial=True).first()
    if not oficial: raise Exception("Oficial não encontrado.")
    return clone_scenario(session, scenario_name, oficial.id)


def delete_scenario(session: Session, scenario_id: int):
    scenario = session.get(Cenario, scenario_id)
    if scenario:
        session.delete(scenario)
        session.commit()
        return True
    return False
