// Extend the existing workspace with visible proposals, retrieval evidence and tool history.
const taskCard = $('#tasks').parentElement;
const proposalBox = node('div', ''); proposalBox.id = 'proposal';
taskCard.insertBefore(proposalBox, $('#manager-actions'));
const planButton = node('button', 'Draft task proposal ↗', 'secondary full');
planButton.type = 'button'; taskCard.insertBefore(planButton, proposalBox);
planButton.onclick = () => { $('#message').value = 'Please propose project-specific tasks based on my confirmed requirements for manager review.'; $('#chat-form').requestSubmit(); };
const traceCard = node('details', '', 'card'); traceCard.append(node('summary', 'Agent activity & source passages'));
const traceContent = node('div',''); traceCard.append(traceContent); taskCard.after(traceCard);
const originalRender = render;
render = function(p) {
  originalRender(p);
  proposalBox.replaceChildren();
  if(p.proposed_tasks?.length) {
    proposalBox.append(node('p', p.status==='approved'?'Approved proposal':'Proposed tasks · not executed', 'eyebrow'));
    p.proposed_tasks.forEach(t=>proposalBox.append(node('div', '○ '+t, 'task')));
  }
  $('#review').disabled=Object.keys(labels).some(k=>!p.requirements[k])||!p.proposed_tasks?.length||p.status!=='discovery'||busy;
  planButton.disabled=p.status!=='discovery'||busy;
  traceContent.replaceChildren();
  for(const run of p.runs||[]) {
    traceContent.append(node('p', `${run.model} · ${run.status} · ${(run.elapsed_ms/1000).toFixed(1)}s`, 'hint'));
    if(run.error) traceContent.append(node('p',run.error,'hint'));
    for(const entry of run.trace) {
      const d=node('details',''); d.append(node('summary',entry.tool+(entry.result?.error?' · blocked':'')));
      d.append(node('pre',JSON.stringify({arguments:entry.arguments,result:entry.result},null,2)));traceContent.append(d);
    }
  }
  const last = [...p.messages].reverse().find(m=>m.sources?.length);
  if(last) for(const source of last.sources){ const d=node('details','');d.append(node('summary',`[${source.id}] ${source.title}`),node('p',source.text,'small'));traceContent.append(d); }
  document.querySelectorAll('.requirement').forEach((row,index)=>{const key=Object.keys(labels)[index]; if(p.provenance?.[key]?.quote)row.title='Client evidence: '+p.provenance[key].quote;});
};
$('#review').onclick=()=>action('review',{version:current.version});
$('#approve').onclick=()=>{if(confirm('Create exactly the displayed proposed tasks? This records your manager approval.'))action('approve',{action:'approve',approval_token:current.approval_token});};
$('#revise').onclick=()=>action('approve',{action:'revise',approval_token:current.approval_token});
const statusLine=node('p','Checking local AI models…','hint');document.querySelector('.heading').after(statusLine);
api('/api/ai-status/').then(s=>{statusLine.textContent=s.ready?`Live AI: ${s.model} · Embeddings: ${s.embedding_model} · ${s.indexed_chunks} indexed passages`:'AI setup incomplete. Install both models and run index_documents. No demo fallback is used.';}).catch(e=>{statusLine.textContent=e.message;});
if(document.body.dataset.staff==='true') {
  const docCard=node('details','','card');docCard.append(node('summary','Manage agency knowledge'));
  const form=node('form','');const title=node('input','');title.placeholder='Document title';title.required=true;title.maxLength=180;
  const content=node('textarea','');content.placeholder='Paste agency policy text (shared with all clients)';content.rows=7;content.required=true;content.maxLength=100000;
  title.setAttribute('aria-label','Document title');content.setAttribute('aria-label','Agency document text');
  const submit=node('button','Embed & save document','primary full');const result=node('p','','hint');form.append(title,content,submit,result);docCard.append(form);traceCard.after(docCard);
  form.onsubmit=async e=>{e.preventDefault();submit.disabled=true;result.textContent='Generating embeddings…';try{const d=await api('/api/documents/',{title:title.value,content:content.value});result.textContent=`Indexed ${d.title}: ${d.chunks} passages.`;}catch(err){result.textContent=err.message;}finally{submit.disabled=false;}};
}
