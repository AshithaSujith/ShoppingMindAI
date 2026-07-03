import { Plus, MessageSquare, ShoppingBag } from "lucide-react";

interface Session {
  id: string;
  title: string;
}

interface SidebarProps {
  sessions: Session[];
  currentSession: string | null;
  newSession: () => void;
  loadSession: (session: Session) => void;
}

export default function Sidebar({
  sessions,
  currentSession,
  newSession,
  loadSession,
}: SidebarProps) {
  return (
    <aside className="w-60 bg-white border-r border-gray-100 flex flex-col shadow-sm">
      <div className="p-5 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gray-900 flex items-center justify-center">
            <ShoppingBag size={16} className="text-white" />
          </div>

          <div>
            <h1 className="text-sm font-bold text-gray-900 leading-none">
              ShopBot
            </h1>
            <p className="text-[10px] text-gray-400 mt-0.5">
              AI Price Comparison
            </p>
          </div>
        </div>
      </div>

      <div className="p-3">
        <button
          onClick={newSession}
          className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl bg-gray-900 text-white text-sm hover:bg-black transition-all"
        >
          <Plus size={14} />
          New Search
        </button>
      </div>

      <div className="px-3 flex-1 overflow-y-auto">
        <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-2 px-1">
          Recent
        </p>

        {sessions.length === 0 ? (
          <p className="text-xs text-gray-300 px-1">
            No searches yet
          </p>
        ) : (
          <div className="space-y-0.5">
            {sessions.map((s) => (
              <button
                key={s.id}
                onClick={() => loadSession(s)}
                className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left text-xs transition ${
                  currentSession === s.id
                    ? "bg-gray-100 text-gray-900 font-medium"
                    : "text-gray-500 hover:bg-gray-50"
                }`}
              >
                <MessageSquare size={12} className="flex-shrink-0" />
                <span className="truncate">{s.title}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}