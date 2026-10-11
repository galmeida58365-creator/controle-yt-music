package com.guigu.controleytmusic;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.text.InputType;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

public class MainActivity extends Activity {

    private static final String PREFS = "config";
    private static final String CHAVE_URL = "url";
    private static final String ENDERECO_PADRAO = "192.168.100.49:5000";
    private static final int PORTA_PADRAO = 5000;
    private static final int COR_FUNDO = 0xFF121212;

    private WebView webView;
    private LinearLayout telaErro;
    private TextView textoErro;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(COR_FUNDO);
        getWindow().setNavigationBarColor(COR_FUNDO);

        FrameLayout raiz = new FrameLayout(this);
        raiz.setBackgroundColor(COR_FUNDO);
        raiz.setFitsSystemWindows(true);

        webView = new WebView(this);
        webView.setBackgroundColor(COR_FUNDO);
        WebSettings ajustes = webView.getSettings();
        ajustes.setJavaScriptEnabled(true);
        ajustes.setDomStorageEnabled(true);
        // Necessario para os alert() da pagina aparecerem
        webView.setWebChromeClient(new WebChromeClient());
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onReceivedError(WebView view, WebResourceRequest req, WebResourceError erro) {
                if (req.isForMainFrame()) {
                    mostrarErro("Não consegui conectar em\n" + urlSalva()
                            + "\n\nVerifique se o servidor está rodando no PC"
                            + " e se o celular está no mesmo Wi-Fi.");
                }
            }
        });
        raiz.addView(webView, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));

        telaErro = criarTelaErro();
        telaErro.setVisibility(View.GONE);
        raiz.addView(telaErro, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));

        TextView engrenagem = new TextView(this);
        engrenagem.setText("⚙");
        engrenagem.setTextColor(Color.parseColor("#888888"));
        engrenagem.setTextSize(TypedValue.COMPLEX_UNIT_SP, 22);
        engrenagem.setPadding(dp(14), dp(8), dp(14), dp(8));
        engrenagem.setOnClickListener(v -> pedirEndereco());
        raiz.addView(engrenagem, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.WRAP_CONTENT, FrameLayout.LayoutParams.WRAP_CONTENT,
                Gravity.TOP | Gravity.END));

        setContentView(raiz);

        if (urlSalva() == null) {
            pedirEndereco();
        } else {
            carregar();
        }
    }

    private LinearLayout criarTelaErro() {
        LinearLayout tela = new LinearLayout(this);
        tela.setOrientation(LinearLayout.VERTICAL);
        tela.setGravity(Gravity.CENTER);
        tela.setBackgroundColor(COR_FUNDO);
        tela.setPadding(dp(30), dp(30), dp(30), dp(30));

        textoErro = new TextView(this);
        textoErro.setTextColor(Color.WHITE);
        textoErro.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16);
        textoErro.setGravity(Gravity.CENTER);
        tela.addView(textoErro);

        Button tentar = new Button(this);
        tentar.setText("Tentar de novo");
        tentar.setOnClickListener(v -> carregar());
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(24);
        tela.addView(tentar, lp);

        Button mudar = new Button(this);
        mudar.setText("Mudar endereço do PC");
        mudar.setOnClickListener(v -> pedirEndereco());
        tela.addView(mudar);

        return tela;
    }

    private void carregar() {
        String url = urlSalva();
        if (url == null) return;
        telaErro.setVisibility(View.GONE);
        webView.setVisibility(View.VISIBLE);
        webView.loadUrl(url);
    }

    private void mostrarErro(String mensagem) {
        textoErro.setText(mensagem);
        webView.setVisibility(View.INVISIBLE);
        telaErro.setVisibility(View.VISIBLE);
    }

    private void pedirEndereco() {
        final boolean primeiraVez = urlSalva() == null;

        final EditText campo = new EditText(this);
        campo.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        campo.setSingleLine(true);
        String atual = primeiraVez ? ENDERECO_PADRAO : urlSalva().replaceFirst("^https?://", "");
        campo.setText(atual);
        campo.setSelection(atual.length());

        FrameLayout caixa = new FrameLayout(this);
        caixa.setPadding(dp(20), dp(8), dp(20), 0);
        caixa.addView(campo);

        AlertDialog.Builder dialogo = new AlertDialog.Builder(this)
                .setTitle("Endereço do PC")
                .setMessage("Digite o IP e a porta que aparecem no terminal do servidor.\nEx: 192.168.100.49:5000")
                .setView(caixa)
                .setCancelable(!primeiraVez)
                .setPositiveButton("Conectar", (d, w) -> {
                    String url = normalizar(campo.getText().toString());
                    if (url == null) {
                        pedirEndereco();
                        return;
                    }
                    getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString(CHAVE_URL, url).apply();
                    carregar();
                });
        if (!primeiraVez) {
            dialogo.setNegativeButton("Cancelar", null);
        }
        dialogo.show();
    }

    // Aceita "192.168.0.10", "192.168.0.10:5000" ou "http://..." e devolve uma URL completa
    private static String normalizar(String texto) {
        String t = texto.trim();
        if (t.isEmpty()) return null;
        if (!t.startsWith("http://") && !t.startsWith("https://")) {
            t = "http://" + t;
        }
        Uri uri = Uri.parse(t);
        if (uri.getHost() == null || uri.getHost().isEmpty()) return null;
        int porta = uri.getPort() == -1 ? PORTA_PADRAO : uri.getPort();
        return uri.getScheme() + "://" + uri.getHost() + ":" + porta + "/";
    }

    private String urlSalva() {
        SharedPreferences prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        return prefs.getString(CHAVE_URL, null);
    }

    private int dp(int valor) {
        return Math.round(valor * getResources().getDisplayMetrics().density);
    }

    @Override
    protected void onDestroy() {
        webView.destroy();
        super.onDestroy();
    }
}
