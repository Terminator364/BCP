package com.blessing.rescuebridge;

import android.app.Activity;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** One automatic handshake on launch; no repeated buttons or manual code entry. */
public final class BCPG4EnrollmentActivity extends Activity {
    private final ExecutorService io=Executors.newSingleThreadExecutor();
    private final Handler ui=new Handler(Looper.getMainLooper());
    private TextView status;
    private Button retry;
    private boolean busy=false,destroyed=false,authorized=false;
    private final int ink=Color.rgb(24,39,61),muted=Color.rgb(93,108,122);
    private final Runnable polling=new Runnable(){
        @Override public void run(){
            if(destroyed||authorized)return;
            probe(false);
            ui.postDelayed(this,8000);
        }
    };

    private TextView label(String s,int size,boolean strong){
        TextView t=new TextView(this);
        t.setText(s);t.setTextSize(size);t.setTextColor(strong?ink:muted);
        t.setPadding(0,12,0,14);return t;
    }
    private void show(String text){
        ui.post(()->{
            if(destroyed)return;
            status.setText(text);
        });
    }
    private static String reason(Exception ex){
        String e=ex.getMessage();
        if(e==null)e="";
        if(e.contains("BCP_HTTP_401"))return "Identité non encore autorisée.";
        if(e.contains("BCP_HTTP_403"))return "Autorisation Windows encore nécessaire.";
        if(e.contains("BCP_HTTP_400"))return "Le PC a refusé la demande. Réessaie après la reconnexion.";
        if(e.contains("G2_PAIRING_REQUIRED"))return "Appairage du téléphone indisponible.";
        if(ex instanceof java.net.UnknownHostException)return "Nom du PC introuvable ; réseau à vérifier.";
        if(ex instanceof java.net.SocketTimeoutException)return "Le PC ne répond pas ; la connexion sera retentée.";
        if(ex instanceof javax.net.ssl.SSLException)return "Connexion chiffrée refusée : certificat du PC à vérifier.";
        if(ex instanceof SecurityException)return "Contrôle d'identité refusé : aucune autorisation accordée.";
        return "Connexion BCP indisponible. Nouvelle tentative automatique.";
    }
    @Override public void onCreate(Bundle state){
        super.onCreate(state);
        ScrollView scroller=new ScrollView(this);
        LinearLayout panel=new LinearLayout(this);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setBackgroundColor(Color.rgb(246,248,251));
        panel.setPadding(32,38,32,30);
        scroller.addView(panel);
        panel.addView(label("BCP  /  MON SAMSUNG",14,true));
        panel.addView(label("Connexion propriétaire",25,true));
        panel.addView(label("La vérification démarre automatiquement. "
               +"Tu ne dois confirmer le téléphone sur Windows qu'une seule fois.",15,false));
        status=label("Recherche de MBMPC…",17,true);
        status.setTextIsSelectable(true);
        panel.addView(status);
        panel.addView(label("Si un code apparaît, ouvre le Centre de contrôle BCP "
              +"sur MBMPC. Compare le code montré sur les deux écrans, "
              +"puis confirme une seule fois sur le PC. La connexion sera "
              +"reconnue automatiquement.",14,false));
        retry=new Button(this);
        retry.setAllCaps(false);
        retry.setText("Réessayer maintenant");
        retry.setOnClickListener(v->handshake());
        panel.addView(retry);
        setContentView(scroller);
        handshake();
        ui.postDelayed(polling,8000);
    }
    private void handshake(){
        if(busy||authorized||destroyed)return;
        busy=true;
        show("Vérification sécurisée de ce téléphone…");
        io.execute(()->{
            try{
                int drives=BCPG4DeviceEnrollment.checkOwnedWindowsDrives(this);
                authorized=true;
                show("Connecté automatiquement à MBMPC. "+drives+
                    " lecteur(s) Windows accessibles.");
            }catch(Exception notTrusted){
                try{
                    String code=BCPG4DeviceEnrollment.request(this);
                    if("ALREADY_ENROLLED".equals(code))
                        show("Téléphone reconnu. La confirmation du profil sur "
                            +"Windows reste à effectuer une seule fois.");
                    else show("Code de contrôle : "+code+
                        "\n\nCompare-le à celui du Centre de contrôle BCP sur MBMPC "
                        +"et autorise ce Samsung une seule fois.");
                }catch(Exception failed){
                    show(reason(failed));
                }
            }finally{busy=false;}
        });
    }
    private void probe(boolean showErrors){
        if(busy||authorized||destroyed)return;
        busy=true;
        io.execute(()->{
            try{
                int count=BCPG4DeviceEnrollment.checkOwnedWindowsDrives(this);
                authorized=true;
                show("Appareil approuvé. Connexion automatique à "+count+
                    " lecteur(s) Windows.");
            }catch(Exception ex){
                if(showErrors)show(reason(ex));
            }finally{busy=false;}
        });
    }
    @Override protected void onDestroy(){
        destroyed=true;
        ui.removeCallbacks(polling);
        io.shutdownNow();
        super.onDestroy();
    }
}
