import streamlit as st
import pandas as pd
import plotly.express as px
from data_loader import init_db, load_factories, load_warehouses, load_routes, load_previsoes, clear_database
from calculations import simular_periodo, obter_range_previsoes
from models import Fabrica, Armazem, Rota, PrevisaoFabrica, PrevisaoArmazem, MovimentacaoDiaria, ResumoMensalFabrica, ResumoMensalArmazem, Cenario, SafraUnidade
import scenarios
import datetime
from sqlalchemy import func, inspect
from utils import export_to_excel, format_dataframe, format_volume, format_valor, get_model_column_config, build_df_from_model, append_totals_row

st.set_page_config(page_title="Comigo - Transbordo de Soja", layout="wide")

def main():
    try:
        st.sidebar.image("logo.svg", width='stretch')
    except Exception:
        pass

    st.title("Sistema de Planejamento de Transbordo - Comigo")
    
    menu = ["Dashboard", "Dados & Cenários", "Carga de Dados", "Otimização"]
    choice = st.sidebar.selectbox("Menu", menu)
    
    session = init_db()
    
    # Busca todos os cenários disponíveis
    all_cenarios = session.query(Cenario).order_by(Cenario.is_oficial.desc(), Cenario.nome).all()
    cenario_options = {c.id: f"{'⭐ ' if c.is_oficial else ''}{c.nome}" for c in all_cenarios}
    
    if choice == "Dashboard":
        st.subheader("Dashboard de Movimentações")
        
        col_s1, col_s2 = st.sidebar.columns(2)
        with col_s1:
            selected_cenario_id = st.selectbox("Cenário Principal", options=list(cenario_options.keys()), format_func=lambda x: cenario_options[x], key='dash_main')
        with col_s2:
            comp_cenario_id = st.selectbox("Cenário Comparação", options=list(cenario_options.keys()), format_func=lambda x: cenario_options[x], index=0 if len(all_cenarios) > 0 else None, key='dash_comp')

        # Lógica para definir o range de datas padrão do Dashboard
        # Dispara quando o cenário muda ou quando os filtros são resetados
        if 'dash_sid' not in st.session_state or st.session_state.dash_sid != selected_cenario_id:
            st.session_state.dash_sid = selected_cenario_id
            
            # Busca as datas reais das movimentações no banco para este cenário
            min_d = session.query(func.min(MovimentacaoDiaria.data)).filter(MovimentacaoDiaria.cenario_id == selected_cenario_id).scalar()
            max_d = session.query(func.max(MovimentacaoDiaria.data)).filter(MovimentacaoDiaria.cenario_id == selected_cenario_id).scalar()
            
            if min_d and max_d:
                st.session_state.input_data_ini = min_d
                st.session_state.input_data_fim = max_d
            else:
                st.session_state.input_data_ini = datetime.date.today() - datetime.timedelta(days=30)
                st.session_state.input_data_fim = datetime.date.today() + datetime.timedelta(days=30)
            
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            data_ini = st.date_input("Data Início", key='input_data_ini')
        with col2:
            data_fim = st.date_input("Data Fim", key='input_data_fim')
        with col3:
            st.write("") 
            st.write("")
            if st.button("Resetar Filtros", width='stretch'):
                # Simplesmente remove a chave de controle para forçar o recálculo do range de datas
                if 'dash_sid' in st.session_state: del st.session_state['dash_sid']
                st.rerun()
            
        try:
            movs = session.query(MovimentacaoDiaria).filter(
                MovimentacaoDiaria.data.between(data_ini, data_fim),
                MovimentacaoDiaria.cenario_id == selected_cenario_id
            ).all()
            
            if movs:
                df_movs = pd.DataFrame([{
                    'Data': m.data,
                    'Origem': session.get(Armazem, m.armazem_id).nome if session.get(Armazem, m.armazem_id) else "N/A",
                    'Destino': session.get(Fabrica, m.fabrica_id).nome if session.get(Fabrica, m.fabrica_id) else "N/A",
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
                    st.dataframe(format_dataframe(append_totals_row(df_movs)), hide_index=True, width='stretch')
                    st.download_button(label="Exportar Visão Diária para Excel", data=export_to_excel(df_movs), file_name="movimentacoes_diarias.xlsx")
                    fig = px.bar(df_movs, x='Data', y='Quantidade (Ton)', color='Destino', title="Volume por Destino (Diário)")
                    st.plotly_chart(fig, width='stretch')
                
                elif visao == "Mensal":
                    df_mes_total = df_movs.groupby('Mês').agg({'Quantidade (Ton)': 'sum', 'Quantidade (Sc)': 'sum', 'Custo Total (R$)': 'sum'}).reset_index()
                    df_mes_rotas = df_movs.groupby(['Mês', 'Origem', 'Destino']).agg({'Quantidade (Ton)': 'sum', 'Quantidade (Sc)': 'sum', 'Custo Total (R$)': 'sum'}).reset_index()
                    
                    baseline_cost = None
                    baseline_vol = None
                    if comp_cenario_id is not None:
                        comp_movs = session.query(MovimentacaoDiaria).filter(
                            MovimentacaoDiaria.data.between(data_ini, data_fim),
                            MovimentacaoDiaria.cenario_id == comp_cenario_id
                        ).all()
                        if comp_movs:
                            baseline_cost = sum(m.custo_total for m in comp_movs)
                            baseline_vol = sum(m.quantidade_ton for m in comp_movs)

                    col_m1, col_m2, col_m3 = st.columns([2, 1, 1])
                    with col_m1:
                        st.write("**Resumo Total por Mês**")
                        st.dataframe(format_dataframe(append_totals_row(df_mes_total)), hide_index=True, width='stretch')
                        st.download_button(label="Exportar Resumo Mensal para Excel", data=export_to_excel(df_mes_total), file_name="resumo_mensal.xlsx")
                    
                    total_vol = df_mes_total['Quantidade (Ton)'].sum()
                    total_cost = df_mes_total['Custo Total (R$)'].sum()
                    
                    with col_m2:
                        st.write("**Indicadores Tonelada**")
                        delta_vol = f"{((total_vol/baseline_vol)-1)*100:.1f}% vs Comparação" if (baseline_vol and baseline_vol > 0) else None
                        st.metric("Total Movimentado (Ton)", format_volume(total_vol), delta=delta_vol)
                        delta_cost = f"{((total_cost/baseline_cost)-1)*100:.1f}% vs Comparação" if (baseline_cost and baseline_cost > 0) else None
                        st.metric("Custo Total (R$)", format_valor(total_cost), delta=delta_cost, delta_color="inverse")
                    
                    with col_m3:
                        st.write("**Indicadores Sacas**")
                        st.metric("Total Movimentado (Sc)", format_volume(df_mes_total['Quantidade (Sc)'].sum()))

                    st.write("**Detalhamento Mensal por Rota**")
                    st.dataframe(format_dataframe(append_totals_row(df_mes_rotas)), hide_index=True, width='stretch')
                    st.download_button(label="Exportar Detalhamento Mensal para Excel", data=export_to_excel(df_mes_rotas), file_name="detalhamento_mensal.xlsx")
                    
                elif visao == "Resumo Fábricas":
                    resumos_fab = session.query(ResumoMensalFabrica).filter(ResumoMensalFabrica.cenario_id == selected_cenario_id).all()
                    if resumos_fab:
                        df_rf = build_df_from_model(resumos_fab, ResumoMensalFabrica)
                        df_rf['Fábrica'] = [session.get(Fabrica, r.fabrica_id).nome if session.get(Fabrica, r.fabrica_id) else "N/A" for r in resumos_fab]
                        df_rf['Mês'] = [r.mes for r in resumos_fab]
                        # Filtro de Fábricas
                        fabs_sel = st.multiselect("Filtrar por Fábrica", options=sorted(df_rf['Fábrica'].unique()), default=[])
                        if fabs_sel: df_rf = df_rf[df_rf['Fábrica'].isin(fabs_sel)]
                        
                        # Reordenar e limpar colunas
                        cols_rf = ['Mês', 'Fábrica'] + [c for c in df_rf.columns if c not in ['Mês', 'Fábrica', 'id', 'cenario_id', 'fabrica_id']]
                        df_rf = df_rf[cols_rf]
                        st.dataframe(format_dataframe(append_totals_row(df_rf)), hide_index=True, width='stretch')
                        st.download_button(label="Exportar Resumo Fábricas para Excel", data=export_to_excel(df_rf), file_name="resumo_fabricas.xlsx")

                elif visao == "Resumo Armazéns":
                    resumos_arm = session.query(ResumoMensalArmazem).filter(ResumoMensalArmazem.cenario_id == selected_cenario_id).all()
                    if resumos_arm:
                        df_ra = build_df_from_model(resumos_arm, ResumoMensalArmazem)
                        df_ra['Armazém'] = [session.get(Armazem, r.armazem_id).nome if session.get(Armazem, r.armazem_id) else "N/A" for r in resumos_arm]
                        df_ra['Mês'] = [r.mes for r in resumos_arm]
                        # Filtro de Armazéns
                        arms_sel = st.multiselect("Filtrar por Armazém", options=sorted(df_ra['Armazém'].unique()), default=[])
                        if arms_sel: df_ra = df_ra[df_ra['Armazém'].isin(arms_sel)]
                        
                        # Reordenar e limpar colunas
                        cols_ra = ['Mês', 'Armazém'] + [c for c in df_ra.columns if c not in ['Mês', 'Armazém', 'id', 'cenario_id', 'armazem_id']]
                        df_ra = df_ra[cols_ra]
                        st.dataframe(format_dataframe(append_totals_row(df_ra)), hide_index=True, width='stretch')
                        st.download_button(label="Exportar Resumo Armazéns para Excel", data=export_to_excel(df_ra), file_name="resumo_armazens.xlsx")
            else:
                st.info("Nenhuma movimentação encontrada para o cenário selecionado.")
        except Exception as e:
            st.error(f"Erro ao carregar dashboard: {e}")


    elif choice == "Dados & Cenários":
        st.subheader("Gerenciamento de Dados e Cenários")
        
        with st.expander("➕ Criar Novo Cenário de Simulação"):
            new_name = st.text_input("Nome do Novo Cenário (ex: Safra Recorde 2026)")
            source_id = st.selectbox("Clonar dados de qual cenário?", options=list(cenario_options.keys()), format_func=lambda x: cenario_options[x], key='clone_source_sel')
            
            if st.button("Criar Cenário"):
                if new_name:
                    with st.spinner("Clonando dados..."):
                        try:
                            scenarios.clone_scenario(session, new_name, source_id)
                            st.success(f"Cenário '{new_name}' criado com sucesso a partir de '{cenario_options[source_id]}'.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao criar cenário: {e}")
                else: st.warning("Informe um nome para o novo cenário.")

        if all_cenarios:
            st.write("---")
            sel_cen_id = st.selectbox("Escolher Cenário para Editar/Otimizar", options=list(cenario_options.keys()), format_func=lambda x: cenario_options[x], key='edit_cen_sel')
            
            if 'edit_sid' not in st.session_state or st.session_state.edit_sid != sel_cen_id:
                st.session_state.edit_sid = sel_cen_id
                
                # Fábricas
                fabs_list = session.query(Fabrica).filter_by(cenario_id=sel_cen_id).all()
                df_fabs = build_df_from_model(fabs_list, Fabrica)
                if not df_fabs.empty: df_fabs['Fábrica'] = [f.nome for f in fabs_list]
                st.session_state.df_fabs_edit = df_fabs
                
                # Armazéns
                arms_list = session.query(Armazem).filter_by(cenario_id=sel_cen_id).all()
                df_arms = build_df_from_model(arms_list, Armazem)
                if not df_arms.empty: df_arms['Armazém'] = [a.nome for a in arms_list]
                st.session_state.df_arms_edit = df_arms
                
                # Rotas
                rots_list = session.query(Rota).filter_by(cenario_id=sel_cen_id).all()
                df_rots = build_df_from_model(rots_list, Rota)
                if not df_rots.empty:
                    df_rots['Origem'] = [session.get(Armazem, r.armazem_id).nome for r in rots_list]
                    df_rots['Destino'] = [session.get(Fabrica, r.fabrica_id).nome for r in rots_list]
                st.session_state.df_rots_edit = df_rots
                
                # Previsões
                pf_list = session.query(PrevisaoFabrica).join(Fabrica).filter(Fabrica.cenario_id == sel_cen_id).all()
                df_pf = build_df_from_model(pf_list, PrevisaoFabrica)
                if not df_pf.empty: df_pf['Fábrica'] = [session.get(Fabrica, p.fabrica_id).nome for p in pf_list]
                st.session_state.df_pfabs_edit = df_pf
                
                pa_list = session.query(PrevisaoArmazem).join(Armazem).filter(Armazem.cenario_id == sel_cen_id).all()
                df_pa = build_df_from_model(pa_list, PrevisaoArmazem)
                if not df_pa.empty: df_pa['Armazém'] = [session.get(Armazem, p.armazem_id).nome for p in pa_list]
                st.session_state.df_parms_edit = df_pa

                # Safras
                safras_list = session.query(SafraUnidade).filter_by(cenario_id=sel_cen_id).all()
                df_saf = build_df_from_model(safras_list, SafraUnidade)
                if not df_saf.empty:
                    unidades = []
                    for s_obj in safras_list:
                        if s_obj.entidade_tipo == 'Armazém': name = session.get(Armazem, s_obj.entidade_id).nome
                        else: name = session.get(Fabrica, s_obj.entidade_id).nome
                        unidades.append(name)
                    df_saf['Unidade'] = unidades
                st.session_state.df_safras_edit = df_saf


            tab_fab, tab_arm, tab_rot, tab_prev, tab_safra, tab_opt = st.tabs(["Fábricas", "Armazéns", "Rotas", "Previsões", "Datas de Safra", "🚀 Otimizar"])
            
            with tab_fab:
                df_show = format_dataframe(append_totals_row(st.session_state.df_fabs_edit))
                edited = st.data_editor(df_show, key="editor_fabs", hide_index=True, column_config=get_model_column_config(Fabrica), width='stretch')
                if st.button("Salvar Alterações Fábricas"):
                    # Filtra a linha de TOTAL e garante IDs válidos
                    for _, row in edited.iterrows():
                        if str(row.get('Fábrica')).upper() == 'TOTAL' or pd.isna(row.get('id')) or row.get('id') == "":
                            continue
                        f = session.get(Fabrica, int(row['id']))
                        if f:
                            f.capacidade_estatica = float(row['Capacidade Estática (Ton)'])
                            f.capacidade_esmagamento_diaria = float(row['Esmagamento Diário (Ton)'])
                            f.capacidade_recebimento_diaria = float(row['Recebimento Diário (Ton)'])
                    session.commit()
                    st.success("Salvo com sucesso!")

            with tab_arm:
                df_show = format_dataframe(append_totals_row(st.session_state.df_arms_edit))
                edited = st.data_editor(df_show, key="editor_arms", hide_index=True, num_rows="dynamic", column_config=get_model_column_config(Armazem), width='stretch')
                if st.button("Salvar Alterações Armazéns"):
                    for _, row in edited.iterrows():
                        if str(row.get('Armazém')).upper() == 'TOTAL':
                            continue
                        if 'id' in row and pd.notna(row['id']) and row['id'] != "":
                            a = session.get(Armazem, int(row['id']))
                            if a:
                                a.nome = row['Armazém']
                                a.capacidade_estatica = float(row['Capacidade Estática (Ton)'])
                                a.capacidade_expedicao_diaria = float(row['Expedição Diária (Ton)'])
                        elif pd.notna(row.get('Armazém')):
                            new_a = Armazem(cenario_id=sel_cen_id, nome=row['Armazém'], capacidade_estatica=float(row['Capacidade Estática (Ton)']), capacidade_expedicao_diaria=float(row['Expedição Diária (Ton)']), estoque_inicial=row.get('Estoque Inicial (Ton)', 0))
                            session.add(new_a)
                    session.commit()
                    st.rerun()

            with tab_rot:
                df_show = format_dataframe(append_totals_row(st.session_state.df_rots_edit))
                edited = st.data_editor(df_show, key="editor_rots", hide_index=True, column_config=get_model_column_config(Rota), width='stretch')
                if st.button("Salvar Alterações Rotas"):
                    for _, row in edited.iterrows():
                        if str(row.get('Origem')).upper() == 'TOTAL' or pd.isna(row.get('id')) or row.get('id') == "":
                            continue
                        r = session.get(Rota, int(row['id']))
                        if r:
                            r.distancia_km = float(row['Distância (km)'])
                            r.custo_frete_ton = float(row['Custo Safra (R$/Ton)'])
                            r.custo_frete_entressafra = float(row['Custo Entressafra (R$/Ton)'])
                    session.commit()
                    st.success("Salvo com sucesso!")

            with tab_prev:
                st.write("**Fábricas**")
                df_f = format_dataframe(append_totals_row(st.session_state.df_pfabs_edit))
                ef = st.data_editor(df_f, key="epf", hide_index=True, column_config=get_model_column_config(PrevisaoFabrica), width='stretch')
                st.write("**Armazéns**")
                df_a = format_dataframe(append_totals_row(st.session_state.df_parms_edit))
                ea = st.data_editor(df_a, key="epa", hide_index=True, column_config=get_model_column_config(PrevisaoArmazem), width='stretch')
                if st.button("Salvar Previsões"):
                    # Processa Fábricas
                    for _, row in ef.iterrows():
                        if str(row.get('Fábrica')).upper() == 'TOTAL' or pd.isna(row.get('id')) or row.get('id') == "":
                            continue
                        p = session.get(PrevisaoFabrica, int(row['id']))
                        if p:
                            p.recebimento_produtor = float(row['Recebimento Produtor (Ton)'])
                            p.vendas = float(row['Vendas (Ton)'])
                    # Processa Armazéns
                    for _, row in ea.iterrows():
                        if str(row.get('Armazém')).upper() == 'TOTAL' or pd.isna(row.get('id')) or row.get('id') == "":
                            continue
                        p = session.get(PrevisaoArmazem, int(row['id']))
                        if p:
                            p.recebimento_produtor = float(row['Recebimento Produtor (Ton)'])
                            p.vendas = float(row['Vendas (Ton)'])
                    session.commit()
                    st.success("Salvo com sucesso!")




            with tab_safra:
                df_show = append_totals_row(st.session_state.df_safras_edit)
                edited = st.data_editor(df_show, key="esaf", hide_index=True, disabled=["id", "Tipo", "Unidade"], column_config=get_model_column_config(SafraUnidade))
                if st.button("Salvar Datas"):
                    for _, row in edited[edited['Unidade'] != 'TOTAL'].iterrows():
                        s = session.get(SafraUnidade, int(row['id']))
                        if s:
                            s.data_inicio = row['Início']
                            s.data_fim = row['Fim']
                    session.commit()
                    st.success("Salvo.")

            with tab_opt:
                col_o1, col_o2 = st.columns(2)
                with col_o1:
                    st.write("### Otimização")
                    estrategia = st.selectbox("Estratégia", ["Econômico", "Expedição", "Segurança"], key="strat_cen")
                    d_ini, d_fim = obter_range_previsoes(session, cenario_id=sel_cen_id)
                    if d_ini and d_fim:
                        if st.button("Rodar Otimização", type="primary", disabled=st.session_state.get('running_sim', False)):
                            st.session_state.running_sim = True
                            with st.spinner("Calculando..."):
                                try:
                                    simular_periodo(session, d_ini, d_fim, cenario_id=sel_cen_id, estrategia=estrategia)
                                    st.success("Concluído.")
                                except Exception as e: st.error(f"Erro: {e}")
                                finally:
                                    st.session_state.running_sim = False
                                    st.rerun()
                    else: st.warning("Dados de previsão insuficientes.")
                with col_o2:
                    st.write("### Exportar Dados")
                    st.write("Baixe os dados atuais deste cenário no formato de carga para edição externa.")
                    
                    # 1. Formata Fábricas para o padrão do template de importação
                    df_fabs = st.session_state.get('df_fabs_edit', pd.DataFrame())
                    if not df_fabs.empty:
                        df_fabs = df_fabs[df_fabs['Fábrica'].astype(str).str.upper() != 'TOTAL']
                        df_fabs_exp = pd.DataFrame({
                            'nome': df_fabs['Fábrica'],
                            'capacidade_estatica': df_fabs['Capacidade Estática (Ton)'],
                            'capacidade_esmagamento_diaria': df_fabs['Esmagamento Diário (Ton)'],
                            'capacidade_recebimento_diaria': df_fabs['Recebimento Diário (Ton)'],
                            'limite_caminhoes': df_fabs['Limite de Caminhões'],
                            'carga_media_caminhao': df_fabs['Carga Média (Ton)'],
                            'estoque_inicial': df_fabs['Estoque Inicial (Ton)']
                        })
                    else:
                        df_fabs_exp = pd.DataFrame(columns=[
                            'nome', 'capacidade_estatica', 'capacidade_esmagamento_diaria', 
                            'capacidade_recebimento_diaria', 'limite_caminhoes', 
                            'carga_media_caminhao', 'estoque_inicial'
                        ])

                    # 2. Formata Armazéns para o padrão do template de importação
                    df_arms = st.session_state.get('df_arms_edit', pd.DataFrame())
                    if not df_arms.empty:
                        df_arms = df_arms[df_arms['Armazém'].astype(str).str.upper() != 'TOTAL']
                        df_arms_exp = pd.DataFrame({
                            'nome': df_arms['Armazém'],
                            'capacidade_estatica': df_arms['Capacidade Estática (Ton)'],
                            'capacidade_expedicao_diaria': df_arms['Expedição Diária (Ton)'],
                            'estoque_inicial': df_arms['Estoque Inicial (Ton)']
                        })
                    else:
                        df_arms_exp = pd.DataFrame(columns=['nome', 'capacidade_estatica', 'capacidade_expedicao_diaria', 'estoque_inicial'])

                    # 3. Formata Rotas para o padrão do template de importação
                    df_rots = st.session_state.get('df_rots_edit', pd.DataFrame())
                    if not df_rots.empty:
                        df_rots = df_rots[df_rots['Origem'].astype(str).str.upper() != 'TOTAL']
                        df_rots_exp = pd.DataFrame({
                            'origem': df_rots['Origem'],
                            'destino': df_rots['Destino'],
                            'distancia_km': df_rots['Distância (km)'],
                            'custo_frete_ton': df_rots['Custo Safra (R$/Ton)']
                        })
                        if 'Custo Entressafra (R$/Ton)' in df_rots.columns:
                            df_rots_exp['custo_frete_entressafra'] = df_rots['Custo Entressafra (R$/Ton)']
                    else:
                        df_rots_exp = pd.DataFrame(columns=['origem', 'destino', 'distancia_km', 'custo_frete_ton', 'custo_frete_entressafra'])

                    # 4. Formata Previsões para o padrão do template de importação
                    df_pf = st.session_state.get('df_pfabs_edit', pd.DataFrame())
                    df_pa = st.session_state.get('df_parms_edit', pd.DataFrame())
                    prev_parts = []
                    if not df_pf.empty:
                        df_pf = df_pf[df_pf['Fábrica'].astype(str).str.upper() != 'TOTAL']
                        df_pf_exp = pd.DataFrame({
                            'entidade': df_pf['Fábrica'],
                            'mes_referencia': df_pf['Mês'],
                            'recebimento_produtor': df_pf['Recebimento Produtor (Ton)'],
                            'vendas': df_pf['Vendas (Ton)'],
                            'eh_safra': 0
                        })
                        prev_parts.append(df_pf_exp)
                    if not df_pa.empty:
                        df_pa = df_pa[df_pa['Armazém'].astype(str).str.upper() != 'TOTAL']
                        df_pa_exp = pd.DataFrame({
                            'entidade': df_pa['Armazém'],
                            'mes_referencia': df_pa['Mês'],
                            'recebimento_produtor': df_pa['Recebimento Produtor (Ton)'],
                            'vendas': df_pa['Vendas (Ton)'],
                            'eh_safra': 0
                        })
                        prev_parts.append(df_pa_exp)
                    if prev_parts:
                        df_prev_exp = pd.concat(prev_parts, ignore_index=True)
                    else:
                        df_prev_exp = pd.DataFrame(columns=['entidade', 'mes_referencia', 'recebimento_produtor', 'vendas', 'eh_safra'])

                    # Botões de download para as 4 tabelas principais
                    st.download_button("📥 Fábricas (Excel)", data=export_to_excel(df_fabs_exp), file_name=f"fabricas_{sel_cen_id}.xlsx")
                    st.download_button("📥 Armazéns (Excel)", data=export_to_excel(df_arms_exp), file_name=f"armazens_{sel_cen_id}.xlsx")
                    st.download_button("📥 Rotas (Excel)", data=export_to_excel(df_rots_exp), file_name=f"rotas_{sel_cen_id}.xlsx")
                    st.download_button("📥 Previsões (Excel)", data=export_to_excel(df_prev_exp), file_name=f"previsoes_{sel_cen_id}.xlsx")


    elif choice == "Carga de Dados":
        st.subheader("Carga de Dados via Planilha (Excel)")
        st.info("A carga agora realiza UPSERT: dados novos são inseridos e dados existentes são atualizados com base no Nome/Unidade.")
        
        sel_cen_id = st.selectbox("Cenário Destino da Carga", options=list(cenario_options.keys()), format_func=lambda x: cenario_options[x], key='load_cen_sel')
        
        col1, col2 = st.columns(2)
        with col1:
            with st.container(border=True):
                f_fab = st.file_uploader("Upload: Fábricas", type=["xlsx"], key="up_fab")
                if f_fab and st.button("🚀 Processar Fábricas", key="btn_fab"):
                    with st.spinner("Processando fábricas..."):
                        res = load_factories(f_fab, sel_cen_id, session=session)
                        st.success(f"{res} fábricas processadas.")
                
            with st.container(border=True):
                f_arm = st.file_uploader("Upload: Armazéns", type=["xlsx"], key="up_arm")
                if f_arm and st.button("🚀 Processar Armazéns", key="btn_arm"):
                    with st.spinner("Processando armazéns..."):
                        res = load_warehouses(f_arm, sel_cen_id, session=session)
                        st.success(f"{res} armazéns processados.")
                
        with col2:
            with st.container(border=True):
                f_rot = st.file_uploader("Upload: Rotas", type=["xlsx"], key="up_rot")
                if f_rot and st.button("🚀 Processar Rotas", key="btn_rot"):
                    with st.spinner("Processando rotas..."):
                        res, skip = load_routes(f_rot, sel_cen_id, session=session)
                        st.success(f"{res} rotas processadas. ({skip} ignoradas)")
                
            with st.container(border=True):
                f_prev = st.file_uploader("Upload: Previsões", type=["xlsx"], key="up_prev")
                if f_prev and st.button("🚀 Processar Previsões", key="btn_prev"):
                    with st.spinner("Processando previsões..."):
                        res, skip = load_previsoes(f_prev, sel_cen_id, session=session)
                        st.success(f"{res} previsões processadas. ({skip} ignoradas)")


        if st.sidebar.button("⚠️ Limpar TODO o Banco de Dados"):
            res, msg = clear_database(session=session)
            if res: st.success(msg)
            else: st.error(msg)

    elif choice == "Otimização":
        st.info("A otimização agora deve ser executada diretamente na tela 'Dados & Cenários' para o cenário desejado.")
        if st.button("Ir para Dados & Cenários"):
            st.rerun()

    session.close()

if __name__ == "__main__":
    main()
