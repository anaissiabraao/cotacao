#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pandas as pd
import datetime
import math
import requests
import polyline
import time
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session, flash
import io
import os
import re
import json
import uuid
from dotenv import load_dotenv
from functools import lru_cache

# Carregar variáveis de ambiente
load_dotenv()

# Configuração do Flask
app = Flask(__name__, static_folder='static')
app.secret_key = os.getenv("SECRET_KEY", "chave_secreta_portoex_2025")

# Inicializar PostgreSQL
try:
    from models import db, Usuario, BaseUnificada, AgenteTransportadora, MemoriaCalculoAgente, Agente, TipoCalculoFrete, FormulaCalculoFrete, ConfiguracaoAgente, HistoricoCalculo, LogSistema
    from config import config
    
    config_name = os.environ.get('FLASK_ENV', 'development')
    app.config.from_object(config[config_name])
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
        # Criar usuário admin padrão
        Usuario.criar_usuario_admin_default()
        print("[PostgreSQL] ✅ Sistema inicializado com sucesso")
        
    POSTGRESQL_AVAILABLE = True
except Exception as e:
    print(f"[PostgreSQL] ❌ Erro: {e}")
    POSTGRESQL_AVAILABLE = False

# Configurações de sessão
app.config["SESSION_PERMANENT"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = datetime.timedelta(days=7)

# Cache para municípios
MUNICIPIOS_CACHE = {}

# ===== FUNÇÕES AUXILIARES LIMPAS =====

def normalizar_cidade_nome(cidade):
    """Normaliza nome da cidade"""
    if not cidade:
        return ""
    return re.sub(r'[^\w\s-]', '', str(cidade).strip().title())

def normalizar_uf(uf):
    """Normaliza UF"""
    if not uf:
        return ""
    return str(uf).strip().upper()[:2]

def obter_ip_cliente():
    """Obtém IP do cliente"""
    return request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', '127.0.0.1'))

def log_acesso(usuario, acao, ip, detalhes=""):
    """Log de acesso simplificado"""
    try:
        if POSTGRESQL_AVAILABLE:
            LogSistema.log('INFO', acao, usuario, ip, detalhes)
        timestamp = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        print(f"[LOG] {timestamp} - {usuario} - {acao} - IP: {ip}")
    except Exception as e:
        print(f"[LOG] Erro: {e}")

# ===== SISTEMA DE CÁLCULO LIMPO =====

def calcular_frete_limpo(origem, uf_origem, destino, uf_destino, peso, cubagem=None, valor_nf=None, tipo_calculo='Fracionado'):
    """Sistema de cálculo limpo usando apenas PostgreSQL"""
    try:
        # Buscar dados na base
        dados_base = BaseUnificada.buscar_fretes(origem, destino, tipo_calculo)
        
        if not dados_base:
            return {'sem_opcoes': True, 'erro': 'Nenhuma rota encontrada'}
        
        resultados = []
        peso_cubado = (cubagem * 250) if cubagem else 0
        peso_usado = max(peso, peso_cubado)
        
        for linha_base in dados_base:
            # Buscar agente configurado
            agente = AgenteTransportadora.query.filter_by(
                nome=linha_base.fornecedor, 
                ativo=True
            ).first()
            
            if agente:
                # Usar sistema do banco
                resultado = calcular_com_agente_banco(agente, linha_base, peso_usado, valor_nf)
            else:
                # Usar cálculo genérico
                resultado = calcular_generico_base(linha_base, peso_usado, valor_nf)
            
            if resultado:
                resultados.append(resultado)
        
        # Ordenar por preço
        resultados.sort(key=lambda x: x.get('total', float('inf')))
        
        # Marcar melhor opção
        if resultados:
            resultados[0]['eh_melhor_opcao'] = True
        
        return {
            'sem_opcoes': len(resultados) == 0,
            'opcoes': resultados,
            'total_opcoes': len(resultados),
            'origem': origem,
            'destino': destino,
            'sistema': 'limpo_postgresql'
        }
        
    except Exception as e:
        print(f"[CALC LIMPO] Erro: {e}")
        return {'sem_opcoes': True, 'erro': str(e)}

def calcular_com_agente_banco(agente, linha_base, peso_usado, valor_nf):
    """Calcula usando configurações do banco"""
    try:
        # Buscar memória ativa
        memoria = MemoriaCalculoAgente.query.filter_by(
            agente_id=agente.id, 
            ativo=True
        ).first()
        
        if not memoria:
            return calcular_generico_base(linha_base, peso_usado, valor_nf)
        
        # Aplicar memória
        dados = {
            'peso_usado': peso_usado,
            'valor_nf': valor_nf or 0,
            'fornecedor': agente.nome
        }
        
        resultado_memoria = memoria.aplicar_memoria_calculo(dados)
        if not resultado_memoria:
            return calcular_generico_base(linha_base, peso_usado, valor_nf)
        
        valor_base = resultado_memoria.get('valor_base', 0)
        
        # Calcular custos usando configurações do agente
        gris = 0
        if agente.gris_percentual > 0 and valor_nf:
            gris = max((valor_nf * agente.gris_percentual / 100), agente.gris_minimo)
        
        pedagio = agente.pedagio_por_bloco if agente.calcula_pedagio else 0
        seguro = (valor_nf * 0.002) if agente.calcula_seguro and valor_nf else 0
        
        total = valor_base + gris + pedagio + seguro
        
        return {
            'fornecedor': agente.nome,
            'tipo_servico': f"{linha_base.tipo} - {agente.nome}",
            'custo_base': valor_base,
            'gris': gris,
            'pedagio': pedagio,
            'seguro': seguro,
            'total': total,
            'peso_usado': f"{peso_usado}kg",
            'prazo': 3,
            'eh_melhor_opcao': False,
            'sistema': 'banco_configurado'
        }
        
    except Exception as e:
        print(f"[AGENTE BANCO] Erro: {e}")
        return None

def calcular_generico_base(linha_base, peso_usado, valor_nf):
    """Cálculo genérico usando valores da base"""
    try:
        valor_base = linha_base.get_valor_por_peso(peso_usado)
        if not valor_base:
            return None
        
        # Custos genéricos
        gris = float(linha_base.gris_exc or 0) if linha_base.gris_exc else 0
        pedagio = float(linha_base.pedagio_100kg or 0) if linha_base.pedagio_100kg else 0
        seguro = (valor_nf * 0.002) if valor_nf else 0
        
        total = valor_base + gris + pedagio + seguro
        
        return {
            'fornecedor': linha_base.fornecedor,
            'tipo_servico': f"{linha_base.tipo} - Genérico",
            'custo_base': valor_base,
            'gris': gris,
            'pedagio': pedagio,
            'seguro': seguro,
            'total': total,
            'peso_usado': f"{peso_usado}kg",
            'prazo': 3,
            'eh_melhor_opcao': False,
            'sistema': 'generico_base'
        }
        
    except Exception as e:
        print(f"[GENERICO] Erro: {e}")
        return None

# ===== ROTAS PRINCIPAIS LIMPAS =====

@app.route('/')
def index():
    """Página principal"""
    usuario_logado = session.get('usuario_logado')
    
    if usuario_logado:
        try:
            # Buscar dados completos do usuário no banco
            usuario_db = Usuario.query.filter_by(nome_usuario=usuario_logado, ativo=True).first()
            
            if usuario_db:
                usuario_dados = {
                    'nome': usuario_db.nome_completo,
                    'nome_usuario': usuario_db.nome_usuario,
                    'tipo': usuario_db.tipo_usuario,
                    'logado': True,
                    'pode_ver_admin': usuario_db.pode_ver_admin or usuario_db.is_admin(),
                    'permissoes': session.get('usuario_permissoes', {})
                }
            else:
                # Usuário não encontrado no banco, limpar sessão
                session.clear()
                usuario_dados = {
                    'nome': 'Visitante',
                    'tipo': 'visitante',
                    'logado': False
                }
            
            log_acesso(usuario_logado, 'ACESSO_HOME', obter_ip_cliente())
        except Exception as e:
            print(f"[INDEX] Erro ao buscar usuário: {e}")
            usuario_dados = {
                'nome': usuario_logado,
                'tipo': 'operador',
                'logado': True,
                'pode_ver_admin': True  # Fallback
            }
    else:
        usuario_dados = {
            'nome': 'Visitante',
            'tipo': 'visitante',
            'logado': False
        }
    
    return render_template('index.html', usuario=usuario_dados)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Sistema de login com banco de dados"""
    if request.method == 'POST':
        nome_usuario = request.form.get('usuario', '').strip()
        senha = request.form.get('senha', '').strip()
        ip_cliente = obter_ip_cliente()
        
        if not nome_usuario or not senha:
            flash('Usuário e senha são obrigatórios')
            return render_template('login.html')
        
        try:
            # Buscar usuário no banco
            usuario = Usuario.query.filter_by(nome_usuario=nome_usuario).first()
            
            if not usuario:
                log_acesso(nome_usuario, 'LOGIN_FALHA_USUARIO_INEXISTENTE', ip_cliente)
                flash('Usuário não encontrado')
                return render_template('login.html')
            
            # Verificar se usuário está bloqueado
            if usuario.is_blocked():
                log_acesso(nome_usuario, 'LOGIN_FALHA_USUARIO_BLOQUEADO', ip_cliente)
                flash('Usuário temporariamente bloqueado. Tente novamente em 30 minutos.')
                return render_template('login.html')
            
            # Verificar se usuário está ativo
            if not usuario.ativo:
                log_acesso(nome_usuario, 'LOGIN_FALHA_USUARIO_INATIVO', ip_cliente)
                flash('Usuário inativo. Contate o administrador.')
                return render_template('login.html')
            
            # Verificar senha
            if usuario.verificar_senha(senha):
                # Login bem-sucedido
                usuario.resetar_tentativas_login()
                usuario.ip_ultimo_login = ip_cliente
                db.session.commit()
                
                # Criar sessão
                session['usuario_logado'] = usuario.nome_usuario
                session['usuario_id'] = usuario.id
                session['usuario_tipo'] = usuario.tipo_usuario
                session['usuario_nome_completo'] = usuario.nome_completo
                session['usuario_permissoes'] = {
                    'pode_calcular_fretes': usuario.pode_calcular_fretes,
                    'pode_ver_admin': usuario.pode_ver_admin,
                    'pode_editar_base': usuario.pode_editar_base,
                    'pode_gerenciar_usuarios': usuario.pode_gerenciar_usuarios,
                    'pode_importar_dados': usuario.pode_importar_dados
                }
                
                log_acesso(nome_usuario, 'LOGIN_SUCESSO', ip_cliente, f'Tipo: {usuario.tipo_usuario}')
                flash(f'Bem-vindo, {usuario.nome_completo}!', 'success')
                return redirect(url_for('index'))
            else:
                # Senha incorreta
                usuario.incrementar_tentativas_login()
                db.session.commit()
                
                log_acesso(nome_usuario, 'LOGIN_FALHA_SENHA_INCORRETA', ip_cliente)
                flash(f'Senha incorreta. Tentativas restantes: {5 - usuario.tentativas_login}')
                return render_template('login.html')
                
        except Exception as e:
            print(f"[LOGIN] Erro: {e}")
            log_acesso(nome_usuario, 'LOGIN_ERRO_SISTEMA', ip_cliente, str(e))
            flash('Erro interno do sistema. Tente novamente.')
            return render_template('login.html')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout"""
    usuario = session.get('usuario_logado', 'DESCONHECIDO')
    session.clear()
    log_acesso(usuario, 'LOGOUT', obter_ip_cliente())
    return redirect(url_for('login'))

# ===== ROTAS DE CÁLCULO LIMPAS =====

@app.route("/calcular_frete_fracionado", methods=["POST"])
def calcular_frete_fracionado():
    """Cálculo de frete fracionado limpo"""
    try:
        data = request.get_json()
        usuario = session.get('usuario_logado', 'DESCONHECIDO')
        
        origem = data.get("municipio_origem")
        uf_origem = data.get("uf_origem")
        destino = data.get("municipio_destino")
        uf_destino = data.get("uf_destino")
        peso = float(data.get("peso", 1))
        cubagem = float(data.get("cubagem", 0.01))
        valor_nf = float(data.get("valor_nf", 0)) if data.get("valor_nf") else None
        
        log_acesso(usuario, 'CALCULO_FRACIONADO', obter_ip_cliente(), 
                  f"{origem}/{uf_origem} → {destino}/{uf_destino}, {peso}kg")
        
        if not all([origem, uf_origem, destino, uf_destino]):
            return jsonify({"error": "Origem e destino são obrigatórios"})
        
        # Sistema limpo
        resultado = calcular_frete_limpo(origem, uf_origem, destino, uf_destino, 
                                       peso, cubagem, valor_nf, 'Fracionado')
        
        return jsonify(resultado)
        
    except Exception as e:
        print(f"[FRACIONADO] Erro: {e}")
        return jsonify({"error": str(e)})

@app.route("/calcular", methods=["POST"])
def calcular_dedicado():
    """Cálculo de frete dedicado limpo"""
    try:
        data = request.get_json()
        usuario = session.get('usuario_logado', 'DESCONHECIDO')
        
        origem = data.get("municipio_origem")
        uf_origem = data.get("uf_origem")
        destino = data.get("municipio_destino")
        uf_destino = data.get("uf_destino")
        peso = float(data.get("peso", 1))
        
        log_acesso(usuario, 'CALCULO_DEDICADO', obter_ip_cliente(), 
                  f"{origem}/{uf_origem} → {destino}/{uf_destino}, {peso}kg")
        
        if not all([origem, uf_origem, destino, uf_destino]):
            return jsonify({"error": "Origem e destino são obrigatórios"})
        
        # Sistema limpo
        resultado = calcular_frete_limpo(origem, uf_origem, destino, uf_destino, 
                                       peso, None, None, 'Dedicado')
        
        return jsonify(resultado)
        
    except Exception as e:
        print(f"[DEDICADO] Erro: {e}")
        return jsonify({"error": str(e)})

@app.route("/calcular_aereo", methods=["POST"])
def calcular_aereo():
    """Cálculo de frete aéreo limpo"""
    try:
        data = request.get_json()
        usuario = session.get('usuario_logado', 'DESCONHECIDO')
        
        origem = data.get("municipio_origem")
        uf_origem = data.get("uf_origem")
        destino = data.get("municipio_destino")
        uf_destino = data.get("uf_destino")
        peso = float(data.get("peso", 5))
        cubagem = float(data.get("cubagem", 0.02))
        
        log_acesso(usuario, 'CALCULO_AEREO', obter_ip_cliente(), 
                  f"{origem}/{uf_origem} → {destino}/{uf_destino}, {peso}kg")
        
        if not all([origem, uf_origem, destino, uf_destino]):
            return jsonify({"error": "Origem e destino são obrigatórios"})
        
        # Sistema limpo
        resultado = calcular_frete_limpo(origem, uf_origem, destino, uf_destino, 
                                       peso, cubagem, None, 'Aéreo')
        
        return jsonify(resultado)
        
    except Exception as e:
        print(f"[AÉREO] Erro: {e}")
        return jsonify({"error": str(e)})

# ===== ROTAS DE ADMINISTRAÇÃO =====

@app.route('/admin')
def admin():
    """Painel administrativo"""
    usuario = session.get('usuario_logado', 'DESCONHECIDO')
    log_acesso(usuario, 'ADMIN_ACESSO', obter_ip_cliente())
    
    try:
        estatisticas = {
            'total_logs': LogSistema.query.count() if POSTGRESQL_AVAILABLE else 0,
            'total_pesquisas': HistoricoCalculo.query.count() if POSTGRESQL_AVAILABLE else 0,
            'usuarios_unicos': 1,
            'ips_unicos': 1,
            'ultimas_atividades': [],
            'acoes_mais_comuns': []
        }
        
        return render_template("admin_melhorado.html", estatisticas=estatisticas)
    except Exception as e:
        print(f"[ADMIN] Erro: {e}")
        return redirect(url_for('index'))

@app.route('/admin/calculadoras')
def admin_calculadoras():
    """Gerenciar calculadoras"""
    return render_template('admin_calculadoras.html')

@app.route('/admin/base-dados')
def admin_base_dados():
    """Gerenciar base de dados"""
    return render_template('admin_base_dados.html')

@app.route('/admin/agentes-memoria')
def admin_agentes_memoria():
    """Gerenciar memórias de cálculo"""
    return render_template('admin_agentes_memoria.html')

@app.route('/admin/usuarios')
def admin_usuarios():
    """Gerenciar usuários do sistema"""
    # Verificar se usuário tem permissão
    if not session.get('usuario_permissoes', {}).get('pode_gerenciar_usuarios', False):
        flash('Acesso negado. Você não tem permissão para gerenciar usuários.', 'danger')
        return redirect(url_for('admin'))
    
    return render_template('admin_usuarios.html')

# ===== APIs LIMPAS =====

@app.route('/api/admin/base-dados', methods=['GET'])
def api_get_base_dados():
    """API para listar dados da base"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        todos = request.args.get('todos', 'false').lower() == 'true'
        
        # Filtros
        query = BaseUnificada.query
        
        if request.args.get('tipo'):
            query = query.filter(BaseUnificada.tipo.ilike(f'%{request.args.get("tipo")}%'))
        if request.args.get('fornecedor'):
            query = query.filter(BaseUnificada.fornecedor.ilike(f'%{request.args.get("fornecedor")}%'))
        if request.args.get('origem'):
            query = query.filter(BaseUnificada.origem.ilike(f'%{request.args.get("origem")}%'))
        if request.args.get('destino'):
            query = query.filter(BaseUnificada.destino.ilike(f'%{request.args.get("destino")}%'))
        
        total = query.count()
        
        if todos:
            registros = query.all()
        else:
            registros = query.offset((page - 1) * per_page).limit(per_page).all()
        
        # Converter para dicionários
        dados = []
        for r in registros:
            dados.append({
                'id': f"{r.fornecedor}_{r.origem}_{r.destino}",
                'tipo': r.tipo,
                'fornecedor': r.fornecedor,
                'base_origem': r.base_origem,
                'origem': r.origem,
                'base_destino': r.base_destino,
                'destino': r.destino,
                'valor_minimo_10': r.valor_minimo_10,
                'peso_20': r.peso_20,
                'peso_30': r.peso_30,
                'peso_50': r.peso_50,
                'peso_70': r.peso_70,
                'peso_100': r.peso_100,
                'peso_150': r.peso_150,
                'peso_200': r.peso_200,
                'peso_300': r.peso_300,
                'peso_500': r.peso_500,
                'acima_500': r.acima_500,
                'pedagio_100kg': r.pedagio_100kg,
                'excedente': r.excedente,
                'seguro': r.seguro,
                'peso_maximo': r.peso_maximo,
                'gris_min': r.gris_min,
                'gris_exc': r.gris_exc,
                'tas': r.tas,
                'despacho': r.despacho
            })
        
        # Filtros disponíveis
        from sqlalchemy import distinct
        filtros = {
            'tipos': [r[0] for r in db.session.query(distinct(BaseUnificada.tipo)).filter(BaseUnificada.tipo.isnot(None)).all()],
            'fornecedores': [r[0] for r in db.session.query(distinct(BaseUnificada.fornecedor)).filter(BaseUnificada.fornecedor.isnot(None)).all()],
            'bases_origem': [r[0] for r in db.session.query(distinct(BaseUnificada.base_origem)).filter(BaseUnificada.base_origem.isnot(None)).all()]
        }
        
        return jsonify({
            'registros': dados,
            'total': total,
            'filtros': filtros
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/agentes-memoria', methods=['GET'])
def api_get_agentes_memoria():
    """API para listar agentes e memórias"""
    try:
        agentes = AgenteTransportadora.query.filter_by(ativo=True).all()
        memorias = MemoriaCalculoAgente.query.filter_by(ativo=True).all()
        
        estatisticas = {
            'transportadoras': AgenteTransportadora.query.filter_by(tipo_agente='transportadora', ativo=True).count(),
            'transferencias': AgenteTransportadora.query.filter_by(tipo_agente='transferencia', ativo=True).count(),
            'agentes_ponta': AgenteTransportadora.query.filter(
                AgenteTransportadora.tipo_agente.in_(['agente_coleta', 'agente_entrega']),
                AgenteTransportadora.ativo == True
            ).count(),
            'memorias_ativas': MemoriaCalculoAgente.query.filter_by(ativo=True).count()
        }
        
        return jsonify({
            'agentes': [a.to_dict() for a in agentes],
            'memorias': [m.to_dict() for m in memorias],
            'estatisticas': estatisticas
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===== APIs DE USUÁRIOS =====

@app.route('/api/admin/usuarios', methods=['GET'])
def api_get_usuarios():
    """Listar usuários do sistema"""
    try:
        # Verificar permissão
        if not session.get('usuario_permissoes', {}).get('pode_gerenciar_usuarios', False):
            return jsonify({'error': 'Acesso negado'}), 403
        
        usuarios = Usuario.query.order_by(Usuario.nome_usuario).all()
        return jsonify([usuario.to_dict() for usuario in usuarios])
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/usuarios', methods=['POST'])
def api_create_usuario():
    """Criar novo usuário"""
    try:
        # Verificar permissão
        if not session.get('usuario_permissoes', {}).get('pode_gerenciar_usuarios', False):
            return jsonify({'error': 'Acesso negado'}), 403
        
        data = request.get_json()
        
        # Validar dados obrigatórios
        if not data.get('nome_usuario') or not data.get('nome_completo') or not data.get('senha'):
            return jsonify({'error': 'Nome de usuário, nome completo e senha são obrigatórios'}), 400
        
        # Verificar se usuário já existe
        if Usuario.query.filter_by(nome_usuario=data['nome_usuario']).first():
            return jsonify({'error': 'Nome de usuário já existe'}), 400
        
        # Verificar email único se fornecido
        if data.get('email'):
            if Usuario.query.filter_by(email=data['email']).first():
                return jsonify({'error': 'Email já está em uso'}), 400
        
        # Criar usuário
        usuario = Usuario(
            nome_usuario=data['nome_usuario'],
            nome_completo=data['nome_completo'],
            email=data.get('email'),
            tipo_usuario=data.get('tipo_usuario', 'operador'),
            pode_calcular_fretes=bool(data.get('pode_calcular_fretes', True)),
            pode_ver_admin=bool(data.get('pode_ver_admin', False)),
            pode_editar_base=bool(data.get('pode_editar_base', False)),
            pode_gerenciar_usuarios=bool(data.get('pode_gerenciar_usuarios', False)),
            pode_importar_dados=bool(data.get('pode_importar_dados', False)),
            ativo=bool(data.get('ativo', True)),
            criado_por=session.get('usuario_logado', 'sistema')
        )
        usuario.set_senha(data['senha'])
        
        db.session.add(usuario)
        db.session.commit()
        
        log_acesso(session.get('usuario_logado'), 'USUARIO_CRIADO', obter_ip_cliente(), 
                  f'Criado usuário: {usuario.nome_usuario}')
        
        return jsonify(usuario.to_dict()), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/usuarios/<int:usuario_id>', methods=['PUT'])
def api_update_usuario(usuario_id):
    """Atualizar usuário"""
    try:
        # Verificar permissão
        if not session.get('usuario_permissoes', {}).get('pode_gerenciar_usuarios', False):
            return jsonify({'error': 'Acesso negado'}), 403
        
        usuario = Usuario.query.get_or_404(usuario_id)
        data = request.get_json()
        
        # Verificar nome único (exceto o próprio)
        if data.get('nome_usuario') != usuario.nome_usuario:
            if Usuario.query.filter_by(nome_usuario=data['nome_usuario']).first():
                return jsonify({'error': 'Nome de usuário já existe'}), 400
        
        # Verificar email único (exceto o próprio)
        if data.get('email') and data.get('email') != usuario.email:
            if Usuario.query.filter_by(email=data['email']).first():
                return jsonify({'error': 'Email já está em uso'}), 400
        
        # Atualizar dados
        usuario.nome_usuario = data.get('nome_usuario', usuario.nome_usuario)
        usuario.nome_completo = data.get('nome_completo', usuario.nome_completo)
        usuario.email = data.get('email', usuario.email)
        usuario.tipo_usuario = data.get('tipo_usuario', usuario.tipo_usuario)
        usuario.pode_calcular_fretes = bool(data.get('pode_calcular_fretes', usuario.pode_calcular_fretes))
        usuario.pode_ver_admin = bool(data.get('pode_ver_admin', usuario.pode_ver_admin))
        usuario.pode_editar_base = bool(data.get('pode_editar_base', usuario.pode_editar_base))
        usuario.pode_gerenciar_usuarios = bool(data.get('pode_gerenciar_usuarios', usuario.pode_gerenciar_usuarios))
        usuario.pode_importar_dados = bool(data.get('pode_importar_dados', usuario.pode_importar_dados))
        usuario.ativo = bool(data.get('ativo', usuario.ativo))
        
        # Atualizar senha se fornecida
        if data.get('senha') and data['senha'] != '******':
            usuario.set_senha(data['senha'])
        
        db.session.commit()
        
        log_acesso(session.get('usuario_logado'), 'USUARIO_ATUALIZADO', obter_ip_cliente(), 
                  f'Atualizado usuário: {usuario.nome_usuario}')
        
        return jsonify(usuario.to_dict())
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/usuarios/<int:usuario_id>/senha', methods=['PUT'])
def api_update_senha_usuario(usuario_id):
    """Alterar senha de usuário"""
    try:
        # Verificar permissão
        if not session.get('usuario_permissoes', {}).get('pode_gerenciar_usuarios', False):
            return jsonify({'error': 'Acesso negado'}), 403
        
        usuario = Usuario.query.get_or_404(usuario_id)
        data = request.get_json()
        
        nova_senha = data.get('nova_senha')
        if not nova_senha or len(nova_senha) < 6:
            return jsonify({'error': 'Senha deve ter pelo menos 6 caracteres'}), 400
        
        # Atualizar senha
        usuario.set_senha(nova_senha)
        usuario.tentativas_login = 0  # Resetar tentativas
        usuario.bloqueado_ate = None  # Desbloquear se estiver bloqueado
        
        db.session.commit()
        
        log_acesso(session.get('usuario_logado'), 'SENHA_ALTERADA', obter_ip_cliente(), 
                  f'Senha alterada para usuário: {usuario.nome_usuario}')
        
        return jsonify({'message': 'Senha alterada com sucesso'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/usuarios/<int:usuario_id>', methods=['DELETE'])
def api_delete_usuario(usuario_id):
    """Excluir usuário"""
    try:
        # Verificar permissão
        if not session.get('usuario_permissoes', {}).get('pode_gerenciar_usuarios', False):
            return jsonify({'error': 'Acesso negado'}), 403
        
        usuario = Usuario.query.get_or_404(usuario_id)
        
        # Não permitir excluir admin padrão
        if usuario.nome_usuario == 'admin':
            return jsonify({'error': 'Não é possível excluir o usuário admin padrão'}), 400
        
        # Não permitir excluir o próprio usuário
        if usuario.id == session.get('usuario_id'):
            return jsonify({'error': 'Não é possível excluir seu próprio usuário'}), 400
        
        nome_usuario = usuario.nome_usuario
        db.session.delete(usuario)
        db.session.commit()
        
        log_acesso(session.get('usuario_logado'), 'USUARIO_EXCLUIDO', obter_ip_cliente(), 
                  f'Excluído usuário: {nome_usuario}')
        
        return jsonify({'message': 'Usuário excluído com sucesso'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# ===== ROTAS AUXILIARES =====

@app.route('/estados')
def estados():
    """Lista estados"""
    estados_brasil = [
        {"sigla": "AC", "nome": "Acre"},
        {"sigla": "AL", "nome": "Alagoas"},
        {"sigla": "AP", "nome": "Amapá"},
        {"sigla": "AM", "nome": "Amazonas"},
        {"sigla": "BA", "nome": "Bahia"},
        {"sigla": "CE", "nome": "Ceará"},
        {"sigla": "DF", "nome": "Distrito Federal"},
        {"sigla": "ES", "nome": "Espírito Santo"},
        {"sigla": "GO", "nome": "Goiás"},
        {"sigla": "MA", "nome": "Maranhão"},
        {"sigla": "MT", "nome": "Mato Grosso"},
        {"sigla": "MS", "nome": "Mato Grosso do Sul"},
        {"sigla": "MG", "nome": "Minas Gerais"},
        {"sigla": "PA", "nome": "Pará"},
        {"sigla": "PB", "nome": "Paraíba"},
        {"sigla": "PR", "nome": "Paraná"},
        {"sigla": "PE", "nome": "Pernambuco"},
        {"sigla": "PI", "nome": "Piauí"},
        {"sigla": "RJ", "nome": "Rio de Janeiro"},
        {"sigla": "RN", "nome": "Rio Grande do Norte"},
        {"sigla": "RS", "nome": "Rio Grande do Sul"},
        {"sigla": "RO", "nome": "Rondônia"},
        {"sigla": "RR", "nome": "Roraima"},
        {"sigla": "SC", "nome": "Santa Catarina"},
        {"sigla": "SP", "nome": "São Paulo"},
        {"sigla": "SE", "nome": "Sergipe"},
        {"sigla": "TO", "nome": "Tocantins"}
    ]
    return jsonify(estados_brasil)

@app.route('/municipios/<uf>')
def municipios(uf):
    """Lista municípios por UF"""
    try:
        # Cache simples
        if uf in MUNICIPIOS_CACHE:
            return jsonify(MUNICIPIOS_CACHE[uf])
        
        # Buscar via IBGE
        url = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            municipios_data = response.json()
            municipios_nomes = [m['nome'] for m in municipios_data]
            MUNICIPIOS_CACHE[uf] = municipios_nomes
            return jsonify(municipios_nomes)
        else:
            return jsonify([])
            
    except Exception as e:
        print(f"[MUNICIPIOS] Erro para {uf}: {e}")
        return jsonify([])

@app.route('/historico')
def historico():
    """Histórico de consultas"""
    try:
        historicos = HistoricoCalculo.query.order_by(HistoricoCalculo.data_calculo.desc()).limit(50).all()
        return jsonify([h.to_dict() for h in historicos])
    except Exception:
        return jsonify([])

# ===== MIDDLEWARE DE AUTENTICAÇÃO =====

def middleware_auth(f):
    """Middleware de autenticação com verificação de permissões"""
    def decorated_function(*args, **kwargs):
        if 'usuario_logado' not in session:
            return redirect(url_for('login'))
        
        # Verificar se usuário ainda existe e está ativo
        try:
            usuario = Usuario.query.filter_by(
                nome_usuario=session.get('usuario_logado'),
                ativo=True
            ).first()
            
            if not usuario:
                session.clear()
                flash('Sessão expirada. Faça login novamente.', 'warning')
                return redirect(url_for('login'))
                
        except Exception:
            pass  # Se erro no banco, continuar (fallback)
        
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def middleware_admin(f):
    """Middleware específico para administradores"""
    def decorated_function(*args, **kwargs):
        if 'usuario_logado' not in session:
            return redirect(url_for('login'))
        
        # Verificar permissões de admin
        permissoes = session.get('usuario_permissoes', {})
        if not permissoes.get('pode_ver_admin', False):
            flash('Acesso negado. Você não tem permissão para acessar esta área.', 'danger')
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# Aplicar middleware nas rotas protegidas
calcular_frete_fracionado = middleware_auth(calcular_frete_fracionado)
calcular_dedicado = middleware_auth(calcular_dedicado)
calcular_aereo = middleware_auth(calcular_aereo)
admin = middleware_admin(admin)
admin_calculadoras = middleware_admin(admin_calculadoras)
admin_base_dados = middleware_admin(admin_base_dados)
admin_agentes_memoria = middleware_admin(admin_agentes_memoria)
admin_usuarios = middleware_admin(admin_usuarios)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 PortoEx iniciando na porta {port}")
    print("✅ Sistema saneado e otimizado")
    app.run(host="0.0.0.0", port=port, debug=True)
