# cash-b app (Android)

Wrapper nativo Android do site cash-b.com, feito com [Capacitor](https://capacitorjs.com/).
Carrega o site de verdade dentro de uma WebView — não duplica nenhuma
funcionalidade, então qualquer atualização do site aparece automaticamente no
app, sem precisar gerar nova versão.

## Como funciona

- `capacitor.config.json` aponta `server.url` pra `https://cash-b.com` — o app
  é, na prática, uma casca nativa em volta do site.
- Links pra fora de cash-b.com (ex: ao gerar cashback e cair na Shopee) abrem
  automaticamente no navegador/app padrão do celular, igual já acontece no
  navegador normal — não é preciso nenhuma configuração extra pra isso.
- Ícone gerado a partir de `static/icons/icon-512.png` (o mesmo ícone do PWA
  do site).

## Pré-requisitos pra compilar

- [Android Studio](https://developer.android.com/studio) instalado (grátis) —
  já vem com o Android SDK, não precisa instalar mais nada.

## Como gerar um APK de teste (pra instalar direto no seu celular)

1. `File > Open` no Android Studio, selecionar a pasta `mobile-app/android`.
2. Esperar o Gradle sincronizar sozinho (a primeira vez demora alguns
   minutos, ele baixa dependências).
3. Conectar o celular via USB (com "Depuração USB" ativada nas Opções do
   desenvolvedor) ou usar um emulador.
4. Clicar no botão verde "Run" (▶) — instala e abre o app direto no celular.

## Como gerar o pacote pra subir na Play Store (.aab)

1. `Build > Generate Signed Bundle / APK`.
2. Escolher **Android App Bundle**.
3. Criar uma chave de assinatura nova (`Create new...`) — **guarde o arquivo
   `.jks` gerado e a senha num lugar seguro** (gerenciador de senhas, HD
   externo). Se perder esse arquivo, não tem como atualizar o app depois —
   só criando um app novo do zero na Play Store.
4. Build type `release`.
5. O `.aab` gerado vai em `android/app/release/` — é esse arquivo que se sobe
   no [Google Play Console](https://play.google.com/console/), em "Versões de
   produção" (ou primeiro em "Teste interno", recomendado pra testar antes de
   publicar de vez pra todo mundo).

## Ícone da Play Store

`play_store_icon_512.png` (nesta pasta) já está no tamanho exato exigido
(512x512) pra subir direto no formulário de "Detalhes do app" do Play
Console.

## Atualizar o ícone (se o design mudar no futuro)

Substitua `static/icons/icon-512.png` (na raiz do repo) e rode de novo:

```
cd mobile-app
python3 gen_icons.py
```

## Limitações conhecidas desse tipo de app (wrapper via WebView)

- **Notificações push:** se o site tiver push notification via navegador (Web
  Push/VAPID), elas não funcionam dentro dessa WebView do mesmo jeito que
  funcionam num navegador de verdade — não é bug, é limitação de WebView. Se
  isso for importante no futuro, dá pra adicionar push nativo de verdade
  (`@capacitor/push-notifications`), mas é um projeto à parte.
- **Precisa de internet:** como o app carrega o site ao vivo, não funciona
  offline (mesma limitação do site hoje).
- Configurado só pra **Android** por enquanto, como combinado — nada aqui
  impede adicionar iOS depois (`npx cap add ios`), só precisa de um Mac com
  Xcode pra compilar.
