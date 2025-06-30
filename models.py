from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

class HistoricoCalculo(db.Model):
    __tablename__ = 'historico_calculos'
    
    id = db.Column(db.Integer, primary_key=True)
    id_historico = db.Column(db.String(20), unique=True, nullable=False, index=True)  # #Ded001, #Fra001, etc.
    
    # Dados do usuário
    usuario = db.Column(db.String(100), nullable=False, index=True)
    ip_cliente = db.Column(db.String(45), nullable=False)  # IPv4 ou IPv6
    
    # Dados da consulta
    tipo_frete = db.Column(db.String(20), nullable=False, index=True)  # 'Dedicado', 'Fracionado', 'Aereo'
    origem_uf = db.Column(db.String(2), nullable=False)
    origem_municipio = db.Column(db.String(100), nullable=False)
    destino_uf = db.Column(db.String(2), nullable=False)
    destino_municipio = db.Column(db.String(100), nullable=False)
    
    # Dados da carga
    peso_real = db.Column(db.Float, nullable=True)
    peso_cubado = db.Column(db.Float, nullable=True)
    peso_usado = db.Column(db.Float, nullable=False)  # Maior entre real e cubado
    valor_nf = db.Column(db.Float, nullable=True)
    
    # Dados específicos por tipo
    cubagem_comprimento = db.Column(db.Float, nullable=True)
    cubagem_largura = db.Column(db.Float, nullable=True)
    cubagem_altura = db.Column(db.Float, nullable=True)
    cubagem_m3 = db.Column(db.Float, nullable=True)
    
    # Resultados da consulta
    distancia_km = db.Column(db.Float, nullable=True)
    tempo_estimado = db.Column(db.String(20), nullable=True)  # "2h 30min"
    pedagio_estimado = db.Column(db.Float, nullable=True)
    
    # Melhores resultados (JSON)
    melhor_custo_total = db.Column(db.Float, nullable=True)
    melhor_fornecedor = db.Column(db.String(100), nullable=True)
    melhor_prazo = db.Column(db.Integer, nullable=True)
    resultados_completos = db.Column(db.Text, nullable=True)  # JSON com todos os resultados
    
    # Metadados
    data_calculo = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    provider_rota = db.Column(db.String(50), nullable=True)  # 'OpenRoute', 'Google', etc.
    sucesso = db.Column(db.Boolean, default=True, nullable=False, index=True)
    erro_detalhes = db.Column(db.Text, nullable=True)
    
    def __repr__(self):
        return f'<HistoricoCalculo {self.id_historico}: {self.tipo_frete} {self.origem_municipio}/{self.origem_uf} → {self.destino_municipio}/{self.destino_uf}>'
    
    def to_dict(self):
        """Converter para dicionário para JSON"""
        return {
            'id': self.id,
            'id_historico': self.id_historico,
            'usuario': self.usuario,
            'ip_cliente': self.ip_cliente,
            'tipo_frete': self.tipo_frete,
            'origem': f"{self.origem_municipio}/{self.origem_uf}",
            'destino': f"{self.destino_municipio}/{self.destino_uf}",
            'peso_real': self.peso_real,
            'peso_cubado': self.peso_cubado,
            'peso_usado': self.peso_usado,
            'valor_nf': self.valor_nf,
            'cubagem_m3': self.cubagem_m3,
            'distancia_km': self.distancia_km,
            'tempo_estimado': self.tempo_estimado,
            'pedagio_estimado': self.pedagio_estimado,
            'melhor_custo_total': self.melhor_custo_total,
            'melhor_fornecedor': self.melhor_fornecedor,
            'melhor_prazo': self.melhor_prazo,
            'data_calculo': self.data_calculo.strftime('%d/%m/%Y %H:%M:%S'),
            'provider_rota': self.provider_rota,
            'sucesso': self.sucesso,
            'erro_detalhes': self.erro_detalhes,
            'resultados_completos': json.loads(self.resultados_completos) if self.resultados_completos else None
        }
    
    @staticmethod
    def salvar_calculo(dados_calculo):
        """
        Salvar um cálculo no histórico
        
        Args:
            dados_calculo (dict): Dicionário com os dados do cálculo
        """
        try:
            # Verificar se já existe um registro com o mesmo id_historico
            existing = HistoricoCalculo.query.filter_by(id_historico=dados_calculo['id_historico']).first()
            if existing:
                return existing.id
            
            # Converter resultados para JSON se necessário
            resultados_json = None
            if 'resultados_completos' in dados_calculo:
                if isinstance(dados_calculo['resultados_completos'], (dict, list)):
                    resultados_json = json.dumps(dados_calculo['resultados_completos'], ensure_ascii=False)
                else:
                    resultados_json = dados_calculo['resultados_completos']
            
            historico = HistoricoCalculo(
                id_historico=dados_calculo['id_historico'],
                usuario=dados_calculo.get('usuario', 'Anônimo'),
                ip_cliente=dados_calculo.get('ip_cliente', '0.0.0.0'),
                tipo_frete=dados_calculo['tipo_frete'],
                origem_uf=dados_calculo['origem_uf'],
                origem_municipio=dados_calculo['origem_municipio'],
                destino_uf=dados_calculo['destino_uf'],
                destino_municipio=dados_calculo['destino_municipio'],
                peso_real=dados_calculo.get('peso_real'),
                peso_cubado=dados_calculo.get('peso_cubado'),
                peso_usado=dados_calculo['peso_usado'],
                valor_nf=dados_calculo.get('valor_nf'),
                cubagem_comprimento=dados_calculo.get('cubagem_comprimento'),
                cubagem_largura=dados_calculo.get('cubagem_largura'),
                cubagem_altura=dados_calculo.get('cubagem_altura'),
                cubagem_m3=dados_calculo.get('cubagem_m3'),
                distancia_km=dados_calculo.get('distancia_km'),
                tempo_estimado=dados_calculo.get('tempo_estimado'),
                pedagio_estimado=dados_calculo.get('pedagio_estimado'),
                melhor_custo_total=dados_calculo.get('melhor_custo_total'),
                melhor_fornecedor=dados_calculo.get('melhor_fornecedor'),
                melhor_prazo=dados_calculo.get('melhor_prazo'),
                resultados_completos=resultados_json,
                provider_rota=dados_calculo.get('provider_rota'),
                sucesso=dados_calculo.get('sucesso', True),
                erro_detalhes=dados_calculo.get('erro_detalhes')
            )
            
            db.session.add(historico)
            db.session.commit()
            return historico.id
            
        except Exception as e:
            db.session.rollback()
            print(f"[ERRO] Falha ao salvar no histórico PostgreSQL: {e}")
            return None
    
    @staticmethod
    def buscar_historico(usuario=None, tipo_frete=None, limite=100):
        """
        Buscar histórico de cálculos
        
        Args:
            usuario (str): Filtrar por usuário específico
            tipo_frete (str): Filtrar por tipo de frete
            limite (int): Número máximo de resultados
            
        Returns:
            list: Lista de registros do histórico
        """
        query = HistoricoCalculo.query
        
        if usuario:
            query = query.filter(HistoricoCalculo.usuario == usuario)
        
        if tipo_frete:
            query = query.filter(HistoricoCalculo.tipo_frete == tipo_frete)
        
        query = query.order_by(HistoricoCalculo.data_calculo.desc())
        
        if limite:
            query = query.limit(limite)
        
        return query.all()

class LogSistema(db.Model):
    __tablename__ = 'logs_sistema'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    nivel = db.Column(db.String(10), nullable=False, index=True)  # INFO, WARN, ERROR, DEBUG
    usuario = db.Column(db.String(100), nullable=True, index=True)
    ip_cliente = db.Column(db.String(45), nullable=True)
    acao = db.Column(db.String(100), nullable=False, index=True)
    detalhes = db.Column(db.Text, nullable=True)
    
    def __repr__(self):
        return f'<LogSistema {self.timestamp}: {self.nivel} - {self.acao}>'
    
    @staticmethod
    def log(nivel, acao, usuario=None, ip_cliente=None, detalhes=None):
        """
        Criar um log no sistema
        
        Args:
            nivel (str): Nível do log (INFO, WARN, ERROR, DEBUG)
            acao (str): Ação que foi executada
            usuario (str): Usuário que executou a ação
            ip_cliente (str): IP do cliente
            detalhes (str): Detalhes adicionais
        """
        try:
            log_entry = LogSistema(
                nivel=nivel.upper(),
                usuario=usuario,
                ip_cliente=ip_cliente,
                acao=acao,
                detalhes=detalhes
            )
            
            db.session.add(log_entry)
            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            print(f"[ERRO] Falha ao salvar log: {e}") 