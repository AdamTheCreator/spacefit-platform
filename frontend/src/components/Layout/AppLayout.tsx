import { useState, useCallback, useEffect, useRef } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  MessageSquare,
  Plus,
  User,
  Settings,
  LogOut,
  Users,
  Key,
  ChevronDown,
  Menu,
  X,
  Kanban,
  FileText,
  Mail,
  Sparkles,
} from 'lucide-react';
import { useAuthStore } from '../../stores/authStore';
import { useChatStore } from '../../stores/chatStore';
import { useChatSessions } from '../../hooks/useChatSessions';
import { usePreferences } from '../../hooks/usePreferences';

interface AppLayoutProps {
  children: React.ReactNode;
}

export function AppLayout({ children }: AppLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const { user, logout } = useAuthStore();
  const { clearChat } = useChatStore();
  const navigate = useNavigate();
  const { sessionId: currentSessionId } = useParams<{ sessionId?: string }>();
  const { sessions, isLoading, deleteSession } = useChatSessions();
  const { data: preferences } = usePreferences();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const handleNewChat = () => {
    clearChat();
    navigate('/chat');
  };

  const handleDeleteSession = async (e: React.MouseEvent, sessionId: string) => {
    e.preventDefault();
    e.stopPropagation();
    await deleteSession(sessionId);
    if (sessionId === currentSessionId) {
      navigate('/chat');
    }
  };

  const menuItems = [
    { path: '/profile', label: 'Profile' },
    { path: '/customers', label: 'Customers' },
    { path: '/connections', label: 'Connections' },
    { path: '/settings', label: 'Settings' },
    { action: 'logout', label: 'Sign out' },
  ];

  const handleDropdownKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (!dropdownOpen) return;

    switch (e.key) {
      case 'Escape':
        setDropdownOpen(false);
        setFocusedIndex(-1);
        break;
      case 'ArrowDown':
        e.preventDefault();
        setFocusedIndex(prev => Math.min(prev + 1, menuItems.length - 1));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setFocusedIndex(prev => Math.max(prev - 1, 0));
        break;
      case 'Enter':
      case ' ':
        e.preventDefault();
        if (focusedIndex >= 0) {
          const item = menuItems[focusedIndex];
          if (item.action === 'logout') {
            handleLogout();
          } else if (item.path) {
            navigate(item.path);
            setDropdownOpen(false);
          }
        }
        break;
      case 'Tab':
        setDropdownOpen(false);
        setFocusedIndex(-1);
        break;
    }
  }, [dropdownOpen, focusedIndex, menuItems, navigate, handleLogout]);

  useEffect(() => {
    if (dropdownOpen) {
      setFocusedIndex(0);
    } else {
      setFocusedIndex(-1);
    }
  }, [dropdownOpen]);

  return (
    <div className="h-screen flex bg-industrial-secondary dark">
      {/* Skip link for keyboard users */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 bg-accent text-industrial-950"
      >
        Skip to main content
      </a>

      {/* Sidebar */}
      <div
        className={`${
          sidebarOpen ? 'w-64' : 'w-0'
        } transition-all duration-300 flex flex-col bg-[var(--bg-elevated)] border-r border-industrial overflow-hidden`}
      >
        {/* Sidebar Header */}
        <div className="p-4 border-b border-industrial">
          <button
            onClick={handleNewChat}
            className="btn-industrial-primary w-full"
          >
            <Plus size={16} />
            New Chat
          </button>
        </div>

        {/* Main Navigation */}
        <div className="p-2 border-b border-industrial">
          <div className="label-technical px-3 py-2">Navigation</div>
          <nav className="space-y-0.5">
            <Link
              to="/pipeline"
              className="nav-industrial-item w-full"
            >
              <Kanban size={14} />
              <span>Pipeline</span>
            </Link>
            <Link
              to="/documents"
              className="nav-industrial-item w-full"
            >
              <FileText size={14} />
              <span>Documents</span>
            </Link>
            <Link
              to="/outreach"
              className="nav-industrial-item w-full"
            >
              <Mail size={14} />
              <span>Outreach</span>
            </Link>
          </nav>
        </div>

        {/* Chat History */}
        <div className="flex-1 overflow-y-auto p-2 scrollbar-industrial">
          <div className="label-technical px-3 py-2">Conversations</div>
          {isLoading ? (
            <div className="text-industrial-muted text-xs font-mono px-3 py-4">Loading...</div>
          ) : sessions.filter(s => s.message_count > 0).length === 0 ? (
            <div className="text-industrial-muted text-xs font-mono px-3 py-4">
              No conversations yet
            </div>
          ) : (
            <div className="space-y-0.5">
              {sessions.filter(s => s.message_count > 0).map((session) => (
                <Link
                  key={session.id}
                  to={`/chat/${session.id}`}
                  className={`flex items-center gap-2 px-3 py-2 text-industrial-secondary hover:bg-[var(--bg-tertiary)] transition-colors group ${
                    session.id === currentSessionId ? 'bg-[var(--bg-tertiary)] border-l-2 border-[var(--accent)]' : ''
                  }`}
                >
                  <MessageSquare size={14} className="text-industrial-muted flex-shrink-0" />
                  <span className="flex-1 truncate text-xs font-mono">
                    {session.title || 'New conversation'}
                  </span>
                  <button
                    onClick={(e) => handleDeleteSession(e, session.id)}
                    className="opacity-0 group-hover:opacity-100 p-1 hover:bg-[var(--bg-secondary)] transition-opacity"
                    title="Delete conversation"
                    aria-label="Delete conversation"
                  >
                    <X size={12} className="text-industrial-muted hover:text-[var(--color-error)]" />
                  </button>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Sidebar Footer */}
        <div className="p-4 border-t border-industrial space-y-3">
          {/* Profile Completion Nudge */}
          {preferences && !preferences.is_complete && (
            <Link
              to="/settings"
              className="block p-3 bg-[var(--bg-tertiary)] hover:bg-[var(--bg-secondary)] border border-industrial transition-colors group"
            >
              <div className="flex items-center gap-2 mb-2">
                <Sparkles size={14} className="text-[var(--accent)]" />
                <span className="label-technical text-[var(--accent)]">Setup Required</span>
              </div>
              <div className="h-1 bg-[var(--bg-secondary)] overflow-hidden mb-2">
                <div
                  className="h-full bg-[var(--accent)] transition-all"
                  style={{ width: `${preferences.completion_percentage}%` }}
                />
              </div>
              <p className="text-xs font-mono text-industrial-muted group-hover:text-industrial-secondary">
                {preferences.completion_percentage}% complete
              </p>
            </Link>
          )}
          <div className="label-technical">SpaceFit v0.1</div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Header */}
        <header className="h-12 flex items-center justify-between px-4 border-b border-industrial bg-[var(--bg-elevated)]">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              aria-label={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
              className="btn-industrial-ghost p-2"
            >
              {sidebarOpen ? <X size={18} /> : <Menu size={18} />}
            </button>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-[var(--accent)]" />
              <span className="font-mono text-xs font-semibold tracking-widest uppercase text-industrial">
                SpaceFit
              </span>
            </div>
          </div>

          {/* User Dropdown */}
          <div className="relative" ref={dropdownRef} onKeyDown={handleDropdownKeyDown}>
            <button
              onClick={() => setDropdownOpen(!dropdownOpen)}
              aria-haspopup="menu"
              aria-expanded={dropdownOpen}
              className="flex items-center gap-2 px-3 py-1.5 text-industrial-secondary hover:bg-[var(--bg-tertiary)] transition-colors border border-transparent hover:border-industrial"
            >
              <div className="w-6 h-6 bg-[var(--accent)] flex items-center justify-center">
                <span className="text-industrial-950 text-xs font-mono font-bold">
                  {user?.first_name?.[0] || user?.email?.[0]?.toUpperCase() || 'U'}
                </span>
              </div>
              <span className="text-xs font-mono hidden sm:block">
                {user?.first_name || user?.email?.split('@')[0]}
              </span>
              <ChevronDown size={14} />
            </button>

            {dropdownOpen && (
              <>
                <div
                  className="fixed inset-0 z-10"
                  onClick={() => setDropdownOpen(false)}
                />
                <div
                  className="absolute right-0 mt-1 w-56 bg-[var(--bg-elevated)] border border-industrial shadow-lg z-20"
                  role="menu"
                  aria-orientation="vertical"
                >
                  <div className="px-4 py-3 border-b border-industrial">
                    <p className="text-xs font-mono font-medium text-industrial">
                      {user?.first_name} {user?.last_name}
                    </p>
                    <p className="text-xs font-mono text-industrial-muted">{user?.email}</p>
                  </div>

                  <Link
                    to="/profile"
                    onClick={() => setDropdownOpen(false)}
                    role="menuitem"
                    tabIndex={focusedIndex === 0 ? 0 : -1}
                    className={`flex items-center gap-3 px-4 py-2 text-industrial-secondary hover:bg-[var(--bg-tertiary)] transition-colors ${focusedIndex === 0 ? 'bg-[var(--bg-tertiary)]' : ''}`}
                  >
                    <User size={14} />
                    <span className="text-xs font-mono uppercase tracking-wide">Profile</span>
                  </Link>

                  <Link
                    to="/customers"
                    onClick={() => setDropdownOpen(false)}
                    role="menuitem"
                    tabIndex={focusedIndex === 1 ? 0 : -1}
                    className={`flex items-center gap-3 px-4 py-2 text-industrial-secondary hover:bg-[var(--bg-tertiary)] transition-colors ${focusedIndex === 1 ? 'bg-[var(--bg-tertiary)]' : ''}`}
                  >
                    <Users size={14} />
                    <span className="text-xs font-mono uppercase tracking-wide">Customers</span>
                  </Link>

                  <Link
                    to="/connections"
                    onClick={() => setDropdownOpen(false)}
                    role="menuitem"
                    tabIndex={focusedIndex === 2 ? 0 : -1}
                    className={`flex items-center gap-3 px-4 py-2 text-industrial-secondary hover:bg-[var(--bg-tertiary)] transition-colors ${focusedIndex === 2 ? 'bg-[var(--bg-tertiary)]' : ''}`}
                  >
                    <Key size={14} />
                    <span className="text-xs font-mono uppercase tracking-wide">Connections</span>
                  </Link>

                  <Link
                    to="/settings"
                    onClick={() => setDropdownOpen(false)}
                    role="menuitem"
                    tabIndex={focusedIndex === 3 ? 0 : -1}
                    className={`flex items-center gap-3 px-4 py-2 text-industrial-secondary hover:bg-[var(--bg-tertiary)] transition-colors ${focusedIndex === 3 ? 'bg-[var(--bg-tertiary)]' : ''}`}
                  >
                    <Settings size={14} />
                    <span className="text-xs font-mono uppercase tracking-wide">Settings</span>
                  </Link>

                  <div className="border-t border-industrial mt-1 pt-1">
                    <button
                      onClick={handleLogout}
                      role="menuitem"
                      tabIndex={focusedIndex === 4 ? 0 : -1}
                      className={`flex items-center gap-3 px-4 py-2 text-[var(--color-error)] hover:bg-[var(--bg-tertiary)] transition-colors w-full ${focusedIndex === 4 ? 'bg-[var(--bg-tertiary)]' : ''}`}
                    >
                      <LogOut size={14} />
                      <span className="text-xs font-mono uppercase tracking-wide">Sign out</span>
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </header>

        {/* Page Content */}
        <main id="main-content" className="flex-1 overflow-hidden bg-industrial">{children}</main>
      </div>
    </div>
  );
}
