import streamlit as st
import pandas as pd
import plotly.express as px
from data_loader import init_db, load_factories, load_warehouses, load_routes, load_previsoes, clear_database
from calculations import simular_periodo, obter_range_previsoes
from models import Fabrica, Armazem, Rota, PrevisaoFabrica, PrevisaoArmazem, MovimentacaoDiaria, ResumoMensalFabrica, ResumoMensalArmazem, Cenario
import scenarios
import datetime
from sqlalchemy import func
import io

st.set_page_config(page_title="Comigo - Transbordo de Soja", layout="wide")

def export_to_excel(df, filename):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

def format_volume(x):
    if pd.isna(x) or x == "": return ""
    try:
        return f"{float(x):,.0f}".replace(",", ".")
    except Exception:
        return x

def format_valor(x):
    if pd.isna(x) or x == "": return ""
    try:
        return f"{float(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return x

def format_dataframe(df):
    format_dict = {}
    for col in df.columns:
        if any(c in col for c in ['Custo', 'Frete', 'Valor']):
            format_dict[col] = format_valor
        elif any(c in col for c in ['Quantidade', 'Estoque', 'Capacidade', 'Recebimento', 'Vendas', 'Volume', 'Distância', 'Esmagado', 'Excedente', 'Envio']):
            format_dict[col] = format_volume
    if format_dict:
        return df.style.format(format_dict)
    return df

def main():
    # Logo no topo da barra lateral
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
        
        # Seletor de Cenário para Visualização
        all_cenarios = session.query(Cenario).all()
        cenario_options = {None: "Oficial (Planejado)"}
        for c in all_cenarios:
            cenario_options[c.id] = f"Simulação: {c.nome}"
            
        selected_cenario_id = st.sidebar.selectbox("Selecionar Cenário", options=list(cenario_options.keys()), format_func=lambda x: cenario_options[x])

        # Inicializar datas no session_state se não existirem
        if 'dash_data_ini' not in st.session_state:
            st.session_state.dash_data_ini = datetime.date.today() - datetime.timedelta(days=30)
        if 'dash_data_fim' not in st.session_state:
            st.session_state.dash_data_fim = datetime.date.today()
            
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            data_ini = st.date_input("Data Início", value=st.session_state.dash_data_ini, key='input_data_ini')
        with col2:
            data_fim = st.date_input("Data Fim", value=st.session_state.dash_data_fim, key='input_data_fim')
        with col3:
            st.write("") # Espaçador
            st.write("")
            if st.button("Visualizar tudo", use_container_width=True):
                min_d = session.query(func.min(MovimentacaoDiaria.data)).filter(MovimentacaoDiaria.cenario_id == selected_cenario_id).scalar()
                max_d = session.query(func.max(MovimentacaoDiaria.data)).filter(MovimentacaoDiaria.cenario_id == selected_cenario_id).scalar()
                if min_d and max_d:
                    st.session_state.dash_data_ini = min_d
                    st.session_state.dash_data_fim = max_d
                    st.rerun()
                else:
                    st.warning("Nenhuma movimentação encontrada para este cenário.")

        # Atualizar session_state
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
                    'Origem': session.query(Armazem).get(m.armazem_id).nome,
                    'Destino': session.query(Fabrica).get(m.fabrica_id).nome,
                    'Quantidade (Ton)': m.quantidade_ton,
                    'Quantidade (Sc)': m.quantidade_ton * 1000 / 60,
                    'Custo (R$)': m.custo_total
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
                    cols_diaria = ['Data', 'Origem', 'Destino', 'Quantidade (Ton)', 'Quantidade (Sc)', 'Custo (R$)']
                    st.dataframe(format_dataframe(df_movs[cols_diaria]))
                    st.download_button(label="Exportar Visão Diária para Excel", data=export_to_excel(df_movs[cols_diaria], "movimentacoes_diarias"), file_name="movimentacoes_diarias.xlsx")
                    fig = px.bar(df_movs, x='Data', y='Quantidade (Ton)', color='Destino', title="Volume por Destino (Diário)")
                    st.plotly_chart(fig, use_container_width=True)
                
                elif visao == "Mensal":
                    df_mes_total = df_movs.groupby('Mês').agg({'Quantidade (Ton)': 'sum', 'Quantidade (Sc)': 'sum', 'Custo (R$)': 'sum'}).reset_index()
                    df_mes_rotas = df_movs.groupby(['Mês', 'Origem', 'Destino']).agg({'Quantidade (Ton)': 'sum', 'Quantidade (Sc)': 'sum', 'Custo (R$)': 'sum'}).reset_index()
                    
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
                    total_cost = df_mes_total['Custo (R$)'].sum()
                    
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
                        df_rf = pd.DataFrame([{
                            'Mês': r.mes,
                            'Fábrica': session.query(Fabrica).get(r.fabrica_id).nome,
                            'Recebimento Produtor (Ton)': r.rec_produtor,
                            'Recebimento Transbordo (Ton)': r.rec_transbordo,
                            'Esmagado (Ton)': r.esmagado,
                            'Saldo Estoque Fim Mês (Ton)': r.saldo_estoque,
                            'Capacidade Estática (Ton)': r.capacidade_estatica,
                            'Excedente (Ton)': r.excedente
                        } for r in resumos_fab])
                        st.dataframe(format_dataframe(df_rf), hide_index=True)
                        st.download_button(label="Exportar Resumo Fábricas para Excel", data=export_to_excel(df_rf, "resumo_fabricas"), file_name="resumo_fabricas.xlsx")
                
                elif visao == "Resumo Armazéns":
                    resumos_arm = session.query(ResumoMensalArmazem).filter_by(cenario_id=selected_cenario_id).all()
                    if resumos_arm:
                        df_ra = pd.DataFrame([{
                            'Mês': r.mes,
                            'Armazém': session.query(Armazem).get(r.armazem_id).nome,
                            'Recebimento Produtor (Ton)': r.rec_produtor,
                            'Envio Transbordo (Ton)': r.envio_transbordo,
                            'Vendas (Ton)': r.vendas,
                            'Saldo Estoque Fim Mês (Ton)': r.saldo_estoque,
                            'Capacidade Estática (Ton)': r.capacidade_estatica,
                            'Excedente (Ton)': r.excedente
                        } for r in resumos_arm])
                        st.dataframe(format_dataframe(df_ra), hide_index=True)
                        st.download_button(label="Exportar Resumo Armazéns para Excel", data=export_to_excel(df_ra, "resumo_armazens"), file_name="resumo_armazens.xlsx")
            else:
                st.info("Nenhuma movimentação encontrada para o período e cenário selecionados.")
        except Exception as e:
            st.error(f"Erro ao carregar dashboard: {e}")

    elif choice == "Cenários de Simulação":
        # ... (rest of logic unchanged, just ensuring no duplicated blocks here)
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
            sel_cen_id = st.selectbox("Escolher Cenário para Editar/Otimizar", options=[c.id for c in cenarios], format_func=lambda x: session.query(Cenario).get(x).nome)
            
            if 'edit_sid' not in st.session_state or st.session_state.edit_sid != sel_cen_id:
                st.session_state.edit_sid = sel_cen_id
                fabs = session.query(Fabrica).filter_by(cenario_id=sel_cen_id).all()
                st.session_state.df_fabs_edit = pd.DataFrame([vars(f) for f in fabs]).drop(['_sa_instance_state', 'cenario_id'], axis=1)
                arms = session.query(Armazem).filter_by(cenario_id=sel_cen_id).all()
                st.session_state.df_arms_edit = pd.DataFrame([vars(a) for a in arms]).drop(['_sa_instance_state', 'cenario_id'], axis=1)
                rots = session.query(Rota).filter_by(cenario_id=sel_cen_id).all()
                data_rots = []
                for r in rots:
                    data_rots.append({
                        'id': r.id,
                        'Origem': session.query(Armazem).get(r.armazem_id).nome,
                        'Destino': session.query(Fabrica).get(r.fabrica_id).nome,
                        'Distância (km)': r.distancia_km,
                        'Custo Frete (Ton)': r.custo_frete_ton
                    })
                st.session_state.df_rots_edit = pd.DataFrame(data_rots)
                f_ids = [f.id for f in fabs]
                a_ids = [a.id for a in arms]
                p_fabs = session.query(PrevisaoFabrica).filter(PrevisaoFabrica.fabrica_id.in_(f_ids)).all()
                st.session_state.df_pfabs_edit = pd.DataFrame([{
                    'id': p.id,
                    'Fábrica': session.query(Fabrica).get(p.fabrica_id).nome,
                    'Mês': p.mes_referencia,
                    'Recebimento Produtor': p.recebimento_produtor,
                    'Vendas': p.vendas
                } for p in p_fabs])
                p_arms = session.query(PrevisaoArmazem).filter(PrevisaoArmazem.armazem_id.in_(a_ids)).all()
                st.session_state.df_parms_edit = pd.DataFrame([{
                    'id': p.id,
                    'Armazém': session.query(Armazem).get(p.armazem_id).nome,
                    'Mês': p.mes_referencia,
                    'Recebimento Produtor': p.recebimento_produtor,
                    'Vendas': p.vendas
                } for p in p_arms])

            if st.button("Excluir este Cenário", type="secondary"):
                if scenarios.delete_scenario(session, sel_cen_id):
                    if 'edit_sid' in st.session_state: del st.session_state.edit_sid
                    st.success("Cenário excluído.")
                    st.rerun()

            tab_fab, tab_arm, tab_rot, tab_prev, tab_opt = st.tabs(["Fábricas", "Armazéns", "Rotas", "Previsões", "Otimizar Cenário"])
            
            with tab_fab:
                st.session_state.df_fabs_edit = st.data_editor(st.session_state.df_fabs_edit, key="editor_fabs", hide_index=True)
                if st.button("Salvar Alterações Fábricas"):
                    for _, row in st.session_state.df_fabs_edit.iterrows():
                        f = session.query(Fabrica).get(row['id'])
                        f.capacidade_estatica = row['capacidade_estatica']
                        f.capacidade_esmagamento_diaria = row['capacidade_esmagamento_diaria']
                        f.capacidade_recebimento_diaria = row['capacidade_recebimento_diaria']
                    session.commit()
                    st.success("Fábricas salvas.")

            with tab_arm:
                st.session_state.df_arms_edit = st.data_editor(st.session_state.df_arms_edit, key="editor_arms", hide_index=True, num_rows="dynamic")
                if st.button("Salvar Alterações Armazéns"):
                    for _, row in st.session_state.df_arms_edit.iterrows():
                        if 'id' in row and not pd.isna(row['id']):
                            a = session.query(Armazem).get(row['id'])
                            a.nome = row['nome']
                            a.capacidade_estatica = row['capacidade_estatica']
                            a.capacidade_expedicao_diaria = row['capacidade_expedicao_diaria']
                        else:
                            new_a = Armazem(cenario_id=sel_cen_id, nome=row['nome'], capacidade_estatica=row['capacidade_estatica'], capacidade_expedicao_diaria=row['capacidade_expedicao_diaria'], estoque_inicial=row.get('estoque_inicial', 0))
                            session.add(new_a)
                    session.commit()
                    del st.session_state.edit_sid
                    st.success("Armazéns atualizados.")
                    st.rerun()

            with tab_rot:
                st.session_state.df_rots_edit = st.data_editor(st.session_state.df_rots_edit, key="editor_rots", hide_index=True)
                if st.button("Salvar Alterações Rotas"):
                    for _, row in st.session_state.df_rots_edit.iterrows():
                        r = session.query(Rota).get(row['id'])
                        r.distancia_km = row['Distância (km)']
                        r.custo_frete_ton = row['Custo Frete (Ton)']
                    session.commit()
                    st.success("Rotas atualizadas.")

            with tab_prev:
                st.write("**Previsões Fábricas**")
                st.session_state.df_pfabs_edit = st.data_editor(st.session_state.df_pfabs_edit, key="editor_pf", hide_index=True)
                st.write("**Previsões Armazéns**")
                st.session_state.df_parms_edit = st.data_editor(st.session_state.df_parms_edit, key="editor_pa", hide_index=True)
                if st.button("Salvar Todas as Previsões"):
                    for _, row in st.session_state.df_pfabs_edit.iterrows():
                        p = session.query(PrevisaoFabrica).get(row['id'])
                        p.recebimento_produtor = row['Recebimento Produtor']
                        p.vendas = row['Vendas']
                    for _, row in st.session_state.df_parms_edit.iterrows():
                        p = session.query(PrevisaoArmazem).get(row['id'])
                        p.recebimento_produtor = row['Recebimento Produtor']
                        p.vendas = row['Vendas']
                    session.commit()
                    st.success("Previsões atualizadas.")

            with tab_opt:
                d_ini, d_fim = obter_range_previsoes(session, cenario_id=sel_cen_id)
                if d_ini and d_fim:
                    if st.button(f"Rodar Otimização do Cenário ({d_ini} a {d_fim})", type="primary"):
                        with st.spinner("Otimizando cenário..."):
                            simular_periodo(session, d_ini, d_fim, cenario_id=sel_cen_id)
                            st.success("Otimização concluída!")
                else: st.warning("Dados insuficientes.")
        else: st.info("Nenhum cenário criado.")

    elif choice == "Carga de Dados":
        st.subheader("Gerenciamento e Carga de Dados via XLSX")
        with st.expander("⚠️ Área de Perigo: Limpar Banco de Dados"):
            if st.button("Apagar todos os dados e reiniciar identidades", type="primary"):
                with st.spinner("Limpando..."):
                    success, msg = clear_database()
                    if success: st.success(msg)
                    else: st.error(msg)
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            file_fab = st.file_uploader("Upload Fábricas", type=["xlsx"])
            if file_fab and st.button("Carregar Fábricas"):
                try:
                    c = load_factories(file_fab)
                    st.success(f"{c} fábricas carregadas!")
                except Exception as e: st.error(f"Erro: {e}")
            file_arm = st.file_uploader("Upload Armazéns", type=["xlsx"])
            if file_arm and st.button("Carregar Armazéns"):
                try:
                    c = load_warehouses(file_arm)
                    st.success(f"{c} armazéns carregados!")
                except Exception as e: st.error(f"Erro: {e}")
        with col_c2:
            file_rot = st.file_uploader("Upload Rotas", type=["xlsx"])
            if file_rot and st.button("Carregar Rotas"):
                try:
                    c, s = load_routes(file_rot)
                    st.success(f"{c} rotas carregadas!")
                except Exception as e: st.error(f"Erro: {e}")
            file_prev = st.file_uploader("Upload Previsões Mensais", type=["xlsx"])
            if file_prev and st.button("Carregar Previsões"):
                try:
                    c, s = load_previsoes(file_prev)
                    st.success(f"{c} previsões carregadas!")
                except Exception as e: st.error(f"Erro: {e}")

    elif choice == "Visualizar Dados":
        st.subheader("Visualização das Tabelas do Banco de Dados")
        tabela = st.selectbox("Selecione a Tabela", ["Fábricas", "Armazéns", "Rotas", "Previsões Fábrica", "Previsões Armazém", "Movimentações Diárias"])
        if tabela == "Fábricas":
            dados = session.query(Fabrica).all()
            if dados:
                df = pd.DataFrame([vars(d) for d in dados]).drop('_sa_instance_state', axis=1)
                st.dataframe(format_dataframe(df))
                st.download_button(label="Exportar para Excel", data=export_to_excel(df, "fabricas"), file_name="fabricas.xlsx")
            else: st.warning("Tabela vazia.")
        elif tabela == "Armazéns":
            dados = session.query(Armazem).all()
            if dados:
                df = pd.DataFrame([vars(d) for d in dados]).drop('_sa_instance_state', axis=1)
                st.dataframe(format_dataframe(df))
                st.download_button(label="Exportar para Excel", data=export_to_excel(df, "armazens"), file_name="armazens.xlsx")
            else: st.warning("Tabela vazia.")
        elif tabela == "Rotas":
            dados = session.query(Rota).all()
            if dados:
                df = pd.DataFrame([{
                    'ID': d.id,
                    'Cenário': session.query(Cenario).get(d.cenario_id).nome if d.cenario_id else "Oficial",
                    'Origem': session.query(Armazem).get(d.armazem_id).nome,
                    'Destino': session.query(Fabrica).get(d.fabrica_id).nome,
                    'Distância (km)': d.distancia_km,
                    'Custo Frete (Ton)': d.custo_frete_ton
                } for d in dados])
                st.dataframe(format_dataframe(df))
                st.download_button(label="Exportar para Excel", data=export_to_excel(df, "rotas"), file_name="rotas.xlsx")
            else: st.warning("Tabela vazia.")
        elif tabela == "Previsões Fábrica":
            dados = session.query(PrevisaoFabrica).all()
            if dados:
                df = pd.DataFrame([{
                    'id': d.id,
                    'Fábrica': session.query(Fabrica).get(d.fabrica_id).nome,
                    'Mês': d.mes_referencia,
                    'Recebimento Produtor': d.recebimento_produtor,
                    'Vendas': d.vendas
                } for d in dados])
                st.dataframe(format_dataframe(df))
            else: st.warning("Tabela vazia.")
        elif tabela == "Previsões Armazém":
            dados = session.query(PrevisaoArmazem).all()
            if dados:
                df = pd.DataFrame([{
                    'id': d.id,
                    'Armazém': session.query(Armazem).get(d.armazem_id).nome,
                    'Mês': d.mes_referencia,
                    'Recebimento Produtor': d.recebimento_produtor,
                    'Vendas': d.vendas
                } for d in dados])
                st.dataframe(format_dataframe(df))
            else: st.warning("Tabela vazia.")
        elif tabela == "Movimentações Diárias":
            dados = session.query(MovimentacaoDiaria).all()
            if dados:
                df = pd.DataFrame([{
                    'Data': d.data,
                    'Cenário': session.query(Cenario).get(d.cenario_id).nome if d.cenario_id else "Oficial",
                    'Origem': session.query(Armazem).get(d.armazem_id).nome,
                    'Destino': session.query(Fabrica).get(d.fabrica_id).nome,
                    'Quantidade (Ton)': d.quantidade_ton,
                    'Quantidade (Sc)': d.quantidade_ton * 1000 / 60,
                    'Custo Total': d.custo_total
                } for d in dados])
                st.dataframe(format_dataframe(df))
                st.download_button(label="Exportar para Excel", data=export_to_excel(df, "movimentacoes"), file_name="movimentacoes.xlsx")
            else: st.warning("Tabela vazia.")

    elif choice == "Otimização":
        st.subheader("Executar Otimização de Transbordo (Planejado)")
        d_sug_ini, d_sug_fim = obter_range_previsoes(session, cenario_id=None)
        col1, col2 = st.columns(2)
        with col1: d_ini = st.date_input("Início da Simulação", d_sug_ini if d_sug_ini else datetime.date.today())
        with col2: d_fim = st.date_input("Fim da Simulação", d_sug_fim if d_sug_fim else datetime.date.today() + datetime.timedelta(days=30))
        if st.button("Otimizar Tudo (Oficial)", type="primary", use_container_width=True):
            with st.spinner("Otimizando..."):
                try:
                    simular_periodo(session, d_ini, d_fim, cenario_id=None)
                    st.success("Otimização concluída!")
                except Exception as e: st.error(f"Erro: {e}")

    session.close()

if __name__ == "__main__":
    main()
