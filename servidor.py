from flask import Flask, render_template_string, request, jsonify
import requests
import time
import os
import json
from ytmusicapi import YTMusic
try:
    from ytmusicapi.auth.oauth import OAuthCredentials
except Exception:
    OAuthCredentials = None

app = Flask(__name__)

PC_IP = "127.0.0.1"
PORT = 26538
BASE_URL = "http://" + PC_IP + ":" + str(PORT) + "/api/v1"

PASTA = os.path.dirname(os.path.abspath(__file__))
AUTH_FILE = os.path.join(PASTA, "oauth.json")
CLIENT_FILE = os.path.join(PASTA, "oauth_client.json")

# Busca de músicas e letras (não precisa de login)
ytmusic = YTMusic()

def obter_ytmusic_auth():
    """Retorna uma instância logada do YTMusic, ou None se o login não existir/falhar.
    Usa OAuth (renovável) quando há oauth_client.json; senão tenta login de navegador.
    Cria uma nova a cada chamada para pegar um re-login sem reiniciar o servidor."""
    try:
        if not os.path.exists(AUTH_FILE):
            return None
        if OAuthCredentials is not None and os.path.exists(CLIENT_FILE):
            with open(CLIENT_FILE, encoding="utf-8") as f:
                cfg = json.load(f)
            creds = OAuthCredentials(client_id=cfg["client_id"], client_secret=cfg["client_secret"])
            return YTMusic(AUTH_FILE, oauth_credentials=creds)
        return YTMusic(AUTH_FILE)
    except Exception as e:
        print("[AUTH] " + str(e))
    return None

@app.after_request
def no_cache(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

def enviar_comando(endpoint, data=None):
    try:
        r = requests.post(BASE_URL + "/" + endpoint, json=data, timeout=3)
        return r.status_code in [200, 201, 204]
    except:
        return False

def api_request(method, endpoint, data=None):
    """POST/PATCH/DELETE genérico para a API do YouTube Music."""
    try:
        r = requests.request(method, BASE_URL + "/" + endpoint, json=data, timeout=4)
        return r.status_code in [200, 201, 204]
    except:
        return False

def obter_musica_atual():
    try:
        for ep in ["song", "musica"]:
            r = requests.get(BASE_URL + "/" + ep, timeout=3)
            if r.status_code == 200:
                return r.json()
    except:
        pass
    return {}

def extrair_itens_fila(obj):
    itens = []
    if isinstance(obj, dict):
        if 'playlistPanelVideoRenderer' in obj:
            r = obj['playlistPanelVideoRenderer']
            title = r.get('title', {}).get('runs', [{}])[0].get('text', 'Sem titulo')
            artist = r.get('shortBylineText', {}).get('runs', [{}])[0].get('text', 'Artista')
            thumbs = r.get('thumbnail', {}).get('thumbnails', [])
            thumb = thumbs[0].get('url', '') if thumbs else ''
            selected = r.get('selected', False)
            itens.append({'title': title, 'artist': artist, 'thumbnail': thumb, 'selected': selected, 'videoId': r.get('videoId', '')})
        else:
            for v in obj.values():
                itens.extend(extrair_itens_fila(v))
    elif isinstance(obj, list):
        for i in obj:
            itens.extend(extrair_itens_fila(i))
    return itens

def _render_de_item(item):
    """Pega o renderer principal de um item da fila (ignora a versão alternativa
    música/clipe, que causava duplicatas)."""
    if not isinstance(item, dict):
        return None
    if 'playlistPanelVideoRenderer' in item:
        return item['playlistPanelVideoRenderer']
    wrap = item.get('playlistPanelVideoWrapperRenderer')
    if isinstance(wrap, dict):
        prim = wrap.get('primaryRenderer', {})
        if isinstance(prim, dict) and 'playlistPanelVideoRenderer' in prim:
            return prim['playlistPanelVideoRenderer']
    return None

def _ids_do_item(item):
    """Todos os videoIds de um item da fila: o principal e as versões alternativas
    (música/clipe têm IDs diferentes; a busca pode devolver qualquer um deles)."""
    ids = []
    rend = _render_de_item(item)
    if rend and rend.get('videoId'):
        ids.append(rend['videoId'])
    wrap = item.get('playlistPanelVideoWrapperRenderer') if isinstance(item, dict) else None
    if isinstance(wrap, dict):
        for c in wrap.get('counterpart', []) or []:
            r = (c.get('counterpartRenderer') or {}).get('playlistPanelVideoRenderer') or {}
            if r.get('videoId'):
                ids.append(r['videoId'])
    return ids

def obter_fila():
    try:
        for ep in ["queue", "informacoes-da-fila"]:
            r = requests.get(BASE_URL + "/" + ep, timeout=3)
            if r.status_code != 200:
                continue
            d = r.json()
            # Formato novo da API: {"items": [...], ...} -> índice = posição real na fila
            if isinstance(d, dict) and isinstance(d.get('items'), list):
                itens = []
                for i, item in enumerate(d['items']):
                    rend = _render_de_item(item)
                    if not rend:
                        continue
                    title = rend.get('title', {}).get('runs', [{}])[0].get('text', 'Sem titulo')
                    artist = rend.get('shortBylineText', {}).get('runs', [{}])[0].get('text', 'Artista')
                    thumbs = rend.get('thumbnail', {}).get('thumbnails', [])
                    thumb = thumbs[0].get('url', '') if thumbs else ''
                    itens.append({
                        'title': title, 'artist': artist, 'thumbnail': thumb,
                        'selected': rend.get('selected', False), 'index': i,
                        'videoId': rend.get('videoId', ''),
                        'videoIds': _ids_do_item(item)
                    })
                return itens
            # Fallback (formato antigo)
            itens = extrair_itens_fila(d)
            for i, it in enumerate(itens):
                it['index'] = i
            return itens
    except:
        pass
    return []

def obter_volume():
    try:
        r = requests.get(BASE_URL + "/volume", timeout=3)
        if r.status_code == 200:
            d = r.json()
            if isinstance(d, dict):
                return {
                    "volume": d.get('volume', d.get('state', d.get('value', 50))),
                    "isMuted": bool(d.get('isMuted', False))
                }
            return {"volume": int(d), "isMuted": False}
    except:
        pass
    return {"volume": 50, "isMuted": False}

def obter_repeat():
    try:
        r = requests.get(BASE_URL + "/repeat-mode", timeout=3)
        if r.status_code == 200:
            return r.json()  # {"mode": "NONE"|"ALL"|"ONE"|null}
    except:
        pass
    return {"mode": None}

def obter_letra():
    """Pega a letra da música tocando agora (via ytmusicapi, não precisa de login)."""
    try:
        vid = None
        titulo = ""
        r = requests.get(BASE_URL + "/song-info", timeout=3)
        if r.status_code == 200:
            info = r.json()
            vid = info.get('videoId')
            titulo = info.get('title', '')
        if not vid:
            return {"title": titulo, "lyrics": None}
        wp = ytmusic.get_watch_playlist(vid)
        lid = wp.get("lyrics")
        if not lid:
            return {"title": titulo, "lyrics": None}
        dados = ytmusic.get_lyrics(lid)
        return {"title": titulo, "lyrics": dados.get("lyrics"), "source": dados.get("source", "")}
    except Exception as e:
        print("[LETRA] " + str(e))
        return {"title": "", "lyrics": None}

def buscar_musicas(termo):
    resultados = ytmusic.search(termo, filter="songs", limit=20)
    lista = []
    for item in resultados:
        video_id = item.get('videoId')
        if not video_id:
            continue
        artistas = ", ".join([a.get('name', '') for a in item.get('artists', []) if a.get('name')])
        thumbs = item.get('thumbnails', [])
        thumb = thumbs[0].get('url', '') if thumbs else ''
        lista.append({
            'videoId': video_id,
            'title': item.get('title', 'Sem titulo'),
            'artist': artistas or 'Artista',
            'duration': item.get('duration', ''),
            'thumbnail': thumb
        })
    return lista

# ===== Login OAuth via API oficial do YouTube (token se renova sozinho) =====
YT_API = "https://www.googleapis.com/youtube/v3/"

def _salvar_token(tok):
    with open(AUTH_FILE, "w", encoding="utf-8") as f:
        json.dump(tok, f, indent=True)

def _refresh_access_token(tok):
    if OAuthCredentials is None or not os.path.exists(CLIENT_FILE):
        return tok
    with open(CLIENT_FILE, encoding="utf-8") as f:
        cfg = json.load(f)
    creds = OAuthCredentials(client_id=cfg["client_id"], client_secret=cfg["client_secret"])
    novo = creds.refresh_token(tok["refresh_token"])
    # O Google devolve {"error": "invalid_grant", ...} quando o login expirou/foi revogado
    # (sem lançar exceção). Antes isso era gravado junto com o token velho e o erro ficava escondido.
    if not isinstance(novo, dict) or "error" in novo or not novo.get("access_token"):
        erro = novo.get("error", "") if isinstance(novo, dict) else ""
        desc = novo.get("error_description", "") if isinstance(novo, dict) else ""
        raise Exception((erro + ": " + desc).strip(": ") or "falha ao renovar o token")
    tok.pop("error", None)
    tok.pop("error_description", None)
    tok.update(novo)
    tok["expires_at"] = int(time.time()) + int(novo.get("expires_in", 3600))
    _salvar_token(tok)
    return tok

erro_token = None  # motivo da última falha ao obter/renovar o token (mostrado no app)

def _explicar_erro_token(e):
    txt = str(e)
    if "invalid_grant" in txt:
        return ("O login expirou ou foi cancelado. No PC, rode o configurar_login.bat de novo. "
                "Se isso acontece toda semana, veja o passo 7.3 do README (publicar o app no Google Cloud).")
    if "invalid_client" in txt or "unauthorized_client" in txt:
        return ("O Client ID/Secret está errado ou foi apagado no Google Cloud. "
                "Apague o oauth_client.json e o oauth.json e rode o configurar_login.bat de novo.")
    return "Não consegui renovar o login (" + txt[:120] + "). Rode o configurar_login.bat de novo."

def obter_access_token():
    """Retorna um access_token válido (renova se estiver perto de expirar). None se não houver login."""
    global erro_token
    erro_token = None
    if not os.path.exists(AUTH_FILE):
        erro_token = "Login das playlists não configurado. No PC, rode o configurar_login.bat (passo 7 do README)."
        return None
    try:
        with open(AUTH_FILE, encoding="utf-8") as f:
            tok = json.load(f)
        if "refresh_token" not in tok:
            return tok.get("access_token")  # formato antigo (navegador), não serve pra API oficial
        if not os.path.exists(CLIENT_FILE):
            erro_token = "Falta o arquivo oauth_client.json. No PC, rode o configurar_login.bat."
            return None
        if int(tok.get("expires_at", 0)) - 60 < int(time.time()):
            tok = _refresh_access_token(tok)
        return tok.get("access_token")
    except Exception as e:
        print("[TOKEN] " + str(e))
        erro_token = _explicar_erro_token(e)
        return None

def _explicar_erro_api(r):
    """Traduz o erro da API do YouTube numa mensagem que diz o que fazer."""
    try:
        err = r.json().get("error", {})
    except Exception:
        err = {}
    motivos = [x.get("reason", "") for x in err.get("errors", []) or []]
    motivos += [x.get("reason", "") for x in err.get("details", []) or [] if isinstance(x, dict)]
    msg = err.get("message", "")
    if "accessNotConfigured" in motivos or "SERVICE_DISABLED" in motivos or "has not been used" in msg:
        return ("A YouTube Data API v3 não está ativada no projeto do Google Cloud (passo 7.1, item 3). "
                "Se acabou de ativar, espere uns 5 minutos e tente de novo.")
    if "quotaExceeded" in motivos:
        return "O limite diário da API do YouTube acabou. Tente de novo amanhã."
    if "channelNotFound" in motivos or r.status_code == 404:
        return ("Essa conta Google não tem canal do YouTube, por isso não tem playlists. "
                "Crie um canal em youtube.com (Criar canal) ou faça o login com outra conta.")
    if ("insufficientPermissions" in motivos or "ACCESS_TOKEN_SCOPE_INSUFFICIENT" in motivos
            or r.status_code == 401):
        return "O login não tem permissão para ler as playlists. Rode o configurar_login.bat de novo."
    return "Erro da API do YouTube (HTTP " + str(r.status_code) + "): " + (msg[:150] or "sem detalhes")

def _yt_get(path, params):
    """GET na API do YouTube com renovação automática do token em caso de 401."""
    global erro_token
    at = obter_access_token()
    if not at:
        return None
    r = requests.get(YT_API + path, params=params, headers={"Authorization": "Bearer " + at}, timeout=10)
    if r.status_code == 401:
        try:
            with open(AUTH_FILE, encoding="utf-8") as f:
                tok = json.load(f)
            tok = _refresh_access_token(tok)
            at = tok.get("access_token")
            r = requests.get(YT_API + path, params=params, headers={"Authorization": "Bearer " + at}, timeout=10)
        except Exception as e:
            print("[YT API] " + str(e))
            erro_token = _explicar_erro_token(e)
            return None
    return r

def obter_playlists():
    try:
        r = _yt_get("playlists", {"part": "snippet,contentDetails", "mine": "true", "maxResults": 50})
        if r is None:
            print("[PLAYLISTS] " + str(erro_token))
            return {"auth": False, "playlists": [], "erro": erro_token}
        if r.status_code != 200:
            print("[PLAYLISTS] HTTP " + str(r.status_code) + " " + r.text[:300])
            return {"auth": False, "playlists": [], "erro": _explicar_erro_api(r)}
        out = []
        for it in r.json().get("items", []):
            sn = it.get("snippet", {})
            thumbs = sn.get("thumbnails", {})
            thumb = (thumbs.get("medium") or thumbs.get("default") or {}).get("url", "")
            out.append({
                "playlistId": it.get("id"),
                "title": sn.get("title", "Playlist"),
                "count": it.get("contentDetails", {}).get("itemCount", ""),
                "thumbnail": thumb
            })
        return {"auth": True, "playlists": out}
    except Exception as e:
        print("[PLAYLISTS] " + str(e))
        return {"auth": False, "playlists": [], "erro": "Erro inesperado: " + str(e)[:150]}

def _limpar_artista(nome):
    if not nome:
        return "Artista"
    if nome.endswith(" - Topic"):
        nome = nome[:-8]
    return nome or "Artista"

def obter_faixas_playlist(playlist_id):
    faixas = []
    token_pagina = None
    for _ in range(4):  # até ~200 músicas (4 páginas de 50)
        params = {"part": "snippet,contentDetails", "playlistId": playlist_id, "maxResults": 50}
        if token_pagina:
            params["pageToken"] = token_pagina
        r = _yt_get("playlistItems", params)
        if r is None or r.status_code != 200:
            break
        d = r.json()
        for it in d.get("items", []):
            sn = it.get("snippet", {})
            vid = it.get("contentDetails", {}).get("videoId")
            if not vid:
                continue
            thumbs = sn.get("thumbnails", {})
            thumb = (thumbs.get("default") or thumbs.get("medium") or {}).get("url", "")
            faixas.append({
                "videoId": vid,
                "title": sn.get("title", "Sem titulo"),
                "artist": _limpar_artista(sn.get("videoOwnerChannelTitle", "")),
                "duration": "",
                "thumbnail": thumb
            })
        token_pagina = d.get("nextPageToken")
        if not token_pagina:
            break
    return faixas

def _indice_do_video(video_id, fila=None):
    """Procura o videoId na fila (inclusive nas versões alternativas). Retorna o índice (ou None)."""
    for it in (fila if fila is not None else obter_fila()):
        if video_id in it.get('videoIds', [it.get('videoId')]):
            return it['index']
    return None

def tocar_agora(video_id):
    antes = obter_fila()
    # Se a música já está na fila, só pula para ela (não duplica)
    idx = _indice_do_video(video_id, antes)
    if idx is not None:
        if any(it['selected'] and it['index'] == idx for it in antes):
            return True  # já está tocando
        return api_request('PATCH', 'queue', {"index": idx})
    # Não está na fila: insere logo após a atual
    ok = enviar_comando('queue', {"videoId": video_id, "insertPosition": "INSERT_AFTER_CURRENT_VIDEO"})
    if not ok:
        return False
    ids_antes = [it['videoId'] for it in antes]
    # Espera a fila atualizar (pode demorar) e pula para a música pelo índice exato.
    # Nunca usa "próxima" às cegas: se a inserção ainda não entrou, isso tocava a música errada.
    for _ in range(12):  # até ~3,6s
        time.sleep(0.3)
        depois = obter_fila()
        idx = _indice_do_video(video_id, depois)
        if idx is None and len(depois) > len(ids_antes):
            # O YT Music às vezes troca o ID (versão clipe x música): acha o item novo pela diferença
            ids_depois = [it['videoId'] for it in depois]
            for i, vid in enumerate(ids_depois):
                if i >= len(ids_antes) or vid != ids_antes[i]:
                    idx = i
                    break
        if idx is not None:
            print("[PLAY] inserida no índice " + str(idx))
            return api_request('PATCH', 'queue', {"index": idx})
    print("[PLAY] a música não apareceu na fila a tempo")
    return False

def adicionar_na_fila(video_id):
    return enviar_comando('queue', {"videoId": video_id, "insertPosition": "INSERT_AT_END"})

HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <title>Controle YouTube Music</title>
    <style>
        :root {
            --accent: #ff3b3b;
            --accent-soft: rgba(255,59,59,0.25);
            --glass: rgba(255,255,255,0.08);
            --glass-forte: rgba(255,255,255,0.14);
            --glass-brd: rgba(255,255,255,0.14);
            --texto-fraco: #b9b9c4;
        }
        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
        html, body { margin: 0; height: 100%; }
        body {
            font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
            color: #fff; background: #0b0b0f; overflow-x: hidden;
        }
        #bg {
            position: fixed; inset: -60px; z-index: -2;
            background-size: cover; background-position: center;
            filter: blur(48px) saturate(1.7) brightness(0.5);
            transform: scale(1.25);
            transition: background-image 0.7s ease;
        }
        #bg-overlay {
            position: fixed; inset: 0; z-index: -1;
            background: linear-gradient(180deg, rgba(11,11,15,0.25), rgba(11,11,15,0.88));
        }
        .wrap { max-width: 520px; margin: 0 auto; padding: 18px 16px 190px; }
        .topo { text-align: center; font-size: 13px; letter-spacing: 2px; text-transform: uppercase;
            color: var(--texto-fraco); margin-bottom: 14px; }

        .glass {
            background: var(--glass);
            backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px);
            border: 1px solid var(--glass-brd); border-radius: 18px;
        }

        .tab-content { display: none; animation: aparecer 0.35s ease; }
        .tab-content.active { display: block; }
        @keyframes aparecer { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }

        /* ---- PLAYER ---- */
        .capa {
            width: min(72vw, 300px); height: min(72vw, 300px);
            border-radius: 22px; object-fit: cover; display: block; margin: 6px auto 20px;
            box-shadow: 0 20px 55px rgba(0,0,0,0.6);
        }
        .capa { transition: opacity 0.35s; }
        .titulo { font-size: 22px; font-weight: 700; text-align: center; margin: 4px 10px; line-height: 1.25;
            display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
        .artista { color: var(--texto-fraco); font-size: 15px; text-align: center; margin-bottom: 18px; }

        .progresso { width: 100%; max-width: 360px; margin: 0 auto 18px; }
        .barra-area { position: relative; padding: 12px 0; cursor: pointer; touch-action: none; }
        .barra { background: rgba(255,255,255,0.18); height: 6px; border-radius: 6px; overflow: hidden; transition: height 0.15s; }
        .barra-preenchida { background: var(--accent); height: 100%; width: 0%; border-radius: 6px; transition: width 0.25s linear; }
        .barra-knob {
            position: absolute; top: 50%; left: 0%; width: 14px; height: 14px; margin: -7px 0 0 -7px;
            border-radius: 50%; background: #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.45);
            pointer-events: none; transition: left 0.25s linear, transform 0.15s;
        }
        .barra-area.arrastando .barra { height: 10px; }
        .barra-area.arrastando .barra-preenchida, .barra-area.arrastando .barra-knob { transition: none; }
        .barra-area.arrastando .barra-knob { transform: scale(1.4); }
        .tempo { display: flex; justify-content: space-between; font-size: 12px; color: var(--texto-fraco); margin-top: 7px; }

        .controls { display: flex; justify-content: center; align-items: center; gap: 14px; margin-bottom: 14px; }
        .ctrl {
            background: var(--glass); border: 1px solid var(--glass-brd); color: #fff;
            width: 54px; height: 54px; border-radius: 50%; font-size: 22px; cursor: pointer;
            display: flex; align-items: center; justify-content: center;
            backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
            transition: transform 0.12s, background 0.2s;
        }
        .ctrl:active { transform: scale(0.9); }
        .ctrl.play {
            width: 74px; height: 74px; font-size: 30px;
            background: var(--accent); border: none;
            box-shadow: 0 10px 30px var(--accent-soft);
        }
        .ctrl.ativo { background: var(--accent); border: none; }

        .row { display: flex; justify-content: center; align-items: center; gap: 10px; margin-bottom: 14px; flex-wrap: wrap; }
        .pill {
            background: var(--glass); border: 1px solid var(--glass-brd); color: #fff;
            padding: 11px 18px; border-radius: 30px; font-size: 14px; cursor: pointer;
            backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
            transition: transform 0.12s, background 0.2s;
        }
        .pill:active { transform: scale(0.94); }
        .pill.ativo { background: var(--accent); border: none; }

        .seek-area { margin: 6px auto 0; padding: 16px; border-radius: 18px; max-width: 360px; text-align: center; }
        .seek-area .rotulo { font-size: 13px; color: var(--texto-fraco); margin-bottom: 10px; }
        input {
            padding: 11px; font-size: 16px; border-radius: 12px; border: 1px solid var(--glass-brd);
            background: rgba(0,0,0,0.25); color: white; outline: none;
        }
        input:focus { border-color: var(--accent); }

        /* ---- LISTAS (busca, fila, playlists) ---- */
        .item {
            display: flex; align-items: center; gap: 12px; padding: 10px; margin: 9px 0;
            border-radius: 14px; background: var(--glass); border: 1px solid var(--glass-brd);
            backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
        }
        .item.current { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent) inset; }
        .item-thumb { width: 48px; height: 48px; border-radius: 10px; object-fit: cover; flex-shrink: 0; }
        .item-txt { flex: 1; overflow: hidden; }
        .item-title { font-size: 14px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .item-artist { font-size: 12px; color: var(--texto-fraco); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .clicavel { cursor: pointer; }
        .mini-btns { display: flex; gap: 6px; flex-shrink: 0; }
        .mini {
            border: 1px solid var(--glass-brd); background: var(--glass); color: #fff;
            border-radius: 10px; font-size: 16px; padding: 9px 12px; cursor: pointer;
        }
        .mini.play { background: var(--accent); border: none; }
        .mini.x { color: #ff8a8a; }

        .search-box { display: flex; gap: 8px; margin-bottom: 16px; }
        .search-box input { flex: 1; min-width: 0; }
        .msg { text-align: center; color: var(--texto-fraco); margin: 22px 10px; line-height: 1.6; }
        .voltar {
            background: var(--glass); border: 1px solid var(--glass-brd); color: #fff;
            padding: 9px 16px; border-radius: 12px; cursor: pointer; margin-bottom: 12px; font-size: 14px;
        }
        .secao-titulo { font-size: 16px; font-weight: 700; margin: 4px 4px 12px; }

        /* ---- LETRA ---- */
        .letra-texto { white-space: pre-wrap; line-height: 1.9; font-size: 16px; padding: 18px; border-radius: 18px; }

        /* ---- VOLUME ---- */
        .volume-value { font-size: 48px; font-weight: 800; color: var(--accent); text-align: center; margin: 24px 0 10px; }
        .volume-slider { width: 90%; max-width: 320px; margin: 18px auto; display: block; accent-color: var(--accent); height: 6px; }

        /* ---- NAV INFERIOR ---- */
        .nav {
            position: fixed; left: 0; right: 0; bottom: 0; z-index: 10;
            display: flex; justify-content: space-around; align-items: stretch;
            padding: 8px 4px calc(10px + env(safe-area-inset-bottom));
            background: rgba(18,18,24,0.6);
            backdrop-filter: blur(22px); -webkit-backdrop-filter: blur(22px);
            border-top: 1px solid var(--glass-brd);
        }
        .nav button {
            background: none; border: none; color: #8d8d99; cursor: pointer; flex: 1;
            display: flex; flex-direction: column; align-items: center; gap: 3px;
            font-size: 10px; padding: 4px 0; transition: color 0.2s;
        }
        .nav button .ic { font-size: 21px; line-height: 1; }
        .nav button.active { color: var(--accent); }

        /* ---- ICONES SVG ---- */
        .svgic { width: 22px; height: 22px; display: inline-block; vertical-align: middle; }
        .svgic path, .svgic line, .svgic polyline, .svgic polygon, .svgic circle, .svgic rect {
            fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round;
        }
        .svgic.fill path, .svgic.fill polygon, .svgic.fill circle { fill: currentColor; stroke: none; }
        .ctrl .svgic { width: 24px; height: 24px; }
        .ctrl.play .svgic { width: 30px; height: 30px; }
        .nav button .svgic { width: 22px; height: 22px; }
        .mini .svgic { width: 18px; height: 18px; }
        .pill .svgic { margin-right: 6px; }
        .pill.icon-so .svgic { margin-right: 0; }
        .voltar .svgic { margin-right: 6px; }
        #btn-repeat { position: relative; }
        #btn-repeat .rep1 { position: absolute; top: 9px; right: 11px; font-size: 10px; font-weight: 800; }

        /* ---- PULAR PARA O TEMPO (escondido até tocar em "Ir para") ---- */
        .seek-area { display: none; }
        .seek-area.aberto { display: block; animation: aparecer 0.25s ease; }

        /* ---- AVISO DE CONEXAO ---- */
        .aviso {
            display: none; margin: 0 0 14px; padding: 10px 14px; border-radius: 14px; font-size: 13px;
            text-align: center; line-height: 1.5; color: #ffc4c4;
            background: rgba(255,80,80,0.14); border: 1px solid rgba(255,110,110,0.4);
        }
        .aviso.visivel { display: block; animation: aparecer 0.3s ease; }

        /* ---- TOAST (substitui os alert) ---- */
        .toast {
            position: fixed; left: 50%; top: calc(14px + env(safe-area-inset-top)); z-index: 30;
            transform: translate(-50%, -20px); opacity: 0; pointer-events: none;
            max-width: 90%; padding: 11px 18px; border-radius: 14px; font-size: 14px; text-align: center;
            background: rgba(28,28,36,0.92); border: 1px solid var(--glass-brd);
            backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.4);
            transition: opacity 0.25s, transform 0.25s;
        }
        .toast.mostrar { opacity: 1; transform: translate(-50%, 0); }
        .toast.ok { border-color: var(--accent); }
        .toast.erro { border-color: #ff6b6b; color: #ffd0d0; }

        /* ---- MINI PLAYER (aparece fora da aba Player) ---- */
        .mini-player {
            position: fixed; left: 10px; right: 10px; bottom: 76px; z-index: 9;
            max-width: 500px; margin: 0 auto; padding: 8px; overflow: hidden;
            display: none; align-items: center; gap: 10px;
            background: rgba(28,28,36,0.75); border: 1px solid var(--glass-brd); border-radius: 16px;
            backdrop-filter: blur(22px); -webkit-backdrop-filter: blur(22px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.45);
        }
        .mini-player.visivel { display: flex; animation: aparecer 0.25s ease; }
        .mp-abrir { display: flex; align-items: center; gap: 10px; flex: 1; overflow: hidden; cursor: pointer; }
        .mp-capa { width: 42px; height: 42px; border-radius: 9px; object-fit: cover; flex-shrink: 0; }
        .mp-btn {
            background: none; border: none; color: #fff; width: 42px; height: 42px; border-radius: 50%;
            display: flex; align-items: center; justify-content: center; cursor: pointer; flex-shrink: 0;
        }
        .mp-btn:active { background: var(--glass-forte); }
        .mp-barra { position: absolute; left: 0; bottom: 0; height: 2px; width: 0%; background: var(--accent); transition: width 0.25s linear; }

        /* ---- EQUALIZADOR (música atual na fila) ---- */
        .eq { display: inline-flex; align-items: flex-end; gap: 2px; height: 12px; margin-right: 6px; vertical-align: -1px; }
        .eq i { width: 3px; height: 3px; background: var(--accent); border-radius: 1px; animation: eq 0.9s infinite ease-in-out; }
        .eq i:nth-child(2) { animation-delay: 0.3s; }
        .eq i:nth-child(3) { animation-delay: 0.6s; }
        @keyframes eq { 0%, 100% { height: 3px; } 50% { height: 12px; } }
        body.pausado .eq i { animation-play-state: paused; }

        /* ---- ESQUELETO DE CARREGAMENTO ---- */
        .esq-bloco, .esq-linha {
            background: linear-gradient(90deg, rgba(255,255,255,0.06) 25%, rgba(255,255,255,0.15) 50%, rgba(255,255,255,0.06) 75%);
            background-size: 200% 100%; animation: brilho 1.2s infinite linear;
        }
        .esq-linha { height: 11px; border-radius: 6px; margin: 5px 0 9px; width: 70%; }
        .esq-linha.curta { width: 40%; }
        @keyframes brilho { from { background-position: 200% 0; } to { background-position: -200% 0; } }

        .mini:active, .pill:active, .voltar:active { transform: scale(0.94); }
    </style>
</head>
<body>
    <div id="bg"></div>
    <div id="bg-overlay"></div>

    <div class="wrap">
        <div class="topo">Controle YouTube Music</div>
        <div id="aviso-conexao" class="aviso"></div>

        <div id="tab-player" class="tab-content active">
            <img id="capa" class="capa" src="https://cdn-icons-png.flaticon.com/512/1384/1384060.png">
            <div id="titulo" class="titulo">Carregando...</div>
            <div id="artista" class="artista">Conectando ao PC...</div>

            <div class="progresso">
                <div class="barra-area" id="barra-total">
                    <div class="barra"><div id="barra-preenchida" class="barra-preenchida"></div></div>
                    <div id="barra-knob" class="barra-knob"></div>
                </div>
                <div class="tempo">
                    <span id="tempo-atual">0:00</span>
                    <span id="tempo-total">0:00</span>
                </div>
            </div>

            <div class="controls">
                <button class="ctrl" onclick="enviar('shuffle')" title="Aleatório" data-ic="shuffle"></button>
                <button class="ctrl" onclick="enviarEAtualizar('previous')" title="Anterior" data-ic="prev"></button>
                <button class="ctrl play" id="btn-play" onclick="tocarPausar()" title="Play/Pause" data-ic="play"></button>
                <button class="ctrl" onclick="enviarEAtualizar('next')" title="Próxima" data-ic="next"></button>
                <button class="ctrl" id="btn-repeat" onclick="alternarRepeat()" title="Repetir" data-ic="repeat"></button>
            </div>
            <div class="row">
                <button class="pill" onclick="avaliar('like')"><span data-ic="heart"></span>Gostei</button>
                <button class="pill" onclick="avaliar('dislike')"><span data-ic="thumbsdown"></span>Não gostei</button>
            </div>
            <div class="row">
                <button class="pill" onclick="pularRelativo(-10)" title="Voltar 10 segundos"><span data-ic="rewind"></span>10s</button>
                <button class="pill" id="btn-irpara" onclick="alternarIrPara()"><span data-ic="clock"></span>Ir para...</button>
                <button class="pill" onclick="pularRelativo(10)" title="Avançar 10 segundos"><span data-ic="forward"></span>10s</button>
            </div>

            <div class="seek-area glass" id="seek-area">
                <div class="rotulo">Pular para o tempo:</div>
                <input type="number" id="min" placeholder="Min" min="0" style="width:62px; text-align:center;">
                <span style="font-size:18px; font-weight:bold; margin:0 2px;">:</span>
                <input type="number" id="sec" placeholder="Seg" min="0" max="59" style="width:62px; text-align:center;">
                <button class="pill icon-so" style="margin-left:8px;" onclick="pularParaTempo()" title="Ir para o tempo" data-ic="arrow"></button>
            </div>
        </div>

        <div id="tab-buscar" class="tab-content">
            <div class="search-box">
                <input type="search" id="busca-input" placeholder="Música ou artista..." onkeydown="if (event.key === 'Enter') buscar()">
                <button class="pill ativo icon-so" onclick="buscar()" title="Buscar" data-ic="search"></button>
            </div>
            <div id="search-list"><p class="msg">Digite o nome de uma música e toque no botão de busca.</p></div>
        </div>

        <div id="tab-fila" class="tab-content">
            <div class="row">
                <button class="pill" onclick="atualizarFila()"><span data-ic="refresh"></span>Atualizar Fila</button>
            </div>
            <p class="msg" style="margin-top:0;">Toque numa música para pular para ela. Use o X para remover.</p>
            <div id="queue-list">Clique em Atualizar Fila...</div>
        </div>

        <div id="tab-letra" class="tab-content">
            <div class="row">
                <button class="pill" onclick="carregarLetra()"><span data-ic="refresh"></span>Atualizar Letra</button>
            </div>
            <div id="letra-titulo" class="secao-titulo" style="text-align:center;"></div>
            <div id="letra-conteudo" class="letra-texto glass"><p class="msg">Toque em Atualizar Letra.</p></div>
        </div>

        <div id="tab-listas" class="tab-content">
            <div class="row">
                <button class="pill" onclick="carregarPlaylists()"><span data-ic="library"></span>Minhas Playlists</button>
            </div>
            <div id="listas-list"><p class="msg">Toque em Minhas Playlists.</p></div>
        </div>

        <div id="tab-volume" class="tab-content">
            <div class="volume-value" id="volume-display">50%</div>
            <input type="range" id="volume-slider" class="volume-slider" min="0" max="100" value="50" oninput="mudarVolume(this.value)">
            <div class="row">
                <button class="pill" onclick="ajustarVolume(-10)"><span data-ic="minus"></span>10</button>
                <button class="pill" id="btn-mudo" onclick="alternarMudo()"><span data-ic="mute"></span>Mudo</button>
                <button class="pill" onclick="ajustarVolume(10)"><span data-ic="plus"></span>10</button>
            </div>
        </div>
    </div>

    <div id="mini-player" class="mini-player">
        <div class="mp-abrir" onclick="mostrarAba('player')">
            <img id="mp-capa" class="mp-capa" src="https://cdn-icons-png.flaticon.com/512/1384/1384060.png">
            <div class="item-txt">
                <div id="mp-titulo" class="item-title"></div>
                <div id="mp-artista" class="item-artist"></div>
            </div>
        </div>
        <button class="mp-btn" id="mp-play" onclick="tocarPausar()" title="Play/Pause" data-ic="play"></button>
        <button class="mp-btn" onclick="enviarEAtualizar('next')" title="Próxima" data-ic="next"></button>
        <div id="mp-barra" class="mp-barra"></div>
    </div>

    <div id="toast" class="toast"></div>

    <div class="nav" id="nav">
        <button class="active" id="btn-player" onclick="mostrarAba('player')"><span data-ic="music"></span>Player</button>
        <button id="btn-buscar" onclick="mostrarAba('buscar')"><span data-ic="search"></span>Buscar</button>
        <button id="btn-fila" onclick="mostrarAba('fila')"><span data-ic="list"></span>Fila</button>
        <button id="btn-letra" onclick="mostrarAba('letra')"><span data-ic="mic"></span>Letra</button>
        <button id="btn-listas" onclick="mostrarAba('listas')"><span data-ic="library"></span>Listas</button>
        <button id="btn-volume" onclick="mostrarAba('volume')"><span data-ic="volume"></span>Volume</button>
    </div>

    <script>
        var ultimaCapa = '';
        var volumeDesejado = null;  // último volume que o usuário escolheu (o servidor reporta errado)
        var abaAtual = 'player';
        var temMusica = false;
        var falhasConexao = 0;
        // Progresso: o servidor manda o tempo 1x por segundo; entre uma resposta e outra o app "anda" sozinho
        var prog = {atual: 0, total: 0, pausado: true, em: 0};
        var arrastando = false;
        var ignorarProgressoAte = 0;  // depois de um seek, ignora o tempo antigo que ainda vem do servidor
        var ignorarPausaAte = 0;

        // ---- Icones SVG (estilo linha) ----
        var ICONS = {
            shuffle: '<polyline points="16 3 21 3 21 8"/><line x1="4" y1="20" x2="21" y2="3"/><polyline points="21 16 21 21 16 21"/><line x1="15" y1="15" x2="21" y2="21"/><line x1="4" y1="4" x2="9" y2="9"/>',
            prev: '<polygon points="19 20 9 12 19 4 19 20"/><line x1="5" y1="19" x2="5" y2="5"/>',
            next: '<polygon points="5 4 15 12 5 20 5 4"/><line x1="19" y1="5" x2="19" y2="19"/>',
            play: '<polygon points="6 4 20 12 6 20 6 4"/>',
            pause: '<rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>',
            repeat: '<polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/>',
            heart: '<path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 1 0-7.78 7.78L12 21.23l8.84-8.84a5.5 5.5 0 0 0 0-7.78z"/>',
            thumbsdown: '<path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3z"/><line x1="17" y1="2" x2="21" y2="2"/><path d="M17 2v11"/>',
            arrow: '<line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>',
            search: '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
            refresh: '<polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>',
            close: '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
            minus: '<line x1="5" y1="12" x2="19" y2="12"/>',
            plus: '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
            mute: '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/>',
            volume: '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/>',
            music: '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
            list: '<line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>',
            mic: '<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/>',
            library: '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>',
            back: '<line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>',
            rewind: '<polygon points="11 19 2 12 11 5 11 19"/><polygon points="22 19 13 12 22 5 22 19"/>',
            forward: '<polygon points="13 19 22 12 13 5 13 19"/><polygon points="2 19 11 12 2 5 2 19"/>',
            clock: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>'
        };
        var ICONS_FILL = {play: 1, prev: 1, next: 1, heart: 1, thumbsdown: 1, mute: 1, volume: 1, music: 1, rewind: 1, forward: 1};

        function ic(nome) {
            var cls = 'svgic' + (ICONS_FILL[nome] ? ' fill' : '');
            return '<svg class="' + cls + '" viewBox="0 0 24 24">' + (ICONS[nome] || '') + '</svg>';
        }

        function aplicarIcones() {
            document.querySelectorAll('[data-ic]').forEach(function(el) {
                el.innerHTML = ic(el.getAttribute('data-ic'));
            });
        }

        function mostrarAba(nome) {
            document.querySelectorAll('.tab-content').forEach(function(el) { el.classList.remove('active'); });
            document.querySelectorAll('.nav button').forEach(function(el) { el.classList.remove('active'); });
            document.getElementById('tab-' + nome).classList.add('active');
            document.getElementById('btn-' + nome).classList.add('active');
            abaAtual = nome;
            window.scrollTo(0, 0);
            atualizarMiniPlayer();
            if (nome === 'fila') atualizarFila();
            if (nome === 'volume') atualizarVolume();
            if (nome === 'letra') carregarLetra();
            if (nome === 'listas') carregarPlaylists();
        }

        function escapar(texto) {
            return String(texto || '')
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }

        function enviar(endpoint, data) {
            return fetch('/api/command', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({endpoint: endpoint, data: data || null})
            });
        }

        // ---- Avisos rápidos (no lugar dos alert) ----
        var toastTimer = null;
        function toast(msg, tipo) {
            var t = document.getElementById('toast');
            t.className = 'toast mostrar' + (tipo ? ' ' + tipo : '');
            t.innerText = msg;
            clearTimeout(toastTimer);
            toastTimer = setTimeout(function() { t.className = 'toast'; }, 2200);
        }

        function enviarEAtualizar(endpoint) {
            enviar(endpoint).then(function() { setTimeout(atualizarEstado, 350); })
                .catch(function() { toast('Erro de conexão.', 'erro'); });
        }

        function tocarPausar() {
            // troca o ícone na hora, sem esperar o servidor
            mostrarPausado(!prog.pausado);
            ignorarPausaAte = Date.now() + 600;  // não deixa uma resposta antiga desfazer o ícone
            enviar('toggle-play').then(function() { setTimeout(atualizarEstado, 700); })
                .catch(function() { toast('Erro de conexão.', 'erro'); });
        }

        function mostrarPausado(pausado) {
            prog.atual = segundosAgora();
            prog.em = Date.now();
            prog.pausado = pausado;
            document.body.classList.toggle('pausado', pausado);
            var nome = pausado ? 'play' : 'pause';
            document.getElementById('btn-play').innerHTML = ic(nome);
            document.getElementById('mp-play').innerHTML = ic(nome);
        }

        function avaliar(tipo) {
            enviar(tipo).then(function(r) {
                if (r.ok) toast(tipo === 'like' ? 'Marcada como Gostei' : 'Marcada como Não gostei', 'ok');
                else toast('Não consegui avaliar.', 'erro');
            }).catch(function() { toast('Erro de conexão.', 'erro'); });
        }

        // ---- Tempo / barra de progresso ----
        function segundosAgora() {
            var s = prog.atual + (prog.pausado ? 0 : (Date.now() - prog.em) / 1000);
            return prog.total > 0 ? Math.min(s, prog.total) : s;
        }

        function desenharProgresso(seg) {
            if (!(prog.total > 0)) return;
            var pct = Math.max(0, Math.min(1, seg / prog.total)) * 100;
            document.getElementById('barra-preenchida').style.width = pct + '%';
            document.getElementById('barra-knob').style.left = pct + '%';
            document.getElementById('mp-barra').style.width = pct + '%';
            document.getElementById('tempo-atual').innerText = formatarTempo(seg);
            document.getElementById('tempo-total').innerText = formatarTempo(prog.total);
        }

        function irParaSegundo(seg) {
            if (!(prog.total > 0)) return;
            seg = Math.round(Math.max(0, Math.min(prog.total, seg)));
            prog.atual = seg;
            prog.em = Date.now();
            ignorarProgressoAte = Date.now() + 1500;
            desenharProgresso(seg);
            enviar('seek-to', {seconds: seg});
        }

        function pularRelativo(delta) {
            irParaSegundo(segundosAgora() + delta);
        }

        function alternarIrPara() {
            var area = document.getElementById('seek-area');
            area.classList.toggle('aberto');
            document.getElementById('btn-irpara').classList.toggle('ativo', area.classList.contains('aberto'));
        }

        function pularParaTempo() {
            var min = parseInt(document.getElementById('min').value) || 0;
            var sec = parseInt(document.getElementById('sec').value) || 0;
            irParaSegundo((min * 60) + sec);
            toast('Indo para ' + formatarTempo((min * 60) + sec));
            alternarIrPara();
        }

        // Barra: tocar OU arrastar o dedo para escolher o ponto da música
        function prepararBarra() {
            var area = document.getElementById('barra-total');
            function fracDoEvento(ev) {
                var rect = area.getBoundingClientRect();
                return Math.max(0, Math.min(1, (ev.clientX - rect.left) / rect.width));
            }
            area.addEventListener('pointerdown', function(ev) {
                if (!(prog.total > 0)) return;
                arrastando = true;
                area.classList.add('arrastando');
                try { area.setPointerCapture(ev.pointerId); } catch (e) {}
                desenharProgresso(fracDoEvento(ev) * prog.total);
            });
            area.addEventListener('pointermove', function(ev) {
                if (arrastando) desenharProgresso(fracDoEvento(ev) * prog.total);
            });
            area.addEventListener('pointerup', function(ev) {
                if (!arrastando) return;
                arrastando = false;
                area.classList.remove('arrastando');
                irParaSegundo(fracDoEvento(ev) * prog.total);
            });
            area.addEventListener('pointercancel', function() {
                arrastando = false;
                area.classList.remove('arrastando');
            });
        }

        // ---- Mini player e aviso de conexão ----
        function atualizarMiniPlayer() {
            var mp = document.getElementById('mini-player');
            mp.classList.toggle('visivel', abaAtual !== 'player' && temMusica);
        }

        function posicionarMiniPlayer() {
            var nav = document.getElementById('nav');
            document.getElementById('mini-player').style.bottom = (nav.offsetHeight + 8) + 'px';
        }

        function avisoConexao(msg) {
            var av = document.getElementById('aviso-conexao');
            if (!msg) { falhasConexao = 0; av.classList.remove('visivel'); return; }
            falhasConexao++;
            if (falhasConexao >= 3) {  // só avisa depois de 3 falhas seguidas, pra não piscar
                av.innerText = msg;
                av.classList.add('visivel');
            }
        }

        function esqueleto(n) {
            var h = '';
            for (var i = 0; i < n; i++) {
                h += '<div class="item"><div class="item-thumb esq-bloco"></div>' +
                     '<div class="item-txt"><div class="esq-linha"></div><div class="esq-linha curta"></div></div></div>';
            }
            return h;
        }

        function formatarTempo(s) {
            if (!s && s !== 0) return "0:00";
            return Math.floor(s/60) + ":" + (Math.floor(s%60) < 10 ? "0" : "") + Math.floor(s%60);
        }

        // ---- capa + cor dinamica ----
        function aplicarCapa(src) {
            if (!src || src === ultimaCapa) return;
            ultimaCapa = src;
            var capa = document.getElementById('capa');
            capa.style.opacity = 0;
            capa.onload = function() { capa.style.opacity = 1; };
            capa.onerror = function() { capa.style.opacity = 1; };
            capa.src = src;
            document.getElementById('mp-capa').src = src;
            document.getElementById('bg').style.backgroundImage = 'url("' + src + '")';
            extrairCor(src);
        }

        function extrairCor(src) {
            try {
                var img = new Image();
                img.crossOrigin = 'anonymous';
                img.onload = function() {
                    try {
                        var c = document.createElement('canvas');
                        c.width = 16; c.height = 16;
                        var ctx = c.getContext('2d');
                        ctx.drawImage(img, 0, 0, 16, 16);
                        var d = ctx.getImageData(0, 0, 16, 16).data;
                        var r = 0, g = 0, b = 0, n = 0;
                        for (var i = 0; i < d.length; i += 4) {
                            var rr = d[i], gg = d[i+1], bb = d[i+2];
                            var mx = Math.max(rr, gg, bb), mn = Math.min(rr, gg, bb);
                            if (mx < 45 || mx > 232) continue;   // ignora muito escuro/claro
                            if (mx - mn < 22) continue;          // ignora cinza
                            r += rr; g += gg; b += bb; n++;
                        }
                        if (n > 0) {
                            definirAccent(Math.round(r/n), Math.round(g/n), Math.round(b/n));
                        }
                    } catch (e) {}
                };
                img.src = src;
            } catch (e) {}
        }

        function definirAccent(r, g, b) {
            // garante um minimo de brilho pra ficar legivel
            var mx = Math.max(r, g, b);
            if (mx < 110) { var f = 110 / (mx || 1); r = Math.min(255, r*f); g = Math.min(255, g*f); b = Math.min(255, b*f); }
            r = Math.round(r); g = Math.round(g); b = Math.round(b);
            var root = document.documentElement.style;
            root.setProperty('--accent', 'rgb(' + r + ',' + g + ',' + b + ')');
            root.setProperty('--accent-soft', 'rgba(' + r + ',' + g + ',' + b + ',0.3)');
        }

        function atualizarEstado() {
            fetch('/api/state')
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    if (!(data && data.title)) {
                        avisoConexao('O YouTube Music não respondeu. Ele está aberto no PC?');
                        return;
                    }
                    avisoConexao(null);
                    temMusica = true;
                    if (document.getElementById('titulo').innerText !== data.title) {
                        document.getElementById('titulo').innerText = data.title;
                        document.getElementById('mp-titulo').innerText = data.title;
                    }
                    document.getElementById('artista').innerText = data.artist || '';
                    document.getElementById('mp-artista').innerText = data.artist || '';
                    if (data.imageSrc) aplicarCapa(data.imageSrc);
                    prog.total = data.songDuration || 0;
                    if (Date.now() > ignorarProgressoAte) {
                        prog.atual = data.elapsedSeconds || 0;
                        prog.em = Date.now();
                    }
                    if (typeof data.isPaused !== 'undefined' && Date.now() > ignorarPausaAte) mostrarPausado(!!data.isPaused);
                    if (!arrastando) desenharProgresso(segundosAgora());
                    atualizarMiniPlayer();
                })
                .catch(function() {
                    avisoConexao('Sem conexão com o PC. Confira o Wi-Fi e se o iniciar_servidor.bat está rodando.');
                });
        }

        function atualizarRepeat() {
            fetch('/api/repeat')
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    var btn = document.getElementById('btn-repeat');
                    if (!btn) return;
                    var m = data.mode;
                    if (m === 'ONE') { btn.innerHTML = ic('repeat') + '<span class="rep1">1</span>'; btn.classList.add('ativo'); btn.title = 'Repetindo esta música'; }
                    else if (m === 'ALL') { btn.innerHTML = ic('repeat'); btn.classList.add('ativo'); btn.title = 'Repetindo a fila'; }
                    else { btn.innerHTML = ic('repeat'); btn.classList.remove('ativo'); btn.title = 'Repetir desligado'; }
                })
                .catch(function() {});
        }

        function alternarRepeat() {
            enviar('switch-repeat', {iteration: 1}).then(function() {
                setTimeout(atualizarRepeat, 300);
            });
        }

        function montarListaMusicas(data) {
            var html = '';
            data.forEach(function(item) {
                var id = escapar(item.videoId);
                html += '<div class="item">' +
                    '<img class="item-thumb" loading="lazy" src="' + escapar(item.thumbnail) + '">' +
                    '<div class="item-txt">' +
                        '<div class="item-title">' + escapar(item.title) + '</div>' +
                        '<div class="item-artist">' + escapar(item.artist) + (item.duration ? ' • ' + escapar(item.duration) : '') + '</div>' +
                    '</div>' +
                    '<div class="mini-btns">' +
                        '<button class="mini play" title="Tocar" onclick="tocarMusica(\\'' + id + '\\')">' + ic('play') + '</button>' +
                        '<button class="mini" title="Adicionar à fila" onclick="adicionarFila(\\'' + id + '\\')">' + ic('plus') + '</button>' +
                    '</div></div>';
            });
            return html;
        }

        function atualizarFila() {
            var ql = document.getElementById('queue-list');
            if (!ql.querySelector('.item')) ql.innerHTML = esqueleto(6);  // só mostra o esqueleto na 1ª carga
            fetch('/api/queue')
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    var html = '';
                    if (Array.isArray(data) && data.length > 0) {
                        data.forEach(function(item) {
                            var c = item.selected ? ' current' : '';
                            var eq = item.selected ? '<span class="eq"><i></i><i></i><i></i></span>' : '';
                            html += '<div class="item' + c + '">' +
                                '<div class="clicavel" style="display:flex;align-items:center;gap:12px;flex:1;overflow:hidden;" onclick="pularFila(' + item.index + ')">' +
                                    '<img class="item-thumb" loading="lazy" src="' + escapar(item.thumbnail) + '">' +
                                    '<div class="item-txt">' +
                                        '<div class="item-title">' + eq + escapar(item.title) + '</div>' +
                                        '<div class="item-artist">' + escapar(item.artist) + '</div>' +
                                    '</div>' +
                                '</div>' +
                                '<button class="mini x" title="Remover" onclick="removerFila(' + item.index + ')">' + ic('close') + '</button>' +
                                '</div>';
                        });
                    } else {
                        html = '<p class="msg">Fila vazia.</p>';
                    }
                    ql.innerHTML = html;
                    var atual = ql.querySelector('.item.current');
                    if (atual && abaAtual === 'fila') atual.scrollIntoView({block: 'center', behavior: 'smooth'});
                })
                .catch(function() {
                    document.getElementById('queue-list').innerHTML = '<p class="msg">Erro ao carregar.</p>';
                });
        }

        function pularFila(index) {
            fetch('/api/queue-jump', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({index: index})
            }).then(function(r) {
                if (r.ok) { mostrarAba('player'); }
                else { toast('Não consegui pular para essa música.', 'erro'); }
            }).catch(function() { toast('Erro de conexão.', 'erro'); });
        }

        function removerFila(index) {
            fetch('/api/queue-remove', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({index: index})
            }).then(function(r) {
                if (r.ok) { toast('Removida da fila'); setTimeout(atualizarFila, 300); }
                else { toast('Não consegui remover.', 'erro'); }
            }).catch(function() { toast('Erro de conexão.', 'erro'); });
        }

        function buscar() {
            var termo = document.getElementById('busca-input').value.trim();
            var lista = document.getElementById('search-list');
            if (!termo) return;
            lista.innerHTML = esqueleto(6);
            fetch('/api/search?q=' + encodeURIComponent(termo))
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    if (!Array.isArray(data) || data.length === 0) {
                        lista.innerHTML = '<p class="msg">Nenhum resultado.</p>';
                        return;
                    }
                    lista.innerHTML = montarListaMusicas(data);
                })
                .catch(function() {
                    lista.innerHTML = '<p class="msg">Erro ao buscar. Veja o terminal do PC.</p>';
                });
        }

        function tocarMusica(id) {
            toast('Colocando a música...');
            fetch('/api/play', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({videoId: id})
            })
            .then(function(r) {
                if (r.ok) { mostrarAba('player'); }
                else { toast('Não consegui tocar essa música.', 'erro'); }
            })
            .catch(function() { toast('Erro de conexão.', 'erro'); });
        }

        function adicionarFila(id) {
            fetch('/api/add-queue', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({videoId: id})
            })
            .then(function(r) {
                if (r.ok) { toast('Adicionada no fim da fila', 'ok'); }
                else { toast('Não consegui adicionar na fila.', 'erro'); }
            })
            .catch(function() { toast('Erro de conexão.', 'erro'); });
        }

        function carregarLetra() {
            document.getElementById('letra-titulo').innerText = '';
            document.getElementById('letra-conteudo').innerHTML = '<p class="msg">Carregando letra...</p>';
            fetch('/api/lyrics')
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    document.getElementById('letra-titulo').innerText = data.title || '';
                    if (data.lyrics) {
                        document.getElementById('letra-conteudo').innerText = data.lyrics;
                    } else {
                        document.getElementById('letra-conteudo').innerHTML = '<p class="msg">Esta música não tem letra disponível.</p>';
                    }
                })
                .catch(function() {
                    document.getElementById('letra-conteudo').innerHTML = '<p class="msg">Erro ao carregar a letra.</p>';
                });
        }

        function carregarPlaylists() {
            var lista = document.getElementById('listas-list');
            lista.innerHTML = esqueleto(5);
            fetch('/api/playlists')
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    if (!data.auth) {
                        lista.innerHTML = '<p class="msg">' + escapar(data.erro || 'Login das playlists não configurado. No PC, rode o configurar_login.bat.') + '</p>';
                        return;
                    }
                    if (!Array.isArray(data.playlists) || data.playlists.length === 0) {
                        lista.innerHTML = '<p class="msg">Nenhuma playlist encontrada nesta conta.<br>Confira se o login foi feito com a mesma conta do YouTube Music (rode o configurar_login.bat de novo para trocar).</p>';
                        return;
                    }
                    var html = '';
                    data.playlists.forEach(function(p) {
                        var pid = escapar(p.playlistId);
                        html += '<div class="item clicavel" data-pid="' + escapar(p.playlistId) + '" data-titulo="' + escapar(p.title) + '" onclick="abrirPlaylist(this.dataset.pid, this.dataset.titulo)">' +
                            '<img class="item-thumb" loading="lazy" src="' + escapar(p.thumbnail) + '">' +
                            '<div class="item-txt">' +
                                '<div class="item-title">' + escapar(p.title) + '</div>' +
                                '<div class="item-artist">' + escapar(p.count) + '</div>' +
                            '</div></div>';
                    });
                    lista.innerHTML = html;
                })
                .catch(function() {
                    lista.innerHTML = '<p class="msg">Erro ao carregar playlists.</p>';
                });
        }

        function abrirPlaylist(pid, titulo) {
            var lista = document.getElementById('listas-list');
            var cabecalho = '<button class="voltar" onclick="carregarPlaylists()">' + ic('back') + 'Voltar</button>' +
                '<div class="secao-titulo">' + escapar(titulo) + '</div>';
            lista.innerHTML = cabecalho + esqueleto(6);
            fetch('/api/playlist-tracks?id=' + encodeURIComponent(pid))
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    if (!Array.isArray(data) || data.length === 0) {
                        lista.innerHTML = cabecalho + '<p class="msg">Playlist vazia ou sem acesso.</p>';
                        return;
                    }
                    lista.innerHTML = cabecalho + montarListaMusicas(data);
                })
                .catch(function() {
                    lista.innerHTML = cabecalho + '<p class="msg">Erro ao abrir a playlist.</p>';
                });
        }

        function atualizarVolume() {
            fetch('/api/volume')
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    var slider = document.getElementById('volume-slider');
                    var btn = document.getElementById('btn-mudo');
                    // O servidor reporta o volume de forma não confiável. Se o usuário já escolheu
                    // um valor nesta sessão, usamos o dele; senão, o do servidor (só na 1ª vez).
                    var vol;
                    if (volumeDesejado !== null) { vol = volumeDesejado; }
                    else { vol = (data.volume != null) ? data.volume : 50; }
                    if (document.activeElement !== slider) { slider.value = vol; }
                    if (data.isMuted) {
                        document.getElementById('volume-display').innerText = 'MUDO';
                        if (btn) { btn.innerHTML = ic('volume') + 'Ativar som'; btn.classList.add('ativo'); }
                    } else {
                        document.getElementById('volume-display').innerText = vol + '%';
                        if (btn) { btn.innerHTML = ic('mute') + 'Mudo'; btn.classList.remove('ativo'); }
                    }
                })
                .catch(function() {});
        }

        function alternarMudo() {
            enviar('toggle-mute').then(function() {
                setTimeout(atualizarVolume, 300);
            });
        }

        function mudarVolume(valor) {
            volumeDesejado = parseInt(valor);
            document.getElementById('volume-display').innerText = valor + '%';
            enviar('volume', {volume: parseInt(valor)});
        }

        function ajustarVolume(delta) {
            var s = document.getElementById('volume-slider');
            var novo = Math.max(0, Math.min(100, parseInt(s.value) + delta));
            s.value = novo;
            mudarVolume(novo);
        }

        function loopPrincipal() {
            atualizarEstado();
            atualizarVolume();
            atualizarRepeat();
        }

        aplicarIcones();
        prepararBarra();
        posicionarMiniPlayer();
        window.addEventListener('resize', posicionarMiniPlayer);
        // anda a barra suavemente entre uma resposta do servidor e outra
        setInterval(function() { if (!arrastando) desenharProgresso(segundosAgora()); }, 250);
        setInterval(loopPrincipal, 1000);
        loopPrincipal();
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML)

@app.route('/api/state')
def state():
    return jsonify(obter_musica_atual())

@app.route('/api/queue')
def queue():
    return jsonify(obter_fila())

@app.route('/api/queue-jump', methods=['POST'])
def queue_jump():
    index = (request.json or {}).get('index')
    print("[FILA PULAR] " + str(index))
    if index is not None and api_request('PATCH', 'queue', {"index": int(index)}):
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 500

@app.route('/api/queue-remove', methods=['POST'])
def queue_remove():
    index = (request.json or {}).get('index')
    print("[FILA REMOVER] " + str(index))
    if index is not None and api_request('DELETE', 'queue/' + str(int(index))):
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 500

@app.route('/api/volume')
def volume():
    return jsonify(obter_volume())

@app.route('/api/repeat')
def repeat():
    return jsonify(obter_repeat())

@app.route('/api/lyrics')
def lyrics():
    return jsonify(obter_letra())

@app.route('/api/playlists')
def playlists():
    return jsonify(obter_playlists())

@app.route('/api/playlist-tracks')
def playlist_tracks():
    pid = request.args.get('id', '').strip()
    if not pid:
        return jsonify([])
    try:
        return jsonify(obter_faixas_playlist(pid))
    except Exception as e:
        print("[FAIXAS] " + str(e))
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/search')
def search():
    termo = request.args.get('q', '').strip()
    if not termo:
        return jsonify([])
    try:
        return jsonify(buscar_musicas(termo))
    except Exception as e:
        print("[ERRO BUSCA] " + str(e))
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/play', methods=['POST'])
def play():
    video_id = (request.json or {}).get('videoId')
    print("[PLAY] " + str(video_id))
    if video_id and tocar_agora(video_id):
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 500

@app.route('/api/add-queue', methods=['POST'])
def add_queue():
    video_id = (request.json or {}).get('videoId')
    print("[ADD FILA] " + str(video_id))
    if video_id and adicionar_na_fila(video_id):
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 500

@app.route('/api/command', methods=['POST'])
def command():
    req = request.json
    endpoint = req.get('endpoint')
    data = req.get('data')
    print("[CMD] " + str(endpoint))
    if endpoint == 'volume':
        if enviar_comando('volume', data):
            return jsonify({"status": "success"})
        return jsonify({"status": "error"}), 500
    if enviar_comando(endpoint, data):
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 500

def ip_da_rede():
    """Descobre o IP do PC na rede local (o que o celular deve usar)."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # não envia nada, só escolhe a placa de rede usada
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()

if __name__ == '__main__':
    print("=" * 60)
    print("SERVIDOR DE CONTROLE YOUTUBE MUSIC")
    print("=" * 60)
    print("No app do celular, use o endereco:  " + ip_da_rede() + ":5000")
    print("(ou abra no navegador do celular: http://" + ip_da_rede() + ":5000)")
    if not os.path.exists(AUTH_FILE):
        print("Playlists desativadas (sem login). Para ativar: configurar_login.bat")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=False)
