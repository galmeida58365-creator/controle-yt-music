"""Cria o login da conta Google (oauth.json) usado pela aba Listas (playlists).
Precisa do Client ID e Client Secret criados no Google Cloud (veja o README)."""
import json
import os
from ytmusicapi import setup_oauth

PASTA = os.path.dirname(os.path.abspath(__file__))
CLIENT_FILE = os.path.join(PASTA, "oauth_client.json")
AUTH_FILE = os.path.join(PASTA, "oauth.json")

print("=" * 60)
print("CONFIGURAR LOGIN DO YOUTUBE (playlists)")
print("=" * 60)

if os.path.exists(CLIENT_FILE):
    with open(CLIENT_FILE, encoding="utf-8") as f:
        cfg = json.load(f)
    print("Usando o Client ID salvo em oauth_client.json")
else:
    cfg = {
        "client_id": input("Cole o Client ID: ").strip(),
        "client_secret": input("Cole o Client Secret: ").strip(),
    }
    with open(CLIENT_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    print("Salvo em oauth_client.json")

print()
print("Vai abrir uma pagina do Google. Entre na sua conta, digite o codigo")
print("que aparecer aqui e autorize. Depois volte aqui e aperte ENTER.")
print()
setup_oauth(cfg["client_id"], cfg["client_secret"], filepath=AUTH_FILE, open_browser=True)
print()
print("Pronto! Login salvo em oauth.json. Reinicie o servidor.")
