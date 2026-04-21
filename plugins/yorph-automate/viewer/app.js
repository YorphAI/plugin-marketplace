// yorph-automate viewer — minimal vanilla JS front-end.

const state = {
  workflows: [],
  selectedId: null,
  currentWorkflow: null,
  currentMermaid: null,
  runs: [],
};

const $ = (id) => document.getElementById(id);

// ── Mermaid init ───────────────────────────────────────────────────────────
mermaid.initialize({
  startOnLoad: false,
  theme: 'base',
  fontFamily: "'Space Mono', monospace",
  themeVariables: {
    primaryColor:       '#eaf7f5',
    primaryTextColor:   '#111827',
    primaryBorderColor: '#1fb69a',
    lineColor:          '#1fb69a',
    secondaryColor:     '#f3f4f6',
    tertiaryColor:      '#ffffff',
  },
});

// ── Fetch helpers ──────────────────────────────────────────────────────────
async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    // Try to parse structured JSON error so callers can render it nicely.
    let parsed = null;
    try { parsed = await res.json(); } catch (_) {}
    if (parsed) {
      const err = new Error(parsed.error || `${res.status} ${res.statusText}`);
      err.status = res.status;
      err.body = parsed;
      throw err;
    }
    const body = await res.text().catch(() => '');
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json();
}

// ── Workflow list ──────────────────────────────────────────────────────────
async function loadWorkflows() {
  try {
    const { workflows } = await api('/api/workflows');
    state.workflows = workflows;
    renderWorkflowList();
    // Auto-select the first one if nothing selected yet.
    if (!state.selectedId && workflows.length) {
      selectWorkflow(workflows[0].id);
    }
    // Topbar meta
    $('topbar-meta').textContent =
      `${workflows.length} workflow${workflows.length === 1 ? '' : 's'}`;
  } catch (e) {
    $('workflow-list').innerHTML =
      `<li class="empty-hint">Failed to load: ${escapeHtml(e.message)}</li>`;
  }
}

function renderWorkflowList() {
  const ul = $('workflow-list');
  if (!state.workflows.length) {
    ul.innerHTML =
      `<li class="empty-hint">No workflows yet. Ask Claude to make one.</li>`;
    return;
  }
  ul.innerHTML = state.workflows.map((w) => {
    const last = w.last_run;
    const dot = last ? `<span class="status-dot ${last.status}"></span>` : `<span class="status-dot"></span>`;
    const lastLabel = last
      ? `${last.status} · ${timeAgo(last.started_at)}`
      : 'never run';
    const sel = w.id === state.selectedId ? ' selected' : '';
    const danger = w.danger && w.danger !== 'low'
      ? `<span class="danger-pip danger-${w.danger}" title="danger: ${w.danger}"></span>`
      : '';
    return `
      <li class="workflow-item${sel}" data-id="${escapeAttr(w.id)}">
        <span class="name">${danger}${escapeHtml(w.name || w.id)}</span>
        <span class="meta">${dot} ${escapeHtml(lastLabel)} · ${w.node_count} nodes</span>
      </li>`;
  }).join('');

  ul.querySelectorAll('.workflow-item').forEach(li => {
    li.addEventListener('click', () => selectWorkflow(li.dataset.id));
  });
}

// ── Workflow detail ────────────────────────────────────────────────────────
async function selectWorkflow(id) {
  state.selectedId = id;
  renderWorkflowList();
  $('empty-state').hidden = true;
  $('workflow-view').hidden = false;
  $('wf-name').textContent = '…';
  $('wf-desc').textContent = '';
  $('wf-chips').innerHTML = '';
  $('mermaid-target').innerHTML = '';
  $('raw-json').textContent = '';

  try {
    const { workflow, mermaid: mSrc, danger, effects } =
      await api(`/api/workflows/${encodeURIComponent(id)}`);
    state.currentWorkflow = workflow;
    state.currentMermaid = mSrc;

    $('wf-name').textContent = workflow.name || workflow.id;
    $('wf-desc').textContent = workflow.description || '';
    const chips = [];
    (workflow.triggers || []).forEach(t =>
      chips.push(`<span class="chip primary">${escapeHtml(t.type || 'trigger')}</span>`)
    );
    chips.push(`<span class="chip">${(workflow.nodes || []).length} nodes</span>`);
    chips.push(`<span class="chip">${(workflow.edges || []).length} edges</span>`);
    if (danger && danger !== 'low') {
      chips.push(`<span class="chip danger danger-${danger}">danger: ${danger}</span>`);
    }
    (effects || []).forEach(e => {
      if (e !== 'read_only') {
        chips.push(`<span class="chip effect effect-${e}">${escapeHtml(e.replace('_', ' '))}</span>`);
      }
    });
    $('wf-chips').innerHTML = chips.join('');

    // Render Mermaid
    const target = $('mermaid-target');
    target.removeAttribute('data-processed');
    target.innerHTML = mSrc;
    try {
      await mermaid.run({ nodes: [target] });
    } catch (e) {
      target.innerHTML = `<pre class="raw-json">${escapeHtml(mSrc)}</pre>`;
    }

    // Raw JSON
    $('raw-json').textContent = JSON.stringify(workflow, null, 2);

    loadRuns(id);
  } catch (e) {
    $('wf-name').textContent = 'Failed to load';
    $('wf-desc').textContent = e.message;
  }
}

// ── Runs ───────────────────────────────────────────────────────────────────
async function loadRuns(workflowId) {
  try {
    const { runs } = await api(`/api/runs?workflow_id=${encodeURIComponent(workflowId)}&limit=50`);
    state.runs = runs;
    $('runs-count').textContent = `${runs.length} run${runs.length === 1 ? '' : 's'}`;
    renderRuns(runs);
  } catch (e) {
    $('runs').innerHTML = `<div class="empty-hint">Failed to load runs: ${escapeHtml(e.message)}</div>`;
  }
}

function renderRuns(runs) {
  const el = $('runs');
  if (!runs.length) {
    el.innerHTML = `<div class="empty-hint">No runs yet. Click Run.</div>`;
    return;
  }
  el.innerHTML = runs.map((r) => {
    const dur = (r.ended_at && r.started_at)
      ? `${((r.ended_at - r.started_at) * 1000).toFixed(0)}ms`
      : '—';
    return `
      <div class="run-row" data-id="${escapeAttr(r.id)}">
        <span>${escapeHtml(timeLong(r.started_at))}</span>
        <span class="run-status ${r.status}">
          <span class="status-dot ${r.status}"></span>${escapeHtml(r.status)}
        </span>
        <span>${dur}</span>
        <span class="run-id">${escapeHtml(r.id)}</span>
        <span class="muted small">${r.error ? escapeHtml(r.error.split('\n')[0].slice(0, 60)) : ''}</span>
      </div>`;
  }).join('');
  el.querySelectorAll('.run-row').forEach(row => {
    row.addEventListener('click', () => openRunModal(row.dataset.id));
  });
}

// ── Run trigger ────────────────────────────────────────────────────────────
async function triggerRun() {
  if (!state.selectedId) return;
  const btn = $('run-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="run-icon">⟳</span> Running…';
  try {
    const { run_id, error } = await api('/api/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workflow_id: state.selectedId, payload: null }),
    });
    if (error) throw new Error(error);
    await loadRuns(state.selectedId);
    await loadWorkflows(); // refresh sidebar last-run status
    openRunModal(run_id);
  } catch (e) {
    if (e.body && Array.isArray(e.body.errors)) {
      const rows = e.body.errors
        .map(x => `  • ${x.path}: ${x.message}`)
        .join('\n');
      openRunModalError(`Validation failed (${e.body.errors.length} error${e.body.errors.length === 1 ? '' : 's'}):\n\n${rows}`);
    } else {
      openRunModalError(e.message);
    }
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span class="run-icon">▶</span> Run';
  }
}

// ── Run modal ──────────────────────────────────────────────────────────────
async function openRunModal(runId) {
  $('run-modal').hidden = false;
  $('run-modal-title').textContent = `Run ${runId.slice(0, 8)}…`;
  $('run-modal-body').innerHTML = '<div class="empty-hint">Loading…</div>';
  try {
    const { run, nodes } = await api(`/api/runs/${encodeURIComponent(runId)}`);
    const dur = (run.ended_at && run.started_at)
      ? `${((run.ended_at - run.started_at) * 1000).toFixed(0)}ms` : '—';

    const finalBlock = run.final_outputs && Object.keys(run.final_outputs).length
      ? `<div class="kv-label">Final outputs</div>
         <pre>${escapeHtml(JSON.stringify(run.final_outputs, null, 2))}</pre>`
      : '';
    const errBlock = run.error
      ? `<div class="kv-label">Run error</div><pre class="error">${escapeHtml(run.error)}</pre>`
      : '';
    const gitBlock = (run.pre_run_git_checkpoints || run.post_run_git_checkpoints)
      ? `<div class="kv-label">Git checkpoints</div>
         <pre>${escapeHtml(JSON.stringify({
           pre: run.pre_run_git_checkpoints || {},
           post: run.post_run_git_checkpoints || {},
         }, null, 2))}</pre>`
      : '';

    const nodeBlocks = nodes.map((n) => {
      const nDur = (n.ended_at && n.started_at)
        ? `${((n.ended_at - n.started_at) * 1000).toFixed(0)}ms` : '';
      return `
        <div class="node-run">
          <div class="node-run-header">
            <span class="status-dot ${n.status}"></span>
            <span class="node-id">${escapeHtml(n.node_id)}</span>
            <span class="tpl">(${escapeHtml(n.template_id)})</span>
            <span class="muted small">· ${escapeHtml(n.status)} · ${nDur}</span>
          </div>
          <div class="node-run-body">
            ${n.error ? `<div class="kv-label">error</div><pre class="error">${escapeHtml(n.error)}</pre>` : ''}
            <div class="kv-label">inputs</div>
            <pre>${escapeHtml(JSON.stringify(n.inputs ?? null, null, 2))}</pre>
            <div class="kv-label">outputs</div>
            <pre>${escapeHtml(JSON.stringify(n.outputs ?? null, null, 2))}</pre>
          </div>
        </div>`;
    }).join('');

    const resumeChip = run.resumed_from
      ? `<span class="chip effect">resumed from ${escapeHtml(run.resumed_from.slice(0, 8))}</span>`
      : '';
    const canResume = run.status === 'failed';
    const resumeBtn = canResume
      ? `<button class="primary-btn" id="resume-btn" data-run-id="${escapeAttr(run.id)}" data-workflow-id="${escapeAttr(run.workflow_id)}">
           <span class="run-icon">↻</span> Resume from this run
         </button>`
      : '';

    $('run-modal-body').innerHTML = `
      <div class="chip-row">
        <span class="chip primary">${escapeHtml(run.status)}</span>
        <span class="chip">${escapeHtml(run.workflow_id)}</span>
        <span class="chip">${escapeHtml(dur)}</span>
        <span class="chip">${escapeHtml(timeLong(run.started_at))}</span>
        ${resumeChip}
      </div>
      ${resumeBtn ? `<div style="margin-top:0.75rem;">${resumeBtn}</div>` : ''}
      ${errBlock}
      ${finalBlock}
      ${gitBlock}
      <div class="kv-label" style="margin-top:1rem;">Nodes</div>
      ${nodeBlocks || '<div class="empty-hint">No node runs recorded.</div>'}
    `;

    const rb = document.getElementById('resume-btn');
    if (rb) rb.addEventListener('click', () => resumeRun(rb.dataset.workflowId, rb.dataset.runId));
  } catch (e) {
    openRunModalError(e.message);
  }
}

function openRunModalError(msg) {
  $('run-modal').hidden = false;
  $('run-modal-title').textContent = 'Run failed to load';
  $('run-modal-body').innerHTML = `<pre class="error">${escapeHtml(msg)}</pre>`;
}

function closeRunModal() { $('run-modal').hidden = true; }

async function resumeRun(workflowId, priorRunId) {
  const rb = document.getElementById('resume-btn');
  if (rb) { rb.disabled = true; rb.innerHTML = '<span class="run-icon">⟳</span> Resuming…'; }
  try {
    const { run_id } = await api('/api/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        workflow_id: workflowId,
        payload: null,
        resume_from: priorRunId,
      }),
    });
    if (state.selectedId) await loadRuns(state.selectedId);
    await loadWorkflows();
    openRunModal(run_id);
  } catch (e) {
    if (e.body && Array.isArray(e.body.errors)) {
      const rows = e.body.errors.map(x => `  • ${x.path}: ${x.message}`).join('\n');
      openRunModalError(`Validation failed:\n\n${rows}`);
    } else {
      openRunModalError(e.message);
    }
  }
}

// ── Raw JSON toggle ────────────────────────────────────────────────────────
function toggleRaw() {
  const body = $('raw-json');
  const chev = $('raw-chev');
  const isOpen = !body.hidden;
  body.hidden = isOpen;
  chev.classList.toggle('open', !isOpen);
}

// ── Helpers ────────────────────────────────────────────────────────────────
function escapeHtml(s) {
  if (s == null) return '';
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
function escapeAttr(s) { return escapeHtml(s); }

function timeLong(ts) {
  if (!ts) return '—';
  const d = new Date(ts * 1000);
  return d.toLocaleString(undefined, {
    month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}
function timeAgo(ts) {
  if (!ts) return 'never';
  const diff = (Date.now() / 1000) - ts;
  if (diff < 60) return `${Math.round(diff)}s ago`;
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
  return `${Math.round(diff / 86400)}d ago`;
}

// ── Events ─────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  $('refresh-btn').addEventListener('click', () => {
    loadWorkflows();
    if (state.selectedId) selectWorkflow(state.selectedId);
  });
  $('run-btn').addEventListener('click', triggerRun);
  $('raw-toggle').addEventListener('click', toggleRaw);
  $('run-modal-close').addEventListener('click', closeRunModal);
  $('run-modal').addEventListener('click', (e) => {
    if (e.target.id === 'run-modal') closeRunModal();
  });
  loadWorkflows();
});
