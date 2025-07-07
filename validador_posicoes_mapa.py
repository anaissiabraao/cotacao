#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema de Validação de Posições das Siglas dos Estados no Mapa do Brasil
Autor: Sistema de Cotação de Fretes
Versão: 1.0
Data: 2024
"""

import json
import math
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path

@dataclass
class Coordenada:
    """Representa uma coordenada (x, y) no mapa SVG"""
    x: float
    y: float
    
    def distancia_para(self, outra: 'Coordenada') -> float:
        """Calcula a distância euclidiana para outra coordenada"""
        return math.sqrt((self.x - outra.x)**2 + (self.y - outra.y)**2)

@dataclass
class Estado:
    """Representa um estado brasileiro com sua posição e limites"""
    sigla: str
    nome: str
    regiao: str
    centro_geografico: Coordenada
    limites: Dict[str, float]  # {'min_x', 'max_x', 'min_y', 'max_y'}
    posicao_atual: Optional[Coordenada] = None
    posicao_sugerida: Optional[Coordenada] = None

@dataclass
class ResultadoValidacao:
    """Resultado da validação de um estado"""
    estado: str
    valido: bool
    motivo: str
    posicao_atual: Coordenada
    posicao_sugerida: Optional[Coordenada] = None
    conflitos: List[str] = None

class ValidadorMapaBrasil:
    """Validador de posições das siglas dos estados no mapa do Brasil"""
    
    def __init__(self):
        self.estados = self._inicializar_estados()
        self.distancia_minima_siglas = 30  # Distância mínima entre siglas (pixels)
        self.tolerancia_limites = 20  # Tolerância para limites do estado (pixels)
        
    def _inicializar_estados(self) -> Dict[str, Estado]:
        """Inicializa os dados dos estados brasileiros com coordenadas dos centros geográficos"""
        estados_data = {
            # REGIÃO NORTE
            'AC': {
                'nome': 'Acre', 'regiao': 'Norte',
                'centro': (55, 240), 'limites': {'min_x': 15, 'max_x': 95, 'min_y': 200, 'max_y': 280}
            },
            'AP': {
                'nome': 'Amapá', 'regiao': 'Norte',
                'centro': (285, 128), 'limites': {'min_x': 250, 'max_x': 320, 'min_y': 80, 'max_y': 180}
            },
            'AM': {
                'nome': 'Amazonas', 'regiao': 'Norte',
                'centro': (215, 130), 'limites': {'min_x': 120, 'max_x': 310, 'min_y': 90, 'max_y': 200}
            },
            'PA': {
                'nome': 'Pará', 'regiao': 'Norte',
                'centro': (328, 160), 'limites': {'min_x': 280, 'max_x': 400, 'min_y': 120, 'max_y': 240}
            },
            'RO': {
                'nome': 'Rondônia', 'regiao': 'Norte',
                'centro': (158, 285), 'limites': {'min_x': 130, 'max_x': 190, 'min_y': 250, 'max_y': 320}
            },
            'RR': {
                'nome': 'Roraima', 'regiao': 'Norte',
                'centro': (235, 118), 'limites': {'min_x': 200, 'max_x': 270, 'min_y': 80, 'max_y': 160}
            },
            'TO': {
                'nome': 'Tocantins', 'regiao': 'Norte',
                'centro': (415, 238), 'limites': {'min_x': 380, 'max_x': 450, 'min_y': 200, 'max_y': 280}
            },
            
            # REGIÃO NORDESTE
            'AL': {
                'nome': 'Alagoas', 'regiao': 'Nordeste',
                'centro': (568, 235), 'limites': {'min_x': 550, 'max_x': 590, 'min_y': 220, 'max_y': 250}
            },
            'BA': {
                'nome': 'Bahia', 'regiao': 'Nordeste',
                'centro': (527, 270), 'limites': {'min_x': 460, 'max_x': 590, 'min_y': 220, 'max_y': 380}
            },
            'CE': {
                'nome': 'Ceará', 'regiao': 'Nordeste',
                'centro': (548, 168), 'limites': {'min_x': 520, 'max_x': 580, 'min_y': 140, 'max_y': 200}
            },
            'MA': {
                'nome': 'Maranhão', 'regiao': 'Nordeste',
                'centro': (458, 180), 'limites': {'min_x': 420, 'max_x': 510, 'min_y': 140, 'max_y': 220}
            },
            'PB': {
                'nome': 'Paraíba', 'regiao': 'Nordeste',
                'centro': (595, 195), 'limites': {'min_x': 575, 'max_x': 615, 'min_y': 175, 'max_y': 215}
            },
            'PE': {
                'nome': 'Pernambuco', 'regiao': 'Nordeste',
                'centro': (548, 215), 'limites': {'min_x': 520, 'max_x': 590, 'min_y': 190, 'max_y': 240}
            },
            'PI': {
                'nome': 'Piauí', 'regiao': 'Nordeste',
                'centro': (505, 185), 'limites': {'min_x': 470, 'max_x': 540, 'min_y': 160, 'max_y': 210}
            },
            'RN': {
                'nome': 'Rio Grande do Norte', 'regiao': 'Nordeste',
                'centro': (595, 178), 'limites': {'min_x': 575, 'max_x': 615, 'min_y': 160, 'max_y': 195}
            },
            'SE': {
                'nome': 'Sergipe', 'regiao': 'Nordeste',
                'centro': (568, 245), 'limites': {'min_x': 550, 'max_x': 585, 'min_y': 235, 'max_y': 265}
            },
            
            # REGIÃO CENTRO-OESTE
            'DF': {
                'nome': 'Distrito Federal', 'regiao': 'Centro-Oeste',
                'centro': (417, 334), 'limites': {'min_x': 410, 'max_x': 425, 'min_y': 325, 'max_y': 340}
            },
            'GO': {
                'nome': 'Goiás', 'regiao': 'Centro-Oeste',
                'centro': (390, 340), 'limites': {'min_x': 350, 'max_x': 450, 'min_y': 300, 'max_y': 380}
            },
            'MT': {
                'nome': 'Mato Grosso', 'regiao': 'Centro-Oeste',
                'centro': (275, 310), 'limites': {'min_x': 220, 'max_x': 350, 'min_y': 260, 'max_y': 380}
            },
            'MS': {
                'nome': 'Mato Grosso do Sul', 'regiao': 'Centro-Oeste',
                'centro': (315, 455), 'limites': {'min_x': 270, 'max_x': 360, 'min_y': 420, 'max_y': 490}
            },
            
            # REGIÃO SUDESTE
            'ES': {
                'nome': 'Espírito Santo', 'regiao': 'Sudeste',
                'centro': (492, 415), 'limites': {'min_x': 475, 'max_x': 510, 'min_y': 390, 'max_y': 440}
            },
            'MG': {
                'nome': 'Minas Gerais', 'regiao': 'Sudeste',
                'centro': (470, 370), 'limites': {'min_x': 420, 'max_x': 530, 'min_y': 330, 'max_y': 420}
            },
            'RJ': {
                'nome': 'Rio de Janeiro', 'regiao': 'Sudeste',
                'centro': (458, 455), 'limites': {'min_x': 440, 'max_x': 485, 'min_y': 440, 'max_y': 475}
            },
            'SP': {
                'nome': 'São Paulo', 'regiao': 'Sudeste',
                'centro': (435, 475), 'limites': {'min_x': 400, 'max_x': 470, 'min_y': 450, 'max_y': 510}
            },
            
            # REGIÃO SUL
            'PR': {
                'nome': 'Paraná', 'regiao': 'Sul',
                'centro': (390, 505), 'limites': {'min_x': 350, 'max_x': 430, 'min_y': 480, 'max_y': 530}
            },
            'RS': {
                'nome': 'Rio Grande do Sul', 'regiao': 'Sul',
                'centro': (358, 588), 'limites': {'min_x': 300, 'max_x': 420, 'min_y': 540, 'max_y': 640}
            },
            'SC': {
                'nome': 'Santa Catarina', 'regiao': 'Sul',
                'centro': (378, 548), 'limites': {'min_x': 340, 'max_x': 420, 'min_y': 530, 'max_y': 570}
            }
        }
        
        estados = {}
        for sigla, data in estados_data.items():
            centro = Coordenada(data['centro'][0], data['centro'][1])
            estados[sigla] = Estado(
                sigla=sigla,
                nome=data['nome'],
                regiao=data['regiao'],
                centro_geografico=centro,
                limites=data['limites']
            )
        
        return estados
    
    def carregar_posicoes_atuais(self, arquivo_posicoes: str = None) -> bool:
        """Carrega as posições atuais das siglas do localStorage ou arquivo"""
        try:
            if arquivo_posicoes and Path(arquivo_posicoes).exists():
                # Carregar de arquivo
                with open(arquivo_posicoes, 'r', encoding='utf-8') as f:
                    posicoes = json.load(f)
            else:
                # Usar posições padrão do código
                posicoes = {
                    'AC': {'x': 55, 'y': 240}, 'AL': {'x': 568, 'y': 235}, 'AP': {'x': 285, 'y': 128},
                    'AM': {'x': 215, 'y': 130}, 'BA': {'x': 527, 'y': 270}, 'CE': {'x': 548, 'y': 168},
                    'DF': {'x': 417, 'y': 334}, 'ES': {'x': 492, 'y': 415}, 'GO': {'x': 390, 'y': 340},
                    'MA': {'x': 458, 'y': 180}, 'MG': {'x': 470, 'y': 370}, 'MS': {'x': 315, 'y': 455},
                    'MT': {'x': 275, 'y': 310}, 'PA': {'x': 328, 'y': 160}, 'PB': {'x': 595, 'y': 195},
                    'PE': {'x': 548, 'y': 215}, 'PI': {'x': 505, 'y': 185}, 'PR': {'x': 390, 'y': 505},
                    'RJ': {'x': 458, 'y': 455}, 'RN': {'x': 595, 'y': 178}, 'RS': {'x': 358, 'y': 588},
                    'RO': {'x': 158, 'y': 285}, 'RR': {'x': 235, 'y': 118}, 'SC': {'x': 378, 'y': 548},
                    'SP': {'x': 435, 'y': 475}, 'SE': {'x': 568, 'y': 245}, 'TO': {'x': 415, 'y': 238}
                }
            
            # Atualizar posições dos estados
            for sigla, pos in posicoes.items():
                if sigla in self.estados:
                    self.estados[sigla].posicao_atual = Coordenada(pos['x'], pos['y'])
            
            print(f"✅ Posições carregadas para {len(posicoes)} estados")
            return True
            
        except Exception as e:
            print(f"❌ Erro ao carregar posições: {e}")
            return False
    
    def validar_posicao_estado(self, sigla: str) -> ResultadoValidacao:
        """Valida a posição de um estado específico"""
        if sigla not in self.estados:
            return ResultadoValidacao(
                estado=sigla, 
                valido=False, 
                motivo="Estado não encontrado",
                posicao_atual=Coordenada(0, 0)
            )
        
        estado = self.estados[sigla]
        if not estado.posicao_atual:
            return ResultadoValidacao(
                estado=sigla,
                valido=False,
                motivo="Posição atual não definida",
                posicao_atual=Coordenada(0, 0),
                posicao_sugerida=estado.centro_geografico
            )
        
        pos_atual = estado.posicao_atual
        erros = []
        
        # 1. Verificar se está dentro dos limites geográficos do estado
        limites = estado.limites
        if not (limites['min_x'] - self.tolerancia_limites <= pos_atual.x <= limites['max_x'] + self.tolerancia_limites):
            erros.append(f"Fora dos limites horizontais ({limites['min_x']}-{limites['max_x']})")
        
        if not (limites['min_y'] - self.tolerancia_limites <= pos_atual.y <= limites['max_y'] + self.tolerancia_limites):
            erros.append(f"Fora dos limites verticais ({limites['min_y']}-{limites['max_y']})")
        
        # 2. Verificar conflitos com outros estados
        conflitos = []
        for outra_sigla, outro_estado in self.estados.items():
            if outra_sigla != sigla and outro_estado.posicao_atual:
                distancia = pos_atual.distancia_para(outro_estado.posicao_atual)
                if distancia < self.distancia_minima_siglas:
                    conflitos.append(f"{outra_sigla} (distância: {distancia:.1f}px)")
        
        if conflitos:
            erros.append(f"Muito próximo de: {', '.join(conflitos)}")
        
        # 3. Calcular posição sugerida se houver erros
        posicao_sugerida = None
        if erros:
            posicao_sugerida = self._calcular_posicao_otima(sigla)
        
        return ResultadoValidacao(
            estado=sigla,
            valido=len(erros) == 0,
            motivo="; ".join(erros) if erros else "Posição válida",
            posicao_atual=pos_atual,
            posicao_sugerida=posicao_sugerida,
            conflitos=conflitos
        )
    
    def _calcular_posicao_otima(self, sigla: str) -> Coordenada:
        """Calcula a posição ótima para um estado"""
        estado = self.estados[sigla]
        centro = estado.centro_geografico
        
        # Começar com o centro geográfico
        melhor_pos = Coordenada(centro.x, centro.y)
        
        # Verificar se o centro está livre
        if self._posicao_livre(melhor_pos, sigla):
            return melhor_pos
        
        # Buscar posição livre em círculos concêntricos
        for raio in range(10, 50, 5):
            for angulo in range(0, 360, 15):
                rad = math.radians(angulo)
                x = centro.x + raio * math.cos(rad)
                y = centro.y + raio * math.sin(rad)
                
                pos_teste = Coordenada(x, y)
                
                # Verificar se está dentro dos limites e livre
                if (self._dentro_dos_limites(pos_teste, estado.limites) and 
                    self._posicao_livre(pos_teste, sigla)):
                    return pos_teste
        
        # Se não encontrou posição livre, retornar centro geográfico
        return centro
    
    def _posicao_livre(self, posicao: Coordenada, sigla_excluir: str) -> bool:
        """Verifica se uma posição está livre de conflitos"""
        for outra_sigla, outro_estado in self.estados.items():
            if outra_sigla != sigla_excluir and outro_estado.posicao_atual:
                distancia = posicao.distancia_para(outro_estado.posicao_atual)
                if distancia < self.distancia_minima_siglas:
                    return False
        return True
    
    def _dentro_dos_limites(self, posicao: Coordenada, limites: Dict) -> bool:
        """Verifica se uma posição está dentro dos limites"""
        return (limites['min_x'] <= posicao.x <= limites['max_x'] and
                limites['min_y'] <= posicao.y <= limites['max_y'])
    
    def validar_mapa_completo(self) -> Dict[str, ResultadoValidacao]:
        """Valida todas as posições do mapa"""
        resultados = {}
        
        print("🔍 Iniciando validação completa do mapa...")
        print("=" * 60)
        
        for sigla in sorted(self.estados.keys()):
            resultado = self.validar_posicao_estado(sigla)
            resultados[sigla] = resultado
            
            status = "✅" if resultado.valido else "❌"
            nome = self.estados[sigla].nome
            print(f"{status} {sigla:2} - {nome:20} | {resultado.motivo}")
        
        return resultados
    
    def gerar_relatorio_detalhado(self, resultados: Dict[str, ResultadoValidacao]) -> str:
        """Gera relatório detalhado da validação"""
        validos = sum(1 for r in resultados.values() if r.valido)
        total = len(resultados)
        
        relatorio = f"""
📊 RELATÓRIO DE VALIDAÇÃO DO MAPA DO BRASIL
{'=' * 60}

📈 ESTATÍSTICAS GERAIS:
• Total de estados: {total}
• Posições válidas: {validos} ({validos/total*100:.1f}%)
• Posições com problemas: {total - validos} ({(total-validos)/total*100:.1f}%)

🔴 ESTADOS COM PROBLEMAS:
"""
        
        problemas_por_regiao = {}
        for sigla, resultado in resultados.items():
            if not resultado.valido:
                regiao = self.estados[sigla].regiao
                if regiao not in problemas_por_regiao:
                    problemas_por_regiao[regiao] = []
                problemas_por_regiao[regiao].append((sigla, resultado))
        
        for regiao, problemas in problemas_por_regiao.items():
            relatorio += f"\n🌎 {regiao.upper()}:\n"
            for sigla, resultado in problemas:
                nome = self.estados[sigla].nome
                relatorio += f"  • {sigla} - {nome}\n"
                relatorio += f"    Problema: {resultado.motivo}\n"
                relatorio += f"    Posição atual: ({resultado.posicao_atual.x:.1f}, {resultado.posicao_atual.y:.1f})\n"
                if resultado.posicao_sugerida:
                    relatorio += f"    Posição sugerida: ({resultado.posicao_sugerida.x:.1f}, {resultado.posicao_sugerida.y:.1f})\n"
                relatorio += "\n"
        
        relatorio += """
🔧 RECOMENDAÇÕES:
1. Execute o método 'aplicar_correcoes_automaticas()' para corrigir automaticamente
2. Para ajustes manuais, use 'gerar_arquivo_correcoes()'
3. Teste as correções com 'simular_correcoes()'
"""
        
        return relatorio
    
    def aplicar_correcoes_automaticas(self) -> Dict[str, Coordenada]:
        """Aplica correções automáticas para todos os problemas"""
        resultados = self.validar_mapa_completo()
        correcoes = {}
        
        print("\n🔧 Aplicando correções automáticas...")
        print("=" * 50)
        
        for sigla, resultado in resultados.items():
            if not resultado.valido and resultado.posicao_sugerida:
                estado = self.estados[sigla]
                pos_antiga = estado.posicao_atual
                pos_nova = resultado.posicao_sugerida
                
                # Aplicar correção
                estado.posicao_atual = pos_nova
                correcoes[sigla] = pos_nova
                
                print(f"✅ {sigla}: ({pos_antiga.x:.1f}, {pos_antiga.y:.1f}) → "
                      f"({pos_nova.x:.1f}, {pos_nova.y:.1f})")
        
        print(f"\n🎯 Total de correções aplicadas: {len(correcoes)}")
        return correcoes
    
    def gerar_arquivo_correcoes(self, arquivo_saida: str = "posicoes_corrigidas.json") -> bool:
        """Gera arquivo JSON com as posições corrigidas"""
        try:
            posicoes = {}
            for sigla, estado in self.estados.items():
                if estado.posicao_atual:
                    posicoes[sigla] = {
                        'x': round(estado.posicao_atual.x, 1),
                        'y': round(estado.posicao_atual.y, 1)
                    }
            
            with open(arquivo_saida, 'w', encoding='utf-8') as f:
                json.dump(posicoes, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Arquivo de correções salvo: {arquivo_saida}")
            return True
            
        except Exception as e:
            print(f"❌ Erro ao salvar arquivo: {e}")
            return False
    
    def gerar_codigo_javascript(self) -> str:
        """Gera código JavaScript para atualizar as posições no frontend"""
        js_code = """
// Código JavaScript para atualizar posições das siglas
function atualizarPosicoesSiglas() {
    const posicoesCorrigidas = {
"""
        
        for sigla, estado in sorted(self.estados.items()):
            if estado.posicao_atual:
                js_code += f'        "{sigla}": {{x: {estado.posicao_atual.x:.1f}, y: {estado.posicao_atual.y:.1f}}},\n'
        
        js_code += """    };
    
    // Aplicar posições
    Object.entries(posicoesCorrigidas).forEach(([sigla, pos]) => {
        const elemento = document.querySelector(`.estado-sigla:contains("${sigla}")`);
        if (elemento) {
            elemento.setAttribute('x', pos.x);
            elemento.setAttribute('y', pos.y);
        }
    });
    
    // Salvar no localStorage
    localStorage.setItem('siglas_positions', JSON.stringify(posicoesCorrigidas));
    
    console.log('✅ Posições das siglas atualizadas com sucesso!');
}

// Executar atualização
atualizarPosicoesSiglas();
"""
        return js_code


def main():
    """Função principal para executar a validação"""
    print("🗺️  VALIDADOR DE POSIÇÕES DO MAPA DO BRASIL")
    print("=" * 60)
    
    # Criar validador
    validador = ValidadorMapaBrasil()
    
    # Carregar posições atuais
    if not validador.carregar_posicoes_atuais():
        print("❌ Erro ao carregar posições. Usando posições padrão.")
    
    # Executar validação completa
    resultados = validador.validar_mapa_completo()
    
    # Gerar e exibir relatório
    relatorio = validador.gerar_relatorio_detalhado(resultados)
    print(relatorio)
    
    # Aplicar correções automáticas
    resposta = input("\n🤔 Deseja aplicar correções automáticas? (s/n): ").lower()
    if resposta in ['s', 'sim', 'y', 'yes']:
        correcoes = validador.aplicar_correcoes_automaticas()
        
        if correcoes:
            # Validar novamente após correções
            print("\n🔍 Validando após correções...")
            resultados_pos_correcao = validador.validar_mapa_completo()
            
            # Gerar arquivos de saída
            validador.gerar_arquivo_correcoes("posicoes_corrigidas.json")
            
            # Gerar código JavaScript
            js_code = validador.gerar_codigo_javascript()
            with open("atualizar_posicoes.js", "w", encoding="utf-8") as f:
                f.write(js_code)
            print("✅ Código JavaScript salvo: atualizar_posicoes.js")
            
            print("\n🎉 Validação e correção concluídas com sucesso!")
        else:
            print("ℹ️  Nenhuma correção foi necessária.")
    
    print("\n👋 Validação finalizada!")


if __name__ == "__main__":
    main() 