/* Perigee app shell — sidebar + top bar + screen router */
const { useMemo } = React;

/* -------- Reusable bits -------- */

function LogoMark({ size = 32 }) {
  return (
    <img src="assets/perigee-logo.png" alt="Perigee" width={size} height={size}
      style={{display:'block', borderRadius:'50%', flexShrink:0, objectFit:'cover'}}/>
  );
}

function Icon({ name, size = 18 }) {
  const paths = {
    home: <><path d="M3 11l9-8 9 8"/><path d="M5 10v10a1 1 0 001 1h4v-6h4v6h4a1 1 0 001-1V10"/></>,
    search: <><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></>,
    building: <><path d="M4 21V5a2 2 0 012-2h8a2 2 0 012 2v16"/><path d="M16 8h3a2 2 0 012 2v11"/><path d="M8 7h2M8 11h2M8 15h2"/></>,
    chart: <><path d="M3 3v18h18"/><path d="m7 14 4-4 3 3 5-6"/></>,
    workflow: <><path d="M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z"/><path d="M10 7h4M7 10v4M17 10v4M10 17h4"/></>,
    sparkles: <><path d="M5 3v4M3 5h4M19 15v4M17 17h4M12 2l2 6 6 2-6 2-2 6-2-6-6-2 6-2z"/></>,
    bell: <><path d="M18 8a6 6 0 10-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 01-3.4 0"/></>,
    plus: <><path d="M12 5v14M5 12h14"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 11-4 0v-.09A1.65 1.65 0 008.92 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 110-4h.09A1.65 1.65 0 004.6 8.92a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 114 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 110 4h-.09a1.65 1.65 0 00-1.51 1z"/></>,
    help: <><circle cx="12" cy="12" r="9"/><path d="M9.1 9a3 3 0 015.8 1c0 2-3 3-3 3M12 17h.01"/></>,
    arrow: <><path d="M5 12h14M13 5l7 7-7 7"/></>,
    filter: <><path d="M22 3H2l8 9.5V19l4 2v-8.5z"/></>,
    map: <><path d="M1 6v16l7-3 8 3 7-3V3l-7 3-8-3z"/><path d="M8 3v16M16 6v15"/></>,
    grid: <><path d="M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z"/></>,
    list: <><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/></>,
    check: <><path d="M5 12l4 4L19 6"/></>,
    dot: <><circle cx="12" cy="12" r="2"/></>,
    calendar: <><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></>,
    star: <><path d="M12 2l3 7 7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1z"/></>,
    dollar: <><path d="M12 1v22M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></>,
    layers: <><path d="M12 2l10 5-10 5L2 7z"/><path d="M2 17l10 5 10-5M2 12l10 5 10-5"/></>,
    users: <><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/></>,
    chat: <><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></>,
    clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
    doc: <><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/></>,
    pin: <><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></>,
    send: <><path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4z"/></>,
    mail: <><rect x="2" y="4" width="20" height="16" rx="2"/><path d="m2 7 10 7 10-7"/></>,
  };
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" style={{flexShrink:0}}>
      {paths[name]}
    </svg>
  );
}

/* -------- Sidebar -------- */

function Sidebar({ screen, setScreen }) {
  const items = [
    { id: 'dashboard', label: 'Dashboard', icon: 'home' },
    { id: 'search', label: 'Find properties', icon: 'search' },
    { id: 'property', label: 'Properties', icon: 'building' },
    { id: 'projects', label: 'Projects', icon: 'layers' },
    { id: 'outreach', label: 'Outreach', icon: 'send' },
    { id: 'contacts', label: 'Contacts', icon: 'users' },
    { id: 'chat', label: 'Chat', icon: 'chat' },
  ];
  const lowerItems = [
    { id: 'settings', label: 'Settings', icon: 'settings' },
  ];
  const demoItems = [
    { id: 'analytics', label: 'Analytics (legacy)', icon: 'chart' },
    { id: 'workflow',  label: 'Workflow (legacy)', icon: 'workflow' },
    { id: 'insights',  label: 'Insights (legacy)', icon: 'sparkles' },
    { id: 'onboarding',label: 'Onboarding state',  icon: 'star' },
    { id: 'empty',     label: 'Empty state',       icon: 'dot' },
  ];
  const [demoOpen, setDemoOpen] = React.useState(false);
  return (
    <aside style={{
      width: 248, background: '#fff', borderRight: '1px solid var(--line)',
      display: 'flex', flexDirection: 'column',
      position: 'sticky', top: 0, height: '100vh',
    }}>
      <div style={{ padding: '20px 18px', display:'flex', alignItems:'center', gap:10, borderBottom:'1px solid var(--line)' }}>
        <LogoMark size={32} />
        <span style={{ fontFamily:'var(--sora)', fontWeight:700, fontSize:17, color:'var(--navy)', letterSpacing:'0.02em' }}>PERIGEE</span>
        <span className="pill pill-mist" style={{marginLeft:'auto', fontSize:10}}>v2.4</span>
      </div>

      <div style={{ padding:'12px 12px' }}>
        <div style={{ fontSize:11, fontWeight:600, letterSpacing:'0.1em', color:'var(--gray)', padding:'8px 10px 4px', textTransform:'uppercase' }}>Workspace</div>
        {items.map(it => (
          <button key={it.id} onClick={() => setScreen(it.id)}
            style={{
              display:'flex', alignItems:'center', gap:10, width:'100%',
              padding:'10px 12px', borderRadius:10,
              background: screen === it.id ? 'var(--navy)' : 'transparent',
              color: screen === it.id ? '#fff' : 'var(--slate)',
              border:'none', cursor:'pointer',
              fontSize:14, fontWeight: screen === it.id ? 600 : 500,
              fontFamily:'var(--inter)',
              marginBottom: 2, textAlign:'left',
              transition:'background 0.15s',
            }}>
            <Icon name={it.icon} size={17}/>
            <span>{it.label}</span>
            {screen === it.id && <span style={{marginLeft:'auto', width:6, height:6, background:'var(--orange)', borderRadius:'50%'}}/>}
          </button>
        ))}
      </div>

      <div style={{ padding:'0 12px' }}>
        <div style={{ fontSize:11, fontWeight:600, letterSpacing:'0.1em', color:'var(--gray)', padding:'14px 10px 4px', textTransform:'uppercase' }}>Account</div>
        {lowerItems.map(it => (
          <button key={it.id} onClick={() => setScreen(it.id)}
            style={{
              display:'flex', alignItems:'center', gap:10, width:'100%',
              padding:'10px 12px', borderRadius:10,
              background: screen === it.id ? 'var(--navy)' : 'transparent',
              color: screen === it.id ? '#fff' : 'var(--slate)',
              border:'none', cursor:'pointer',
              fontSize:14, fontWeight: screen === it.id ? 600 : 500,
              fontFamily:'var(--inter)',
              marginBottom: 2, textAlign:'left',
            }}>
            <Icon name={it.icon} size={17}/>
            <span>{it.label}</span>
          </button>
        ))}

        {/* Collapsible demo states */}
        <button onClick={() => setDemoOpen(o => !o)}
          style={{
            display:'flex', alignItems:'center', gap:8, width:'100%',
            padding:'12px 10px 4px', textTransform:'uppercase',
            fontSize:11, fontWeight:600, letterSpacing:'0.1em',
            color:'var(--gray)', background:'transparent', border:'none',
            cursor:'pointer', textAlign:'left', fontFamily:'var(--inter)',
          }}>
          <span>Demo screens</span>
          <span style={{transform: demoOpen ? 'rotate(90deg)' : 'rotate(0)', transition:'transform 0.15s', fontSize:9}}>▶</span>
        </button>
        {demoOpen && demoItems.map(it => (
          <button key={it.id} onClick={() => setScreen(it.id)}
            style={{
              display:'flex', alignItems:'center', gap:10, width:'100%',
              padding:'8px 12px', borderRadius:10,
              background: screen === it.id ? 'var(--navy)' : 'transparent',
              color: screen === it.id ? '#fff' : 'var(--gray)',
              border:'none', cursor:'pointer',
              fontSize:13, fontWeight: screen === it.id ? 600 : 400,
              fontFamily:'var(--inter)',
              marginBottom: 2, textAlign:'left',
            }}>
            <Icon name={it.icon} size={15}/>
            <span>{it.label}</span>
          </button>
        ))}
      </div>

      <div style={{ marginTop:'auto', padding: 14, borderTop:'1px solid var(--line)' }}>
        <div style={{ background:'var(--cream)', borderRadius:12, padding:14, position:'relative', overflow:'hidden' }}>
          <img src="assets/goose-solar.png" alt="" style={{position:'absolute', right:-18, bottom:-14, width:96, height:96, objectFit:'contain', opacity:0.95}}/>
          <div style={{position:'relative', zIndex:1, maxWidth:130}}>
            <div style={{fontSize:12, fontWeight:600, color:'var(--navy)', fontFamily:'var(--sora)'}}>Trial · 9 days left</div>
            <div style={{fontSize:11, color:'var(--slate)', marginTop:4, lineHeight:1.4}}>Add a seat for $39/mo</div>
            <button className="btn btn-primary btn-sm" style={{marginTop:10, padding:'6px 10px', fontSize:12}}>Upgrade</button>
          </div>
        </div>
        <div style={{display:'flex', alignItems:'center', gap:10, padding:'12px 4px 0'}}>
          <div style={{position:'relative', flexShrink:0}}>
            <div className="avatar" style={{width:34, height:34, fontSize:13}}>JL</div>
            <span title="Connected" style={{position:'absolute', right:-1, bottom:-1, width:10, height:10, borderRadius:'50%', background:'#2F7A3B', border:'2px solid #fff'}}></span>
          </div>
          <div style={{flex:1, minWidth:0}}>
            <div style={{fontSize:13, fontWeight:600, color:'var(--navy)'}}>Jordan Lee</div>
            <div style={{fontSize:11, color:'var(--slate)', display:'flex', alignItems:'center', gap:5}}>
              <span style={{width:6, height:6, borderRadius:'50%', background:'#2F7A3B', display:'inline-block'}}></span>
              Connected
            </div>
          </div>
          <Icon name="settings" size={16}/>
        </div>
      </div>
    </aside>
  );
}

/* -------- Topbar -------- */
function Topbar({ title, subtitle, actions }) {
  return (
    <header style={{
      display:'flex', alignItems:'center', gap:16,
      padding:'18px 32px',
      borderBottom:'1px solid var(--line)',
      background:'rgba(255,255,255,0.7)', backdropFilter:'blur(10px)',
      position:'sticky', top:0, zIndex:10,
    }}>
      <div style={{flex:1, minWidth:0}}>
        <h1 style={{fontSize:22, fontWeight:600}}>{title}</h1>
        {subtitle && <div style={{fontSize:13, color:'var(--slate)', marginTop:2}}>{subtitle}</div>}
      </div>
      <div style={{display:'flex', alignItems:'center', gap:10}}>
        <div style={{display:'flex', alignItems:'center', gap:8, background:'#fff', border:'1px solid var(--line)', borderRadius:10, padding:'8px 12px', width:280, color:'var(--gray)'}}>
          <Icon name="search" size={15}/>
          <span style={{fontSize:13}}>Search properties, comps, people…</span>
          <span style={{marginLeft:'auto', fontSize:10, background:'var(--moonlight)', padding:'2px 6px', borderRadius:4, color:'var(--slate)'}} className="mono">⌘K</span>
        </div>
        <button className="btn btn-ghost btn-sm" style={{padding:8}} aria-label="Notifications"><Icon name="bell" size={18}/></button>
        <button className="btn btn-ghost btn-sm" style={{padding:8}} aria-label="Help"><Icon name="help" size={18}/></button>
        {actions}
      </div>
    </header>
  );
}

window.PerigeeShell = { Sidebar, Topbar, Icon, LogoMark };
