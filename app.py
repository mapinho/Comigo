import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date

from models import SessionLocal, Factory, Warehouse, DailyLogFactory, DailyLogWarehouse, FreightTransfer, init_db
from data_loader import load_factories, load_warehouses, load_routes, load_daily_updates
from calculations import run_simulation
from generate_templates import generate_templates
import os

st.set_page_config(page_title="Sistema de Transbordo - Dashboard", layout="wide")

# Initialize DB on first run
@st.cache_resource
def setup_db():
    init_db()
    if not os.path.exists('templates'):
        generate_templates()

setup_db()

st.title("Sistema de Gestão de Transbordo de Soja")

tabs = st.tabs(["Dashboard", "Simulação & Movimentações", "Comparativo Previsto x Realizado", "Carga de Dados"])

def get_data():
    session = SessionLocal()
    try:
        factories = pd.read_sql(session.query(Factory).statement, session.bind)
        warehouses = pd.read_sql(session.query(Warehouse).statement, session.bind)
        daily_f = pd.read_sql(session.query(DailyLogFactory).statement, session.bind)
        daily_w = pd.read_sql(session.query(DailyLogWarehouse).statement, session.bind)
        transfers = pd.read_sql(session.query(FreightTransfer).statement, session.bind)
        return factories, warehouses, daily_f, daily_w, transfers
    finally:
        session.close()

factories_df, warehouses_df, daily_f_df, daily_w_df, transfers_df = get_data()

with tabs[0]:
    st.header("Visão Geral dos Estoques (Previsto)")
    
    if not daily_f_df.empty:
        # Merge with factory names
        daily_f_df = daily_f_df.merge(factories_df[['id', 'name']], left_on='factory_id', right_on='id', suffixes=('', '_factory'))
        daily_f_df['Entity'] = daily_f_df['name']
        daily_f_df['Type'] = 'Fábrica'
        
        daily_w_df = daily_w_df.merge(warehouses_df[['id', 'name']], left_on='warehouse_id', right_on='id', suffixes=('', '_warehouse'))
        daily_w_df['Entity'] = daily_w_df['name']
        daily_w_df['Type'] = 'Armazém'

        # Filter by Date
        min_date = pd.to_datetime(daily_f_df['date']).min().date()
        max_date = pd.to_datetime(daily_f_df['date']).max().date()
        
        selected_date = st.slider("Selecione a Data", min_value=min_date, max_value=max_date, value=min_date)

        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Fábricas")
            df_f_filtered = daily_f_df[pd.to_datetime(daily_f_df['date']).dt.date == selected_date]
            fig_f = px.bar(df_f_filtered, x='Entity', y='estimated_stock', title=f"Estoque Estimado - Fábricas ({selected_date})", text='estimated_stock')
            st.plotly_chart(fig_f, use_container_width=True)

        with col2:
            st.subheader("Armazéns")
            df_w_filtered = daily_w_df[pd.to_datetime(daily_w_df['date']).dt.date == selected_date]
            if not df_w_filtered.empty:
                fig_w = px.bar(df_w_filtered, x='Entity', y='estimated_stock', title=f"Estoque Estimado - Armazéns ({selected_date})", text='estimated_stock')
                st.plotly_chart(fig_w, use_container_width=True)
            else:
                st.info("Sem dados de armazéns para a data.")

with tabs[1]:
    st.header("Movimentação de Cargas e Caminhões")
    
    if not transfers_df.empty:
        transfers_df = transfers_df.merge(warehouses_df[['id', 'name']], left_on='warehouse_id', right_on='id')
        transfers_df = transfers_df.rename(columns={'name': 'Armazém'})
        transfers_df = transfers_df.merge(factories_df[['id', 'name']], left_on='factory_id', right_on='id')
        transfers_df = transfers_df.rename(columns={'name': 'Fábrica'})

        st.subheader("Histórico de Transferências")
        st.dataframe(transfers_df[['date', 'Armazém', 'Fábrica', 'amount_tons', 'vehicles_used', 'total_freight_cost']])

        # Group by Route
        route_group = transfers_df.groupby(['Armazém', 'Fábrica']).sum(numeric_only=True).reset_index()
        fig_routes = px.bar(route_group, x='Armazém', y='amount_tons', color='Fábrica', barmode='group', title="Total Transferido por Rota (Tons)")
        st.plotly_chart(fig_routes, use_container_width=True)

        st.subheader("Caminhões em Espera nas Fábricas")
        if not daily_f_df.empty:
            fig_trucks = px.line(daily_f_df, x='date', y='waiting_trucks_estimated', color='Entity', title="Previsão de Caminhões em Espera por Dia")
            st.plotly_chart(fig_trucks, use_container_width=True)

with tabs[2]:
    st.header("Comparativo: Previsto x Realizado")
    if not daily_f_df.empty:
        df_real_f = daily_f_df.dropna(subset=['real_stock']).copy()
        if not df_real_f.empty:
            st.subheader("Fábricas - Estoque")
            for f_name in df_real_f['Entity'].unique():
                df_f_spec = df_real_f[df_real_f['Entity'] == f_name]
                fig_comp = px.line(df_f_spec, x='date', y=['estimated_stock', 'real_stock'], title=f"{f_name}: Estimado vs Real")
                st.plotly_chart(fig_comp, use_container_width=True)
        else:
            st.info("Nenhum dado real de estoque atualizado para fábricas ainda.")
            
    if not daily_w_df.empty:
        df_real_w = daily_w_df.dropna(subset=['real_stock']).copy()
        if not df_real_w.empty:
            st.subheader("Armazéns - Estoque")
            # Only show first 5 to not overload
            for w_name in df_real_w['Entity'].unique()[:5]:
                df_w_spec = df_real_w[df_real_w['Entity'] == w_name]
                fig_comp_w = px.line(df_w_spec, x='date', y=['estimated_stock', 'real_stock'], title=f"{w_name}: Estimado vs Real")
                st.plotly_chart(fig_comp_w, use_container_width=True)
        else:
            st.info("Nenhum dado real de estoque atualizado para armazéns ainda.")


with tabs[3]:
    st.header("Carga de Dados e Simulação")
    
    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        st.subheader("1. Fazer Download dos Templates")
        with open("templates/factories_template.xlsx", "rb") as file:
            st.download_button(label="Template Fábricas", data=file, file_name="factories_template.xlsx")
        with open("templates/warehouses_template.xlsx", "rb") as file:
            st.download_button(label="Template Armazéns", data=file, file_name="warehouses_template.xlsx")
        with open("templates/routes_template.xlsx", "rb") as file:
            st.download_button(label="Template Rotas", data=file, file_name="routes_template.xlsx")
        with open("templates/daily_updates_template.xlsx", "rb") as file:
            st.download_button(label="Template Atualizações Reais", data=file, file_name="daily_updates_template.xlsx")
            
    with col_dl2:
        st.subheader("2. Fazer Upload dos Dados")
        factories_file = st.file_uploader("Upload Fábricas (.xlsx)", type=["xlsx"])
        warehouses_file = st.file_uploader("Upload Armazéns (.xlsx)", type=["xlsx"])
        routes_file = st.file_uploader("Upload Rotas (.xlsx)", type=["xlsx"])
        updates_file = st.file_uploader("Upload Atualizações Diárias (.xlsx)", type=["xlsx"])

        if st.button("Carregar Dados Iniciais"):
            if factories_file: load_factories(factories_file)
            if warehouses_file: load_warehouses(warehouses_file)
            if routes_file: load_routes(routes_file)
            st.success("Dados base carregados com sucesso!")
            
        if updates_file and st.button("Carregar Atualizações Reais"):
            load_daily_updates(updates_file)
            st.success("Atualizações carregadas com sucesso!")

    st.subheader("3. Executar Simulação")
    sim_days = st.number_input("Dias para Simulação", min_value=1, max_value=365, value=30)
    sim_start = st.date_input("Data de Início da Simulação", value=date.today())
    if st.button("Rodar Simulação Diária"):
        with st.spinner("Simulando as movimentações..."):
            run_simulation(start_date=sim_start, num_days=sim_days)
        st.success("Simulação concluída! Recarregue a página (ou clique em outra aba) para ver os dados atualizados no Dashboard.")
