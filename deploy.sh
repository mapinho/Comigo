#!/bin/bash
cd /opt/comigo

echo "--- Buscando atualizações no GitHub ---"
git pull origin main # ou master, dependendo da sua branch padrão

echo "--- Reiniciando os Containers (Streamlit & MCP Server) ---"
sudo docker compose down
sudo docker compose up -d --build

echo "--- Deploy finalizado com sucesso! ---"
