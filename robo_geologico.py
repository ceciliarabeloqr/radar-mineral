import warnings
# Oculta os avisos assustadores e inúteis do Google e do Python
warnings.filterwarnings("ignore")

import pandas as pd
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import time
import os
from datetime import datetime

print("🚀 A iniciar o Radar Mineral...")
print("✅ Bibliotecas carregadas com sucesso. A configurar a Inteligência Artificial...")

# 1. Configuração da IA 
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=GOOGLE_API_KEY)
modelo = genai.GenerativeModel('gemini-2.5-flash')

# 2. Configurações de Busca
paginas_para_buscar = 5 
fontes = [
    {'nome': 'Agência iNFRA', 'url_base': 'https://agenciainfra.com/blog/page/{}/', 'filtrar': True},
    {'nome': 'In The Mine', 'url_base': 'https://www.inthemine.com.br/site/page/{}/', 'filtrar': False}
]

palavras_chave_filtro = ['mineração', 'minério', 'anm', 'mme', 'geologia', 'barragem', 'jazida', 'cobre', 'ouro', 'ferro', 'lítio', 'mineral', 'vale', 'ibram', 'setor mineral', 'cbpm', 'ferrovia', 'concessão']
termos_sujos = ['@', 'facebook', 'instagram', 'twitter', 'linkedin', 'whatsapp', 'assine', 'contato', 'anuncie', 'expediente', 'leia mais', 'vídeo', 'video', 'tv', 'assista', 'youtube']
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

print("📂 A aceder à base de dados de notícias (CSV)...")
# 3. Forçar Correção do Histórico (CSV)
arquivo_hist = 'historico_noticias.csv'
if os.path.exists(arquivo_hist):
    try:
        hist = pd.read_csv(arquivo_hist)
        if 'resumo' in hist.columns:
            hist['resumo'] = hist['resumo'].replace(['pendente', 'PENDENTE', 'Conteúdo insuficiente.', 'Falha', 'Conteúdo insuficiente', 'Ignorado'], 'Pendente')
            hist['resumo'] = hist['resumo'].fillna('Pendente')
    except:
        hist = pd.DataFrame(columns=['site', 'titulo', 'link', 'data_extracao', 'resumo', 'keywords'])
else:
    hist = pd.DataFrame(columns=['site', 'titulo', 'link', 'data_extracao', 'resumo', 'keywords'])

# 4. Busca Dinâmica
print(f"🔎 A procurar matérias novas nas últimas {paginas_para_buscar} páginas dos portais...")
novas = []
for fonte in fontes:
    for pagina in range(1, paginas_para_buscar + 1):
        print(f"   -> A varrer a página {pagina} do portal {fonte['nome']}...")
        url = fonte['url_base'].format(pagina)
        if pagina == 1:
            url = url.replace('page/1/', '')
        try:
            res = requests.get(url, headers=headers, timeout=20)
            soup = BeautifulSoup(res.text, 'html.parser')
            for a in soup.find_all('a'):
                titulo = " ".join(a.get_text().split())
                link = a.get('href')
                
                if not link or not link.startswith('http'): continue
                if len(titulo) < 20 or any(s in titulo.lower() for s in termos_sujos): continue
                
                if not fonte['filtrar'] or any(p in titulo.lower() for p in palavras_chave_filtro):
                    if link not in hist['link'].values and not any(n['link'] == link for n in novas):
                        novas.append({'site': fonte['nome'], 'titulo': titulo, 'link': link, 'resumo': 'Pendente', 'keywords': '', 'data_extracao': 'Data a definir'})
        except: continue

# 5. Fila de Processamento
if len(novas) > 0:
    df_total = pd.concat([pd.DataFrame(novas), hist], ignore_index=True).drop_duplicates(subset='link')
else:
    df_total = hist.copy()

fila = df_total[df_total['resumo'].str.contains('Pendente', case=False, na=True)].head(15)
prontas = df_total[~df_total['link'].isin(fila['link'])]

print(f"📈 Extração concluída. Total na fila de espera: {len(df_total[df_total['resumo'].str.contains('Pendente', case=False, na=True)])} matérias.")
print(f"⚙️ A iniciar o processamento do lote atual ({len(fila)} notícias)...")

processadas = []
for i, n in fila.iterrows():
    try:
        print(f"\n📖 A ler matéria: {n['titulo'][:45]}...")
        art = requests.get(n['link'], headers=headers, timeout=15)
        s_art = BeautifulSoup(art.text, 'html.parser')
        
        meta_data = s_art.find('meta', property='article:published_time')
        if meta_data and meta_data.get('content'):
            data_real = datetime.strptime(meta_data['content'][:10], '%Y-%m-%d').strftime('%d/%m/%Y')
            n['data_extracao'] = data_real
        elif n['data_extracao'] == 'Data a definir':
            n['data_extracao'] = datetime.now().strftime('%d/%m/%Y')
        
        texto = " ".join([p.get_text() for p in s_art.find_all('p') if len(p.get_text()) > 60])
        
        if len(texto) > 400:
            prompt = f"Como geóloga especialista, resuma tecnicamente esta notícia de mineração em 1 parágrafo.\n\nIMPORTANTE: Na última linha do seu texto, coloque EXATAMENTE 3 hashtags relacionadas. Formato obrigatório: #Palavra1 #Palavra2 #Palavra3\n\nTexto: {texto[:4000]}"
            
            sucesso = False
            tentativas = 0
            while not sucesso and tentativas < 3:
                try:
                    resumo_ia = modelo.generate_content(prompt).text.strip()
                    sucesso = True
                except Exception as api_err:
                    if '429' in str(api_err):
                        print(f"   ⏳ A Google atingiu o limite. A pausar durante 65 segundos (Tentativa {tentativas+1}/3)...")
                        time.sleep(65)
                        tentativas += 1
                    else:
                        raise api_err
            
            if sucesso:
                if '#' in resumo_ia:
                    partes = resumo_ia.split('#')
                    n['resumo'] = partes[0].strip()
                    n['keywords'] = "#" + " #".join([p.strip().replace(' ', '') for p in partes[1:] if p.strip()])
                else:
                    n['resumo'] = resumo_ia
                    n['keywords'] = "#Mineração #SetorMineral #Geologia"
                print("   ✅ Resumo finalizado e dados extraídos com sucesso!")
            else:
                n['resumo'] = 'Pendente'
                print("   ❌ A falhar consecutivamente. Guardada para a próxima rodada.")
                
        else:
            n['resumo'] = 'Ignorado'
            print("   ⚠️ Detetado texto demasiado curto ou ficheiro de vídeo. Matéria ignorada.")
        
        processadas.append(n)
        print("   ⏸️ A pausar 30 segundos por segurança...")
        time.sleep(30) 
        
    except Exception as e:
        print(f"   ❌ Erro de ligação à página. Motivo: {str(e)[:50]}")
        n['resumo'] = 'Pendente'
        processadas.append(n)
        time.sleep(10)

# 6. Guardar CSV
print("\n💾 A guardar o progresso no ficheiro CSV...")
if not fila.empty:
    df_final = pd.concat([pd.DataFrame(processadas), prontas], ignore_index=True).drop_duplicates(subset='link')
else:
    df_final = df_total.copy()
    
df_final.to_csv(arquivo_hist, index=False, encoding='utf-8-sig')

# 7. Gerar HTML
df_exibir = df_final[~df_final['resumo'].str.contains('Pendente|Ignorado', case=False, na=False)].head(150)

if not df_exibir.empty:
    print("🎨 A construir o painel visual atualizado...")
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
            <a href="{r['link']}" target="_blank" class="btn">Ler Matéria na Íntegra</a>
        </div>"""
    
    html_template = f"""<!DOCTYPE html>
<html lang="pt-PT">
<head>
    <meta charset="UTF-8">
    <title>Notícias do Setor Mineral</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Inter', sans-serif; background: #f8f9fa; color: #333; margin: 0; padding: 30px 20px; }}
        .container {{ max-width: 900px; margin: auto; }}
        .header {{ border-bottom: 2px solid #2c3e50; margin-bottom: 30px; padding-bottom: 15px; }}
        h1 {{ color: #2c3e50; font-size: 28px; margin: 0; font-weight: 700; letter-spacing: -0.5px; }}
        .subtitle {{ color: #6c757d; font-size: 14px; margin-top: 5px; text-transform: uppercase; letter-spacing: 1px; font-weight: 600; }}
        .filters {{ background: #fff; padding: 20px; border: 1px solid #e9ecef; border-radius: 4px; display: flex; gap: 15px; margin-bottom: 30px; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }}
        input, select {{ padding: 12px 15px; border: 1px solid #ced4da; border-radius: 4px; flex: 1; font-size: 14px; color: #495057; outline: none; transition: border-color 0.2s; }}
        input:focus, select:focus {{ border-color: #4a90e2; }}
        .card {{ background: #fff; padding: 25px 30px; border: 1px solid #e9ecef; border-radius: 4px; margin-bottom: 20px; border-left: 4px solid #2c3e50; box-shadow: 0 2px 5px rgba(0,0,0,0.02); transition: box-shadow 0.2s; }}
        .card:hover {{ box-shadow: 0 5px 15px rgba(0,0,0,0.05); }}
        .tags {{ margin-bottom: 12px; display: flex; align-items: center; }}
        .site-tag {{ background: #e9ecef; color: #495057; padding: 4px 8px; border-radius: 3px; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }}
        .date-tag {{ color: #6c757d; font-size: 12px; margin-left: 12px; font-weight: 500; }}
        h3 {{ margin: 0 0 12px 0; color: #212529; font-size: 18px; line-height: 1.4; }}
        p {{ margin: 0 0 15px 0; color: #495057; line-height: 1.6; font-size: 15px; }}
        .keywords {{ color: #0056b3; font-size: 13px; font-weight: 500; margin-bottom: 15px; }}
        .btn {{ display: inline-block; padding: 8px 16px; background: transparent; color: #2c3e50; text-decoration: none; border: 1px solid #2c3e50; border-radius: 4px; font-size: 13px; font-weight: 600; transition: all 0.2s; }}
        .btn:hover {{ background: #2c3e50; color: #fff; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Notícias do Setor Mineral</h1>
            <div class="subtitle">Monitorização Diária e Resumos Técnicos</div>
        </div>
        <div class="filters">
            <input type="text" id="busca" placeholder="Pesquisar por palavra-chave, empresa ou mineral..." onkeyup="filtrar()">
            <select id="filtroData" onchange="filtrar()">
                <option value="">Todas as Datas</option>
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
            for(let c of cards) {{
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
    print("🎉 Painel guardado. O processo terminou com sucesso!")
