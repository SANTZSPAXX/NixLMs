const $ = (s) => document.querySelector(s);
async function call(path, body) {
  const options = body === undefined ? {} : {
    method: "POST", headers: {"Content-Type":"application/json"},
    body: JSON.stringify(body)
  };
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Falha na solicitação.");
  return data;
}
async function refreshMedia() {
  const box = $("#media-status");
  box.textContent = "Consultando dependências e modelos locais...";
  try {
    const s = await call("/api/media/status");
    const missing = Object.entries(s.packages).filter(([, ok]) => !ok).map(([name]) => name);
    box.textContent = "NSFW: " + (s.nsfw_enabled ? "ativado" : "desativado") +
      " · Modelos locais: " + s.models.length +
      " · Dependências ausentes: " + (missing.length ? missing.join(", ") : "nenhuma") +
      " · Bootstrap automático: " + (s.auto_install ? "habilitado" : "desabilitado");
    $("#nsfw").checked = s.nsfw_enabled;
  } catch (e) { box.textContent = e.message; }
}
$("#refresh").onclick = refreshMedia;
$("#mode").onchange = () => {
  const video = $("#mode").value === "image-to-video";
  $("#frames").disabled = !video;
};
$("#nsfw").onchange = async () => {
  try {
    await call("/api/media/nsfw", {enabled: $("#nsfw").checked});
    await refreshMedia();
  } catch (e) { alert(e.message); $("#nsfw").checked = !$("#nsfw").checked; }
};
$("#download").onclick = async () => {
  const repo_id = $("#repo").value.trim();
  const mode = $("#mode").value;
  if (!repo_id) return alert("Informe o ID do modelo.");
  if (!confirm("Baixar " + repo_id + " para uso local? O tamanho máximo é 4 GiB para imagem ou 10 GiB para vídeo. O download usa internet e disco locais.")) return;
  $("#media-result").textContent = "Baixando modelo...";
  try {
    const result = await call("/api/media/download", {repo_id, mode, confirm:true});
    $("#media-result").textContent = "Modelo baixado e registrado:\n" + JSON.stringify(result.download, null, 2);
    await refreshMedia();
  } catch (e) { $("#media-result").textContent = e.message; }
};
$("#generate").onclick = async () => {
  const mode = $("#mode").value, repo_id = $("#repo").value.trim();
  const prompt = $("#prompt").value.trim();
  if (!repo_id || !prompt) return alert("Informe o modelo e o prompt.");
  if (mode !== "text-to-image" && !$("#image-path").value.trim())
    return alert("Coloque a imagem em data/media/input e informe seu nome de arquivo.");
  $("#media-result").textContent = "Carregando modelo local e gerando... A inferência pode demorar.";
  try {
    const size = Number($("#size").value);
    const result = await call("/api/media/generate", {
      mode, repo_id, prompt, image_path: $("#image-path").value.trim(),
      nsfw: $("#nsfw").checked, steps: Number($("#steps").value),
      width:size, height:size, frames:Number($("#frames").value)
    });
    const g = result.generation, name = g.output.split(/[\\/]/).pop();
    const url = "/api/media/file?name=" + encodeURIComponent(name);
    $("#media-result").innerHTML = "<p>Concluído: " + g.mode + " · " + g.bytes + " bytes</p>" +
      (g.output.endsWith(".mp4") ? '<video controls src="'+url+'"></video>' : '<img alt="Imagem gerada pela NixLMs" src="'+url+'">') +
      '<p><a href="'+url+'" download>Salvar resultado</a></p>';
  } catch (e) { $("#media-result").textContent = e.message; }
};
refreshMedia();
