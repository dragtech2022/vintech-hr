'use strict';
const $ = s => document.querySelector(s);
const esc = v => String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let state={employees:[],shifts:[]}, csrf='', view='employees', editor=null, busy=false;
const days=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
async function api(path,method='GET',data){
 const response=await fetch(path,{method,credentials:'same-origin',headers:{'Content-Type':'application/json','X-HR-Request':'1','X-CSRF-Token':csrf},...(data?{body:JSON.stringify(data)}:{})});
 const payload=await response.json();
 if(!response.ok){if(response.status===401&&path!='/api/login')showLogin();throw new Error(payload.error||'Request failed. Try again.');}
 return payload;
}
function showLogin(){csrf='';state={employees:[],shifts:[]};$('#employee-rows').replaceChildren();$('#shift-cards').replaceChildren();$('#activity-rows').replaceChildren();$('#editor').close();$('#editor-fields').replaceChildren();$('#workspace').hidden=true;$('#login-screen').hidden=false;}
function toast(message){$('#toast').textContent=message;$('#toast').hidden=false;setTimeout(()=>$('#toast').hidden=true,4000);}
async function load(){
 $('#page-error').textContent='';$('#loading').hidden=false;
 try{state=await api('/api/data');render();}catch(e){$('#page-error').textContent=e.message;}finally{$('#loading').hidden=true;}
}
async function start(user){csrf=user.csrf;$('#username').textContent=user.username;$('#login-screen').hidden=true;$('#workspace').hidden=false;await load();}
$('#login-form').addEventListener('submit',async e=>{e.preventDefault();const b=e.target.querySelector('button');b.disabled=true;$('#login-error').textContent='';try{await start(await api('/api/login','POST',Object.fromEntries(new FormData(e.target))));e.target.reset();}catch(err){$('#login-error').textContent=err.message;}finally{b.disabled=false;}});
$('#logout').onclick=async()=>{try{await api('/api/logout','POST',{});showLogin();}catch(e){$('#page-error').textContent=e.message;}};
function render(){
 view=['employees','shifts','activity'].includes(location.hash.slice(1))?location.hash.slice(1):'employees';
 document.querySelectorAll('nav a').forEach(a=>{a.classList.toggle('active',a.dataset.view===view);if(a.dataset.view===view)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
 const active=state.employees.filter(e=>e.status==='Active');
 $('#count-active').textContent=active.length;$('#count-monthly').textContent=active.filter(e=>e.pay_basis==='Monthly').length;$('#count-daily').textContent=active.filter(e=>e.pay_basis==='Daily').length;$('#count-shifts').textContent=state.shifts.filter(s=>s.active).length;
 for(const v of ['employees','shifts','activity'])$('#'+v+'-view').hidden=v!==view;
 $('#page-title').textContent={employees:'Employees',shifts:'Shift master',activity:'Activity log'}[view];
 $('#page-description').textContent={employees:'Manage your team and their allowed shifts.',shifts:'Define working hours for every day of the week.',activity:'A record of changes made by your administrators.'}[view];
 $('#export-button').hidden=view!=='employees';$('#add-button').hidden=view==='activity';$('#add-button').textContent=view==='shifts'?'+ Add shift':'+ Add employee';
 if(view==='employees')renderEmployees();if(view==='shifts')renderShifts();if(view==='activity')loadActivity();
}
function renderEmployees(){
 const search=$('#search').value.toLowerCase(),status=$('#status-filter').value;
 const rows=state.employees.filter(e=>(status==='all'||e.status===status)&&[e.name,e.code,e.department,e.designation].join(' ').toLowerCase().includes(search));
 $('#result-count').textContent=`${rows.length} ${rows.length===1?'employee':'employees'}`;
 $('#employee-rows').innerHTML=rows.map(e=>`<tr><td><strong>${esc(e.name)}</strong><small>${esc(e.code)}</small></td><td><strong>${esc(e.department||'—')}</strong><small>${esc(e.designation||'—')}</small></td><td>${esc(formatDate(e.joined))}</td><td>${esc(e.pay_basis)}</td><td>${e.shifts.length?e.shifts.map(id=>`<span class="pill">${esc(state.shifts.find(s=>s.id===id)?.code||'Unavailable')}</span>`).join(''):'<span class="muted">Not assigned</span>'}</td><td><span class="status ${e.status==='Inactive'?'inactive':''}">${esc(e.status)}</span></td><td><button class="edit" data-edit-employee="${e.id}" aria-label="Edit ${esc(e.name)}">Edit</button></td></tr>`).join('');
 $('#employee-empty').hidden=rows.length>0;const none=state.employees.length===0;
 $('#empty-title').textContent=none?'Build your employee directory':'No matching employees';$('#empty-description').textContent=none?'Add your first employee, then assign their allowed shifts.':'Try a different search or employee status.';$('#empty-add').hidden=!none;
}
function formatDate(s){const [y,m,d]=s.split('-');return `${d}/${m}/${y}`;}
function renderShifts(){
 $('#shift-empty').hidden=state.shifts.length>0;
 $('#shift-cards').innerHTML=state.shifts.map(s=>{const enabled=s.schedule.filter(d=>d.enabled), first=enabled[0], uniform=enabled.every(d=>d.start===first.start&&d.end===first.end&&d.next_day===first.next_day),assigned=state.employees.filter(e=>e.shifts.includes(s.id)).length;return `<article class="shift-card"><div class="card-head"><span class="pill">${esc(s.code)}</span><span class="status ${!s.active?'inactive':''}">${s.active?'Active':'Inactive'}</span></div><h2>${esc(s.name)}</h2><p class="muted">${enabled.length} days per week · ${assigned} assigned employees</p><div class="timing">${uniform?`${esc(first.start)} – ${esc(first.end)}${first.next_day?' <span class="pill">Next day</span>':''}`:'Varies by weekday'}</div><p class="muted">${s.schedule.map((d,i)=>d.enabled?days[i].slice(0,3):null).filter(Boolean).join(' · ')}</p><dl><div><dt>Full-day minimum</dt><dd>${s.min_full} minutes</dd></div><div><dt>Half-day minimum</dt><dd>${s.min_half} minutes</dd></div><div><dt>Unpaid break</dt><dd>${s.lunch_minutes} minutes</dd></div><div><dt>Arrival window</dt><dd>−${s.arrival_before} / +${s.arrival_after} min</dd></div></dl><button class="edit" data-edit-shift="${s.id}">Edit shift</button></article>`;}).join('');
}
async function loadActivity(){try{const data=await api('/api/audit');$('#activity-rows').innerHTML=data.rows.length?data.rows.map(r=>`<tr><td>${esc(new Date(r.at*1000).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'}))} IST</td><td>${esc(r.username)}</td><td>${r.action==='create'?'Created':'Updated'}</td><td>${esc(r.entity)} #${r.entity_id}</td></tr>`).join(''):'<tr><td colspan="4" class="muted">No changes recorded yet.</td></tr>';}catch(e){$('#page-error').textContent=e.message;}}
function field(label,name,value='',type='text',required=false,max=120){return `<label>${esc(label)}${required?' *':''}<input name="${name}" type="${type}" value="${esc(value)}" ${required?'required':''} ${['number','date','time'].includes(type)?'':`maxlength="${max}"`} ${type==='number'?'min="0" step="1" max="1440"':''}></label>`;}
function select(label,name,options,value){return `<label>${esc(label)}<select name="${name}">${options.map(o=>`<option value="${esc(o)}" ${o===value?'selected':''}>${esc(o)}</option>`).join('')}</select></label>`;}
function openEmployee(id){
 const e=state.employees.find(r=>r.id===id)||{code:'',name:'',department:'',designation:'',joined:'',email:'',phone:'',pay_basis:'Monthly',status:'Active',shifts:[]};editor={type:'employee',id:e.id,version:e.version};
 $('#editor-title').textContent=e.id?'Edit employee':'Add employee';$('#editor-kicker').textContent='EMPLOYEE RECORD';$('#save-editor').textContent='Save employee';
 $('#editor-fields').innerHTML=`<section class="form-section"><h3>Personal & employment details</h3><div class="form-grid">${field('Employee code','code',e.code,'text',true,30)}${field('Full name','name',e.name,'text',true)}${field('Department','department',e.department,'text',false,80)}${field('Designation','designation',e.designation,'text',false,80)}${field('Joining date','joined',e.joined,'date',true)}${select('Pay basis','pay_basis',['Monthly','Daily'],e.pay_basis)}${field('Email','email',e.email,'email',false,160)}${field('Phone','phone',e.phone,'tel',false,30)}${select('Employment status','status',['Active','Inactive'],e.status)}</div></section><section class="form-section"><h3>Allowed shifts</h3><p>Select up to three shifts. These are permitted options, not a fixed roster or a punch-processing rule.</p><div class="checks">${state.shifts.filter(s=>s.active).map(s=>`<label class="check-card"><input type="checkbox" name="shifts" value="${s.id}" ${e.shifts.includes(s.id)?'checked':''}>${esc(s.code)} · ${esc(s.name)}</label>`).join('')||'<p>Create a shift in Shift master, then assign it here.</p>'}</div></section>`;
 showEditor();
}
function openShift(id){
 const s=state.shifts.find(r=>r.id===id)||{code:'',name:'',schedule:days.map(()=>({enabled:true,start:'08:00',end:'17:00',next_day:false})),min_full:480,min_half:240,lunch_minutes:30,arrival_before:120,arrival_after:60,active:1};editor={type:'shift',id:s.id,version:s.version};
 $('#editor-title').textContent=s.id?'Edit shift':'Add shift';$('#editor-kicker').textContent='SHIFT CONFIGURATION';$('#save-editor').textContent='Save shift';
 $('#editor-fields').innerHTML=`<section class="form-section"><div class="form-grid">${field('Shift code','code',s.code,'text',true,30)}${field('Shift name','name',s.name,'text',true,80)}${select('Status','status',['Active','Inactive'],s.active?'Active':'Inactive')}</div></section><section class="form-section"><h3>Weekly schedule</h3><p>Use 24-hour times. Select Next day when a shift ends the following morning. Disabled weekdays are unscheduled; this does not determine paid weekly offs.</p><button type="button" class="secondary" id="copy-monday">Copy Monday times to all days</button><div class="table-wrap"><table class="day-table"><thead><tr><th>Working day</th><th>Start</th><th>End</th><th>Next day</th></tr></thead><tbody>${s.schedule.map((d,i)=>`<tr><td><input type="checkbox" name="enabled_${i}" aria-label="${days[i]} enabled" ${d.enabled?'checked':''}>${days[i].slice(0,3)}</td><td><input type="time" name="start_${i}" aria-label="${days[i]} start" value="${d.start}" required></td><td><input type="time" name="end_${i}" aria-label="${days[i]} end" value="${d.end}" required></td><td><input type="checkbox" name="next_day_${i}" aria-label="${days[i]} ends next day" ${d.next_day?'checked':''}></td></tr>`).join('')}</tbody></table></div></section><section class="form-section"><h3>Attendance settings · minutes</h3><p>Saved for future attendance processing. No punches or payroll are calculated in this release.</p><div class="form-grid">${field('Minimum full-day hours (minutes)','min_full',s.min_full,'number',true)}${field('Minimum half-day hours (minutes)','min_half',s.min_half,'number',true)}${field('Unpaid break (minutes)','lunch_minutes',s.lunch_minutes,'number',true)}${field('Arrival before start (minutes)','arrival_before',s.arrival_before,'number',true)}${field('Arrival after start (minutes)','arrival_after',s.arrival_after,'number',true)}</div></section>`;
 showEditor();
 $('#copy-monday').onclick=()=>{const form=$('#editor-form');for(let i=1;i<7;i++){for(const k of ['start','end'])form.elements[`${k}_${i}`].value=form.elements[`${k}_0`].value;form.elements[`next_day_${i}`].checked=form.elements.next_day_0.checked;}toast('Monday times copied. Working-day selections kept.');};
}
function showEditor(){$('#editor-error').textContent='';$('#editor').showModal();$('#editor').scrollTop=0;}
function closeEditor(){if(busy)return;$('#editor').close();}
$('#close-editor').onclick=closeEditor;$('#cancel-editor').onclick=closeEditor;
$('#editor').addEventListener('cancel',e=>{if(busy)e.preventDefault();});
$('#editor-form').onsubmit=async event=>{
 event.preventDefault();if(busy)return;const form=event.target,raw=new FormData(form),data=Object.fromEntries(raw);if(editor.version)data.version=editor.version;
 if(editor.type==='employee')data.shifts=raw.getAll('shifts').map(Number);
 else{data.active=data.status==='Active'?1:0;delete data.status;data.schedule=days.map((_,i)=>({enabled:raw.has(`enabled_${i}`),start:raw.get(`start_${i}`),end:raw.get(`end_${i}`),next_day:raw.has(`next_day_${i}`)}));for(const k of ['min_full','min_half','lunch_minutes','arrival_before','arrival_after'])data[k]=Number(raw.get(k));}
 busy=true;$('#save-editor').disabled=true;$('#editor-error').textContent='';
 try{await api(`/api/${editor.type==='employee'?'employees':'shifts'}${editor.id?'/'+editor.id:''}`,editor.id?'PUT':'POST',data);$('#editor').close();toast(editor.type==='employee'?'Employee saved.':'Shift saved.');await load();}catch(e){$('#editor-error').textContent=e.message;}finally{busy=false;$('#save-editor').disabled=false;}
};
$('#search').oninput=renderEmployees;$('#status-filter').onchange=renderEmployees;
$('#add-button').onclick=()=>view==='shifts'?openShift():openEmployee();$('#empty-add').onclick=()=>openEmployee();$('#empty-shift').onclick=()=>openShift();
$('#employee-rows').onclick=e=>{const b=e.target.closest('[data-edit-employee]');if(b)openEmployee(Number(b.dataset.editEmployee));};
$('#shift-cards').onclick=e=>{const b=e.target.closest('[data-edit-shift]');if(b)openShift(Number(b.dataset.editShift));};
window.addEventListener('hashchange',()=>{if(csrf)render();});
api('/api/me').then(start).catch(showLogin);
