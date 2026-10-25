const $ = (id) => document.getElementById(id);
let lastRequest = null, map = null, mapLayers = [];
const iso = d => d.toISOString().slice(0,10);
const today = new Date(), after = new Date(today), before = new Date(today);
after.setDate(after.getDate()-10); before.setDate(before.getDate()-30);
$("beforeDate").value=iso(before); $("afterDate").value=iso(after);
$("beforeDate").max=iso(today); $("afterDate").max=iso(today);

function payload(){return {before_date:$("beforeDate").value,after_date:$("afterDate").value,west:Number($("west").value),south:Number($("south").value),east:Number($("east").value),north:Number($("north").value)}}
function status(message, error=false){$("status").textContent=message;$("status").classList.toggle("error",error)}
async function readJsonResponse(response){
  const body=await response.text();
  if(!body || !body.trim()) throw new Error(`Server returned an empty response (HTTP ${response.status}). Make sure the backend is running without --reload, then retry.`);
  let data;
  try{data=JSON.parse(body)}catch{throw new Error(`Server returned a non-JSON response (HTTP ${response.status}): ${body.slice(0,180)}`)}
  if(!response.ok) throw new Error(data.detail||data.message||`Request failed (HTTP ${response.status}).`);
  return data;
}
function renderCategories(items){
  const el=$("categories");el.replaceChildren();
  if(!items||!items.length){const p=document.createElement("p");p.className="hint";p.textContent="No candidate category passed the current screening threshold.";el.appendChild(p);return}
  items.forEach(item=>{const row=document.createElement("div");row.className="category-row";const b=document.createElement("b");b.textContent=item.name;const s=document.createElement("span");
    const share=item.share_of_changed_pixels ?? item.share_of_valid_pixels;
    s.textContent=`${share ?? "—"}% · ${Number(item.pixels||0).toLocaleString()} pixels`;row.append(b,s);el.appendChild(row)})
}
function renderMap(data){
  const mapEl=$("map");
  if(typeof L==="undefined"){mapEl.replaceChildren();const msg=document.createElement("div");msg.className="map-loading";msg.textContent="Map library could not load. Check internet and refresh.";mapEl.appendChild(msg);return}
  if(!map){
    map=L.map(mapEl,{zoomControl:true});
    // Adds the actual geographic background; without this the overlay looks like a blank red grid.
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>'}).addTo(map);
  }
  mapLayers.forEach(layer=>map.removeLayer(layer));mapLayers=[];
  const b=data.bbox,bounds=[[b.south,b.west],[b.north,b.east]];
  mapLayers.push(L.rectangle(bounds,{color:"#68e0bd",weight:2,fill:false}).addTo(map));
  (data.map_cells||[]).forEach(cell=>{
    const opacity=Math.min(.65,.15+Number(cell.change_density_percent||0)/75);
    const rect=L.rectangle([[cell.south,cell.west],[cell.north,cell.east]],{color:"#ff5964",weight:1,fillColor:"#ff414d",fillOpacity:opacity})
      .bindPopup(`<b>Elevated visual difference</b><br>Flagged-pixel density: ${cell.change_density_percent}%<br>Approximate bounds:<br>${Number(cell.south).toFixed(4)}, ${Number(cell.west).toFixed(4)} — ${Number(cell.north).toFixed(4)}, ${Number(cell.east).toFixed(4)}`).addTo(map);
    mapLayers.push(rect);
  });
  map.fitBounds(bounds);setTimeout(()=>map.invalidateSize(),200);
}
$("analyzeBtn").addEventListener("click",async()=>{
 const req=payload();
 if(!req.before_date||!req.after_date)return status("Choose both dates.",true);
 if(req.before_date>=req.after_date)return status("Before date must be earlier than after date.",true);
 if(req.east<=req.west||req.north<=req.south)return status("Check geographic coordinates.",true);
 $("analyzeBtn").disabled=true;$("reportBtn").disabled=true;status("Requesting satellite imagery and screening possible clouds…");
 try{
   const response=await fetch("/api/compare",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(req)});
   const data=await readJsonResponse(response);
   $("beforeImg").src=data.before_image;$("afterImg").src=data.after_image;$("overlayImg").src=data.overlay_image;$("heatImg").src=data.heatmap_image;$("cloudImg").src=data.cloud_image;
   $("changePct").textContent=`${data.changed_pixel_percent}%`;$("cloudPct").textContent=`${data.cloud_candidate_percent}%`;$("priority").textContent=data.screening_level;
   $("priority").style.color=data.screening_level==="High"?"#ff9a8b":data.screening_level==="Medium"?"#ffd37c":"#68e0bd";
   $("dateSummary").textContent=`${data.before_date} → ${data.after_date}`;$("beforeLabel").textContent=data.before_date;$("afterLabel").textContent=data.after_date;
   $("caveat").textContent=data.caveat||"Prototype screening estimate.";$("cloudNote").textContent=data.cloud_note||"";
   renderCategories(data.categories);$("results").hidden=false;lastRequest=req;$("reportBtn").disabled=false;
   status("Analysis complete. Review the images, categories and geographic map.");renderMap(data);
   $("results").scrollIntoView({behavior:"smooth",block:"start"});
 }catch(error){status(error instanceof TypeError?"Could not connect to the backend. Check that the terminal server is running at 127.0.0.1:8000.":(error.message||"Analysis failed; check the VS Code terminal."),true)}
 finally{$("analyzeBtn").disabled=false}
});
$("reportBtn").addEventListener("click",async()=>{
 if(!lastRequest)return;$("reportBtn").disabled=true;status("Generating PDF report…");
 try{
   const response=await fetch("/api/report",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(lastRequest)});
   if(!response.ok){await readJsonResponse(response)}
   const blob=await response.blob();if(!blob.size)throw new Error("Server returned an empty PDF. Retry the report.");
   const url=URL.createObjectURL(blob),link=document.createElement("a");link.href=url;link.download="terrawatch_change_report.pdf";document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1500);status("PDF report downloaded.");
 }catch(error){status(error.message||"PDF report generation failed.",true)}
 finally{$("reportBtn").disabled=false}
});
fetch("/api/health").then(readJsonResponse).then(()=>{}).catch(()=>status("Backend health check failed. Start the server and refresh.",true));
