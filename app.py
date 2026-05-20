import streamlit as st
import pandas as pd
import plotly.express as px
from data_loader import init_db, load_factories, load_warehouses, load_routes, load_previsoes, clear_database
from calculations import simular_periodo, obter_range_previsoes
from models import Fabrica, Armazem, Rota, PrevisaoFabrica, PrevisaoArmazem, MovimentacaoDiaria, ResumoMensalFabrica, ResumoMensalArmazem
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
    if pd.isna(x): return ""
    return f"{x:,.0f}".replace(",", ".")

def format_valor(x):
    if pd.isna(x): return ""
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def format_dataframe(df):
    format_dict = {}
    for col in df.columns:
        if 'Custo' in col or 'Frete' in col or 'Valor' in col:
            format_dict[col] = format_valor
        elif any(c in col for c in ['Quantidade', 'Estoque', 'Capacidade', 'Recebimento', 'Vendas', 'Volume', 'Distância', 'Esmagado', 'Excedente', 'Envio']):
            format_dict[col] = format_volume
    if format_dict:
        return df.style.format(format_dict)
    return df

def main():
    st.title("Sistema de Planejamento de Transbordo - Comigo")
    
    menu = ["Dashboard", "Carga de Dados", "Visualizar Dados", "Otimização"]
    choice = st.sidebar.selectbox("Menu", menu)
    
    session = init_db()
    
    if choice == "Dashboard":
        st.subheader("Dashboard de Movimentações")
        
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
                min_d = session.query(func.min(MovimentacaoDiaria.data)).scalar()
                max_d = session.query(func.max(MovimentacaoDiaria.data)).scalar()
                if min_d and max_d:
                    st.session_state.dash_data_ini = min_d
                    st.session_state.dash_data_fim = max_d
                    st.rerun()
                else:
                    st.warning("Nenhuma movimentação encontrada.")

        # Atualizar session_state com os valores dos inputs para manter consistência
        st.session_state.dash_data_ini = data_ini
        st.session_state.dash_data_fim = data_fim
            
        # Carregar dados
        try:
            movs = session.query(MovimentacaoDiaria).filter(MovimentacaoDiaria.data.between(data_ini, data_fim)).all()
            
            if movs:
                df_movs = pd.DataFrame([{
                    'Data': m.data,
                    'Origem': session.query(Armazem).get(m.armazem_id).nome,
                    'Destino': session.query(Fabrica).get(m.fabrica_id).nome,
                    'Quantidade (Ton)': m.quantidade_ton,
                    'Quantidade (Sc)': m.quantidade_ton * 1000 / 60,
                    'Custo (R$)': m.custo_total
                } for m in movs])
                
                # Adicionar coluna de Mês para agrupamento
                df_movs['Mês'] = pd.to_datetime(df_movs['Data']).dt.strftime('%Y-%m')
                
                visao = st.radio("Selecione a Visão", ["Diária", "Mensal", "Resumo Fábricas", "Resumo Armazéns"], horizontal=True)
                
                if visao == "Diária" or visao == "Mensal":
                    # Filtros de Origem e Destino
                    col_f1, col_f2 = st.columns(2)
                    with col_f1:
                        origens = st.multiselect("Filtrar por Origem", options=df_movs['Origem'].unique(), default=[])
                    with col_f2:
                        destinos = st.multiselect("Filtrar por Destino", options=df_movs['Destino'].unique(), default=[])
                        
                    if origens:
                        df_movs = df_movs[df_movs['Origem'].isin(origens)]
                    if destinos:
                        df_movs = df_movs[df_movs['Destino'].isin(destinos)]
                
                if visao == "Diária":
                    cols_diaria = ['Data', 'Origem', 'Destino', 'Quantidade (Ton)', 'Quantidade (Sc)', 'Custo (R$)']
                    st.dataframe(format_dataframe(df_movs[cols_diaria]))
                    st.download_button(
                        label="Exportar Visão Diária para Excel",
                        data=export_to_excel(df_movs[cols_diaria], "movimentacoes_diarias"),
                        file_name="movimentacoes_diarias.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    
                    # Gráficos Diários
                    fig = px.bar(df_movs, x='Data', y='Quantidade (Ton)', color='Destino', title="Volume por Destino (Diário)")
                    st.plotly_chart(fig, use_container_width=True)
                    
                    fig_custo = px.pie(df_movs, values='Custo (R$)', names='Origem', title="Distribuição de Custos por Origem")
                    st.plotly_chart(fig_custo, use_container_width=True)
                
                elif visao == "Mensal":
                    # Agrupamento Mensal
                    df_mes_total = df_movs.groupby('Mês').agg({
                        'Quantidade (Ton)': 'sum', 
                        'Quantidade (Sc)': 'sum', 
                        'Custo (R$)': 'sum'
                    }).reset_index()
                    
                    df_mes_rotas = df_movs.groupby(['Mês', 'Origem', 'Destino']).agg({
                        'Quantidade (Ton)': 'sum',
                        'Quantidade (Sc)': 'sum',
                        'Custo (R$)': 'sum'
                    }).reset_index()
                    
                    col_m1, col_m2, col_m3 = st.columns([2, 1, 1])
                    with col_m1:
                        st.write("**Resumo Total por Mês**")
                        st.dataframe(format_dataframe(df_mes_total), hide_index=True)
                        st.download_button(
                            label="Exportar Resumo Mensal para Excel",
                            data=export_to_excel(df_mes_total, "resumo_mensal"),
                            file_name="resumo_mensal.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    with col_m2:
                        st.write("**Indicadores Tonelada**")
                        st.metric("Total Movimentado (Ton)", format_volume(df_mes_total['Quantidade (Ton)'].sum()))
                        st.metric("Custo Total (R$)", format_valor(df_mes_total['Custo (R$)'].sum()))
                    with col_m3:
                        st.write("**Indicadores Sacas**")
                        st.metric("Total Movimentado (Sc)", format_volume(df_mes_total['Quantidade (Sc)'].sum()))
                    
                    st.write("**Detalhamento Mensal por Rota**")
                    st.dataframe(format_dataframe(df_mes_rotas), hide_index=True)
                    st.download_button(
                        label="Exportar Detalhamento Mensal para Excel",
                        data=export_to_excel(df_mes_rotas, "detalhamento_mensal"),
                        file_name="detalhamento_mensal.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    
                    # Gráficos Mensais
                    fig_mes = px.bar(df_mes_rotas, x='Mês', y='Quantidade (Ton)', color='Destino', title="Volume Total Mensal por Destino", barmode='group')
                    st.plotly_chart(fig_mes, use_container_width=True)
                    
                    fig_custo_mes = px.bar(df_mes_rotas, x='Mês', y='Custo (R$)', color='Origem', title="Custo de Frete Mensal por Origem", barmode='group')
                    st.plotly_chart(fig_custo_mes, use_container_width=True)
                    
                elif visao == "Resumo Fábricas":
                    resumos_fab = session.query(ResumoMensalFabrica).all()
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
                        st.download_button(
                            label="Exportar Resumo Fábricas para Excel",
                            data=export_to_excel(df_rf, "resumo_fabricas"),
                            file_name="resumo_fabricas.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    else:
                        st.info("Nenhum resumo de fábrica gerado. Rode a otimização primeiro.")
                        
                elif visao == "Resumo Armazéns":
                    resumos_arm = session.query(ResumoMensalArmazem).all()
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
                        st.download_button(
                            label="Exportar Resumo Armazéns para Excel",
                            data=export_to_excel(df_ra, "resumo_armazens"),
                            file_name="resumo_armazens.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    else:
                        st.info("Nenhum resumo de armazém gerado. Rode a otimização primeiro.")
                    
            else:
                st.info(f"Nenhuma movimentação encontrada para o período {data_ini} a {data_fim}.")
        except Exception as e:
            st.error(f"Erro ao carregar dashboard: {e}")

    elif choice == "Carga de Dados":
        st.subheader("Gerenciamento e Carga de Dados via XLSX")
        
        st.info("Utilize os templates disponíveis na pasta 'templates'.")
        
        with st.expander("⚠️ Área de Perigo: Limpar Banco de Dados"):
            st.warning("Esta ação apagará **todos** os dados do sistema e reiniciará os identificadores (IDs). Use com cuidado, pois é irreversível.")
            if st.button("Apagar todos os dados e reiniciar identidades", type="primary"):
                with st.spinner("Limpando banco de dados..."):
                    success, msg = clear_database()
                    if success:
                        st.success(msg)
                    else:
                        st.error(msg)
        
        col_c1, col_c2 = st.columns(2)
        
        with col_c1:
            file_fab = st.file_uploader("Upload Fábricas", type=["xlsx"])
            if file_fab:
                if st.button("Carregar Fábricas"):
                    try:
                        c = load_factories(file_fab)
                        st.success(f"{c} fábricas carregadas com sucesso!")
                    except Exception as e:
                        st.error(f"Erro ao carregar fábricas: {e}")
                    
            file_arm = st.file_uploader("Upload Armazéns", type=["xlsx"])
            if file_arm:
                if st.button("Carregar Armazéns"):
                    try:
                        c = load_warehouses(file_arm)
                        st.success(f"{c} armazéns carregados com sucesso!")
                    except Exception as e:
                        st.error(f"Erro ao carregar armazéns: {e}")
        
        with col_c2:
            file_rot = st.file_uploader("Upload Rotas", type=["xlsx"])
            if file_rot:
                if st.button("Carregar Rotas"):
                    try:
                        c, s = load_routes(file_rot)
                        st.success(f"{c} rotas carregadas com sucesso!")
                        if s > 0:
                            st.warning(f"{s} rotas ignoradas por não encontrar origem ou destino.")
                    except Exception as e:
                        st.error(f"Erro ao carregar rotas: {e}")
                    
            file_prev = st.file_uploader("Upload Previsões Mensais", type=["xlsx"])
            if file_prev:
                if st.button("Carregar Previsões"):
                    try:
                        c, s = load_previsoes(file_prev)
                        st.success(f"{c} previsões carregadas com sucesso!")
                        if s > 0:
                            st.warning(f"{s} previsões ignoradas por não encontrar a entidade.")
                    except Exception as e:
                        st.error(f"Erro ao carregar previsões: {e}")

    elif choice == "Visualizar Dados":
        st.subheader("Visualização das Tabelas do Banco de Dados")
        
        tabela = st.selectbox("Selecione a Tabela", ["Fábricas", "Armazéns", "Rotas", "Previsões Fábrica", "Previsões Armazém", "Movimentações Diárias"])
        
        if tabela == "Fábricas":
            dados = session.query(Fabrica).all()
            if dados:
                df = pd.DataFrame([vars(d) for d in dados]).drop('_sa_instance_state', axis=1)
                st.dataframe(format_dataframe(df))
                st.download_button(
                    label="Exportar para Excel",
                    data=export_to_excel(df, "fabricas"),
                    file_name="fabricas.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("Tabela de Fábricas está vazia.")
                
        elif tabela == "Armazéns":
            dados = session.query(Armazem).all()
            if dados:
                df = pd.DataFrame([vars(d) for d in dados]).drop('_sa_instance_state', axis=1)
                st.dataframe(format_dataframe(df))
                st.download_button(
                    label="Exportar para Excel",
                    data=export_to_excel(df, "armazens"),
                    file_name="armazens.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("Tabela de Armazéns está vazia.")
                
        elif tabela == "Rotas":
            dados = session.query(Rota).all()
            if dados:
                df = pd.DataFrame([{
                    'ID': d.id,
                    'Origem (Armazém)': session.query(Armazem).get(d.armazem_id).nome if session.query(Armazem).get(d.armazem_id) else "N/A",
                    'Destino (Fábrica)': session.query(Fabrica).get(d.fabrica_id).nome if session.query(Fabrica).get(d.fabrica_id) else "N/A",
                    'Distância (km)': d.distancia_km,
                    'Custo Frete (Ton)': d.custo_frete_ton
                } for d in dados])
                st.dataframe(format_dataframe(df))
                st.download_button(
                    label="Exportar para Excel",
                    data=export_to_excel(df, "rotas"),
                    file_name="rotas.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("Tabela de Rotas está vazia.")
                
        elif tabela == "Previsões Fábrica":
            dados = session.query(PrevisaoFabrica).all()
            if dados:
                df = pd.DataFrame([{
                    'Fábrica': session.query(Fabrica).get(d.fabrica_id).nome if session.query(Fabrica).get(d.fabrica_id) else "N/A",
                    'Mês': d.mes_referencia,
                    'Recebimento Produtor': d.recebimento_produtor,
                    'Vendas': d.vendas,
                    'Safra': d.eh_safra
                } for d in dados])
                st.dataframe(format_dataframe(df))
                st.download_button(
                    label="Exportar para Excel",
                    data=export_to_excel(df, "previsoes_fabrica"),
                    file_name="previsoes_fabrica.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("Tabela de Previsões Fábrica está vazia.")

        elif tabela == "Previsões Armazém":
            dados = session.query(PrevisaoArmazem).all()
            if dados:
                df = pd.DataFrame([{
                    'Armazém': session.query(Armazem).get(d.armazem_id).nome if session.query(Armazem).get(d.armazem_id) else "N/A",
                    'Mês': d.mes_referencia,
                    'Recebimento Produtor': d.recebimento_produtor,
                    'Vendas': d.vendas,
                    'Safra': d.eh_safra
                } for d in dados])
                st.dataframe(format_dataframe(df))
                st.download_button(
                    label="Exportar para Excel",
                    data=export_to_excel(df, "previsoes_armazem"),
                    file_name="previsoes_armazem.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("Tabela de Previsões Armazém está vazia.")

        elif tabela == "Movimentações Diárias":
            dados = session.query(MovimentacaoDiaria).all()
            if dados:
                df = pd.DataFrame([{
                    'Data': d.data,
                    'Origem': session.query(Armazem).get(d.armazem_id).nome,
                    'Destino': session.query(Fabrica).get(d.fabrica_id).nome,
                    'Quantidade (Ton)': d.quantidade_ton,
                    'Quantidade (Sc)': d.quantidade_ton * 1000 / 60,
                    'Custo Total': d.custo_total
                } for d in dados])
                st.dataframe(format_dataframe(df))
                st.download_button(
                    label="Exportar para Excel",
                    data=export_to_excel(df, "movimentacoes"),
                    file_name="movimentacoes.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("Tabela de Movimentações está vazia.")

    elif choice == "Otimização":
        st.subheader("Executar Otimização de Transbordo")
        
        # Tentar obter range sugerido
        d_sug_ini, d_sug_fim = obter_range_previsoes(session)
        
        col1, col2 = st.columns(2)
        with col1:
            d_ini = st.date_input("Início da Simulação", d_sug_ini if d_sug_ini else datetime.date.today())
        with col2:
            d_fim = st.date_input("Fim da Simulação", d_sug_fim if d_sug_fim else datetime.date.today() + datetime.timedelta(days=30))
            
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            if st.button("Rodar Otimização (Período Selecionado)", use_container_width=True):
                with st.spinner("Otimizando..."):
                    try:
                        simular_periodo(session, d_ini, d_fim)
                        st.success("Otimização concluída!")
                    except Exception as e:
                        st.error(f"Erro na otimização: {e}")
        with col_b2:
            if st.button("Otimizar tudo (Base Completa de Previsões)", use_container_width=True):
                if d_sug_ini and d_sug_fim:
                    with st.spinner(f"Otimizando de {d_sug_ini} até {d_sug_fim}..."):
                        try:
                            simular_periodo(session, d_sug_ini, d_sug_fim)
                            st.success("Otimização total concluída!")
                        except Exception as e:
                            st.error(f"Erro na otimização total: {e}")
                else:
                    st.warning("Não foram encontradas previsões para definir o período total.")

    session.close()

if __name__ == "__main__":
    main()
