import pandas as pd
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from models import Base, Fabrica, Armazem, Rota, PrevisaoFabrica, PrevisaoArmazem
from dotenv import load_dotenv

load_dotenv()

def get_engine():
    user = os.getenv("DB_USER", "comigo")
    password = os.getenv("DB_PASSWORD", "Comigo36908!")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    db = os.getenv("DB_NAME", "comigo")
    
    url = f"postgresql://{user}:{password}@{host}:{port}/{db}"
    return create_engine(url)

def init_db():
    engine = get_engine()
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()

def clear_database():
    session = init_db()
    try:
        # Pega as tabelas na ordem reversa de dependência (para evitar problemas de FK, embora o CASCADE ajude)
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
    session.query(Fabrica).delete()
    count = 0
    for _, row in df.iterrows():
        nome = row.get('nome')
        if pd.isna(nome):
            continue
        fabrica = Fabrica(
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
    session.query(Armazem).delete()
    count = 0
    for _, row in df.iterrows():
        nome = row.get('nome')
        if pd.isna(nome):
            continue
        armazem = Armazem(
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
    session.query(Rota).delete()
    count = 0
    skipped = 0
    for _, row in df.iterrows():
        origem = str(row['origem']).strip()
        destino = str(row['destino']).strip()

        armazem = session.query(Armazem).filter(Armazem.nome == origem).first()
        fabrica = session.query(Fabrica).filter(Fabrica.nome == destino).first()

        if armazem and fabrica:
            rota = Rota(
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
    session.query(PrevisaoFabrica).delete()
    session.query(PrevisaoArmazem).delete()
    count = 0
    skipped = 0
    for _, row in df.iterrows():
        nome_entidade = str(row['entidade']).strip()
        mes_ref = pd.to_datetime(row['mes_referencia']).date().replace(day=1)
        
        # Tenta achar como fabrica
        fabrica = session.query(Fabrica).filter(Fabrica.nome == nome_entidade).first()
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
            
        # Tenta achar como armazem
        armazem = session.query(Armazem).filter(Armazem.nome == nome_entidade).first()
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
