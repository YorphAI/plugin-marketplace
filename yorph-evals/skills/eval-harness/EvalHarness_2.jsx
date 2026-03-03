import { useState, useRef, useCallback } from "react";
import * as XLSX from "xlsx";
import { BarChart, Bar, RadarChart, Radar, PolarGrid, PolarAngleAxis, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

const C = {
  bg:"#080a0f", surface:"#0f1118", border:"#1a1f2e", borderBright:"#242b40",
  text:"#b8c2e0", textDim:"#434d6a", textBright:"#dde3ff",
  A:"#f0a500", Adim:"rgba(240,165,0,0.12)",
  B:"#00c9a0", Bdim:"rgba(0,201,160,0.10)",
  red:"#ff4566", purple:"#9b7fff",
  mono:"'IBM Plex Mono', monospace", sans:"'DM Sans', sans-serif",
};

const gs = `
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600&display=swap');
  *{box-sizing:border-box;margin:0;padding:0;}
  ::-webkit-scrollbar{width:3px;height:3px;}
  ::-webkit-scrollbar-thumb{background:#242b40;border-radius:2px;}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:0.3}}
  @keyframes fadeIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
`;

async function readFile(file) {
  if (file.name.match(/\.(xlsx|xls)$/i)) {
    return new Promise(res => {
      const r = new FileReader();
      r.onload = e => {
        const wb = XLSX.read(e.target.result, { type: "binary" });
        res(wb.SheetNames.map(n => "=== Sheet: " + n + " ===\n" + XLSX.utils.sheet_to_csv(wb.Sheets[n])).join("\n\n"));
      };
      r.readAsBinaryString(file);
    });
  }
  return new Promise(res => { const r = new FileReader(); r.onload = e => res(e.target.result); r.readAsText(file); });
}

async function callClaude(system, user, maxTokens) {
  const tokens = maxTokens || 30000;
  const body = { model: "claude-sonnet-4-20250514", max_tokens: tokens, messages: [{ role: "user", content: user }] };
  if (system && system.trim()) body.system = system;
  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!res.ok) {
    const e = await res.json().catch(() => ({}));
    throw new Error(e.error ? e.error.message : "HTTP " + res.status);
  }
  const d = await res.json();
  const text = d.content.filter(b => b.type === "text").map(b => b.text).join("");
  return { text, stop_reason: d.stop_reason };
}

function buildAnalystPrompt(dataCtx) {
  const data = dataCtx
    ? "Here is the dataset to analyze:\n\n" + dataCtx
    : "(No data provided)";
  return "You are a senior data analyst conducting a thorough data quality review.\n\n" + data + "\n\nPlease analyze this data comprehensively. Look for any issues, anomalies, or problems including:\n- Data quality issues (nulls, outliers, impossible values, duplicates)\n- Schema or structural problems (type mismatches, inconsistent casing, encoding)\n- Metric or calculation ambiguities (columns that should match but don't)\n- Temporal/date issues (partial periods, backdating, inconsistent formats)\n- Join or relational problems if multiple tables are present (orphaned keys, fanout, key type mismatches)\n- Business logic problems (cancelled orders in revenue, status lifecycle issues)\n\nBe thorough and specific. Name exact columns and values affected where possible.";
}

// Judge prompt: just give it the data + responses.
// The judge skill (system prompt) carries all rubric logic.
function buildJudgePrompt(dataCtx, responseA, responseB) {
  return "You are evaluating two data analysts who were each given the same dataset and asked to find any issues — with no hints about what to look for.\n\n" +
    "## Data Context\n" + (dataCtx || "(no data provided)") + "\n\n" +
    "## Analyst A Response\n" + responseA + "\n\n" +
    "## Analyst B Response\n" + responseB + "\n\n" +
    "Apply your evaluation rubric to score both analysts. Derive the challenge set from the data and responses — do not expect a manifest to be provided. Follow your skill instructions exactly and output only the required JSON.";
}

function DropZone({ label, accept, multiple, onFiles }) {
  const [drag, setDrag] = useState(false);
  const ref = useRef();
  return (
    <div
      onDragOver={e => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={e => { e.preventDefault(); setDrag(false); onFiles(Array.from(e.dataTransfer.files)); }}
      onClick={() => ref.current.click()}
      style={{ border: "1px dashed " + (drag ? "#f0a500" : "#242b40"), borderRadius: 6, padding: "11px 16px",
        background: drag ? "rgba(240,165,0,0.12)" : "transparent", cursor: "pointer", textAlign: "center", transition: "all 0.2s" }}>
      <input ref={ref} type="file" accept={accept} multiple={multiple} style={{ display: "none" }}
        onChange={e => onFiles(Array.from(e.target.files))} />
      <div style={{ fontFamily: C.mono, fontSize: 10, color: C.textDim, letterSpacing: "0.1em" }}>{"⬆ " + label}</div>
    </div>
  );
}

function Pill({ name, onRemove }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5, background: C.surface,
      border: "1px solid " + C.borderBright, borderRadius: 20, padding: "2px 8px 2px 6px",
      fontFamily: C.mono, fontSize: 10, color: C.text, marginRight: 5, marginBottom: 4 }}>
      <span style={{ color: C.B }}>{"◆"}</span>{name}
      <span onClick={e => { e.stopPropagation(); onRemove(); }}
        style={{ cursor: "pointer", color: C.textDim, marginLeft: 2, fontSize: 11 }}>{"✕"}</span>
    </span>
  );
}

function Log({ entries }) {
  return (
    <div style={{ fontFamily: C.mono, fontSize: 10, lineHeight: 1.8, overflowY: "auto", maxHeight: "100%", padding: "10px 14px" }}>
      {!entries.length && <span style={{ color: C.textDim }}>No activity yet.</span>}
      {entries.map((e, i) => (
        <div key={i} style={{ animation: "fadeIn 0.2s ease",
          color: e.type === "error" ? C.red : e.type === "success" ? C.B : e.type === "info" ? C.A : C.textDim }}>
          <span style={{ color: C.textDim, marginRight: 8 }}>{e.ts}</span>{e.msg}
        </div>
      ))}
    </div>
  );
}

function ScoreBar({ scoreA, scoreB }) {
  if (scoreA == null) return null;
  return (
    <div style={{ display: "flex", gap: 5, alignItems: "center", marginTop: 5 }}>
      <span style={{ fontFamily: C.mono, fontSize: 9, color: C.A, width: 18, textAlign: "right" }}>{scoreA}</span>
      <div style={{ flex: 1, height: 4, background: C.border, borderRadius: 2, overflow: "hidden" }}>
        <div style={{ width: (scoreA * 10) + "%", height: "100%", background: C.A, transition: "width 0.5s" }} />
      </div>
      <div style={{ flex: 1, height: 4, background: C.border, borderRadius: 2, overflow: "hidden", transform: "scaleX(-1)" }}>
        <div style={{ width: (scoreB * 10) + "%", height: "100%", background: C.B, transition: "width 0.5s" }} />
      </div>
      <span style={{ fontFamily: C.mono, fontSize: 9, color: C.B, width: 18 }}>{scoreB}</span>
    </div>
  );
}

function ChallengeRow({ c, active, onClick, idx }) {
  const dc = c.difficulty === "Easy" ? C.B : c.difficulty === "Hard" ? C.red : C.A;
  const scored = c.scoreA != null;
  const icon = !scored ? "○" : c.winner === "A" ? "▲" : c.winner === "B" ? "▼" : "═";
  const ic = !scored ? C.textDim : c.winner === "A" ? C.A : c.winner === "B" ? C.B : C.purple;
  return (
    <div onClick={onClick} style={{ padding: "9px 14px", borderBottom: "1px solid " + C.border, cursor: "pointer",
      background: active ? "rgba(240,165,0,0.04)" : "transparent",
      borderLeft: "2px solid " + (active ? C.A : "transparent"), transition: "all 0.15s" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
        <span style={{ fontFamily: C.mono, fontSize: 11, color: ic }}>{icon}</span>
        <span style={{ fontSize: 12, color: C.textBright, fontWeight: 500, flex: 1 }}>{(idx + 1) + ". " + c.name}</span>
        {c.difficulty && <span style={{ fontFamily: C.mono, fontSize: 9, color: dc, background: dc + "1a", padding: "1px 5px", borderRadius: 2 }}>{c.difficulty}</span>}
      </div>
      {c.category && <div style={{ fontFamily: C.mono, fontSize: 9, color: C.textDim, marginTop: 2 }}>{c.category}</div>}
      <ScoreBar scoreA={c.scoreA} scoreB={c.scoreB} />
      {scored && <div style={{ fontFamily: C.mono, fontSize: 9, color: ic, marginTop: 3 }}>
        {c.winner === "TIE" ? "TIE" : "Condition " + c.winner + " wins"}
      </div>}
    </div>
  );
}

const DEFAULT_JUDGE_SKILL = `You are an expert evaluator comparing two data analysts on data quality tasks.

Apply the following rubric:

## Derive the Challenge Set
Read the data and both responses. Construct challenges from these categories:
- Temporal (partial periods, backdated records, inconsistent formats)
- Metric Ambiguity (columns measuring the same thing differently, grain mismatches)
- Structural / Schema (inconsistent casing, mixed types, duplicates, null codes)
- Null Patterns (structured/conditional nulls, high null rates)
- Relational / Join (key mismatches, fanout, orphaned FKs, ID collisions)
- Business Logic (label leakage, status traps, impossible values, outliers)

Include a challenge if: it is detectable from the data AND would materially affect analysis if missed.
Aim for 5-10 challenges. Don't pad. Don't collapse distinct issues.

## Score Each Challenge (per analyst)
- detectionScore 0-3: 0=missed, 1=vague hint, 2=clearly identified, 3=identified with specific column/value/count
- depthScore 0-3: 0=none, 1=named only, 2=explained impact, 3=root cause + quantified
- handlingScore 0-4: 0=none, 1=acknowledged, 2=plausible fix, 3=correct specific fix, 4=correct fix + verified

Total = sum (max 10). Winner = higher scorer; TIE if within 1 point.

## Difficulty Heuristic
- Easy: visible with .value_counts(), .info(), .describe()
- Medium: requires cross-tabulation or comparing aggregates
- Hard: requires domain knowledge, temporal reasoning, or multi-step verification

## Output
Respond ONLY with valid JSON, no markdown, no text outside the object:
{"responseASummary":"...","responseBSummary":"...","overallWinner":"A"|"B"|"TIE","overallReasoning":"...","challenges":[{"name":"...","category":"...","difficulty":"Easy|Medium|Hard","description":"...","scoreA":N,"scoreB":N,"winner":"A"|"B"|"TIE","detectionA":N,"detectionB":N,"depthA":N,"depthB":N,"handlingA":N,"handlingB":N,"reasoning":"..."}]}`;

export default function EvalHarness() {
  const [tab, setTab] = useState("setup");
  const [systemA, setSystemA] = useState("You are a helpful data analyst. Analyze the data thoroughly and identify any issues, ambiguities, and quality problems you find.");
  const [systemB, setSystemB] = useState("");
  const [judgeSkill, setJudgeSkill] = useState(DEFAULT_JUDGE_SKILL);
  const [dataFiles, setDataFiles] = useState([]);
  const [logs, setLogs] = useState([]);
  const [evalResult, setEvalResult] = useState(null);
  const [running, setRunning] = useState(false);
  const [phase, setPhase] = useState("");
  const [selected, setSelected] = useState(null);

  const log = useCallback((msg, type) => {
    const t = type || "dim";
    const ts = new Date().toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
    setLogs(prev => [...prev.slice(-200), { msg, type: t, ts }]);
  }, []);

  const handleSkillFiles = useCallback(async (files, setter) => {
    const text = await readFile(files[0]);
    setter(text);
    log("Loaded: " + files[0].name + " (" + text.length + " chars)", "success");
  }, [log]);

  const handleDataFiles = useCallback(async files => {
    log("Loading " + files.length + " file(s)...", "info");
    const loaded = await Promise.all(files.map(async f => {
      const content = await readFile(f);
      log("  ok " + f.name + " - " + content.split("\n").length + " lines", "success");
      return { name: f.name, content };
    }));
    setDataFiles(prev => {
      const names = new Set(prev.map(f => f.name));
      return [...prev, ...loaded.filter(f => !names.has(f.name))];
    });
  }, [log]);

  const runEval = async () => {
    if (running) return;
    if (!systemB.trim()) { log("Condition B is empty - paste your analyst skill first", "error"); return; }
    setRunning(true); setEvalResult(null); setSelected(null); setTab("results");

    const dataCtx = dataFiles.map(f => "=== File: " + f.name + " ===\n" + f.content.slice(0, 6000)).join("\n\n");
    const analystPrompt = buildAnalystPrompt(dataCtx);

    try {
      setPhase("calling A + B in parallel...");
      log("Step 1: Calling A and B blind (no challenge hints)", "info");

      const [resA, resB] = await Promise.all([
        callClaude(systemA, analystPrompt, 30000),
        callClaude(systemB, analystPrompt, 30000),
      ]);

      if (resA.stop_reason === "max_tokens") log("WARNING: Condition A was TRUNCATED", "error");
      if (resB.stop_reason === "max_tokens") log("WARNING: Condition B was TRUNCATED", "error");
      log("A: " + resA.text.length + " chars, stop=" + resA.stop_reason, "success");
      log("B: " + resB.text.length + " chars, stop=" + resB.stop_reason, "success");

      setPhase("judging...");
      log("Step 2: Judge deriving challenges and scoring both responses...", "info");
      const judgeRes = await callClaude(judgeSkill, buildJudgePrompt(dataCtx, resA.text, resB.text), 30000);

      if (judgeRes.stop_reason === "max_tokens") log("WARNING: Judge response was truncated", "error");
      log("Judge responded - parsing...", "info");

      let judgeData;
      try {
        judgeData = JSON.parse(judgeRes.text.replace(/```json|```/g, "").trim());
      } catch(e) {
        throw new Error("Judge returned unparseable JSON: " + judgeRes.text.slice(0, 400));
      }

      setEvalResult({
        responseA: resA.text,
        responseB: resB.text,
        responseASummary: judgeData.responseASummary,
        responseBSummary: judgeData.responseBSummary,
        overallWinner: judgeData.overallWinner,
        overallReasoning: judgeData.overallReasoning,
        challenges: judgeData.challenges || [],
      });

      setSelected(0);
      const ch = judgeData.challenges || [];
      const bW = ch.filter(c => c.winner === "B").length;
      const aW = ch.filter(c => c.winner === "A").length;
      log("Done - " + ch.length + " challenges derived. B wins " + bW + ", A wins " + aW, bW > aW ? "success" : "info");

    } catch(err) {
      log("Error: " + err.message, "error");
    } finally {
      setRunning(false); setPhase("");
    }
  };

  const chs = evalResult ? evalResult.challenges : [];
  const wA = chs.filter(c => c.winner === "A").length;
  const wB = chs.filter(c => c.winner === "B").length;
  const ties = chs.filter(c => c.winner === "TIE").length;

  const barData = chs.map((c, i) => ({ name: "" + (i + 1), A: c.scoreA || 0, B: c.scoreB || 0 }));
  const radarData = ["Easy", "Medium", "Hard"].map(d => {
    const rel = chs.filter(c => c.difficulty === d);
    return {
      subject: d,
      A: rel.length ? +(rel.reduce((s,c) => s + (c.scoreA||0), 0) / rel.length).toFixed(1) : 0,
      B: rel.length ? +(rel.reduce((s,c) => s + (c.scoreB||0), 0) / rel.length).toFixed(1) : 0,
    };
  });

  const selCh = selected !== null ? chs[selected] : null;
  const wc = w => w === "A" ? C.A : w === "B" ? C.B : C.purple;
  const wb = w => w === "A" ? C.Adim : w === "B" ? C.Bdim : "rgba(155,127,255,0.1)";

  const TA = { fontFamily: C.mono, fontSize: 11, background: C.bg, color: C.textBright,
    border: "1px solid " + C.borderBright, borderRadius: 4, padding: "8px 10px",
    width: "100%", resize: "vertical", outline: "none", lineHeight: 1.7 };

  const isDisabled = running;

  return (
    <div style={{ background: C.bg, minHeight: "100vh", color: C.text, fontFamily: C.sans, display: "flex", flexDirection: "column" }}>
      <style>{gs}</style>

      {/* Header */}
      <div style={{ background: C.surface, borderBottom: "1px solid " + C.border, padding: "10px 18px",
        display: "flex", alignItems: "center", gap: 14, position: "sticky", top: 0, zIndex: 100 }}>
        <div style={{ fontFamily: C.mono, fontSize: 11, color: C.A, letterSpacing: "0.15em", display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ width: 7, height: 7, borderRadius: "50%", background: C.A, display: "inline-block",
            boxShadow: "0 0 8px " + C.A, animation: running ? "pulse 1s infinite" : "none" }} />
          EVAL HARNESS
        </div>
        {["setup", "results", "logs"].map(t => (
          <button key={t} onClick={() => setTab(t)} style={{ fontFamily: C.mono, fontSize: 10, letterSpacing: "0.1em",
            textTransform: "uppercase", padding: "5px 12px", borderRadius: 3, border: "none", cursor: "pointer",
            background: tab === t ? C.A : "transparent", color: tab === t ? "#000" : C.textDim, fontWeight: tab === t ? 700 : 400 }}>
            {t}{t === "logs" && logs.length ? " (" + logs.length + ")" : ""}
          </button>
        ))}
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 12 }}>
          {running && <span style={{ fontFamily: C.mono, fontSize: 10, color: C.A }}>{phase}</span>}
          <span style={{ fontFamily: C.mono, fontSize: 9, padding: "3px 8px", borderRadius: 3, background: C.Adim, color: C.A, border: "1px solid " + C.A }}>A: BASELINE</span>
          <span style={{ fontFamily: C.mono, fontSize: 9, padding: "3px 8px", borderRadius: 3, background: C.Bdim, color: C.B, border: "1px solid " + C.B }}>B: SKILL</span>
          <button onClick={runEval} disabled={isDisabled} style={{
            fontFamily: C.mono, fontSize: 11, fontWeight: 700, letterSpacing: "0.08em",
            padding: "7px 18px", borderRadius: 4, border: "none",
            cursor: isDisabled ? "not-allowed" : "pointer",
            background: isDisabled ? C.borderBright : C.A,
            color: isDisabled ? C.textDim : "#000", transition: "all 0.15s" }}>
            {running ? "● " + phase : "▶ RUN EVAL"}
          </button>
        </div>
      </div>

      {/* SETUP — 4 columns: data | judge skill | condition A | condition B */}
      {tab === "setup" && (
        <div style={{ display: "grid", gridTemplateColumns: "220px 1fr 1fr 1fr", flex: 1 }}>

          {/* Col 1: Data files */}
          <div style={{ borderRight: "1px solid " + C.border, padding: 18, display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ fontFamily: C.mono, fontSize: 9, letterSpacing: "0.2em", color: C.textDim, textTransform: "uppercase" }}>Data Files</div>
            <DropZone label="Drop CSV / Excel / TXT" accept=".csv,.xlsx,.xls,.txt,.json,.md" multiple onFiles={handleDataFiles} />
            <div>
              {dataFiles.map((f, i) => <Pill key={i} name={f.name} onRemove={() => setDataFiles(p => p.filter((_, j) => j !== i))} />)}
              {!dataFiles.length && <div style={{ fontFamily: C.mono, fontSize: 10, color: C.textDim, marginTop: 4 }}>No files loaded</div>}
            </div>
            <div style={{ marginTop: "auto", fontFamily: C.mono, fontSize: 9, color: C.textDim, lineHeight: 1.8, padding: "8px 10px",
              background: "rgba(255,255,255,0.02)", borderRadius: 4, border: "1px solid " + C.border }}>
              Files are sent to all three calls (A, B, judge) truncated to 6000 chars each.
            </div>
          </div>

          {/* Col 2: Judge skill */}
          <div style={{ borderRight: "1px solid " + C.border, padding: 18, display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ fontFamily: C.mono, fontSize: 9, letterSpacing: "0.2em", color: C.purple, textTransform: "uppercase" }}>Judge Skill</div>
            <div style={{ fontFamily: C.mono, fontSize: 10, color: C.textDim, lineHeight: 1.6, padding: "8px 10px",
              background: "rgba(155,127,255,0.05)", borderRadius: 4, border: "1px solid rgba(155,127,255,0.15)" }}>
              The judge derives challenges from the data and responses using this rubric — no dataset-specific manifest needed.
            </div>
            <DropZone label="Drop judge-SKILL.md to override" accept=".md,.txt" onFiles={f => handleSkillFiles(f, setJudgeSkill)} />
            <textarea value={judgeSkill} onChange={e => setJudgeSkill(e.target.value)} rows={22} style={TA} />
          </div>

          {/* Col 3: Condition A */}
          <div style={{ borderRight: "1px solid " + C.border, padding: 18, display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ fontFamily: C.mono, fontSize: 9, letterSpacing: "0.2em", color: C.A, textTransform: "uppercase" }}>Condition A — Baseline</div>
            <div style={{ fontFamily: C.mono, fontSize: 10, color: C.textDim, lineHeight: 1.6, padding: "8px 10px",
              background: "rgba(240,165,0,0.05)", borderRadius: 4, border: "1px solid " + C.Adim }}>
              Both analysts get the same blind prompt — no challenge hints.
            </div>
            <textarea value={systemA} onChange={e => setSystemA(e.target.value)} rows={22} style={TA} />
          </div>

          {/* Col 4: Condition B */}
          <div style={{ padding: 18, display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ fontFamily: C.mono, fontSize: 9, letterSpacing: "0.2em", color: C.B, textTransform: "uppercase" }}>Condition B — Analyst Skill</div>
            <div style={{ fontFamily: C.mono, fontSize: 10, color: C.textDim, lineHeight: 1.6, padding: "8px 10px",
              background: "rgba(0,201,160,0.05)", borderRadius: 4, border: "1px solid " + C.Bdim }}>
              Same blind prompt — only the system prompt differs.
            </div>
            <DropZone label="Drop SKILL.md here" accept=".md,.txt" onFiles={f => handleSkillFiles(f, setSystemB)} />
            <textarea value={systemB} onChange={e => setSystemB(e.target.value)} rows={19} style={TA} placeholder="Paste analyst SKILL.md or drop above..." />
          </div>
        </div>
      )}

      {/* RESULTS */}
      {tab === "results" && (
        <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", flex: 1, minHeight: 0, overflow: "hidden" }}>
          <div style={{ borderRight: "1px solid " + C.border, overflowY: "auto", display: "flex", flexDirection: "column" }}>
            {evalResult && (
              <div style={{ padding: "12px 14px", borderBottom: "1px solid " + C.border, background: wb(evalResult.overallWinner) }}>
                <div style={{ fontFamily: C.mono, fontSize: 11, fontWeight: 700, color: wc(evalResult.overallWinner), marginBottom: 5 }}>
                  {"OVERALL: " + (evalResult.overallWinner === "TIE" ? "TIE" : "CONDITION " + evalResult.overallWinner + " WINS")}
                </div>
                <div style={{ fontSize: 11, color: C.text, lineHeight: 1.5 }}>{evalResult.overallReasoning}</div>
              </div>
            )}
            {chs.length > 0 && (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", borderBottom: "1px solid " + C.border }}>
                {[["A", wA, C.A], ["B", wB, C.B], ["TIE", ties, C.purple]].map(([l, v, c]) => (
                  <div key={l} style={{ padding: "10px 6px", textAlign: "center", borderRight: "1px solid " + C.border }}>
                    <div style={{ fontFamily: C.mono, fontSize: 20, fontWeight: 700, color: c, lineHeight: 1 }}>{v}</div>
                    <div style={{ fontFamily: C.mono, fontSize: 9, color: C.textDim, marginTop: 2, letterSpacing: "0.08em" }}>{l}</div>
                  </div>
                ))}
              </div>
            )}
            {!chs.length
              ? <div style={{ padding: 24, textAlign: "center", fontFamily: C.mono, fontSize: 10, color: C.textDim, lineHeight: 2 }}>
                  {running ? phase : "No results yet.\nRun the eval first."}
                </div>
              : chs.map((c, i) => <ChallengeRow key={i} c={c} active={selected === i} onClick={() => setSelected(i)} idx={i} />)
            }
          </div>

          <div style={{ display: "flex", flexDirection: "column", overflow: "hidden" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", borderBottom: "1px solid " + C.border, height: 210 }}>
              <div style={{ padding: "12px 18px", borderRight: "1px solid " + C.border }}>
                <div style={{ fontFamily: C.mono, fontSize: 9, color: C.textDim, letterSpacing: "0.15em", textTransform: "uppercase", marginBottom: 6 }}>Score per Challenge</div>
                <ResponsiveContainer width="100%" height={162}>
                  <BarChart data={barData} barGap={2} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                    <XAxis dataKey="name" tick={{ fill: C.textDim, fontFamily: C.mono, fontSize: 9 }} />
                    <YAxis domain={[0, 10]} tick={{ fill: C.textDim, fontFamily: C.mono, fontSize: 9 }} />
                    <Tooltip contentStyle={{ background: C.surface, border: "1px solid " + C.borderBright, fontFamily: C.mono, fontSize: 11 }} />
                    <Bar dataKey="A" fill={C.A} radius={[2, 2, 0, 0]} />
                    <Bar dataKey="B" fill={C.B} radius={[2, 2, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div style={{ padding: "12px 18px" }}>
                <div style={{ fontFamily: C.mono, fontSize: 9, color: C.textDim, letterSpacing: "0.15em", textTransform: "uppercase", marginBottom: 6 }}>Avg Score by Difficulty</div>
                <ResponsiveContainer width="100%" height={162}>
                  <RadarChart data={radarData} margin={{ top: 10, right: 20, left: 20, bottom: 10 }}>
                    <PolarGrid stroke={C.border} />
                    <PolarAngleAxis dataKey="subject" tick={{ fill: C.text, fontFamily: C.mono, fontSize: 10 }} />
                    <Radar name="A" dataKey="A" stroke={C.A} fill={C.A} fillOpacity={0.2} />
                    <Radar name="B" dataKey="B" stroke={C.B} fill={C.B} fillOpacity={0.2} />
                    <Tooltip contentStyle={{ background: C.surface, border: "1px solid " + C.borderBright, fontFamily: C.mono, fontSize: 11 }} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {!selCh
              ? <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: C.mono, fontSize: 11, color: C.textDim }}>
                  {running ? phase : evalResult ? "← Select a challenge" : "Run the eval to see results"}
                </div>
              : <div style={{ flex: 1, overflow: "auto" }}>
                  <div style={{ padding: "12px 18px", borderBottom: "1px solid " + C.border, background: C.surface }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: C.textBright }}>{selCh.name}</div>
                    <div style={{ fontFamily: C.mono, fontSize: 10, color: C.textDim, marginTop: 3 }}>
                      {[selCh.category, selCh.difficulty].filter(Boolean).join(" · ")}
                    </div>
                    {selCh.description && <div style={{ fontSize: 12, color: C.text, marginTop: 6, lineHeight: 1.5 }}>{selCh.description}</div>}
                  </div>

                  <div style={{ padding: "12px 18px", borderBottom: "1px solid " + C.border, background: "rgba(0,0,0,0.2)" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                      <span style={{ fontFamily: C.mono, fontSize: 11, fontWeight: 700, padding: "3px 12px", borderRadius: 3,
                        background: wb(selCh.winner), color: wc(selCh.winner), border: "1px solid " + wc(selCh.winner) }}>
                        {selCh.winner === "TIE" ? "TIE" : "CONDITION " + selCh.winner + " WINS"}
                      </span>
                      <span style={{ fontFamily: C.mono, fontSize: 10, padding: "2px 8px", borderRadius: 3, background: C.Adim, color: C.A }}>{"A: " + selCh.scoreA + "/10"}</span>
                      <span style={{ fontFamily: C.mono, fontSize: 10, padding: "2px 8px", borderRadius: 3, background: C.Bdim, color: C.B }}>{"B: " + selCh.scoreB + "/10"}</span>
                    </div>
                    <div style={{ fontSize: 12, color: C.text, lineHeight: 1.6, marginBottom: 10 }}>{selCh.reasoning}</div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
                      {[["Detection (0-3)", "detectionA", "detectionB"], ["Depth (0-3)", "depthA", "depthB"], ["Handling (0-4)", "handlingA", "handlingB"]].map(([l, kA, kB]) => (
                        <div key={l} style={{ background: C.surface, borderRadius: 4, padding: "7px 10px", border: "1px solid " + C.border }}>
                          <div style={{ fontFamily: C.mono, fontSize: 9, color: C.textDim, marginBottom: 4, letterSpacing: "0.08em" }}>{l.toUpperCase()}</div>
                          <div style={{ display: "flex", gap: 8 }}>
                            <span style={{ fontFamily: C.mono, fontSize: 11, color: C.A }}>{"A: " + selCh[kA]}</span>
                            <span style={{ fontFamily: C.mono, fontSize: 11, color: C.B }}>{"B: " + selCh[kB]}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div style={{ padding: "8px 18px", background: C.surface, borderBottom: "1px solid " + C.border }}>
                    <span style={{ fontFamily: C.mono, fontSize: 9, color: C.textDim, letterSpacing: "0.1em" }}>
                      FULL ANALYST RESPONSES — one per condition, judge scores all challenges from these
                    </span>
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr" }}>
                    {[["A", C.A, evalResult && evalResult.responseA, evalResult && evalResult.responseASummary],
                      ["B", C.B, evalResult && evalResult.responseB, evalResult && evalResult.responseBSummary]].map(([cond, color, resp, summary]) => (
                      <div key={cond} style={{ padding: "14px 18px",
                        borderRight: cond === "A" ? "1px solid " + C.border : "none",
                        borderTop: "1px solid " + C.border }}>
                        <div style={{ fontFamily: C.mono, fontSize: 10, color: color, letterSpacing: "0.12em", marginBottom: 4 }}>{"● CONDITION " + cond}</div>
                        <div style={{ fontFamily: C.mono, fontSize: 10, color: C.textDim, fontStyle: "italic", marginBottom: 10,
                          lineHeight: 1.5, padding: "6px 8px", background: C.surface, borderRadius: 4 }}>
                          {summary}
                        </div>
                        <div style={{ fontSize: 12, lineHeight: 1.75, color: C.text, whiteSpace: "pre-wrap" }}>{resp}</div>
                      </div>
                    ))}
                  </div>
                </div>
            }
          </div>
        </div>
      )}

      {/* LOGS */}
      {tab === "logs" && (
        <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
          <div style={{ padding: "8px 14px", borderBottom: "1px solid " + C.border, display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ fontFamily: C.mono, fontSize: 10, color: C.textDim, letterSpacing: "0.1em" }}>ACTIVITY LOG</span>
            <button onClick={() => setLogs([])} style={{ fontFamily: C.mono, fontSize: 10, padding: "3px 10px", borderRadius: 3,
              border: "1px solid " + C.borderBright, background: "transparent", color: C.textDim, cursor: "pointer" }}>Clear</button>
            <span style={{ fontFamily: C.mono, fontSize: 10, color: C.textDim, marginLeft: "auto" }}>{logs.length + " entries"}</span>
          </div>
          <div style={{ flex: 1, overflow: "auto" }}><Log entries={logs} /></div>
        </div>
      )}
    </div>
  );
}
