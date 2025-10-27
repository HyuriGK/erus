import http.server
import socketserver
import webbrowser
import os
from threading import Timer
import sqlite3
import json
from datetime import datetime, timedelta
import hashlib
import time
from socketserver import ThreadingMixIn
import threading
import socket  
from urllib.parse import parse_qs

# ==============================================================================
# Configurações Globais
# ==============================================================================

# Configurações do servidor
PORT = 8000
HOST = "10.1.1.177"

# Nomes dos arquivos HTML
MAIN_HTML_FILE = "prog.acab.html"
FATURAMENTO_HTML_FILE = "faturamento.html"
DASHBOARD_HTML_FILE = "dashboard.html"
CARTEIRA_HTML_FILE = "CARTEIRA.html"
REFUGO_HTML_FILE = "REFUGO.html"
TERCEIRO_HTML_FILE = "terceiro.html"
INVENTARIO_HTML_FILE = "inventario.html"
RAMAIS_HTML_FILE = "ramais.html"
UNIFICADO_HTML_FILE = "unificado.html"
CLIENTES_HTML_FILE = "clientes.html" # Dashboard de Análise de Faturamento - Por Cliente
ITENS_HTML_FILE = "itens.html"
FICHA_ITEM_HTML_FILE = "ficha_item.html"
ADERENCIA_HTML_FILE = "aderencia.html"
PRODUCAO_APONTADA_HTML_FILE = "producao_apontada.html"
FATURAMENTO_DETALHADO_FILE = "faturamentodetalhado.html"
CONTROLE_MODELOS_HTML_FILE = "controlemodelos.html"
ORDEM_MONITOR_HTML_FILE = "ordem_monitor.html" # NOVO: Arquivo do monitor de ordens

# Nomes dos bancos de dados
DB_NAME = "programacao_acabamento.db"
PRODUCAO_DB_NAME = "producaobancodedados.db" # BANCO DE DADOS PARA O MONITOR

# ==============================================================================
# Mixin e Funções de Auxílio
# ==============================================================================
class ThreadedTCPServer(ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True

def parse_float_br(value):
    """
    Converte uma string de formato numérico BR (vírgula decimal, 
    ponto separador de milhar opcional) para float.
    """
    if isinstance(value, (int, float)):
        return float(value)
    
    value_str = str(value or '0').strip()
    
    # Remove R$, símbolos de porcentagem, espaços, etc.
    value_str = value_str.replace('R$', '').replace('%', '').replace(' ', '').strip()
    
    # Se houver ponto E vírgula (padrão 1.234,50), remove o ponto (separador de milhar) e troca a vírgula por ponto.
    if value_str.count('.') > 0 and value_str.count(',') > 0:
        value_str = value_str.replace('.', '')
        value_str = value_str.replace(',', '.')
    # Se houver apenas vírgula (padrão 4,67), troca por ponto.
    elif value_str.count(',') > 0:
        value_str = value_str.replace(',', '.')

    try:
        return float(value_str)
    except ValueError:
        return 0.0

def clean_and_parse_float(value):
    """
    Limpa e converte um valor que pode vir com formatação de milhar BR (ponto)
    e decimal BR (vírgula) ou decimal universal (ponto).
    """
    if isinstance(value, (int, float)):
        return float(value)
    
    value_str = str(value or '0').strip()
    
    # 1. Tenta limpar o separador de milhar BR (ponto) e usa vírgula como decimal (Ex: 1.000,50 -> 1000,50)
    if value_str.count('.') > 0 and value_str.count(',') > 0:
        value_str = value_str.replace('.', '')
    
    # 2. Troca vírgula por ponto (para o padrão float do Python/DB) (Ex: 1000,50 -> 1000.50)
    value_str = value_str.replace(',', '.')
    
    try:
        return float(value_str)
    except ValueError:
        return 0.0

# ==============================================================================
# Classe de Banco de Dados Principal (programacao_acabamento.db)
# ==============================================================================
class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME, timeout=30, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row 
        self.create_tables()

    def get_cursor(self):
        return self.conn.cursor()

    def create_tables(self):
        cursor = self.get_cursor()
        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS registros (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT, codigo TEXT NOT NULL,
                    op TEXT DEFAULT '', descricao TEXT NOT NULL, quant INTEGER NOT NULL,
                    quant_escariar INTEGER DEFAULT 0, quant_rebarba INTEGER DEFAULT 0, peso REAL,
                    material TEXT DEFAULT '', cliente TEXT DEFAULT '', carga TEXT DEFAULT '',
                    terceiro TEXT DEFAULT '', rebarbar TEXT DEFAULT '', escariar TEXT DEFAULT '',
                    observacoes TEXT DEFAULT '', situacao TEXT DEFAULT 'finalizada',
                    data_finalizacao TEXT DEFAULT '', prioridade TEXT DEFAULT 'baixa',
                    tipo TEXT DEFAULT 'interno', causa TEXT DEFAULT '', setor TEXT DEFAULT '',
                    apontado INTEGER DEFAULT 0, valor REAL DEFAULT 0, ultFaturamento TEXT DEFAULT ''
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS recebimentos (
                    registro_id INTEGER PRIMARY KEY, carga TEXT NOT NULL, data_recebimento TEXT NOT NULL,
                    FOREIGN KEY (registro_id) REFERENCES registros(id) ON DELETE CASCADE
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS itens (
                    codigo TEXT PRIMARY KEY, descricao TEXT, peso REAL, cliente TEXT
                )
            ''')
            cursor.execute(''' CREATE TABLE IF NOT EXISTS programacoes ( id INTEGER PRIMARY KEY AUTOINCREMENT, data_criacao TEXT NOT NULL, data_entrega TEXT NOT NULL, arquivo TEXT NOT NULL ) ''')
            cursor.execute(''' CREATE TABLE IF NOT EXISTS programacao_itens ( id INTEGER PRIMARY KEY AUTOINCREMENT, programacao_id INTEGER NOT NULL, registro_id INTEGER NOT NULL, FOREIGN KEY (programacao_id) REFERENCES programacoes(id) ) ''')
            cursor.execute(''' CREATE TABLE IF NOT EXISTS carteira_pedidos ( id INTEGER PRIMARY KEY AUTOINCREMENT, pedido TEXT NOT NULL, entrega TEXT NOT NULL, razao_social TEXT NOT NULL, codigo TEXT NOT NULL, nome_produto TEXT NOT NULL, material TEXT NOT NULL, saldo REAL NOT NULL, peso_un REAL NOT NULL, peso_total REAL NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ) ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ramais (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, ramal TEXT NOT NULL
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS faturamento_clientes_geral (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data TEXT, codigo_cliente TEXT, cliente TEXT, codigo_item TEXT,
                    descricao_item TEXT, quant REAL, preco_un REAL, material TEXT,
                    peso_un REAL, peso_total REAL, valor_total REAL
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS faturamento_clientes_detalhado (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data TEXT, codigo_cliente TEXT, cliente TEXT, codigo_item TEXT,
                    descricao_item TEXT, quant REAL, preco_un REAL, material TEXT,
                    peso_un REAL, peso_total REAL, valor_total REAL
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS fichas_avaliacao (
                    "main-item-code" TEXT PRIMARY KEY NOT NULL,
                    "client-name" TEXT, "client-billing" REAL, "client-weight-billed" REAL,
                    "client-billing-rep" REAL, "item-total-weight" REAL, "main-item-description" TEXT,
                    "item-rend-metalurgico" TEXT, "item-weight" REAL, "item-molde-metal" TEXT,
                    "item-qty" INTEGER, "item-analise-rendimento" TEXT,
                    "photoSrc" TEXT,
                    "dificuldade-moldagem" TEXT, "dificuldade-fusao" TEXT,
                    "dificuldade-acabamento" TEXT, "dificuldade-custos" TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS relatorios_aderencia (
                    name TEXT PRIMARY KEY NOT NULL,
                    data TEXT,
                    headerFusao TEXT,
                    headerAcabamento TEXT,
                    fusao_data TEXT,
                    acabamento_data TEXT,
                    pesoProgramado REAL,
                    pesoRealizado REAL,
                    aderenciaFusaoNum REAL,
                    aderenciaAcabamentoNum REAL
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS producao_apontada (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data TEXT,
                    setor TEXT,
                    produto TEXT,
                    liga TEXT,
                    peso_un REAL,
                    quant INTEGER,
                    peso_liq_total REAL
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS metas_producao_setor (
                    setor TEXT PRIMARY KEY NOT NULL,
                    meta_peso REAL NOT NULL
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS metas_faturamento (
                    mes_ano TEXT PRIMARY KEY NOT NULL,
                    meta_peso REAL NOT NULL
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS producao_total_mensal (
                    mes_ano TEXT PRIMARY KEY NOT NULL,
                    peso_total REAL NOT NULL DEFAULT 0.0
                )
            ''')
            cursor.execute('DROP TABLE IF EXISTS producao_total_refugo') 
            
            # Dados iniciais
            cursor.execute('SELECT COUNT(*) FROM ramais')
            if cursor.fetchone()[0] == 0:
                dados_iniciais_ramais = [
                    ('ALESSANDRA', '210'), ('ALMOXARIFADO', '206'), ('EDUARDA', '201'),
                    ('ELISANGELA', '202'), ('GIOVANI FELIX', '208'), ('HUMBERTO', '211'),
                    ('ISAAC', '209'), ('JADSON', '205'), ('LABORATORIO', '207'),
                    ('LAYANE', '200'), ('LUIS', '203'), ('ROBISON', '204')
                ]
                cursor.executemany('INSERT INTO ramais (nome, ramal) VALUES (?, ?)', dados_iniciais_ramais)

            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Erro ao criar tabelas: {e}")
        finally:
            cursor.close()

    def close(self):
        if self.conn:
            self.conn.close()

    # --- Métodos de Dados (Mantidos no código completo) ---
    
    def save_producao_total_mensal(self, mes_ano, peso_total):
        cursor = self.get_cursor()
        try:
            sql = '''
                INSERT INTO producao_total_mensal (mes_ano, peso_total)
                VALUES (?, ?)
                ON CONFLICT(mes_ano) DO UPDATE SET
                    peso_total=excluded.peso_total
            '''
            cursor.execute(sql, (mes_ano, peso_total))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Erro ao salvar peso total de produção (refugo mensal): {e}")
            self.conn.rollback()
            return False
        finally:
            cursor.close()

    def get_producao_total_mensal(self, mes_ano):
        cursor = self.get_cursor()
        try:
            cursor.execute('SELECT peso_total FROM producao_total_mensal WHERE mes_ano = ?', (mes_ano,))
            row = cursor.fetchone()
            return row['peso_total'] if row else 0.0 
        except sqlite3.Error as e:
            print(f"Erro ao buscar peso total de produção (refugo mensal): {e}")
            return 0.0
        finally:
            cursor.close()

    def save_meta_producao_setor(self, setor, meta_peso):
        cursor = self.get_cursor()
        try:
            sql = '''
                INSERT INTO metas_producao_setor (setor, meta_peso)
                VALUES (?, ?)
                ON CONFLICT(setor) DO UPDATE SET
                    meta_peso=excluded.meta_peso
            '''
            cursor.execute(sql, (setor, meta_peso))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Erro ao salvar meta de produção do setor '{setor}': {e}")
            self.conn.rollback()
            return False
        finally:
            cursor.close()

    def get_all_metas_producao_setor(self):
        cursor = self.get_cursor()
        try:
            cursor.execute('SELECT setor, meta_peso FROM metas_producao_setor')
            return [{'setor': row['setor'], 'meta_peso': row['meta_peso']} for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Erro ao buscar metas de produção dos setores: {e}")
            return []
        finally:
            cursor.close()
            
    def clear_metas_producao_setor(self):
        cursor = self.get_cursor()
        try:
            cursor.execute('DELETE FROM metas_producao_setor')
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Erro ao limpar metas de produção dos setores: {e}")
            self.conn.rollback()
            return False
        finally:
            cursor.close()

    def save_faturamento_data_geral(self, data_array):
        cursor = self.get_cursor()
        try:
            cursor.execute('BEGIN TRANSACTION')
            cursor.execute('DELETE FROM faturamento_clientes_geral')
            rows_to_insert = []
            if len(data_array) > 1:
                for row in data_array[1:]:
                    if len(row) >= 11:
                        try:
                            quant = parse_float_br(row[5])
                            preco_un = parse_float_br(row[6])
                            peso_un = parse_float_br(row[8]) 
                            peso_total_calc = parse_float_br(row[9])
                            valor_total_calc = parse_float_br(row[10])
                            
                            rows_to_insert.append((
                                str(row[0]), str(row[1] or ''), str(row[2] or ''), str(row[3] or ''),
                                str(row[4] or ''), quant, preco_un, str(row[7] or ''), peso_un,
                                peso_total_calc, valor_total_calc
                            ))
                        except Exception as e:
                            print(f"Aviso: Linha de dados ignorada devido a erro de conversão: {e}. Linha: {row}")
                            continue
            if rows_to_insert:
                cursor.executemany('''
                    INSERT INTO faturamento_clientes_geral (
                        data, codigo_cliente, cliente, codigo_item, descricao_item, 
                        quant, preco_un, material, peso_un, peso_total, valor_total
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', rows_to_insert)
            self.conn.commit()
            return {'success': True}
        except sqlite3.Error as e:
            print(f"Erro ao salvar dados de faturamento de clientes (geral): {e}")
            self.conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            cursor.close()

    def get_faturamento_data_geral(self):
        cursor = self.get_cursor()
        try:
            cursor.execute('SELECT * FROM faturamento_clientes_geral')
            data_rows = []
            for row in cursor.fetchall():
                data_rows.append([
                    row['data'], row['codigo_cliente'], row['cliente'], row['codigo_item'], 
                    row['descricao_item'], row['quant'], row['preco_un'], row['material'], 
                    row['peso_un'], row['peso_total'], row['valor_total']
                ])
            return data_rows
        except sqlite3.Error as e:
            print(f"Erro ao buscar dados de faturamento de clientes (geral): {e}")
            return []
        finally:
            cursor.close()
            
    def save_faturamento_data_detalhado(self, data_array):
        cursor = self.get_cursor()
        try:
            cursor.execute('BEGIN TRANSACTION')
            cursor.execute('DELETE FROM faturamento_clientes_detalhado')
            rows_to_insert = []
            if len(data_array) > 1:
                for row in data_array[1:]:
                    if len(row) >= 11:
                        try:
                            quant = parse_float_br(row[5])
                            preco_un = parse_float_br(row[6])
                            peso_un = parse_float_br(row[8]) 
                            peso_total_calc = quant * peso_un
                            valor_total_calc = quant * preco_un

                            rows_to_insert.append((
                                str(row[0]), str(row[1] or ''), str(row[2] or ''), str(row[3] or ''),
                                str(row[4] or ''), quant, preco_un, str(row[7] or ''), peso_un,
                                peso_total_calc, valor_total_calc
                            ))
                        except Exception as e:
                            print(f"Aviso: Linha de dados detalhada ignorada devido a erro de conversão: {e}. Linha: {row}")
                            continue
            if rows_to_insert:
                cursor.executemany('''
                    INSERT INTO faturamento_clientes_detalhado (
                        data, codigo_cliente, cliente, codigo_item, descricao_item, 
                        quant, preco_un, material, peso_un, peso_total, valor_total
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', rows_to_insert)
            self.conn.commit()
            return {'success': True}
        except sqlite3.Error as e:
            print(f"Erro ao salvar dados de faturamento de clientes detalhado: {e}")
            self.conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            cursor.close()

    def get_faturamento_data_detalhado(self):
        cursor = self.get_cursor()
        try:
            cursor.execute('SELECT * FROM faturamento_clientes_detalhado')
            data_rows = []
            for row in cursor.fetchall():
                data_rows.append([
                    row['data'], row['codigo_cliente'], row['cliente'], row['codigo_item'], 
                    row['descricao_item'], row['quant'], row['preco_un'], row['material'], 
                    row['peso_un'], row['peso_total'], row['valor_total']
                ])
            return data_rows
        except sqlite3.Error as e:
            print(f"Erro ao buscar dados de faturamento de clientes detalhado: {e}")
            return []
        finally:
            cursor.close()
    
    def save_faturamento_data_itens(self, data_array):
        return self.save_faturamento_data_detalhado(data_array)

    def get_faturamento_data_itens(self):
        return self.get_faturamento_data_detalhado()
            
    def save_meta_peso(self, mes_ano, meta_peso):
        cursor = self.get_cursor()
        try:
            sql = '''
                INSERT INTO metas_faturamento (mes_ano, meta_peso)
                VALUES (?, ?)
                ON CONFLICT(mes_ano) DO UPDATE SET
                    meta_peso=excluded.meta_peso
            '''
            cursor.execute(sql, (mes_ano, meta_peso))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Erro ao salvar meta de faturamento: {e}")
            self.conn.rollback()
            return False
        finally:
            cursor.close()

    def get_meta_peso(self, mes_ano):
        cursor = self.get_cursor()
        try:
            cursor.execute('SELECT meta_peso FROM metas_faturamento WHERE mes_ano = ?', (mes_ano,))
            row = cursor.fetchone()
            return row['meta_peso'] if row else 0.0 
        except sqlite3.Error as e:
            print(f"Erro ao buscar meta de faturamento: {e}")
            return 0.0
        finally:
            cursor.close()

    def save_producao_data(self, data_array):
        cursor = self.get_cursor()
        try:
            cursor.execute('BEGIN TRANSACTION')
            cursor.execute('DELETE FROM producao_apontada')
            rows_to_insert = []
            if data_array and len(data_array) > 0:
                for row in data_array:
                    if len(row) >= 7: 
                        try:
                            data = str(row[0] or '') 
                            setor = str(row[1] or '')
                            produto = str(row[2] or '')
                            liga = str(row[3] or '')
                            peso_un = clean_and_parse_float(row[4])
                            quant = int(clean_and_parse_float(row[5])) 
                            peso_liq_total = clean_and_parse_float(row[6])
                            rows_to_insert.append((
                                data, setor, produto, liga, peso_un, quant, peso_liq_total
                            ))
                        except Exception as e:
                            print(f"Aviso: Linha de dados de produção ignorada devido a erro de conversão: {e}. Linha: {row}")
                            continue
            if rows_to_insert:
                cursor.executemany('''
                    INSERT INTO producao_apontada (
                        data, setor, produto, liga, peso_un, quant, peso_liq_total
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', rows_to_insert)
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Erro ao salvar dados de produção apontada: {e}")
            self.conn.rollback()
            return False
        finally:
            cursor.close()

    def get_producao_data(self):
        cursor = self.get_cursor()
        try:
            cursor.execute('SELECT data, setor, produto, liga, peso_un, quant, peso_liq_total FROM producao_apontada ORDER BY data DESC')
            header = ["Data", "Setor", "Produto", "Liga", "Peso (un)", "Quant.", "Peso Liq. Total"]
            data_rows = [header]
            for row in cursor.fetchall():
                data_rows.append([
                    row['data'], row['setor'], row['produto'], row['liga'],
                    row['peso_un'], row['quant'], row['peso_liq_total']
                ])
            return data_rows
        except sqlite3.Error as e:
            print(f"Erro ao buscar dados de produção apontada: {e}")
            return [["Data", "Setor", "Produto", "Liga", "Peso (un)", "Quant.", "Peso Liq. Total"]]
        finally:
            cursor.close()
    
    def clear_producao_data(self):
        cursor = self.get_cursor()
        try:
            cursor.execute('DELETE FROM producao_apontada')
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Erro ao limpar dados de produção apontada: {e}")
            self.conn.rollback()
            return False
        finally:
            cursor.close()
    
    def get_faturamento_registros(self):
        cursor = self.get_cursor()
        try:
            cursor.execute('SELECT * FROM registros WHERE tipo = "faturamento" ORDER BY data DESC')
            registros = []
            for row in cursor.fetchall():
                registro = dict(row)
                registro['peso_total'] = (registro['peso'] or 0) * (registro['quant'] or 0)
                registros.append(registro)
            return registros
        except sqlite3.Error as e:
            print(f"Erro ao buscar registros de faturamento: {e}")
            return []
        finally:
            cursor.close()
    
    def get_refugo_registros(self):
        cursor = self.get_cursor()
        try:
            cursor.execute('SELECT *, CAST(apontado AS INTEGER) as apontado FROM registros WHERE tipo = "refugo" ORDER BY data DESC')
            registros = []
            for row in cursor.fetchall():
                registro = dict(row)
                registro['peso_total'] = (registro['peso'] or 0) * (registro['quant'] or 0)
                registros.append(registro)
            return registros
        except sqlite3.Error as e:
            print(f"Erro ao buscar registros de refugo: {e}")
            return []
        finally:
            cursor.close()
    
    def clear_refugo_data(self):
        cursor = self.get_cursor()
        try:
            cursor.execute('DELETE FROM registros WHERE tipo = "refugo"')
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Erro ao limpar dados de refugo: {e}")
            self.conn.rollback()
            return False
        finally:
            cursor.close()

    def import_refugo_data(self, data_array):
        cursor = self.get_cursor()
        try:
            cursor.execute('BEGIN TRANSACTION')
            cursor.execute('DELETE FROM registros WHERE tipo = "refugo"')
            rows_to_insert = []
            for row in data_array:
                rows_to_insert.append((
                    row.get('data'), row.get('codigo'), row.get('descricao', ''), row.get('quant', 0), 
                    row.get('peso', 0.0), row.get('material', ''), row.get('causa', ''), 
                    row.get('setor', ''), row.get('apontado', 0), 'refugo'
                ))
            if rows_to_insert:
                cursor.executemany('''
                    INSERT INTO registros (
                        data, codigo, descricao, quant, peso, material, causa, setor, apontado, tipo
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', rows_to_insert)
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Erro ao importar dados de refugo: {e}")
            self.conn.rollback()
            return False
        finally:
            cursor.close()
            
    def get_inventario_registros(self):
        cursor = self.get_cursor()
        try:
            cursor.execute('SELECT * FROM registros WHERE tipo = "estoque" ORDER BY codigo ASC')
            registros = []
            for row in cursor.fetchall():
                registro = dict(row)
                registro['peso_total'] = (registro['peso'] or 0) * (registro['quant'] or 0)
                registros.append(registro)
            return registros
        except sqlite3.Error as e:
            print(f"Erro ao buscar registros de inventário: {e}")
            return []
        finally:
            cursor.close()

    def get_carteira_pedidos(self):
        cursor = self.get_cursor()
        try:
            cursor.execute('SELECT * FROM carteira_pedidos ORDER BY created_at DESC')
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Erro ao buscar pedidos da carteira: {e}")
            return []
        finally:
            cursor.close()

    def save_carteira_pedidos(self, pedidos):
        cursor = self.get_cursor()
        try:
            cursor.execute('BEGIN TRANSACTION')
            cursor.execute('DELETE FROM carteira_pedidos')
            for pedido in pedidos:
                cursor.execute('''
                    INSERT INTO carteira_pedidos (pedido, entrega, razao_social, codigo, nome_produto, material, saldo, peso_un, peso_total)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    pedido.get('pedido', ''), pedido.get('entrega', ''), pedido.get('razao_social', ''),
                    pedido.get('codigo', ''), pedido.get('nome_produto', ''), pedido.get('material', ''),
                    pedido.get('saldo', 0), pedido.get('peso_un', 0), pedido.get('peso_total', 0)
                ))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Erro ao salvar carteira de pedidos: {e}")
            self.conn.rollback()
            return False
        finally:
            cursor.close()
    
    def add_registro(self, registro):
        cursor = self.get_cursor()
        try:
            cursor.execute('''
                INSERT INTO registros (
                    data, codigo, op, descricao, quant, peso, material, cliente, carga, 
                    terceiro, rebarbar, escariar, observacoes, situacao, data_finalizacao, 
                    prioridade, tipo, causa, setor, apontado, valor, ultFaturamento
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                registro.get('data'), registro.get('codigo'), registro.get('op', ''), 
                registro.get('descricao', ''), registro.get('quant', 0), 
                registro.get('peso', 0.0), registro.get('material', ''), 
                registro.get('cliente', ''), registro.get('carga', ''), 
                registro.get('terceiro', ''), registro.get('rebarbar', ''), 
                registro.get('escariar', ''), registro.get('observacoes', ''), 
                registro.get('situacao', 'finalizada'), registro.get('data_finalizacao', ''), 
                registro.get('prioridade', 'baixa'), registro.get('tipo', 'interno'), 
                registro.get('causa', ''), registro.get('setor', ''), 
                registro.get('apontado', 0), registro.get('valor', 0.0), 
                registro.get('ultFaturamento', '')
            ))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Erro ao adicionar registro: {e}")
            self.conn.rollback()
            return None
        finally:
            cursor.close()
            
    def update_registro(self, registro_id, updates):
        cursor = self.get_cursor()
        try:
            set_clauses = []
            values = []
            for key, value in updates.items():
                set_clauses.append(f"{key} = ?")
                values.append(value)
            if not set_clauses:
                return False
            values.append(registro_id)
            sql = f"UPDATE registros SET {', '.join(set_clauses)} WHERE id = ?"
            cursor.execute(sql, tuple(values))
            self.conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Erro ao atualizar registro {registro_id}: {e}")
            self.conn.rollback()
            return False
        finally:
            cursor.close()
            
    def delete_registro(self, registro_id):
        cursor = self.get_cursor()
        try:
            cursor.execute('DELETE FROM registros WHERE id = ?', (registro_id,))
            self.conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Erro ao deletar registro {registro_id}: {e}")
            self.conn.rollback()
            return False
        finally:
            cursor.close()

    def get_all_registros(self):
        cursor = self.get_cursor()
        try:
            cursor.execute('SELECT *, CAST(apontado AS INTEGER) as apontado FROM registros ORDER BY data DESC')
            registros = []
            for row in cursor.fetchall():
                registro = dict(row)
                registro['peso_total'] = (registro['peso'] or 0) * (registro['quant'] or 0)
                registros.append(registro)
            return registros
        except sqlite3.Error as e:
            print(f"Erro ao buscar todos os registros: {e}")
            return []
        finally:
            cursor.close()
            
    def get_recebimentos(self):
        cursor = self.get_cursor()
        try:
            cursor.execute('SELECT registro_id as id, carga, data_recebimento FROM recebimentos')
            return [dict(row) for row in cursor.fetchall()] 
        except sqlite3.Error as e:
            print(f"Erro ao buscar recebimentos: {e}")
            return []
        finally:
            cursor.close()

    def add_recebimento(self, registro_id, carga):
        cursor = self.get_cursor()
        data_recebimento = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO recebimentos (registro_id, carga, data_recebimento)
                VALUES (?, ?, ?)
            ''', (registro_id, carga, data_recebimento))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Erro ao adicionar recebimento: {e}")
            self.conn.rollback()
            return False
        finally:
            cursor.close()

    def remove_recebimento(self, registro_id):
        cursor = self.get_cursor()
        try:
            cursor.execute('DELETE FROM recebimentos WHERE registro_id = ?', (registro_id,))
            self.conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Erro ao remover recebimento: {e}")
            self.conn.rollback()
            return False
        finally:
            cursor.close()

    def get_all_ramais(self):
        cursor = self.get_cursor()
        try:
            cursor.execute('SELECT * FROM ramais ORDER BY nome ASC')
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Erro ao buscar ramais: {e}")
            return []
        finally:
            cursor.close()

    def add_ramal(self, data):
        cursor = self.get_cursor()
        try:
            cursor.execute('INSERT INTO ramais (nome, ramal) VALUES (?, ?)', 
                           (data.get('nome'), data.get('ramal')))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Erro ao adicionar ramal: {e}")
            self.conn.rollback()
            return None
        finally:
            cursor.close()

    def delete_ramal(self, ramal_id):
        cursor = self.get_cursor()
        try:
            cursor.execute('DELETE FROM ramais WHERE id = ?', (ramal_id,))
            self.conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Erro ao deletar ramal: {e}")
            self.conn.rollback()
            return False
        finally:
            cursor.close()
            
    def get_all_itens(self):
        cursor = self.get_cursor()
        try:
            cursor.execute('SELECT * FROM itens ORDER BY codigo ASC')
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Erro ao buscar itens: {e}")
            return []
        finally:
            cursor.close()

    def upsert_item(self, data):
        cursor = self.get_cursor()
        try:
            sql = '''
                INSERT INTO itens (codigo, descricao, peso, cliente)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(codigo) DO UPDATE SET
                    descricao=excluded.descricao,
                    peso=excluded.peso,
                    cliente=excluded.cliente
            '''
            cursor.execute(sql, (data.get('codigo'), data.get('descricao'), data.get('peso'), data.get('cliente')))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Erro ao salvar item: {e}")
            self.conn.rollback()
            return False
        finally:
            cursor.close()

    def delete_item(self, codigo):
        cursor = self.get_cursor()
        try:
            cursor.execute('DELETE FROM itens WHERE codigo = ?', (codigo,))
            self.conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Erro ao deletar item: {e}")
            self.conn.rollback()
            return False
        finally:
            cursor.close()

    def import_backup_data(self, data):
        print("Executando importação de backup...")
        try:
            self.conn.execute('BEGIN TRANSACTION')
            self.conn.execute('DELETE FROM registros WHERE tipo = "terceiro"')
            self.conn.execute('DELETE FROM recebimentos')
            self.conn.execute('DELETE FROM itens')
            
            if 'registros' in data:
                registros_to_insert = [(
                    r.get('data'), r.get('codigo'), r.get('op', ''), r.get('descricao', ''), 
                    r.get('quant', 0), r.get('peso', 0.0), r.get('material', ''), 
                    r.get('cliente', ''), r.get('carga', ''), r.get('terceiro', ''), 
                    r.get('rebarbar', ''), r.get('escariar', ''), r.get('observacoes', ''), 
                    r.get('situacao', 'finalizada'), r.get('data_finalizacao', ''), 
                    r.get('prioridade', 'baixa'), r.get('tipo', 'terceiro'), r.get('causa', ''),
                    r.get('setor', ''), r.get('apontado', 0), r.get('valor', 0.0), 
                    r.get('ultFaturamento', '')
                ) for r in data['registros']]
                
                if registros_to_insert:
                    self.conn.executemany('''
                        INSERT INTO registros (
                            data, codigo, op, descricao, quant, peso, material, cliente, carga, 
                            terceiro, rebarbar, escariar, observacoes, situacao, data_finalizacao, 
                            prioridade, tipo, causa, setor, apontado, valor, ultFaturamento
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', registros_to_insert)

            if 'recebidos' in data:
                recebimentos_to_insert = [(r.get('id'), r.get('carga'), r.get('data_recebimento', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))) 
                                           for r in data['recebidos'] if 'id' in r and 'carga' in r]
                if recebimentos_to_insert:
                    self.conn.executemany('''
                        INSERT OR REPLACE INTO recebimentos (registro_id, carga, data_recebimento)
                        VALUES (?, ?, ?)
                    ''', recebimentos_to_insert)
                    
            if 'itensConhecidos' in data:
                itens_to_insert = []
                for entry in data['itensConhecidos']:
                    if isinstance(entry, list) and len(entry) == 2:
                        codigo, item_data = entry
                        itens_to_insert.append((
                            item_data.get('codigo', codigo), 
                            item_data.get('descricao', ''), 
                            item_data.get('peso', 0.0), 
                            item_data.get('cliente', '')
                        ))
                if itens_to_insert:
                     self.conn.executemany('''
                        INSERT OR REPLACE INTO itens (codigo, descricao, peso, cliente)
                        VALUES (?, ?, ?, ?)
                    ''', itens_to_insert)
            
            self.conn.commit()
            print("Importação de backup concluída com sucesso.")
            return True
        except sqlite3.Error as e:
            print(f"Erro durante a importação de backup: {e}")
            self.conn.rollback()
            return False

    def get_all_aderencia_reports(self):
        cursor = self.get_cursor()
        try:
            cursor.execute('SELECT * FROM relatorios_aderencia ORDER BY data DESC')
            return [dict(row) for row in cursor.fetchall()] 
        except sqlite3.Error as e:
            print(f"Erro ao buscar relatórios de aderência: {e}")
            return []
        finally:
            cursor.close()

    def save_aderencia_report(self, name, data):
        cursor = self.get_cursor()
        try:
            sql = '''
                INSERT INTO relatorios_aderencia (
                    name, data, headerFusao, headerAcabamento, fusao_data, acabamento_data, 
                    pesoProgramado, pesoRealizado, aderenciaFusaoNum, aderenciaAcabamentoNum
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    data=excluded.data,
                    headerFusao=excluded.headerFusao,
                    headerAcabamento=excluded.headerAcabamento,
                    fusao_data=excluded.fusao_data,
                    acabamento_data=excluded.acabamento_data,
                    pesoProgramado=excluded.pesoProgramado,
                    pesoRealizado=excluded.pesoRealizado,
                    aderenciaFusaoNum=excluded.aderenciaFusaoNum,
                    aderenciaAcabamentoNum=excluded.aderenciaAcabamentoNum
            '''
            cursor.execute(sql, (
                name, data.get('data'), data.get('headerFusao'), data.get('headerAcabamento'),
                data.get('fusao_data'), data.get('acabamento_data'), data.get('pesoProgramado'),
                data.get('pesoRealizado'), data.get('aderenciaFusaoNum'), data.get('aderenciaAcabamentoNum')
            ))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Erro ao salvar relatório de aderência: {e}")
            self.conn.rollback()
            return False
        finally:
            cursor.close()

    def delete_aderencia_report(self, name):
        cursor = self.get_cursor()
        try:
            cursor.execute('DELETE FROM relatorios_aderencia WHERE name = ?', (name,))
            self.conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Erro ao deletar relatório de aderência: {e}")
            self.conn.rollback()
            return False
        finally:
            cursor.close()
            
    def get_all_fichas(self):
        cursor = self.get_cursor()
        try:
            cursor.execute('SELECT * FROM fichas_avaliacao')
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Erro ao buscar fichas de avaliação: {e}")
            return []
        finally:
            cursor.close()

    def save_ficha(self, ficha_data):
        cursor = self.get_cursor()
        try:
            keys = [f'"{k}"' for k in ficha_data.keys()]
            values = list(ficha_data.values())
            placeholders = ', '.join(['?'] * len(keys))
            set_updates = [f'"{k}"=excluded."{k}"' for k in ficha_data.keys()]
            
            sql = f'''
                INSERT INTO fichas_avaliacao ({', '.join(keys)})
                VALUES ({placeholders})
                ON CONFLICT("main-item-code") DO UPDATE SET {', '.join(set_updates)}
            '''
            cursor.execute(sql, values)
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Erro ao salvar ficha: {e}")
            self.conn.rollback()
            return False
        finally:
            cursor.close()

    def delete_ficha(self, item_code):
        cursor = self.get_cursor()
        try:
            cursor.execute('DELETE FROM fichas_avaliacao WHERE "main-item-code" = ?', (item_code,))
            self.conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Erro ao deletar ficha: {e}")
            self.conn.rollback()
            return False
        finally:
            cursor.close()

# ==============================================================================
# Classe de Banco de Dados de Produção (producaobancodedados.db)
# ==============================================================================
class ProducaoDatabase:
    def __init__(self):
        self.conn = sqlite3.connect(PRODUCAO_DB_NAME, timeout=30, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()

    def get_cursor(self):
        return self.conn.cursor()

    def create_tables(self):
        cursor = self.get_cursor()
        try:
            # Tabela simples de chave-valor para armazenar os diferentes objetos JSON da página
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS production_data_store (
                    data_key TEXT PRIMARY KEY NOT NULL,
                    data_json TEXT NOT NULL,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Erro ao criar tabelas no banco de dados de produção: {e}")
        finally:
            cursor.close()

    def save_data(self, key, json_data):
        """Salva ou atualiza um dado JSON para uma chave específica."""
        cursor = self.get_cursor()
        try:
            sql = '''
                INSERT INTO production_data_store (data_key, data_json, last_updated)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(data_key) DO UPDATE SET
                    data_json=excluded.data_json,
                    last_updated=CURRENT_TIMESTAMP
            '''
            cursor.execute(sql, (key, json_data))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Erro ao salvar dados de produção para a chave '{key}': {e}")
            self.conn.rollback()
            return False
        finally:
            cursor.close()

    def load_all_data(self):
        """Carrega todos os dados da tabela e os retorna como um dicionário."""
        cursor = self.get_cursor()
        all_data = {}
        try:
            cursor.execute('SELECT data_key, data_json FROM production_data_store')
            rows = cursor.fetchall()
            for row in rows:
                # Decodifica o JSON para que o Python o entenda como dict/list
                try:
                    all_data[row['data_key']] = json.loads(row['data_json'])
                except json.JSONDecodeError:
                    print(f"Aviso: JSON mal formatado no DB para a chave '{row['data_key']}'. Pulando.")
                    all_data[row['data_key']] = {} # Retorna um objeto vazio para evitar quebrar o JS
            return all_data
        except sqlite3.Error as e:
            print(f"Erro ao carregar todos os dados de produção: {e}")
            return {}
        finally:
            cursor.close()

    def clear_monitor_data(self):
        """Limpa os dados específicos do monitor de produção (opData e sectorData)."""
        cursor = self.get_cursor()
        try:
            # Deleta as chaves específicas para não afetar outros possíveis dados na tabela
            cursor.execute("DELETE FROM production_data_store WHERE data_key IN ('opData', 'sectorData')")
            self.conn.commit()
            return cursor.rowcount >= 0 # Retorna True mesmo se nada for deletado
        except sqlite3.Error as e:
            print(f"Erro ao limpar dados do monitor de produção: {e}")
            self.conn.rollback()
            return False
        finally:
            cursor.close()

    def clear_refugo_data_keys(self):
        """Limpa os dados específicos do dashboard de refugo (rawData e monthlyProduction)."""
        cursor = self.get_cursor()
        try:
            cursor.execute("DELETE FROM production_data_store WHERE data_key IN (?, ?)", 
                           ('refugoRawData', 'refugoMonthlyProduction'))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Erro ao limpar dados de refugo do monitor: {e}")
            self.conn.rollback()
            return False
        finally:
            cursor.close()

    def close(self):
        if self.conn:
            self.conn.close()

# ==============================================================================
# Handler de Requisições HTTP
# ==============================================================================
class Handler(http.server.SimpleHTTPRequestHandler):
    
    def __init__(self, *args, **kwargs):
        self.db = Database()
        self.db_prod = ProducaoDatabase() 
        super().__init__(*args, directory=os.getcwd(), **kwargs)

    def _send_json_response(self, data, status_code=200):
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def _read_json_body(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            return json.loads(post_data.decode('utf-8'))
        except (TypeError, json.JSONDecodeError, KeyError) as e:
            return None

    # --- HANDLERS GET (Omitidos para brevidade, mas incluídos no código final) ---
    def handle_get_load_producao_all(self):
        all_data = self.db_prod.load_all_data()
        self._send_json_response(all_data)

    def handle_get_producao_total_mensal(self):
        query_params = self.path.split('?', 1)
        mes_ano = None
        if len(query_params) > 1:
            params = parse_qs(query_params[1])
            mes_ano = params.get('mes_ano', [None])[0]
        if not mes_ano:
            self._send_json_response({'peso_total': 0.0, 'error': 'Parâmetro mes_ano é obrigatório.'}, status_code=400)
            return
        peso_total = self.db.get_producao_total_mensal(mes_ano)
        self._send_json_response({'peso_total': str(peso_total)}) 
        
    def handle_get_metas_producao_setor(self):
        metas = self.db.get_all_metas_producao_setor() 
        self._send_json_response(metas) 

    def handle_get_faturamento_clientes_geral(self):
        EXCEL_HEADERS = ["DATA", "CÓD. CLIENTE", "CLIENTE", "CÓDIGO", "DESCRIÇÃO", "QUANT.", "Preço (Un)", "MATERIAL", "Peso Un", "Peso Total", "R$ Total"]
        data_rows = self.db.get_faturamento_data_geral()
        final_data_array = [EXCEL_HEADERS] + data_rows
        self._send_json_response(final_data_array)
        
    def handle_get_faturamento_clientes_detalhado(self):
        EXCEL_HEADERS = ["DATA", "CÓD. CLIENTE", "CLIENTE", "CÓDIGO", "DESCRIÇÃO", "QUANT.", "Preço (Un)", "MATERIAL", "Peso Un", "Peso Total", "R$ Total"]
        data_rows = self.db.get_faturamento_data_detalhado()
        final_data_array = [EXCEL_HEADERS] + data_rows
        self._send_json_response(final_data_array)
        
    def handle_get_faturamento_itens(self):
        EXCEL_HEADERS = ["DATA", "CÓD. CLIENTE", "CLIENTE", "CÓDIGO", "DESCRIÇÃO", "QUANT.", "Preço (Un)", "MATERIAL", "Peso Un", "Peso Total", "R$ Total"]
        data_rows = self.db.get_faturamento_data_itens()
        final_data_array = [EXCEL_HEADERS] + data_rows
        self._send_json_response(final_data_array)

    def handle_get_meta_peso(self):
        query_params = self.path.split('?', 1)
        mes_ano = None
        if len(query_params) > 1:
            params = parse_qs(query_params[1])
            mes_ano = params.get('mes_ano', [None])[0]
        if not mes_ano:
            mes_ano = datetime.now().strftime('%Y-%m')
        meta_peso = self.db.get_meta_peso(mes_ano)
        self._send_json_response({'mes_ano': mes_ano, 'meta_peso': meta_peso}) 

    def handle_get_producao_data(self):
        data_rows = self.db.get_producao_data()
        self._send_json_response(data_rows)
    
    def handle_get_aderencia(self):
        reports = self.db.get_all_aderencia_reports()
        self._send_json_response(reports)

    def handle_get_fichas(self):
        fichas = self.db.get_all_fichas()
        self._send_json_response(fichas)

    def handle_get_itens(self):
        itens = self.db.get_all_itens()
        self._send_json_response(itens)
    
    def handle_get_registros(self):
        registros = self.db.get_all_registros()
        self._send_json_response(registros)

    def handle_get_recebidos(self):
        recebimentos = self.db.get_recebimentos()
        self._send_json_response(recebimentos)

    def handle_get_ramais(self):
        ramais = self.db.get_all_ramais()
        self._send_json_response(ramais)
        
    def handle_get_faturamento(self):
        registros = self.db.get_faturamento_registros()
        self._send_json_response(registros)
    
    def handle_get_refugo(self):
        registros = self.db.get_refugo_registros()
        self._send_json_response(registros)

    def handle_get_inventario(self):
        registros = self.db.get_inventario_registros()
        self._send_json_response(registros)

    def handle_get_carteira(self):
        pedidos = self.db.get_carteira_pedidos()
        self._send_json_response(pedidos)

    # --- HANDLERS POST (Omitidos para brevidade, mas incluídos no código final) ---
    def handle_post_save_producao_all(self):
        data_to_save = self._read_json_body()
        if not data_to_save or not isinstance(data_to_save, dict):
            self._send_json_response({'success': False, 'error': 'Corpo da requisição inválido ou ausente.'}, status_code=400)
            return
        success = True
        errors = []
        for key, value in data_to_save.items():
            try:
                json_value = json.dumps(value) 
                if not self.db_prod.save_data(key, json_value):
                    success = False
                    errors.append(key)
            except Exception as e:
                success = False
                errors.append(f"{key}: {e}")
        
        if success:
            self._send_json_response({'success': True, 'message': 'Todos os dados de produção foram salvos com sucesso.'})
        else:
            self._send_json_response({
                'success': False,
                'error': f'Falha ao salvar os seguintes conjuntos de dados: {", ".join(errors)}'
            }, status_code=500)
            
    def handle_post_clear_producao_monitor(self):
        success = self.db_prod.clear_monitor_data()
        if success:
            self._send_json_response({'success': True, 'message': 'Dados do monitor de produção limpos com sucesso.'})
        else:
            self._send_json_response({'success': False, 'error': 'Erro ao limpar os dados do monitor de produção no banco de dados.'}, status_code=500)
            
    def handle_post_clear_refugo_from_prod_db(self):
        success = self.db_prod.clear_refugo_data_keys()
        if success:
            self._send_json_response({'success': True, 'message': 'Dados de refugo (importação e produção) limpos com sucesso.'})
        else:
            self._send_json_response({'success': False, 'error': 'Erro ao limpar os dados de refugo no banco de dados.'}, status_code=500)

    def handle_post_producao_total_mensal(self):
        data = self._read_json_body()
        if data and 'mes_ano' in data and 'peso_total' in data:
            try:
                peso_total = clean_and_parse_float(data['peso_total'])
                mes_ano = data['mes_ano']
                success = self.db.save_producao_total_mensal(mes_ano, peso_total)
                if success:
                    self._send_json_response({'success': True, 'peso_total': str(peso_total), 'message': f'Peso total de produção para {mes_ano} salvo com sucesso.'})
                else:
                    self._send_json_response({'success': False, 'error': 'Erro ao salvar peso total no banco de dados.'}, status_code=500)
            except ValueError:
                self._send_json_response({'success': False, 'error': 'Valor do peso total de produção inválido.'}, status_code=400)
        else:
            self._send_json_response({'success': False, 'error': 'Dados inválidos ou ausentes (mes_ano e peso_total são obrigatórios).'}, status_code=400)

    def handle_post_clear_refugo_data(self):
        success = self.db.clear_refugo_data()
        if success:
            self._send_json_response({'success': True, 'message': 'Dados de refugo limpos com sucesso.'})
        else:
            self._send_json_response({'success': False, 'error': 'Erro ao limpar dados de refugo.'}, status_code=500)

    def handle_post_import_refugo(self):
        data_array = self._read_json_body()
        if data_array and isinstance(data_array, list):
            success = self.db.import_refugo_data(data_array)
            if success:
                self._send_json_response({'success': True, 'message': f'{len(data_array)} registros de refugo importados com sucesso.'})
            else:
                self._send_json_response({'success': False, 'error': 'Erro ao importar dados de refugo no banco de dados.'}, status_code=500)
        else:
            self._send_json_response({'success': False, 'error': 'Dados inválidos ou ausentes para importação de refugo.'}, status_code=400)

    def handle_post_meta_producao_setor(self):
        data = self._read_json_body()
        if data and 'setor' in data and 'meta_peso' in data:
            try:
                meta_peso = clean_and_parse_float(data['meta_peso']) 
                setor = data['setor']
                if meta_peso < 0:
                    raise ValueError("A meta não pode ser um valor negativo.")
                success = self.db.save_meta_producao_setor(setor, meta_peso)
                if success:
                    self._send_json_response({'success': True, 'meta_peso': str(meta_peso), 'message': f'Meta para o setor {setor} salva com sucesso.'})
                else:
                    self._send_json_response({'success': False, 'error': 'Erro ao salvar meta no banco de dados.'}, status_code=500)
            except ValueError as e:
                self._send_json_response({'success': False, 'error': f'Valor da meta de peso inválido: {e}'}, status_code=400)
            except Exception as e:
                self._send_json_response({'success': False, 'error': f'Erro inesperado: {e}'}, status_code=500)
        else:
            self._send_json_response({'success': False, 'error': 'Dados inválidos ou ausentes (setor e meta_peso são obrigatórios).'}, status_code=400)

    def handle_post_clear_metas_producao_setor(self):
        success = self.db.clear_metas_producao_setor()
        if success:
            self._send_json_response({'success': True, 'message': 'Metas de produção limpas com sucesso.'})
        else:
            self._send_json_response({'success': False, 'error': 'Erro ao limpar metas de produção.'}, status_code=500)

    def handle_post_faturamento_clientes_geral(self):
        data_array = self._read_json_body()
        if data_array and isinstance(data_array, list):
            result = self.db.save_faturamento_data_geral(data_array)
            self._send_json_response(result, status_code=200 if result.get('success') else 500)
        else:
            self._send_json_response({'success': False, 'error': 'Dados inválidos ou ausentes.'}, status_code=400)
        
    def handle_post_faturamento_clientes_detalhado(self):
        data_array = self._read_json_body()
        if data_array and isinstance(data_array, list):
            result = self.db.save_faturamento_data_detalhado(data_array) 
            self._send_json_response(result, status_code=200 if result.get('success') else 500)
        else:
            self._send_json_response({'success': False, 'error': 'Dados inválidos ou ausentes.'}, status_code=400)

    def handle_post_faturamento_itens(self):
        data_array = self._read_json_body()
        if data_array and isinstance(data_array, list):
            result = self.db.save_faturamento_data_itens(data_array) 
            self._send_json_response(result, status_code=200 if result.get('success') else 500)
        else:
            self._send_json_response({'success': False, 'error': 'Dados inválidos ou ausentes.'}, status_code=400)

    def handle_post_meta_peso(self):
        data = self._read_json_body()
        if data and 'mes_ano' in data and 'meta_peso' in data:
            try:
                meta_peso = clean_and_parse_float(data['meta_peso']) 
                mes_ano = data['mes_ano']
                success = self.db.save_meta_peso(mes_ano, meta_peso)
                if success:
                    self._send_json_response({'success': True, 'message': f'Meta para {mes_ano} salva com sucesso.'})
                else:
                    self._send_json_response({'success': False, 'error': 'Erro ao salvar meta no banco de dados.'}, status_code=500)
            except ValueError:
                self._send_json_response({'success': False, 'error': 'Valor da meta de peso inválido.'}, status_code=400)
        else:
            self._send_json_response({'success': False, 'error': 'Dados inválidos ou ausentes (mes_ano e meta_peso são obrigatórios).'}, status_code=400)

    def handle_post_producao_data(self):
        data_array = self._read_json_body()
        if data_array and isinstance(data_array, list):
            success = self.db.save_producao_data(data_array)
            if success:
                self._send_json_response({'success': True, 'message': 'Dados de produção salvos com sucesso no DB.'})
            else:
                self._send_json_response({'success': False, 'error': 'Erro ao salvar dados no banco de dados.'}, status_code=500)
        else:
            self._send_json_response({'success': False, 'error': 'Dados inválidos ou ausentes.'}, status_code=400)

    def handle_post_clear_producao_data(self):
        success = self.db.clear_producao_data()
        if success:
            self._send_json_response({'success': True, 'message': 'Tabela de produção apontada limpa com sucesso.'})
        else:
            self._send_json_response({'success': False, 'error': 'Erro ao limpar a tabela de produção apontada.'}, status_code=500)
    
    def handle_post_aderencia(self):
        body = self._read_json_body()
        if body and "name" in body and "data" in body:
            success = self.db.save_aderencia_report(body['name'], body['data'])
            if success:
                self._send_json_response({'success': True, 'message': 'Relatório salvo com sucesso.'})
            else:
                self._send_json_response({'success': False, 'error': 'Erro ao salvar relatório no banco de dados.'}, status_code=500)
        else:
            self._send_json_response({'success': False, 'error': 'Dados do relatório inválidos ou ausentes.'}, status_code=400)

    def handle_delete_aderencia(self):
        body = self._read_json_body()
        if body and 'name' in body:
            success = self.db.delete_aderencia_report(body['name'])
            if success:
                 self._send_json_response({'success': True})
            else:
                 self._send_json_response({'success': False, 'error': 'Relatório não encontrado ou erro ao deletar.'}, status_code=404)
        else:
            self._send_json_response({'success': False, 'error': 'Nome do relatório não fornecido'}, status_code=400)

    def handle_post_ficha(self):
        ficha_data = self._read_json_body()
        if ficha_data and "main-item-code" in ficha_data:
            success = self.db.save_ficha(ficha_data)
            if success:
                self._send_json_response({'success': True, 'message': 'Ficha salva com sucesso.'})
            else:
                self._send_json_response({'success': False, 'error': 'Erro ao salvar ficha no banco de dados.'}, status_code=500)
        else:
            self._send_json_response({'success': False, 'error': 'Dados da ficha inválidos ou ausentes.'}, status_code=400)

    def handle_delete_ficha(self):
        data = self._read_json_body()
        if data and 'item_code' in data:
            success = self.db.delete_ficha(data['item_code'])
            if success:
                 self._send_json_response({'success': True})
            else:
                 self._send_json_response({'success': False, 'error': 'Item não encontrado ou erro ao deletar.'}, status_code=404)
        else:
            self._send_json_response({'success': False, 'error': 'Código do item não fornecido'}, status_code=400)

    def handle_delete_item(self):
        data = self._read_json_body()
        if data and 'codigo' in data:
            success = self.db.delete_item(data['codigo'])
            self._send_json_response({'success': success})
        else:
            self._send_json_response({'success': False, 'error': 'Código do item não fornecido'}, status_code=400)

    def handle_post_item(self):
        data = self._read_json_body()
        if data:
            success = self.db.upsert_item(data)
            self._send_json_response({'success': success})
        else:
            self._send_json_response({'success': False, 'error': 'Dados inválidos'}, status_code=400)
    
    def handle_import_backup(self):
        data = self._read_json_body()
        if data:
            success = self.db.import_backup_data(data)
            if success:
                self._send_json_response({'success': True})
            else:
                self._send_json_response({'success': False, 'error': 'Erro no servidor durante a importação.'}, status_code=500)
        else:
            self._send_json_response({'success': False, 'error': 'Dados de backup inválidos ou ausentes.'}, status_code=400)
    
    def handle_save_carteira(self):
        pedidos = self._read_json_body()
        if pedidos is not None:
            success = self.db.save_carteira_pedidos(pedidos)
            if success:
                self._send_json_response({'success': True})
            else:
                self._send_json_response({'success': False, 'error': 'Erro no servidor ao salvar a carteira.'}, status_code=500)
        else:
            self._send_json_response({'success': False, 'error': 'Dados de carteira inválidos ou ausentes.'}, status_code=400)

    def handle_post_registros(self):
        registro = self._read_json_body()
        if registro:
            registro_id = self.db.add_registro(registro)
            if registro_id:
                self._send_json_response({'success': True, 'id': registro_id})
            else:
                self._send_json_response({'success': False, 'error': 'Erro ao adicionar registro'}, status_code=500)
        else:
            self._send_json_response({'success': False, 'error': 'Dados inválidos'}, status_code=400)

    def handle_update_registro(self):
        data = self._read_json_body()
        if data and 'id' in data and 'updates' in data:
            success = self.db.update_registro(data['id'], data['updates'])
            self._send_json_response({'success': success})
        else:
            self._send_json_response({'success': False, 'error': 'Dados inválidos'}, status_code=400)

    def handle_delete_registro(self):
        data = self._read_json_body()
        if data and 'id' in data:
            success = self.db.delete_registro(data['id'])
            self._send_json_response({'success': success})
        else:
            self._send_json_response({'success': False, 'error': 'ID não fornecido'}, status_code=400)

    def handle_post_recebidos(self):
        data = self._read_json_body()
        if data and 'id' in data and 'carga' in data and 'checked' in data:
            registro_id = data['id']
            carga = data['carga']
            if data['checked']:
                success = self.db.add_recebimento(registro_id, carga)
            else:
                success = self.db.remove_recebimento(registro_id)
            self._send_json_response({'success': success})
        else:
            self._send_json_response({'success': False, 'error': 'Dados inválidos'}, status_code=400)
            
    def handle_post_ramal(self):
        data = self._read_json_body()
        if data:
            ramal_id = self.db.add_ramal(data)
            if ramal_id:
                self._send_json_response({'success': True, 'id': ramal_id})
            else:
                self._send_json_response({'success': False, 'error': 'Erro ao adicionar ramal'}, status_code=500)
        else:
            self._send_json_response({'success': False, 'error': 'Dados inválidos'}, status_code=400)

    def handle_delete_ramal(self):
        data = self._read_json_body()
        if data and 'id' in data:
            success = self.db.delete_ramal(data['id'])
            self._send_json_response({'success': success})
        else:
            self._send_json_response({'success': False, 'error': 'ID não fornecido'}, status_code=400)

    # ==========================================================================
    # --- DO_GET com Logging Aprimorado (Log Mais Bonito) ---
    # ==========================================================================
    def do_GET(self):
        # Mapeamento de rotas amigáveis para nomes de arquivos
        routes = {
            '/': f'/{MAIN_HTML_FILE}', '/faturamento': f'/{FATURAMENTO_HTML_FILE}',
            '/dashboard': f'/{DASHBOARD_HTML_FILE}', '/carteira': f'/{CARTEIRA_HTML_FILE}',
            '/refugo': f'/{REFUGO_HTML_FILE}', '/terceiro': f'/{TERCEIRO_HTML_FILE}',
            '/inventario': f'/{INVENTARIO_HTML_FILE}', '/ramais': f'/{RAMAIS_HTML_FILE}',
            '/unificado': f'/{UNIFICADO_HTML_FILE}', 
            '/clientes': f'/{CLIENTES_HTML_FILE}',
            '/itens': f'/{ITENS_HTML_FILE}',
            '/ficha-item': f'/{FICHA_ITEM_HTML_FILE}',
            '/aderencia': f'/{ADERENCIA_HTML_FILE}',
            '/producao-apontada': f'/{PRODUCAO_APONTADA_HTML_FILE}',
            '/faturamentodetalhado': f'/{FATURAMENTO_DETALHADO_FILE}',
            '/controlemodelos': f'/{CONTROLE_MODELOS_HTML_FILE}',
            '/monitor': f'/{ORDEM_MONITOR_HTML_FILE}' 
        }
        
        # Rotas de API
        api_routes = {
            '/api/registros': self.handle_get_registros, 
            '/api/faturamento': self.handle_get_faturamento,
            '/api/refugo': self.handle_get_refugo, 
            '/api/inventario': self.handle_get_inventario,
            '/api/carteira': self.handle_get_carteira, 
            '/api/recebidos': self.handle_get_recebidos,
            '/api/ramais': self.handle_get_ramais, 
            '/api/itens': self.handle_get_itens, 
            '/api/faturamento-clientes': self.handle_get_faturamento_clientes_geral,
            '/api/faturamento-clientes-detalhado': self.handle_get_faturamento_clientes_detalhado,
            '/api/faturamento-itens-dashboard': self.handle_get_faturamento_itens,
            '/api/fichas': self.handle_get_fichas,
            '/api/aderencia': self.handle_get_aderencia,
            '/api/producao': self.handle_get_producao_data,
            '/api/metas': self.handle_get_meta_peso,
            '/api/metas-producao': self.handle_get_metas_producao_setor,
            '/api/producao-total-mensal': self.handle_get_producao_total_mensal,
            '/api/producao/load_all': self.handle_get_load_producao_all 
        }
        
        path_without_query = self.path.split('?')[0]
        
        # --- LÓGICA DE LOG DE ACESSO ---
        client_ip = self.client_address[0]
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 1. Tenta resolver o nome da máquina (Hostname)
        try:
            # Esta chamada de rede PODE CAUSAR LENTIDÃO se o DNS reverso não estiver configurado
            hostname = socket.gethostbyaddr(client_ip)[0]
        except Exception: 
            hostname = client_ip # Fallback para o IP

        # 2. Verifica se é uma rota de tela HTML (rota amigável ou acesso direto a .html)
        is_html_route = self.path in routes or path_without_query.endswith('.html')
        is_api_route = path_without_query in api_routes
        
        # 3. Se for uma rota amigável, mapeia para o arquivo real (E isso não afeta o log, pois path_without_query guarda o nome da rota)
        if self.path in routes:
            self.path = routes[self.path]

        # 4. Processa e exibe o log para TODAS as telas HTML (o log "bonito")
        if is_html_route:
            # Novo Log com design aprimorado (mais bonito)
            print("\n===========================================================")
            print(f"| ACESSO DE TELA: {path_without_query.upper()}")
            print("|---------------------------------------------------------")
            print(f"| HORA:         {timestamp}")
            print(f"| MÁQUINA/HOST: {hostname}")
            print(f"| IP:           {client_ip}")
            print("===========================================================")

            # Verifica se o arquivo existe após o mapeamento da rota
            if not os.path.exists(self.path.lstrip('/')):
                self.send_error(404, f"Arquivo não encontrado: {self.path}")
                return
        
        # 5. Processa rotas de API
        elif is_api_route:
            # Não loga requisições de API (para manter o console limpo)
            api_routes[path_without_query]()
            return
            
        # 6. Serve arquivos estáticos ou as telas HTML mapeadas
        return http.server.SimpleHTTPRequestHandler.do_GET(self)
    
    # ==========================================================================
    # --- DO_POST para Rotas de API ---
    # ==========================================================================
    def do_POST(self):
        api_routes = {
            '/api/registros': self.handle_post_registros,
            '/api/update': self.handle_update_registro,
            '/api/delete': self.handle_delete_registro,
            '/api/recebidos': self.handle_post_recebidos,
            '/api/ramais': self.handle_post_ramal,
            '/api/ramais-delete': self.handle_delete_ramal,
            '/api/itens': self.handle_post_item,
            '/api/import': self.handle_import_backup,
            '/api/itens-delete': self.handle_delete_item,
            '/api/save-carteira': self.handle_save_carteira,
            '/api/faturamento-clientes': self.handle_post_faturamento_clientes_geral,
            '/api/faturamento-clientes-detalhado': self.handle_post_faturamento_clientes_detalhado,
            '/api/faturamento-itens-dashboard': self.handle_post_faturamento_itens,
            '/api/fichas': self.handle_post_ficha,
            '/api/fichas-delete': self.handle_delete_ficha,
            '/api/aderencia': self.handle_post_aderencia,
            '/api/aderencia-delete': self.handle_delete_aderencia,
            '/api/producao': self.handle_post_producao_data,
            '/api/producao/clear': self.handle_post_clear_producao_data,
            '/api/metas': self.handle_post_meta_peso,
            '/api/metas-producao': self.handle_post_meta_producao_setor,
            '/api/metas-producao/clear': self.handle_post_clear_metas_producao_setor,
            '/api/refugo/clear': self.handle_post_clear_refugo_data,
            '/api/refugo/import': self.handle_post_import_refugo,
            '/api/producao-total-mensal': self.handle_post_producao_total_mensal,
            '/api/producao/save_all': self.handle_post_save_producao_all,
            '/api/producao/clear_monitor': self.handle_post_clear_producao_monitor, 
            '/api/refugo/clear_from_prod_db': self.handle_post_clear_refugo_from_prod_db 
        }
        
        if self.path in api_routes:
            api_routes[self.path]()
        else:
            self.send_error(404, "Endpoint não encontrado")


# ==============================================================================
# Inicialização
# ==============================================================================

def run_server():
    if not os.path.exists(DASHBOARD_HTML_FILE):
        print(f"AVISO: Arquivo principal {DASHBOARD_HTML_FILE} não encontrado.")
        print("Certifique-se de que todos os arquivos .html necessários estão no mesmo diretório.")
    
    # Garante que ambos os arquivos de banco de dados e suas tabelas sejam criados na inicialização
    db = Database()
    db.close()
    db_prod = ProducaoDatabase()
    db_prod.close()
    
    with ThreadedTCPServer((HOST, PORT), Handler) as httpd:
        print(f"Servidor Fundição ERUS rodando em http://{HOST}:{PORT}")
        print(f"  - Banco de dados principal: {DB_NAME}")
        print(f"  - Banco de dados de produção: {PRODUCAO_DB_NAME}")
        print(f"Página Monitor de Ordens: http://{HOST}:{PORT}/monitor") 
        print(f"Página clientes (Detalhado): http://{HOST}:{PORT}/clientes")
        print(f"Página Detalhada/Meta: http://{HOST}:{PORT}/faturamentodetalhado")
        print(f"Página itens: http://{HOST}:{PORT}/itens")
        print(f"Página Ficha Item: http://{HOST}:{PORT}/ficha-item")
        print(f"Página Aderência: http://{HOST}:{PORT}/aderencia")
        print(f"Página Produção Apontada: http://{HOST}:{PORT}/producao-apontada")
        print(f"Página Controle de Modelos: http://{HOST}:{PORT}/controlemodelos")
        print("Pressione Ctrl+C para encerrar.")
        
        # Abre o monitor no navegador automaticamente
        webbrowser.open(f"http://{HOST}:{PORT}/processos.html") 
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor encerrado.")
        finally:
            httpd.server_close()

if __name__ == "__main__":
    run_server()