import pandas as pd
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import time
import os
import re
from datetime import datetime

# Configuração da IA
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=GOOGLE_API_KEY)
modelo = genai.GenerativeModel('gemini-2.5-flash')

# 1. Configurações de Busca e Filtros
fontes = [
    {'nome': 'Agência iNFRA', 'url': 'https://agenciainfra.com/blog/', 'filtrar': True},
    {'nome': 'In The Mine', 'url': 'https://www.inthemine.com.br/site/', 'filtrar': False}
]

palavras_chave = ['mineração', 'minério', 'anm', 'mme', 'geologia', 'barragem', 'jazida', 'cobre', 'ouro', 'ferro', 'lítio', 'minerais']
# LISTA NEGRA: Remove e-mails, redes sociais e botões
termos_sujos = ['@', 'facebook', 'instagram', 'twitter', 'linkedin', 'whatsapp', 'assine', 'contato', 'anuncie', 'expediente', 'leia mais', 'clique aqui']

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

def titulo_valido(t):
    t_clean = t.strip().lower()
    # Rejeita se for muito curto, muito longo ou tiver termos sujos
    if len(t_clean) < 30 or len(t_clean) > 150: return False
    if any(sujo in t_clean for sujo in termos_sujos): return False
    # Rejeita se parecer um e-mail
    if re.search(r'[\w\.-]+@[\w\.-]+', t_clean): return False
    return True

# 2. COLETA DE DADOS
print("🔎 Iniciando coleta limpa...")
novas = []
for fonte in fontes:
    try:
        res = requests.get(fonte['url'], headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        for a in soup.find_all('a'):
            titulo = " ".join(a.get_text().split())
            link = a.get('href')
            if titulo_valido(titulo) and link and link.startswith('http'):
                if not fonte['filtrar'] or any(p in titulo.lower() for p in palavras_chave):
                    if not any(n['link'] == link for n in novas):
                        novas.append({'site': fonte['nome'], 'titulo': titulo, 'link': link})
    except: continue

# 3. RESUMOS COM IA
arquivo_hist = 'historico_noticias.csv'
if os.path.exists(arquivo_hist):
    hist = pd.read_csv(arquivo_hist)
else:
    hist = pd.DataFrame(columns=['site', 'titulo', 'link', 'data_extracao', 'resumo'])

noticias_para_processar = [n for n in novas if n['link'] not in hist['link'].values][:10] # 10 por vez

print(f"⚡ Processando {len(noticias_para_processar)} novas matérias...")
novos_dados = []
for n in noticias_para_processar:
    try:
        print(f"Lendo: {n['titulo'][:50]}...")
        art = requests.get(n['link'], headers=headers, timeout=15)
        s_art = BeautifulSoup(art.text, 'html.parser')
        # Pega o texto dos parágrafos
        texto = " ".join([p.get_text() for p in s_art.find_all('p')])
        
        if len(texto) > 300:
            prompt = f"Como um especialista em geologia, resuma esta notícia em 1 parágrafo técnico. Se houver minerais citados, destaque-os. Texto: {texto[:4000]}"
            resumo = modelo.generate_content(prompt).text.strip()
            novos_dados.append({**n, 'data_extracao': datetime.now().strftime('%d/%m/%Y'), 'resumo': resumo})
            time.sleep(15) # Pausa estratégica
    except: continue

# 4. SALVAR E GERAR HTML
if novos_dados:
    df_final = pd.concat([pd.DataFrame(novos_dados), hist]).head(50)
    df_final.to_csv(arquivo_hist, index=False, encoding='utf-8-sig')

    # GERADOR DE HTML (DENTRO DO PYTHON PARA ATUALIZAR SOZINHO)
    datas = df_final['data_extracao'].unique()
    opcoes = "".join([f'<option value="{d}">{d}</option>' for d in datas])
    
    html = f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><title>Radar Mineral</title><style>body{{font-family:sans-serif;background:#f4f4f4;padding:20px}}.card{{background:#fff;padding:15px;margin-bottom:15px;border-radius:8px;border-left:5px solid #d4af37}}h1{{color:#2c3e50}}</style></head><body><h1>⚒️ Radar Mineral - Cecília Rabelo</h1><div id="lista">"""
    for _, r in df_final.iterrows():
        html += f"""<div class="card"><strong>{r['site']}</strong> | {r['data_extracao']}<h3>{r['titulo']}</h3><p>{r['resumo']}</p><a href="{r['link']}" target="_blank">Ver mais</a></div>"""
    html += "</div></body></html>"
    
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(html)
