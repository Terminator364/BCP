package com.blessing.rescuebridge;

import android.app.Activity;
import android.content.Intent;
import android.database.Cursor;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.provider.OpenableColumns;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Owner-only Android SAF file upload. User selects an actual document and
 * explicitly confirms the Windows target. No remote write without the
 * individually authenticated and locally enrolled owner device.
 */
public final class BCPG4FileTransferActivity extends Activity {
    private static final int PICK_DOCUMENT=2301;
    private final ExecutorService io=Executors.newSingleThreadExecutor();
    private Uri source;
    private TextView status,selected;
    private EditText target;
    private Button send;
    private boolean busy=false;

    private TextView info(String s,int size){
        TextView t=new TextView(this);
        t.setText(s);t.setTextSize(size);t.setTextColor(Color.rgb(30,52,72));
        t.setPadding(0,8,0,12);
        return t;
    }
    private Button action(String label,Runnable runnable){
        Button b=new Button(this);
        b.setText(label);b.setAllCaps(false);
        b.setMinHeight(56);b.setOnClickListener(v->runnable.run());
        return b;
    }
    private void message(String text){
        runOnUiThread(()->{
            if(status!=null)status.setText(text);
        });
    }
    private void finishBusy(){
        runOnUiThread(()->{
            busy=false;
            if(send!=null)send.setEnabled(source!=null);
        });
    }
    @Override public void onCreate(Bundle state){
        super.onCreate(state);
        if(state!=null){
            String raw=state.getString("source");
            if(raw!=null)source=Uri.parse(raw);
        }
        ScrollView scroll=new ScrollView(this);
        LinearLayout panel=new LinearLayout(this);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setBackgroundColor(Color.rgb(245,247,250));
        panel.setPadding(32,36,32,32);
        scroll.addView(panel);
        panel.addView(info("BCP · Fichiers Windows",23));
        panel.addView(info("Envoi sécurisé vers MBMPC. Sélectionne un document "
                +"sur ce téléphone, choisis son dossier Windows et confirme "
                +"l'envoi. Chaque fichier utilise un transfert reprenable "
                +"et un contrôle SHA-256 intégral.",14));
        panel.addView(action("1 · Sélectionner un fichier Android",this::selectDocument));
        selected=info(source==null?"Aucun fichier sélectionné.":"Fichier : "+source,14);
        selected.setTextIsSelectable(true);
        panel.addView(selected);
        panel.addView(info("2 · Destination complète sur MBMPC",14));
        target=new EditText(this);
        target.setSingleLine(true);
        target.setTextSize(14);
        target.setHint("C:\\Users\\Lenovo\\Downloads\\document.pdf");
        if(state!=null)target.setText(state.getString("target",""));
        panel.addView(target);
        panel.addView(info("La destination doit déjà avoir un dossier parent existant. "
                +"Un fichier existant ne sera jamais écrasé automatiquement. "
                +"L'appairage G2 seul ne suffit pas : le profil G4 doit être validé sur Windows.",13));
        send=action("3 · Envoyer le fichier sélectionné",this::upload);
        send.setEnabled(source!=null);
        panel.addView(send);
        status=info("Aucun transfert en cours.",15);
        status.setTextIsSelectable(true);
        panel.addView(status);
        panel.addView(action("Retour",this::finish));
        setContentView(scroll);
    }
    private void selectDocument(){
        if(busy)return;
        Intent picker=new Intent(Intent.ACTION_OPEN_DOCUMENT);
        picker.setType("*/*");
        picker.addCategory(Intent.CATEGORY_OPENABLE);
        picker.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION |
                        Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
        startActivityForResult(picker,PICK_DOCUMENT);
    }
    private String displayName(Uri uri){
        try(Cursor cursor=getContentResolver().query(uri,
            new String[]{OpenableColumns.DISPLAY_NAME},null,null,null)){
            if(cursor!=null&&cursor.moveToFirst()){
                String raw=cursor.getString(0);
                if(raw!=null&&!raw.isEmpty()){
                    String safe=raw.replaceAll("[<>:\\\\/|?*\\p{Cntrl}]","_");
                    safe=safe.replaceAll("[. ]+$","").trim();
                    if(!safe.isEmpty()&&safe.length()<=120)return safe;
                }
            }
        }catch(Exception ignored){}
        return "bcp-document.bin";
    }
    @Override protected void onActivityResult(int requestCode,int resultCode,Intent data){
        super.onActivityResult(requestCode,resultCode,data);
        if(requestCode!=PICK_DOCUMENT||resultCode!=RESULT_OK||
           data==null||data.getData()==null)return;
        source=data.getData();
        try{
            int flags=data.getFlags()&Intent.FLAG_GRANT_READ_URI_PERMISSION;
            if(flags!=0)getContentResolver().takePersistableUriPermission(source,flags);
        }catch(SecurityException ignored){
            // The active grant still works while the activity runs.
        }
        String name=displayName(source);
        selected.setText("Fichier sélectionné : "+name);
        if(target.getText().toString().trim().isEmpty())
            target.setText("C:\\Users\\Lenovo\\Downloads\\"+name);
        send.setEnabled(true);
        status.setText("Fichier prêt. Vérifie la destination Windows puis confirme.");
    }
    private void upload(){
        if(busy||source==null)return;
        final Uri selectedUri=source;
        final String destination=target.getText().toString().trim();
        if(destination.isEmpty()){
            status.setText("Destination Windows obligatoire.");return;
        }
        busy=true;send.setEnabled(false);
        message("Vérification de l'intégrité du fichier…");
        io.execute(()->{
            try{
                org.json.JSONObject done=BCPG4FileUploader.upload(
                    this,selectedUri,destination,false,null,(sent,total)->
                       message("Envoi sécurisé : "+sent+" / "+total+
                               " octets. Reprise possible après coupure."));
                message("Transfert confirmé par MBMPC. SHA-256 : "+
                    done.getString("sha256")+
                    "\nFichier : "+done.getString("path"));
            }catch(Exception ex){
                message("Transfert non terminé : "+ex.getClass().getSimpleName()+
                    ". Rien n'est validé sur Windows sans SHA-256 correct. "
                    +"Rouvre le même fichier pour reprendre, ou vérifie ton profil G4.");
            }finally{finishBusy();}
        });
    }
    @Override protected void onSaveInstanceState(Bundle out){
        super.onSaveInstanceState(out);
        if(source!=null)out.putString("source",source.toString());
        if(target!=null)out.putString("target",target.getText().toString());
    }
    @Override protected void onDestroy(){
        io.shutdown();
        super.onDestroy();
    }
}
