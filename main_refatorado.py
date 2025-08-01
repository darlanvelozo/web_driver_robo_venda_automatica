import time
import os
import argparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from dotenv import load_dotenv
import datetime
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import logging
import psycopg2
import tempfile
import shutil

# Configurar logging apenas para erros
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Carregar variáveis do arquivo .env
load_dotenv()

# Configurações do banco de dados
DB_CONFIG = {
    'host': '187.62.153.52',
    'database': 'robo_venda_automatica',
    'user': 'admin',
    'password': 'qualidade@trunks.57',
    'port': 5432
}

class ProspectoProcessor:
    def __init__(self):
        self.conn = None
        self.screenshots_dir = "screenshots"
        self.start_time = None
        self.current_prospecto_id = None
        self.tentativa_atual = None  # Controla a tentativa atual da execução
        self.primeira_chamada = True  # Flag para identificar primeira chamada da execução
        
        # Criar pasta para screenshots apenas para erros
        if not os.path.exists(self.screenshots_dir):
            os.makedirs(self.screenshots_dir)
    
    def conectar_banco(self):
        """Conecta ao banco de dados PostgreSQL"""
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            return True
        except Exception as e:
            logger.error(f"Erro ao conectar ao banco: {e}")
            return False
    
    def desconectar_banco(self):
        """Desconecta do banco de dados"""
        if self.conn:
            self.conn.close()
    
    def salvar_prospecto(self, nome_prospecto, id_prospecto_hubsoft, status_atual, erro=None, resultado=None):
        """Salva ou atualiza dados do prospecto no banco"""
        if not self.conn:
            return False
        
        try:
            cursor = self.conn.cursor()
            tempo_processamento = int(time.time() - self.start_time) if self.start_time else 0
            
            # Mapear status interno para os valores permitidos pela tabela
            status_mapping = {
                "INICIANDO": "processando",
                "LOGIN_REALIZADO": "processando", 
                "NAVEGACAO_PROSPECTOS": "processando",
                "PROSPECTO_LOCALIZADO": "processando",
                "MENU_ACOES_ABERTO": "processando",
                "WIZARD_INICIADO": "processando",
                "WIZARD_TELA1": "processando",
                "WIZARD_SELECOES": "processando", 
                "WIZARD_TELA2": "processando",
                "CONCLUIDO": "finalizado",
                "ERRO_LOGIN": "erro",
                "ERRO_NAVEGACAO": "erro",
                "ERRO_LOCALIZACAO": "erro",
                "ERRO_ACOES": "erro",
                "ERRO_CONVERTER": "erro",
                "ERRO_WIZARD1": "erro",
                "ERRO_WIZARD_SELECOES": "erro",
                "ERRO_WIZARD2": "erro",
                "ERRO_FINALIZACAO": "erro",
                "ERRO_GERAL": "erro"
            }
            
            status_db = status_mapping.get(status_atual, "erro")
            
            # VERIFICAÇÃO CRÍTICA: Só permite "finalizado" se for realmente CONCLUIDO com sucesso
            if status_db == "finalizado" and resultado != "sucesso":
                print(f"⚠️ ATENÇÃO: Status '{status_atual}' mapeado para 'finalizado' mas resultado não é 'sucesso'")
                status_db = "erro"
                erro = f"Processo não finalizado corretamente. Status original: {status_atual}"
                resultado = "falha"
            
            # Verificar se já existe
            cursor.execute(
                "SELECT id, tentativas_processamento FROM prospectos WHERE id_prospecto_hubsoft = %s",
                (id_prospecto_hubsoft,)
            )
            resultado_busca = cursor.fetchone()
            
            if resultado_busca:
                # Atualizar registro existente
                id_existente, tentativas_atuais = resultado_busca
                self.current_prospecto_id = id_existente
                
                # CORREÇÃO: Incrementar tentativas apenas na primeira chamada da execução
                if self.primeira_chamada:
                    self.tentativa_atual = tentativas_atuais + 1
                    self.primeira_chamada = False
                    print(f"🔄 Nova execução iniciada - Tentativa {self.tentativa_atual}")
                else:
                    # Manter a mesma tentativa para atualizações de status da mesma execução
                    self.tentativa_atual = tentativas_atuais if self.tentativa_atual is None else self.tentativa_atual
                
                # VERIFICAÇÃO: Se atingiu 3 tentativas e está com erro, marcar como erro final
                if self.tentativa_atual >= 3 and status_db == "erro":
                    print(f"❌ Prospecto {nome_prospecto} atingiu o máximo de 3 tentativas - marcando como erro final")
                    erro = f"Máximo de 3 tentativas atingido. Última falha: {erro}" if erro else "Máximo de 3 tentativas atingido"
                    status_db = "erro"  # Força status como erro
                    resultado = "falha"  # Força resultado como falha
                
                cursor.execute("""
                    UPDATE prospectos SET
                        nome_prospecto = %s,
                        status = %s,
                        data_atualizacao = %s,
                        data_processamento = %s,
                        tentativas_processamento = %s,
                        erro_processamento = %s,
                        tempo_processamento = %s,
                        resultado_processamento = %s
                    WHERE id = %s
                """, (
                    nome_prospecto, status_db, datetime.datetime.now(), datetime.datetime.now(),
                    self.tentativa_atual, erro, tempo_processamento, resultado, id_existente
                ))
                
                print(f"🔄 Atualizando prospecto ID {id_existente}: {status_atual} -> {status_db} (Tentativa {self.tentativa_atual})")
            else:
                # Criar novo registro
                self.tentativa_atual = 1
                self.primeira_chamada = False
                
                cursor.execute("""
                    INSERT INTO prospectos (
                        nome_prospecto, id_prospecto_hubsoft, status, 
                        data_criacao, data_atualizacao, data_processamento,
                        tentativas_processamento, erro_processamento,
                        tempo_processamento, resultado_processamento
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    nome_prospecto, id_prospecto_hubsoft, status_db,
                    datetime.datetime.now(), datetime.datetime.now(), datetime.datetime.now(),
                    self.tentativa_atual, erro, tempo_processamento, resultado
                ))
                self.current_prospecto_id = cursor.fetchone()[0]
                
                print(f"✨ Criando novo prospecto ID {self.current_prospecto_id}: {status_atual} -> {status_db} (Tentativa {self.tentativa_atual})")
            
            self.conn.commit()
            cursor.close()
            return True
            
        except Exception as e:
            logger.error(f"Erro ao salvar prospecto: {e}")
            if self.conn:
                self.conn.rollback()
            return False
    
    def capturar_screenshot_erro(self, driver, nome, etapa):
        """Captura screenshot apenas em caso de erro"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.screenshots_dir}/ERRO_{timestamp}_{etapa}_{nome}.png"
            driver.save_screenshot(filename)
            logger.error(f"Screenshot de erro salvo: {filename}")
            print(f"📸 Screenshot de erro salvo: {filename}")
            return filename
        except Exception as e:
            logger.error(f"Erro ao capturar screenshot: {e}")
            return None

def main(nome_filtro=None, id_prospecto=None):
    """
    Função principal que automatiza a conversão de prospectos em clientes
    """
    processor = ProspectoProcessor()
    processor.start_time = time.time()
    
    # Conectar ao banco
    if not processor.conectar_banco():
        print("❌ Falha ao conectar ao banco de dados")
        return
    
    print("✅ Conectado ao banco de dados PostgreSQL")
    
    
    # VERIFICAÇÃO: Não processar se já tem 3 ou mais tentativas
    try:
        cursor = processor.conn.cursor()
        cursor.execute(
            "SELECT tentativas_processamento, status FROM prospectos WHERE id_prospecto_hubsoft = %s",
            (str(id_prospecto),)
        )
        resultado = cursor.fetchone()
        cursor.close()
        
        if resultado:
            tentativas, status = resultado
            if tentativas >= 3:
                print(f"❌ Prospecto {nome_filtro} (ID: {id_prospecto}) já atingiu o máximo de 3 tentativas")
                processor.desconectar_banco()
                return
            if status == 'erro' and tentativas >= 3:
                print(f"❌ Prospecto {nome_filtro} (ID: {id_prospecto}) já marcado como erro final")
                processor.desconectar_banco()
                return
    except Exception as e:
        print(f"⚠️ Erro ao verificar tentativas: {e}")
    
    print(f"🤖 Iniciando processamento: {nome_filtro} (ID: {id_prospecto})")
    
    # Configurar argumentos de linha de comando
    parser = argparse.ArgumentParser(description='Automatização de conversão de prospectos')
    parser.add_argument('--no-headless', action='store_true', 
                        help='Executar o navegador em modo visível (desabilita headless)')
    args = parser.parse_args()
    
    # MUDANÇA: Agora headless é padrão, use --no-headless para desabilitar
    headless = not args.no_headless and os.environ.get('HEADLESS', 'true').lower() != 'false'
    
    # Obter credenciais do .env
    usuario = os.environ.get('USUARIO', '')
    senha = os.environ.get('SENHA', '')
    
    if not usuario or not senha:
        print("❌ Credenciais não encontradas no arquivo .env")
        processor.desconectar_banco()
        return
    
    # Configurações do Chrome (mesmas do arquivo original)
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
    
    if headless:
        chrome_options.add_argument("--headless=new")
        # Configurações adicionais para headless
        chrome_options.add_argument('--disable-gpu')  # Necessário para alguns sistemas
        chrome_options.add_argument('--window-size=1920,1080')  # Força tamanho em headless
        chrome_options.add_argument('--force-device-scale-factor=1')  # Escala normal
        print("🕶️ Executando em modo headless")
    
    print(f"⚙️ Configurando o Chrome... (Modo headless: {'Sim' if headless else 'Não'})")
    
    driver = None
    temp_dir = None
    try:
        # Inicializar status
        processor.salvar_prospecto(nome_filtro, id_prospecto, "INICIANDO")
        
        # Adicionar diretório único para evitar conflitos
        temp_dir = tempfile.mkdtemp()
        chrome_options.add_argument(f"--user-data-dir={temp_dir}")
        chrome_options.add_argument("--no-first-run")
        chrome_options.add_argument("--disable-default-apps")
        
        driver = webdriver.Chrome(options=chrome_options)
        wait = WebDriverWait(driver, 15)
        
        # ETAPA 1: Login
        try:
            print("🔐 ETAPA 1: Realizando login...")
            driver.get("https://megalinktelecom.hubsoft.com.br/login")
            
            # Campo de email
            email_input = wait.until(EC.presence_of_element_located((By.NAME, "email")))
            email_input.clear()
            email_input.send_keys(usuario)
            time.sleep(1)
            
            # Botão Validar
            validar_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Validar')]")))
            validar_button.click()
            
            # Campo de senha
            password_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password']")))
            password_input.clear()
            password_input.send_keys(senha)
            time.sleep(1)
            
            # Botão Entrar
            entrar_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Entrar')]")))
            entrar_button.click()
            
            time.sleep(5)
            
            processor.salvar_prospecto(nome_filtro, id_prospecto, "LOGIN_REALIZADO")
            print("✅ ETAPA 1: Login realizado com sucesso")
            
        except Exception as e:
            erro_detalhado = f"ETAPA 1 - ERRO LOGIN: {str(e)}"
            print(f"❌ {erro_detalhado}")
            processor.capturar_screenshot_erro(driver, "login", "ETAPA1")
            processor.salvar_prospecto(nome_filtro, id_prospecto, "ERRO_LOGIN", erro_detalhado)
            raise
        
        # ETAPA 2: Navegação para Prospectos
        try:
            print("🧭 ETAPA 2: Navegando para prospectos...")
            # Expandir menu Cliente
            cliente_arrow = wait.until(EC.element_to_be_clickable((By.XPATH, "//i[contains(@class, 'icon-chevron-right') and contains(@class, 'arrow')]")))
            cliente_arrow.click()
            time.sleep(1)
            
            # Clicar em Prospectos
            prospectos_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[@class='title ng-scope ng-binding flex' and contains(text(), 'Prospectos')]//parent::a")))
            prospectos_link.click()
            time.sleep(3)
            
            processor.salvar_prospecto(nome_filtro, id_prospecto, "NAVEGACAO_PROSPECTOS")
            print("✅ ETAPA 2: Navegação concluída com sucesso")
            
        except Exception as e:
            erro_detalhado = f"ETAPA 2 - ERRO NAVEGAÇÃO: {str(e)}"
            print(f"❌ {erro_detalhado}")
            processor.capturar_screenshot_erro(driver, "navegacao", "ETAPA2")
            processor.salvar_prospecto(nome_filtro, id_prospecto, "ERRO_NAVEGACAO", erro_detalhado)
            raise
        
        # ETAPA 3: Filtrar e localizar prospecto
        try:
            print("🔍 ETAPA 3: Localizando prospecto...")
            # Localizar tabela
            tabela = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.dataTable.row-border.hover")))
            
            # Filtrar por nome
            campo_busca = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[ng-model='vm.filtros.busca']")))
            campo_busca.clear()
            campo_busca.send_keys(nome_filtro)
            campo_busca.send_keys(Keys.ENTER)
            time.sleep(2)
            
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
            
            processor.salvar_prospecto(nome_filtro, id_prospecto, "PROSPECTO_LOCALIZADO")
            print("✅ ETAPA 3: Prospecto localizado com sucesso")
            
        except Exception as e:
            erro_detalhado = f"ETAPA 3 - ERRO LOCALIZAÇÃO PROSPECTO: {str(e)}"
            print(f"❌ {erro_detalhado}")
            processor.capturar_screenshot_erro(driver, "localizacao", "ETAPA3")
            processor.salvar_prospecto(nome_filtro, id_prospecto, "ERRO_LOCALIZACAO", erro_detalhado)
            raise
        
        # ETAPA 4: Clicar no botão de Ações
        try:
            print("⚙️ ETAPA 4: Abrindo menu de ações...")
            xpath_acoes = f"//tr[.//td[normalize-space(.)='{id_prospecto}']]/descendant::button[@aria-label='Open menu with custom trigger' and .//span[normalize-space(.)='Ações']]"
            acoes_button = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_acoes)))
            
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", acoes_button)
            time.sleep(1)
            
            acoes_button.click()
            time.sleep(2)
            
            processor.salvar_prospecto(nome_filtro, id_prospecto, "MENU_ACOES_ABERTO")
            print("✅ ETAPA 4: Menu de ações aberto com sucesso")
            
        except Exception as e:
            erro_detalhado = f"ETAPA 4 - ERRO MENU AÇÕES: {str(e)}"
            print(f"❌ {erro_detalhado}")
            processor.capturar_screenshot_erro(driver, "acoes", "ETAPA4")
            processor.salvar_prospecto(nome_filtro, id_prospecto, "ERRO_ACOES", erro_detalhado)
            raise
        
        # ETAPA 5: Converter em Cliente
        try:
            print("🔄 ETAPA 5: Convertendo para cliente...")
            converter_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[@style='color:green' and contains(text(), 'Converter em Cliente')]")))
            driver.execute_script("arguments[0].click();", converter_button)
            time.sleep(3)
            
            processor.salvar_prospecto(nome_filtro, id_prospecto, "WIZARD_INICIADO")
            print("✅ ETAPA 5: Wizard de conversão iniciado com sucesso")
            
        except Exception as e:
            erro_detalhado = f"ETAPA 5 - ERRO CONVERSÃO: {str(e)}"
            print(f"❌ {erro_detalhado}")
            processor.capturar_screenshot_erro(driver, "converter", "ETAPA5")
            processor.salvar_prospecto(nome_filtro, id_prospecto, "ERRO_CONVERTER", erro_detalhado)
            raise
        
        # ETAPA 6: Wizard - Primeira tela
        try:
            print("📋 ETAPA 6: Preenchendo wizard (1/4)...")
            # Primeiro botão
            primeiro_botao = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[5]/md-dialog/md-dialog-content/div/hubsoft-cliente-wizard/div[2]/md-dialog-actions/div[2]/button")))
            driver.execute_script("arguments[0].click();", primeiro_botao)
            time.sleep(2)
            
            # Segundo botão
            segundo_botao = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[5]/md-dialog/md-dialog-content/div/hubsoft-cliente-wizard/div[2]/md-dialog-actions/div[2]/button")))
            driver.execute_script("arguments[0].click();", segundo_botao)
            time.sleep(3)
            
            processor.salvar_prospecto(nome_filtro, id_prospecto, "WIZARD_TELA1")
            print("✅ ETAPA 6: Primeira tela do wizard concluída com sucesso")
            
        except Exception as e:
            erro_detalhado = f"ETAPA 6 - ERRO WIZARD TELA 1: {str(e)}"
            print(f"❌ {erro_detalhado}")
            processor.capturar_screenshot_erro(driver, "wizard1", "ETAPA6")
            processor.salvar_prospecto(nome_filtro, id_prospecto, "ERRO_WIZARD1", erro_detalhado)
            raise
        
        # ETAPA 7: Wizard - Seleções
        try:
            print("📝 ETAPA 7: Preenchendo wizard (2/4)...")
            # Primeiro md-select
            md_select1 = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[5]/md-dialog/md-dialog-content/div/hubsoft-cliente-wizard/div[1]/div/div/form/div/md-input-container/md-select")))
            driver.execute_script("arguments[0].click();", md_select1)
            time.sleep(1)
            
            md_option1 = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[7]/md-select-menu/md-content/md-option")))
            driver.execute_script("arguments[0].click();", md_option1)
            time.sleep(1)
            
            # Segundo md-select
            md_select2 = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[5]/md-dialog/md-dialog-content/div/hubsoft-cliente-wizard/div[1]/div/div/form/div/div[2]/md-input-container[2]/md-select")))
            driver.execute_script("arguments[0].click();", md_select2)
            time.sleep(1)
            
            opcao_25 = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[8]/md-select-menu/md-content/md-option[25]")))
            driver.execute_script("arguments[0].click();", opcao_25)
            time.sleep(1)
            
            # Avançar
            botao_avancar = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[5]/md-dialog/md-dialog-content/div/hubsoft-cliente-wizard/div[2]/md-dialog-actions/div[2]/button")))
            driver.execute_script("arguments[0].click();", botao_avancar)
            time.sleep(2)
            
            processor.salvar_prospecto(nome_filtro, id_prospecto, "WIZARD_SELECOES")
            print("✅ ETAPA 7: Seleções do wizard concluídas com sucesso")
            
        except Exception as e:
            erro_detalhado = f"ETAPA 7 - ERRO WIZARD SELEÇÕES: {str(e)}"
            print(f"❌ {erro_detalhado}")
            processor.capturar_screenshot_erro(driver, "wizard_selecoes", "ETAPA7")
            processor.salvar_prospecto(nome_filtro, id_prospecto, "ERRO_WIZARD_SELECOES", erro_detalhado)
            raise
        
        # ETAPA 8: Wizard - Próxima tela
        try:
            print("📋 ETAPA 8: Preenchendo wizard (3/4)...")
            # Próximo botão
            proximo_botao = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[5]/md-dialog/md-dialog-content/div/hubsoft-cliente-wizard/div[2]/md-dialog-actions/div[2]/button")))
            driver.execute_script("arguments[0].click();", proximo_botao)
            time.sleep(3)
            
            # Novo md-select
            novo_md_select = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[5]/md-dialog/md-dialog-content/div/hubsoft-cliente-wizard/div[1]/div/form/div[1]/div/md-input-container[1]/md-select")))
            driver.execute_script("arguments[0].click();", novo_md_select)
            time.sleep(1)
            
            primeira_opcao = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[7]/md-select-menu/md-content/md-option[1]")))
            driver.execute_script("arguments[0].click();", primeira_opcao)
            time.sleep(2)
            
            processor.salvar_prospecto(nome_filtro, id_prospecto, "WIZARD_TELA2")
            print("✅ ETAPA 8: Terceira tela do wizard concluída com sucesso")
            
        except Exception as e:
            erro_detalhado = f"ETAPA 8 - ERRO WIZARD TELA 2: {str(e)}"
            print(f"❌ {erro_detalhado}")
            processor.capturar_screenshot_erro(driver, "wizard2", "ETAPA8")
            processor.salvar_prospecto(nome_filtro, id_prospecto, "ERRO_WIZARD2", erro_detalhado)
            raise
        
        # ETAPA 9: Finalização
        try:
            print("💾 ETAPA 9: Finalizando (4/4)...")
            # Primeiro botão final
            primeiro_final = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[5]/md-dialog/md-dialog-content/div/hubsoft-cliente-wizard/div[2]/md-dialog-actions/div[2]/button")))
            driver.execute_script("arguments[0].click();", primeiro_final)
            time.sleep(2)
            
            # Segundo botão final
            segundo_final = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[5]/md-dialog/md-dialog-content/div/hubsoft-cliente-wizard/div[2]/md-dialog-actions/div[2]/button")))
            driver.execute_script("arguments[0].click();", segundo_final)
            time.sleep(2)
            
            # Botão SALVAR
            botao_salvar = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[5]/md-dialog/md-dialog-content/div/hubsoft-cliente-wizard/div[2]/md-dialog-actions/div[2]/div/button")))
            driver.execute_script("arguments[0].click();", botao_salvar)
            time.sleep(3)
            
            processor.salvar_prospecto(nome_filtro, id_prospecto, "CONCLUIDO", None, "sucesso")
            
            tempo_total = int(time.time() - processor.start_time)
            print(f"🎉 ETAPA 9: SUCESSO! Prospecto convertido em {tempo_total}s")
            
        except Exception as e:
            erro_detalhado = f"ETAPA 9 - ERRO FINALIZAÇÃO: {str(e)}"
            print(f"❌ {erro_detalhado}")
            processor.capturar_screenshot_erro(driver, "finalizacao", "ETAPA9")
            processor.salvar_prospecto(nome_filtro, id_prospecto, "ERRO_FINALIZACAO", erro_detalhado)
            raise
        
    except Exception as e:
        erro_detalhado = f"ERRO GERAL DO PROCESSO: {str(e)}"
        logger.error(erro_detalhado)
        print(f"❌ {erro_detalhado}")
        if processor.current_prospecto_id:
            processor.salvar_prospecto(nome_filtro, id_prospecto, "ERRO_GERAL", erro_detalhado, "falha")
        if driver:
            processor.capturar_screenshot_erro(driver, "erro_geral", "GERAL")
    finally:
        if driver:
            driver.quit()
        if temp_dir:
            shutil.rmtree(temp_dir)
        processor.desconectar_banco()
        print("🔌 Desconectado do banco")

#if __name__ == "__main__":
#    main("JOÃO SILVA SANTOS", "1518")