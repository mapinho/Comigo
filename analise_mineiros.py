import pandas as pd
from data_loader import init_db
from models import Cenario, Armazem, Fabrica, MovimentacaoDiaria, ResumoMensalFabrica

session = init_db()

# 1. Identificar Cenário Oficial e Entidades
oficial = session.query(Cenario).filter_by(is_oficial=True).first()
if not oficial:
    print("Cenário Oficial não encontrado.")
    exit()

mineiros = session.query(Armazem).filter(Armazem.nome == 'MINEIROS', Armazem.cenario_id == oficial.id).first()
complexo = session.query(Fabrica).filter(Fabrica.nome == 'COMPL. INDUSTRIAL', Fabrica.cenario_id == oficial.id).first()
palmeiras = session.query(Fabrica).filter(Fabrica.nome == 'PALMEIRAS', Fabrica.cenario_id == oficial.id).first()

sc_vendas = session.query(Cenario).filter(Cenario.nome.ilike('%Vendas%'), Cenario.is_oficial == False).first()

print(f"Relatório de Análise: Armazém MINEIROS")
print(f"ID MINEIROS: {mineiros.id}")
print(f"ID COMPLEXO: {complexo.id}, ID PALMEIRAS: {palmeiras.id}")

if sc_vendas:
    print(f"Cenário de Vendas encontrado: ID {sc_vendas.id}")
    
    # Pegar IDs das entidades clonadas no cenário de Vendas
    mineiros_v = session.query(Armazem).filter(Armazem.nome == 'MINEIROS', Armazem.cenario_id == sc_vendas.id).first()
    complexo_v = session.query(Fabrica).filter(Fabrica.nome == 'COMPL. INDUSTRIAL', Fabrica.cenario_id == sc_vendas.id).first()
    palmeiras_v = session.query(Fabrica).filter(Fabrica.nome == 'PALMEIRAS', Fabrica.cenario_id == sc_vendas.id).first()

    # 2. Analisar Movimentações no Planejado (Cenário Oficial)
    movs_p = session.query(MovimentacaoDiaria).filter(
        MovimentacaoDiaria.armazem_id == mineiros.id, 
        MovimentacaoDiaria.cenario_id == oficial.id
    ).all()
    
    df_p = pd.DataFrame([{
        'Data': m.data,
        'Destino': 'Complexo' if m.fabrica_id == complexo.id else 'Palmeiras',
        'Volume': m.quantidade_ton
    } for m in movs_p])
    
    # 3. Analisar Movimentações no Cenário Vendas
    movs_v = session.query(MovimentacaoDiaria).filter(
        MovimentacaoDiaria.armazem_id == mineiros_v.id, 
        MovimentacaoDiaria.cenario_id == sc_vendas.id
    ).all()
    
    df_v = pd.DataFrame([{
        'Data': m.data,
        'Destino': 'Complexo' if m.fabrica_id == complexo_v.id else 'Palmeiras',
        'Volume': m.quantidade_ton
    } for m in movs_v])

    print("\n--- RESUMO PLANEJADO (OFFICIAL) ---")
    if not df_p.empty:
        print(df_p.groupby('Destino')['Volume'].agg(['sum', 'count']))
    else:
        print("Sem movimentações em Mineiros no Planejado.")

    print("\n--- RESUMO CENÁRIO VENDAS ---")
    if not df_v.empty:
        print(df_v.groupby('Destino')['Volume'].agg(['sum', 'count']))
        
        # Encontrar a primeira data que Mineiros enviou para Palmeiras
        first_p = df_v[df_v['Destino'] == 'Palmeiras'].sort_values('Data').head(1)
        if not first_p.empty:
            data_obs = first_p['Data'].values[0]
            mes_obs = pd.to_datetime(data_obs).strftime('%Y-%m')
            print(f"\nPrimeiro envio para Palmeiras detectado em: {data_obs}")
            
            # Verificar situação das fábricas nesse mês
            rf_complexo = session.query(ResumoMensalFabrica).filter_by(cenario_id=sc_vendas.id, fabrica_id=complexo_v.id, mes=mes_obs).first()
            rf_palmeiras = session.query(ResumoMensalFabrica).filter_by(cenario_id=sc_vendas.id, fabrica_id=palmeiras_v.id, mes=mes_obs).first()
            
            print(f"\nSituação em {mes_obs} (Fim do Mês):")
            if rf_complexo:
                status_c = "LOTADO" if rf_complexo.saldo_estoque >= rf_complexo.capacidade_estatica - 100 else "Com Espaço"
                print(f"  Complexo Industrial: Estoque {rf_complexo.saldo_estoque:,.0f} / Cap {rf_complexo.capacidade_estatica:,.0f} -> STATUS: {status_c}")
            if rf_palmeiras:
                status_p = "CRÍTICO" if rf_palmeiras.saldo_estoque < 1000 else "Ok"
                print(f"  Palmeiras: Estoque {rf_palmeiras.saldo_estoque:,.0f} / Cap {rf_palmeiras.capacidade_estatica:,.0f} -> STATUS: {status_p}")
    else:
        print("Sem movimentações em Mineiros no cenário Vendas.")
else:
    print("Cenário com nome 'Vendas' não encontrado no banco.")

session.close()
