const $=s=>document.querySelector(s), all=s=>[...document.querySelectorAll(s)];
async function api(path,opt={}){const r=await fetch(path,{headers:{"Content-Type":"application/json"},...opt});const d=await r.json();if(!r.ok)throw Error(d.error||"Falha");return d}
function toast(s){const t=$("#toast");t.textContent=s;t.classList.add("show");setTimeout(()=>t.classList.remove("show"),2500)}
function esc(s){return String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
function bytes(n){return n<1024?n+" B":n<1048576?(n/1024).toFixed(1)+" KB":(n/1048576).toFixed(2)+" MB"}
function show(v){all(".view").forEach(x=>x.classList.toggle("active",x.id===v));all(".nav").forEach(x=>x.classList.toggle("active",x.dataset.view===v));const titles={overview:"Visão geral",chat:"Conversar",learning:"Aprendizagem",library:"Biblioteca privada",frameworks:"Frameworks de IA",huggingface:"Hugging Face",diagnostics:"Diagnóstico"};$("#title").textContent=titles[v];if(v==="library")loadLibrary();if(v==="frameworks")loadFrameworks();if(v==="huggingface")loadHuggingFaceStatus();if(v==="diagnostics")loadDiagnostics()}
all(".nav").forEach(b=>b.onclick=()=>show(b.dataset.view));all("[data-go]").forEach(b=>b.onclick=()=>show(b.dataset.go));
async function loadStatus(){try{const d=await api("/api/status"),s=d.library;$("#knowledge").textContent=d.knowledge;$("#messages").textContent=d.messages;$("#documents").textContent=s.documents;$("#chunks").textContent=s.chunks;$("#python").textContent=d.python;$("#platform").textContent=d.platform;$("#cpu").textContent=d.cpu;$("#learn-knowledge").textContent=d.knowledge;$("#learn-docs").textContent=s.documents;$("#lib-docs").textContent=s.documents;$("#lib-chunks").textContent=s.chunks;$("#lib-size").textContent=bytes(s.database_bytes)}catch(e){toast(e.message)}}
async function loadLibrary(){await loadStatus();const d=await api("/api/library");$("#results").innerHTML=d.documents.length?d.documents.map(x=>'<div class="result"><b>'+esc(x.title)+'</b><small>'+x.chunks+' trechos · '+bytes(x.bytes)+'</small></div>').join(""):"Nenhum documento importado."}
async function searchLibrary(){const q=$("#query").value.trim();if(!q)return;try{const d=await api("/api/library/search",{method:"POST",body:JSON.stringify({query:q})});$("#results").innerHTML=d.results.length?d.results.map(x=>'<div class="result"><b>'+esc(x.title)+'</b><p>'+esc(x.content)+'</p></div>').join(""):"Nenhum trecho encontrado."}catch(e){toast(e.message)}}
$("#search").onclick=searchLibrary;$("#query").onkeydown=e=>{if(e.key==="Enter")searchLibrary()};
$("#file").onchange=async e=>{const f=e.target.files[0];if(!f)return;if(f.size>5242880){toast("Arquivo acima de 5 MB.");return}try{const d=await api("/api/library/import",{method:"POST",body:JSON.stringify({name:f.name,content:await f.text()})});toast("Importados: "+d.imported.length+" · ignorados: "+d.skipped.length);loadLibrary()}catch(x){toast(x.message)}e.target.value=""};
function addBubble(role,msg){const box=document.createElement("div");box.className="bubble "+role;const label=document.createElement("small");label.textContent=role==="nix"?"NIXLMs · AGENTE LOCAL":"VOCÊ";const p=document.createElement("p");p.textContent=msg;box.append(label,p);$("#thread").append(box);$("#thread").scrollTop=$("#thread").scrollHeight}
$("#chat-form").onsubmit=async e=>{e.preventDefault();const input=$("#message"),msg=input.value.trim();if(!msg)return;addBubble("user",msg);input.value="";try{const d=await api("/api/chat",{method:"POST",body:JSON.stringify({message:msg})});addBubble("nix",d.reply);loadStatus()}catch(x){addBubble("nix","Falha: "+x.message)}};
async function loadFrameworks(){const box=$("#framework-list");box.textContent="Consultando inventário...";try{const d=await api("/api/frameworks");box.innerHTML=d.map(x=>'<article class="panel card"><div><b>'+esc(x.name)+'</b><small>'+esc(x.purpose)+'</small></div><span class="pill '+(x.installed?"ok":"off")+'">'+(x.installed?"INSTALADO "+esc(x.version||""):"NÃO INSTALADO")+'</span></article>').join("")}catch(e){box.textContent=e.message}}
async function loadDiagnostics(){try{const d=await api("/api/diagnostics");$("#diag-summary").textContent=d.ok?"Todas as verificações obrigatórias passaram.":(d.status==="failed"?"Falha em uma ou mais verificações.":"Sistema operacional com avisos; consulte os itens abaixo.");$("#diag-list").innerHTML=Object.entries(d.checks).map(([k,v])=>{const info=v.status==="info",good=v.status==="ok"||info;const label=info?"INFO":(good?"OK":"ATENÇÃO");return '<article class="panel card diagnostic"><span class="icon '+(good?"":"fail")+'">'+(info?"i":(good?"✓":"!"))+'</span><div><b>'+esc(k.replaceAll("_"," "))+'</b><small>'+esc(v.detail)+'</small></div><span class="pill '+(good?"ok":"off")+'">'+label+'</span></article>'}).join("")}catch(e){$("#diag-summary").textContent=e.message}}
$("#run").onclick=loadDiagnostics;$("#refresh").onclick=()=>loadStatus().then(()=>toast("Painel atualizado."));$("#framework-refresh").onclick=loadFrameworks;
function clock(){$("#clock").textContent=new Date().toLocaleTimeString("pt-BR")}clock();setInterval(clock,1000);loadStatus();

let hfSelected=null;
async function loadHuggingFaceStatus(){
 try{
  const d=await api("/api/huggingface/status");
  $("#hf-anonymous").textContent=d.anonymous_public_access?"ATIVO":"INDISPONÍVEL";
  $("#hf-download-support").textContent=d.download_support?"DISPONÍVEL":"INSTALAR";
  $("#hf-inference-support").textContent=d.inference_support?"DISPONÍVEL":"INSTALAR";
  $("#hf-active").textContent="Geração: "+(d.active_model?.repo_id||"—")+" · Embeddings: "+(d.active_encoder?.repo_id||"—");
  $("#hf-status").textContent="Acesso anônimo: sem token · Inferência hospedada: desativada · Visão: "+(d.active_perception?.vision?.repo_id||"—")+" · Áudio: "+(d.active_perception?.speech?.repo_id||"—")+" · Repositórios locais: "+d.repositories.length;
  $("#hf-local-list").innerHTML=d.repositories.length?d.repositories.map(x=>'<div class="result"><b>'+esc(x.repo_id)+'</b><small>'+esc(x.repo_type)+' · revisão '+esc(String(x.revision||"").slice(0,12))+' · '+bytes(x.downloaded_bytes||0)+'</small></div>').join(""):"Nenhum recurso local registrado.";
  return d;
 }catch(e){$("#hf-status").textContent=e.message;throw e}
}
async function searchHuggingFace(){
 const type=$("#hf-type").value,q=$("#hf-query").value.trim();
 $("#hf-results").textContent="Consultando catálogo público...";
 try{
  const d=await api("/api/huggingface/search?type="+encodeURIComponent(type)+"&q="+encodeURIComponent(q)+"&limit=12");
  $("#hf-results").innerHTML=d.results.length?d.results.map(x=>'<article class="panel card hf-result"><div class="hf-result-head"><b>'+esc(x.id)+'</b><span class="pill">'+esc(x.license||"licença não informada")+'</span></div><div class="hf-result-meta"><span>'+esc(x.pipeline_tag||x.library_name||x.repo_type)+'</span><span>Downloads: '+esc(x.downloads??"—")+'</span><span>Gated: '+(x.gated?"sim":"não")+'</span></div><div class="hf-result-actions"><button class="ghost" data-hf-details="'+esc(x.repo_type)+'" data-repo="'+esc(x.id)+'">Detalhes</button>'+(x.repo_type!=="space"&&!x.private&&!x.gated?'<button class="primary" data-hf-download="'+esc(x.repo_type)+'" data-repo="'+esc(x.id)+'">Baixar</button>':"")+'</div></article>').join(""):"Nenhum recurso público encontrado.";
  all("[data-hf-details]").forEach(b=>b.onclick=()=>showHuggingFaceDetails(b.dataset.hfDetails,b.dataset.repo));
  all("[data-hf-download]").forEach(b=>b.onclick=()=>downloadHuggingFace(b.dataset.hfDownload,b.dataset.repo));
 }catch(e){$("#hf-results").textContent=e.message}
}
async function showHuggingFaceDetails(type,id){
 const box=$("#hf-detail");box.textContent="Consultando detalhes...";
 try{
  const d=await api("/api/huggingface/details?type="+encodeURIComponent(type)+"&repo_id="+encodeURIComponent(id));
  hfSelected={type,id};
  const status=await api("/api/huggingface/status");
  const local=status.repositories.some(x=>x.repo_type===type&&x.repo_id===id);
  const files=(d.siblings||[]).slice(0,20).map(x=>({path:x.path,size:x.size}));
  box.innerHTML='<div class="panel-head">RECURSO · '+esc(type.toUpperCase())+'</div><p><b>'+esc(d.id)+'</b></p><p>Licença: '+esc(d.license||"não informada")+' · Gated: '+esc(String(d.gated))+' · Privado: '+esc(String(d.private))+'</p><p>Tarefa: '+esc(d.pipeline_tag||d.library_name||"não informada")+' · Downloads: '+esc(d.downloads??"—")+' · Likes: '+esc(d.likes??"—")+'</p><p>Revisão SHA: '+esc(d.sha||"não informada")+'</p><p>'+esc(d.description||"Sem descrição no card.")+'</p><pre>'+esc(JSON.stringify(files,null,2))+'</pre><div class="hf-actions">'+(type!=="space"&&!local&&!d.private&&!d.gated?'<button class="primary" id="hf-detail-download">Baixar artefatos permitidos</button>':"")+(type==="model"&&local&&d.pipeline_tag==="text-generation"?'<button class="primary" id="hf-detail-activate">Ativar geração CPU</button>':"")+(type==="model"&&local&&d.library_name==="sentence-transformers"&&["sentence-similarity","feature-extraction"].includes(d.pipeline_tag)?'<button class="primary" id="hf-detail-activate-embeddings">Ativar embeddings CPU</button>':"")+(type==="model"&&local&&d.pipeline_tag==="image-to-text"?'<button class="primary" id="hf-detail-activate-vision">Ativar visão CPU</button>':"")+(type==="model"&&local&&d.pipeline_tag==="automatic-speech-recognition"?'<button class="primary" id="hf-detail-activate-speech">Ativar áudio CPU</button>':"")+'<a class="ghost" href="'+esc(d.url)+'" target="_blank" rel="noopener">Abrir no Hub ↗</a></div>';
  if($("#hf-detail-download"))$("#hf-detail-download").onclick=()=>downloadHuggingFace(type,id);
  if($("#hf-detail-activate"))$("#hf-detail-activate").onclick=()=>activateHuggingFace(id,"generator");
  if($("#hf-detail-activate-embeddings"))$("#hf-detail-activate-embeddings").onclick=()=>activateHuggingFace(id,"embeddings");
  if($("#hf-detail-activate-vision"))$("#hf-detail-activate-vision").onclick=()=>activateHuggingFace(id,"vision");
  if($("#hf-detail-activate-speech"))$("#hf-detail-activate-speech").onclick=()=>activateHuggingFace(id,"speech");
  if($("#hf-detail-activate-embeddings"))$("#hf-detail-activate-embeddings").onclick=()=>activateHuggingFace(id,"embeddings");
 }catch(e){box.textContent=e.message}
}
async function downloadHuggingFace(type,id){
 if(type==="space"){toast("Spaces não são executados nem baixados.");return}
 if(!confirm("Baixar "+id+" para armazenamento local? Modelos: até 1,5 GB; datasets: até 512 MB. Nenhum serviço pago será chamado."))return;
 try{
  toast("Download iniciado; aguarde...");
  const d=await api("/api/huggingface/download",{method:"POST",body:JSON.stringify({repo_type:type,repo_id:id})});
  toast("Download local concluído: "+id);
  await loadHuggingFaceStatus();
  await showHuggingFaceDetails(type,id);
 }catch(e){toast(e.message)}
}
async function activateHuggingFace(id,role="generator"){
 try{
  const d=await api("/api/huggingface/activate",{method:"POST",body:JSON.stringify({repo_id:id,role})});
  toast((role==="embeddings"?"Embeddings":role==="vision"?"Visão":role==="speech"?"Áudio":"Modelo")+" local ativado em CPU: "+(d.active_model?.repo_id||d.active_encoder?.repo_id));
  await loadHuggingFaceStatus();
 }catch(e){toast(e.message)}
}
$("#hf-search").onclick=searchHuggingFace;
$("#hf-query").onkeydown=e=>{if(e.key==="Enter")searchHuggingFace()};
$("#hf-refresh").onclick=()=>loadHuggingFaceStatus().then(()=>toast("Hugging Face atualizado."));
$("#hf-deactivate").onclick=async()=>{try{await api("/api/huggingface/deactivate",{method:"POST",body:JSON.stringify({role:"generator"})});toast("Modelo Hugging Face desativado.");loadHuggingFaceStatus()}catch(e){toast(e.message)}};
$("#hf-deactivate-embedding").onclick=async()=>{try{await api("/api/huggingface/deactivate",{method:"POST",body:JSON.stringify({role:"embeddings"})});toast("Encoder nativo restaurado.");loadHuggingFaceStatus()}catch(e){toast(e.message)}};
$("#hf-deactivate-vision").onclick=async()=>{try{await api("/api/huggingface/deactivate",{method:"POST",body:JSON.stringify({role:"vision"})});toast("Visão local desativada.");loadHuggingFaceStatus()}catch(e){toast(e.message)}};
$("#hf-deactivate-audio").onclick=async()=>{try{await api("/api/huggingface/deactivate",{method:"POST",body:JSON.stringify({role:"speech"})});toast("Áudio local desativado.");loadHuggingFaceStatus()}catch(e){toast(e.message)}};


// Hands-free voice interface: browser STT/TTS, wake phrase and allowlisted UI actions.
(()=>{
 const SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;
 const toggle=$("#voice-toggle"), state=$("#voice-state"), help=$("#voice-help");
 const orb=$("#voice-orb"), repeat=$("#voice-repeat"), mute=$("#voice-mute");
 if(!toggle||!state)return;
 let recognition=null, listening=false, muted=false, speaking=false, lastSpoken="";
 let pendingVoiceAction=null, restartTimer=null;
 const say=(message)=>{
  lastSpoken=String(message||"").trim();
  if(!lastSpoken||muted||!("speechSynthesis" in window))return;
  window.speechSynthesis.cancel();
  if(recognition&&listening){try{recognition.stop()}catch(e){}}
  const utterance=new SpeechSynthesisUtterance(lastSpoken);
  utterance.lang="pt-BR"; utterance.rate=1.02; utterance.pitch=1;
  const voices=window.speechSynthesis.getVoices();
  utterance.voice=voices.find(v=>/^pt-BR$/i.test(v.lang))||voices.find(v=>/^pt/i.test(v.lang))||null;
  utterance.onstart=()=>{speaking=true;orb.classList.add("speaking")};
  const resumeAfterSpeech=()=>{speaking=false;orb.classList.remove("speaking");if(listening&&recognition){restartTimer=setTimeout(()=>{try{recognition.start()}catch(e){}},350)}};
  utterance.onend=resumeAfterSpeech;
  utterance.onerror=resumeAfterSpeech;
  speaking=true;
  window.speechSynthesis.speak(utterance);
 };
 const setState=(label,detail)=>{
  state.textContent=label;help.textContent=detail;
  orb.classList.toggle("listening",listening);
  toggle.textContent=listening?"Desativar microfone":"Ativar microfone";
  toggle.classList.toggle("danger",listening);
 };
 const normalizeVoice=s=>String(s||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase().replace(/[^\p{L}\p{N}\s]/gu," ").replace(/\s+/g," ").trim();
 const speakAndShow=(message)=>{addBubble("nix",message);say(message)};
 const postChat=async(message)=>{
  addBubble("user","🎙️ "+message);
  try{
   const d=await api("/api/chat",{method:"POST",body:JSON.stringify({message})});
   addBubble("nix",d.reply);loadStatus();say(d.reply);
  }catch(e){speakAndShow("Não consegui processar a solicitação: "+e.message)}
 };
 const stopListening=()=>{
  listening=false;
  if(restartTimer)clearTimeout(restartTimer);
  if(recognition){try{recognition.onend=null;recognition.stop()}catch(e){}}
  setState("Microfone desativado","Diga “Ativar microfone” na interface para iniciar novamente.");
 };
 const startListening=()=>{
  if(!SpeechRecognition){setState("Navegador sem suporte","Use Chrome ou Edge atualizado para reconhecimento de fala.");toast("Reconhecimento de voz não suportado neste navegador.");return}
  if(listening)return;
  recognition=new SpeechRecognition();
  recognition.lang="pt-BR";recognition.continuous=true;recognition.interimResults=false;recognition.maxAlternatives=1;
  recognition.onstart=()=>setState("Ouvindo a palavra “Nix”","Fale “Nix” e depois sua pergunta ou comando.");
  recognition.onresult=(event)=>{
   for(let i=event.resultIndex;i<event.results.length;i++){
    if(!event.results[i].isFinal)continue;
    const heard=event.results[i][0]?.transcript||"";
    const normalized=normalizeVoice(heard);
    const match=normalized.match(/^(?:oi |ola )?nix(?: lms)?(?:\s+(.*))?$/);
    if(!match)continue;
    const command=(match[1]||"").trim();
    if(!command){say("Estou ouvindo. Pode falar.");continue}
    handleVoiceCommand(command);
   }
  };
  recognition.onerror=(event)=>{
   if(event.error==="not-allowed"||event.error==="service-not-allowed"){stopListening();setState("Permissão de microfone negada","Autorize o microfone nas permissões do navegador.");}
   else if(event.error!=="no-speech"&&event.error!=="aborted")setState("Falha no reconhecimento","Verifique o microfone e a conexão do navegador.");
  };
  recognition.onend=()=>{
   if(listening&&!speaking){restartTimer=setTimeout(()=>{try{recognition.start()}catch(e){}},500)}
  };
  listening=true;
  try{recognition.start()}catch(e){listening=false;setState("Não foi possível iniciar","Verifique as permissões do microfone.");}
 };
 const navigateByVoice=(target,label)=>{
  show(target);speakAndShow("Abrindo "+label+".");
 };
 const confirmAction=async()=>{
  if(!pendingVoiceAction)return false;
  const role=pendingVoiceAction;pendingVoiceAction=null;
  try{
   await api("/api/huggingface/deactivate",{method:"POST",body:JSON.stringify({role})});
   await loadHuggingFaceStatus();
   speakAndShow("Componente local desativado com sucesso.");
  }catch(e){speakAndShow("Não consegui desativar o componente: "+e.message)}
  return true;
 };
 async function handleVoiceCommand(raw){
  const cmd=normalizeVoice(raw);
  if(pendingVoiceAction){
   if(/^(confirmar|confirmo|sim|pode confirmar)$/.test(cmd)){await confirmAction();return}
   if(/^(cancelar|cancela|nao|não)$/.test(cmd)){pendingVoiceAction=null;speakAndShow("Ação cancelada.");return}
   pendingVoiceAction=null;
  }
  if(/^(pare de ouvir|parar de ouvir|desligar microfone|desative o microfone|desativar microfone|encerrar escuta)$/.test(cmd)){
   say("Vou desligar o microfone.");stopListening();return;
  }
  if(/^(pare de falar|parar de falar|silenciar|mudo)$/.test(cmd)){muted=true;window.speechSynthesis?.cancel();speakAndShow("Fala silenciada. Continuo ouvindo.");return}
  if(/^(voltar a falar|ativar fala|dessilenciar|falar novamente)$/.test(cmd)){muted=false;speakAndShow("Voz de resposta ativada.");return}
  if(/^(repetir|repita|repetir resposta)$/.test(cmd)){say(lastSpoken||"Ainda não tenho uma resposta para repetir.");return}
  if(/^(confirmar|confirmo)$/.test(cmd)){speakAndShow("Não há nenhuma ação aguardando confirmação.");return}
  if(/^(cancelar|cancela)$/.test(cmd)){speakAndShow("Não há nenhuma ação pendente.");return}
  const pages=[
   [/\b(visao geral|inicio|painel principal)\b/,"overview","a visão geral"],
   [/\b(conversa|conversar|chat)\b/,"chat","a conversa"],
   [/\b(aprendizagem|aprendizado)\b/,"learning","a aprendizagem"],
   [/\b(biblioteca|biblioteca privada)\b/,"library","a biblioteca privada"],
   [/\b(frameworks|estruturas de ia)\b/,"frameworks","os frameworks"],
   [/\b(hugging face|modelos publicos)\b/,"huggingface","o Hugging Face"],
   [/\b(diagnostico|diagnosticos)\b/,"diagnostics","o diagnóstico"],
   [/\b(laboratorio de midia|midia|geracao de imagem)\b/,"media","o laboratório de mídia"]
  ];
  for(const [pattern,target,label] of pages){if(pattern.test(cmd)){if(target==="media"){window.location.href="/media";return}navigateByVoice(target,label);return}}
  if(/^(atualizar|atualize|recarregar|recarregue) (painel|status|sistema|visao geral)$/.test(cmd)){
   await loadStatus();speakAndShow("Painel atualizado. Sistema em execução.");return;
  }
  if(/^(executar|rodar|fazer) diagnostico$/.test(cmd)){
   show("diagnostics");await loadDiagnostics();speakAndShow("Diagnóstico atualizado. Consulte os resultados na tela.");return;
  }
  const search=cmd.match(/^(?:pesquisar|buscar|procure) na biblioteca (?:por )?(.+)$/);
  if(search){
   try{
    const d=await api("/api/library/search",{method:"POST",body:JSON.stringify({query:search[1]})});
    const results=d.results||[];
    speakAndShow(results.length?("Encontrei "+results.length+" resultados. "+results.slice(0,3).map(x=>(x.title||"Documento")+": "+(x.content||"").slice(0,180)).join(". ")):"Não encontrei resultados na biblioteca.");
   }catch(e){speakAndShow("A pesquisa falhou: "+e.message)}
   return;
  }
  const deactivate=cmd.match(/^desativar (modelo de linguagem|geracao local|embeddings|visao|audio|modelo de fala)$/);
  if(deactivate){
   const role=/embeddings/.test(cmd)?"embeddings":/visao/.test(cmd)?"vision":/(audio|fala)/.test(cmd)?"speech":"generator";
   pendingVoiceAction=role;speakAndShow("Confirme: deseja desativar "+deactivate[1]+"? Diga “Nix, confirmar” ou “Nix, cancelar”.");return;
  }
  if(/^(ajuda|quais comandos|o que posso fazer)$/.test(cmd)){
   speakAndShow("Você pode pedir para abrir conversa, biblioteca, aprendizagem, frameworks, Hugging Face, diagnóstico e laboratório de mídia; atualizar o painel; pesquisar na biblioteca; ou conversar normalmente. Para chamar, comece com Nix.");return;
  }
  await postChat(raw);
 }
 toggle.addEventListener("click",()=>listening?stopListening():startListening());
 repeat.addEventListener("click",()=>say(lastSpoken));
 mute.addEventListener("click",()=>{
  muted=!muted;mute.textContent=muted?"Ativar fala":"Silenciar fala";
  if(muted)window.speechSynthesis?.cancel();else say("Fala ativada.");
 });
 repeat.disabled=false;
 setState("Voz desativada",SpeechRecognition?"Ative o microfone uma vez; depois a palavra-chave “Nix” inicia cada interação.":"Este navegador não oferece reconhecimento de voz compatível.");
})();
