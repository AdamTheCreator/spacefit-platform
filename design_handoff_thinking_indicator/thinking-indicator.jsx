/* Perigee — live thinking indicator (chat)
 * One-shot simulated run. variant: 'whisper' | 'log' | 'orbit'
 * Calls onDone() when the run completes.
 */
const TIuseState = React.useState;
const TIuseEffect = React.useEffect;

const TI_AGENTS = [
  { id:'scout',      name:'Scout',      color:'#3A5BA0', task:'Pulling nearby businesses & demographics' },
  { id:'analyst',    name:'Analyst',    color:'#C25E1F', task:'Reviewing the trade area for gaps' },
  { id:'matchmaker', name:'Matchmaker', color:'#2F7A3B', task:'Scoring tenant fits against the roster' },
];

/* phase: 0 read, 1 plan, 2 scout, 3 analyst, 4 matchmaker, 5 draft → onDone */
const TI_PHASES = [
  { dur: 1500, label: 'Reading your question' },
  { dur: 1500, label: 'Planning the approach' },
  { dur: 2200, label: 'Researching the trade area' },
  { dur: 2200, label: 'Analyzing tenant gaps' },
  { dur: 2200, label: 'Matching tenants' },
  { dur: 1800, label: 'Drafting your answer' },
];

function tiAgentStatus(i, phase) {
  const activeAt = i + 2;
  if (phase < activeAt) return 'idle';
  if (phase === activeAt) return 'active';
  return 'done';
}

function TISpinner({ size=13, color='var(--orange)' }) {
  return (
    <svg className="ti-spin" width={size} height={size} viewBox="0 0 24 24" fill="none" style={{flexShrink:0}}>
      <circle cx="12" cy="12" r="9" stroke="var(--line)" strokeWidth="3"/>
      <path d="M21 12a9 9 0 00-9-9" stroke={color} strokeWidth="3" strokeLinecap="round"/>
    </svg>
  );
}

const TICheck = ({ size=13, color='#2F7A3B' }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6L9 17l-5-5"/></svg>
);

/* ---------- Variant: whisper ---------- */
function TIWhisper({ phase }) {
  return (
    <div style={{display:'flex', gap:10, alignItems:'center'}}>
      <div style={{width:28, height:28, borderRadius:'50%', flexShrink:0, overflow:'hidden', position:'relative'}}>
        <img src="assets/perigee-logo.png" alt="" style={{width:'100%', height:'100%', objectFit:'cover', display:'block'}}/>
        <div className="ti-breathe" style={{position:'absolute', inset:-3, borderRadius:'50%', border:'1.5px solid var(--orange)'}}></div>
      </div>
      <div style={{display:'flex', flexDirection:'column', gap:5, minWidth:0}}>
        <div className="ti-shimmer" style={{fontSize:13.5, fontWeight:500}} key={TI_PHASES[phase].label}>
          {TI_PHASES[phase].label}…
        </div>
        <div style={{display:'flex', gap:10, alignItems:'center', height:16}}>
          {TI_AGENTS.map((a,i) => {
            const st = tiAgentStatus(i, phase);
            if (st === 'idle') return null;
            return (
              <span key={a.id} className="ti-rise" style={{display:'inline-flex', alignItems:'center', gap:5, fontSize:11, color: st==='active' ? 'var(--navy)' : 'var(--gray)', transition:'color 0.3s'}}>
                <span className={st==='active' ? 'ti-pulse' : ''} style={{width:7, height:7, borderRadius:'50%', background: st==='done' ? 'var(--line-strong)' : a.color, transition:'background 0.3s'}}></span>
                {a.name}
                {st==='done' && <TICheck size={9} color="var(--gray)"/>}
              </span>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/* ---------- Variant: log ---------- */
function TILogRow({ live, done, label, color }) {
  return (
    <div className="ti-rise" style={{display:'flex', gap:9, alignItems:'flex-start', padding:'7px 0'}}>
      <div style={{width:16, display:'flex', justifyContent:'center', paddingTop:1}}>
        {live ? <TISpinner color={color || 'var(--orange)'}/> : done ? <TICheck/> : (
          <span style={{width:7, height:7, borderRadius:'50%', background:'var(--line-strong)', marginTop:4}}></span>
        )}
      </div>
      <div style={{fontSize:12.5, fontWeight: live ? 600 : 500, color: live ? 'var(--navy)' : done ? 'var(--slate)' : 'var(--gray)', minWidth:0}}>{label}</div>
    </div>
  );
}

function TILog({ phase, tick }) {
  const [open, setOpen] = TIuseState(true);
  const rows = [{ key:'plan', label:'Understanding the request', live: phase <= 1, done: phase > 1 }];
  TI_AGENTS.forEach((a, i) => {
    const st = tiAgentStatus(i, phase);
    if (st !== 'idle') rows.push({ key:a.id, label:`${a.name} · ${a.task.toLowerCase()}`, live: st==='active', done: st==='done', color:a.color });
  });
  if (phase >= 5) rows.push({ key:'draft', label:'Drafting your answer', live:true, done:false });

  return (
    <div style={{display:'flex', gap:10, alignItems:'flex-start'}}>
      <div style={{width:28, height:28, borderRadius:'50%', flexShrink:0, overflow:'hidden'}}>
        <img src="assets/perigee-logo.png" alt="" style={{width:'100%', height:'100%', objectFit:'cover', display:'block'}}/>
      </div>
      <div style={{flex:1, minWidth:0, maxWidth:460}}>
        <div style={{background:'#fff', border:'1px solid var(--line)', borderRadius:12, padding:'11px 14px 8px'}}>
          <button onClick={()=>setOpen(o=>!o)} style={{display:'flex', alignItems:'center', gap:8, width:'100%', background:'none', border:'none', padding:0, cursor:'pointer', fontFamily:'var(--inter)', textAlign:'left'}}>
            <TISpinner/>
            <span style={{fontSize:12.5, fontWeight:600, color:'var(--navy)'}}>{TI_PHASES[phase].label}…</span>
            <span style={{marginLeft:'auto', fontSize:11, color:'var(--gray)', fontVariantNumeric:'tabular-nums'}}>{tick}s</span>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--gray)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{transform: open?'rotate(180deg)':'none', transition:'transform 0.2s'}}><path d="M6 9l6 6 6-6"/></svg>
          </button>
          {open && (
            <div style={{marginTop:6, borderTop:'1px solid var(--line)', paddingTop:4}}>
              {rows.map(r => <TILogRow key={r.key} live={r.live} done={r.done} label={r.label} color={r.color}/>)}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ---------- Variant: orbit ---------- */
function TIOrbit({ phase }) {
  const active = TI_AGENTS.map((a,i)=>({ ...a, st: tiAgentStatus(i, phase) })).filter(a=>a.st!=='idle');
  return (
    <div style={{display:'flex', gap:16, alignItems:'center'}}>
      <div style={{position:'relative', width:60, height:60, flexShrink:0}}>
        <div className="ti-orbit" style={{position:'absolute', inset:0, borderRadius:'50%', border:'1px solid var(--mist)'}}>
          {TI_AGENTS.map((a,i) => {
            const st = tiAgentStatus(i, phase);
            return (
              <span key={a.id} style={{
                position:'absolute', top:-4, left:'50%', marginLeft:-4,
                width:8, height:8, borderRadius:'50%',
                background: st==='idle' ? 'transparent' : st==='done' ? 'var(--line-strong)' : a.color,
                transform:`rotate(${i*120}deg)`, transformOrigin:'4px 34px',
                transition:'background 0.3s',
                boxShadow: st==='active' ? '0 0 0 3px rgba(255,138,61,0.15)' : 'none',
              }}></span>
            );
          })}
        </div>
        <div style={{position:'absolute', inset:13, borderRadius:'50%', overflow:'hidden'}}>
          <img src="assets/perigee-logo.png" alt="" style={{width:'100%', height:'100%', objectFit:'cover', display:'block'}}/>
        </div>
      </div>
      <div style={{minWidth:0}}>
        <div className="ti-shimmer" style={{fontSize:13.5, fontWeight:600}} key={TI_PHASES[phase].label}>{TI_PHASES[phase].label}…</div>
        <div style={{display:'flex', gap:6, marginTop:7, flexWrap:'wrap', minHeight:22}}>
          {active.map(a => (
            <span key={a.id} className="ti-rise" style={{
              display:'inline-flex', alignItems:'center', gap:6,
              padding:'3px 9px', borderRadius:999, fontSize:11, fontWeight:500,
              background: a.st==='active' ? '#fff' : 'transparent',
              border: `1px solid ${a.st==='active' ? 'var(--line-strong)' : 'var(--line)'}`,
              color: a.st==='active' ? 'var(--navy)' : 'var(--gray)',
              transition:'all 0.3s',
            }}>
              <span className={a.st==='active' ? 'ti-pulse' : ''} style={{width:6, height:6, borderRadius:'50%', background: a.st==='done' ? 'var(--line-strong)' : a.color}}></span>
              {a.st==='active' ? `${a.name} — ${a.task.toLowerCase()}` : a.name}
              {a.st==='done' && <TICheck size={9} color="var(--gray)"/>}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ---------- One-shot runner ---------- */
function ThinkingIndicator({ variant='whisper', onDone }) {
  const [phase, setPhase] = TIuseState(0);
  const [tick, setTick] = TIuseState(0);

  TIuseEffect(() => {
    let alive = true;
    const t = setTimeout(() => {
      if (!alive) return;
      if (phase + 1 >= TI_PHASES.length) { onDone && onDone(); }
      else setPhase(phase + 1);
    }, TI_PHASES[phase].dur);
    return () => { alive = false; clearTimeout(t); };
  }, [phase]);

  TIuseEffect(() => {
    const iv = setInterval(() => setTick(t => t + 1), 1000);
    return () => clearInterval(iv);
  }, []);

  if (variant === 'log') return <TILog phase={phase} tick={tick}/>;
  if (variant === 'orbit') return <TIOrbit phase={phase}/>;
  return <TIWhisper phase={phase}/>;
}

/* Receipt line shown above the answer once the run completes */
function ThinkingReceipt({ seconds=11 }) {
  return (
    <div style={{fontSize:11, color:'var(--gray)', display:'flex', alignItems:'center', gap:6, paddingLeft:40, marginBottom:6}}>
      <TICheck size={10} color="var(--gray)"/>
      Worked with Scout, Analyst &amp; Matchmaker · {seconds}s
    </div>
  );
}

window.PerigeeThinking = { ThinkingIndicator, ThinkingReceipt };
