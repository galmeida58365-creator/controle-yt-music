# Controle YT Music

Controle o **YouTube Music Desktop** do seu PC pelo celular: play/pause, pular músicas, volume,
fila, busca, letras e suas playlists.

```
Celular (app ou navegador)  ──Wi-Fi──>  servidor.py (no PC)  ──>  YouTube Music Desktop (no PC)
```

> Funciona só no **Windows**, com o celular e o PC **na mesma rede Wi-Fi**.

---

## O que você vai precisar

- Um PC com Windows
- Um celular Android (ou qualquer celular com navegador)
- Os dois conectados no **mesmo Wi-Fi**
- Uns 15 minutos (mais uns 10 se quiser a aba de playlists)

---

## Passo 1: Instalar o YouTube Music Desktop

1. Baixe o instalador em **https://github.com/th-ch/youtube-music/releases**
   (pegue o arquivo `YouTube-Music-Setup-x.x.x.exe` da versão mais recente).
2. Instale, abra e entre na sua conta do YouTube.

## Passo 2: Ligar a API do YouTube Music

O servidor conversa com o YouTube Music por um plugin que vem desligado.

1. No YouTube Music Desktop, abra o menu **Plugins** (no topo da janela).
2. Ative **API Server**.
3. No mesmo menu, entre nas opções do **API Server** e confira:
   - **Port**: `26538`
   - Na opção de autorização: **Não autorizar**

   ⚠️ Sem o "Não autorizar", o servidor não consegue controlar o player.

## Passo 3: Instalar o Python

1. Baixe em **https://www.python.org/downloads/** (versão 3.10 ou mais nova).
2. Na primeira tela do instalador, **marque a caixa "Add python.exe to PATH"** e clique em *Install Now*.

## Passo 4: Baixar este projeto

- Na página do projeto no GitHub, clique em **Code → Download ZIP** e extraia numa pasta
  (ex.: `Documentos\controle-yt-music`).
- Ou, se você usa git: `git clone <link do repositório>`.

## Passo 5: Rodar o servidor

1. Deixe o **YouTube Music Desktop aberto**.
2. Dê dois cliques em **`iniciar_servidor.bat`**.
   - Na **primeira vez** ele instala as bibliotecas sozinho (demora 1–2 minutos).
3. Se o Windows perguntar sobre o **Firewall**, marque **Redes privadas** e clique em **Permitir acesso**.
4. Na janela preta vai aparecer algo assim:

   ```
   No app do celular, use o endereco:  192.168.0.15:5000
   ```

   Anote esse endereço. **Deixe essa janela aberta** enquanto usar o controle.

## Passo 6: Abrir no celular

**Opção A, pelo app (recomendado)**

1. Instale o APK no celular (veja a aba **Releases** deste repositório, ou compile, veja abaixo).
   O Android pode pedir para permitir "instalar apps de fontes desconhecidas".
2. Abra o app e digite o endereço que apareceu no Passo 5 (ex.: `192.168.0.15:5000`).

**Opção B, pelo navegador**

Abra o Chrome do celular e acesse `http://192.168.0.15:5000` (com o seu endereço).
Dica: no menu do Chrome, *Adicionar à tela inicial* para virar um "atalho de app".

Pronto! A aba **Player**, **Buscar**, **Fila**, **Letra** e **Volume** já funcionam.
A aba **Listas** (suas playlists) precisa do passo opcional abaixo.

---

## Passo 7 (opcional): Ativar a aba de playlists

Para ler as **suas** playlists, o servidor precisa de permissão da sua conta Google.
Isso é feito pela API oficial do YouTube, que é gratuita, mas exige criar uma "chave" sua.

### 7.1 Criar a chave no Google Cloud

1. Acesse **https://console.cloud.google.com/** e entre com sua conta Google.
2. No topo, clique no seletor de projetos → **Novo projeto** → dê um nome (ex.: `controle-yt-music`) → **Criar**.
   Confirme que o projeto novo está selecionado.
3. Menu ☰ → **APIs e serviços → Biblioteca** → pesquise **YouTube Data API v3** → **Ativar**.
4. Menu ☰ → **APIs e serviços → Tela de consentimento OAuth** (ou *Google Auth Platform*):
   - Tipo de usuário: **Externo**.
   - Preencha o nome do app e seu e-mail (o resto pode deixar em branco) e salve.
   - Em **Público-alvo / Usuários de teste**, adicione **o seu próprio e-mail**.
5. Menu ☰ → **APIs e serviços → Credenciais → Criar credenciais → ID do cliente OAuth**:
   - Tipo de aplicativo: **TVs e dispositivos de entrada limitada**.
   - Clique em **Criar** e copie o **ID do cliente** e a **Chave secreta do cliente**.

### 7.2 Fazer o login

1. Dê dois cliques em **`configurar_login.bat`**.
2. Cole o **ID do cliente** e a **Chave secreta** quando pedir.
3. Vai abrir uma página do Google: entre na sua conta, digite o código que aparece na janela preta e autorize.
   Se aparecer *"O Google não verificou este app"*, clique em **Avançado → Acessar (não seguro)**.
   O "app" é você mesmo, então é seguro.
4. Volte na janela preta e aperte **Enter**.
5. Feche e abra de novo o `iniciar_servidor.bat`.

### 7.3 Evitar que o login expire a cada 7 dias

Enquanto o projeto do Google estiver em **modo de teste**, o Google derruba o login a cada 7 dias.
Para não ter que refazer toda semana:

- Em **Tela de consentimento OAuth / Público-alvo**, clique em **Publicar app** → **Confirmar**.
  (Não precisa enviar para verificação; para uso pessoal basta publicar.)
- Depois de publicar, rode o `configurar_login.bat` mais uma vez.

> 🔒 Os arquivos `oauth.json` e `oauth_client.json` são o seu login. **Não compartilhe.**
> Eles já estão no `.gitignore` e não vão para o GitHub.

---

## Problemas comuns

| Problema | O que fazer |
|---|---|
| O app não conecta / tela branca | Confira se o `iniciar_servidor.bat` está aberto e se o celular está no **mesmo Wi-Fi**. |
| Conectava e parou de conectar | O IP do PC mudou. Veja o endereço novo na janela do servidor e corrija no app. |
| Não conecta nunca | Firewall: no Windows, a rede Wi-Fi tem que estar como **Rede privada** (*Configurações → Rede e Internet → Wi-Fi → propriedades*). Teste também abrir `http://IP:5000` no navegador do celular. |
| Aviso "O YouTube Music não respondeu" | O YouTube Music Desktop está fechado ou o plugin **API Server** está desligado (Passo 2). |
| Botões não fazem nada | No plugin API Server, a opção de autorização precisa estar em **Não autorizar**. |
| "Python não encontrado" | Reinstale o Python marcando **Add python.exe to PATH**. |
| Aba Listas diz "login expirado" | Rode o `configurar_login.bat` de novo (e veja o passo 7.3). |
| Volume no app diferente do PC | Limitação da API do YouTube Music: o app mostra o último volume escolhido nele. |

---

## Para desenvolvedores

| Arquivo | Pra que serve |
|---|---|
| `servidor.py` | Servidor Flask + a tela de controle (o HTML está dentro do arquivo). |
| `iniciar_servidor.bat` | Cria o `.venv` na primeira vez e inicia o servidor. |
| `configurar_login.py` / `.bat` | Cria o `oauth.json` (login das playlists). |
| `app-android/` | App Android (Java): só abre a tela do servidor e guarda o IP do PC. |

- Mudou o `servidor.py`? É só reiniciar o servidor; **não precisa recompilar o app**.
- **Compilar o APK**: abra a pasta `app-android` no Android Studio →
  menu **Build → Generate App Bundles or APKs → Generate APKs**. O arquivo sai como `app-debug.apk`.
- Servidor sem o `.bat`:
  ```
  python -m venv .venv
  .venv\Scripts\pip install -r requirements.txt
  .venv\Scripts\python servidor.py
  ```
