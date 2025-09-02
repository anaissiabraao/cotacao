from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json
import re
from decimal import Decimal
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class Usuario(db.Model):
    """
    Modelo para usuários do sistema
    Sistema completo de autenticação com PostgreSQL
    """
    __tablename__ = 'usuarios'
    
    id = db.Column(db.Integer, primary_key=True)
    nome_usuario = db.Column(db.String(50), unique=True, nullable=False, index=True)
    nome_completo = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True, index=True)
    senha_hash = db.Column(db.String(255), nullable=False)
    
    # Níveis de acesso
    tipo_usuario = db.Column(db.String(20), nullable=False, default='operador', index=True)  # 'admin', 'operador', 'consultor'
    ativo = db.Column(db.Boolean, default=True, nullable=False, index=True)
    
    # Permissões específicas
    pode_calcular_fretes = db.Column(db.Boolean, default=True, nullable=False)
    pode_ver_admin = db.Column(db.Boolean, default=False, nullable=False)
    pode_editar_base = db.Column(db.Boolean, default=False, nullable=False)
    pode_gerenciar_usuarios = db.Column(db.Boolean, default=False, nullable=False)
    pode_importar_dados = db.Column(db.Boolean, default=False, nullable=False)
    
    # Informações de sessão
    ultimo_login = db.Column(db.DateTime, nullable=True)
    ip_ultimo_login = db.Column(db.String(45), nullable=True)
    tentativas_login = db.Column(db.Integer, default=0, nullable=False)
    bloqueado_ate = db.Column(db.DateTime, nullable=True)
    
    # Metadados
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    criado_por = db.Column(db.String(50), nullable=True)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f'<Usuario {self.nome_usuario} ({self.tipo_usuario})>'
    
    def set_senha(self, senha):
        """Define senha com hash"""
        self.senha_hash = generate_password_hash(senha)
    
    def verificar_senha(self, senha):
        """Verifica senha"""
        return check_password_hash(self.senha_hash, senha)
    
    def is_admin(self):
        """Verifica se é administrador"""
        return self.tipo_usuario == 'admin' or self.pode_gerenciar_usuarios
    
    def is_blocked(self):
        """Verifica se usuário está bloqueado"""
        if self.bloqueado_ate:
            return datetime.utcnow() < self.bloqueado_ate
        return False
    
    def incrementar_tentativas_login(self):
        """Incrementa tentativas de login falhadas"""
        self.tentativas_login += 1
        
        # Bloquear após 5 tentativas por 30 minutos
        if self.tentativas_login >= 5:
            self.bloqueado_ate = datetime.utcnow() + datetime.timedelta(minutes=30)
    
    def resetar_tentativas_login(self):
        """Reseta tentativas após login bem-sucedido"""
        self.tentativas_login = 0
        self.bloqueado_ate = None
        self.ultimo_login = datetime.utcnow()
    
    def to_dict(self, incluir_sensiveis=False):
        """Converte para dicionário"""
        dados = {
            'id': self.id,
            'nome_usuario': self.nome_usuario,
            'nome_completo': self.nome_completo,
            'email': self.email,
            'tipo_usuario': self.tipo_usuario,
            'ativo': self.ativo,
            'pode_calcular_fretes': self.pode_calcular_fretes,
            'pode_ver_admin': self.pode_ver_admin,
            'pode_editar_base': self.pode_editar_base,
            'pode_gerenciar_usuarios': self.pode_gerenciar_usuarios,
            'pode_importar_dados': self.pode_importar_dados,
            'ultimo_login': self.ultimo_login.strftime('%d/%m/%Y %H:%M:%S') if self.ultimo_login else None,
            'criado_em': self.criado_em.strftime('%d/%m/%Y %H:%M:%S'),
            'criado_por': self.criado_por,
            'is_blocked': self.is_blocked()
        }
        
        if incluir_sensiveis:
            dados.update({
                'ip_ultimo_login': self.ip_ultimo_login,
                'tentativas_login': self.tentativas_login,
                'bloqueado_ate': self.bloqueado_ate.strftime('%d/%m/%Y %H:%M:%S') if self.bloqueado_ate else None
            })
        
        return dados
    
    @staticmethod
    def criar_usuario_admin_default():
        """Cria usuário admin padrão se não existir"""
        try:
            admin_existente = Usuario.query.filter_by(nome_usuario='admin').first()
            
            if not admin_existente:
                admin = Usuario(
                    nome_usuario='admin',
                    nome_completo='Administrador do Sistema',
                    email='admin@portoex.com',
                    tipo_usuario='admin',
                    pode_calcular_fretes=True,
                    pode_ver_admin=True,
                    pode_editar_base=True,
                    pode_gerenciar_usuarios=True,
                    pode_importar_dados=True,
                    criado_por='sistema'
                )
                admin.set_senha('admin123')  # Senha padrão
                
                db.session.add(admin)
                db.session.commit()
                
                print("[USUARIO] ✅ Usuário admin padrão criado (admin/admin123)")
                return True
            else:
                print("[USUARIO] ⚠️ Usuário admin já existe")
                return False
                
        except Exception as e:
            db.session.rollback()
            print(f"[USUARIO] Erro ao criar admin: {e}")
            return False

class BaseUnificada(db.Model):
    """
    Modelo para a tabela base_unificada existente no PostgreSQL
    Representa os dados de frete das transportadoras
    """
    __tablename__ = 'base_unificada'
    
    # Campos da tabela existente - usando chave composta
    tipo = db.Column('Tipo', db.Text)
    fornecedor = db.Column('Fornecedor', db.Text, primary_key=True)
    base_origem = db.Column('Base Origem', db.Text)
    origem = db.Column('Origem', db.Text, primary_key=True)
    base_destino = db.Column('Base Destino', db.Text)
    destino = db.Column('Destino', db.Text, primary_key=True)
    
    # Faixas de peso
    valor_minimo_10 = db.Column('VALOR MÍNIMO ATÉ 10', db.Text)
    peso_20 = db.Column('20', db.Text)
    peso_30 = db.Column('30', db.Text)
    peso_50 = db.Column('50', db.Text)
    peso_70 = db.Column('70', db.Text)
    peso_100 = db.Column('100', db.Text)
    peso_150 = db.Column('150', db.Text)
    peso_200 = db.Column('200', db.Text)
    peso_300 = db.Column('300', db.Text)
    peso_500 = db.Column('500', db.Text)
    acima_500 = db.Column('Acima 500', db.Text)
    
    # Custos adicionais
    pedagio_100kg = db.Column('Pedagio (100 Kg)', db.Text)
    excedente = db.Column('EXCEDENTE', db.Text)
    seguro = db.Column('Seguro', db.Text)
    peso_maximo = db.Column('PESO MÁXIMO TRANSPORTADO', db.Text)
    gris_min = db.Column('Gris Min', db.Text)
    gris_exc = db.Column('Gris Exc', db.Text)
    tas = db.Column('TAS', db.Text)
    despacho = db.Column('DESPACHO', db.Text)
    
    def __repr__(self):
        return f'<BaseUnificada {self.fornecedor}: {self.origem} → {self.destino}>'
    
    def get_valor_por_peso(self, peso_kg):
        """
        Retorna o valor do frete baseado no peso
        
        Args:
            peso_kg (float): Peso em kg
            
        Returns:
            str: Valor do frete para a faixa de peso
        """
        try:
            peso_kg = float(peso_kg)
            
            if peso_kg <= 10:
                return self._parse_valor(self.valor_minimo_10)
            elif peso_kg <= 20:
                return self._parse_valor(self.peso_20)
            elif peso_kg <= 30:
                return self._parse_valor(self.peso_30)
            elif peso_kg <= 50:
                return self._parse_valor(self.peso_50)
            elif peso_kg <= 70:
                return self._parse_valor(self.peso_70)
            elif peso_kg <= 100:
                return self._parse_valor(self.peso_100)
            elif peso_kg <= 150:
                return self._parse_valor(self.peso_150)
            elif peso_kg <= 200:
                return self._parse_valor(self.peso_200)
            elif peso_kg <= 300:
                return self._parse_valor(self.peso_300)
            elif peso_kg <= 500:
                return self._parse_valor(self.peso_500)
            else:
                return self._parse_valor(self.acima_500)
                
        except (ValueError, TypeError):
            return None
    
    def _parse_valor(self, valor_str):
        """
        Converte string de valor para float
        
        Args:
            valor_str (str): String com valor (ex: "R$ 25,50" ou "25.50")
            
        Returns:
            float: Valor numérico ou None se inválido
        """
        if not valor_str:
            return None
            
        try:
            # Remover símbolos e converter vírgula para ponto
            valor_limpo = str(valor_str).replace('R$', '').replace(' ', '').replace(',', '.')
            return float(valor_limpo)
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def buscar_fretes(origem, destino, tipo_frete=None):
        """
        Busca fretes disponíveis entre origem e destino
        
        Args:
            origem (str): Cidade de origem
            destino (str): Cidade de destino
            tipo_frete (str): Tipo do frete (opcional)
            
        Returns:
            list: Lista de registros de frete
        """
        query = BaseUnificada.query.filter(
            BaseUnificada.origem.ilike(f'%{origem}%'),
            BaseUnificada.destino.ilike(f'%{destino}%')
        )
        
        if tipo_frete:
            query = query.filter(BaseUnificada.tipo.ilike(f'%{tipo_frete}%'))
        
        return query.all()
    
    @staticmethod
    def listar_fornecedores():
        """
        Lista todos os fornecedores únicos
        
        Returns:
            list: Lista de fornecedores
        """
        result = db.session.query(BaseUnificada.fornecedor).distinct().all()
        return [r[0] for r in result if r[0]]
    
    @staticmethod
    def listar_origens():
        """
        Lista todas as origens únicas
        
        Returns:
            list: Lista de cidades de origem
        """
        result = db.session.query(BaseUnificada.origem).distinct().all()
        return [r[0] for r in result if r[0]]
    
    @staticmethod
    def listar_destinos():
        """
        Lista todos os destinos únicos
        
        Returns:
            list: Lista de cidades de destino
        """
        result = db.session.query(BaseUnificada.destino).distinct().all()
        return [r[0] for r in result if r[0]]

class Agente(db.Model):
    __tablename__ = 'agentes'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), unique=True, nullable=False, index=True)
    # Lista de tipos de cálculo habilitados para o agente (ex: ["fracionado","dedicado","aereo"])
    tipos_calculo = db.Column(db.Text, nullable=True)  # JSON serializado como texto
    ativo = db.Column(db.Boolean, default=True, nullable=False, index=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<Agente {self.nome} ativo={self.ativo}>'

    def get_tipos(self):
        try:
            return json.loads(self.tipos_calculo) if self.tipos_calculo else []
        except Exception:
            return []

    def set_tipos(self, tipos_lista):
        try:
            self.tipos_calculo = json.dumps(list(tipos_lista or []), ensure_ascii=False)
        except Exception:
            self.tipos_calculo = '[]'

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

class TipoCalculoFrete(db.Model):
    """
    Modelo para tipos de cálculo de frete configuráveis
    Permite criar diferentes tipos de cálculo (fracionado, dedicado, aéreo, etc.)
    """
    __tablename__ = 'tipos_calculo_frete'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False, index=True)  # Ex: "Fracionado", "Dedicado"
    descricao = db.Column(db.Text, nullable=True)
    ativo = db.Column(db.Boolean, default=True, nullable=False, index=True)
    ordem_exibicao = db.Column(db.Integer, default=0, nullable=False)
    
    # Configurações específicas do tipo
    usa_peso_cubado = db.Column(db.Boolean, default=True, nullable=False)
    usa_valor_nf = db.Column(db.Boolean, default=False, nullable=False)
    usa_distancia = db.Column(db.Boolean, default=True, nullable=False)
    usa_pedagio = db.Column(db.Boolean, default=True, nullable=False)
    
    # Metadados
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relacionamentos
    formulas = db.relationship('FormulaCalculoFrete', backref='tipo_calculo', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<TipoCalculoFrete {self.nome}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'descricao': self.descricao,
            'ativo': self.ativo,
            'ordem_exibicao': self.ordem_exibicao,
            'usa_peso_cubado': self.usa_peso_cubado,
            'usa_valor_nf': self.usa_valor_nf,
            'usa_distancia': self.usa_distancia,
            'usa_pedagio': self.usa_pedagio,
            'criado_em': self.criado_em.strftime('%d/%m/%Y %H:%M:%S'),
            'total_formulas': self.formulas.count()
        }

class FormulaCalculoFrete(db.Model):
    """
    Modelo para fórmulas de cálculo configuráveis
    Permite criar fórmulas matemáticas personalizadas para cada tipo de frete
    """
    __tablename__ = 'formulas_calculo_frete'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False, index=True)  # Ex: "Cálculo Fracionado Padrão"
    descricao = db.Column(db.Text, nullable=True)
    
    # Relacionamento com tipo de cálculo
    tipo_calculo_id = db.Column(db.Integer, db.ForeignKey('tipos_calculo_frete.id'), nullable=False, index=True)
    
    # Fórmula matemática (usando variáveis)
    formula = db.Column(db.Text, nullable=False)  # Ex: "(peso_usado * valor_kg) + (distancia * 0.15) + pedagio"
    
    # Condições para aplicar a fórmula (JSON)
    condicoes = db.Column(db.Text, nullable=True)  # JSON com condições: {"peso_min": 0, "peso_max": 100, "origem": "SP"}
    
    # Configurações adicionais
    ativo = db.Column(db.Boolean, default=True, nullable=False, index=True)
    prioridade = db.Column(db.Integer, default=0, nullable=False)  # Maior prioridade = aplicada primeiro
    
    # Valores padrão para variáveis
    valores_padrao = db.Column(db.Text, nullable=True)  # JSON: {"valor_kg": 2.5, "taxa_seguro": 0.02}
    
    # Metadados
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f'<FormulaCalculoFrete {self.nome}>'
    
    def get_condicoes(self):
        """Retorna condições como dicionário"""
        try:
            return json.loads(self.condicoes) if self.condicoes else {}
        except Exception:
            return {}
    
    def set_condicoes(self, condicoes_dict):
        """Define condições a partir de dicionário"""
        try:
            self.condicoes = json.dumps(condicoes_dict, ensure_ascii=False)
        except Exception:
            self.condicoes = '{}'
    
    def get_valores_padrao(self):
        """Retorna valores padrão como dicionário"""
        try:
            return json.loads(self.valores_padrao) if self.valores_padrao else {}
        except Exception:
            return {}
    
    def set_valores_padrao(self, valores_dict):
        """Define valores padrão a partir de dicionário"""
        try:
            self.valores_padrao = json.dumps(valores_dict, ensure_ascii=False)
        except Exception:
            self.valores_padrao = '{}'
    
    def aplicar_formula(self, variaveis):
        """
        Aplica a fórmula com as variáveis fornecidas
        
        Args:
            variaveis (dict): Dicionário com variáveis (peso_usado, distancia, etc.)
            
        Returns:
            float: Resultado do cálculo ou None se erro
        """
        try:
            # Combinar valores padrão com variáveis fornecidas
            valores = self.get_valores_padrao().copy()
            valores.update(variaveis)
            
            # Verificar condições
            if not self._verificar_condicoes(valores):
                return None
            
            # Aplicar fórmula
            formula_segura = self._preparar_formula_segura(self.formula)
            resultado = eval(formula_segura, {"__builtins__": {}}, valores)
            
            return float(resultado) if resultado is not None else None
            
        except Exception as e:
            print(f"[ERRO] Falha ao aplicar fórmula {self.nome}: {e}")
            return None
    
    def _verificar_condicoes(self, valores):
        """Verifica se as condições da fórmula são atendidas"""
        try:
            condicoes = self.get_condicoes()
            
            for campo, condicao in condicoes.items():
                if campo not in valores:
                    continue
                    
                valor = valores[campo]
                
                # Condições numéricas
                if isinstance(condicao, dict):
                    if 'min' in condicao and valor < condicao['min']:
                        return False
                    if 'max' in condicao and valor > condicao['max']:
                        return False
                    if 'igual' in condicao and valor != condicao['igual']:
                        return False
                
                # Condições de string
                elif isinstance(condicao, str):
                    if str(valor).lower() != condicao.lower():
                        return False
                
                # Condições de lista (contém)
                elif isinstance(condicao, list):
                    if str(valor) not in [str(c) for c in condicao]:
                        return False
            
            return True
            
        except Exception:
            return True  # Se erro, não bloquear
    
    def _preparar_formula_segura(self, formula):
        """Prepara fórmula para execução segura"""
        # Substituir funções matemáticas comuns
        formula_segura = formula.replace('max(', 'max(').replace('min(', 'min(')
        formula_segura = formula_segura.replace('abs(', 'abs(').replace('round(', 'round(')
        
        # Remover caracteres perigosos
        caracteres_perigosos = ['import', 'exec', 'eval', '__', 'open', 'file']
        for char in caracteres_perigosos:
            if char in formula_segura:
                raise ValueError(f"Fórmula contém código inseguro: {char}")
        
        return formula_segura
    
    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'descricao': self.descricao,
            'tipo_calculo_id': self.tipo_calculo_id,
            'tipo_calculo_nome': self.tipo_calculo.nome if self.tipo_calculo else None,
            'formula': self.formula,
            'condicoes': self.get_condicoes(),
            'valores_padrao': self.get_valores_padrao(),
            'ativo': self.ativo,
            'prioridade': self.prioridade,
            'criado_em': self.criado_em.strftime('%d/%m/%Y %H:%M:%S')
        }

class ConfiguracaoAgente(db.Model):
    """
    Configurações específicas de cada agente
    Liga agentes a tipos de cálculo e fórmulas específicas
    """
    __tablename__ = 'configuracoes_agente'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Relacionamentos
    agente_id = db.Column(db.Integer, db.ForeignKey('agentes.id'), nullable=False, index=True)
    tipo_calculo_id = db.Column(db.Integer, db.ForeignKey('tipos_calculo_frete.id'), nullable=False, index=True)
    
    # Configurações específicas do agente para este tipo de cálculo
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    
    # Sobrescrever valores padrão das fórmulas (JSON)
    valores_customizados = db.Column(db.Text, nullable=True)  # {"valor_kg": 3.0, "taxa_adicional": 0.05}
    
    # Fórmulas específicas para este agente (se não usar as padrão do tipo)
    formulas_customizadas = db.Column(db.Text, nullable=True)  # JSON com IDs das fórmulas customizadas
    
    # Metadados
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relacionamentos
    agente = db.relationship('Agente', backref='configuracoes')
    tipo_calculo = db.relationship('TipoCalculoFrete', backref='configuracoes_agente')
    
    def __repr__(self):
        return f'<ConfiguracaoAgente {self.agente.nome if self.agente else "?"} - {self.tipo_calculo.nome if self.tipo_calculo else "?"}>'
    
    def get_valores_customizados(self):
        """Retorna valores customizados como dicionário"""
        try:
            return json.loads(self.valores_customizados) if self.valores_customizados else {}
        except Exception:
            return {}
    
    def set_valores_customizados(self, valores_dict):
        """Define valores customizados a partir de dicionário"""
        try:
            self.valores_customizados = json.dumps(valores_dict, ensure_ascii=False)
        except Exception:
            self.valores_customizados = '{}'
    
    def get_formulas_customizadas(self):
        """Retorna lista de IDs das fórmulas customizadas"""
        try:
            return json.loads(self.formulas_customizadas) if self.formulas_customizadas else []
        except Exception:
            return []
    
    def set_formulas_customizadas(self, formula_ids):
        """Define fórmulas customizadas a partir de lista de IDs"""
        try:
            self.formulas_customizadas = json.dumps(list(formula_ids), ensure_ascii=False)
        except Exception:
            self.formulas_customizadas = '[]'
    
    def to_dict(self):
        return {
            'id': self.id,
            'agente_id': self.agente_id,
            'agente_nome': self.agente.nome if self.agente else None,
            'tipo_calculo_id': self.tipo_calculo_id,
            'tipo_calculo_nome': self.tipo_calculo.nome if self.tipo_calculo else None,
            'ativo': self.ativo,
            'valores_customizados': self.get_valores_customizados(),
            'formulas_customizadas': self.get_formulas_customizadas(),
            'criado_em': self.criado_em.strftime('%d/%m/%Y %H:%M:%S')
        }

class AgenteTransportadora(db.Model):
    """
    Modelo para armazenar informações detalhadas dos agentes/transportadoras
    Substitui lógica hardcoded por dados configuráveis
    """
    __tablename__ = 'agentes_transportadora'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), unique=True, nullable=False, index=True)
    nome_normalizado = db.Column(db.String(150), nullable=False, index=True)  # Nome em uppercase para busca
    
    # Informações básicas
    tipo_agente = db.Column(db.String(50), nullable=False, index=True)  # 'transportadora', 'agente_coleta', 'agente_entrega', 'transferencia'
    ativo = db.Column(db.Boolean, default=True, nullable=False, index=True)
    
    # Lógica de cálculo específica
    logica_calculo = db.Column(db.String(100), nullable=False)  # 'valor_fixo_faixa', 'valor_por_kg', 'tabela_especifica', 'formula_customizada'
    
    # Configurações de GRIS
    gris_percentual = db.Column(db.Float, default=0.0)  # Percentual do GRIS (ex: 0.1 para 0.1%)
    gris_minimo = db.Column(db.Float, default=0.0)  # Valor mínimo do GRIS
    calcula_seguro = db.Column(db.Boolean, default=True)  # Se calcula seguro separado
    
    # Configurações de pedágio
    calcula_pedagio = db.Column(db.Boolean, default=True)
    pedagio_por_bloco = db.Column(db.Float, default=0.0)  # Valor por bloco de pedágio
    
    # Parâmetros específicos (JSON)
    parametros_calculo = db.Column(db.Text, nullable=True)  # JSON com parâmetros específicos
    
    # Observações e descrição da lógica
    descricao_logica = db.Column(db.Text, nullable=True)
    observacoes = db.Column(db.Text, nullable=True)
    
    # Metadados
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f'<AgenteTransportadora {self.nome} ({self.tipo_agente})>'
    
    def get_parametros_calculo(self):
        """Retorna parâmetros de cálculo como dicionário"""
        try:
            return json.loads(self.parametros_calculo) if self.parametros_calculo else {}
        except Exception:
            return {}
    
    def set_parametros_calculo(self, parametros_dict):
        """Define parâmetros de cálculo a partir de dicionário"""
        try:
            self.parametros_calculo = json.dumps(parametros_dict, ensure_ascii=False)
        except Exception:
            self.parametros_calculo = '{}'
    
    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'nome_normalizado': self.nome_normalizado,
            'tipo_agente': self.tipo_agente,
            'ativo': self.ativo,
            'logica_calculo': self.logica_calculo,
            'gris_percentual': self.gris_percentual,
            'gris_minimo': self.gris_minimo,
            'calcula_seguro': self.calcula_seguro,
            'calcula_pedagio': self.calcula_pedagio,
            'pedagio_por_bloco': self.pedagio_por_bloco,
            'parametros_calculo': self.get_parametros_calculo(),
            'descricao_logica': self.descricao_logica,
            'observacoes': self.observacoes,
            'criado_em': self.criado_em.strftime('%d/%m/%Y %H:%M:%S')
        }

class MemoriaCalculoAgente(db.Model):
    """
    Modelo para armazenar memórias de cálculo específicas por agente
    Permite configurar como cada agente calcula seus valores
    """
    __tablename__ = 'memorias_calculo_agente'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Relacionamento com agente
    agente_id = db.Column(db.Integer, db.ForeignKey('agentes_transportadora.id'), nullable=False, index=True)
    
    # Tipo de memória
    tipo_memoria = db.Column(db.String(100), nullable=False, index=True)  # 'faixa_peso', 'valor_por_kg', 'formula_especifica'
    nome_memoria = db.Column(db.String(200), nullable=False)  # Ex: "Cálculo REUNIDAS por faixa"
    
    # Condições de aplicação
    condicoes_aplicacao = db.Column(db.Text, nullable=True)  # JSON: {"peso_min": 0, "peso_max": 100, "tipo_servico": "TRANSFERENCIA"}
    
    # Configuração da memória de cálculo
    configuracao_memoria = db.Column(db.Text, nullable=False)  # JSON com toda a configuração
    
    # Prioridade e status
    prioridade = db.Column(db.Integer, default=0, nullable=False)  # Maior prioridade = aplicada primeiro
    ativo = db.Column(db.Boolean, default=True, nullable=False, index=True)
    
    # Metadados
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relacionamento
    agente = db.relationship('AgenteTransportadora', backref='memorias_calculo')
    
    def __repr__(self):
        return f'<MemoriaCalculoAgente {self.nome_memoria}>'
    
    def get_condicoes_aplicacao(self):
        """Retorna condições como dicionário"""
        try:
            return json.loads(self.condicoes_aplicacao) if self.condicoes_aplicacao else {}
        except Exception:
            return {}
    
    def set_condicoes_aplicacao(self, condicoes_dict):
        """Define condições a partir de dicionário"""
        try:
            self.condicoes_aplicacao = json.dumps(condicoes_dict, ensure_ascii=False)
        except Exception:
            self.condicoes_aplicacao = '{}'
    
    def get_configuracao_memoria(self):
        """Retorna configuração como dicionário"""
        try:
            return json.loads(self.configuracao_memoria) if self.configuracao_memoria else {}
        except Exception:
            return {}
    
    def set_configuracao_memoria(self, config_dict):
        """Define configuração a partir de dicionário"""
        try:
            self.configuracao_memoria = json.dumps(config_dict, ensure_ascii=False)
        except Exception:
            self.configuracao_memoria = '{}'
    
    def aplicar_memoria_calculo(self, dados_calculo):
        """
        Aplica a memória de cálculo aos dados fornecidos
        
        Args:
            dados_calculo (dict): Dados do cálculo (peso, valor_nf, linha_base, etc.)
            
        Returns:
            dict: Resultado do cálculo com detalhes
        """
        try:
            # Verificar condições de aplicação
            if not self._verificar_condicoes(dados_calculo):
                return None
            
            config = self.get_configuracao_memoria()
            
            if self.tipo_memoria == 'faixa_peso':
                return self._aplicar_calculo_faixa_peso(dados_calculo, config)
            elif self.tipo_memoria == 'valor_por_kg':
                return self._aplicar_calculo_por_kg(dados_calculo, config)
            elif self.tipo_memoria == 'formula_especifica':
                return self._aplicar_formula_especifica(dados_calculo, config)
            else:
                return None
                
        except Exception as e:
            print(f"[MEMORIA] Erro ao aplicar memória {self.nome_memoria}: {e}")
            return None
    
    def _verificar_condicoes(self, dados_calculo):
        """Verifica se as condições para aplicar a memória são atendidas"""
        try:
            condicoes = self.get_condicoes_aplicacao()
            
            for campo, condicao in condicoes.items():
                if campo not in dados_calculo:
                    continue
                    
                valor = dados_calculo[campo]
                
                if isinstance(condicao, dict):
                    if 'min' in condicao and valor < condicao['min']:
                        return False
                    if 'max' in condicao and valor > condicao['max']:
                        return False
                elif isinstance(condicao, str):
                    if str(valor).upper() != condicao.upper():
                        return False
                elif isinstance(condicao, list):
                    if str(valor).upper() not in [str(c).upper() for c in condicao]:
                        return False
            
            return True
            
        except Exception:
            return True  # Se erro, não bloquear
    
    def _aplicar_calculo_faixa_peso(self, dados_calculo, config):
        """Aplica cálculo por faixa de peso (ex: REUNIDAS)"""
        peso = dados_calculo.get('peso_usado', 0)
        
        # Buscar faixa apropriada
        faixas = config.get('faixas_peso', {})
        for faixa_nome, faixa_config in faixas.items():
            peso_min = faixa_config.get('peso_min', 0)
            peso_max = faixa_config.get('peso_max', float('inf'))
            
            if peso_min <= peso <= peso_max:
                valor_base = faixa_config.get('valor_fixo', 0)
                return {
                    'valor_base': valor_base,
                    'faixa_aplicada': faixa_nome,
                    'logica': 'faixa_peso'
                }
        
        return None
    
    def _aplicar_calculo_por_kg(self, dados_calculo, config):
        """Aplica cálculo por peso (ex: PTX)"""
        peso = dados_calculo.get('peso_usado', 0)
        valor_por_kg = config.get('valor_por_kg', 0)
        
        valor_base = peso * valor_por_kg
        
        return {
            'valor_base': valor_base,
            'peso_usado': peso,
            'valor_por_kg': valor_por_kg,
            'logica': 'valor_por_kg'
        }
    
    def _aplicar_formula_especifica(self, dados_calculo, config):
        """Aplica fórmula específica personalizada"""
        try:
            formula = config.get('formula', '')
            variaveis = dados_calculo.copy()
            variaveis.update(config.get('variaveis_adicionais', {}))
            
            # Aplicar fórmula de forma segura
            resultado = eval(formula, {"__builtins__": {}}, variaveis)
            
            return {
                'valor_base': float(resultado),
                'formula_aplicada': formula,
                'variaveis_usadas': variaveis,
                'logica': 'formula_especifica'
            }
            
        except Exception as e:
            print(f"[FORMULA] Erro ao aplicar fórmula: {e}")
            return None
    
    def to_dict(self):
        return {
            'id': self.id,
            'agente_id': self.agente_id,
            'agente_nome': self.agente.nome if self.agente else None,
            'tipo_memoria': self.tipo_memoria,
            'nome_memoria': self.nome_memoria,
            'condicoes_aplicacao': self.get_condicoes_aplicacao(),
            'configuracao_memoria': self.get_configuracao_memoria(),
            'prioridade': self.prioridade,
            'ativo': self.ativo,
            'criado_em': self.criado_em.strftime('%d/%m/%Y %H:%M:%S')
        } 