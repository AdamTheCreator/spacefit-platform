/* Perigee — Thinking-indicator exploration
 * Three options, all driven by the same simulated timeline so motion is comparable.
 */
const { useState, useEffect, useRef } = React;

/* ---------- Shared simulated timeline ---------- */
const AGENTS = [
  { id:'scout',      name:'Scout',      color:'#3A5BA0', task:'Pulling nearby businesses & demographics' },
  { id:'analyst',    name:'Analyst',    color:'#C25E1F', task:'Reviewing the trade area for gaps' },
  { id:'matchmaker', name:'Matchmaker', color:'#2F7A3B', task:'Scoring tenant fits against the roster' },
];

/* phase: 0 read, 1 plan, 2 scout, 3 analyst, 4 matchmaker, 5 draft, 6 done */
const PHASES = [
  { dur: 1700, label: 'Reading your question' },
  { dur: 1700, label: 'Planning the approach' },
  { dur: 2300, label: 'Researching the trade area' },
  { dur: 2300, label: 'Analyzing tenant gaps' },
  { dur: 2300, label: 'Matching tenants' },
  { dur: 1900, label: 'Drafting your answer' },
  { dur: 3200, label: 'Done' },
];

function usePhase() {
  const [phase, setPhase] = useState(0);
  const [tick, setTick] = useState(0); // elapsed seconds
  useEffect(() => {
    let alive = true;
    const t = setTimeout(() => {
      if (!alive) return;
      setPhase(p => {
        const next = (p + 1) % PHASES.length;
        if (next === 0) setTick(0);
        return next;
      });
    }, PHASES[phase].dur);
    return () => { alive = false; clearTimeout(t); };
  }, [phase]);
  useEffect(() => {
    const iv = setInterval(() => setTick(t => t + 1), 1000);
    return () => clearInterval(iv);
  }, []);
  return { phase, tick };
}

/* agent status for a phase: idle | active | done */
function agentStatus(i, phase) {
  const activeAt = i + 2; // scout@2, analyst@3, matchmaker@4
  if (phase < activeAt) return 'idle';
  if (phase === activeAt) return 'active';
  return 'done';
}

const isDone = (phase) => phase === 6;
const isWorking = (phase) => phase < 6;

/* ---------- Shared chat-frame chrome ---------- */
function UserBubble() {
  return (
    <div style={{display:'flex', justifyContent:'flex-end'}}>
      <div style={{maxWidth:'75%', background:'var(--navy)', color:'#fff', padding:'11px 15px',
        borderRadius:'16px 16px 4px 16px', fontSize:13.5, lineHeight:1.5}}>
        Analyze property: 29 Lovell Ave, Mill Valley CA — what tenants are missing from this trade area?
      </div>
    </div>
  );
}

function AnswerBubble({ show }) {
  return (
    <div style={{
      display:'flex', gap:10, alignItems:'flex-start',
      opacity: show ? 1 : 0, transform: show ? 'none' : 'translateY(6px)',
      transition:'opacity 0.35s, transform 0.35s',
      height: show ? 'auto' : 0, overflow:'hidden',
    }}>
      <div style={{width:28, height:28, borderRadius:'50%', flexShrink:0, overflow:'hidden'}}>
        <img src="assets/perigee-logo.png" alt="" style={{width:'100%', height:'100%', objectFit:'cover', display:'block'}}/>
      </div>
      <div style={{background:'#fff', border:'1px solid var(--line)', borderRadius:'14px 14px 14px 4px', padding:'12px 14px', fontSize:13, color:'var(--navy)', lineHeight:1.55}}>
        The trade area around 29 Lovell Ave shows three clear gaps: no specialty coffee within a 10-minute walk, no fast-casual lunch option, and an underserved fitness segment given the daytime population…
      </div>
    </div>
  );
}

function Composer({ working }) {
  return (
    <div style={{marginTop:'auto', paddingTop:14}}>
      {working && (
        <div style={{display:'flex', justifyContent:'center', marginBottom:10}}>
          <button className="btn btn-ghost btn-sm" style={{fontSize:12, color:'var(--slate)', gap:7}}>
            <span style={{width:9, height:9, background:'var(--deep)', borderRadius:2, display:'inline-block'}}></span>
            Stop generating
          </button>
        </div>
      )}
      <div style={{display:'flex', gap:10, alignItems:'center', background:'var(--cream)', borderRadius:12, padding:'10px 14px', border:'1px solid var(--line)'}}>
        <span style={{flex:1, fontSize:13, color:'var(--gray)'}}>{working ? 'Perigee is working…' : 'Ask a follow-up'}</span>
        <span style={{width:26, height:26, borderRadius:8, background: working ? 'var(--moonlight)' : 'var(--orange)', display:'flex', alignItems:'center', justifyContent:'center', color: working ? 'var(--gray)' : '#fff'}}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 19V5M5 12l7-7 7 7"/></svg>
        </span>
      </div>
    </div>
  );
}

function Frame({ children }) {
  return (
    <div style={{
      width:'100%', height:'100%', background:'#FDFCF9', borderRadius:16,
      border:'1px solid var(--line)', padding:'22px 24px 18px',
      display:'flex', flexDirection:'column', gap:16, overflow:'hidden',
      fontFamily:'var(--inter)',
    }}>
      {children}
    </div>
  );
}

/* =====================================================================
   OPTION A — Whisper line
   One quiet shimmering status line. Subagents are tiny dots that join
   the line while active, then tick off. Collapses to a receipt caption.
   ===================================================================== */
function ThinkingA() {
  const { phase } = usePhase();
  const done = isDone(phase);

  return (
    <Frame>
      <UserBubble/>

      {!done ? (
        <div style={{display:'flex', gap:10, alignItems:'center'}}>
          <div style={{width:28, height:28, borderRadius:'50%', flexShrink:0, overflow:'hidden', position:'relative'}}>
            <img src="assets/perigee-logo.png" alt="" style={{width:'100%', height:'100%', objectFit:'cover', display:'block'}}/>
            <div className="ti-breathe" style={{position:'absolute', inset:-3, borderRadius:'50%', border:'1.5px solid var(--orange)'}}/>
          </div>
          <div style={{display:'flex', flexDirection:'column', gap:5, minWidth:0}}>
            <div className="ti-shimmer" style={{fontSize:13.5, fontWeight:500}} key={PHASES[phase].label}>
              {PHASES[phase].label}…
            </div>
            {/* subagent dots join the line */}
            <div style={{display:'flex', gap:6, alignItems:'center', height:18}}>
              {AGENTS.map((a,i) => {
                const st = agentStatus(i, phase);
                if (st === 'idle') return null;
                return (
                  <span key={a.id} style={{
                    display:'inline-flex', alignItems:'center', gap:5,
                    fontSize:11, color: st==='active' ? 'var(--navy)' : 'var(--gray)',
                    transition:'color 0.3s',
                  }}>
                    <span className={st==='active' ? 'ti-pulse' : ''} style={{
                      width:7, height:7, borderRadius:'50%',
                      background: st==='done' ? 'var(--line-strong)' : a.color,
                      transition:'background 0.3s',
                    }}/>
                    {a.name}
                    {st==='done' && (
                      <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="var(--gray)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6L9 17l-5-5"/></svg>
                    )}
                  </span>
                );
              })}
            </div>
          </div>
        </div>
      ) : (
        <div style={{display:'grid', gap:8}}>
          <div style={{fontSize:11, color:'var(--gray)', display:'flex', alignItems:'center', gap:6, paddingLeft:38}}>
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6L9 17l-5-5"/></svg>
            Worked with Scout, Analyst & Matchmaker · 11s
          </div>
          <AnswerBubble show/>
        </div>
      )}

      <Composer working={!done}/>
    </Frame>
  );
}

/* =====================================================================
   OPTION B — Work log card
   A compact card that appends one row per step. Live row has a spinner,
   finished rows tick off. Collapses to a one-line summary when done.
   ===================================================================== */
function Spinner({ size=13, color='var(--orange)' }) {
  return (
    <svg className="ti-spin" width={size} height={size} viewBox="0 0 24 24" fill="none" style={{flexShrink:0}}>
      <circle cx="12" cy="12" r="9" stroke="var(--line)" strokeWidth="3"/>
      <path d="M21 12a9 9 0 00-9-9" stroke={color} strokeWidth="3" strokeLinecap="round"/>
    </svg>
  );
}

function LogRow({ live, done, label, sub, color }) {
  return (
    <div className="ti-rise" style={{display:'flex', gap:9, alignItems:'flex-start', padding:'7px 0'}}>
      <div style={{width:16, display:'flex', justifyContent:'center', paddingTop:1}}>
        {live ? <Spinner color={color || 'var(--orange)'}/> : done ? (
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#2F7A3B" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6L9 17l-5-5"/></svg>
        ) : (
          <span style={{width:7, height:7, borderRadius:'50%', background:'var(--line-strong)', marginTop:4}}/>
        )}
      </div>
      <div style={{minWidth:0}}>
        <div style={{fontSize:12.5, fontWeight: live ? 600 : 500, color: live ? 'var(--navy)' : done ? 'var(--slate)' : 'var(--gray)'}}>{label}</div>
        {sub && live && <div style={{fontSize:11, color:'var(--slate)', marginTop:2}}>{sub}</div>}
      </div>
    </div>
  );
}

function ThinkingB() {
  const { phase, tick } = usePhase();
  const done = isDone(phase);
  const [open, setOpen] = useState(true);

  const rows = [];
  rows.push({ key:'plan', label:'Understanding the request', live: phase <= 1, done: phase > 1 });
  AGENTS.forEach((a, i) => {
    const st = agentStatus(i, phase);
    if (st !== 'idle') rows.push({ key:a.id, label:`${a.name} · ${a.task.toLowerCase()}`, live: st==='active', done: st==='done', color:a.color });
  });
  if (phase >= 5) rows.push({ key:'draft', label:'Drafting your answer', live: phase===5, done: phase>5 });

  return (
    <Frame>
      <UserBubble/>

      <div style={{display:'flex', gap:10, alignItems:'flex-start'}}>
        <div style={{width:28, height:28, borderRadius:'50%', flexShrink:0, overflow:'hidden'}}>
          <img src="assets/perigee-logo.png" alt="" style={{width:'100%', height:'100%', objectFit:'cover', display:'block'}}/>
        </div>
        <div style={{flex:1, minWidth:0}}>
          <div style={{
            background:'#fff', border:'1px solid var(--line)', borderRadius:12,
            padding: done ? '9px 14px' : '11px 14px 8px',
            transition:'padding 0.25s',
          }}>
            {/* header */}
            <button onClick={()=>setOpen(o=>!o)} style={{
              display:'flex', alignItems:'center', gap:8, width:'100%', background:'none', border:'none',
              padding:0, cursor:'pointer', fontFamily:'var(--inter)', textAlign:'left',
            }}>
              {!done ? <Spinner/> : (
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#2F7A3B" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6L9 17l-5-5"/></svg>
              )}
              <span style={{fontSize:12.5, fontWeight:600, color:'var(--navy)'}}>
                {done ? 'Analyzed with 3 agents' : PHASES[phase].label + '…'}
              </span>
              <span style={{marginLeft:'auto', fontSize:11, color:'var(--gray)', fontVariantNumeric:'tabular-nums'}}>{done ? '11s' : `${tick}s`}</span>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--gray)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{transform: open?'rotate(180deg)':'none', transition:'transform 0.2s'}}><path d="M6 9l6 6 6-6"/></svg>
            </button>
            {/* rows */}
            {open && !done && (
              <div style={{marginTop:6, borderTop:'1px solid var(--line)', paddingTop:4}}>
                {rows.map(r => <LogRow key={r.key} {...r}/>)}
              </div>
            )}
          </div>
          <div style={{marginTop:10}}>
            <AnswerBubble show={done}/>
          </div>
        </div>
      </div>

      <Composer working={!done}/>
    </Frame>
  );
}

/* =====================================================================
   OPTION C — Orbit badge
   On-brand: the Perigee mark with an orbit ring; subagents are moons
   that dock onto the ring while active. Status text sits beside it,
   agent chips only when >0 active. Collapses into the answer.
   ===================================================================== */
function ThinkingC() {
  const { phase } = usePhase();
  const done = isDone(phase);
  const activeAgents = AGENTS.map((a,i)=>({ ...a, st: agentStatus(i, phase) })).filter(a=>a.st!=='idle');

  return (
    <Frame>
      <UserBubble/>

      {!done ? (
        <div style={{display:'flex', gap:16, alignItems:'center'}}>
          {/* orbit badge */}
          <div style={{position:'relative', width:64, height:64, flexShrink:0}}>
            <div className="ti-orbit" style={{position:'absolute', inset:0, borderRadius:'50%', border:'1px solid var(--mist)'}}>
              {AGENTS.map((a,i) => {
                const st = agentStatus(i, phase);
                return (
                  <span key={a.id} style={{
                    position:'absolute', top:-4, left:'50%', marginLeft:-4,
                    width:8, height:8, borderRadius:'50%',
                    background: st==='idle' ? 'transparent' : st==='done' ? 'var(--line-strong)' : a.color,
                    transform:`rotate(${i*120}deg)`, transformOrigin:'4px 36px',
                    transition:'background 0.3s',
                    boxShadow: st==='active' ? '0 0 0 3px rgba(255,138,61,0.15)' : 'none',
                  }}/>
                );
              })}
            </div>
            <div style={{position:'absolute', inset:14, borderRadius:'50%', overflow:'hidden'}}>
              <img src="assets/perigee-logo.png" alt="" style={{width:'100%', height:'100%', objectFit:'cover', display:'block'}}/>
            </div>
          </div>

          <div style={{minWidth:0}}>
            <div className="ti-shimmer" style={{fontSize:14, fontWeight:600}} key={PHASES[phase].label}>{PHASES[phase].label}…</div>
            <div style={{display:'flex', gap:6, marginTop:8, flexWrap:'wrap', minHeight:24}}>
              {activeAgents.map(a => (
                <span key={a.id} className="ti-rise" style={{
                  display:'inline-flex', alignItems:'center', gap:6,
                  padding:'4px 10px', borderRadius:999, fontSize:11, fontWeight:500,
                  background: a.st==='active' ? '#fff' : 'transparent',
                  border: `1px solid ${a.st==='active' ? 'var(--line-strong)' : 'var(--line)'}`,
                  color: a.st==='active' ? 'var(--navy)' : 'var(--gray)',
                  transition:'all 0.3s',
                }}>
                  <span className={a.st==='active' ? 'ti-pulse' : ''} style={{width:6, height:6, borderRadius:'50%', background: a.st==='done' ? 'var(--line-strong)' : a.color}}/>
                  {a.st==='active' ? `${a.name} — ${a.task.toLowerCase()}` : a.name}
                  {a.st==='done' && <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="var(--gray)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6L9 17l-5-5"/></svg>}
                </span>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div style={{display:'grid', gap:8}}>
          <div style={{fontSize:11, color:'var(--gray)', display:'flex', alignItems:'center', gap:6, paddingLeft:38}}>
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6L9 17l-5-5"/></svg>
            Scout, Analyst & Matchmaker · 11s
          </div>
          <AnswerBubble show/>
        </div>
      )}

      <Composer working={!done}/>
    </Frame>
  );
}

Object.assign(window, { ThinkingA, ThinkingB, ThinkingC });
