#!/bin/bash

echo "Instalando Google Chrome e dependências..."

# Atualizar repositórios
echo "1. Atualizando repositórios..."
sudo apt update

# Instalar dependências necessárias
echo "2. Instalando dependências do sistema..."
sudo apt install -y wget curl unzip

# Adicionar repositório do Google Chrome
echo "3. Adicionando repositório do Google Chrome..."
wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
sudo sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'

# Atualizar novamente após adicionar o repositório
echo "4. Atualizando repositórios novamente..."
sudo apt update

# Instalar Google Chrome
echo "5. Instalando Google Chrome..."
sudo apt install -y google-chrome-stable

# Instalar outras dependências que podem ser necessárias
echo "6. Instalando bibliotecas adicionais..."
sudo apt install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libgtk-3-0 \
    libasound2

# Verificar instalação
echo "7. Verificando instalação..."
if command -v google-chrome &> /dev/null; then
    echo "Google Chrome instalado com sucesso!"
    google-chrome --version
else
    echo "Erro na instalação do Google Chrome"
fi

echo "Instalação concluída!" 