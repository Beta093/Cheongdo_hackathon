import { useState, useRef, useEffect } from 'react';
import { api } from '../services/api';
import { Send } from 'lucide-react';

export default function Chat() {
  const [messages, setMessages] = useState([
    {
      id: 1,
      role: 'assistant',
      content: '안녕하세요! 감잡아 AI 어드바이저입니다. 🍊\n\n감 재배에 관해 궁금한 점이나 문제가 있으시면 편하게 물어봐주세요!'
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    // 사용자 메시지 추가
    const userMessage = {
      id: messages.length + 1,
      role: 'user',
      content: input
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      // SSE 스트리밍
      let fullResponse = '';
      await api.streamChat('demo-farm', input, (chunk) => {
        fullResponse += chunk;
        // 실시간으로 메시지 업데이트
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last.role === 'assistant') {
            return [
              ...prev.slice(0, -1),
              { ...last, content: fullResponse }
            ];
          }
          return prev;
        });
      });

      // 응답이 없으면 기본 응답 추가
      if (!fullResponse) {
        setMessages((prev) => [
          ...prev,
          {
            id: prev.length + 1,
            role: 'assistant',
            content: '죄송합니다. 답변을 생성할 수 없었습니다. 다시 시도해 주세요.'
          }
        ]);
      }
    } catch (error) {
      console.error('메시지 전송 실패:', error);
      setMessages((prev) => [
        ...prev,
        {
          id: prev.length + 1,
          role: 'assistant',
          content: '⚠️ 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.'
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-green-50 to-blue-50 flex flex-col">
      {/* 헤더 */}
      <header className="bg-white shadow">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center gap-4">
          <button
            onClick={() => navigate('/')}
            className="p-2 hover:bg-gray-100 rounded-lg"
          >
            <ArrowLeft className="w-5 h-5 text-gray-600" />
          </button>
          <h1 className="text-2xl font-bold text-gray-800">
            감잡아 AI 상담
          </h1>
        </div>
      </header>

      {/* 채팅 영역 */}
      <main className="flex-1 max-w-4xl mx-auto w-full px-6 py-8 overflow-y-auto">
        <div className="space-y-4">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-xs lg:max-w-md xl:max-w-lg px-4 py-3 rounded-lg ${
                  msg.role === 'user'
                    ? 'bg-blue-600 text-white rounded-br-none'
                    : 'bg-gray-100 text-gray-800 rounded-bl-none'
                }`}
              >
                <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-gray-100 text-gray-800 px-4 py-3 rounded-lg rounded-bl-none flex gap-2">
                <Loader className="w-4 h-4 animate-spin" />
                <span className="text-sm">생각 중...</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </main>

      {/* 입력 영역 */}
      <footer className="bg-white border-t">
        <form
          onSubmit={handleSendMessage}
          className="max-w-4xl mx-auto px-6 py-4 flex gap-2"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="질문을 입력해 주세요..."
            disabled={loading}
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white font-semibold p-2 rounded-lg transition flex items-center gap-2"
          >
            <Send className="w-4 h-4" />
            <span className="hidden sm:inline">전송</span>
          </button>
        </form>
      </footer>
    </div>
  );
}
