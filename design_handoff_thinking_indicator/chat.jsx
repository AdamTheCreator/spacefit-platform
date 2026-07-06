/* Perigee — Free-form chat
 * Zero-friction chat surface. Not project-scoped until promoted.
 */
const FUseState = React.useState;
const FIc = window.PerigeeShell.Icon;

/* ---------- Seed data ---------- */
const RECENT_CHATS = [
  { id:'c1', title:'Average rent PSF for Scottsdale strip retail', when:'14m ago', msgs:8, scope:'free' },
  { id:'c2', title:'Cold outreach template — tenant rep intro', when:'1h ago', msgs:12, scope:'free' },
  { id:'c3', title:'Tenant roster refresh', when:'2h ago', msgs:14, scope:'project', projectName:'Camelback Retail Center' },
  { id:'c4', title:'Phoenix-metro daytime pop benchmarks', when:'Yesterday', msgs:6, scope:'free' },
  { id:'c5', title:'Comp analysis for shortlist', when:'Yesterday', msgs:28, scope:'project', projectName:'Gilbert Crossing' },
  { id:'c6', title:'Google Places reliability vs. CoStar', when:'2d ago', msgs:5, scope:'free' },
  { id:'c7', title:'Underwriting assumptions review', when:'3d ago', msgs:22, scope:'project', projectName:'Tempe Town Square' },
  { id:'c8', title:'Anchor grocer market share Phoenix', when:'4d ago', msgs:9, scope:'free' },
];

const ARCHIVED_CHATS = [
  { id:'a1', title:'How to read a Placer trade area PDF', when:'42d ago', msgs:11 },
  { id:'a2', title:'Cap rate trends Q3 2025', when:'51d ago', msgs:7 },
  { id:'a3', title:'Draft for Linkedin InMail', when:'60d ago', msgs:4 },
];

/* ---------- Screen root ---------- */
function ChatScreen() {
  const [active, setActive] = FUseState(() => localStorage.getItem('perigee-chat-active') || 'empty');
  const [filter, setFilter] = FUseState('all'); // all | free | project
  const [showArchived, setShowArchived] = FUseState(false);
  const [promoting, setPromoting] = FUseState(false);

  function pick(id) { setActive(id); localStorage.setItem('perigee-chat-active', id); }
  function newChat() { pick('new'); }

  const rows = RECENT_CHATS.filter(c =>
    filter === 'all' ? true :
    filter === 'free' ? c.scope === 'free' :
    c.scope === 'project'
  );

  return (
    <div style={{display:'grid', gridTemplateColumns:'280px 1fr', minHeight:'calc(100vh - 74px)'}}>
      {/* Left rail */}
      <aside style={{borderRight:'1px solid var(--line)', background:'#fff', display:'flex', flexDirection:'column'}}>
        <div style={{padding:'16px 14px', borderBottom:'1px solid var(--line)'}}>
          <button onClick={newChat} className="btn btn-accent" style={{width:'100%', justifyContent:'center'}}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 3a2.83 2.83 0 114 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>
            New chat
          </button>
          <div className="mono" style={{fontSize:10, color:'var(--slate)', textAlign:'center', marginTop:8}}>⌘ ⇧ N</div>
        </div>

        <div style={{padding:'14px 14px 6px'}}>
          <div style={{fontSize:11, fontWeight:600, color:'var(--slate)', letterSpacing:'0.08em', textTransform:'uppercase', marginBottom:10}}>Recent chats</div>
          <div style={{display:'flex', gap:4, background:'var(--cream)', padding:3, borderRadius:8, marginBottom:8}}>
            {[['all','All'],['free','Free-form'],['project','In projects']].map(([id,label])=>(
              <button key={id} onClick={()=>setFilter(id)} style={{
                flex:1, padding:'6px 8px', borderRadius:5, border:'none',
                background: filter===id?'#fff':'transparent',
                boxShadow: filter===id?'var(--shadow-sm)':'none',
                color: filter===id?'var(--navy)':'var(--slate)',
                fontSize:11, fontWeight:500, cursor:'pointer', fontFamily:'var(--inter)',
              }}>{label}</button>
            ))}
          </div>
        </div>

        <div style={{flex:1, overflow:'auto', padding:'0 8px 8px'}}>
          {rows.map(c => (
            <button key={c.id} onClick={()=>pick(c.id)} style={{
              display:'block', width:'100%', textAlign:'left',
              padding:'10px 12px', borderRadius:8, border:'none',
              background: active===c.id ? 'var(--cream)' : 'transparent',
              cursor:'pointer', marginBottom:2, fontFamily:'var(--inter)',
            }}
              onMouseEnter={e=>{ if(active!==c.id) e.currentTarget.style.background='var(--moonlight)'; }}
              onMouseLeave={e=>{ if(active!==c.id) e.currentTarget.style.background='transparent'; }}>
              <div style={{fontSize:13, fontWeight: active===c.id?600:500, color:'var(--navy)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap'}}>{c.title}</div>
              <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginTop:4, gap:6}}>
                {c.scope==='project' ? (
                  <span style={{fontSize:10, padding:'2px 7px', background:'var(--moonlight)', color:'var(--orbit)', borderRadius:5, fontWeight:500, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', maxWidth:140}}>In: {c.projectName}</span>
                ) : (
                  <span style={{fontSize:10, color:'var(--slate)'}}>{c.msgs} messages</span>
                )}
                <span style={{fontSize:10, color:'var(--gray)', flexShrink:0}}>{c.when}</span>
              </div>
            </button>
          ))}

          {/* Archived section */}
          <div style={{marginTop:16, borderTop:'1px solid var(--line)', paddingTop:10}}>
            <button onClick={()=>setShowArchived(s=>!s)} style={{
              display:'flex', alignItems:'center', gap:6, width:'100%',
              padding:'6px 12px', background:'transparent', border:'none',
              color:'var(--slate)', fontSize:11, fontWeight:600, letterSpacing:'0.08em', textTransform:'uppercase',
              cursor:'pointer', fontFamily:'var(--inter)',
            }}>
              <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor" style={{transform: showArchived?'rotate(90deg)':'none', transition:'transform 0.15s'}}><path d="M8 5l8 7-8 7z"/></svg>
              Archived ({ARCHIVED_CHATS.length})
            </button>
            {showArchived && (
              <div style={{marginTop:4}}>
                {ARCHIVED_CHATS.map(c => (
                  <button key={c.id} onClick={()=>pick(c.id)} style={{
                    display:'block', width:'100%', textAlign:'left',
                    padding:'8px 12px', borderRadius:8, border:'none', background:'transparent',
                    cursor:'pointer', marginBottom:2, opacity:0.7,
                    fontFamily:'var(--inter)',
                  }}>
                    <div style={{fontSize:12, fontWeight:500, color:'var(--navy)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap'}}>{c.title}</div>
                    <div style={{fontSize:10, color:'var(--gray)', marginTop:3}}>{c.when} · auto-archived</div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div>
        {active==='empty' && <ChatEmptyState onStart={newChat}/>}
        {active==='new' && <ActiveChat isNew onPromote={()=>setPromoting(true)}/>}
        {active!=='empty' && active!=='new' && <ActiveChat chat={[...RECENT_CHATS, ...ARCHIVED_CHATS].find(c=>c.id===active)} onPromote={()=>setPromoting(true)}/>}
      </div>

      {promoting && <PromoteModal close={()=>setPromoting(false)}/>}
    </div>
  );
}

/* ---------- Empty state ---------- */
function ChatEmptyState({ onStart }) {
  return (
    <div style={{padding:'80px 48px', display:'flex', justifyContent:'center'}}>
      <div style={{maxWidth:560, textAlign:'center'}}>
        <img src="assets/goose-planet.png" alt="" style={{width:180, height:180, objectFit:'contain'}}/>
        <h1 style={{fontSize:32, fontFamily:'var(--sora)', fontWeight:700, color:'var(--navy)', letterSpacing:'-0.015em', marginTop:16}}>Start by asking a question.</h1>
        <p style={{fontSize:15, color:'var(--slate)', lineHeight:1.6, marginTop:14, maxWidth:480, marginLeft:'auto', marginRight:'auto'}}>
          Perigee's specialist agents can analyze trade areas, research tenants, and draft outreach. For ongoing deals, start a project instead.
        </p>
        <div style={{display:'flex', gap:10, justifyContent:'center', marginTop:26}}>
          <button className="btn btn-accent" onClick={onStart}>Start a new chat</button>
          <button className="btn btn-secondary">Create a project</button>
        </div>

        <div style={{marginTop:48, textAlign:'left'}}>
          <div style={{fontSize:11, fontWeight:600, color:'var(--slate)', letterSpacing:'0.08em', textTransform:'uppercase', marginBottom:12, textAlign:'center'}}>Try one of these</div>
          <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:10}}>
            {[
              ['What\'s the average rent PSF for strip retail in Scottsdale?','chart'],
              ['Draft a cold outreach email to a tenant rep broker','chat'],
              ['Pull Google Places for coffee shops within a mile of ZIP 85251','pin'],
              ['Summarize the latest cap rate trends for Phoenix retail','sparkles'],
            ].map(([text, icon]) => (
              <button key={text} className="card" style={{padding:'14px 16px', textAlign:'left', cursor:'pointer', border:'1px solid var(--line)', background:'#fff', fontFamily:'var(--inter)'}}
                onMouseEnter={e=>{e.currentTarget.style.borderColor='var(--navy)'; e.currentTarget.style.transform='translateY(-1px)';}}
                onMouseLeave={e=>{e.currentTarget.style.borderColor='var(--line)'; e.currentTarget.style.transform='none';}}>
                <div style={{display:'flex', gap:10, alignItems:'flex-start'}}>
                  <div style={{width:28, height:28, borderRadius:6, background:'var(--moonlight)', color:'var(--orbit)', display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0}}><FIc name={icon} size={14}/></div>
                  <span style={{fontSize:13, color:'var(--navy)', lineHeight:1.45}}>{text}</span>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ---------- Active chat view ---------- */
function ActiveChat({ chat, isNew, onPromote }) {
  const title = isNew ? 'New chat' : (chat?.title || 'Chat');
  const isProject = chat?.scope === 'project';
  const seedMsgs = isNew ? [] : [
    { role:'user', text:'What\'s the average rent PSF for strip retail in Scottsdale right now?' },
    { role:'ai', text:'Based on the latest Phoenix-metro retail benchmarks, Scottsdale strip retail is averaging $32–38/sf NNN for well-located inline space, with anchor-adjacent pricing pushing $42+/sf. A few caveats worth naming since this is a free-form chat — I don\'t have project data to ground this in, so numbers come from training data and external sources.',
      cites:[['Google Places & Census ACS','gray']] },
    { role:'user', text:'What about Old Town specifically?' },
    { role:'ai', text:'Old Town Scottsdale trades meaningfully higher — asking rents cluster around $45–58/sf NNN for quality ground-floor retail, driven by tourism-adjacent daytime traffic and limited new supply. The spread between Old Town and broader Scottsdale is ~35% on a blended basis.', cites:[['Census ACS','gray']] },
  ];

  const [extra, setExtra] = FUseState([]);          // messages added this session
  const [running, setRunning] = FUseState(false);   // agents working
  const [draft, setDraft] = FUseState('');
  const startedAt = React.useRef(0);
  const msgs = [...seedMsgs, ...extra];

  function send() {
    const text = draft.trim();
    if (!text || running) return;
    setExtra(x => [...x, { role:'user', text }]);
    setDraft('');
    startedAt.current = Date.now();
    setRunning(true);
  }

  function finishRun() {
    const secs = Math.max(1, Math.round((Date.now() - startedAt.current) / 1000));
    setRunning(false);
    setExtra(x => [...x, {
      role:'ai', receipt: secs,
      text: 'Based on what Scout pulled and Analyst\u2019s trade-area review, three gaps stand out: no specialty coffee within a 10-minute walk, no fast-casual lunch option, and an underserved fitness segment given the daytime population. Matchmaker scored 12 tenants against the roster \u2014 the top three fits are ready for outreach.',
      cites:[['Google Places & Census ACS','gray']],
    }]);
  }

  return (
    <div style={{display:'flex', flexDirection:'column', height:'calc(100vh - 74px)'}}>
      {/* Header */}
      <div style={{padding:'16px 24px', borderBottom:'1px solid var(--line)', background:'#fff', display:'flex', alignItems:'center', gap:14}}>
        <div style={{flex:1, minWidth:0}}>
          <div style={{display:'flex', alignItems:'center', gap:10}}>
            <h1 style={{fontSize:17, fontFamily:'var(--sora)', fontWeight:600, color:'var(--navy)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap'}}>{title}</h1>
            {isProject ? (
              <span className="pill pill-mist" style={{fontSize:10}}>In: {chat.projectName}</span>
            ) : (
              <span className="pill" style={{fontSize:10}}>Free-form</span>
            )}
          </div>
          {!isNew && chat?.when && <div style={{fontSize:11, color:'var(--slate)', marginTop:3}}>Started {chat.when} · {chat.msgs || msgs.length} messages</div>}
        </div>
        {!isProject && !isNew && (
          <button className="btn btn-secondary btn-sm" onClick={onPromote}>
            <FIc name="layers" size={13}/> Save to project
          </button>
        )}
        <button className="btn btn-ghost btn-sm" style={{padding:8}} aria-label="Menu">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="19" cy="12" r="2"/></svg>
        </button>
      </div>

      {/* Messages */}
      <div style={{flex:1, overflow:'auto', padding:'24px 32px'}}>
        <div style={{maxWidth:780, margin:'0 auto', display:'grid', gap:18}}>
          {isNew && msgs.length === 0 ? <NewChatIntro/> : msgs.map((m,i)=><FFMessage key={i} m={m}/>)}
          {running && <window.PerigeeThinking.ThinkingIndicator variant="log" onDone={finishRun}/>}
          {!isNew && !running && msgs.length >= 4 && extra.length === 0 && <PromoteNudge onPromote={onPromote}/>}
        </div>
      </div>

      {/* Composer */}
      <div style={{padding:'16px 24px', borderTop:'1px solid var(--line)', background:'#fff'}}>
        <div style={{maxWidth:780, margin:'0 auto'}}>
          {running && (
            <div style={{display:'flex', justifyContent:'center', marginBottom:10}}>
              <button className="btn btn-ghost btn-sm" onClick={finishRun} style={{fontSize:12, color:'var(--slate)', gap:7}}>
                <span style={{width:9, height:9, background:'var(--deep)', borderRadius:2, display:'inline-block'}}></span>
                Stop generating
              </button>
            </div>
          )}
          <div style={{display:'flex', gap:10, alignItems:'flex-end', background:'var(--cream)', borderRadius:14, padding:'10px 12px', border:'1px solid var(--line)'}}>
            <button className="btn btn-ghost btn-sm" style={{padding:8}} title="Attach document">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M21.4 11.1L12.5 20a5 5 0 01-7-7l8.9-8.9a3.3 3.3 0 014.7 4.7l-8.9 8.9a1.7 1.7 0 01-2.4-2.4l8.3-8.3"/></svg>
            </button>
            <textarea rows={1}
              value={draft}
              onChange={e=>setDraft(e.target.value)}
              onKeyDown={e=>{ if (e.key==='Enter' && !e.shiftKey) { e.preventDefault(); send(); } }}
              placeholder={running ? 'Perigee is working\u2026' : 'Ask anything — no project context applied'}
              style={{flex:1, border:'none', background:'transparent', outline:'none', fontSize:14, fontFamily:'var(--inter)', color:'var(--navy)', resize:'none', padding:'8px 6px', maxHeight:120}}></textarea>
            <button className="btn btn-accent btn-sm" onClick={send} disabled={running || !draft.trim()} style={{padding:'8px 14px', opacity: (running || !draft.trim()) ? 0.5 : 1}}>Send</button>
          </div>
          <div style={{fontSize:11, color:'var(--slate)', textAlign:'center', marginTop:8}}>
            No project context. {isNew ? 'Your BYOK config and specialist models still apply.' : <>Citations will pull from external sources only · <a href="#" onClick={(e)=>{e.preventDefault(); onPromote();}} style={{color:'var(--orbit)'}}>Save to project</a> to ground in your uploaded data.</>}
          </div>
        </div>
      </div>
    </div>
  );
}

function NewChatIntro() {
  return (
    <div style={{padding:'40px 20px', textAlign:'center'}}>
      <div style={{width:56, height:56, margin:'0 auto', background:'var(--navy)', borderRadius:'50%', position:'relative', overflow:'hidden'}}>
        <div style={{position:'absolute', inset:0, background:'radial-gradient(circle at 30% 35%, #F5F1E8 0 10px, transparent 11px), radial-gradient(circle at 75% 28%, #FF8A3D 0 5px, transparent 6px)'}}/>
        <div style={{position:'absolute', left:-10, right:-10, top:'42%', height:'60%', borderTop:'2px solid #A7C7F7', borderRadius:'50%', transform:'rotate(-16deg)'}}/>
      </div>
      <h2 style={{fontSize:22, fontFamily:'var(--sora)', fontWeight:600, color:'var(--navy)', marginTop:16, letterSpacing:'-0.01em'}}>What can I help you work on?</h2>
      <p style={{fontSize:13, color:'var(--slate)', marginTop:8, lineHeight:1.55, maxWidth:440, marginLeft:'auto', marginRight:'auto'}}>Free-form mode. No project context applied. If this turns into a real deal, save it to a project anytime.</p>
    </div>
  );
}

function FFMessage({ m }) {
  if (m.role === 'user') {
    return (
      <div style={{display:'flex', justifyContent:'flex-end'}}>
        <div style={{maxWidth:'78%', background:'var(--navy)', color:'#fff', padding:'12px 16px', borderRadius:'16px 16px 4px 16px', fontSize:14, lineHeight:1.5}}>{m.text}</div>
      </div>
    );
  }
  return (
    <div>
    {m.receipt && <window.PerigeeThinking.ThinkingReceipt seconds={m.receipt}/>}
    <div style={{display:'flex', gap:12, alignItems:'flex-start'}}>
      <div style={{width:32, height:32, borderRadius:'50%', flexShrink:0, overflow:'hidden'}}>
        <img src="assets/perigee-logo.png" alt="Perigee" style={{width:'100%', height:'100%', objectFit:'cover', display:'block'}}/>
      </div>
      <div style={{flex:1, maxWidth:'82%'}}>
        <div style={{background:'#fff', border:'1px solid var(--line)', borderRadius:'16px 16px 16px 4px', padding:'14px 16px'}}>
          <div style={{fontSize:14, color:'var(--navy)', lineHeight:1.6}}>{m.text}</div>
          {m.cites && (
            <div style={{display:'flex', gap:6, marginTop:12, flexWrap:'wrap'}}>
              {m.cites.map((c,i)=> <span key={i} className="pill" style={{fontSize:10}}>Per {c[0]}</span>)}
            </div>
          )}
        </div>
      </div>
    </div>
    </div>
  );
}

function PromoteNudge({ onPromote }) {
  const [dismissed, setDismissed] = FUseState(false);
  if (dismissed) return null;
  return (
    <div style={{background:'var(--cream)', border:'1px solid #E5D9B6', borderRadius:12, padding:'14px 16px', display:'flex', gap:12, alignItems:'center'}}>
      <span style={{fontSize:18}}>💡</span>
      <div style={{flex:1, fontSize:13, color:'var(--navy)'}}>
        <b>This is getting interesting.</b> <span style={{color:'var(--slate)'}}>Save this chat to a project to ground future answers in your uploaded data.</span>
      </div>
      <button className="btn btn-primary btn-sm" onClick={onPromote}>Save to project</button>
      <button className="btn btn-ghost btn-sm" onClick={()=>setDismissed(true)} style={{padding:'6px 8px', color:'var(--slate)'}} aria-label="Dismiss">✕</button>
    </div>
  );
}

/* ---------- Promote modal ---------- */
function PromoteModal({ close }) {
  const [mode, setMode] = FUseState('existing'); // existing | new
  const [q, setQ] = FUseState('');
  const [picked, setPicked] = FUseState(null);
  const [newName, setNewName] = FUseState('');
  const [newAddr, setNewAddr] = FUseState('');
  const projects = [
    {id:'p1', name:'1842 Boston Post Rd', city:'Scottsdale', status:'Underwriting'},
    {id:'p2', name:'Camelback Retail Center', city:'Phoenix', status:'LOI'},
    {id:'p3', name:'Ahwatukee Plaza', city:'Phoenix', status:'Sourced'},
    {id:'p4', name:'Gilbert Crossing', city:'Gilbert', status:'Screening'},
    {id:'p5', name:'Tempe Town Square', city:'Tempe', status:'Closing'},
  ].filter(p => !q || p.name.toLowerCase().includes(q.toLowerCase()));

  return (
    <div onClick={close} style={{position:'fixed', inset:0, zIndex:100, background:'rgba(15,27,45,0.55)', backdropFilter:'blur(4px)', display:'flex', alignItems:'center', justifyContent:'center', padding:20}}>
      <div onClick={e=>e.stopPropagation()} style={{background:'#fff', borderRadius:20, width:'100%', maxWidth:560, boxShadow:'0 24px 80px rgba(15,27,45,0.3)', overflow:'hidden'}}>
        <div style={{padding:'24px 28px 8px', display:'flex', alignItems:'center', gap:14, borderBottom:'1px solid var(--line)'}}>
          <img src="assets/goose-carriers.png" alt="" style={{width:56, height:56, objectFit:'contain', flexShrink:0}}/>
          <div>
            <h3 style={{fontSize:18, fontWeight:600}}>Save chat to a project</h3>
            <p style={{fontSize:13, color:'var(--slate)', marginTop:2}}>Future messages will ground in your project's uploaded data.</p>
          </div>
        </div>

        <div style={{display:'flex', borderBottom:'1px solid var(--line)'}}>
          {[['existing','Pick existing'],['new','Create new']].map(([id,label])=>(
            <button key={id} onClick={()=>setMode(id)} style={{
              flex:1, padding:'14px 16px', background: mode===id?'#fff':'var(--cream)',
              border:'none', borderBottom: mode===id?'2px solid var(--orange)':'2px solid transparent',
              color: mode===id?'var(--navy)':'var(--slate)',
              fontWeight: mode===id?600:500, fontSize:13, cursor:'pointer', fontFamily:'var(--inter)',
            }}>{label}</button>
          ))}
        </div>

        {mode==='existing' && (
          <div style={{padding:'18px 24px'}}>
            <div style={{display:'flex', gap:8, alignItems:'center', background:'#fff', border:'1px solid var(--line)', borderRadius:10, padding:'10px 12px', marginBottom:12}}>
              <FIc name="search" size={14}/>
              <input autoFocus value={q} onChange={e=>setQ(e.target.value)} placeholder="Search your projects" style={{flex:1, border:'none', outline:'none', fontSize:13, fontFamily:'var(--inter)', color:'var(--navy)'}}/>
            </div>
            <div style={{maxHeight:260, overflow:'auto', display:'grid', gap:4}}>
              {projects.map(p=>(
                <button key={p.id} onClick={()=>setPicked(p.id)} style={{
                  display:'flex', alignItems:'center', justifyContent:'space-between', gap:10,
                  padding:'12px 14px', borderRadius:10,
                  border: picked===p.id?'1px solid var(--navy)':'1px solid var(--line)',
                  background: picked===p.id?'var(--moonlight)':'#fff',
                  cursor:'pointer', fontFamily:'var(--inter)', textAlign:'left',
                }}>
                  <div>
                    <div style={{fontSize:13, fontWeight:600, color:'var(--navy)'}}>{p.name}</div>
                    <div style={{fontSize:11, color:'var(--slate)', marginTop:2}}>{p.city} · {p.status}</div>
                  </div>
                  {picked===p.id && <div style={{width:22, height:22, borderRadius:'50%', background:'var(--navy)', color:'#fff', display:'flex', alignItems:'center', justifyContent:'center'}}><FIc name="check" size={12}/></div>}
                </button>
              ))}
            </div>
          </div>
        )}

        {mode==='new' && (
          <div style={{padding:'18px 24px', display:'grid', gap:14}}>
            <label><div style={{fontSize:13, fontWeight:500, marginBottom:6}}>Project name *</div><input className="input" value={newName} onChange={e=>setNewName(e.target.value)} placeholder="Suggested: Scottsdale strip retail scan" style={{width:'100%'}}/></label>
            <label><div style={{fontSize:13, fontWeight:500, marginBottom:6}}>Property address</div><input className="input" value={newAddr} onChange={e=>setNewAddr(e.target.value)} placeholder="Optional — link to a property" style={{width:'100%'}}/></label>
            <div style={{padding:'10px 12px', background:'var(--cream)', borderRadius:8, fontSize:12, color:'var(--slate)', lineHeight:1.5}}>
              <b style={{color:'var(--navy)'}}>Tip</b> — your existing chat history stays. The shift is forward-looking: new messages benefit from project context and uploaded data.
            </div>
          </div>
        )}

        <div style={{padding:'14px 24px', borderTop:'1px solid var(--line)', background:'var(--cream)', display:'flex', justifyContent:'flex-end', gap:10}}>
          <button className="btn btn-ghost" onClick={close}>Cancel</button>
          <button className="btn btn-accent" disabled={mode==='existing' ? !picked : !newName} style={{opacity: (mode==='existing'?!!picked:!!newName)?1:0.5}} onClick={close}>
            {mode==='existing' ? 'Save to project' : 'Create & save'}
          </button>
        </div>
      </div>
    </div>
  );
}

window.PerigeeChat = { ChatScreen };
