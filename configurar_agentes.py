#!/usr/bin/env python3
from app2 import app

with app.app_context():
    from models import AgenteTransportadora, MemoriaCalculoAgente, db
    import json
    
    print("🔧 Configurando agentes com lógica de cálculo no banco...")
    
    # 1. Criar/atualizar agentes
    agentes_config = [
        {
            'nome': 'PTX',
            'tipo_agente': 'agente_coleta',  # Agente de coleta - só tem origem
            'logica_calculo': 'valor_por_kg',
            'gris_percentual': 0.0,
            'gris_minimo': 0.0,
            'calcula_seguro': False,
            'calcula_pedagio': False,
            'pedagio_por_bloco': 0.0,
            'parametros_calculo': {'peso_maximo': 1000, 'volume_maximo': 100},
            'descricao_logica': 'Agente de coleta - valor por kg'
        },
        {
            'nome': 'Jem/Dfl',
            'tipo_agente': 'transferencia',  # Transferência - vai de base para base
            'logica_calculo': 'tabela_especifica',
            'gris_percentual': 0.0,
            'gris_minimo': 0.0,
            'calcula_seguro': False,
            'calcula_pedagio': False,
            'pedagio_por_bloco': 0.0,
            'parametros_calculo': {'peso_maximo': 1000, 'volume_maximo': 100},
            'descricao_logica': 'Transferência - tabela de faixas'
        },
        {
            'nome': 'SOL',
            'tipo_agente': 'transferencia',
            'logica_calculo': 'tabela_especifica',
            'gris_percentual': 0.0,
            'gris_minimo': 0.0,
            'calcula_seguro': False,
            'calcula_pedagio': False,
            'pedagio_por_bloco': 0.0,
            'parametros_calculo': {'peso_maximo': 1000, 'volume_maximo': 100},
            'descricao_logica': 'Transferência - tabela de faixas'
        },
        {
            'nome': 'FILIAL SP',
            'tipo_agente': 'agente_entrega',  # Agente de entrega - só tem destino
            'logica_calculo': 'valor_fixo_faixa',
            'gris_percentual': 0.0,
            'gris_minimo': 0.0,
            'calcula_seguro': False,
            'calcula_pedagio': False,
            'pedagio_por_bloco': 0.0,
            'parametros_calculo': {'peso_maximo': 1000, 'volume_maximo': 100},
            'descricao_logica': 'Agente de entrega - valor fixo'
        },
        {
            'nome': 'GLI',
            'tipo_agente': 'agente_entrega',
            'logica_calculo': 'valor_fixo_faixa',
            'gris_percentual': 0.0,
            'gris_minimo': 0.0,
            'calcula_seguro': False,
            'calcula_pedagio': False,
            'pedagio_por_bloco': 0.0,
            'parametros_calculo': {'peso_maximo': 1000, 'volume_maximo': 100},
            'descricao_logica': 'Agente de entrega - valor fixo'
        }
    ]
    
    for agente_data in agentes_config:
        agente = AgenteTransportadora.query.filter_by(nome=agente_data['nome']).first()
        if not agente:
            agente = AgenteTransportadora()
            agente.nome = agente_data['nome']
            agente.nome_normalizado = agente_data['nome'].upper()
            db.session.add(agente)
            print(f"✅ Criado agente: {agente_data['nome']}")
        else:
            print(f"🔄 Atualizando agente: {agente_data['nome']}")
        
        # Atualizar dados
        agente.tipo_agente = agente_data['tipo_agente']
        agente.logica_calculo = agente_data['logica_calculo']
        agente.gris_percentual = agente_data['gris_percentual']
        agente.gris_minimo = agente_data['gris_minimo']
        agente.calcula_seguro = agente_data['calcula_seguro']
        agente.calcula_pedagio = agente_data['calcula_pedagio']
        agente.pedagio_por_bloco = agente_data['pedagio_por_bloco']
        agente.set_parametros_calculo(agente_data['parametros_calculo'])
        agente.descricao_logica = agente_data['descricao_logica']
        agente.ativo = True
    
    db.session.commit()
    
    # 2. Criar memórias de cálculo
    memorias_config = [
        {
            'agente_nome': 'PTX',
            'tipo_memoria': 'valor_por_kg',
            'nome_memoria': 'PTX - Valor por kg',
            'configuracao': {'valor_por_kg': 0.25},  # R$ 0.25 por kg
            'prioridade': 1
        },
        {
            'agente_nome': 'Jem/Dfl',
            'tipo_memoria': 'tabela_especifica',
            'nome_memoria': 'Jem/Dfl - Tabela de faixas',
            'configuracao': {
                'usar_valor_minimo': True,
                'faixas': [20, 30, 50, 70, 100, 150, 200, 300, 500]
            },
            'prioridade': 1
        },
        {
            'agente_nome': 'SOL',
            'tipo_memoria': 'tabela_especifica',
            'nome_memoria': 'SOL - Tabela de faixas',
            'configuracao': {
                'usar_valor_minimo': True,
                'faixas': [20, 30, 50, 70, 100, 150, 200, 300, 500]
            },
            'prioridade': 1
        },
        {
            'agente_nome': 'FILIAL SP',
            'tipo_memoria': 'valor_fixo_faixa',
            'nome_memoria': 'FILIAL SP - Valor fixo',
            'configuracao': {'faixa_especifica': 'VALOR MÍNIMO ATÉ 10'},  # Usar valor mínimo
            'prioridade': 1
        },
        {
            'agente_nome': 'GLI',
            'tipo_memoria': 'valor_fixo_faixa',
            'nome_memoria': 'GLI - Valor fixo',
            'configuracao': {'faixa_especifica': 'VALOR MÍNIMO ATÉ 10'},  # Usar valor mínimo
            'prioridade': 1
        }
    ]
    
    for memoria_data in memorias_config:
        agente = AgenteTransportadora.query.filter_by(nome=memoria_data['agente_nome']).first()
        if not agente:
            print(f"❌ Agente {memoria_data['agente_nome']} não encontrado")
            continue
        
        # Verificar se já existe memória
        memoria_existente = MemoriaCalculoAgente.query.filter_by(
            agente_id=agente.id,
            nome_memoria=memoria_data['nome_memoria']
        ).first()
        
        if memoria_existente:
            print(f"🔄 Atualizando memória: {memoria_data['nome_memoria']}")
            memoria = memoria_existente
        else:
            memoria = MemoriaCalculoAgente()
            memoria.agente_id = agente.id
            db.session.add(memoria)
            print(f"✅ Criada memória: {memoria_data['nome_memoria']}")
        
        # Atualizar dados
        memoria.tipo_memoria = memoria_data['tipo_memoria']
        memoria.nome_memoria = memoria_data['nome_memoria']
        memoria.configuracao_memoria = json.dumps(memoria_data['configuracao'], ensure_ascii=False)
        memoria.prioridade = memoria_data['prioridade']
        memoria.ativo = True
    
    db.session.commit()
    print("✅ Configuração de agentes concluída!")
