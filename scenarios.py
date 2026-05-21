from models import Cenario, Fabrica, Armazem, Rota, PrevisaoFabrica, PrevisaoArmazem
from sqlalchemy.orm import Session

def clone_baseline_to_scenario(session: Session, scenario_name: str):
    # 1. Criar o Cenário
    new_scenario = Cenario(nome=scenario_name)
    session.add(new_scenario)
    session.commit()
    
    scenario_id = new_scenario.id
    
    # Mapas para manter integridade referencial (ID Antigo -> ID Novo)
    fabrica_map = {}
    armazem_map = {}
    
    # 2. Clonar Fábricas
    baseline_fabricas = session.query(Fabrica).filter(Fabrica.cenario_id == None).all()
    for f in baseline_fabricas:
        new_f = Fabrica(
            cenario_id=scenario_id,
            nome=f.nome,
            capacidade_estatica=f.capacidade_estatica,
            capacidade_esmagamento_diaria=f.capacidade_esmagamento_diaria,
            capacidade_recebimento_diaria=f.capacidade_recebimento_diaria,
            limite_caminhoes=f.limite_caminhoes,
            carga_media_caminhao=f.carga_media_caminhao,
            estoque_inicial=f.estoque_inicial
        )
        session.add(new_f)
        session.flush() # Para gerar o ID novo
        fabrica_map[f.id] = new_f.id
        
    # 3. Clonar Armazéns
    baseline_armazens = session.query(Armazem).filter(Armazem.cenario_id == None).all()
    for a in baseline_armazens:
        new_a = Armazem(
            cenario_id=scenario_id,
            nome=a.nome,
            capacidade_estatica=a.capacidade_estatica,
            capacidade_expedicao_diaria=a.capacidade_expedicao_diaria,
            estoque_inicial=a.estoque_inicial
        )
        session.add(new_a)
        session.flush()
        armazem_map[a.id] = new_a.id
        
    # 4. Clonar Rotas
    baseline_rotas = session.query(Rota).filter(Rota.cenario_id == None).all()
    for r in baseline_rotas:
        if r.armazem_id in armazem_map and r.fabrica_id in fabrica_map:
            new_r = Rota(
                cenario_id=scenario_id,
                armazem_id=armazem_map[r.armazem_id],
                fabrica_id=fabrica_map[r.fabrica_id],
                distancia_km=r.distancia_km,
                custo_frete_ton=r.custo_frete_ton
            )
            session.add(new_r)
            
    # 5. Clonar Previsões de Fábrica
    for old_id, new_id in fabrica_map.items():
        preds = session.query(PrevisaoFabrica).filter_by(fabrica_id=old_id).all()
        for p in preds:
            new_p = PrevisaoFabrica(
                fabrica_id=new_id,
                mes_referencia=p.mes_referencia,
                recebimento_produtor=p.recebimento_produtor,
                vendas=p.vendas,
                eh_safra=p.eh_safra
            )
            session.add(new_p)
            
    # 6. Clonar Previsões de Armazém
    for old_id, new_id in armazem_map.items():
        preds = session.query(PrevisaoArmazem).filter_by(armazem_id=old_id).all()
        for p in preds:
            new_p = PrevisaoArmazem(
                armazem_id=new_id,
                mes_referencia=p.mes_referencia,
                recebimento_produtor=p.recebimento_produtor,
                vendas=p.vendas,
                eh_safra=p.eh_safra
            )
            session.add(new_p)
            
    session.commit()
    return scenario_id

def delete_scenario(session: Session, scenario_id: int):
    scenario = session.query(Cenario).get(scenario_id)
    if scenario:
        session.delete(scenario)
        session.commit()
        return True
    return False
