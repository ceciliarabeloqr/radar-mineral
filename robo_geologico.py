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

palavras_chave_filtro = ['mineração', 'minério', 'anm', 'mme', 'geologia', 'barragem', 'jazida', 'cobre', 'ouro', 'ferro', 'lítio', 'mineral', 'vale', 'itaboraí', 'serra leste']
termos_sujos = ['@', 'facebook', 'instagram', 'twitter', 'linkedin', 'whatsapp', 'assine', 'contato', 'anuncie', 'expediente', 'leia mais', 'clique aqui', 'infra em 1 minuto', 'nesta edição']

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

def titulo_valido(t):
    t_clean = t.strip().lower()
    if len(t_clean) < 25 or len(t_clean) > 180: return False
    if any(sujo in t_clean for sujo in termos_sujos): return False
    if re.search(r'[\w\.-]+@[\w\.-]+', t_clean): return False
    return True

# 2. Carregar Histórico
arquivo_hist = 'historico_noticias.csv'
if os.path.exists(arquivo_hist):
    hist = pd.read_csv(arquivo_hist)
else:
    hist = pd.DataFrame(columns=['site', 'titulo', 'link', 'data_extracao', 'resumo', 'keywords'])

# 3. Coleta de TUDO (Série Histórica)
print("🔎 Varrendo portais de mineração...")
novas_encontradas = []
for fonte in fontes:
    try:
        res = requests.get(fonte['url'], headers=headers, timeout=20)
        soup = BeautifulSoup(res.text, 'html.parser')
        for a in soup.find_all('a'):
            titulo = " ".join(a.get_text().split())
            link = a.get('href')
            if titulo_valido(titulo) and link and link.startswith('http'):
                if not fonte['filtrar'] or any(p in titulo.lower() for p in palavras_chave_filtro):
                    if link not in hist['link'].values and not any(n['link'] == link for n in novas_encontradas):
                        novas_encontradas.append({'site': fonte['nome'], 'titulo': titulo, 'link': link, 'resumo': 'Pendente', 'keywords': ''})
    except: continue

# 4. Processamento de Resumos (Fila de 50 matérias)
pendentes = pd.concat([pd.DataFrame(novas_encontradas), hist[hist['resumo'] == 'Pendente']])
ja_prontas = hist[hist['resumo'] != 'Pendente']

print(f"📈 {len(pendentes)} matérias aguardando resumo.")
processadas_agora = []

for i, n in pendentes.head(50).iterrows():
    tentativas = 0
    while tentativas < 2:
        try:
            art = requests.get(n['link'], headers=headers, timeout=15)
            s_art = BeautifulSoup(art.text, 'html.parser')
            texto = " ".join([p.get_text() for p in s_art.find_all('p')])
            
            if len(texto) > 300:
                prompt = f"Como geólogo especialista, resuma tecnicamente em 1 parágrafo e extraia 3 keywords com # ao final. Texto: {texto[:4000]}"
                resposta = modelo.generate_content(prompt).text.strip()
                
                partes = resposta.split('#')
                n['resumo'] = partes[0].strip()
                n['keywords'] = "#" + " #".join([p.strip() for p in partes[1:]]) if len(partes) > 1 else ""
                n['data_extracao'] = datetime.now().strftime('%d/%m/%Y')
                processadas_agora.append(n)
                time.sleep(25) # Pausa estratégica ANTI-429
            break
        except Exception as e:
            if "429" in str(e):
                print("⏳ Limite atingido. Pausando 60s...")
                time.sleep(60)
                tentativas += 1
            else: break

# 5. Salvar e Gerar Interface
df_final = pd.concat([pd.DataFrame(processadas_agora), pendentes.iloc[len(processadas_agora):], ja_prontas]).drop_duplicates(subset='link').head(200)
df_final.to_csv(arquivo_hist, index=False, encoding='utf-8-sig')

datas = df_final[df_final['resumo'] != 'Pendente']['data_extracao'].unique()
opcoes_datas = "".join([f'<option value="{d}">{d}</option>' for d in sorted(datas, reverse=True)])

cards_html = ""
for _, r in df_final[df_final['resumo'] != 'Pendente'].iterrows():
    cards_html += f"""
    <div class="card" data-date="{r['data_extracao']}">
        <div class="tags"><span class="site-tag">{r['site']}</span><span class="date-tag">{r['data_extracao']}</span></div>
        <h3>{r['titulo']}</h3>
        <p>{r['resumo']}</p>
        <div class="keywords">{r['keywords']}</div>
        <a href="{r['link']}" target="_blank" class="btn">Ler Matéria</a>
    </div>"""

html_template = f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Radar Mineral | Cecília Rabelo</title>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; background: #f0f2f5; margin: 0; padding: 20px; }}
        .container {{ max-width: 1000px; margin: auto; }}
        h1 {{ text-align: center; color: #1a3a5a; border-bottom: 5px solid #d4af37; padding-bottom: 10px; }}
        .filters {{ background: #fff; padding: 20px; border-radius: 12px; display: flex; gap: 15px; margin-bottom: 25px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
        .filters input, .filters select {{ padding: 12px; border: 1px solid #ddd; border-radius: 8px; flex: 1; }}
        .card {{ background: #fff; padding: 20px; border-radius: 12px; margin-bottom: 20px; border-left: 8px solid #d4af37; box-shadow: 0 4px 8px rgba(0,0,0,0.05); }}
        .site-tag {{ background: #1a3a5a; color: #fff; padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: bold; }}
        .date-tag {{ background: #7f8c8d; color: #fff; padding: 4px 10px; border-radius: 4px; font-size: 11px; margin-left: 8px; }}
        .keywords {{ color: #d4af37; font-weight: bold; margin-top: 10px; }}
        .btn {{ display: inline-block; margin-top: 15px; padding: 10px 18px; background: #27ae60; color: #fff; text-decoration: none; border-radius: 6px; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>⛏️ Radar Mineral - Série Histórica</h1>
        <div class="filters">
            <input type="text" id="busca" placeholder="🔍 Pesquisar notícia ou #tag..." onkeyup="filtrar()">
            <select id="filtroData" onchange="filtrar()">
                <option value="">📅 Todas as Datas</option>
                {opcoes_datas}
            </select>
        </div>
        <div id="lista">{cards_html}</div>
    </div>
    <script>
        function filtrar() {{
            let b = document.getElementById('busca').value.toLowerCase();
            let d = document.getElementById('filtroData').value;
            let cards = document.getElementsByClassName('card');
            for (let c of cards) {{
                let t = c.innerText.toLowerCase();
                let dt = c.getAttribute('data-date');
                c.style.display = (t.includes(b) && (d === "" || dt === d)) ? "block" : "none";
            }}
        }}
    </script>
</body>
</html>"""

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html_template)
