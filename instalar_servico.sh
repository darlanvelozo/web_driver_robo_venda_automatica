#!/bin/bash

echo "🚀 Instalando serviço de Gestão de Leads..."

# Verificar se está rodando como root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Este script precisa ser executado como root (usar sudo)"
    exit 1
fi

# Copiar arquivo de serviço para diretório do systemd
echo "📁 Copiando arquivo de serviço..."
cp gestao_leads_bot.service /etc/systemd/system/

# Recarregar configurações do systemd
echo "🔄 Recarregando configurações do systemd..."
systemctl daemon-reload

# Habilitar o serviço para iniciar automaticamente
echo "✅ Habilitando serviço para iniciar automaticamente..."
systemctl enable gestao_leads_bot.service

# Iniciar o serviço
echo "🚀 Iniciando serviço..."
systemctl start gestao_leads_bot.service

# Verificar status
echo "📊 Status do serviço:"
systemctl status gestao_leads_bot.service --no-pager -l

echo ""
echo "✅ Instalação concluída!"
echo ""
echo "📋 Comandos úteis:"
echo "   - Ver status: sudo systemctl status gestao_leads_bot"
echo "   - Ver logs: sudo journalctl -u gestao_leads_bot -f"
echo "   - Parar serviço: sudo systemctl stop gestao_leads_bot"
echo "   - Reiniciar serviço: sudo systemctl restart gestao_leads_bot"
echo "   - Desabilitar serviço: sudo systemctl disable gestao_leads_bot"
echo "" 