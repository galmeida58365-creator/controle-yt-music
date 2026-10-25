# Política de Privacidade: Controle de Musica

*Última atualização: 25 de outubro de 2026*

O **Controle de Musica** (projeto [controle-yt-music](https://github.com/galmeida58365-creator/controle-yt-music)) é um programa de código aberto que cada pessoa roda **no próprio computador** para controlar o YouTube Music Desktop pelo celular.

## Quais dados o app acessa
Quando você ativa a aba de playlists, o app pede permissão à sua conta Google (escopo `https://www.googleapis.com/auth/youtube`) **apenas para listar as suas playlists e as músicas delas**, usando a API oficial do YouTube (YouTube Data API v3). O app não publica, altera ou apaga nada na sua conta.

## Onde os dados ficam
- O login (token de acesso) fica salvo **somente no seu computador**, no arquivo `oauth.json`, dentro da pasta do programa.
- As informações das playlists são mostradas na tela do seu celular, que se conecta direto ao seu PC pela sua rede Wi-Fi.
- **Nenhum dado é enviado para servidores do desenvolvedor ou de terceiros.** Não existe servidor central: cada pessoa roda a sua própria cópia.
- O app não usa cookies de rastreamento, anúncios ou análise de uso.

## Como remover o acesso
- Apague o arquivo `oauth.json` da pasta do programa; e/ou
- Revogue o acesso em [myaccount.google.com/permissions](https://myaccount.google.com/permissions).

## Uso dos dados do Google
O uso de informações recebidas das APIs do Google segue a [Política de Dados do Usuário dos Serviços de API do Google](https://developers.google.com/terms/api-services-user-data-policy), incluindo os requisitos de Uso Limitado.

## Contato
Dúvidas: abra uma *issue* em [github.com/galmeida58365-creator/controle-yt-music/issues](https://github.com/galmeida58365-creator/controle-yt-music/issues).
