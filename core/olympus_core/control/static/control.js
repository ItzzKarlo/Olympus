'use strict';
const $ = selector => document.querySelector(selector);
const pages = ['Overview','Preview','Simulation','Services','Display','Config','Logs','Devices','Backups','Releases','Diagnostics'];
let csrf = '', state = null, activePage = 'Overview', overrides = {}, configLoaded = null, validated = '', dirty = false, restarting = null;
const message = text => { $('#message').textContent = text; };
const json = data => JSON.stringify(data, null, 2);
function node(tag, text, cls) { const n = document.createElement(tag); if(text !== undefined) n.textContent = text; if(cls) n.className = cls; return n; }
async function api(path, method='GET', body) {
  const response = await fetch('/api/control'+path, {method, headers:{'Content-Type':'application/json','X-CSRF-Token':csrf}, body:body === undefined ? undefined : JSON.stringify(body), signal:AbortSignal.timeout(18000)});
  const result = await response.json();
  if(response.status === 401) { location.replace('/control/login'); throw new Error('Login required'); }
  if(!result.ok) throw new Error(result.error?.message || 'Request failed');
  return result.data;
}
function action(selector, handler) { $(selector).addEventListener('click', () => Promise.resolve().then(handler).catch(e=>message(e.message))); }
function form(selector, handler) { $(selector).addEventListener('submit', e=>{e.preventDefault(); Promise.resolve(handler(e.target)).catch(error=>message(error.message));}); }
function table(target, rows, columns, actions) {
  target.replaceChildren();
  if(!rows.length) { target.append(node('p','No entries.')); return; }
  const t=node('table'), head=node('tr');
  for(const [title] of columns) head.append(node('th',title));
  if(actions) head.append(node('th','Actions'));
  t.append(head);
  for(const row of rows) {
    const tr=node('tr');
    for(const [,field] of columns) tr.append(node('td', typeof field === 'function' ? field(row) : row[field] ?? '—'));
    if(actions) {const td=node('td'); actions(row,td); tr.append(td);}
    t.append(tr);
  }
  target.append(t);
}
function button(parent, text, handler) {const b=node('button',text);b.addEventListener('click',()=>Promise.resolve().then(handler).catch(e=>message(e.message)));parent.append(b);}
function card(parent, title, values) {const box=node('article',undefined,'card');box.append(node('h2',title));for(const [k,v] of Object.entries(values)) box.append(node('p',`${k}: ${typeof v === 'object' ? json(v) : v ?? '—'}`));parent.append(box);}
function showPage(name) {
  if(!pages.includes(name)) return;
  activePage=name; $('#page-title').textContent=name;
  document.querySelectorAll('[data-section]').forEach(n=>{n.hidden=n.dataset.section!==name;});
  document.querySelectorAll('nav button').forEach(n=>n.setAttribute('aria-current',n.textContent===name?'page':'false'));
  const load={Services:loadServices,Config:()=>configLoaded?null:loadConfig(),Devices:loadDevices,Backups:loadBackups,Releases:loadReleases};
  if(load[name]) Promise.resolve(load[name]()).catch(e=>message(e.message));
}
for(const name of pages) {const b=node('button',name);b.onclick=()=>showPage(name);$('#navigation').append(b);}
document.querySelectorAll('[data-page]').forEach(b=>b.onclick=()=>showPage(b.dataset.page));
async function normal() {await api('/overrides','DELETE'); overrides={};populatePreview();message('Normal operation restored. Persistent config and real state are unchanged.');await poll();}
document.querySelectorAll('.normal').forEach(b=>b.onclick=()=>normal().catch(e=>message(e.message)));
action('#logout',async()=>{await api('/logout','POST',{});location.replace('/control/login');});

function updateStatus(s) {
  state=s; $('#version').textContent=`v${s.release.version}`;
  $('#connection').textContent=restarting?'CORE RESTARTING · RECONNECTING':'CORE ONLINE';
  $('#connection').className='badge '+(restarting?'unknown':'up');
  const doc=s.overrides; overrides=doc?.settings || {};
  $('#override-banner').hidden=!doc;
  const ttl=doc?.expires_at ? `${Math.max(0,Math.ceil((doc.expires_at-Date.now()/1000)/60))}m remaining` : 'until reset / reboot';
  $('#override-summary').textContent=doc?`Season: ${overrides.seasonal_date||'AUTO'} · ${overrides.day_night.toUpperCase()} · scene ${overrides.scene.toUpperCase()} · ${overrides.simulation?.kind||'no simulation'} · ${ttl}`:'';
  $('#time-policy').textContent=`Real time: ${s.local_time}\nSchedule: ${json(s.night_schedule)}\nAUTO: ${s.auto_night?'NIGHT':'DAY'}\nOverride: ${overrides.day_night||'auto'}\nEffective: ${s.effective_night?'NIGHT':'DAY'}`;
  const overview=$('#overview');overview.replaceChildren();
  card(overview,'Olympus',{Version:s.release.version,Revision:s.release.revision,Provenance:s.release.source_tree,Release:s.release_path,'Core uptime':`${s.core_uptime_seconds}s`,Scene:s.scene,'Real scene':s.real_scene,'Seasonal date':overrides.seasonal_date||s.local_time.slice(0,10),'Day / night':s.effective_night?'NIGHT':'DAY','Display clients':s.display_clients});
  const host=s.real.core_host;
  card(overview,'Hermes',host?{'CPU %':host.system.cpu_percent,'RAM %':host.system.ram_percent,'Load 1m':host.load_average_1m,'Temperature °C':host.cpu_temperature_celsius,'Disk %':host.storage.root_used_percent,'Uptime seconds':host.system.uptime_seconds}:{Status:'Telemetry pending'});
  const net=s.real.network;card(overview,'Network',net?{Gateway:net.gateway.status,DNS:net.dns.status,Internet:net.internet.status,HTTPS:net.https.status}:{Status:'Unavailable'});
  card(overview,'Agents',Object.fromEntries(Object.values(s.real.machines).map(m=>[m.hostname,`${m.online?'ONLINE':'OFFLINE'} · ${m.last_seen}`])));
  card(overview,'Monitored services',Object.fromEntries(Object.values(s.real.services).map(m=>[m.name,m.status])));
  card(overview,'Safety',{Incidents:s.real.alerts.length,'Control overrides':doc?'ACTIVE':'none','Config restart required':s.restart_required});
  const d=$('#display-info');d.replaceChildren();card(d,'WALL',{Clients:s.display_clients,URL:s.kiosk_url,Scene:s.scene,Overrides:overrides});
}
async function poll() {
  try {
    if(restarting) await fetch('/health',{cache:'no-store',signal:AbortSignal.timeout(3000)});
    const s=await api('/status');
    if(restarting && (s.core_uptime_seconds < restarting.uptime || restarting.disconnected)) {restarting=null;message('Core reconnected. State refreshed.');csrf=(await api('/session')).csrf;}
    if(restarting && Date.now()-restarting.started>20000) {const r=await api('/services');if(r.last_action?.error){message(r.last_action.error);restarting=null;}}
    updateStatus(s);
    if(activePage==='Services') await loadServices();
  } catch(error) {
    if(restarting) restarting.disconnected=true;
    $('#connection').textContent=restarting?'OLYMPUS CORE RESTARTING… Reconnecting…':'CORE UNAVAILABLE · Reconnecting…';
    $('#connection').className='badge down';
    if(!restarting) message(error.message);
  }
}
async function pollingLoop(){await poll();setTimeout(pollingLoop,4000);}

const presets=[['AUTO / REAL DATE',''],["New Year’s Day",'01-01'],['Deep Winter','01-20'],["Valentine’s Day",'02-14'],['Early Spring','03-15'],['Easter','easter'],['Peak Spring','04-15'],['May Day','05-01'],['Midsummer','06-21'],['Peak Summer','07-15'],['Late Summer','08-20'],['Early Autumn','09-15'],['German Unity Day','10-03'],['Deep Autumn','10-15'],['Halloween','10-31'],["St. Martin’s Day",'11-11'],['Advent','12-01'],["St. Nicholas Day",'12-06'],['Christmas season','12-20'],['Christmas Eve','12-24'],['Christmas Day','12-25'],['Boxing Day','12-26'],["New Year’s Eve",'12-31']];
function easter(year){const a=year%19,b=Math.floor(year/100),c=year%100,d=Math.floor(b/4),e=b%4,f=Math.floor((b+8)/25),g=Math.floor((b-f+1)/3),h=(19*a+b-d-g+15)%30,i=Math.floor(c/4),k=c%4,l=(32+2*e+2*i-h-k)%7,m=Math.floor((a+11*h+22*l)/451),month=Math.floor((h+l-7*m+114)/31),day=(h+l-7*m+114)%31+1;return `${year}-${String(month).padStart(2,'0')}-${String(day).padStart(2,'0')}`;}
for(const [label,value] of presets){const o=node('option',label);o.value=value;$('#date-preset').append(o);}
$('#date-preset').onchange=e=>{const year=new Date().getFullYear();$('#preview').seasonal_date.value=e.target.value==='easter'?easter(year):e.target.value?`${year}-${e.target.value}`:'';$('#manual-date').value='';};
action('#auto-date',()=>{$('#preview').seasonal_date.value='';$('#manual-date').value='';});
function populatePreview(){const f=$('#preview');f.seasonal_date.value=overrides.seasonal_date||'';f.day_night.value=overrides.day_night||'auto';f.scene.value=overrides.scene||'auto';for(const k of ['enabled','intensity','animations']) f[k].value=overrides.environment?.[k]||'auto';f.reduced_motion.checked=overrides.environment?.reduced_motion||false;f.ttl_minutes.value=String(overrides.ttl_minutes??30);}
form('#preview',async f=>{const data={...overrides,seasonal_date:$('#manual-date').value||f.seasonal_date.value||null,day_night:f.day_night.value,scene:f.scene.value,ttl_minutes:Number(f.ttl_minutes.value),environment:{enabled:f.enabled.value,intensity:f.intensity.value,animations:f.animations.value,reduced_motion:f.reduced_motion.checked}};await api('/overrides','PUT',data);message('Preview applied live.');await poll();});
const variants={news:['notable','important','major','critical','outage','recovery'],system:['blocker','warning','critical','dns-degraded','dns-down','gateway-down','internet-down','service-down','agent-offline'],football:['pre-match','kickoff','live','bayern-goal','opponent-goal','halftime','second-half','full-time','victory','defeat','draw','outage','recovery','score-correction'],media:['playing','paused','local','outage','recovery'],gaming:['fortnite','minecraft','among-us','goat-simulator','custom'],development:['active']};
function changeVariants(){const f=$('#simulation');f.variant.replaceChildren();for(const v of variants[f.kind.value]){const o=node('option',v);o.value=v;f.variant.append(o);}}
$('#simulation').kind.onchange=changeVariants;changeVariants();
form('#simulation',async f=>{const sim=Object.fromEntries(new FormData(f));const ttl=Number(sim.ttl_minutes);delete sim.ttl_minutes;for(const k of ['cpu','ram','progress','duration','fps']) sim[k]=Number(sim[k]);await api('/overrides','PUT',{...overrides,scene:'auto',simulation:sim,ttl_minutes:ttl});message('Simulation active. Real collectors continue.');await poll();});
action('#clear-simulation',async()=>{await api('/overrides','PUT',{...overrides,simulation:null,scene:'auto'});await poll();message('Simulation cleared. Other preview overrides retained.');});

async function serviceAction(key,verb){if(!confirm(`${verb.toUpperCase()} Olympus ${key}?${key==='core'?' Control will disconnect. Stopping Core requires manual recovery.':''}`))return;const response=await api(`/services/${key}/${verb}`,'POST',{confirm:true});if(key==='core'&&verb==='restart'){restarting={uptime:state?.core_uptime_seconds||0,started:Date.now(),disconnected:false};message('OLYMPUS CORE RESTARTING… Reconnecting…');}else message(response.note||response.message||'Job submitted.');await loadServices();}
async function loadServices(){const data=await api('/services');table($('#services'),data.units,[['Unit','Id'],['State','ActiveState'],['Substate','SubState'],['Result','Result'],['PID','MainPID'],['Restarts','NRestarts'],['Active since','ActiveEnterTimestamp'],['Exit','ExecMainStatus']],(row,td)=>{for(const verb of ['start','stop','restart',...(row.key==='kiosk'?['reset-failed']:[])])button(td,verb,()=>serviceAction(row.key,verb));});$('#last-action').textContent=data.last_action?json(data.last_action):'';}
action('#refresh-services',loadServices);action('#restart-kiosk',()=>serviceAction('kiosk','restart'));
async function loadConfig(){if(dirty&&!confirm('Discard unsaved config draft?'))return;configLoaded=await api('/config');$('#config-text').value=configLoaded.text;$('#config-text').disabled=!configLoaded.editable;dirty=false;validated='';$('#apply-config').disabled=true;$('#config-status').textContent=configLoaded.restart_required?'CORE RESTART REQUIRED':configLoaded.editable?'Loaded':'READ ONLY: local cleanup required';const form=$('#structured-fields');form.replaceChildren();for(const [key,value]of Object.entries(configLoaded.fields)){const label=node('label',key),input=node('input');input.name=key;input.type=typeof value==='boolean'?'checkbox':typeof value==='number'?'number':'text';if(input.type==='checkbox')input.checked=value;else input.value=value??'';input.dataset.kind=typeof value;input.dataset.initial=String(value??'');label.append(input);form.append(label);}await loadHistory();}
function markDirty(){dirty=true;validated='';$('#apply-config').disabled=true;$('#config-status').textContent='UNSAVED CHANGES';}
$('#config-text').addEventListener('input',markDirty);
function draft(){if(!configLoaded)throw new Error('Load config first');return {text:$('#config-text').value,checksum:configLoaded.checksum};}
action('#load-config',loadConfig);
action('#patch-config',async()=>{const changes={};for(const input of $('#structured-fields').elements){const value=input.type==='checkbox'?input.checked:input.type==='number'?Number(input.value):input.value;if(String(value)!==input.dataset.initial)changes[input.name]=value;}const result=await api('/config/structured','POST',{...draft(),changes});$('#config-text').value=result.text;markDirty();message('Structured changes applied to raw draft. Validate before saving.');});
action('#validate-config',async()=>{const data=await api('/config/validate','POST',draft());$('#config-diff').textContent=data.diff||'No differences.';validated=$('#config-text').value;$('#apply-config').disabled=!data.diff;message('Config valid. Review the diff before applying.');});
action('#apply-config',async()=>{if(validated!==$('#config-text').value)throw new Error('Validate this draft first');if(!confirm('Back up and atomically replace persistent config with the reviewed diff? Core restart will be required.'))return;await api('/config/apply','POST',{...draft(),confirm:true});dirty=false;await loadConfig();message('Config saved. CORE RESTART REQUIRED.');});
async function loadHistory(){table($('#config-history'),await api('/config/history'),[['Backup','name'],['Bytes','size'],['SHA256','checksum']],(row,td)=>{button(td,'View / diff',async()=>{$('#history-view').textContent=json(await api('/config/history/'+row.name));});button(td,'Restore',async()=>{const review=await api('/config/history/'+row.name);$('#history-view').textContent=review.diff; if(!confirm('Restore '+row.name+'? Review the history diff before accepting. Current config will be backed up.'))return;await api('/config/restore','POST',{name:row.name,checksum:configLoaded.checksum,confirm:true});dirty=false;await loadConfig();});});}
action('#load-history',loadHistory);
form('#logs-form',async f=>{const rows=await api('/logs?'+new URLSearchParams(new FormData(f)));$('#logs').replaceChildren();for(const row of rows){const line=node('div',`${row.time?new Date(Number(row.time)/1000).toISOString():''} [${row.priority}] ${row.message}`,Number(row.priority)<=3?'log-error':Number(row.priority)===4?'log-warning':'');$('#logs').append(line);}});
async function loadDevices(){table($('#devices'),await api('/devices'),[['Name','display_name'],['Agent ID','agent_id'],['Platform','platform'],['Fingerprint','fingerprint'],['Last seen','last_seen'],['Trust',r=>r.revoked?'REVOKED':'trusted'],['Online',r=>r.online?'online':'offline']],(row,td)=>{if(!row.revoked)button(td,'Revoke',async()=>{if(confirm('Revoke '+row.display_name+'?')){await api('/devices/'+encodeURIComponent(row.agent_id)+'/revoke','POST',{confirm:true});await loadDevices();}});});}
action('#load-devices',loadDevices);
form('#enrollment',async f=>{$('#enrollment-result').textContent=json(await api('/enrollment','POST',{label:f.label.value,ttl_minutes:Number(f.ttl_minutes.value)}));});
async function loadBackups(){const b=await api('/backups');$('#backup-info').textContent=`${b.directory}\nCount: ${b.count} · retention: ${b.retention_days} days`;table($('#backups'),b.entries,[['File','name'],['Bytes','size'],['Created',r=>new Date(r.timestamp*1000).toISOString()]]);}
action('#load-backups',loadBackups);action('#create-backup',async()=>{message('Creating SQLite backup…');await api('/backups','POST',{});await loadBackups();message('Backup created.');});
async function loadReleases(){$('#releases').textContent=json(await api('/releases'));}action('#load-releases',loadReleases);
action('#run-diagnostics',async()=>{$('#diagnostics').textContent=(await api('/diagnostics')).bundle;});
action('#copy-diagnostics',async()=>{const text=$('#diagnostics').textContent;if(!text)throw new Error('Run diagnostics first');try{await navigator.clipboard.writeText(text);message('Diagnostic bundle copied.');}catch{const selection=getSelection(),range=document.createRange();range.selectNodeContents($('#diagnostics'));selection.removeAllRanges();selection.addRange(range);message('Bundle selected. Press Ctrl+C to copy (HTTP clipboard fallback).');}});
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
(async()=>{csrf=(await api('/session')).csrf;await poll();populatePreview();showPage('Overview');setTimeout(pollingLoop,4000);})().catch(e=>message(e.message));
