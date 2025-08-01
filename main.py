import time
import os
import argparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException # Added
from dotenv import load_dotenv
import datetime
import csv  # Importação para suporte a CSV
import json
from urllib.parse import urlparse, parse_qs
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Carregar variáveis do arquivo .env
load_dotenv()

def main(nome_filtro=None, id_prospecto=None):
    
    """
    Função principal que automatiza a navegação no sistema:
    1. Realiza login no sistema
    2. Abre o menu lateral
    3. Clica na seta ao lado de "Cliente" para expandir o submenu
    4. Clica na opção "Prospectos"
    5. Captura screenshots de cada etapa
    6. Captura as requisições HTTP e respostas
    
    Args:
        nome_filtro (str): Nome do prospecto para filtrar na tabela
        id_prospecto (str): ID do prospecto para clicar no botão de ações
    """
    # Configurar argumentos de linha de comando apenas para headless
    parser = argparse.ArgumentParser(description='Automatização de navegação web')
    parser.add_argument('--headless', action='store_true', 
                        help='Executar o navegador em modo invisível (headless)')
    args = parser.parse_args()
    
    # Também pode ser configurado por variável de ambiente
    headless = args.headless or os.environ.get('HEADLESS', '').lower() == 'true'
    
    # Usar valores padrão se não fornecidos
    if nome_filtro is None:
        nome_filtro = "FERNANDO DEIVID SANTOS SARAIVA"
    if id_prospecto is None:
        id_prospecto = "1505"
    
    print(f"Nome para filtro: {nome_filtro}")
    print(f"ID do prospecto para ação: {id_prospecto}")
    
    # Obter credenciais do .env
    usuario = os.environ.get('USUARIO', '')
    senha = os.environ.get('SENHA', '')
    
    if not usuario:
        print("AVISO: Email do usuário não encontrado no arquivo .env")
        usuario = input("Digite o email do usuário: ")
    
    if not senha:
        print("AVISO: Senha não encontrada no arquivo .env")
        senha = input("Digite a senha: ")
    
    # Criar pasta para screenshots
    screenshots_dir = "screenshots"
    if not os.path.exists(screenshots_dir):
        os.makedirs(screenshots_dir)
    
    # Criar pasta para logs de requisições
    requests_dir = "requests_logs"
    if not os.path.exists(requests_dir):
        os.makedirs(requests_dir)
    
    # Nome dos arquivos de log
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"{requests_dir}/requests_log_{timestamp}.csv"
    network_file = f"{requests_dir}/network_details_{timestamp}.json"
    
    print(f"Configurando o Chrome... (Modo headless: {'Sim' if headless else 'Não'})")
    
    # Configurações do Chrome
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument('--enable-logging')
    chrome_options.add_argument('--v=1')
    
    # Configurações especiais para garantir janela grande
    chrome_options.add_argument('--start-maximized')  # Inicia maximizado
    chrome_options.add_argument('--window-size=1920,1080')  # Tamanho inicial grande
    
    # Habilitar logs de performance e DevTools Protocol
    chrome_options.set_capability("goog:loggingPrefs", {
        "browser": "ALL",
        "performance": "ALL",
        "network": "ALL"
    })
    
    # Adicione a opção headless apenas se solicitado
    if headless:
        chrome_options.add_argument("--headless=new")
        # Configurações adicionais para headless
        chrome_options.add_argument('--disable-gpu')  # Necessário para alguns sistemas
        chrome_options.add_argument('--window-size=1920,1080')  # Força tamanho em headless
        chrome_options.add_argument('--force-device-scale-factor=1')  # Escala normal
    
    # Lista para armazenar informações das requisições
    all_requests = []
    
    # Tente iniciar o Chrome
    try:
        print("Iniciando o Chrome...")
        driver = webdriver.Chrome(options=chrome_options)
        
        # Configuração para captura de rede usando CDP
        driver.execute_cdp_cmd("Network.enable", {})
        
        # Função para capturar screenshots
        def capturar_screenshot(nome):
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{screenshots_dir}/{timestamp}_{nome}.png"
            driver.save_screenshot(filename)
            print(f"Screenshot '{nome}' salvo como '{filename}'")
            return filename
            
        # Função para registrar requisições com detalhes
        def registrar_requisicao(etapa, url, method, request_headers=None, request_data=None, 
                                status_code=None, response_headers=None, response_body=None):
            # Analisar URL para entender a requisição
            parsed_url = urlparse(url)
            path = parsed_url.path
            query = parse_qs(parsed_url.query)
            
            # Tentar determinar o propósito da requisição
            purpose = "Desconhecido"
            if "login" in path.lower():
                purpose = "Autenticação"
            elif "cliente" in path.lower() or "cliente" in url.lower():
                purpose = "Relacionado a Cliente"
                if "prospectos" in path.lower() or "prospectos" in url.lower():
                    purpose = "Listagem de Prospectos"
            elif "api" in path.lower():
                purpose = "Chamada de API"
            
            # Criar entrada de log
            req_entry = {
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                "etapa": etapa,
                "url": url,
                "method": method,
                "path": path,
                "query_params": str(query),
                "request_headers": str(request_headers),
                "request_data": str(request_data),
                "status_code": str(status_code) if status_code else "",
                "response_headers": str(response_headers) if response_headers else "",
                "response_body": str(response_body)[:500] if response_body else "",  # Limitado a 500 caracteres
                "purpose": purpose
            }
            
            all_requests.append(req_entry)
            
            # Log para console
            print(f"Requisição registrada: {method} {url} ({status_code})")
            return req_entry
        
        # Configurar interceptação de requisições
        def configure_request_interception():
            # Usar o Chrome DevTools Protocol para interceptar requisições
            driver.execute_cdp_cmd("Network.setRequestInterception", {"patterns": [{"urlPattern": "*"}]})
            
            # Adicionar event listeners para eventos de rede
            driver.execute_cdp_cmd("Network.requestWillBeSent", lambda params: on_request_will_be_sent(params))
            driver.execute_cdp_cmd("Network.responseReceived", lambda params: on_response_received(params))
        
        # Função para iniciar captura de rede para uma etapa específica
        def iniciar_captura_rede(etapa_descricao):
            print(f"=== Iniciando captura de rede para: {etapa_descricao} ===")
            
            # Limpar logs anteriores
            driver.get_log('browser')
            driver.get_log('performance')
            
            # Habilitar monitoramento de rede
            driver.execute_cdp_cmd("Network.enable", {})
            
            # Registrar início da etapa
            return etapa_descricao
        
        # Função para capturar detalhes de rede durante uma etapa
        def capturar_requisicoes(etapa_descricao):
            etapa_atual = etapa_descricao
            print(f"Capturando requisições para: {etapa_atual}")
            
            # Capturar logs de performance
            perf_logs = driver.get_log('performance')
            
            # Processar logs de performance para extrair informações de rede
            requisicoes = []
            respostas = {}
            
            for entry in perf_logs:
                try:
                    log = json.loads(entry['message'])['message']
                    
                    # Capturar informações de requisição
                    if log['method'] == 'Network.requestWillBeSent':
                        req = log['params']
                        request_id = req['requestId']
                        url = req['request']['url']
                        
                        # Ignorar recursos estáticos
                        if any(ext in url for ext in ['.png', '.jpg', '.jpeg', '.gif', '.css', '.woff', '.ttf']):
                            continue
                            
                        method = req['request']['method']
                        headers = req['request'].get('headers', {})
                        
                        # Salvar temporariamente os detalhes da requisição
                        requisicoes.append({
                            'id': request_id,
                            'url': url,
                            'method': method,
                            'headers': headers,
                            'data': req['request'].get('postData', '')
                        })
                    
                    # Capturar informações de resposta
                    elif log['method'] == 'Network.responseReceived':
                        resp = log['params']
                        request_id = resp['requestId']
                        
                        # Salvar temporariamente os detalhes da resposta
                        respostas[request_id] = {
                            'status': resp['response']['status'],
                            'headers': resp['response'].get('headers', {}),
                            'mime': resp['response'].get('mimeType', '')
                        }
                except Exception as e:
                    print(f"Erro ao processar log: {e}")
            
            # Combinar informações de requisição e resposta
            for req in requisicoes:
                request_id = req['id']
                if request_id in respostas:
                    resp = respostas[request_id]
                    
                    # Registrar a requisição completa
                    registrar_requisicao(
                        etapa=etapa_atual,
                        url=req['url'],
                        method=req['method'],
                        request_headers=req['headers'],
                        request_data=req['data'],
                        status_code=resp['status'],
                        response_headers=resp['headers']
                    )
            
            count = len(requisicoes)
            print(f"Capturadas {count} requisições na etapa: {etapa_atual}")
            
            # Salvar continuamente o arquivo de log para não perder dados
            salvar_requisicoes_csv()
            
            return count
        
        # Função para salvar as requisições em CSV
        def salvar_requisicoes_csv():
            # Verifica se há dados para salvar
            if not all_requests:
                logger.warning("Nenhuma requisição capturada para salvar nos logs.")
                return
            
            total_reqs = len(all_requests)
            logger.info(f"Salvando {total_reqs} requisições nos arquivos de log...")
            
            # Salvamento em CSV
            try:
                with open(log_filename, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = ["timestamp", "etapa", "url", "method", "path", "query_params", 
                                 "request_headers", "request_data", "status_code", 
                                 "response_headers", "response_body", "purpose"]
                    
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    
                    # Adicionar barra de progresso para arquivos grandes
                    for i, req in enumerate(all_requests):
                        writer.writerow(req)
                        # Mostrar progresso a cada 50 itens
                        if (i + 1) % 50 == 0 or i + 1 == total_reqs:
                            logger.info(f"Progresso CSV: {i + 1}/{total_reqs} requisições ({(i + 1) / total_reqs * 100:.1f}%)")
                
                logger.info(f"✅ Arquivo CSV salvo com sucesso em: {log_filename}")
            except Exception as e:
                logger.error(f"❌ Erro ao salvar arquivo CSV: {e}")
                # Tentar salvar em um arquivo de backup
                try:
                    backup_csv = f"{log_filename}.backup"
                    with open(backup_csv, 'w', newline='', encoding='utf-8') as csvfile:
                        fieldnames = ["timestamp", "etapa", "url", "method", "path", "query_params", 
                                     "request_headers", "request_data", "status_code", 
                                     "response_headers", "response_body", "purpose"]
                        
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        writer.writeheader()
                        for req in all_requests:
                            writer.writerow(req)
                    logger.info(f"✅ Arquivo CSV de backup salvo em: {backup_csv}")
                except Exception as backup_error:
                    logger.error(f"❌ Falha também no backup CSV: {backup_error}")
            
            # Salvamento em JSON
            try:
                # Salvar com tratamento para garantir integridade do JSON
                with open(network_file, 'w', encoding='utf-8') as jsonfile:
                    # Sanitizar os dados para garantir serialização JSON válida
                    sanitized_requests = []
                    for req in all_requests:
                        sanitized_req = {}
                        for key, value in req.items():
                            # Garantir que valores são serializáveis
                            if isinstance(value, (str, int, float, bool, type(None))):
                                sanitized_req[key] = value
                            else:
                                # Converter para string com tratamento de erro
                                try:
                                    sanitized_req[key] = str(value)
                                except Exception:
                                    sanitized_req[key] = "<Valor não serializável>"
                        sanitized_requests.append(sanitized_req)
                    
                    json.dump(sanitized_requests, jsonfile, indent=2, ensure_ascii=False)
                
                logger.info(f"✅ Arquivo JSON salvo com sucesso em: {network_file}")
            except Exception as e:
                logger.error(f"❌ Erro ao salvar arquivo JSON: {e}")
                # Tentar salvar em formato simplificado
                try:
                    backup_json = f"{network_file}.backup"
                    with open(backup_json, 'w', encoding='utf-8') as jsonfile:
                        # Usar uma versão ainda mais simplificada
                        simple_data = [{k: str(v) for k, v in req.items()} for req in all_requests]
                        json.dump(simple_data, jsonfile, ensure_ascii=False)
                    logger.info(f"✅ Arquivo JSON simplificado salvo em: {backup_json}")
                except Exception as backup_error:
                    logger.error(f"❌ Falha também no backup JSON: {backup_error}")
            
            # Criar um arquivo de resumo rápido com estatísticas
            try:
                stats_file = f"{requests_dir}/stats_{timestamp}.txt"
                with open(stats_file, 'w', encoding='utf-8') as statsfile:
                    # Contar requisições por etapa
                    etapas = {}
                    for req in all_requests:
                        etapa = req.get('etapa', 'Desconhecida')
                        if etapa in etapas:
                            etapas[etapa] += 1
                        else:
                            etapas[etapa] = 1
                    
                    # Contar códigos de status
                    status_codes = {}
                    for req in all_requests:
                        status = req.get('status_code', 'Desconhecido')
                        if status in status_codes:
                            status_codes[status] += 1
                        else:
                            status_codes[status] = 1
                    
                    # Escrever estatísticas
                    statsfile.write(f"=== RESUMO DA CAPTURA DE REQUISIÇÕES ===\n")
                    statsfile.write(f"Data/Hora: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    
                    statsfile.write(f"--- REQUISIÇÕES POR ETAPA ---\n")
                    for etapa, count in etapas.items():
                        statsfile.write(f"{etapa}: {count} requisições ({count/total_reqs*100:.1f}%)\n")
                    
                    statsfile.write(f"\n--- CÓDIGOS DE STATUS ---\n")
                    for status, count in status_codes.items():
                        statsfile.write(f"Status {status}: {count} requisições ({count/total_reqs*100:.1f}%)\n")
                
                logger.info(f"✅ Arquivo de estatísticas salvo em: {stats_file}")
            except Exception as e:
                logger.error(f"❌ Erro ao criar arquivo de estatísticas: {e}")
            
            print(f"\n📊 Logs de requisições salvos com sucesso!")
            print(f"📄 CSV: {log_filename}")
            print(f"📄 JSON: {network_file}")
            print(f"📄 Estatísticas: {stats_file if 'stats_file' in locals() else 'Não gerado'}")

    except Exception as e:
        print(f"Falha ao iniciar o Chrome: {e}")
        print("Por favor, verifique se o Google Chrome está instalado no sistema.")
        # Tentar capturar screenshot em caso de erro
        try:
            driver.save_screenshot(f"screenshots/erro_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            print("Screenshot do erro salvo")
        except Exception:
            print("Não foi possível salvar screenshot do erro")
        return

    # Navegar para a URL
    try:
        print("=== ETAPA 1: Acessando a página de login ===")
        etapa_atual = iniciar_captura_rede("Acesso à página de login")
        driver.get("https://megalinktelecom.hubsoft.com.br/login")
        capturar_screenshot("01_pagina_login")
        capturar_requisicoes(etapa_atual)
        
        # Aguardar até que o campo de email esteja visível e disponível
        print("Aguardando carregamento da página...")
        wait = WebDriverWait(driver, 15)  # Aumentando o tempo de espera para 15 segundos
        
        # Tentar vários seletores possíveis para o campo de email
        try:
            # Primeira tentativa: usar o name="email"
            email_input = wait.until(
                EC.presence_of_element_located((By.NAME, "email"))
            )
            print("Campo de email localizado pelo atributo 'name'")
        except Exception:
            try:
                # Segunda tentativa: usar o id="input_0"
                email_input = wait.until(
                    EC.presence_of_element_located((By.ID, "input_0"))
                )
                print("Campo de email localizado pelo atributo 'id'")
            except Exception:
                # Terceira tentativa: usar um seletor CSS mais genérico
                email_input = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email']"))
                )
                print("Campo de email localizado pelo seletor CSS")
        
        print("=== ETAPA 2: Preenchendo o campo de email ===")
        print(f"Preenchendo o campo com o email: {usuario}")
        email_input.clear()  # Limpar o campo primeiro
        etapa_atual = iniciar_captura_rede("Preenchimento do campo de email")
        email_input.send_keys(usuario)
        capturar_screenshot("02_email_preenchido")
        capturar_requisicoes(etapa_atual)
        
        # Esperar um pouco para garantir que o formulário reconheça a entrada (ativa o botão)
        time.sleep(1)
        
        print("=== ETAPA 3: Clicando no botão Validar ===")
        # Localizar o botão "Validar" e clicar nele
        print("Procurando o botão Validar...")
        
        # Tentativas diferentes para localizar o botão
        try:
            # Tentativa 1: Pelo texto do botão
            validar_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Validar')]"))
            )
            print("Botão Validar localizado pelo texto")
        except:
            try:
                # Tentativa 2: Pelo aria-label
                validar_button = wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Validar']"))
                )
                print("Botão Validar localizado pelo aria-label")
            except:
                try:
                    # Tentativa 3: Pela classe CSS
                    validar_button = wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "button.submit-button"))
                    )
                    print("Botão Validar localizado pela classe CSS")
                except:
                    # Tentativa 4: Qualquer botão tipo submit
                    validar_button = wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
                    )
                    print("Botão Validar localizado pelo tipo 'submit'")
        
        # Clicar no botão Validar
        print("Clicando no botão Validar...")
        etapa_atual = iniciar_captura_rede("Clique no botão Validar")
        validar_button.click()
        capturar_screenshot("03_botao_validar_clicado")
        capturar_requisicoes(etapa_atual)
        
        print("Botão Validar clicado com sucesso!")
        
        print("=== ETAPA 4: Aguardando o campo de senha ===")
        # Aguardar o campo de senha aparecer
        print("Aguardando o campo de senha...")
        
        # Tentar vários seletores possíveis para localizar o campo de senha
        try:
            # Tentativa 1: Pelo tipo e nome
            password_input = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password'][name='password']"))
            )
            print("Campo de senha localizado pelo tipo e nome")
        except:
            try:
                # Tentativa 2: Pelo ID
                password_input = wait.until(
                    EC.presence_of_element_located((By.ID, "input_2"))
                )
                print("Campo de senha localizado pelo ID")
            except:
                try:
                    # Tentativa 3: Pelo placeholder
                    password_input = wait.until(
                        EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Senha']"))
                    )
                    print("Campo de senha localizado pelo placeholder")
                except:
                    # Tentativa 4: Qualquer input do tipo password
                    password_input = wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password']"))
                    )
                    print("Campo de senha localizado pelo tipo 'password'")
        
        capturar_screenshot("04_campo_senha_apareceu")
        
        print("=== ETAPA 5: Preenchendo o campo de senha ===")
        # Preencher o campo com a senha
        print("Preenchendo o campo de senha...")
        etapa_atual = iniciar_captura_rede("Preenchimento do campo de senha")
        password_input.clear()
        password_input.send_keys(senha)
        print("Senha preenchida com sucesso!")
        capturar_screenshot("05_senha_preenchida")
        capturar_requisicoes(etapa_atual)
        
        # Pequena pausa para garantir que o botão Entrar esteja ativo
        time.sleep(1)
        
        print("=== ETAPA 6: Clicando no botão Entrar ===")
        # Localizar e clicar no botão "Entrar"
        print("Procurando o botão Entrar...")
        
        # Tentativas diferentes para localizar o botão Entrar
        try:
            # Tentativa 1: Pelo texto do botão
            entrar_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Entrar')]"))
            )
            print("Botão Entrar localizado pelo texto")
        except:
            try:
                # Tentativa 2: Pelo aria-label
                entrar_button = wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Entrar']"))
                )
                print("Botão Entrar localizado pelo aria-label")
            except:
                try:
                    # Tentativa 3: Pela classe CSS
                    entrar_button = wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "button.submit-button"))
                    )
                    print("Botão Entrar localizado pela classe CSS")
                except:
                    # Tentativa 4: Qualquer botão tipo submit
                    entrar_button = wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
                    )
                    print("Botão Entrar localizado pelo tipo 'submit'")
        
        # Clicar no botão Entrar
        print("Clicando no botão Entrar...")
        etapa_atual = iniciar_captura_rede("Clique no botão Entrar")
        entrar_button.click()
        capturar_screenshot("06_botao_entrar_clicado")
        capturar_requisicoes(etapa_atual)
        
        print("Botão Entrar clicado com sucesso!")
        
        print("=== ETAPA 7: Aguardando conclusão do login ===")
        # Aguardar que o login seja concluído e a página dashboard seja exibida
        print("Aguardando conclusão do login...")
        
        # Aguardar alguns segundos para o carregamento da página
        time.sleep(5)
        
        # Capturar screenshot da página após login
        etapa_atual = iniciar_captura_rede("Login concluído")
        capturar_screenshot("07_login_concluido")
        capturar_requisicoes(etapa_atual)
        
        # Verificar se o login foi bem-sucedido
        if "dashboard" in driver.current_url or "painel" in driver.current_url:
            print("Login realizado com sucesso!")
            
            print("=== ETAPA 8: Clicando na seta de expansão ao lado de 'Cliente' ===")
            # Agora vamos localizar e clicar na seta para expandir o menu Cliente
            print("Procurando a seta de expansão de 'Cliente'...")
            
            # Primeiro, precisamos localizar o elemento Cliente para depois acessar a seta
            try:
                # Tentativa 1: Localizar o elemento Cliente primeiro
                cliente_element = wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'ms-navigation-button') and .//span[contains(text(), 'Cliente')]]"))
                )
                print("Elemento 'Cliente' localizado com sucesso!")
                
                # Agora vamos localizar a seta dentro deste elemento
                cliente_arrow = wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//i[contains(@class, 'icon-chevron-right') and contains(@class, 'arrow')]"))
                )
                print("Seta de expansão localizada com sucesso!")
            except:
                try:
                    # Tentativa 2: Localizar diretamente a seta usando o seletor fornecido
                    cliente_arrow = wait.until(
                        EC.element_to_be_clickable((By.XPATH, "//i[contains(@class, 'icon-chevron-right') and contains(@class, 'arrow') and contains(@class, 'ng-scope')]"))
                    )
                    print("Seta de expansão localizada pelo seletor específico")
                except:
                    try:
                        # Tentativa 3: Localizar qualquer seta de expansão no menu
                        cliente_arrow = wait.until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, ".ms-navigation-button .icon-chevron-right.arrow"))
                        )
                        print("Seta de expansão localizada pela classe CSS")
                    except Exception as e:
                        print(f"Não foi possível localizar a seta de expansão: {e}")
                        # Capturar screenshot para análise
                        capturar_screenshot("erro_seta_cliente")
                        raise e
            
            # Capture um screenshot antes de clicar na seta
            capturar_screenshot("08_antes_clicar_seta")
            
            # Clicar na seta para expandir o submenu
            print("Clicando na seta para expandir o submenu de Cliente...")
            etapa_atual = iniciar_captura_rede("Expansão do submenu Cliente")
            cliente_arrow.click()
            
            print("Seta de expansão clicada com sucesso!")
            capturar_requisicoes(etapa_atual)
            
            # Aguardar um momento para que o submenu se expanda
            time.sleep(1)
            
            # Capturar screenshot do submenu expandido
            capturar_screenshot("09_submenu_expandido")
            
            print("=== ETAPA 9: Clicando na opção 'Prospectos' ===")
            # Agora vamos localizar e clicar no link "Prospectos"
            print("Procurando a opção 'Prospectos'...")
            
            # Tentar localizar a opção "Prospectos" de várias formas
            try:
                # Tentativa 1: Usando o texto do span
                prospectos_link = wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//span[@class='title ng-scope ng-binding flex' and contains(text(), 'Prospectos')]//parent::a"))
                )
                print("Link 'Prospectos' localizado pelo texto do span")
            except Exception:
                try:
                    # Tentativa 2: Pelo href
                    prospectos_link = wait.until(
                        EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/cliente/prospectos') or contains(@ui-sref, 'prospectos')]"))
                    )
                    print("Link 'Prospectos' localizado pelo href ou ui-sref")
                except Exception:
                    try:
                        # Tentativa 3: Qualquer link com texto contendo "Prospectos"
                        prospectos_link = wait.until(
                            EC.element_to_be_clickable((By.XPATH, "//a[contains(., 'Prospectos')]"))
                        )
                        print("Link 'Prospectos' localizado pelo texto")
                    except Exception as e:
                        print(f"Não foi possível localizar o link 'Prospectos': {e}")
                        # Capturar screenshot para análise
                        capturar_screenshot("erro_link_prospectos")
                        raise e
            
            # Capture um screenshot antes de clicar no link
            capturar_screenshot("10_antes_clicar_prospectos")
            
            # Clicar no link "Prospectos"
            print("Clicando no link 'Prospectos'...")
            etapa_atual = iniciar_captura_rede("Navegação para página de Prospectos")
            prospectos_link.click()
            
            print("Link 'Prospectos' clicado com sucesso!")
            capturar_requisicoes(etapa_atual)
            
            # Aguardar o carregamento da página de prospectos
            time.sleep(3)
            
            # Capturar screenshot da página de prospectos
            capturar_screenshot("11_pagina_prospectos")
            print("=== ETAPA 10: Extraindo dados da tabela para CSV ===")
            # Aguardar a tabela de prospectos carregar
            print("Aguardando carregamento da tabela...")

            try:
                # Localizar a tabela na página
                tabela = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "table.dataTable.row-border.hover"))
                )
                print("Tabela localizada com sucesso!")
                
                # Capturar screenshot da tabela
                capturar_screenshot("13_tabela_localizada")
                
                # Extrair os dados da tabela
                print("Extraindo os dados da tabela...")
                
                # Obter os cabeçalhos da tabela
                headers = []
                header_cells = tabela.find_elements(By.CSS_SELECTOR, "thead th")
                for cell in header_cells:
                    headers.append(cell.text.strip())
                
                print(f"Cabeçalhos encontrados: {headers}")
                
                # Obter as linhas da tabela
                rows = []
                table_rows = tabela.find_elements(By.CSS_SELECTOR, "tbody tr")
                
                for row in table_rows:
                    row_data = []
                    cells = row.find_elements(By.TAG_NAME, "td")
                    for cell in cells:
                        row_data.append(cell.text.strip())
                    rows.append(row_data)
                
                print(f"Total de linhas encontradas: {len(rows)}")
                
                # Criar o arquivo CSV
                csv_filename = f"prospectos_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                print(f"Salvando dados no arquivo CSV: {csv_filename}")
                
                with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
                    csv_writer = csv.writer(csvfile)
                    # Escrever os cabeçalhos
                    csv_writer.writerow(headers)
                    # Escrever as linhas de dados
                    csv_writer.writerows(rows)
                
                print(f"Arquivo CSV '{csv_filename}' criado com sucesso!")
                capturar_screenshot("14_dados_salvos_csv")
                etapa_atual = iniciar_captura_rede("Extração de dados da tabela")
                capturar_requisicoes(etapa_atual)
                
                print("=== ETAPA 10.5: Filtrando tabela pelo nome especificado ===")
                print("Localizando campo de busca para filtrar...")
                
                try:
                    # Localizar o campo de input de busca
                    campo_busca = wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "input[ng-model='vm.filtros.busca']"))
                    )
                    print("Campo de busca localizado com sucesso!")
                    
                    # Limpar o campo antes de preencher
                    campo_busca.clear()
                    time.sleep(0.5)
                    
                    # Preencher o campo com "Darlan"
                    campo_busca.send_keys(nome_filtro)
                    print(f"Campo preenchido com: {nome_filtro}")
                    
                    # Pressionar Enter para aplicar o filtro
                    campo_busca.send_keys(Keys.ENTER)
                    print("Filtro aplicado com Enter")
                    
                    # Aguardar um momento para o filtro ser processado
                    time.sleep(2)
                    
                    # Capturar screenshot após aplicar o filtro
                    capturar_screenshot("14.5_filtro_aplicado")
                    
                    print("Filtro aplicado com sucesso!")
                    
                except Exception as e:
                    print(f"Erro ao aplicar filtro: {str(e)}")
                    capturar_screenshot("14.5_erro_filtro")
                
                print("=== ETAPA 11: Localizando e clicando no botão de Ações para o ID especificado ===")
                
                # CRÍTICO: Maximizar janela ANTES de procurar o botão de Ações
                print("🔧 MAXIMIZANDO JANELA DO NAVEGADOR (essencial para visualizar botões na tabela)...")
                
                # Primeiro, definir um tamanho grande para garantir
                try:
                    # Para headless, é importante definir um tamanho específico primeiro
                    driver.set_window_size(1920, 1080)
                    print("✅ Tamanho inicial definido: 1920x1080")
                    time.sleep(1)
                    
                    # Tentar maximizar (funciona melhor após definir um tamanho)
                    driver.maximize_window()
                    print("✅ Janela maximizada com sucesso!")
                    
                    # Em modo headless, forçar tamanho máximo de tela
                    if headless:
                        # Para headless, usar tamanho de tela full HD ou maior
                        driver.set_window_size(1920, 1080)
                        print("✅ Modo headless: viewport definido para 1920x1080")
                        
                        # Opção adicional: tentar definir um tamanho ainda maior para headless
                        try:
                            driver.execute_script("window.moveTo(0, 0);")
                            driver.execute_script("window.resizeTo(screen.width, screen.height);")
                            print("✅ JavaScript: janela redimensionada para tamanho máximo da tela")
                        except:
                            pass
                    
                    # Aguardar a janela se ajustar e a tabela re-renderizar
                    time.sleep(3)
                    print("✅ Aguardando re-renderização da tabela com janela maximizada...")
                    
                    # Capturar screenshot após maximização
                    capturar_screenshot("11.5_janela_maximizada")
                    
                except Exception as e:
                    print(f"⚠️ Erro ao maximizar: {e}")
                    # Fallback final: garantir pelo menos um tamanho grande
                    try:
                        driver.set_window_size(1920, 1080)
                        print("✅ Fallback: tamanho 1920x1080 aplicado")
                        time.sleep(2)
                    except:
                        print("❌ Não foi possível ajustar o tamanho da janela")
                
                # Forçar um refresh da página para garantir que a tabela seja re-renderizada
                try:
                    driver.execute_script("window.dispatchEvent(new Event('resize'));")
                    print("✅ Evento de redimensionamento disparado para atualizar layout")
                except:
                    pass
                
                print(f"Procurando o botão de Ações para o ID: {id_prospecto}")

                # Primeira abordagem: Tenta encontrar o ID na tabela e então o botão relacionado
                try:
                    # Procurar a linha com o ID especificado
                    id_encontrado = False
                    
                    # Descobrir qual coluna contém o ID (geralmente é a primeira, mas vamos verificar)
                    id_column_index = -1
                    for i, header in enumerate(headers):
                        if header.lower() in ['id', '#', 'código', 'codigo']:
                            id_column_index = i
                            print(f"Coluna de ID encontrada no índice {id_column_index}")
                            break
                    
                    if id_column_index == -1:
                        print("Aviso: Não foi possível identificar a coluna de ID pelos cabeçalhos")
                        print("Assumindo que a coluna de ID é a primeira (índice 0)")
                        id_column_index = 0
                    
                    # Ensure the table is interactable, especially after a filter.
                    try:
                        tabela = wait.until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "table.dataTable.row-border.hover"))
                        )
                        print("Tabela de prospectos confirmada/re-localizada.")
                    except TimeoutException:
                        print("Erro: Tabela de prospectos não encontrada após o filtro. Não é possível prosseguir com a busca do ID.")
                        capturar_screenshot("erro_tabela_nao_encontrada_etapa12")
                        raise Exception("Tabela de prospectos não encontrada em ETAPA 12.")

                    acoes_button = None
                    # This flag will determine if ETAPA 13 should run
                    etapa12_sucesso_e_botao_clicado = False 

                    try:
                        # Strategy 1: Find row by ID text, then find the specific button by aria-label and span text
                        xpath_acoes_button_s1 = (
                            f"//tr[.//td[normalize-space(.)='{id_prospecto}']]/descendant::button[@aria-label='Open menu with custom trigger' and .//span[normalize-space(.)='Ações']]"
                        )
                        print(f"Tentando localizar botão Ações (S1) com XPath: {xpath_acoes_button_s1}")
                        acoes_button = wait.until(
                            EC.element_to_be_clickable((By.XPATH, xpath_acoes_button_s1))
                        )
                        print("Botão de Ações (S1) localizado pela ID do prospecto, aria-label e texto no span.")

                    except TimeoutException:
                        print(f"Tentativa S1 falhou. Tentando XPath alternativo (S2) para o botão Ações para o ID {id_prospecto}.")
                        # Strategy 2: Find row by ID text, then button by class and containing 'Ações'
                        xpath_acoes_button_s2 = (
                            f"//tr[.//td[normalize-space(.)='{id_prospecto}']]/descendant::button[contains(@class, 'reference-button') and contains(., 'Ações')]"
                        )
                        try:
                            print(f"Tentando localizar botão Ações (S2) com XPath: {xpath_acoes_button_s2}")
                            acoes_button = wait.until(
                                EC.element_to_be_clickable((By.XPATH, xpath_acoes_button_s2))
                            )
                            print("Botão de Ações (S2) localizado pela ID do prospecto, classe e texto 'Ações'.")
                        except TimeoutException:
                            print(f"Tentativa S2 falhou. Tentando XPath alternativo (S3) mais genérico.")
                            # Strategy 3: Find row by ID text, then any button in that row that seems like an actions menu
                            xpath_acoes_button_s3 = (
                                f"//tr[.//td[normalize-space(.)='{id_prospecto}']]/descendant::button[contains(@ng-click, '$mdMenu.open') or .//span[contains(text(), 'Ações')]]"
                            )
                            try:
                                print(f"Tentando localizar botão Ações (S3) com XPath: {xpath_acoes_button_s3}")
                                acoes_button = wait.until(
                                    EC.element_to_be_clickable((By.XPATH, xpath_acoes_button_s3))
                                )
                                print("Botão de Ações (S3) localizado (genérico) pela ID do prospecto.")
                            except TimeoutException:
                                print(f"Não foi possível localizar o botão de Ações para o ID {id_prospecto} após múltiplas tentativas.")
                                capturar_screenshot(f"erro_localizar_acoes_id_{id_prospecto}")
                                raise Exception(f"Falha crítica: Botão Ações para ID {id_prospecto} não encontrado.")
                    
                    if acoes_button: # If any strategy above succeeded
                        print(f"Botão de Ações para o ID {id_prospecto} localizado e pronto para clique.")
                        capturar_screenshot(f"15_antes_clicar_acoes_id_{id_prospecto}")
                        
                        print("Clicando no botão de Ações...")
                        clicked_successfully_in_etapa12 = False
                        try:
                            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center', inline: 'center'});", acoes_button)
                            time.sleep(0.7) # Increased pause after scroll for stability

                            # Re-check clickability after scroll and potential animations
                            wait.until(EC.element_to_be_clickable(acoes_button))
                            
                            etapa_atual = iniciar_captura_rede("Clique no botão de Ações")
                            
                            # Method 1: Standard click
                            acoes_button.click()
                            print("Clique normal no botão Ações executado com sucesso.")
                            clicked_successfully_in_etapa12 = True
                        except Exception as e_click_normal:
                            print(f"Clique normal falhou: {e_click_normal}. Tentando clique com JavaScript.")
                            current_exception = e_click_normal
                            try:
                                if "stale element reference" in str(current_exception).lower():
                                    print("Elemento Ações tornou-se stale antes do clique JS. Re-localizando...")
                                    # Re-fetch using the most reliable XPath (S1)
                                    xpath_refetch = f"//tr[.//td[normalize-space(.)='{id_prospecto}']]/descendant::button[@aria-label='Open menu with custom trigger' and .//span[normalize-space(.)='Ações']]"
                                    acoes_button = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_refetch)))
                                    print("Elemento Ações re-localizado para clique JS.")
                                
                                driver.execute_script("arguments[0].click();", acoes_button)
                                print("Clique com JavaScript no botão Ações executado com sucesso.")
                                clicked_successfully_in_etapa12 = True
                            except Exception as e_click_js:
                                print(f"Clique com JavaScript falhou: {e_click_js}. Tentando ActionChains.")
                                current_exception = e_click_js
                                try:
                                    if "stale element reference" in str(current_exception).lower():
                                        print("Elemento Ações tornou-se stale antes do ActionChains. Re-localizando...")
                                        xpath_refetch = f"//tr[.//td[normalize-space(.)='{id_prospecto}']]/descendant::button[@aria-label='Open menu with custom trigger' and .//span[normalize-space(.)='Ações']]"
                                        acoes_button = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_refetch)))
                                        print("Elemento Ações re-localizado para ActionChains.")

                                    actions = ActionChains(driver)
                                    actions.move_to_element(acoes_button).click().perform()
                                    print("Clique com ActionChains no botão Ações executado com sucesso.")
                                    clicked_successfully_in_etapa12 = True
                                except Exception as e_click_action:
                                    print(f"Todas as tentativas de clique no botão Ações falharam: {e_click_action}")
                                    capturar_screenshot(f"erro_clique_acoes_id_{id_prospecto}")
                                    raise # Re-raise the last exception

                        if clicked_successfully_in_etapa12:
                            print("Botão de Ações clicado com sucesso!")
                            capturar_screenshot(f"16_menu_acoes_aberto_id_{id_prospecto}")
                            capturar_requisicoes(etapa_atual)
                            time.sleep(2) # Aguardar menu abrir completamente
                            etapa12_sucesso_e_botao_clicado = True # Set flag for ETAPA 13
                        # else: # Failure to click already raised an exception
                            # print(f"Falha crítica ao clicar no botão de Ações para o ID {id_prospecto}.")
                    # else: # acoes_button was not found, exception already raised
                        # print(f"AVISO: Botão de Ações para ID {id_prospecto} não foi encontrado. ETAPA 13 será pulada.")

                    # ETAPA 13 will only run if etapa12_sucesso_e_botao_clicado is True
                    if etapa12_sucesso_e_botao_clicado:
                                
                                # Nova etapa para clicar no botão "Converter em Cliente"
                                print("=== ETAPA 12: Localizando e clicando no botão 'Converter em Cliente' ===")
                                print("Procurando o elemento com texto 'Converter em Cliente' de cor verde...")
                                
                                try:
                                    # Tentativa 1: Pelo span com estilo de cor verde e texto específico
                                    converter_button = wait.until(
                                        EC.element_to_be_clickable((By.XPATH, "//span[@style='color:green' and contains(text(), 'Converter em Cliente')]"))
                                    )
                                    print("Botão 'Converter em Cliente' localizado pelo span verde")
                                except Exception as e1:
                                    print(f"Erro na tentativa 1: {e1}")
                                    try:
                                        # Tentativa 2: Qualquer span com cor verde
                                        converter_button = wait.until(
                                            EC.element_to_be_clickable((By.CSS_SELECTOR, "span[style='color:green']"))
                                        )
                                        print("Botão 'Converter em Cliente' localizado por span com cor verde")
                                    except Exception as e2:
                                        print(f"Erro na tentativa 2: {e2}")
                                        try:
                                            # Tentativa 3: Pelo texto em qualquer elemento
                                            converter_button = wait.until(
                                                EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Converter em Cliente')]"))
                                            )
                                            print("Botão 'Converter em Cliente' localizado pelo texto")
                                        except Exception as e3:
                                            print(f"Erro na tentativa 3: {e3}")
                                            
                                            # Tentativa 4: Encontrar pelo pai do span (botão)
                                            try:
                                                # Primeiro, tentar encontrar o span (mesmo que não seja clicável)
                                                span = driver.find_element(By.XPATH, "//span[@style='color:green']")
                                                print("Span verde encontrado, tentando encontrar o botão pai...")
                                                
                                                # Subir para o pai até encontrar um botão
                                                converter_button = span
                                                max_attempts = 5
                                                for i_loop_var in range(max_attempts):
                                                    try:
                                                        # Verificar se é um botão
                                                        if converter_button.tag_name == 'button':
                                                            print(f"Botão pai encontrado após {i_loop_var+1} iterações")
                                                            break
                                                        
                                                        # Subir para o pai
                                                        converter_button = converter_button.find_element(By.XPATH, "..")
                                                    except Exception:
                                                        print("Falha ao navegar para o elemento pai")
                                                        break
                                                
                                                if converter_button.tag_name != 'button':
                                                    raise Exception("Não foi possível encontrar o botão pai do span verde")
                                                    
                                            except Exception as e4:
                                                print(f"Erro na tentativa 4: {e4}")
                                                
                                                # Tentativa 5: Localizar todos os botões e verificar
                                                print("Tentando localizar qualquer botão relacionado...")
                                                buttons = driver.find_elements(By.TAG_NAME, "button")
                                                converter_button = None
                                                
                                                for btn in buttons:
                                                    try:
                                                        if "converter" in btn.text.lower() or "cliente" in btn.text.lower():
                                                            converter_button = btn
                                                            print(f"Botão encontrado com texto: '{btn.text}'")
                                                            break
                                                    except:
                                                        pass
                                                
                                                if not converter_button:
                                                    print("Nenhum botão relacionado encontrado, tentando botões dentro do menu...")
                                                    try:
                                                        # Tentar encontrar o menu aberto
                                                        menu = driver.find_element(By.CSS_SELECTOR, "md-menu-content")
                                                        menu_buttons = menu.find_elements(By.TAG_NAME, "button")
                                                        
                                                        if len(menu_buttons) > 0:
                                                            print(f"Encontrados {len(menu_buttons)} botões no menu. Usando o primeiro.")
                                                            converter_button = menu_buttons[0]
                                                        else:
                                                            raise Exception("Nenhum botão encontrado no menu")
                                                    except Exception as e5:
                                                        print(f"Erro final: {e5}")
                                                        capturar_screenshot("erro_localizar_converter")
                                                        raise Exception("Não foi possível localizar o botão 'Converter em Cliente'")
                                
                                # Se chegou aqui, encontrou o botão
                                capturar_screenshot("18_antes_clicar_converter")
                                
                                # Rolar até o botão e clicar
                                print("Clicando no botão 'Converter em Cliente'...")
                                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", converter_button)
                                time.sleep(1)
                                
                                # JavaScript click às vezes é mais confiável em elementos de menu
                                etapa_atual = iniciar_captura_rede("Clique no botão 'Converter em Cliente'")
                                try:
                                    driver.execute_script("arguments[0].click();", converter_button)
                                    print("Clique executado via JavaScript")
                                except Exception as e:
                                    print(f"Falha no clique via JavaScript: {e}")
                                    print("Tentando clique normal...")
                                    converter_button.click()
                                
                                print("Botão 'Converter em Cliente' clicado com sucesso!")
                                capturar_requisicoes(etapa_atual)
                                
                                # Aguardar carregamento da próxima página
                                time.sleep(3)
                                capturar_screenshot("19_apos_clicar_converter")
                                
                                print("=== ETAPA 13: Clicando no primeiro botão do wizard ===")
                                print("Procurando o primeiro botão do wizard...")
                                
                                try:
                                    # Aguardar o botão aparecer e tornar-se clicável
                                    primeiro_botao = wait.until(
                                        EC.element_to_be_clickable((By.XPATH, "/html/body/div[5]/md-dialog/md-dialog-content/div/hubsoft-cliente-wizard/div[2]/md-dialog-actions/div[2]/button"))
                                    )
                                    print("Primeiro botão do wizard localizado com sucesso!")
                                    
                                    # Capturar screenshot antes de clicar
                                    capturar_screenshot("20_antes_primeiro_botao_wizard")
                                    
                                    # Clicar no primeiro botão
                                    etapa_atual = iniciar_captura_rede("Clique no primeiro botão do wizard")
                                    
                                    # Rolar até o botão para garantir que está visível
                                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", primeiro_botao)
                                    time.sleep(1)
                                    
                                    # Tentar diferentes métodos de clique
                                    try:
                                        primeiro_botao.click()
                                        print("Primeiro botão clicado com sucesso (clique normal)")
                                    except Exception as e_click:
                                        print(f"Clique normal falhou: {e_click}. Tentando JavaScript...")
                                        driver.execute_script("arguments[0].click();", primeiro_botao)
                                        print("Primeiro botão clicado com sucesso (JavaScript)")
                                    
                                    capturar_requisicoes(etapa_atual)
                                    
                                    # Aguardar um momento entre os cliques
                                    time.sleep(2)
                                    capturar_screenshot("21_apos_primeiro_botao_wizard")
                                    
                                    print("=== ETAPA 14: Clicando no segundo botão do wizard ===")
                                    print("Procurando o segundo botão do wizard...")
                                    
                                    # Aguardar o segundo botão (que pode ser o mesmo XPath se a tela mudou)
                                    segundo_botao = wait.until(
                                        EC.element_to_be_clickable((By.XPATH, "/html/body/div[5]/md-dialog/md-dialog-content/div/hubsoft-cliente-wizard/div[2]/md-dialog-actions/div[2]/button"))
                                    )
                                    print("Segundo botão do wizard localizado com sucesso!")
                                    
                                    # Capturar screenshot antes do segundo clique
                                    capturar_screenshot("22_antes_segundo_botao_wizard")
                                    
                                    # Clicar no segundo botão
                                    etapa_atual = iniciar_captura_rede("Clique no segundo botão do wizard")
                                    
                                    # Rolar até o botão para garantir que está visível
                                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", segundo_botao)
                                    time.sleep(1)
                                    
                                    # Tentar diferentes métodos de clique
                                    try:
                                        segundo_botao.click()
                                        print("Segundo botão clicado com sucesso (clique normal)")
                                    except Exception as e_click:
                                        print(f"Clique normal falhou: {e_click}. Tentando JavaScript...")
                                        driver.execute_script("arguments[0].click();", segundo_botao)
                                        print("Segundo botão clicado com sucesso (JavaScript)")
                                    
                                    capturar_requisicoes(etapa_atual)
                                    
                                    # Aguardar carregamento após o segundo clique
                                    time.sleep(3)
                                    capturar_screenshot("23_apos_segundo_botao_wizard")
                                    
                                    print("Ambos os botões do wizard foram clicados com sucesso!")
                                    
                                    print("=== ETAPA 15: Clicando no elemento md-select ===")
                                    print("Procurando o elemento md-select do wizard...")
                                    
                                    # Aguardar o elemento md-select aparecer e tornar-se clicável
                                    md_select_element = wait.until(
                                        EC.element_to_be_clickable((By.XPATH, "/html/body/div[5]/md-dialog/md-dialog-content/div/hubsoft-cliente-wizard/div[1]/div/div/form/div/md-input-container/md-select"))
                                    )
                                    print("Elemento md-select localizado com sucesso!")
                                    
                                    # Capturar screenshot antes de clicar
                                    capturar_screenshot("24_antes_clicar_md_select")
                                    
                                    # Primeiro clique no md-select
                                    etapa_atual = iniciar_captura_rede("Primeiro clique no md-select")
                                    
                                    # Rolar até o elemento para garantir que está visível
                                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", md_select_element)
                                    time.sleep(0.5)
                                    
                                    # Tentar diferentes métodos de clique
                                    try:
                                        md_select_element.click()
                                        print("Primeiro clique no md-select executado com sucesso (clique normal)")
                                    except Exception as e_click:
                                        print(f"Clique normal falhou: {e_click}. Tentando JavaScript...")
                                        driver.execute_script("arguments[0].click();", md_select_element)
                                        print("Primeiro clique no md-select executado com sucesso (JavaScript)")
                                    
                                    capturar_requisicoes(etapa_atual)
                                    capturar_screenshot("25_apos_primeiro_clique_md_select")
                                    
                                    # Aguardar 1 segundo conforme solicitado
                                    print("Aguardando 1 segundo antes de clicar no md-option...")
                                    time.sleep(1)
                                    
                                    # Clicar no elemento md-option
                                    print("Procurando e clicando no elemento md-option...")
                                    etapa_atual = iniciar_captura_rede("Clique no md-option")
                                    
                                    # Localizar o elemento md-option
                                    try:
                                        md_option_element = wait.until(
                                            EC.element_to_be_clickable((By.XPATH, "/html/body/div[7]/md-select-menu/md-content/md-option"))
                                        )
                                        print("Elemento md-option localizado com sucesso!")
                                    except Exception as e:
                                        print(f"Erro ao localizar md-option: {e}")
                                        # Tentar localizar de forma mais genérica
                                        try:
                                            md_option_element = wait.until(
                                                EC.element_to_be_clickable((By.CSS_SELECTOR, "md-select-menu md-content md-option"))
                                            )
                                            print("Elemento md-option localizado com seletor CSS genérico!")
                                        except Exception as e2:
                                            print(f"Erro também com seletor genérico: {e2}")
                                            # Última tentativa - qualquer md-option visível
                                            md_option_element = wait.until(
                                                EC.element_to_be_clickable((By.TAG_NAME, "md-option"))
                                            )
                                            print("Elemento md-option localizado por tag name!")
                                    
                                    # Capturar screenshot antes de clicar no md-option
                                    capturar_screenshot("26_antes_clicar_md_option")
                                    
                                    # Rolar até o elemento para garantir que está visível
                                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", md_option_element)
                                    time.sleep(0.5)
                                    
                                    # Tentar diferentes métodos de clique no md-option
                                    try:
                                        md_option_element.click()
                                        print("Clique no md-option executado com sucesso (clique normal)")
                                    except Exception as e_click:
                                        print(f"Clique normal no md-option falhou: {e_click}. Tentando JavaScript...")
                                        driver.execute_script("arguments[0].click();", md_option_element)
                                        print("Clique no md-option executado com sucesso (JavaScript)")
                                    
                                    capturar_requisicoes(etapa_atual)
                                    capturar_screenshot("27_apos_clicar_md_option")
                                    
                                    print("Sequência md-select -> md-option executada com sucesso!")
                                    
                                    print("=== ETAPA 16: Segundo md-select, opção específica e botão avançar ===")
                                    print("Procurando o segundo elemento md-select...")
                                    
                                    # Aguardar um momento para que a interface se estabilize
                                    time.sleep(1)
                                    
                                    # Localizar o segundo md-select
                                    try:
                                        segundo_md_select = wait.until(
                                            EC.element_to_be_clickable((By.XPATH, "/html/body/div[5]/md-dialog/md-dialog-content/div/hubsoft-cliente-wizard/div[1]/div/div/form/div/div[2]/md-input-container[2]/md-select"))
                                        )
                                        print("Segundo md-select localizado com sucesso!")
                                        
                                        # Capturar screenshot antes de clicar
                                        capturar_screenshot("28_antes_segundo_md_select")
                                        
                                        # Clicar no segundo md-select
                                        etapa_atual = iniciar_captura_rede("Clique no segundo md-select")
                                        
                                        # Rolar até o elemento para garantir que está visível
                                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", segundo_md_select)
                                        time.sleep(0.5)
                                        
                                        # Tentar diferentes métodos de clique
                                        try:
                                            segundo_md_select.click()
                                            print("Segundo md-select clicado com sucesso (clique normal)")
                                        except Exception as e_click:
                                            print(f"Clique normal falhou: {e_click}. Tentando JavaScript...")
                                            driver.execute_script("arguments[0].click();", segundo_md_select)
                                            print("Segundo md-select clicado com sucesso (JavaScript)")
                                        
                                        capturar_requisicoes(etapa_atual)
                                        capturar_screenshot("29_apos_segundo_md_select")
                                        
                                        # Aguardar o menu aparecer
                                        time.sleep(1)
                                        
                                        # Localizar e clicar na opção específica (md-option[25])
                                        print("Procurando a opção md-option[25]...")
                                        etapa_atual = iniciar_captura_rede("Clique na opção md-option[25]")
                                        
                                        try:
                                            opcao_25 = wait.until(
                                                EC.element_to_be_clickable((By.XPATH, "/html/body/div[8]/md-select-menu/md-content/md-option[25]"))
                                            )
                                            print("Opção md-option[25] localizada com sucesso!")
                                        except Exception as e:
                                            print(f"Erro ao localizar md-option[25]: {e}")
                                            # Tentar localizar de forma mais genérica
                                            try:
                                                # Tentar localizar na div[7] caso a numeração tenha mudado
                                                opcao_25 = wait.until(
                                                    EC.element_to_be_clickable((By.XPATH, "/html/body/div[7]/md-select-menu/md-content/md-option[25]"))
                                                )
                                                print("Opção md-option[25] localizada na div[7]!")
                                            except Exception as e2:
                                                print(f"Erro também na div[7]: {e2}")
                                                # Última tentativa - tentar encontrar qualquer md-option[25]
                                                opcao_25 = wait.until(
                                                    EC.element_to_be_clickable((By.CSS_SELECTOR, "md-option:nth-child(25)"))
                                                )
                                                print("Opção md-option[25] localizada por CSS selector!")
                                        
                                        # Capturar screenshot antes de clicar na opção
                                        capturar_screenshot("30_antes_opcao_25")
                                        
                                        # Rolar até a opção para garantir que está visível
                                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", opcao_25)
                                        time.sleep(0.5)
                                        
                                        # Clicar na opção 25
                                        try:
                                            opcao_25.click()
                                            print("Opção md-option[25] clicada com sucesso (clique normal)")
                                        except Exception as e_click:
                                            print(f"Clique normal na opção falhou: {e_click}. Tentando JavaScript...")
                                            driver.execute_script("arguments[0].click();", opcao_25)
                                            print("Opção md-option[25] clicada com sucesso (JavaScript)")
                                        
                                        capturar_requisicoes(etapa_atual)
                                        capturar_screenshot("31_apos_opcao_25")
                                        
                                        # Aguardar um momento para que a seleção seja processada
                                        time.sleep(1)
                                        
                                        # Clicar no botão para avançar
                                        print("Procurando o botão para avançar...")
                                        etapa_atual = iniciar_captura_rede("Clique no botão avançar")
                                        
                                        botao_avancar = wait.until(
                                            EC.element_to_be_clickable((By.XPATH, "/html/body/div[5]/md-dialog/md-dialog-content/div/hubsoft-cliente-wizard/div[2]/md-dialog-actions/div[2]/button"))
                                        )
                                        print("Botão avançar localizado com sucesso!")
                                        
                                        # Capturar screenshot antes de clicar no botão
                                        capturar_screenshot("32_antes_botao_avancar")
                                        
                                        # Rolar até o botão para garantir que está visível
                                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", botao_avancar)
                                        time.sleep(0.5)
                                        
                                        # Clicar no botão avançar
                                        try:
                                            botao_avancar.click()
                                            print("Botão avançar clicado com sucesso (clique normal)")
                                        except Exception as e_click:
                                            print(f"Clique normal no botão falhou: {e_click}. Tentando JavaScript...")
                                            driver.execute_script("arguments[0].click();", botao_avancar)
                                            print("Botão avançar clicado com sucesso (JavaScript)")
                                        
                                        capturar_requisicoes(etapa_atual)
                                        capturar_screenshot("33_apos_botao_avancar")
                                        
                                        print("ETAPA 16 concluída: segundo md-select → opção 25 → botão avançar!")
                                        
                                        print("=== ETAPA 17: Próximo botão, novo md-select e primeira opção ===")
                                        
                                        # Aguardar um momento para que a interface se estabilize
                                        time.sleep(2)
                                        
                                        # Clicar no próximo botão (mesmo XPath do anterior)
                                        print("Clicando no próximo botão do wizard...")
                                        etapa_atual = iniciar_captura_rede("Clique no próximo botão do wizard")
                                        
                                        try:
                                            proximo_botao = wait.until(
                                                EC.element_to_be_clickable((By.XPATH, "/html/body/div[5]/md-dialog/md-dialog-content/div/hubsoft-cliente-wizard/div[2]/md-dialog-actions/div[2]/button"))
                                            )
                                            print("Próximo botão localizado com sucesso!")
                                            
                                            # Capturar screenshot antes de clicar
                                            capturar_screenshot("34_antes_proximo_botao")
                                            
                                            # Rolar até o botão para garantir que está visível
                                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", proximo_botao)
                                            time.sleep(0.5)
                                            
                                            # Clicar no próximo botão
                                            try:
                                                proximo_botao.click()
                                                print("Próximo botão clicado com sucesso (clique normal)")
                                            except Exception as e_click:
                                                print(f"Clique normal falhou: {e_click}. Tentando JavaScript...")
                                                driver.execute_script("arguments[0].click();", proximo_botao)
                                                print("Próximo botão clicado com sucesso (JavaScript)")
                                            
                                            capturar_requisicoes(etapa_atual)
                                            capturar_screenshot("35_apos_proximo_botao")
                                            
                                            # Aguardar o novo elemento aparecer na próxima tela
                                            print("Aguardando o novo md-select aparecer...")
                                            time.sleep(3)
                                            
                                            # Localizar e clicar no novo md-select
                                            print("Procurando o novo elemento md-select...")
                                            etapa_atual = iniciar_captura_rede("Clique no novo md-select")
                                            
                                            novo_md_select = wait.until(
                                                EC.element_to_be_clickable((By.XPATH, "/html/body/div[5]/md-dialog/md-dialog-content/div/hubsoft-cliente-wizard/div[1]/div/form/div[1]/div/md-input-container[1]/md-select"))
                                            )
                                            print("Novo md-select localizado com sucesso!")
                                            
                                            # Capturar screenshot antes de clicar no novo md-select
                                            capturar_screenshot("36_antes_novo_md_select")
                                            
                                            # Rolar até o elemento para garantir que está visível
                                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", novo_md_select)
                                            time.sleep(0.5)
                                            
                                            # Clicar no novo md-select
                                            try:
                                                novo_md_select.click()
                                                print("Novo md-select clicado com sucesso (clique normal)")
                                            except Exception as e_click:
                                                print(f"Clique normal falhou: {e_click}. Tentando JavaScript...")
                                                driver.execute_script("arguments[0].click();", novo_md_select)
                                                print("Novo md-select clicado com sucesso (JavaScript)")
                                            
                                            capturar_requisicoes(etapa_atual)
                                            capturar_screenshot("37_apos_novo_md_select")
                                            
                                            # Aguardar o menu aparecer
                                            time.sleep(1)
                                            
                                            # Localizar e clicar na primeira opção (md-option[1])
                                            print("Procurando a primeira opção md-option[1]...")
                                            etapa_atual = iniciar_captura_rede("Clique na primeira opção")
                                            
                                            try:
                                                primeira_opcao = wait.until(
                                                    EC.element_to_be_clickable((By.XPATH, "/html/body/div[7]/md-select-menu/md-content/md-option[1]"))
                                                )
                                                print("Primeira opção md-option[1] localizada com sucesso!")
                                            except Exception as e:
                                                print(f"Erro ao localizar md-option[1]: {e}")
                                                # Tentar localizar de forma mais genérica
                                                try:
                                                    # Tentar localizar em outra div caso a numeração tenha mudado
                                                    primeira_opcao = wait.until(
                                                        EC.element_to_be_clickable((By.XPATH, "/html/body/div[8]/md-select-menu/md-content/md-option[1]"))
                                                    )
                                                    print("Primeira opção md-option[1] localizada na div[8]!")
                                                except Exception as e2:
                                                    print(f"Erro também na div[8]: {e2}")
                                                    # Última tentativa - primeira opção por CSS
                                                    primeira_opcao = wait.until(
                                                        EC.element_to_be_clickable((By.CSS_SELECTOR, "md-option:first-child"))
                                                    )
                                                    print("Primeira opção localizada por CSS selector!")
                                            
                                            # Capturar screenshot antes de clicar na primeira opção
                                            capturar_screenshot("38_antes_primeira_opcao")
                                            
                                            # Rolar até a opção para garantir que está visível
                                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", primeira_opcao)
                                            time.sleep(0.5)
                                            
                                            # Clicar na primeira opção
                                            try:
                                                primeira_opcao.click()
                                                print("Primeira opção md-option[1] clicada com sucesso (clique normal)")
                                            except Exception as e_click:
                                                print(f"Clique normal na primeira opção falhou: {e_click}. Tentando JavaScript...")
                                                driver.execute_script("arguments[0].click();", primeira_opcao)
                                                print("Primeira opção md-option[1] clicada com sucesso (JavaScript)")
                                            
                                            capturar_requisicoes(etapa_atual)
                                            capturar_screenshot("39_apos_primeira_opcao")
                                            
                                            print("ETAPA 17 concluída: próximo botão → novo md-select → primeira opção!")
                                            
                                            print("=== ETAPA 18: Finalização - Três cliques finais ===")
                                            
                                            # Aguardar um momento para que a interface se estabilize
                                            time.sleep(2)
                                            
                                            # PRIMEIRO CLIQUE - Botão padrão
                                            print("1/3 - Clicando no primeiro botão final...")
                                            etapa_atual = iniciar_captura_rede("Primeiro clique final")
                                            
                                            try:
                                                primeiro_botao_final = wait.until(
                                                    EC.element_to_be_clickable((By.XPATH, "/html/body/div[5]/md-dialog/md-dialog-content/div/hubsoft-cliente-wizard/div[2]/md-dialog-actions/div[2]/button"))
                                                )
                                                print("Primeiro botão final localizado com sucesso!")
                                                
                                                # Capturar screenshot antes do primeiro clique
                                                capturar_screenshot("40_antes_primeiro_botao_final")
                                                
                                                # Rolar até o botão para garantir que está visível
                                                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", primeiro_botao_final)
                                                time.sleep(0.5)
                                                
                                                # Clicar no primeiro botão final
                                                try:
                                                    primeiro_botao_final.click()
                                                    print("Primeiro botão final clicado com sucesso (clique normal)")
                                                except Exception as e_click:
                                                    print(f"Clique normal falhou: {e_click}. Tentando JavaScript...")
                                                    driver.execute_script("arguments[0].click();", primeiro_botao_final)
                                                    print("Primeiro botão final clicado com sucesso (JavaScript)")
                                                
                                                capturar_requisicoes(etapa_atual)
                                                capturar_screenshot("41_apos_primeiro_botao_final")
                                                
                                                # Aguardar entre cliques
                                                time.sleep(2)
                                                
                                                # SEGUNDO CLIQUE - Mesmo botão padrão
                                                print("2/3 - Clicando no segundo botão final...")
                                                etapa_atual = iniciar_captura_rede("Segundo clique final")
                                                
                                                segundo_botao_final = wait.until(
                                                    EC.element_to_be_clickable((By.XPATH, "/html/body/div[5]/md-dialog/md-dialog-content/div/hubsoft-cliente-wizard/div[2]/md-dialog-actions/div[2]/button"))
                                                )
                                                print("Segundo botão final localizado com sucesso!")
                                                
                                                # Capturar screenshot antes do segundo clique
                                                capturar_screenshot("42_antes_segundo_botao_final")
                                                
                                                # Rolar até o botão para garantir que está visível
                                                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", segundo_botao_final)
                                                time.sleep(0.5)
                                                
                                                # Clicar no segundo botão final
                                                try:
                                                    segundo_botao_final.click()
                                                    print("Segundo botão final clicado com sucesso (clique normal)")
                                                except Exception as e_click:
                                                    print(f"Clique normal falhou: {e_click}. Tentando JavaScript...")
                                                    driver.execute_script("arguments[0].click();", segundo_botao_final)
                                                    print("Segundo botão final clicado com sucesso (JavaScript)")
                                                
                                                capturar_requisicoes(etapa_atual)
                                                capturar_screenshot("43_apos_segundo_botao_final")
                                                
                                                # Aguardar entre cliques
                                                time.sleep(2)
                                                
                                                # TERCEIRO CLIQUE - Botão de SALVAR
                                                print("3/3 - Clicando no botão de SALVAR...")
                                                etapa_atual = iniciar_captura_rede("Clique no botão Salvar")
                                                
                                                botao_salvar = wait.until(
                                                    EC.element_to_be_clickable((By.XPATH, "/html/body/div[5]/md-dialog/md-dialog-content/div/hubsoft-cliente-wizard/div[2]/md-dialog-actions/div[2]/div/button"))
                                                )
                                                print("Botão SALVAR localizado com sucesso!")
                                                
                                                # Capturar screenshot antes do clique de salvar
                                                capturar_screenshot("44_antes_botao_salvar")
                                                
                                                # Rolar até o botão para garantir que está visível
                                                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", botao_salvar)
                                                time.sleep(0.5)
                                                
                                                # Clicar no botão SALVAR
                                                try:
                                                    botao_salvar.click()
                                                    print("Botão SALVAR clicado com sucesso (clique normal)")
                                                except Exception as e_click:
                                                    print(f"Clique normal falhou: {e_click}. Tentando JavaScript...")
                                                    driver.execute_script("arguments[0].click();", botao_salvar)
                                                    print("Botão SALVAR clicado com sucesso (JavaScript)")
                                                
                                                capturar_requisicoes(etapa_atual)
                                                capturar_screenshot("45_apos_botao_salvar")
                                                
                                                # Aguardar finalização do processo
                                                time.sleep(3)
                                                capturar_screenshot("46_processo_finalizado")
                                                
                                                print("🎉 ETAPA 18 CONCLUÍDA - PROCESSO TOTALMENTE FINALIZADO! 🎉")
                                                print("✅ Sequência completa executada:")
                                                print("   1️⃣ Primeiro botão final")
                                                print("   2️⃣ Segundo botão final") 
                                                print("   3️⃣ Botão SALVAR")
                                                print("🏁 Cliente convertido e salvo com sucesso!")
                                                
                                            except Exception as e:
                                                print(f"❌ Erro na ETAPA 18 (Finalização): {e}")
                                                capturar_screenshot("erro_etapa_18_finalizacao")
                                                print("⚠️  Processo pode não ter sido finalizado completamente")
                                            
                                        except Exception as e:
                                            print(f"Erro na ETAPA 17: {e}")
                                            capturar_screenshot("erro_etapa_17")
                                            # Não interromper o script, apenas registrar o erro
                                        
                                    except Exception as e:
                                        print(f"Erro na ETAPA 16: {e}")
                                        capturar_screenshot("erro_etapa_16")
                                        # Não interromper o script, apenas registrar o erro
                                    
                                except Exception as e:
                                    print(f"Erro ao clicar nos botões do wizard: {e}")
                                    capturar_screenshot("erro_botoes_wizard")
                                    # Não interromper o script, apenas registrar o erro
                                
                                etapa_atual = iniciar_captura_rede("Finalização do wizard")
                                capturar_requisicoes(etapa_atual)
                                
                                # Aguardar alguns segundos para visualização final
                                time.sleep(5)
                    
                    if not id_encontrado:
                        print(f"ERRO: ID {id_prospecto} não foi encontrado na tabela após o filtro (se aplicado).")
                        capturar_screenshot("15_id_nao_encontrado")
                    
                    if not id_encontrado:
                        print(f"ERRO: ID {id_prospecto} não foi encontrado na tabela após o filtro (se aplicado).")
                        capturar_screenshot("15_id_nao_encontrado")
                        
                except Exception as e:
                    print(f"Erro na etapa 11: {str(e)}")
                    capturar_screenshot("15_erro_etapa11")
                    # raise e # Considerar se deve parar o script ou tentar continuar

                    if not id_encontrado:
                        print(f"Aviso: ID {id_prospecto} não encontrado na tabela")
                        raise Exception(f"ID {id_prospecto} não encontrado na tabela de prospectos")
                
                except Exception as e:
                    print(f"Erro ao localizar ou clicar no botão de Ações: {e}")
                    capturar_screenshot("erro_botao_acoes")
            
            except Exception as e:
                print(f"Erro ao extrair dados da tabela: {e}")
                capturar_screenshot("erro_extracao_tabela")
            
            print("=== PROCESSO CONCLUÍDO COM SUCESSO! ===")
            print("Todas as screenshots foram salvas na pasta 'screenshots'")
            
            # No final, antes de fechar o navegador
            print("Salvando logs de requisições...")
            salvar_requisicoes_csv()
            
            print("Análise de requisições concluída com sucesso!")
            
        else:
            print("Possível falha no login. Verifique as screenshots.")
        
        # Aguardar alguns segundos antes de fechar
        print("Aguardando 5 segundos...")
        time.sleep(5)
        
    except Exception as e:
        print(f"Erro ao interagir com a página: {e}")
        # Tentar capturar screenshot em caso de erro
        try:
            capturar_screenshot("erro_geral")
            print("Screenshot do erro salvo")
            # Tentar salvar os logs já capturados
            salvar_requisicoes_csv()
        except:
            pass
    finally:
        # Fechar o navegador
        print("Fechando o navegador...")
        driver.quit()
        print("Navegador fechado com sucesso!")

#if __name__ == "__main__":
#    main("JOÃO SILVA SANTOS", "1518")




