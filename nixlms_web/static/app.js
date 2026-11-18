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
async function loadFrameworks(){const box=$("#framework-list");box.textContent="Consultando inventário...";try{const d=await api("/api/frameworks");box.innerHTML=d.map(x=>{const state=x.installation_state||(x.installed?"installed":"absent");const ambiguous=state==="metadata_only"||state==="module_only";const label=state==="installed"?"INSTALADO "+esc(x.version||""):(ambiguous?"INCONSISTENTE":"NÃO INSTALADO");return '<article class="panel card"><div><b>'+esc(x.name)+'</b><small>'+esc(x.purpose)+'</small></div><span class="pill '+(state==="installed"?"ok":"off")+'">'+label+'</span></article>'}).join("")}catch(e){box.textContent=e.message}}
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
