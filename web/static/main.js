async function api(path, opts = {}){
  const res = await fetch(path, {headers:{'Content-Type':'application/json'}, ...opts});
  return res.json();
}

async function loadConfig(){
  const cfg = await api('/api/config');
  document.getElementById('base_url').value = cfg.base_url || '';
  document.getElementById('model').value = cfg.model || '';
  document.getElementById('api_key').value = cfg.api_key || '';
  document.getElementById('device_type').value = cfg.device_type || 'adb';
  document.getElementById('device_id').value = cfg.device_id || '';
  document.getElementById('max_steps').value = cfg.max_steps || 100;
}

async function saveConfig(){
  const data = {
    base_url: document.getElementById('base_url').value,
    model: document.getElementById('model').value,
    api_key: document.getElementById('api_key').value,
    device_type: document.getElementById('device_type').value,
    device_id: document.getElementById('device_id').value,
    max_steps: Number(document.getElementById('max_steps').value || 100),
  };
  const res = await api('/api/config', {method:'POST', body: JSON.stringify(data)});
  if(res.ok){ alert('保存成功'); }
}

async function listDevices(){
  const res = await api('/api/devices');
  const ul = document.getElementById('deviceList');
  ul.innerHTML = '';
  if(res.error){ ul.innerText = 'Error: '+res.error; return; }
  (res.devices||[]).forEach(d=>{
    const li = document.createElement('li');
    li.textContent = `${d.device_id} [${d.connection_type}] ${d.status} ${d.model ? ' - '+d.model : ''}`;
    ul.appendChild(li);
  });
}

async function connect(){
  const address = document.getElementById('connect_address').value;
  if(!address){ alert('请输入 address'); return; }
  const res = await api('/api/connect', {method:'POST', body: JSON.stringify({address})});
  alert(res.message || JSON.stringify(res));
  listDevices();
}

async function disconnect(){
  const address = document.getElementById('connect_address').value;
  const res = await api('/api/disconnect', {method:'POST', body: JSON.stringify({address})});
  alert(res.message || JSON.stringify(res));
  listDevices();
}

// Screenshot handling
let _screenshotInterval = null;
let _screenshotRealtime = false;

async function fetchScreenshot(){
  try{
    const res = await api('/api/screenshot');
    if(res.error){ console.warn('screenshot error', res.error); return; }
    const img = document.getElementById('screenshotImg');
    img.src = res.image;
    document.getElementById('screenshotSize').textContent = `${res.width}x${res.height}`;
    document.getElementById('screenshotApp').textContent = res.current_app || '—';
    document.getElementById('screenshotTime').textContent = new Date().toLocaleTimeString();
  }catch(e){ console.warn(e); }
}

function startScreenshotPolling(){
  if(_screenshotInterval) clearInterval(_screenshotInterval);
  // change polling to every 3 seconds to reduce load and bandwidth
  _screenshotInterval = setInterval(fetchScreenshot, 3000);
}

function stopScreenshotPolling(){
  if(_screenshotInterval) clearInterval(_screenshotInterval);
  _screenshotInterval = null;
}

function setRealtime(on){
  _screenshotRealtime = on;
  if(on){ startScreenshotPolling(); } else { stopScreenshotPolling(); }
}

async function runTask(){
  const task = document.getElementById('task').value;
  if(!task){ alert('请输入任务描述'); return; }
  const pre = document.getElementById('result');
  pre.textContent = '';
  document.getElementById('runTask').disabled = true;

  // Close previous event source if exists
  if (window._runEventSource) {
    window._runEventSource.close();
    window._runEventSource = null;
  }

  const es = new EventSource('/api/run_stream?task=' + encodeURIComponent(task));
  window._runEventSource = es;

  es.onmessage = function(e){
    pre.textContent += e.data + '\n';
    pre.scrollTop = pre.scrollHeight;
  };

  es.addEventListener('result', function(e){
    pre.textContent += '\n=== RESULT ===\n' + e.data + '\n';
  });

  es.addEventListener('error', function(e){
    pre.textContent += '\n=== ERROR ===\n' + (e.data || '') + '\n';
  });

  es.addEventListener('done', function(e){
    pre.textContent += '\n=== DONE ===\n';
    es.close();
    document.getElementById('runTask').disabled = false;
    window._runEventSource = null;
  });

  es.onerror = function(e){
    if (es.readyState === EventSource.CLOSED) {
      document.getElementById('runTask').disabled = false;
      window._runEventSource = null;
    }
  };
}

async function getApps(){
  const res = await api('/api/apps');
  const ul = document.getElementById('apps'); ul.innerHTML='';
  (res.apps||[]).forEach(a=>{ const li=document.createElement('li'); li.textContent=a; ul.appendChild(li)});
}

window.addEventListener('load', ()=>{
  loadConfig();
  document.getElementById('saveConfig').addEventListener('click', saveConfig);
  document.getElementById('refreshConfig').addEventListener('click', loadConfig);
  document.getElementById('btnList').addEventListener('click', listDevices);
  document.getElementById('btnConnect').addEventListener('click', connect);
  document.getElementById('btnDisconnect').addEventListener('click', disconnect);
  document.getElementById('runTask').addEventListener('click', runTask);
  document.getElementById('btnApps').addEventListener('click', getApps);

  // Screenshot controls
  document.getElementById('realtimeToggle').addEventListener('change', (e)=> setRealtime(e.target.checked));
  document.getElementById('refreshScreenshot').addEventListener('click', fetchScreenshot);
  // initially load one screenshot
  fetchScreenshot();

  // Initialize collapsible sections (persist state in localStorage)
  document.querySelectorAll('.card.card-collapsible').forEach(section => {
    const btn = section.querySelector('.collapse-toggle');
    const header = section.querySelector('.card-header');
    const key = 'collapse_' + (section.querySelector('h2')?.textContent?.trim() || '');

    // restore state
    const collapsed = localStorage.getItem(key) === '1';
    if(collapsed){
      section.classList.add('collapsed');
      btn.setAttribute('aria-expanded','false');
      btn.textContent = '+';
    }

    btn.addEventListener('click', ()=>{
      const isCollapsed = section.classList.toggle('collapsed');
      btn.setAttribute('aria-expanded', isCollapsed ? 'false' : 'true');
      btn.textContent = isCollapsed ? '+' : '−';
      localStorage.setItem(key, isCollapsed ? '1' : '0');
    });
  });

});