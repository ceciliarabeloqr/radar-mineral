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
    # Garante que as colunas existam
    if 'resumo' not in hist.columns: hist['resumo'] = 'Pendente'
    if 'keywords' not in hist.columns: hist['keywords'] = ''
else:
    hist = pd.DataFrame(columns=['site', 'titulo', 'link', 'data_extracao', 'resumo', 'keywords'])

# 3. Varredura de Novas Notícias
print("🔎 Buscando novidades nos portais...")
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
                    if link not in hist['link'].values:
                        novas_encontradas.append({'site': fonte['nome'], 'titulo': titulo, 'link': link, 'resumo': 'Pendente', 'keywords': '', 'data_extracao': datetime.now().strftime('%d/%m/%Y')})
    except: continue

# 4. CRIAÇÃO DA FILA (Prioridade Total aos Pendentes)
df_novas = pd.DataFrame(novas_encontradas)
# Unimos o que já tínhamos no CSV com as novas que acabamos de achar
df_total = pd.concat([df_novas, hist]).drop_duplicates(subset='link')

# Selecionamos APENAS as que ainda não têm resumo (as de 13/03 e ontem estão aqui!)
fila_pendentes = df_total[df_total['resumo'] == 'Pendente'].head(20)
ja_prontas = df_total[df_total['resumo'] != 'Pendente']

print(f"📈 Total na fila de processamento: {len(df_total[df_total['resumo'] == 'Pendente'])} matérias.")

processadas_agora = []
if not fila_pendentes.empty:
    print(f"⚡ Processando lote de {len(fila_pendentes)} resumos...")
    for i, n in fila_pendentes.iterrows():
        try:
            print(f"Resumindo: {n['titulo'][:50]}...")
            art = requests.get(n['link'], headers=headers, timeout=15)
            s_art = BeautifulSoup(art.text, 'html.parser')
            texto = " ".join([p.get_text() for p in s_art.find_all('p')])
            
            if len(texto) > 300:
                prompt = f"Como geólogo especialista, resuma tecnicamente em 1 parágrafo e extraia 3 keywords com # ao final. Texto: {texto[:4000]}"
                resposta = modelo.generate_content(prompt).text.strip()
                partes = resposta.split('#')
                n['resumo'] = partes[0].strip()
                n['keywords'] = "#" + " #".join([p.strip() for p in partes[1:]]) if len(partes) > 1 else ""
                processadas_agora.append(n)
                time.sleep(25) # Pausa obrigatória para não dar erro 429
            else:
                n['resumo'] = 'Conteúdo insuficiente para resumo.'
                processadas_agora.append(n)
        except:
            print(f"❌ Falha temporária em: {n['titulo'][:30]}")
            processadas_agora.append(n) # Mantém como pendente para a próxima

# 5. Salvar e Gerar HTML
df_final = pd.concat([pd.DataFrame(processadas_agora), df_total[~df_total['link'].isin(fila_pendentes['link'])]]).drop_duplicates(subset='link')
df_final.to_csv(arquivo_hist, index=False, encoding='utf-8-sig')

# SÓ GERA O HTML COM O QUE TEM RESUMO DE VERDADE
df_exibir = df_final[~df_final['resumo'].isin(['Pendente', 'Falha ao processar.'])].head(100)

if not df_exibir.empty:
    print("🎨 Atualizando painel visual...")
    datas = df_exibir['data_extracao'].unique()
    opcoes_datas = "".join([f'<option value="{d}">{d}</option>' for d in sorted(datas, reverse=True)])
    cards_html = ""
    for _, r in df_exibir.iterrows():
        cards_html += f"""<div class="card" data-date="{r['data_extracao']}"><div class="tags"><span class="site-tag">{r['site']}</span><span class="date-tag">{r['data_extracao']}</span></div><h3>{r['titulo']}</h3><p>{r['resumo']}</p><div class="keywords">{r['keywords']}</div><a href="{r['link']}" target="_blank" class="btn">Ler Matéria</a></div>"""
    
    # [O restante do seu código HTML template aqui...]
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><title>Radar Mineral</title><style>body{{font-family:'Segoe UI',sans-serif;background:#f0f2f5;padding:20px}}.container{{max-width:1000px;margin:auto}}h1{{text-align:center;color:#1a3a5a;border-bottom:5px solid #d4af37;padding-bottom:10px}}.filters{{background:#fff;padding:20px;border-radius:12px;display:flex;gap:15px;margin-bottom:25px;box-shadow:0 4px 6px rgba(0,0,0,0.1)}}input,select{{padding:12px;border:1px solid #ddd;border-radius:8px;flex:1}}.card{{background:#fff;padding:25px;border-radius:12px;margin-bottom:20px;border-left:8px solid #d4af37;box-shadow:0 4px 8px rgba(0,0,0,0.05)}}.site-tag{{background:#1a3a5a;color:#fff;padding:4px 10px;border-radius:4px;font-size:11px}}.date-tag{{background:#7f8c8d;color:#fff;padding:4px 10px;border-radius:4px;font-size:11px;margin-left:8px}}.keywords{{color:#d4af37;font-weight:bold;margin-top:10px}}.btn{{display:inline-block;margin-top:15px;padding:10px 18px;background:#27ae60;color:#fff;text-decoration:none;border-radius:6px;font-weight:bold}}</style></head><body><div class="container"><h1>⛏️ Radar Mineral - Cecília Rabelo</h1><div class="filters"><input type="text" id="busca" placeholder="🔍 Pesquisar..." onkeyup="filtrar()"><select id="filtroData" onchange="filtrar()"><option value="">📅 Todas as Datas</option>{opcoes_datas}</select></div><div id="lista">{cards_html}</div></div><script>function filtrar(){{let b=document.getElementById('busca').value.toLowerCase();let d=document.getElementById('filtroData').value;let cards=document.getElementsByClassName('card');for(let c of cards){{let t=c.innerText.toLowerCase();let dt=c.getAttribute('data-date');c.style.display=(t.includes(b)&&(d===""||dt===d))?"block":"none"}}}}</script></body></html>""")
    </script>
</body>
</html>"""

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html_template)
