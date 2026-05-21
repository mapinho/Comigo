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
    # 1. Busca no st.secrets (forma segura)
    user, password, host, port, db = None, None, None, None, None
    url = None
    source = "Nenhum"
    
    config_from_secrets = False
    try:
        # Tenta acessar postgres de forma ultra segura
        if st.secrets and "postgres" in st.secrets:
            s = st.secrets["postgres"]
            if "uri" in s:
                url = s["uri"]
                config_from_secrets = True
                source = "Streamlit Secrets (URI)"
            else:
                user = s.get("user")
                password = s.get("password")
                host = s.get("host")
                port = str(s.get("port", "5432"))
                db = s.get("database")
                if user and password and host and db:
                    config_from_secrets = True
                    source = "Streamlit Secrets (Campos)"
    except Exception:
        # Localmente sem secrets.toml, st.secrets falha. Ignoramos.
        pass

    # 2. Busca no ambiente (Local via .env ou OS)
    if not config_from_secrets:
        user = os.getenv("DB_USER")
        password = os.getenv("DB_PASSWORD")
        host = os.getenv("DB_HOST")
        port = os.getenv("DB_PORT", "5432")
        db = os.getenv("DB_NAME")
        if user and host and db:
            source = "Variáveis de Ambiente (.env)"

    # 3. Tratamento de Fallback e Identificação de Nuvem
    is_cloud = os.getenv("STREAMLIT_RUNTIME_ENV") or "STREAMLIT_SERVER_PORT" in os.environ
    
    if not url and not all([user, password, host, db]):
        if is_cloud:
            raise ConnectionError("Secrets não detectados na nuvem. Verifique o painel do Streamlit.")
        
        # Padrão apenas para DESENVOLVIMENTO LOCAL
        user, password, host, port, db = "comigo", "Comigo36908!", "localhost", "5432", "comigo"
        source = "Padrão Local (Desenvolvimento)"

    if not url:
        import urllib.parse
        u = urllib.parse.quote_plus(str(user))
        p = urllib.parse.quote_plus(str(password))
        url = f"postgresql://{u}:{p}@{host}:{port}/{db}"

    # Dialeto e SSL
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    
    if "sslmode" not in url:
        # Só exige SSL se NÃO for localhost (local costuma não ter SSL configurado)
        is_local = any(x in url for x in ["@localhost", "@127.0.0.1", "@[::1]"])
        if not is_local:
            url += ("&" if "?" in url else "?") + "sslmode=require"
        
    return create_engine(url, pool_pre_ping=True), source

def init_db():
    try:
        engine, source = get_engine()
        # Ping de teste
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        Base.metadata.create_all(engine)
        return sessionmaker(bind=engine)()
    except Exception as e:
        st.error("### ❌ Erro de Conexão com o Banco de Dados")
        
        # Painel de Diagnóstico Seguro
        st.write(f"**Origem das credenciais detectada:** `{source if 'source' in locals() else 'Erro antes da detecção'}`")
        
        with st.expander("🔍 Painel de Diagnóstico (Ajuda no Debug)"):
            try:
                if st.secrets:
                    st.write("Chaves presentes no seu `st.secrets`:", list(st.secrets.keys()))
                    if "postgres" in st.secrets:
                        st.write("Sub-chaves em `[postgres]`:", list(st.secrets["postgres"].keys()))
            except Exception:
                st.write("Streamlit Secrets não configurado ou inacessível (normal em ambiente local).")
            
            st.write("**Erro Técnico:**")
            st.code(str(e))
        
        st.stop()
        return None

def upgrade_db():
    try:
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
                    pass
    except Exception:
        pass

def clear_database():
    session = init_db()
    if not session: return False, "Erro ao inicializar banco."
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
    if not session: return 0
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
    if not session: return 0
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
    if not session: return 0, 0
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
    if not session: return 0, 0
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
