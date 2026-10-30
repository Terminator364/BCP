package com.blessing.rescuebridge;

import android.app.Activity;
import android.graphics.Color;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * One-time owner enrollment. No automatic permissions, no copied secrets.
 * Windows-local consent and six-digit challenge verification remain mandatory.
 */
public final class BCPG4EnrollmentActivity extends Activity {
    private final ExecutorService io=Executors.newSingleThreadExecutor();
    private TextView status;
    private boolean busy;
    private final int ink=Color.rgb(25,42,63), muted=Color.rgb(93,111,130);

    private TextView label(String s,int sp,boolean strong){
        TextView t=new TextView(this);
        t.setText(s);t.setTextSize(sp);t.setTextColor(strong?ink:muted);
        t.setPadding(0,12,0,14);
        return t;
    }
    private Button button(String name,Runnable action){
        Button b=new Button(this);
        b.setAllCaps(false);b.setText(name);b.setTextSize(15);
        b.setMinHeight(55);
        b.setOnClickListener(v->action.run());
        return b;
    }
    private void output(String message){
        runOnUiThread(()->{
            busy=false;
            if(status!=null)status.setText(message);
        });
    }
    @Override public void onCreate(Bundle bundle){
        super.onCreate(bundle);
        ScrollView scroller=new ScrollView(this);
        LinearLayout body=new LinearLayout(this);
        body.setOrientation(LinearLayout.VERTICAL);
        body.setBackgroundColor(Color.rgb(245,247,250));
        body.setPadding(30,38,30,30);
        scroller.addView(body);
        body.addView(label("BCP  /  G4",13,true));
        body.addView(label("Mon appareil de confiance",24,true));
        body.addView(label("Cet écran prépare une identité individuelle pour ce téléphone. "
                +"L'appairage G2 existant ne suffit pas à obtenir des droits Windows.",
                15,false));
        body.addView(label("1. Demande un code depuis ce Samsung.\n"
                +"2. Sur MBMPC, ouvre « BCP - Profil proprietaire ».\n"
                +"3. Sélectionne ce téléphone et saisis le code affiché ici.\n"
                +"4. Confirme personnellement sur Windows.\n"
                +"5. Vérifie ensuite l'accès propriétaire depuis ce téléphone.",
                15,false));
        body.addView(button("1 · Demander mon code unique",this::request));
        body.addView(button("2 · Vérifier les droits depuis Samsung",this::probe));
        status=label("Aucun droit n'est accordé automatiquement.",16,true);
        status.setTextIsSelectable(true);
        body.addView(status);
        body.addView(label("Les clés restent protégées sur Android. Les autorisations "
                +"sont individuelles et révocables sur MBMPC. Les commandes Windows "
                +"sensibles conservent les protections Windows et UAC.",13,false));
        body.addView(button("Retour à BCP",this::finish));
        setContentView(scroller);
    }
    private void request(){
        if(busy)return;
        busy=true;
        status.setText("Connexion à MBMPC et préparation de la demande…");
        io.execute(()->{
            try{
                String code=BCPG4DeviceEnrollment.request(this);
                output("Code à saisir sur MBMPC : "+code+
                    "\n\nOuvre « BCP - Profil proprietaire ». "
                    +"Ce code ne donne aucun accès sans ta confirmation Windows.");
            }catch(Exception ex){
                output("Demande en attente ou indisponible : "+
                    ex.getClass().getSimpleName()+
                    ". Vérifie le lien G2/Tailscale et les demandes déjà en attente.");
            }
        });
    }
    private void probe(){
        if(busy)return;
        busy=true;
        status.setText("Validation des signatures propriétaires…");
        io.execute(()->{
            try{
                int count=BCPG4DeviceEnrollment.checkOwnedWindowsDrives(this);
                output("G4 confirmé : "+count+" lecteur(s) Windows accessibles "
                      +"avec cette identité individuelle.");
            }catch(Exception ex){
                output("Accès propriétaire non confirmé : "+
                    ex.getClass().getSimpleName()+
                    ". Vérifie la confirmation sur Windows ou la connexion.");
            }
        });
    }
    @Override protected void onDestroy(){
        io.shutdownNow();
        super.onDestroy();
    }
}
