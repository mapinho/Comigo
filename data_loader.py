import pandas as pd
import os
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from models import Base, Fabrica, Armazem, Rota, PrevisaoFabrica, PrevisaoArmazem
from dotenv import load_dotenv

# Carrega .env apenas se o arquivo existir (ambiente local)
if os.path.exists(".env"):
    load_dotenv()

def get_engine():
    # 1. Tenta pegar do st.secrets (Streamlit Cloud)
    # 2. Se falhar, tenta do os.environ (Local com .env)
    
    try:
        if hasattr(st, "secrets") and "postgres" in st.secrets:
            s = st.secrets["postgres"]
            user = s.get("user")
            password = s.get("password")
            host = s.get("host")
            port = str(s.get("port", "5432"))
            db = s.get("database")
            if not all([user, password, host, db]):
                raise KeyError("Alguns campos obrigatorios estao faltando em st.secrets['postgres']")
        else:
            raise KeyError("Chave 'postgres' nao encontrada em st.secrets")
    except (KeyError, AttributeError, FileNotFoundError):
        user = os.getenv("DB_USER", "comigo")
        password = os.getenv("DB_PASSWORD", "Comigo36908!")
        host = os.getenv("DB_HOST", "localhost")
        port = os.getenv("DB_PORT", "5432")
        db = os.getenv("DB_NAME", "comigo")
    
    # Adiciona sslmode=require para compatibilidade obrigatoria com Aiven.io
    url = f"postgresql://{user}:{password}@{host}:{port}/{db}?sslmode=require"
    
    # Tratamento para DATABASE_URL (caso use Heroku ou similar)
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        url = env_url.replace("postgres://", "postgresql://", 1)
        if "?" not in url:
            url += "?sslmode=require"
        
    return create_engine(url, pool_pre_ping=True)

def init_db():
    engine = get_engine()
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()

def upgrade_db():
    engine = get_engine()
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        tables_to_upgrade = [
            'fabricas', 'armazens', 'rotas', 
            'movimentacoes_diarias', 'resumo_mensal_fabrica', 'resumo_mensal_armazem'
        ]
        for table in tables_to_upgrade:
            try:
                conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN cenario_id INTEGER REFERENCES cenarios(id) ON DELETE CASCADE;'))
                conn.commit()
            except Exception:
                # Column probably already exists
                pass

def clear_database():
    session = init_db()
    try:
        # Pega as tabelas na ordem reversa de dependência
        tables = [table.name for table in reversed(Base.metadata.sorted_tables)]
        for table in tables:
            session.execute(text(f'TRUNCATE TABLE "{table}" RESTART IDENTITY CASCADE;'))
        session.commit()
        return True, "Banco de dados limpo e identidades reiniciadas com sucesso."
    except Exception as e:
        session.rollback()
        return False, f"Erro ao limpar banco de dados: {str(e)}"
    finally:
        session.close()

def load_factories(file_path):
    df = pd.read_excel(file_path)
    session = init_db()
    session.query(Fabrica).filter(Fabrica.cenario_id == None).delete()
    count = 0
    for _, row in df.iterrows():
        nome = row.get('nome')
        if pd.isna(nome):
            continue
        fabrica = Fabrica(
            cenario_id=None,
            nome=str(nome).strip(),
            capacidade_estatica=row['capacidade_estatica'],
            capacidade_esmagamento_diaria=row['capacidade_esmagamento_diaria'],
            capacidade_recebimento_diaria=row['capacidade_recebimento_diaria'],
            limite_caminhoes=row['limite_caminhoes'],
            carga_media_caminhao=row['carga_media_caminhao'],
            estoque_inicial=row['estoque_inicial']
        )
        session.add(fabrica)
        count += 1
    session.commit()
    session.close()
    return count

def load_warehouses(file_path):
    df = pd.read_excel(file_path)
    session = init_db()
    session.query(Armazem).filter(Armazem.cenario_id == None).delete()
    count = 0
    for _, row in df.iterrows():
        nome = row.get('nome')
        if pd.isna(nome):
            continue
        armazem = Armazem(
            cenario_id=None,
            nome=str(nome).strip(),
            capacidade_estatica=row['capacidade_estatica'],
            capacidade_expedicao_diaria=row['capacidade_expedicao_diaria'],
            estoque_inicial=row['estoque_inicial']
        )
        session.add(armazem)
        count += 1
    session.commit()
    session.close()
    return count

def load_routes(file_path):
    df = pd.read_excel(file_path)
    session = init_db()
    session.query(Rota).filter(Rota.cenario_id == None).delete()
    count = 0
    skipped = 0
    for _, row in df.iterrows():
        origem = str(row['origem']).strip()
        destino = str(row['destino']).strip()

        armazem = session.query(Armazem).filter(Armazem.nome == origem, Armazem.cenario_id == None).first()
        fabrica = session.query(Fabrica).filter(Fabrica.nome == destino, Fabrica.cenario_id == None).first()

        if armazem and fabrica:
            rota = Rota(
                cenario_id=None,
                armazem_id=armazem.id,
                fabrica_id=fabrica.id,
                distancia_km=row['distancia_km'],
                custo_frete_ton=row['custo_frete_ton']
            )
            session.add(rota)
            count += 1
        else:
            skipped += 1
    session.commit()
    session.close()
    return count, skipped

def load_previsoes(file_path):
    df = pd.read_excel(file_path)
    session = init_db()
    # Deletar previsões que pertencem a fábricas/armazéns do Baseline
    baseline_fab_ids = [f.id for f in session.query(Fabrica.id).filter(Fabrica.cenario_id == None).all()]
    baseline_arm_ids = [a.id for a in session.query(Armazem.id).filter(Armazem.cenario_id == None).all()]
    session.query(PrevisaoFabrica).filter(PrevisaoFabrica.fabrica_id.in_(baseline_fab_ids)).delete(synchronize_session=False)
    session.query(PrevisaoArmazem).filter(PrevisaoArmazem.armazem_id.in_(baseline_arm_ids)).delete(synchronize_session=False)
    
    count = 0
    skipped = 0
    for _, row in df.iterrows():
        nome_entidade = str(row['entidade']).strip()
        mes_ref = pd.to_datetime(row['mes_referencia']).date().replace(day=1)
        
        # Tenta achar como fabrica no baseline
        fabrica = session.query(Fabrica).filter(Fabrica.nome == nome_entidade, Fabrica.cenario_id == None).first()
        if fabrica:
            prev = PrevisaoFabrica(
                fabrica_id=fabrica.id,
                mes_referencia=mes_ref,
                recebimento_produtor=row.get('recebimento_produtor', 0),
                vendas=row.get('vendas', 0),
                eh_safra=row.get('eh_safra', 0)
            )
            session.add(prev)
            count += 1
            continue
            
        # Tenta achar como armazem no baseline
        armazem = session.query(Armazem).filter(Armazem.nome == nome_entidade, Armazem.cenario_id == None).first()
        if armazem:
            prev = PrevisaoArmazem(
                armazem_id=armazem.id,
                mes_referencia=mes_ref,
                recebimento_produtor=row.get('recebimento_produtor', 0),
                vendas=row.get('vendas', 0),
                eh_safra=row.get('eh_safra', 0)
            )
            session.add(prev)
            count += 1
        else:
            skipped += 1
            
    session.commit()
    session.close()
    return count, skipped
