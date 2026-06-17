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

@st.cache_resource
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
        import logging
        logging.getLogger(__name__).debug("st.secrets falhou; assumindo ambiente local.")

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
        
        # Só executa create_all e upgrade_db uma vez por execução do app
        if 'db_initialized' not in st.session_state:
            # Ping de teste
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            Base.metadata.create_all(engine)
            
            # Chama upgrade_db para garantir que colunas novas existam
            upgrade_db(engine)
            st.session_state.db_initialized = True
        
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

def upgrade_db(engine=None):
    try:
        if engine is None:
            engine, _ = get_engine()
            
        with engine.connect() as conn:
            # 0. Adiciona is_oficial na tabela cenarios
            try:
                conn.execute(text('ALTER TABLE "cenarios" ADD COLUMN is_oficial BOOLEAN DEFAULT FALSE;'))
                conn.commit()
            except Exception as e:
                import logging
                logging.getLogger(__name__).debug(f"Coluna is_oficial pode já existir: {e}")

            # 1. Adiciona cenario_id em várias tabelas
            tables_to_upgrade = [
                'fabricas', 'armazens', 'rotas', 
                'movimentacoes_diarias', 'resumo_mensal_fabrica', 'resumo_mensal_armazem', 'safras_unidades'
            ]
            for table in tables_to_upgrade:
                try:
                    conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN cenario_id INTEGER REFERENCES cenarios(id) ON DELETE CASCADE;'))
                    conn.commit()
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).debug(f"Coluna cenario_id na tabela {table} pode já existir: {e}")
            
            # 2. Adiciona custo_frete_entressafra na tabela rotas
            try:
                conn.execute(text('ALTER TABLE "rotas" ADD COLUMN custo_frete_entressafra FLOAT DEFAULT 0;'))
                conn.commit()
                # Opcional: inicializa com o valor da safra se estiver zerado
                conn.execute(text('UPDATE "rotas" SET custo_frete_entressafra = custo_frete_ton WHERE custo_frete_entressafra = 0;'))
                conn.commit()
            except Exception as e:
                import logging
                logging.getLogger(__name__).debug(f"Coluna custo_frete_entressafra pode já existir: {e}")

            # 3. Garante existência do Cenário Oficial e Migra Dados Órfãos
            from sqlalchemy.orm import Session
            with Session(engine) as session:
                from models import Cenario
                oficial = session.query(Cenario).filter_by(is_oficial=True).first()
                if not oficial:
                    # Tenta reaproveitar um 'Oficial' existente ou cria novo
                    oficial = session.query(Cenario).filter_by(nome='Oficial (Planejado)').first()
                    if oficial:
                        oficial.is_oficial = True
                    else:
                        oficial = Cenario(nome='Oficial (Planejado)', is_oficial=True)
                        session.add(oficial)
                    session.commit()
                
                oficial_id = oficial.id
                
                # Migra registros NULL para o ID Oficial
                for table in tables_to_upgrade:
                    try:
                        session.execute(text(f'UPDATE "{table}" SET cenario_id = :oid WHERE cenario_id IS NULL'), {'oid': oficial_id})
                    except Exception as e:
                        import logging
                        logging.getLogger(__name__).debug(f"Falha ao migrar dados órfãos da tabela {table}: {e}")
                session.commit()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Erro ao atualizar estrutura do banco de dados: {e}")

def clear_database(session=None):
    close_session = False
    if not session:
        session = init_db()
        close_session = True
        
    if not session: return False, "Erro ao inicializar banco."
    try:
        # Pega as tabelas na ordem reversa de dependência
        tables = [table.name for table in reversed(Base.metadata.sorted_tables)]
        
        # Detecta se é SQLite
        is_sqlite = session.bind.dialect.name == 'sqlite'
        
        for table in tables:
            if is_sqlite:
                session.execute(text(f'DELETE FROM "{table}";'))
            else:
                session.execute(text(f'TRUNCATE TABLE "{table}" RESTART IDENTITY CASCADE;'))
        
        if is_sqlite:
            # Reseta sequências no SQLite
            session.execute(text("DELETE FROM sqlite_sequence;"))
            
        session.commit()
        return True, "Banco de dados limpo e identidades reiniciadas com sucesso."
    except Exception as e:
        session.rollback()
        return False, f"Erro ao limpar banco de dados: {str(e)}"
    finally:
        if close_session:
            session.close()

def load_factories(file_path, cenario_id, session=None):
    df = pd.read_excel(file_path)
    df.columns = [str(col).strip().lower() for col in df.columns]
    close_session = False
    if not session:
        session = init_db()
        close_session = True
    
    if not session: return 0
    count = 0
    for _, row in df.iterrows():
        nome = str(row.get('nome')).strip()
        if pd.isna(nome) or nome == 'nan':
            continue
        
        # UPSERT logic
        fabrica = session.query(Fabrica).filter_by(cenario_id=cenario_id, nome=nome).first()
        if not fabrica:
            fabrica = Fabrica(cenario_id=cenario_id, nome=nome)
            session.add(fabrica)
        
        fabrica.capacidade_estatica = row['capacidade_estatica']
        fabrica.capacidade_esmagamento_diaria = row['capacidade_esmagamento_diaria']
        fabrica.capacidade_recebimento_diaria = row['capacidade_recebimento_diaria']
        fabrica.limite_caminhoes = row['limite_caminhoes']
        fabrica.carga_media_caminhao = row['carga_media_caminhao']
        fabrica.estoque_inicial = row['estoque_inicial']
        count += 1
    session.commit()
    if close_session:
        session.close()
    return count

def load_warehouses(file_path, cenario_id, session=None):
    df = pd.read_excel(file_path)
    df.columns = [str(col).strip().lower() for col in df.columns]
    close_session = False
    if not session:
        session = init_db()
        close_session = True
        
    if not session: return 0
    count = 0
    for _, row in df.iterrows():
        nome = str(row.get('nome')).strip()
        if pd.isna(nome) or nome == 'nan':
            continue
        
        # UPSERT logic
        armazem = session.query(Armazem).filter_by(cenario_id=cenario_id, nome=nome).first()
        if not armazem:
            armazem = Armazem(cenario_id=cenario_id, nome=nome)
            session.add(armazem)
            
        armazem.capacidade_estatica = row['capacidade_estatica']
        armazem.capacidade_expedicao_diaria = row['capacidade_expedicao_diaria']
        armazem.estoque_inicial = row['estoque_inicial']
        count += 1
    session.commit()
    if close_session:
        session.close()
    return count

def load_routes(file_path, cenario_id, session=None):
    df = pd.read_excel(file_path)
    df.columns = [str(col).strip().lower() for col in df.columns]
    close_session = False
    if not session:
        session = init_db()
        close_session = True
        
    if not session: return 0, 0
    count = 0
    skipped = 0
    for _, row in df.iterrows():
        origem = str(row['origem']).strip()
        destino = str(row['destino']).strip()

        armazem = session.query(Armazem).filter(Armazem.nome == origem, Armazem.cenario_id == cenario_id).first()
        fabrica = session.query(Fabrica).filter(Fabrica.nome == destino, Fabrica.cenario_id == cenario_id).first()

        if armazem and fabrica:
            # UPSERT logic
            rota = session.query(Rota).filter_by(cenario_id=cenario_id, armazem_id=armazem.id, fabrica_id=fabrica.id).first()
            if not rota:
                rota = Rota(cenario_id=cenario_id, armazem_id=armazem.id, fabrica_id=fabrica.id)
                session.add(rota)
            
            rota.distancia_km = row['distancia_km']
            rota.custo_frete_ton = row['custo_frete_ton']
            rota.custo_frete_entressafra = row.get('custo_frete_entressafra', row['custo_frete_ton'])
            count += 1
        else:
            skipped += 1
    session.commit()
    if close_session:
        session.close()
    return count, skipped

def load_previsoes(file_path, cenario_id, session=None):
    df = pd.read_excel(file_path)
    df.columns = [str(col).strip().lower() for col in df.columns]
    close_session = False
    if not session:
        session = init_db()
        close_session = True
        
    if not session: return 0, 0
    
    count = 0
    skipped = 0
    for _, row in df.iterrows():
        nome_entidade = str(row['entidade']).strip()
        mes_ref = pd.to_datetime(row['mes_referencia']).date().replace(day=1)
        
        # Tenta achar como fabrica no cenario
        fabrica = session.query(Fabrica).filter(Fabrica.nome == nome_entidade, Fabrica.cenario_id == cenario_id).first()
        if fabrica:
            # UPSERT logic
            prev = session.query(PrevisaoFabrica).filter_by(fabrica_id=fabrica.id, mes_referencia=mes_ref).first()
            if not prev:
                prev = PrevisaoFabrica(fabrica_id=fabrica.id, mes_referencia=mes_ref)
                session.add(prev)
            
            prev.recebimento_produtor = row.get('recebimento_produtor', 0)
            prev.vendas = row.get('vendas', 0)
            count += 1
            continue
            
        # Tenta achar como armazem no cenario
        armazem = session.query(Armazem).filter(Armazem.nome == nome_entidade, Armazem.cenario_id == cenario_id).first()
        if armazem:
            # UPSERT logic
            prev = session.query(PrevisaoArmazem).filter_by(armazem_id=armazem.id, mes_referencia=mes_ref).first()
            if not prev:
                prev = PrevisaoArmazem(armazem_id=armazem.id, mes_referencia=mes_ref)
                session.add(prev)
                
            prev.recebimento_produtor = row.get('recebimento_produtor', 0)
            prev.vendas = row.get('vendas', 0)
            count += 1
        else:
            skipped += 1
            
    session.commit()
    if close_session:
        session.close()
    return count, skipped
