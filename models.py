from sqlalchemy import Column, Integer, String, Float, ForeignKey, Date, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import datetime

Base = declarative_base()

class Fabrica(Base):
    __tablename__ = 'fabricas'
    
    id = Column(Integer, primary_key=True)
    nome = Column(String(100), nullable=False)
    capacidade_estatica = Column(Float, nullable=False)
    capacidade_esmagamento_diaria = Column(Float, nullable=False)
    capacidade_recebimento_diaria = Column(Float, nullable=False)
    limite_caminhoes = Column(Integer, nullable=False)
    carga_media_caminhao = Column(Float, nullable=False)
    estoque_inicial = Column(Float, nullable=False)
    
    previsoes = relationship("PrevisaoFabrica", back_populates="fabrica")
    rotas = relationship("Rota", back_populates="fabrica")

class Armazem(Base):
    __tablename__ = 'armazens'
    
    id = Column(Integer, primary_key=True)
    nome = Column(String(100), nullable=False)
    capacidade_estatica = Column(Float, nullable=False)
    capacidade_expedicao_diaria = Column(Float, nullable=False)
    estoque_inicial = Column(Float, nullable=False)
    
    previsoes = relationship("PrevisaoArmazem", back_populates="armazem")
    rotas = relationship("Rota", back_populates="armazem")

class Rota(Base):
    __tablename__ = 'rotas'
    
    id = Column(Integer, primary_key=True)
    armazem_id = Column(Integer, ForeignKey('armazens.id'), nullable=False)
    fabrica_id = Column(Integer, ForeignKey('fabricas.id'), nullable=False)
    distancia_km = Column(Float, nullable=False)
    custo_frete_ton = Column(Float, nullable=False)
    
    armazem = relationship("Armazem", back_populates="rotas")
    fabrica = relationship("Fabrica", back_populates="rotas")

class PrevisaoFabrica(Base):
    __tablename__ = 'previsoes_fabrica'
    
    id = Column(Integer, primary_key=True)
    fabrica_id = Column(Integer, ForeignKey('fabricas.id'), nullable=False)
    mes_referencia = Column(Date, nullable=False) # Primeiro dia do mês
    recebimento_produtor = Column(Float, default=0)
    vendas = Column(Float, default=0)
    eh_safra = Column(Integer, default=0) # 1 se for safra, 0 caso contrário
    
    fabrica = relationship("Fabrica", back_populates="previsoes")

class PrevisaoArmazem(Base):
    __tablename__ = 'previsoes_armazem'
    
    id = Column(Integer, primary_key=True)
    armazem_id = Column(Integer, ForeignKey('armazens.id'), nullable=False)
    mes_referencia = Column(Date, nullable=False)
    recebimento_produtor = Column(Float, default=0)
    vendas = Column(Float, default=0)
    eh_safra = Column(Integer, default=0)
    
    armazem = relationship("Armazem", back_populates="previsoes")

class MovimentacaoDiaria(Base):
    __tablename__ = 'movimentacoes_diarias'
    
    id = Column(Integer, primary_key=True)
    data = Column(Date, nullable=False)
    armazem_id = Column(Integer, ForeignKey('armazens.id'), nullable=False)
    fabrica_id = Column(Integer, ForeignKey('fabricas.id'), nullable=False)
    quantidade_ton = Column(Float, nullable=False)
    custo_total = Column(Float, nullable=False)

class LogExecucao(Base):
    __tablename__ = 'logs_execucao'
    
    id = Column(Integer, primary_key=True)
    data_execucao = Column(DateTime, default=datetime.datetime.now)
    status = Column(String(50))
    mensagem = Column(String(500))

class ResumoMensalFabrica(Base):
    __tablename__ = 'resumo_mensal_fabrica'
    
    id = Column(Integer, primary_key=True)
    mes = Column(String(7), nullable=False) # 'YYYY-MM'
    fabrica_id = Column(Integer, ForeignKey('fabricas.id'), nullable=False)
    rec_produtor = Column(Float, default=0)
    rec_transbordo = Column(Float, default=0)
    esmagado = Column(Float, default=0)
    saldo_estoque = Column(Float, default=0)
    capacidade_estatica = Column(Float, default=0)
    excedente = Column(Float, default=0)

class ResumoMensalArmazem(Base):
    __tablename__ = 'resumo_mensal_armazem'
    
    id = Column(Integer, primary_key=True)
    mes = Column(String(7), nullable=False) # 'YYYY-MM'
    armazem_id = Column(Integer, ForeignKey('armazens.id'), nullable=False)
    rec_produtor = Column(Float, default=0)
    envio_transbordo = Column(Float, default=0)
    vendas = Column(Float, default=0)
    saldo_estoque = Column(Float, default=0)
    capacidade_estatica = Column(Float, default=0)
    excedente = Column(Float, default=0)
