import streamlit as st
import pandas as pd
import plotly.express as px
from data_loader import init_db, load_factories, load_warehouses, load_routes, load_previsoes, clear_database
from calculations import simular_periodo, obter_range_previsoes
from models import Fabrica, Armazem, Rota, PrevisaoFabrica, PrevisaoArmazem, MovimentacaoDiaria, ResumoMensalFabrica, ResumoMensalArmazem, Cenario, SafraUnidade
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
            st.write("") 
            st.write("")
            if st.button("Visualizar tudo", use_container_width=True):
                min_d = session.query(func.min(MovimentacaoDiaria.data)).filter(MovimentacaoDiaria.cenario_id == selected_cenario_id).scalar()
                max_d = session.query(func.max(MovimentacaoDiaria.data)).filter(MovimentacaoDiaria.cenario_id == selected_cenario_id).scalar()
                if min_d and max_d:
                    st.session_state.dash_data_ini = min_d
                    st.session_state.dash_data_fim = max_d
                    st.rerun()
                else:
                    st.warning("Nenhuma movimentação encontrada.")

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
                        
                        fabricas_sel = st.multiselect("Filtrar por Fábrica", options=df_rf['Fábrica'].unique(), default=[])
                        if fabricas_sel:
                            df_rf = df_rf[df_rf['Fábrica'].isin(fabricas_sel)]

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
                        
                        armazens_sel = st.multiselect("Filtrar por Armazém", options=df_ra['Armazém'].unique(), default=[])
                        if armazens_sel:
                            df_ra = df_ra[df_ra['Armazém'].isin(armazens_sel)]

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
            sel_cen_id = st.selectbox("Escolher Cenário para Editar/Otimizar", options=[c.id for c in cenarios], format_func=lambda x: session.query(Cenario).get(x).nome)
            
            # Lógica de Persistência e Recuperação de Dados do Cenário
            if 'edit_sid' not in st.session_state or st.session_state.edit_sid != sel_cen_id:
                st.session_state.edit_sid = sel_cen_id
                
                # 1. Fábricas
                fabs = session.query(Fabrica).filter_by(cenario_id=sel_cen_id).all()
                st.session_state.df_fabs_edit = pd.DataFrame([{
                    'id': f.id, 'nome': f.nome, 'capacidade_estatica': f.capacidade_estatica,
                    'capacidade_esmagamento_diaria': f.capacidade_esmagamento_diaria,
                    'capacidade_recebimento_diaria': f.capacidade_recebimento_diaria,
                    'limite_caminhoes': f.limite_caminhoes, 'carga_media_caminhao': f.carga_media_caminhao,
                    'estoque_inicial': f.estoque_inicial
                } for f in fabs])
                
                # 2. Armazéns
                arms = session.query(Armazem).filter_by(cenario_id=sel_cen_id).all()
                st.session_state.df_arms_edit = pd.DataFrame([{
                    'id': a.id, 'nome': a.nome, 'capacidade_estatica': a.capacidade_estatica,
                    'capacidade_expedicao_diaria': a.capacidade_expedicao_diaria,
                    'estoque_inicial': a.estoque_inicial
                } for a in arms])
                
                # 3. Rotas
                rots = session.query(Rota).filter_by(cenario_id=sel_cen_id).all()
                st.session_state.df_rots_edit = pd.DataFrame([{
                    'id': r.id, 
                    'Origem': session.get(Armazem, r.armazem_id).nome if session.get(Armazem, r.armazem_id) else "N/A",
                    'Destino': session.get(Fabrica, r.fabrica_id).nome if session.get(Fabrica, r.fabrica_id) else "N/A",
                    'Distância (km)': r.distancia_km, 'Custo Safra': r.custo_frete_ton,
                    'Custo Entressafra': r.custo_frete_entressafra
                } for r in rots])
                
                # 4. Previsões Fábrica
                p_fabs = session.query(PrevisaoFabrica).join(Fabrica).filter(Fabrica.cenario_id == sel_cen_id).all()
                st.session_state.df_pfabs_edit = pd.DataFrame([{
                    'id': p.id, 
                    'Fábrica': session.get(Fabrica, p.fabrica_id).nome if session.get(Fabrica, p.fabrica_id) else "N/A",
                    'Mês': p.mes_referencia, 'Recebimento Produtor': p.recebimento_produtor, 'Vendas': p.vendas
                } for p in p_fabs])
                
                # 5. Previsões Armazém
                p_arms = session.query(PrevisaoArmazem).join(Armazem).filter(Armazem.cenario_id == sel_cen_id).all()
                st.session_state.df_parms_edit = pd.DataFrame([{
                    'id': p.id, 
                    'Armazém': session.get(Armazem, p.armazem_id).nome if session.get(Armazem, p.armazem_id) else "N/A",
                    'Mês': p.mes_referencia, 'Recebimento Produtor': p.recebimento_produtor, 'Vendas': p.vendas
                } for p in p_arms])

                # 6. Datas de Safra (Auto-inicialização se faltar para o cenário)
                for f in fabs:
                    if not session.query(SafraUnidade).filter_by(cenario_id=sel_cen_id, entidade_tipo='Fábrica', entidade_id=f.id).first():
                        session.add(SafraUnidade(cenario_id=sel_cen_id, entidade_tipo='Fábrica', entidade_id=f.id, data_inicio=datetime.date(2026,1,15), data_fim=datetime.date(2026,4,15)))
                for a in arms:
                    if not session.query(SafraUnidade).filter_by(cenario_id=sel_cen_id, entidade_tipo='Armazém', entidade_id=a.id).first():
                        session.add(SafraUnidade(cenario_id=sel_cen_id, entidade_tipo='Armazém', entidade_id=a.id, data_inicio=datetime.date(2026,1,15), data_fim=datetime.date(2026,4,15)))
                session.commit()

                safras = session.query(SafraUnidade).filter_by(cenario_id=sel_cen_id).all()
                st.session_state.df_safras_edit = pd.DataFrame([{
                    'id': s.id, 'Tipo': s.entidade_tipo, 
                    'Unidade': session.get(Armazem, s.entidade_id).nome if s.entidade_tipo == 'Armazém' else session.get(Fabrica, s.entidade_id).nome,
                    'Início': s.data_inicio, 'Fim': s.data_fim
                } for s in safras])

            if st.button("Excluir este Cenário", type="secondary"):
                if scenarios.delete_scenario(session, sel_cen_id):
                    if 'edit_sid' in st.session_state: del st.session_state.edit_sid
                    st.success("Cenário excluído.")
                    st.rerun()

            tab_fab, tab_arm, tab_rot, tab_prev, tab_safra, tab_opt = st.tabs(["Fábricas", "Armazéns", "Rotas", "Previsões", "Datas de Safra", "Otimizar Cenário"])
            
            with tab_fab:
                st.session_state.df_fabs_edit = st.data_editor(st.session_state.df_fabs_edit, key="editor_fabs", hide_index=True, disabled=["id", "nome"])
                if st.button("Salvar Alterações Fábricas"):
                    for _, row in st.session_state.df_fabs_edit.iterrows():
                        f = session.get(Fabrica, int(row['id']))
                        if f:
                            f.capacidade_estatica = float(row['capacidade_estatica'])
                            f.capacidade_esmagamento_diaria = float(row['capacidade_esmagamento_diaria'])
                            f.capacidade_recebimento_diaria = float(row['capacidade_recebimento_diaria'])
                    session.commit()
                    st.success("Salvo.")

            with tab_arm:
                st.session_state.df_arms_edit = st.data_editor(st.session_state.df_arms_edit, key="editor_arms", hide_index=True, num_rows="dynamic", disabled=["id"])
                if st.button("Salvar Alterações Armazéns"):
                    for _, row in st.session_state.df_arms_edit.iterrows():
                        if 'id' in row and not pd.isna(row['id']):
                            a = session.get(Armazem, int(row['id']))
                            if a:
                                a.nome = row['nome']
                                a.capacidade_estatica = float(row['capacidade_estatica'])
                                a.capacidade_expedicao_diaria = float(row['capacidade_expedicao_diaria'])
                        else:
                            new_a = Armazem(cenario_id=sel_cen_id, nome=row['nome'], capacidade_estatica=float(row['capacidade_estatica']), capacidade_expedicao_diaria=float(row['capacidade_expedicao_diaria']), estoque_inicial=row.get('estoque_inicial', 0))
                            session.add(new_a)
                    session.commit()
                    del st.session_state.edit_sid
                    st.success("Atualizado.")
                    st.rerun()

            with tab_rot:
                st.session_state.df_rots_edit = st.data_editor(st.session_state.df_rots_edit, key="editor_rots", hide_index=True, disabled=["id", "Origem", "Destino"])
                if st.button("Salvar Alterações Rotas"):
                    for _, row in st.session_state.df_rots_edit.iterrows():
                        r = session.get(Rota, int(row['id']))
                        if r:
                            r.distancia_km = float(row['Distância (km)'])
                            r.custo_frete_ton = float(row['Custo Safra'])
                            r.custo_frete_entressafra = float(row['Custo Entressafra'])
                    session.commit()
                    st.success("Rotas salvas.")

            with tab_prev:
                st.write("**Previsões Fábricas**")
                st.session_state.df_pfabs_edit = st.data_editor(st.session_state.df_pfabs_edit, key="editor_pf", hide_index=True, disabled=["id", "Fábrica", "Mês"])
                st.write("**Previsões Armazéns**")
                st.session_state.df_parms_edit = st.data_editor(st.session_state.df_parms_edit, key="editor_pa", hide_index=True, disabled=["id", "Armazém", "Mês"])
                if st.button("Salvar Todas as Previsões"):
                    for _, row in st.session_state.df_pfabs_edit.iterrows():
                        p = session.get(PrevisaoFabrica, int(row['id']))
                        if p:
                            p.recebimento_produtor = float(row['Recebimento Produtor'])
                            p.vendas = float(row['Vendas'])
                    for _, row in st.session_state.df_parms_edit.iterrows():
                        p = session.get(PrevisaoArmazem, int(row['id']))
                        if p:
                            p.recebimento_produtor = float(row['Recebimento Produtor'])
                            p.vendas = float(row['Vendas'])
                    session.commit()
                    st.success("Previsões atualizadas.")

            with tab_safra:
                st.info("Defina as janelas exatas de safra para cada unidade.")
                st.session_state.df_safras_edit = st.data_editor(st.session_state.df_safras_edit, key="editor_safra", hide_index=True, num_rows="dynamic", disabled=["id", "Tipo", "Unidade"])
                if st.button("Salvar Datas de Safra"):
                    for _, row in st.session_state.df_safras_edit.iterrows():
                        s = session.get(SafraUnidade, int(row['id']))
                        if s:
                            s.data_inicio = row['Início']
                            s.data_fim = row['Fim']
                    session.commit()
                    st.success("Datas salvas.")

            with tab_opt:
                estrategia = st.selectbox("Estratégia de Otimização", ["Econômico", "Expedição", "Segurança"], key="strat_cen")
                d_ini, d_fim = obter_range_previsoes(session, cenario_id=sel_cen_id)
                if d_ini and d_fim:
                    if st.button(f"Rodar Otimização ({estrategia})", type="primary"):
                        with st.spinner("Calculando..."):
                            simular_periodo(session, d_ini, d_fim, cenario_id=sel_cen_id, estrategia=estrategia)
                            st.success("Concluído.")
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
        st.subheader("Gerenciamento e Edição de Dados (Planejado)")
        st.info("As alterações feitas aqui afetam o cenário **Oficial (Planejado)**.")

        tabela = st.selectbox("Selecione a Tabela", ["Fábricas", "Armazéns", "Rotas", "Previsões Fábrica", "Previsões Armazém", "Datas de Safra", "Movimentações Diárias"])

        if tabela == "Fábricas":
            dados = session.query(Fabrica).filter_by(cenario_id=None).all()
            if dados:
                df = pd.DataFrame([{
                    'id': d.id, 'nome': d.nome, 'capacidade_estatica': d.capacidade_estatica,
                    'capacidade_esmagamento_diaria': d.capacidade_esmagamento_diaria,
                    'capacidade_recebimento_diaria': d.capacidade_recebimento_diaria,
                    'limite_caminhoes': d.limite_caminhoes, 'carga_media_caminhao': d.carga_media_caminhao,
                    'estoque_inicial': d.estoque_inicial
                } for d in dados])
                edited_df = st.data_editor(df, hide_index=True, disabled=["id", "nome"], key="vis_edit_fab_base")
                if st.button("Salvar Alterações Fábricas"):
                    for _, row in edited_df.iterrows():
                        obj = session.get(Fabrica, int(row['id']))
                        if obj:
                            obj.capacidade_estatica = float(row['capacidade_estatica'])
                            obj.capacidade_esmagamento_diaria = float(row['capacidade_esmagamento_diaria'])
                            obj.capacidade_recebimento_diaria = float(row['capacidade_recebimento_diaria'])
                    session.commit()
                    st.success("Fábricas atualizadas.")
                st.download_button(label="Exportar Excel", data=export_to_excel(df, "fabricas"), file_name="fabricas.xlsx")
            else: st.warning("Vazio.")

        elif tabela == "Armazéns":
            dados = session.query(Armazem).filter_by(cenario_id=None).all()
            if dados:
                df = pd.DataFrame([{
                    'id': d.id, 'nome': d.nome, 'capacidade_estatica': d.capacidade_estatica,
                    'capacidade_expedicao_diaria': d.capacidade_expedicao_diaria,
                    'estoque_inicial': d.estoque_inicial
                } for d in dados])
                edited_df = st.data_editor(df, hide_index=True, disabled=["id", "nome"], key="vis_edit_arm_base")
                if st.button("Salvar Alterações Armazéns"):
                    for _, row in edited_df.iterrows():
                        obj = session.get(Armazem, int(row['id']))
                        if obj:
                            obj.capacidade_estatica = float(row['capacidade_estatica'])
                            obj.capacidade_expedicao_diaria = float(row['capacidade_expedicao_diaria'])
                    session.commit()
                    st.success("Armazéns atualizados.")
                st.download_button(label="Exportar Excel", data=export_to_excel(df, "armazens"), file_name="armazens.xlsx")
            else: st.warning("Vazio.")

        elif tabela == "Rotas":
            dados = session.query(Rota).filter_by(cenario_id=None).all()
            if dados:
                df_data = []
                for d in dados:
                    arm = session.get(Armazem, d.armazem_id)
                    fab = session.get(Fabrica, d.fabrica_id)
                    df_data.append({
                        'id': d.id, 
                        'Origem': arm.nome if arm else "N/A",
                        'Destino': fab.nome if fab else "N/A",
                        'Distância (km)': d.distancia_km, 'Custo Safra': d.custo_frete_ton,
                        'Custo Entressafra': d.custo_frete_entressafra
                    })
                df = pd.DataFrame(df_data)
                edited_df = st.data_editor(df, hide_index=True, disabled=["id", "Origem", "Destino"], key="vis_edit_rot_base")
                if st.button("Salvar Alterações Rotas"):
                    for _, row in edited_df.iterrows():
                        obj = session.get(Rota, int(row['id']))
                        if obj:
                            obj.distancia_km = float(row['Distância (km)'])
                            obj.custo_frete_ton = float(row['Custo Safra'])
                            obj.custo_frete_entressafra = float(row['Custo Entressafra'])
                    session.commit()
                    st.success("Rotas atualizadas.")
                st.download_button(label="Exportar Excel", data=export_to_excel(df, "rotas"), file_name="rotas.xlsx")
            else: st.warning("Vazio.")

        elif tabela == "Previsões Fábrica":
            dados = session.query(PrevisaoFabrica).join(Fabrica).filter(Fabrica.cenario_id == None).all()
            if dados:
                df = pd.DataFrame([{
                    'id': d.id, 
                    'Fábrica': session.get(Fabrica, d.fabrica_id).nome if session.get(Fabrica, d.fabrica_id) else "N/A",
                    'Mês': d.mes_referencia, 'Recebimento Produtor': d.recebimento_produtor, 'Vendas': d.vendas
                } for d in dados])
                edited_df = st.data_editor(df, hide_index=True, disabled=["id", "Fábrica", "Mês"], key="vis_edit_pfab_base")
                if st.button("Salvar Previsões Fábrica"):
                    for _, row in edited_df.iterrows():
                        obj = session.get(PrevisaoFabrica, int(row['id']))
                        if obj:
                            obj.recebimento_produtor = float(row['Recebimento Produtor'])
                            obj.vendas = float(row['Vendas'])
                    session.commit()
                    st.success("Previsões salvas.")
            else: st.warning("Vazio.")

        elif tabela == "Previsões Armazém":
            dados = session.query(PrevisaoArmazem).join(Armazem).filter(Armazem.cenario_id == None).all()
            if dados:
                df = pd.DataFrame([{
                    'id': d.id, 
                    'Armazém': session.get(Armazem, d.armazem_id).nome if session.get(Armazem, d.armazem_id) else "N/A",
                    'Mês': d.mes_referencia, 'Recebimento Produtor': d.recebimento_produtor, 'Vendas': d.vendas
                } for d in dados])
                edited_df = st.data_editor(df, hide_index=True, disabled=["id", "Armazém", "Mês"], key="vis_edit_parm_base")
                if st.button("Salvar Previsões Armazém"):
                    for _, row in edited_df.iterrows():
                        obj = session.get(PrevisaoArmazem, int(row['id']))
                        if obj:
                            obj.recebimento_produtor = float(row['Recebimento Produtor'])
                            obj.vendas = float(row['Vendas'])
                    session.commit()
                    st.success("Previsões salvas.")
            else: st.warning("Vazio.")

        elif tabela == "Datas de Safra":
            # Garantir inicialização de datas para o Planejado
            arms = session.query(Armazem).filter(Armazem.cenario_id == None).all()
            fabs = session.query(Fabrica).filter(Fabrica.cenario_id == None).all()
            for a in arms:
                if not session.query(SafraUnidade).filter_by(cenario_id=None, entidade_tipo='Armazém', entidade_id=a.id).first():
                    session.add(SafraUnidade(cenario_id=None, entidade_tipo='Armazém', entidade_id=a.id, data_inicio=datetime.date(2026,1,15), data_fim=datetime.date(2026,4,15)))
            for f in fabs:
                if not session.query(SafraUnidade).filter_by(cenario_id=None, entidade_tipo='Fábrica', entidade_id=f.id).first():
                    session.add(SafraUnidade(cenario_id=None, entidade_tipo='Fábrica', entidade_id=f.id, data_inicio=datetime.date(2026,1,15), data_fim=datetime.date(2026,4,15)))
            session.commit()

            dados = session.query(SafraUnidade).filter(SafraUnidade.cenario_id == None).all()
            df_safra = pd.DataFrame([{
                'id': d.id, 'Tipo': d.entidade_tipo,
                'Unidade': session.get(Armazem, d.entidade_id).nome if d.entidade_tipo == 'Armazém' else session.get(Fabrica, d.entidade_id).nome,
                'Início': d.data_inicio, 'Fim': d.data_fim
            } for d in dados])
            edited_df = st.data_editor(df_safra, hide_index=True, disabled=["id", "Tipo", "Unidade"], key="vis_edit_safra_plan_base")
            if st.button("Salvar Datas de Safra"):
                for _, row in edited_df.iterrows():
                    obj = session.get(SafraUnidade, int(row['id']))
                    if obj:
                        obj.data_inicio = row['Início']
                        obj.data_fim = row['Fim']
                session.commit()
                st.success("Configurações de Safra atualizadas.")

        elif tabela == "Movimentações Diárias":
            dados = session.query(MovimentacaoDiaria).filter(MovimentacaoDiaria.cenario_id == None).all()
            if dados:
                df = pd.DataFrame([{
                    'Data': d.data, 
                    'Origem': session.get(Armazem, d.armazem_id).nome if session.get(Armazem, d.armazem_id) else "N/A",
                    'Destino': session.get(Fabrica, d.fabrica_id).nome if session.get(Fabrica, d.fabrica_id) else "N/A",
                    'Quantidade (Ton)': d.quantidade_ton, 'Quantidade (Sc)': d.quantidade_ton * 1000 / 60,
                    'Custo Total': d.custo_total
                } for d in dados])
                st.dataframe(format_dataframe(df), hide_index=True)
                st.download_button(label="Exportar Excel", data=export_to_excel(df, "movimentacoes"), file_name="movimentacoes.xlsx")
            else: st.warning("Vazio.")

    elif choice == "Otimização":
        st.subheader("Executar Otimização de Transbordo (Oficial)")
        st.info("O sistema processará o transbordo a partir da data inicial até que todos os armazéns estejam zerados.")
        
        estrategia = st.selectbox("Estratégia de Otimização", ["Econômico", "Expedição", "Segurança"], key="strat_oficial")
        d_sug_ini, d_sug_fim = obter_range_previsoes(session, cenario_id=None)
        
        col1, col2 = st.columns(2)
        with col1: 
            d_ini = st.date_input("Início da Simulação", d_sug_ini if d_sug_ini else datetime.date.today())
        with col2:
            st.write("**Fim das Entradas (Previsões):**")
            st.write(f"`{d_sug_fim}`" if d_sug_fim else "`Não detectado`")

        if st.button("Rodar Otimização Completa (Até zerar armazéns)", type="primary", use_container_width=True):
            if d_sug_fim:
                with st.spinner("Calculando otimização oficial..."):
                    try:
                        simular_periodo(session, d_ini, d_sug_fim, cenario_id=None, estrategia=estrategia)
                        st.success("Otimização concluída com sucesso!")
                    except Exception as e: 
                        st.error(f"Erro no processamento: {e}")
            else:
                st.warning("Não foi possível detectar o período das previsões. Certifique-se de que os dados foram carregados.")


    session.close()

if __name__ == "__main__":
    main()
