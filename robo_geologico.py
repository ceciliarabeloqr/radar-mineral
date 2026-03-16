import pandas as pd
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import time
import os
import re
from datetime import datetime

# 1. Configuração da IA
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=GOOGLE_API_KEY)
modelo = genai.GenerativeModel('gemini-2.5-flash')

fontes = [
    {'nome': 'Agência iNFRA', 'url': 'https://agenciainfra.com/blog/', 'filtrar': True},
    {'nome': 'In The Mine', 'url': 'https://www.inthemine.com.br/site/', 'filtrar': False}
]

palavras_chave_filtro = ['mineração', 'minério', 'anm', 'mme', 'geologia', 'barragem', 'jazida', 'cobre', 'ouro', 'ferro', 'lítio', 'mineral', 'vale']
termos_sujos = ['@', 'facebook', 'instagram', 'twitter', 'linkedin', 'whatsapp', 'assine', 'contato', 'anuncie', 'expediente', 'leia mais']

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

# 2. Carregar Histórico
arquivo_hist = 'historico_noticias.csv'
if os.path.exists(arquivo_hist):
    hist = pd.read_csv(arquivo_hist)
else:
    hist = pd.DataFrame(columns=['site', 'titulo', 'link', 'data_extracao', 'resumo', 'keywords'])

# 3. Coleta de Links (Pega TUDO, mas não resume tudo de uma vez)
novas_encontradas = []
for fonte in fontes:
    try:
        res = requests.get(fonte['url'], headers=headers, timeout=20)
        soup = BeautifulSoup(res.text, 'html.parser')
        for a in soup.find_all('a'):
            titulo = " ".join(a.get_text().split())
            link = a.get('href')
            if len(titulo) > 25 and link and link.startswith('http'):
                if not fonte['filtrar'] or any(p in titulo.lower() for p in palavras_chave_filtro):
                    if link not in hist['link'].values and not any(n['link'] == link for n in novas_encontradas):
                        novas_encontradas.append({'site': fonte['nome'], 'titulo': titulo, 'link': link, 'resumo': 'Pendente', 'keywords': ''})
    except: continue

# 4. FILA INTELIGENTE (O segredo do sucesso)
# Junta as novas encontradas com as que ficaram pendentes de ontem
pendentes = pd.concat([pd.DataFrame(novas_encontradas), hist[hist['resumo'] == 'Pendente']])
ja_prontas = hist[hist['resumo'] != 'Pendente']

# Processamos apenas 15 por rodada para GARANTIR que não haverá erro 429
fatiar_processamento = pendentes.head(15)
restante_pendente = pendentes.iloc[15:]

print(f"🚀 Iniciando processamento de 15 notícias de um total de {len(pendentes)} pendentes.")

processadas_agora = []
for i, n in fatiar_processamento.iterrows():
    try:
        art = requests.get(n['link'], headers=headers, timeout=15)
        s_art = BeautifulSoup(art.text, 'html.parser')
        texto = " ".join([p.get_text() for p in s_art.find_all('p')])
        
        if len(texto) > 300:
            prompt = f"Como geólogo, resuma em 1 parágrafo técnico e extraia 3 keywords com # ao final. Texto: {texto[:4000]}"
            resposta = modelo.generate_content(prompt).text.strip()
            
            partes = resposta.split('#')
            n['resumo'] = partes[0].strip()
            n['keywords'] = "#" + " #".join([p.strip() for p in partes[1:]]) if len(partes) > 1 else ""
            n['data_extracao'] = datetime.now().strftime('%d/%m/%Y')
            processadas_agora.append(n)
            print(f"✅ Sucesso: {n['titulo'][:30]}")
            time.sleep(35) # PAUSA DE SEGURANÇA TOTAL
    except:
        n['resumo'] = 'Pendente' # Se der erro em uma, ela volta para a fila
        processadas_agora.append(n)

# 5. Salvar TUDO (Une as novas processadas, as que ainda faltam e as antigas)
df_final = pd.concat([pd.DataFrame(processadas_agora), restante_pendente, ja_prontas]).drop_duplicates(subset='link')
df_final.to_csv(arquivo_hist, index=False, encoding='utf-8-sig')

# 6. Gerar o HTML (Mesmo código de interface com busca e data)
# ... (Mantém a mesma lógica de geração do index.html que te mandei antes) ...
