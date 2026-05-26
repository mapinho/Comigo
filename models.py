from sqlalchemy import Column, Integer, String, Float, ForeignKey, Date, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import datetime

Base = declarative_base()

class Cenario(Base):
    __tablename__ = 'cenarios'
    
    id = Column(Integer, primary_key=True, info={'label': 'ID', 'type': 'number', 'disabled': True})
    nome = Column(String(100), unique=True, nullable=False, info={'label': 'Nome do Cenário'})
    data_criacao = Column(DateTime, default=datetime.datetime.now, info={'label': 'Data de Criação', 'type': 'date', 'disabled': True})

class Fabrica(Base):
    __tablename__ = 'fabricas'
    
    id = Column(Integer, primary_key=True, info={'label': 'id', 'type': 'number', 'disabled': True})
    cenario_id = Column(Integer, ForeignKey('cenarios.id', ondelete='CASCADE'), nullable=True, info={'hidden': True})
    nome = Column(String(100), nullable=False, info={'label': 'Fábrica', 'disabled': True})
    capacidade_estatica = Column(Float, nullable=False, info={'label': 'Capacidade Estática (Ton)', 'type': 'number', 'format': '%.2f', 'step': 0.01})
    capacidade_esmagamento_diaria = Column(Float, nullable=False, info={'label': 'Esmagamento Diário (Ton)', 'type': 'number', 'format': '%.2f', 'step': 0.01})
    capacidade_recebimento_diaria = Column(Float, nullable=False, info={'label': 'Recebimento Diário (Ton)', 'type': 'number', 'format': '%.2f', 'step': 0.01})
    limite_caminhoes = Column(Integer, nullable=False, info={'label': 'Limite de Caminhões', 'type': 'number', 'format': '%.0f', 'step': 1})
    carga_media_caminhao = Column(Float, nullable=False, info={'label': 'Carga Média (Ton)', 'type': 'number', 'format': '%.2f', 'step': 0.01})
    estoque_inicial = Column(Float, nullable=False, info={'label': 'Estoque Inicial (Ton)', 'type': 'number', 'format': '%.2f', 'step': 0.01})
    
    previsoes = relationship("PrevisaoFabrica", back_populates="fabrica", cascade="all, delete-orphan")
    rotas = relationship("Rota", back_populates="fabrica", cascade="all, delete-orphan")

class Armazem(Base):
    __tablename__ = 'armazens'
    
    id = Column(Integer, primary_key=True, info={'label': 'id', 'type': 'number', 'disabled': True})
    cenario_id = Column(Integer, ForeignKey('cenarios.id', ondelete='CASCADE'), nullable=True, info={'hidden': True})
    nome = Column(String(100), nullable=False, info={'label': 'Armazém', 'disabled': True})
    capacidade_estatica = Column(Float, nullable=False, info={'label': 'Capacidade Estática (Ton)', 'type': 'number', 'format': '%.2f', 'step': 0.01})
    capacidade_expedicao_diaria = Column(Float, nullable=False, info={'label': 'Expedição Diária (Ton)', 'type': 'number', 'format': '%.2f', 'step': 0.01})
    estoque_inicial = Column(Float, nullable=False, info={'label': 'Estoque Inicial (Ton)', 'type': 'number', 'format': '%.2f', 'step': 0.01})
    
    previsoes = relationship("PrevisaoArmazem", back_populates="armazem", cascade="all, delete-orphan")
    rotas = relationship("Rota", back_populates="armazem", cascade="all, delete-orphan")

class Rota(Base):
    __tablename__ = 'rotas'
    
    id = Column(Integer, primary_key=True, info={'label': 'id', 'type': 'number', 'disabled': True})
    cenario_id = Column(Integer, ForeignKey('cenarios.id', ondelete='CASCADE'), nullable=True, info={'hidden': True})
    armazem_id = Column(Integer, ForeignKey('armazens.id', ondelete='CASCADE'), nullable=False, info={'hidden': True})
    fabrica_id = Column(Integer, ForeignKey('fabricas.id', ondelete='CASCADE'), nullable=False, info={'hidden': True})
    distancia_km = Column(Float, nullable=False, info={'label': 'Distância (km)', 'type': 'number', 'format': '%.2f', 'step': 0.01})
    custo_frete_ton = Column(Float, nullable=False, info={'label': 'Custo Safra (R$/Ton)', 'type': 'number', 'format': '%.2f', 'step': 0.01})
    custo_frete_entressafra = Column(Float, nullable=False, default=0, info={'label': 'Custo Entressafra (R$/Ton)', 'type': 'number', 'format': '%.2f', 'step': 0.01})
    
    armazem = relationship("Armazem", back_populates="rotas")
    fabrica = relationship("Fabrica", back_populates="rotas")

class PrevisaoFabrica(Base):
    __tablename__ = 'previsoes_fabrica'
    
    id = Column(Integer, primary_key=True, info={'label': 'id', 'type': 'number', 'disabled': True})
    fabrica_id = Column(Integer, ForeignKey('fabricas.id', ondelete='CASCADE'), nullable=False, info={'hidden': True})
    mes_referencia = Column(Date, nullable=False, info={'label': 'Mês', 'type': 'date', 'disabled': True})
    recebimento_produtor = Column(Float, default=0, info={'label': 'Recebimento Produtor (Ton)', 'type': 'number', 'format': '%.2f', 'step': 0.01})
    vendas = Column(Float, default=0, info={'label': 'Vendas (Ton)', 'type': 'number', 'format': '%.2f', 'step': 0.01})
    
    fabrica = relationship("Fabrica", back_populates="previsoes")

class PrevisaoArmazem(Base):
    __tablename__ = 'previsoes_armazem'
    
    id = Column(Integer, primary_key=True, info={'label': 'id', 'type': 'number', 'disabled': True})
    armazem_id = Column(Integer, ForeignKey('armazens.id', ondelete='CASCADE'), nullable=False, info={'hidden': True})
    mes_referencia = Column(Date, nullable=False, info={'label': 'Mês', 'type': 'date', 'disabled': True})
    recebimento_produtor = Column(Float, default=0, info={'label': 'Recebimento Produtor (Ton)', 'type': 'number', 'format': '%.2f', 'step': 0.01})
    vendas = Column(Float, default=0, info={'label': 'Vendas (Ton)', 'type': 'number', 'format': '%.2f', 'step': 0.01})
    
    armazem = relationship("Armazem", back_populates="previsoes")

class SafraUnidade(Base):
    __tablename__ = 'safras_unidades'
    
    id = Column(Integer, primary_key=True, info={'label': 'id', 'type': 'number', 'disabled': True})
    cenario_id = Column(Integer, ForeignKey('cenarios.id', ondelete='CASCADE'), nullable=True, info={'hidden': True})
    entidade_tipo = Column(String(20), nullable=False, info={'label': 'Tipo', 'disabled': True})
    entidade_id = Column(Integer, nullable=False, info={'hidden': True})
    data_inicio = Column(Date, nullable=False, info={'label': 'Início', 'type': 'date'})
    data_fim = Column(Date, nullable=False, info={'label': 'Fim', 'type': 'date'})

class MovimentacaoDiaria(Base):
    __tablename__ = 'movimentacoes_diarias'
    
    id = Column(Integer, primary_key=True, info={'label': 'id', 'type': 'number', 'disabled': True})
    cenario_id = Column(Integer, ForeignKey('cenarios.id', ondelete='CASCADE'), nullable=True, info={'hidden': True})
    data = Column(Date, nullable=False, info={'label': 'Data', 'type': 'date'})
    armazem_id = Column(Integer, ForeignKey('armazens.id', ondelete='CASCADE'), nullable=False, info={'hidden': True})
    fabrica_id = Column(Integer, ForeignKey('fabricas.id', ondelete='CASCADE'), nullable=False, info={'hidden': True})
    quantidade_ton = Column(Float, nullable=False, info={'label': 'Quantidade (Ton)', 'type': 'number', 'format': '%.2f'})
    custo_total = Column(Float, nullable=False, info={'label': 'Custo Total (R$)', 'type': 'number', 'format': '%.2f'})

class LogExecucao(Base):
    __tablename__ = 'logs_execucao'
    
    id = Column(Integer, primary_key=True)
    data_execucao = Column(DateTime, default=datetime.datetime.now)
    status = Column(String(50))
    mensagem = Column(String(500))

class ResumoMensalFabrica(Base):
    __tablename__ = 'resumo_mensal_fabrica'
    
    id = Column(Integer, primary_key=True)
    cenario_id = Column(Integer, ForeignKey('cenarios.id', ondelete='CASCADE'), nullable=True)
    mes = Column(String(7), nullable=False) # 'YYYY-MM'
    fabrica_id = Column(Integer, ForeignKey('fabricas.id', ondelete='CASCADE'), nullable=False)
    rec_produtor = Column(Float, default=0, info={'label': 'Recebimento Produtor (Ton)', 'type': 'number'})
    rec_transbordo = Column(Float, default=0, info={'label': 'Recebimento Transbordo (Ton)', 'type': 'number'})
    esmagado = Column(Float, default=0, info={'label': 'Esmagado (Ton)', 'type': 'number'})
    saldo_estoque = Column(Float, default=0, info={'label': 'Saldo Estoque (Ton)', 'type': 'number'})
    capacidade_estatica = Column(Float, default=0, info={'label': 'Capacidade Estática (Ton)', 'type': 'number'})
    excedente = Column(Float, default=0, info={'label': 'Excedente (Ton)', 'type': 'number'})

class ResumoMensalArmazem(Base):
    __tablename__ = 'resumo_mensal_armazem'
    
    id = Column(Integer, primary_key=True)
    cenario_id = Column(Integer, ForeignKey('cenarios.id', ondelete='CASCADE'), nullable=True)
    mes = Column(String(7), nullable=False) # 'YYYY-MM'
    armazem_id = Column(Integer, ForeignKey('armazens.id', ondelete='CASCADE'), nullable=False)
    rec_produtor = Column(Float, default=0, info={'label': 'Recebimento Produtor (Ton)', 'type': 'number'})
    envio_transbordo = Column(Float, default=0, info={'label': 'Envio Transbordo (Ton)', 'type': 'number'})
    vendas = Column(Float, default=0, info={'label': 'Vendas (Ton)', 'type': 'number'})
    saldo_estoque = Column(Float, default=0, info={'label': 'Saldo Estoque (Ton)', 'type': 'number'})
    capacidade_estatica = Column(Float, default=0, info={'label': 'Capacidade Estática (Ton)', 'type': 'number'})
    excedente = Column(Float, default=0, info={'label': 'Excedente (Ton)', 'type': 'number'})
