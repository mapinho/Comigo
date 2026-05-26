import streamlit as st
import pandas as pd
import plotly.express as px
from data_loader import init_db, load_factories, load_warehouses, load_routes, load_previsoes, clear_database
from calculations import simular_periodo, obter_range_previsoes
from models import Fabrica, Armazem, Rota, PrevisaoFabrica, PrevisaoArmazem, MovimentacaoDiaria, ResumoMensalFabrica, ResumoMensalArmazem, Cenario, SafraUnidade
import scenarios
import datetime
from sqlalchemy import func
from utils import export_to_excel, format_dataframe, format_volume, format_valor, get_model_column_config, build_df_from_model

st.set_page_config(page_title="Comigo - Transbordo de Soja", layout="wide")

def main():
    try:
        st.sidebar.image("logo.svg", use_container_width=True)
    except Exception:
        pass

    st.title("Sistema de Planejamento de Transbordo - Comigo")
    
    menu = ["Dashboard", "Cenários de Simulação", "Carga de Dados", "Visualizar Dados", "Otimização"]
    choice = st.sidebar.selectbox("Menu", menu)
    
    session = init_db()
    
    if choice == "Dashboard":
        st.subheader("Dashboard de Movimentações")
        
        all_cenarios = session.query(Cenario).all()
        cenario_options = {None: "Oficial (Planejado)"}
        for c in all_cenarios:
            cenario_options[c.id] = f"Simulação: {c.nome}"
            
        selected_cenario_id = st.sidebar.selectbox("Selecionar Cenário", options=list(cenario_options.keys()), format_func=lambda x: cenario_options[x])

        if 'dash_sid' not in st.session_state or st.session_state.dash_sid != selected_cenario_id:
            st.session_state.dash_sid = selected_cenario_id
            min_d = session.query(func.min(MovimentacaoDiaria.data)).filter(MovimentacaoDiaria.cenario_id == selected_cenario_id).scalar()
            max_d = session.query(func.max(MovimentacaoDiaria.data)).filter(MovimentacaoDiaria.cenario_id == selected_cenario_id).scalar()
            
            if min_d and max_d:
                st.session_state.dash_data_ini = min_d
                st.session_state.dash_data_fim = max_d
            else:
                st.session_state.dash_data_ini = datetime.date.today() - datetime.timedelta(days=30)
                st.session_state.dash_data_fim = datetime.date.today() + datetime.timedelta(days=30)
            
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            data_ini = st.date_input("Data Início", value=st.session_state.dash_data_ini, key='input_data_ini')
        with col2:
            data_fim = st.date_input("Data Fim", value=st.session_state.dash_data_fim, key='input_data_fim')
        with col3:
            st.write("") 
            st.write("")
            if st.button("Resetar Filtros", use_container_width=True):
                if 'dash_sid' in st.session_state: del st.session_state.dash_sid
                st.rerun()

        st.session_state.dash_data_ini = data_ini
        st.session_state.dash_data_fim = data_fim
            
        try:
            movs = session.query(MovimentacaoDiaria).filter(
                MovimentacaoDiaria.data.between(data_ini, data_fim),
                MovimentacaoDiaria.cenario_id == selected_cenario_id
            ).all()
            
            if movs:
                df_movs = pd.DataFrame([{
                    'Data': m.data,
                    'Origem': session.get(Armazem, m.armazem_id).nome,
                    'Destino': session.get(Fabrica, m.fabrica_id).nome,
                    'Quantidade (Ton)': m.quantidade_ton,
                    'Quantidade (Sc)': m.quantidade_ton * 1000 / 60,
                    'Custo Total (R$)': m.custo_total
                } for m in movs])
                
                df_movs['Mês'] = pd.to_datetime(df_movs['Data']).dt.strftime('%Y-%m')
                visao = st.radio("Selecione a Visão", ["Diária", "Mensal", "Resumo Fábricas", "Resumo Armazéns"], horizontal=True)
                
                if visao in ["Diária", "Mensal"]:
                    col_f1, col_f2 = st.columns(2)
                    with col_f1:
                        origens = st.multiselect("Filtrar por Origem", options=df_movs['Origem'].unique(), default=[])
                    with col_f2:
                        destinos = st.multiselect("Filtrar por Destino", options=df_movs['Destino'].unique(), default=[])
                    if origens: df_movs = df_movs[df_movs['Origem'].isin(origens)]
                    if destinos: df_movs = df_movs[df_movs['Destino'].isin(destinos)]
                
                if visao == "Diária":
                    st.dataframe(format_dataframe(df_movs), hide_index=True)
                    st.download_button(label="Exportar Visão Diária para Excel", data=export_to_excel(df_movs, "movimentacoes_diarias"), file_name="movimentacoes_diarias.xlsx")
                    fig = px.bar(df_movs, x='Data', y='Quantidade (Ton)', color='Destino', title="Volume por Destino (Diário)")
                    st.plotly_chart(fig, use_container_width=True)
                
                elif visao == "Mensal":
                    df_mes_total = df_movs.groupby('Mês').agg({'Quantidade (Ton)': 'sum', 'Quantidade (Sc)': 'sum', 'Custo Total (R$)': 'sum'}).reset_index()
                    df_mes_rotas = df_movs.groupby(['Mês', 'Origem', 'Destino']).agg({'Quantidade (Ton)': 'sum', 'Quantidade (Sc)': 'sum', 'Custo Total (R$)': 'sum'}).reset_index()
                    
                    baseline_cost = None
                    baseline_vol = None
                    if selected_cenario_id is not None:
                        base_movs = session.query(MovimentacaoDiaria).filter(
                            MovimentacaoDiaria.data.between(data_ini, data_fim),
                            MovimentacaoDiaria.cenario_id == None
                        ).all()
                        if base_movs:
                            baseline_cost = sum(m.custo_total for m in base_movs)
                            baseline_vol = sum(m.quantidade_ton for m in base_movs)

                    col_m1, col_m2, col_m3 = st.columns([2, 1, 1])
                    with col_m1:
                        st.write("**Resumo Total por Mês**")
                        st.dataframe(format_dataframe(df_mes_total), hide_index=True)
                        st.download_button(label="Exportar Resumo Mensal para Excel", data=export_to_excel(df_mes_total, "resumo_mensal"), file_name="resumo_mensal.xlsx")
                    
                    total_vol = df_mes_total['Quantidade (Ton)'].sum()
                    total_cost = df_mes_total['Custo Total (R$)'].sum()
                    
                    with col_m2:
                        st.write("**Indicadores Tonelada**")
                        delta_vol = f"{((total_vol/baseline_vol)-1)*100:.1f}% vs Planejado" if baseline_vol else None
                        st.metric("Total Movimentado (Ton)", format_volume(total_vol), delta=delta_vol)
                        delta_cost = f"{((total_cost/baseline_cost)-1)*100:.1f}% vs Planejado" if baseline_cost else None
                        st.metric("Custo Total (R$)", format_valor(total_cost), delta=delta_cost, delta_color="inverse")
                    
                    with col_m3:
                        st.write("**Indicadores Sacas**")
                        st.metric("Total Movimentado (Sc)", format_volume(df_mes_total['Quantidade (Sc)'].sum()))

                    st.write("**Detalhamento Mensal por Rota**")
                    st.dataframe(format_dataframe(df_mes_rotas), hide_index=True)
                    st.download_button(label="Exportar Detalhamento Mensal para Excel", data=export_to_excel(df_mes_rotas, "detalhamento_mensal"), file_name="detalhamento_mensal.xlsx")
                    
                elif visao == "Resumo Fábricas":
                    resumos_fab = session.query(ResumoMensalFabrica).filter_by(cenario_id=selected_cenario_id).all()
                    if resumos_fab:
                        df_rf = build_df_from_model(resumos_fab, ResumoMensalFabrica)
                        # Adiciona nomes humanos (build_df_from_model pegou IDs e campos técnicos)
                        df_rf['Fábrica'] = [session.get(Fabrica, r.fabrica_id).nome for r in resumos_fab]
                        df_rf['Mês'] = [r.mes for r in resumos_fab]
                        st.dataframe(format_dataframe(df_rf), hide_index=True)
                        st.download_button(label="Exportar Resumo Fábricas para Excel", data=export_to_excel(df_rf, "resumo_fabricas"), file_name="resumo_fabricas.xlsx")
                
                elif visao == "Resumo Armazéns":
                    resumos_arm = session.query(ResumoMensalArmazem).filter_by(cenario_id=selected_cenario_id).all()
                    if resumos_arm:
                        df_ra = build_df_from_model(resumos_arm, ResumoMensalArmazem)
                        df_ra['Armazém'] = [session.get(Armazem, r.armazem_id).nome for r in resumos_arm]
                        df_ra['Mês'] = [r.mes for r in resumos_arm]
                        st.dataframe(format_dataframe(df_ra), hide_index=True)
                        st.download_button(label="Exportar Resumo Armazéns para Excel", data=export_to_excel(df_ra, "resumo_armazens"), file_name="resumo_armazens.xlsx")
            else:
                st.info("Nenhuma movimentação encontrada.")
        except Exception as e:
            st.error(f"Erro ao carregar dashboard: {e}")

    elif choice == "Cenários de Simulação":
        st.subheader("Gerenciamento de Cenários de Simulação")
        
        with st.expander("Criar Novo Cenário"):
            new_name = st.text_input("Nome do Cenário (ex: Safra Recorde 2026)")
            if st.button("Criar Cenário (Clonar Planejado)"):
                if new_name:
                    with st.spinner("Clonando dados..."):
                        try:
                            scenarios.clone_baseline_to_scenario(session, new_name)
                            st.success(f"Cenário '{new_name}' criado com sucesso!")
                            if 'edit_sid' in st.session_state: del st.session_state.edit_sid
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao criar cenário: {e}")
                else: st.warning("Informe um nome.")

        cenarios = session.query(Cenario).all()
        if cenarios:
            st.write("---")
            sel_cen_id = st.selectbox("Escolher Cenário para Editar/Otimizar", options=[c.id for c in cenarios], format_func=lambda x: session.get(Cenario, x).nome)
            
            if 'edit_sid' not in st.session_state or st.session_state.edit_sid != sel_cen_id:
                st.session_state.edit_sid = sel_cen_id
                st.session_state.df_fabs_edit = build_df_from_model(session.query(Fabrica).filter_by(cenario_id=sel_cen_id).all(), Fabrica)
                st.session_state.df_arms_edit = build_df_from_model(session.query(Armazem).filter_by(cenario_id=sel_cen_id).all(), Armazem)
                st.session_state.df_rots_edit = build_df_from_model(session.query(Rota).filter_by(cenario_id=sel_cen_id).all(), Rota)
                st.session_state.df_pfabs_edit = build_df_from_model(session.query(PrevisaoFabrica).join(Fabrica).filter(Fabrica.cenario_id == sel_cen_id).all(), PrevisaoFabrica)
                st.session_state.df_parms_edit = build_df_from_model(session.query(PrevisaoArmazem).join(Armazem).filter(Armazem.cenario_id == sel_cen_id).all(), PrevisaoArmazem)
                st.session_state.df_safras_edit = build_df_from_model(session.query(SafraUnidade).filter_by(cenario_id=sel_cen_id).all(), SafraUnidade)

            tab_fab, tab_arm, tab_rot, tab_prev, tab_safra, tab_opt = st.tabs(["Fábricas", "Armazéns", "Rotas", "Previsões", "Datas de Safra", "Otimizar Cenário"])
            
            with tab_fab:
                st.session_state.df_fabs_edit = st.data_editor(st.session_state.df_fabs_edit, key="editor_fabs", hide_index=True, column_config=get_model_column_config(Fabrica))
                if st.button("Salvar Alterações Fábricas"):
                    for _, row in st.session_state.df_fabs_edit.iterrows():
                        f = session.get(Fabrica, int(row['id']))
                        if f:
                            f.capacidade_estatica = float(row['Capacidade Estática (Ton)'])
                            f.capacidade_esmagamento_diaria = float(row['Esmagamento Diário (Ton)'])
                            f.capacidade_recebimento_diaria = float(row['Recebimento Diário (Ton)'])
                    session.commit()
                    st.success("Salvo.")

            with tab_arm:
                st.session_state.df_arms_edit = st.data_editor(st.session_state.df_arms_edit, key="editor_arms", hide_index=True, column_config=get_model_column_config(Armazem))
                if st.button("Salvar Alterações Armazéns"):
                    for _, row in st.session_state.df_arms_edit.iterrows():
                        a = session.get(Armazem, int(row['id']))
                        if a:
                            a.capacidade_estatica = float(row['Capacidade Estática (Ton)'])
                            a.capacidade_expedicao_diaria = float(row['Expedição Diária (Ton)'])
                    session.commit()
                    st.success("Salvo.")

            with tab_rot:
                st.session_state.df_rots_edit = st.data_editor(st.session_state.df_rots_edit, key="editor_rots", hide_index=True, column_config=get_model_column_config(Rota))
                if st.button("Salvar Alterações Rotas"):
                    for _, row in st.session_state.df_rots_edit.iterrows():
                        r = session.get(Rota, int(row['id']))
                        if r:
                            r.distancia_km = float(row['Distância (km)'])
                            r.custo_frete_ton = float(row['Custo Safra (R$/Ton)'])
                            r.custo_frete_entressafra = float(row['Custo Entressafra (R$/Ton)'])
                    session.commit()
                    st.success("Salvo.")

            with tab_prev:
                st.write("**Fábricas**")
                st.session_state.df_pfabs_edit = st.data_editor(st.session_state.df_pfabs_edit, key="epf", hide_index=True, column_config=get_model_column_config(PrevisaoFabrica))
                st.write("**Armazéns**")
                st.session_state.df_parms_edit = st.data_editor(st.session_state.df_parms_edit, key="epa", hide_index=True, column_config=get_model_column_config(PrevisaoArmazem))
                if st.button("Salvar Previsões"):
                    for _, row in st.session_state.df_pfabs_edit.iterrows():
                        p = session.get(PrevisaoFabrica, int(row['id']))
                        if p:
                            p.recebimento_produtor = float(row['Recebimento Produtor (Ton)'])
                            p.vendas = float(row['Vendas (Ton)'])
                    for _, row in st.session_state.df_parms_edit.iterrows():
                        p = session.get(PrevisaoArmazem, int(row['id']))
                        if p:
                            p.recebimento_produtor = float(row['Recebimento Produtor (Ton)'])
                            p.vendas = float(row['Vendas (Ton)'])
                    session.commit()
                    st.success("Salvo.")

            with tab_safra:
                df = st.session_state.df_safras_edit
                # Resolve os nomes das unidades para exibição
                unidades = []
                for _, row in df.iterrows():
                    s_obj = session.get(SafraUnidade, int(row['id']))
                    if s_obj.entidade_tipo == 'Armazém':
                        name = session.get(Armazem, s_obj.entidade_id).nome
                    else:
                        name = session.get(Fabrica, s_obj.entidade_id).nome
                    unidades.append(name)
                df['Unidade'] = unidades

                st.session_state.df_safras_edit = st.data_editor(
                    df, 
                    key="esaf", 
                    hide_index=True, 
                    disabled=["id", "Tipo", "Unidade"],
                    column_config=get_model_column_config(SafraUnidade)
                )
                if st.button("Salvar Datas"):
                    for _, row in st.session_state.df_safras_edit.iterrows():
                        s = session.get(SafraUnidade, int(row['id']))
                        if s:
                            s.data_inicio = row['Início']
                            s.data_fim = row['Fim']
                    session.commit()
                    st.success("Salvo.")

            with tab_opt:
                estrategia = st.selectbox("Estratégia", ["Econômico", "Expedição", "Segurança"], key="strat_cen")
                d_ini, d_fim = obter_range_previsoes(session, cenario_id=sel_cen_id)
                if d_ini and d_fim:
                    if st.button("Rodar Otimização Cenário", type="primary"):
                        simular_periodo(session, d_ini, d_fim, cenario_id=sel_cen_id, estrategia=estrategia)
                        st.success("Concluído.")

    elif choice == "Visualizar Dados":
        st.subheader("Edição do Planejado (Oficial)")
        tabela = st.selectbox("Selecione a Tabela", ["Fábricas", "Armazéns", "Rotas", "Previsões Fábrica", "Previsões Armazém", "Datas de Safra"])
        
        model_map = {"Fábricas": Fabrica, "Armazéns": Armazem, "Rotas": Rota, "Previsões Fábrica": PrevisaoFabrica, "Previsões Armazém": PrevisaoArmazem, "Datas de Safra": SafraUnidade}
        curr_model = model_map[tabela]
        
        if tabela in ["Fábricas", "Armazéns", "Rotas", "Datas de Safra"]:
            dados = session.query(curr_model).filter_by(cenario_id=None).all()
        elif tabela == "Previsões Fábrica":
            dados = session.query(PrevisaoFabrica).join(Fabrica).filter(Fabrica.cenario_id == None).all()
        else:
            dados = session.query(PrevisaoArmazem).join(Armazem).filter(Armazem.cenario_id == None).all()
            
        df = build_df_from_model(dados, curr_model)

        # Resolve nomes para Datas de Safra no Oficial
        if tabela == "Datas de Safra":
            unidades = []
            for _, row in df.iterrows():
                s_obj = session.get(SafraUnidade, int(row['id']))
                if s_obj.entidade_tipo == 'Armazém':
                    name = session.get(Armazem, s_obj.entidade_id).nome
                else:
                    name = session.get(Fabrica, s_obj.entidade_id).nome
                unidades.append(name)
            df['Unidade'] = unidades

        edited_df = st.data_editor(df, hide_index=True, key=f"vis_{tabela}", disabled=["id", "Fábrica", "Armazém", "Mês", "Tipo", "Unidade"], column_config=get_model_column_config(curr_model))
        
        if st.button(f"Salvar {tabela}"):
            for _, row in edited_df.iterrows():
                obj = session.get(curr_model, int(row['id']))
                if obj:
                    for col in edited_df.columns:
                        if col == 'id' or 'Fábrica' in col or 'Armazém' in col or 'Mês' in col or 'Tipo' in col: continue
                        # Busca o nome real da coluna no SQLAlchemy através do label
                        mapper = inspect(curr_model)
                        for column in mapper.attrs:
                            sa_col = getattr(curr_model, column.key).property.columns[0]
                            if sa_col.info.get('label') == col:
                                setattr(obj, column.key, row[col])
            session.commit()
            st.success("Salvo com sucesso!")

    elif choice == "Otimização":
        st.subheader("Executar Otimização Oficial")
        estrategia = st.selectbox("Estratégia", ["Econômico", "Expedição", "Segurança"], key="strat_oficial")
        d_ini, d_fim = obter_range_previsoes(session, cenario_id=None)
        if st.button("Rodar Otimização Completa", type="primary"):
            simular_periodo(session, d_ini, d_fim, cenario_id=None, estrategia=estrategia)
            st.success("Concluído.")

    session.close()

if __name__ == "__main__":
    main()
