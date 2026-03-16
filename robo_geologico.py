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

# Expandimos as palavras-chave para capturar mais notícias
palavras_chave_filtro = ['mineração', 'minério', 'anm', 'mme', 'geologia', 'barragem', 'jazida', 'cobre', 'ouro', 'ferro', 'lítio', 'mineral', 'vale', 'ibram', 'setor mineral', 'esg', 'sustentabilidade']
termos_sujos = ['@', 'facebook', 'instagram', 'twitter', 'linkedin', 'whatsapp', 'assine', 'contato', 'anuncie', 'expediente', 'leia mais', 'política de privacidade', 'comentários']

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

def titulo_valido(t):
    t_clean = t.strip().lower()
    if len(t_clean) < 30 or len(t_clean) > 200: return False
    if any(sujo in t_clean for sujo in termos_sujos): return False
    return True

# 2. Carregar e Limpar Histórico
arquivo_hist = 'historico_noticias.csv'
if os.path.exists(arquivo_hist):
    hist = pd.read_csv(arquivo_hist)
    # LIMPEZA: Remove linhas que capturaram lixo (textos de comentários ou privacidade)
    palavras_lixo = ['comunicação descreve', 'política de privacidade', 'akismet', 'submissão de conteúdo']
    hist = hist[~hist['resumo'].str.contains('|'.join(palavras_lixo), case=False, na=False)]
else:
    hist = pd.DataFrame(columns=['site', 'titulo', 'link', 'data_extracao', 'resumo', 'keywords'])

# 3. Varredura de Notícias
print("🔎 Buscando novidades em mineração...")
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
                        novas_encontradas.append({
                            'site': fonte['nome'], 'titulo': titulo, 'link': link, 
                            'resumo': 'Pendente', 'keywords': '', 'data_extracao': datetime.now().strftime('%d/%m/%Y')
                        })
    except: continue

# 4. Processamento da Fila (Até 20 por vez)
df_novas = pd.DataFrame(novas_encontradas)
df_total = pd.concat([df_novas, hist]).drop_duplicates(subset='link')
fila_pendentes = df_total[df_total['resumo'] == 'Pendente'].head(20)
ja_prontas = df_total[df_total['resumo'] != 'Pendente']

print(f"📈 {len(df_total[df_total['resumo'] == 'Pendente'])} notícias aguardando. Processando 20 agora...")

processadas_agora = []
for i, n in fila_pendentes.iterrows():
    try:
        art = requests.get(n['link'], headers=headers, timeout=15)
        s_art = BeautifulSoup(art.text, 'html.parser')
        # Tenta pegar apenas o texto principal da matéria (evitando menus e rodapés)
        paragrafos = s_art.find_all('p')
        texto = " ".join([p.get_text() for p in paragrafos if len(p.get_text()) > 50])
        
        if len(texto) > 400:
            prompt = f"Como geólogo sênior, resuma tecnicamente esta notícia de mineração em 1 parágrafo e adicione 3 #keywords no final. Texto: {texto[:4000]}"
            resposta = modelo.generate_content(prompt).text.strip()
            
            partes = resposta.split('#')
            n['resumo'] = partes[0].strip()
            n['keywords'] = "#" + " #".join([p.strip() for p in partes[1:]]) if len(partes) > 1 else ""
            processadas_agora.append(n)
            print(f"✅ Sucesso: {n['titulo'][:40]}...")
            time.sleep(28) # Pausa segura
        else:
            n['resumo'] = 'Link sem conteúdo textual relevante.'
            processadas_agora.append(n)
    except:
        n['resumo'] = 'Pendente'
        processadas_agora.append(n)

# 5. Salvar e Gerar HTML Final
df_final = pd.concat([pd.DataFrame(processadas_agora), df_total[~df_total['link'].isin(fila_pendentes['link'])]]).drop_duplicates(subset='link')
df_final.to_csv(arquivo_hist, index=False, encoding='utf-8-sig')

# Exibir tudo que tem resumo (limitando às 100 mais recentes para o site não ficar pesado)
df_exibir = df_final[~df_final['resumo'].isin(['Pendente', 'Link sem conteúdo textual relevante.'])].sort_values(by='data_extracao', ascending=False).head(100)

if not df_exibir.empty:
    print(f"🎨 Gerando interface com {len(df_exibir)} notícias...")
    datas = sorted(df_exibir['data_extracao'].unique(), reverse=True)
    opcoes_datas = "".join([f'<option value="{d}">{d}</option>' for d in datas])
    
    cards_html = ""
    for _, r in df_exibir.iterrows():
        cards_html += f"""
        <div class="card" data-date="{r['data_extracao']}">
            <div class="tags"><span class="site-tag">{r['site']}</span><span class="date-tag">{r['data_extracao']}</span></div>
            <h3>{r['titulo']}</h3>
            <p>{r['resumo']}</p>
            <div class="keywords">{r['keywords']}</div>
            <a href="{r['link']}" target="_blank" class="btn">Ler Matéria Completa</a>
        </div>"""

    # Template HTML completo (com busca e data)
    html_template = f"""
    <!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><title>Radar Mineral</title><style>
    body{{font-family:'Segoe UI',sans-serif;background:#f0f2f5;margin:0;padding:20px}}.container{{max-width:1000px;margin:auto}}
    h1{{text-align:center;color:#1a3a5a;border-bottom:5px solid #d4af37;padding-bottom:10px}}
    .filters{{background:#fff;padding:20px;border-radius:12px;display:flex;gap:15px;margin-bottom:25px;box-shadow:0 4px 6px rgba(0,0,0,0.1)}}
    input,select{{padding:12px;border:1px solid #ddd;border-radius:8px;flex:1}}
    .card{{background:#fff;padding:25px;border-radius:12px;margin-bottom:20px;border-left:8px solid #d4af37;box-shadow:0 4px 8px rgba(0,0,0,0.05)}}
    .site-tag{{background:#1a3a5a;color:#fff;padding:4px 10px;border-radius:4px;font-size:11px}}
    .date-tag{{background:#7f8c8d;color:#fff;padding:4px 10px;border-radius:4px;font-size:11px;margin-left:8px}}
    .keywords{{color:#d4af37;font-weight:bold;margin-top:10px}}.btn{{display:inline-block;margin-top:15px;padding:10px 18px;background:#27ae60;color:#fff;text-decoration:none;border-radius:6px;font-weight:bold}}
    </style></head><body><div class="container"><h1>⛏️ Radar Mineral - Cecília Rabelo</h1><div class="filters">
    <input type="text" id="busca" placeholder="🔍 Pesquisar notícia ou #tag..." onkeyup="filtrar()"><select id="filtroData" onchange="filtrar()">
    <option value="">📅 Todas as Datas</option>{opcoes_datas}</select></div><div id="lista">{cards_html}</div></div><script>
    function filtrar(){{let b=document.getElementById('busca').value.toLowerCase();let d=document.getElementById('filtroData').value;let cards=document.getElementsByClassName('card');
    for(let c of cards){{let t=c.innerText.toLowerCase();let dt=c.getAttribute('data-date');c.style.display=(t.includes(b)&&(d===""||dt===d))?"block":"none"}}}}</script></body></html>"""
    
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(html_template)
