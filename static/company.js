'use strict';
let companyState={companies:[],tabs:[]}, companyEditor=null, companyBusy=false, companyDocs=[];
async function loadCompanies(){
 const [records,schema]=await Promise.all([api('/api/companies'),api('/api/company-schema')]);
 companyState={...records,...schema};
}
function clearCompanies(){companyState={companies:[],tabs:[]};companyEditor=null;companyDocs=[];$('#company-document-form').reset();$('#company-editor-title').textContent='Company Master';$('#company-rows').replaceChildren();$('#company-editor').close();$('#company-fields').replaceChildren();$('#company-document-rows').replaceChildren();}
function renderCompanies(){
 const term=$('#company-search').value.toLowerCase();
 const records=companyState.companies.filter(c=>[c.company_no,c.short_name,c.name,c.branch,c.city].join(' ').toLowerCase().includes(term));
 $('#company-count').textContent=`${records.length} ${records.length===1?'company':'companies'}`;
 $('#company-rows').innerHTML=records.map(c=>`<tr><td>${esc(c.company_no)}</td><td><div class="company-name">${c.logo_id?`<img class="company-logo" src="/api/company-documents/${c.logo_id}/file" alt="">`:''}<div><strong>${esc(c.name)}</strong><small>${esc(c.short_name)}</small></div></div></td><td>${esc(c.branch||'—')}</td><td>${esc(c.city||'—')}</td><td><span class="status ${c.active==='Inactive'?'inactive':''}">${esc(c.active)}</span></td><td><button class="edit" data-edit-company="${c.id}">Open / edit</button></td></tr>`).join('');
 $('#company-empty').hidden=records.length>0;
 $('#company-empty-text').textContent=companyState.companies.length?'No companies match your search.':'Create your first company to save its details, settings and documents.';
}
function companyField(f,c){
 const value=c[f.key]??(f.key==='active'?'Active':'');
 const attrs=`name="${f.key}" ${f.required?'required':''}`;
 if(f.type==='checkbox')return `<label class="check-card"><input type="checkbox" name="${f.key}" ${value?'checked':''}>${esc(f.label)}</label>`;
 if(f.type==='select')return `<label>${esc(f.label)}<select ${attrs}>${f.options.map(v=>`<option value="${esc(v)}" ${v===value?'selected':''}>${esc(v||'Select…')}</option>`).join('')}</select></label>`;
 if(f.type==='textarea')return `<label>${esc(f.label)}<textarea ${attrs} maxlength="2000" rows="3">${esc(value)}</textarea></label>`;
 const numeric=['integer','decimal','percent'].includes(f.type),type=numeric?'number':f.type==='email'?'email':f.type==='date'?'date':'text';
 return `<label>${esc(f.label)}${f.required?' *':''}<input ${attrs} type="${type}" value="${esc(value)}" ${numeric?`min="0" max="${f.max_value??(f.type==='percent'?100:999999999999)}" step="${f.type==='integer'?1:'0.0001'}"`:`maxlength="${f.max??160}"`}></label>`;
}
function selectCompanyTab(id){
 document.querySelectorAll('[data-company-tab]').forEach(b=>{const selected=b.dataset.companyTab===id;b.classList.toggle('selected',selected);b.setAttribute('aria-selected',String(selected));b.tabIndex=selected?0:-1;});
 document.querySelectorAll('[data-company-panel]').forEach(p=>p.hidden=p.dataset.companyPanel!==id);
 $('#company-save-footer').hidden=id==='documents';
}
function openCompany(id){
 const company=companyState.companies.find(c=>c.id===id)||{};
 companyEditor={...company};
 $('#company-editor-title').textContent=company.id?company.name:'Create company';
 $('#company-editor-subtitle').textContent=company.id?`Company ${company.company_no} · edit details and documents`:'Company Master';
 $('#company-tabs').innerHTML=[...companyState.tabs,{id:'documents',label:'Documents'}].map(t=>`<button type="button" role="tab" id="company-tab-${t.id}" aria-controls="company-panel-${t.id}" data-company-tab="${t.id}">${esc(t.label)}</button>`).join('');
 $('#company-fields').innerHTML=companyState.tabs.map(t=>`<div role="tabpanel" aria-labelledby="company-tab-${t.id}" id="company-panel-${t.id}" data-company-panel="${t.id}" hidden>${t.id==='statutory'?'<div class="notice"><strong>Settings for future payroll</strong><span>These values are stored only. This release does not calculate contributions, overtime, bonus or tax. Enter your approved company settings.</span></div>':''}${t.id==='other'?'<div class="notice"><span>Application limits and contacts are stored for future workflows. Upload your HR policy in Documents.</span></div>':''}${t.sections.map(s=>`<section class="form-section"><h3>${esc(s.title)}</h3>${s.title==='Salary slip email settings'?'<p>Email delivery is not enabled yet. Enter an environment variable name for a future server-managed password; do not enter a password here.</p>':''}<div class="form-grid ${s.title==='Allowance heads'?'allowance-grid':''}">${s.fields.map(f=>companyField(f,company)).join('')}</div></section>`).join('')}</div>`).join('');
 $('#company-error').textContent='';$('#company-document-error').textContent='';
 $('#company-document-rows').replaceChildren();companyDocs=[];resetDocument();
 $('#company-document-controls').hidden=!company.id;$('#company-document-save-first').hidden=!!company.id;
 selectCompanyTab('details');$('#company-editor').showModal();$('#company-editor').scrollTop=0;
 if(company.id)refreshDocuments().catch(e=>$('#company-document-error').textContent=e.message);
}
$('#company-tabs').onclick=e=>{const b=e.target.closest('[data-company-tab]');if(b)selectCompanyTab(b.dataset.companyTab);};
$('#company-tabs').onkeydown=e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;const tabs=[...document.querySelectorAll('[data-company-tab]')];const index=tabs.indexOf(document.activeElement);if(index<0)return;e.preventDefault();let next=e.key==='Home'?0:e.key==='End'?tabs.length-1:(index+(e.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;tabs[next].click();tabs[next].focus();};
$('#company-form').addEventListener('invalid',e=>{const panel=e.target.closest('[data-company-panel]');if(panel)selectCompanyTab(panel.dataset.companyPanel);},true);
$('#company-form').onsubmit=async e=>{
 e.preventDefault();if(companyBusy)return;
 const data={}, form=e.target;
 companyState.tabs.forEach(t=>t.sections.forEach(s=>s.fields.forEach(f=>data[f.key]=f.type==='checkbox'?form.elements[f.key].checked:form.elements[f.key].value)));
 if(companyEditor.id)data.version=companyEditor.version;
 companyBusy=true;$('#save-company').disabled=true;$('#company-error').textContent='';
 try{
  const result=await api('/api/companies'+(companyEditor.id?'/'+companyEditor.id:''),companyEditor.id?'PUT':'POST',data);
  companyEditor=result.company;
  $('#company-editor-title').textContent=companyEditor.name;
  $('#company-editor-subtitle').textContent=`Company ${companyEditor.company_no} · edit details and documents`;
  $('#company-document-controls').hidden=false;$('#company-document-save-first').hidden=true;
  await loadCompanies();renderCompanies();toast('Company saved.');
 }catch(err){$('#company-error').textContent=err.message;}finally{companyBusy=false;$('#save-company').disabled=false;}
};
function closeCompany(){if(companyBusy)return;const form=$('#company-form');if(companyEditor&&companyState.tabs.some(t=>t.sections.some(s=>s.fields.some(f=>{const expected=companyEditor[f.key]??(f.key==='active'?'Active':f.type==='checkbox'?false:'');return (f.type==='checkbox'?form.elements[f.key].checked:form.elements[f.key].value)!==expected;})))){if(!confirm('Discard unsaved company changes?'))return;}$('#company-editor').close();}
$('#close-company').onclick=closeCompany;$('#cancel-company').onclick=closeCompany;
$('#company-editor').addEventListener('cancel',e=>{e.preventDefault();closeCompany();});
$('#company-search').oninput=renderCompanies;
$('#company-rows').onclick=e=>{const b=e.target.closest('[data-edit-company]');if(b)openCompany(Number(b.dataset.editCompany));};
$('#empty-company').onclick=()=>openCompany();
async function refreshDocuments(){
 const id=companyEditor.id;const result=await api(`/api/companies/${id}/documents`);
 if(companyEditor?.id!==id||!$('#company-editor').open)return;
 companyDocs=result.documents;
 const today=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Kolkata',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
 $('#company-document-rows').innerHTML=companyDocs.map(d=>`<tr><td><strong>${esc(d.document_type)}</strong><small>${esc(d.kind)} · ${esc(d.authority_group||'No group')}</small></td><td><a class="edit" href="/api/company-documents/${d.id}/file" target="_blank" rel="noopener">${esc(d.filename)}</a></td><td>${esc(d.expiry_date||'—')}${d.expiry_date&&d.expiry_date<today?'<span class="pill">Expired</span>':d.popup_date&&d.popup_date<=today?'<span class="pill">Review due</span>':''}</td><td>${esc(d.popup_date||'—')}</td><td><button type="button" class="edit" data-edit-document="${d.id}">Edit</button><button type="button" class="edit" data-archive-document="${d.id}">Archive</button></td></tr>`).join('')||'<tr><td colspan="5">No documents uploaded.</td></tr>';
}
function resetDocument(){const form=$('#company-document-form');form.reset();form.elements.document_id.value='';form.elements.version.value='';$('#document-file').required=true;$('#document-file-note').textContent='PDF, PNG or JPEG · maximum 4 MiB. Logo: PNG or JPEG.';$('#save-company-document').textContent='Upload document';}
$('#reset-company-document').onclick=()=>{if(!companyBusy)resetDocument();};
$('#company-document-rows').onclick=async e=>{
 const edit=e.target.closest('[data-edit-document]'),archive=e.target.closest('[data-archive-document]');if(companyBusy)return;
 if(edit){const d=companyDocs.find(d=>d.id===Number(edit.dataset.editDocument));const form=$('#company-document-form');form.reset();for(const k of ['kind','document_type','document_date','authority_group','expiry_date','popup_date','remark','version'])form.elements[k].value=d[k];form.elements.document_id.value=d.id;$('#document-file').required=false;$('#document-file-note').textContent=`Current: ${d.filename}. Leave file empty to keep it.`;$('#save-company-document').textContent='Save document';form.elements.document_type.focus();}
 if(archive){const d=companyDocs.find(d=>d.id===Number(archive.dataset.archiveDocument));if(!confirm(`Archive ${d.filename}? It will disappear from the active document list.`))return;companyBusy=true;try{await api(`/api/companies/${companyEditor.id}/documents/${d.id}/archive`,'POST',{version:d.version});resetDocument();await refreshDocuments();await loadCompanies();renderCompanies();toast('Document archived.');}catch(err){$('#company-document-error').textContent=err.message;}finally{companyBusy=false;}}
};
$('#company-document-form').onsubmit=async e=>{
 e.preventDefault();if(companyBusy)return;const form=e.target,raw=new FormData(form),data=Object.fromEntries(raw),file=form.elements.file.files[0];delete data.file;
 const id=data.document_id;delete data.document_id;if(id)data.version=Number(data.version);else delete data.version;
 companyBusy=true;$('#save-company-document').disabled=true;$('#company-document-error').textContent='';
 try{
  if(file){if(file.size>companyState.max_file)throw new Error('Maximum file size is 4 MiB.');data.filename=file.name;data.content=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=()=>reject(new Error('Unable to read file.'));reader.readAsDataURL(file);});}
  await api(`/api/companies/${companyEditor.id}/documents${id?'/'+id:''}`,id?'PUT':'POST',data);
  resetDocument();await refreshDocuments();await loadCompanies();renderCompanies();toast('Document saved.');
 }catch(err){$('#company-document-error').textContent=err.message;}finally{companyBusy=false;$('#save-company-document').disabled=false;}
};

api('/api/me').then(start).catch(showLogin);
