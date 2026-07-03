interface WelcomeScreenProps {
  onQuickSend: (text: string) => void;
}

export default function WelcomeScreen({
  onQuickSend,
}: WelcomeScreenProps) {
  const suggestions = [
    {
      emoji: "🌶️",
      title: "Nirapara Chicken Masala",
      subtitle: "Spices & groceries",
    },
    {
      emoji: "👟",
      title: "Nike Running Shoes",
      subtitle: "Footwear",
    },
    {
      emoji: "📱",
      title: "iPhone 17 Pro",
      subtitle: "Smartphones",
    },
    {
      emoji: "🛒",
      title: "Amul Butter",
      subtitle: "Daily essentials",
    },
  ];

  return (
    <div className="w-full max-w-2xl">
      <div className="bg-white border border-gray-100 rounded-2xl p-5 shadow-sm">
        <p className="text-sm font-semibold text-gray-900 mb-1">
          ✨ Hi! I'm your AI shopping assistant.
        </p>

        <p className="text-xs text-gray-500 mb-4 leading-relaxed">
          I compare prices across Amazon, Flipkart, Croma & more.
        </p>

        <div className="grid grid-cols-2 gap-2">
          {suggestions.map((s, i) => (
            <button
              key={i}
              onClick={() => onQuickSend(s.title)}
              className="flex items-center gap-3 p-3 border border-gray-100 rounded-xl hover:border-gray-300 hover:shadow-sm transition text-left bg-gray-50 hover:bg-white"
            >
              <span className="text-xl">{s.emoji}</span>

              <div>
                <div className="text-xs font-medium text-gray-900">
                  {s.title}
                </div>

                <div className="text-[10px] text-gray-400">
                  {s.subtitle}
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}