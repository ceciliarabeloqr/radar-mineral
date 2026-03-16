import pandas as pd
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import time
import os
from datetime import datetime

# 1. Configuração da IA
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=GOOGLE_API_KEY)
modelo = genai.GenerativeModel('gemini-2.5-flash')

# 2. Máquina do Tempo: Navegar por múltiplas páginas
paginas_para_buscar = 3 # Lê a capa, página 2 e página 3
fontes = [
    {'nome': 'Agência iNFRA', 'url_base': 'https://agenciainfra.com/blog/page/{}/', 'filtrar': True},
    {'nome': 'In The Mine', 'url_base': 'https://www.inthemine.com.br/site/page/{}/', 'filtrar': False}
]

palavras_chave_filtro = ['mineração', 'minério', 'anm', 'mme', 'geologia', 'barragem', 'jazida', 'cobre', 'ouro', 'ferro', 'lítio', 'mineral', 'vale', 'ibram', 'setor mineral', 'cbpm']
termos_sujos = ['@', 'facebook', 'instagram', 'twitter', 'linkedin', 'whatsapp', 'assine', 'contato', 'anuncie', 'expediente', 'leia mais']
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

# 3. Forçar Correção do Histórico (CSV)
arquivo_hist = 'historico_noticias.csv'
if os.path.exists(arquivo_hist):
    hist = pd.read_csv(arquivo_hist)
    # Se alguma notícia antiga falhou antes, forçamos ela a voltar para a fila
    if 'resumo' in hist.columns:
        hist['resumo'] = hist['resumo'].replace(['Conteúdo insuficiente.', 'Falha', 'Conteúdo insuficiente'], 'Pendente')
        hist['resumo'] = hist['resumo'].fillna('Pendente')
else:
    hist = pd.DataFrame(columns=['site', 'titulo', 'link', 'data_extracao', 'resumo', 'keywords'])

# 4. Busca Profunda (Lendo páginas antigas)
print("🔎 Voltando no tempo: varrendo páginas 1, 2 e 3 dos portais...")
novas = []
for fonte in fontes:
    for pagina in range(1, paginas_para_buscar + 1):
        url = fonte['url_base'].format(pagina)
        if pagina == 1:
            url = url.replace('page/1/', '') # Arruma o link da capa
        
        try:
            res = requests.get(url, headers=headers, timeout=20)
            soup = BeautifulSoup(res.text, 'html.parser')
            for a in soup.find_all('a'):
                titulo = " ".join(a.get_text().split())
                link = a.get('href')
                if len(titulo) > 28 and link and link.startswith('http') and not any(s in titulo.lower() for s in termos_sujos):
                    if not fonte['filtrar'] or any(p in titulo.lower() for p in palavras_chave_filtro):
                        if link not in hist['link'].values and not any(n['link'] == link for n in novas):
                            novas.append({'site': fonte['nome'], 'titulo': titulo, 'link': link, 'resumo': 'Pendente', 'keywords': '', 'data_extracao': datetime.now().strftime('%d/%m/%Y')})
        except: continue

# 5. Fila de Processamento
df_total = pd.concat([pd.DataFrame(novas), hist]).drop_duplicates(subset='link')
fila = df_total[df_total['resumo'] == 'Pendente'].head(15)
prontas = df_total[~df_total['link'].isin(fila['link'])]

print(f"📈 Total na fila: {len(df_total[df_total['resumo'] == 'Pendente'])} notícias antigas e novas. Processando {len(fila)} agora...")

processadas = []
for i, n in fila.iterrows():
    try:
        print(f"Resumindo: {n['titulo'][:50]}...")
        art = requests.get(n['link'], headers=headers, timeout=15)
        s_art = BeautifulSoup(art.text, 'html.parser')
        texto = " ".join([p.get_text() for p in s_art.find_all('p') if len(p.get_text()) > 60])
        
        if len(texto) > 400:
            prompt = f"Como geólogo especialista, resuma tecnicamente esta notícia de mineração em 1 parágrafo e adicione 3 #keywords no final. Texto: {texto[:4000]}"
            resumo_ia = modelo.generate_content(prompt).text.strip()
            partes = resumo_ia.split('#')
            n['resumo'] = partes[0].strip()
            n['keywords'] = "#" + " #".join([p.strip() for p in partes[1:]]) if len(partes) > 1 else ""
            time.sleep(30) # Pausa segura
        else:
            n['resumo'] = 'Ignorado'
        processadas.append(n)
    except Exception as e:
        n['resumo'] = 'Pendente'
        processadas.append(n)

# 6. Salvar e Gerar HTML
df_final = pd.concat([pd.DataFrame(processadas), prontas]).drop_duplicates(subset='link')
df_final.to_csv(arquivo_hist, index=False, encoding='utf-8-sig')

df_exibir = df_final[~df_final['resumo'].isin(['Pendente', 'Ignorado'])].head(100)

if not df_exibir.empty:
    print(f"🎨 Atualizando site com {len(df_exibir)} notícias (incluindo antigas resgatadas).")
    datas = sorted(df_exibir['data_extracao'].unique(), reverse=True)
    opcoes_datas = "".join([f'<option value="{d}">{d}</option>' for d in datas])
    cards_html = ""
    for _, r in df_exibir.iterrows():
        cards_html += f"""<div class="card" data-date="{r['data_extracao']}"><div class="tags"><span class="site-tag">{r['site']}</span><span class="date-tag">{r['data_extracao']}</span></div><h3>{r['titulo']}</h3><p>{r['resumo']}</p><div class="keywords">{r['keywords']}</div><a href="{r['link']}" target="_blank" class="btn">Ler Matéria</a></div>"""
    
    html_template = f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><title>Radar Mineral</title><style>body{{font-family:sans-serif;background:#f0f2f5;padding:20px}}.container{{max-width:1000px;margin:auto}}h1{{text-align:center;color:#1a3a5a;border-bottom:5px solid #d4af37;padding-bottom:10px}}.filters{{background:#fff;padding:20px;border-radius:12px;display:flex;gap:15px;margin-bottom:25px;box-shadow:0 4px 6px rgba(0,0,0,0.1)}}input,select{{padding:12px;border:1px solid #ddd;border-radius:8px;flex:1}}.card{{background:#fff;padding:25px;border-radius:12px;margin-bottom:20px;border-left:8px solid #d4af37;box-shadow:0 4px 8px rgba(0,0,0,0.05)}}.site-tag{{background:#1a3a5a;color:#fff;padding:4px 10px;border-radius:4px;font-size:11px}}.date-tag{{background:#7f8c8d;color:#fff;padding:4px 10px;border-radius:4px;font-size:11px;margin-left:8px}}.keywords{{color:#d4af37;font-weight:bold;margin-top:10px}}.btn{{display:inline-block;margin-top:15px;padding:10px 18px;background:#27ae60;color:#fff;text-decoration:none;border-radius:6px;font-weight:bold}}</style></head><body><div class="container"><h1>⛏️ Radar Mineral - Cecília Rabelo</h1><div class="filters"><input type="text" id="busca" placeholder="🔍 Pesquisar..." onkeyup="filtrar()"><select id="filtroData" onchange="filtrar()"><option value="">📅 Todas as Datas</option>{opcoes_datas}</select></div><div id="lista">{cards_html}</div></div><script>function filtrar(){{let b=document.getElementById('busca').value.toLowerCase();let d=document.getElementById('filtroData').value;let cards=document.getElementsByClassName('card');for(let c of cards){{let t=c.innerText.toLowerCase();let dt=c.getAttribute('data-date');c.style.display=(t.includes(b)&&(d===""||dt===d))?"block":"none"}}}}</script></body></html>"""
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(html_template)
