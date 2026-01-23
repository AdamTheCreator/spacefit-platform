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
    // Clear the chat store to reset state
    clearChat();
    // Navigate to /chat - session will be created when user sends first message
    navigate('/chat');
  };

  const handleDeleteSession = async (e: React.MouseEvent, sessionId: string) => {
    e.preventDefault();
    e.stopPropagation();
    await deleteSession(sessionId);
    // If we deleted the current session, navigate to the main chat
    if (sessionId === currentSessionId) {
      navigate('/chat');
    }
  };

  // Menu items for keyboard navigation
  const menuItems = [
    { path: '/profile', label: 'Profile' },
    { path: '/customers', label: 'Customers' },
    { path: '/connections', label: 'Connections' },
    { path: '/settings', label: 'Settings' },
    { action: 'logout', label: 'Sign out' },
  ];

  // Handle keyboard navigation in dropdown
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

  // Reset focus when dropdown opens/closes
  useEffect(() => {
    if (dropdownOpen) {
      setFocusedIndex(0);
    } else {
      setFocusedIndex(-1);
    }
  }, [dropdownOpen]);

  return (
    <div className="h-screen flex bg-gray-900">
      {/* Skip link for keyboard users */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-blue-600 focus:text-white focus:rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-gray-900"
      >
        Skip to main content
      </a>

      {/* Sidebar */}
      <div
        className={`${
          sidebarOpen ? 'w-64' : 'w-0'
        } transition-all duration-300 flex flex-col bg-gray-800 border-r border-gray-700 overflow-hidden`}
      >
        {/* Sidebar Header */}
        <div className="p-4 border-b border-gray-700">
          <button
            onClick={handleNewChat}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
          >
            <Plus size={18} />
            New Chat
          </button>
        </div>

        {/* Main Navigation */}
        <div className="p-2 border-b border-gray-700 space-y-1">
          <Link
            to="/pipeline"
            className="flex items-center gap-3 px-3 py-2 text-gray-300 hover:bg-gray-700 rounded-lg transition-colors"
          >
            <Kanban size={18} className="text-indigo-400" />
            <span className="text-sm font-medium">Deal Pipeline</span>
          </Link>
          <Link
            to="/documents"
            className="flex items-center gap-3 px-3 py-2 text-gray-300 hover:bg-gray-700 rounded-lg transition-colors"
          >
            <FileText size={18} className="text-green-400" />
            <span className="text-sm font-medium">Documents</span>
          </Link>
          <Link
            to="/outreach"
            className="flex items-center gap-3 px-3 py-2 text-gray-300 hover:bg-gray-700 rounded-lg transition-colors"
          >
            <Mail size={18} className="text-amber-400" />
            <span className="text-sm font-medium">Outreach</span>
          </Link>
        </div>

        {/* Chat History */}
        <div className="flex-1 overflow-y-auto p-2">
          <div className="text-xs text-gray-500 uppercase tracking-wider px-2 py-2">
            Conversations
          </div>
          {isLoading ? (
            <div className="text-gray-500 text-sm px-2 py-4">Loading...</div>
          ) : sessions.filter(s => s.message_count > 0).length === 0 ? (
            <div className="text-gray-500 text-sm px-2 py-4">
              No conversations yet
            </div>
          ) : (
            <div className="space-y-1">
              {sessions.filter(s => s.message_count > 0).map((session) => (
                <Link
                  key={session.id}
                  to={`/chat/${session.id}`}
                  className={`flex items-center gap-2 px-3 py-2 text-gray-300 hover:bg-gray-700 rounded-lg transition-colors group ${
                    session.id === currentSessionId ? 'bg-gray-700' : ''
                  }`}
                >
                  <MessageSquare size={16} className="text-gray-500 flex-shrink-0" />
                  <span className="flex-1 truncate text-sm">
                    {session.title || 'New conversation'}
                  </span>
                  <button
                    onClick={(e) => handleDeleteSession(e, session.id)}
                    className="opacity-0 group-hover:opacity-100 p-1 hover:bg-gray-600 rounded transition-opacity"
                    title="Delete conversation"
                    aria-label="Delete conversation"
                  >
                    <X size={14} className="text-gray-400 hover:text-red-400" />
                  </button>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Sidebar Footer */}
        <div className="p-4 border-t border-gray-700 space-y-3">
          {/* Profile Completion Nudge */}
          {preferences && !preferences.is_complete && (
            <Link
              to="/settings"
              className="block p-3 bg-purple-900/30 hover:bg-purple-900/40 border border-purple-700/50 rounded-lg transition-colors group"
            >
              <div className="flex items-center gap-2 mb-2">
                <Sparkles size={16} className="text-purple-400" />
                <span className="text-sm font-medium text-purple-300">Personalize AI</span>
              </div>
              <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden mb-1">
                <div
                  className="h-full bg-purple-500 transition-all"
                  style={{ width: `${preferences.completion_percentage}%` }}
                />
              </div>
              <p className="text-xs text-gray-400 group-hover:text-gray-300">
                {preferences.completion_percentage}% complete - Set up your preferences
              </p>
            </Link>
          )}
          <div className="text-xs text-gray-500">SpaceFit AI v0.1</div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Header */}
        <header className="h-14 flex items-center justify-between px-4 border-b border-gray-700 bg-gray-800/50">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              aria-label={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
              className="p-2 text-gray-400 hover:text-white hover:bg-gray-700 rounded-lg transition-colors"
            >
              {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
            <h1 className="text-lg font-semibold text-white">SpaceFit AI</h1>
          </div>

          {/* User Dropdown */}
          <div className="relative" ref={dropdownRef} onKeyDown={handleDropdownKeyDown}>
            <button
              onClick={() => setDropdownOpen(!dropdownOpen)}
              aria-haspopup="menu"
              aria-expanded={dropdownOpen}
              className="flex items-center gap-2 px-3 py-2 text-gray-300 hover:bg-gray-700 rounded-lg transition-colors"
            >
              <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center">
                <span className="text-white text-sm font-medium">
                  {user?.first_name?.[0] || user?.email?.[0]?.toUpperCase() || 'U'}
                </span>
              </div>
              <span className="text-sm hidden sm:block">
                {user?.first_name || user?.email?.split('@')[0]}
              </span>
              <ChevronDown size={16} />
            </button>

            {dropdownOpen && (
              <>
                <div
                  className="fixed inset-0 z-10"
                  onClick={() => setDropdownOpen(false)}
                />
                <div
                  className="absolute right-0 mt-2 w-56 bg-gray-800 border border-gray-700 rounded-lg shadow-lg z-20 py-1"
                  role="menu"
                  aria-orientation="vertical"
                >
                  <div className="px-4 py-3 border-b border-gray-700">
                    <p className="text-sm font-medium text-white">
                      {user?.first_name} {user?.last_name}
                    </p>
                    <p className="text-xs text-gray-400">{user?.email}</p>
                  </div>

                  <Link
                    to="/profile"
                    onClick={() => setDropdownOpen(false)}
                    role="menuitem"
                    tabIndex={focusedIndex === 0 ? 0 : -1}
                    className={`flex items-center gap-3 px-4 py-2 text-gray-300 hover:bg-gray-700 transition-colors ${focusedIndex === 0 ? 'bg-gray-700' : ''}`}
                  >
                    <User size={16} />
                    <span className="text-sm">Profile</span>
                  </Link>

                  <Link
                    to="/customers"
                    onClick={() => setDropdownOpen(false)}
                    role="menuitem"
                    tabIndex={focusedIndex === 1 ? 0 : -1}
                    className={`flex items-center gap-3 px-4 py-2 text-gray-300 hover:bg-gray-700 transition-colors ${focusedIndex === 1 ? 'bg-gray-700' : ''}`}
                  >
                    <Users size={16} />
                    <span className="text-sm">Customers</span>
                  </Link>

                  <Link
                    to="/connections"
                    onClick={() => setDropdownOpen(false)}
                    role="menuitem"
                    tabIndex={focusedIndex === 2 ? 0 : -1}
                    className={`flex items-center gap-3 px-4 py-2 text-gray-300 hover:bg-gray-700 transition-colors ${focusedIndex === 2 ? 'bg-gray-700' : ''}`}
                  >
                    <Key size={16} />
                    <span className="text-sm">Connections</span>
                  </Link>

                  <Link
                    to="/settings"
                    onClick={() => setDropdownOpen(false)}
                    role="menuitem"
                    tabIndex={focusedIndex === 3 ? 0 : -1}
                    className={`flex items-center gap-3 px-4 py-2 text-gray-300 hover:bg-gray-700 transition-colors ${focusedIndex === 3 ? 'bg-gray-700' : ''}`}
                  >
                    <Settings size={16} />
                    <span className="text-sm">Settings</span>
                  </Link>

                  <div className="border-t border-gray-700 mt-1 pt-1">
                    <button
                      onClick={handleLogout}
                      role="menuitem"
                      tabIndex={focusedIndex === 4 ? 0 : -1}
                      className={`flex items-center gap-3 px-4 py-2 text-red-400 hover:bg-gray-700 transition-colors w-full ${focusedIndex === 4 ? 'bg-gray-700' : ''}`}
                    >
                      <LogOut size={16} />
                      <span className="text-sm">Sign out</span>
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </header>

        {/* Page Content */}
        <main id="main-content" className="flex-1 overflow-hidden">{children}</main>
      </div>
    </div>
  );
}
