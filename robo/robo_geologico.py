import pandas as pd
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import time
import os
from datetime import datetime

# Configuração da IA (O GitHub vai ler a chave do 'Cofre' de Secrets)
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=GOOGLE_API_KEY)
modelo = genai.GenerativeModel('gemini-2.5-flash')

# Configurações de Busca
fontes = [
    {'nome': 'Agência iNFRA', 'url': 'https://agenciainfra.com/blog/', 'filtrar': True},
    {'nome': 'In The Mine', 'url': 'https://www.inthemine.com.br/site/', 'filtrar': False}
]

palavras_chave = ['mineração', 'minério', 'anm', 'mme', 'geologia', 'barragem', 'garimpo', 'jazida', 'cobre', 'ouro', 'ferro', 'lítio']
termos_sujos = ['assine', 'nesta edição', 'infra em 1 minuto', 'expediente', 'contato', 'anuncie', 'podcast']

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

def limpar_texto(t):
    return " ".join(t.split())

# 1. BUSCA DE NOTÍCIAS
print("🔎 Buscando matérias atualizadas...")
novas_noticias = []
for fonte in fontes:
    try:
        res = requests.get(fonte['url'], headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        for a in soup.find_all('a'):
            titulo = limpar_texto(a.get_text())
            link = a.get('href')
            
            # Validação de Título Limpo
            if len(titulo) > 25 and link and link.startswith('http'):
                titulo_lower = titulo.lower()
                if not any(sujo in titulo_lower for sujo in termos_sujos):
                    if not fonte['filtrar'] or any(p in titulo_lower for p in palavras_chave):
                        if not any(n['link'] == link for n in novas_noticias):
                            novas_noticias.append({'site': fonte['nome'], 'titulo': titulo, 'link': link})
    except: pass

# 2. PROCESSAMENTO COM IA (EVITANDO ERRO 429)
arquivo_hist = 'historico_noticias.csv'
if os.path.exists(arquivo_hist):
    hist = pd.read_csv(arquivo_hist)
else:
    hist = pd.DataFrame(columns=['site', 'titulo', 'link', 'data_extracao', 'resumo'])

noticias_para_resumir = [n for n in novas_noticias if n['link'] not in hist['link'].values]

print(f"⚡ {len(noticias_para_resumir)} novas matérias encontradas!")

novos_dados = []
for n in noticias_para_resumir[:15]: # Processa 15 por vez para não travar a cota
    try:
        print(f"Resumindo: {n['titulo'][:50]}...")
        artigo = requests.get(n['link'], headers=headers, timeout=15)
        s_art = BeautifulSoup(artigo.text, 'html.parser')
        corpo = " ".join([p.get_text() for p in s_art.find_all('p')])
        
        if len(corpo) > 200:
            resumo = modelo.generate_content(f"Resuma para um geólogo em 1 parágrafo: {corpo[:4000]}").text.strip()
            novos_dados.append({**n, 'data_extracao': datetime.now().strftime('%d/%m/%Y'), 'resumo': resumo})
            time.sleep(15) # Pausa estratégica anti-429
    except: continue

# 3. ATUALIZAÇÃO DOS ARQUIVOS
if novos_dados:
    df_atualizado = pd.concat([pd.DataFrame(novos_dados), hist]).head(100) # Mantém as últimas 100
    df_atualizado.to_csv(arquivo_hist, index=False, encoding='utf-8-sig')

# (O script gera o index.html automaticamente após atualizar o CSV)
# [Aqui você colaria o código de geração do HTML que te mandei antes]
