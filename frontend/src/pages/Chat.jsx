import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { Send, ArrowLeft, Loader } from 'lucide-react';

export default function Chat() {
  const navigate = useNavigate();
  const [messages, setMessages] = useState([
    {
      id: 1,
      role: 'assistant',
      content: '안녕하세요! 감잡아 AI 어드바이저입니다. 🍊\n\n감 재배에 관해 궁금한 점이나 문제가 있으시면 편하게 물어봐주세요!\n\n💡 질문 예시:\n• "오늘 할 일이 뭐야?"\n• "앞으로 한 달 계획을 세워줘"\n• "잎에 하얀 가루 같은 게 있어요"'
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

    const userMessage = {
      id: messages.length + 1,
      role: 'user',
      content: input
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    const assistantMessage = {
      id: messages.length + 2,
      role: 'assistant',
      content: ''
    };
    setMessages((prev) => [...prev, assistantMessage]);

    try {
      let fullResponse = '';
      await api.streamChat('demo-farm', input, (chunk) => {
        fullResponse += chunk;
        setMessages((prev) => [
          ...prev.slice(0, -1),
          { ...assistantMessage, content: fullResponse }
        ]);
      });

      if (!fullResponse) {
        setMessages((prev) => [
          ...prev.slice(0, -1),
          {
            ...assistantMessage,
            content: '죄송합니다. 답변을 생성할 수 없었습니다. 다시 시도해 주세요.'
          }
        ]);
      }
    } catch (error) {
      console.error('메시지 전송 실패:', error);
      setMessages((prev) => [
        ...prev.slice(0, -1),
        {
          ...assistantMessage,
          content: '⚠️ 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.'
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-orange-50 to-amber-50 flex flex-col">
      {/* 헤더 */}
      <header className="bg-white shadow-sm border-b-2 border-orange-200">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center gap-4">
          <button
            onClick={() => navigate('/')}
            className="p-2 hover:bg-orange-100 rounded-lg transition text-orange-600"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div className="flex-1">
            <h1 className="text-2xl font-bold bg-gradient-to-r from-orange-600 to-orange-500 bg-clip-text text-transparent">
              🍊 감잡아 AI 상담
            </h1>
            <p className="text-sm text-gray-500">AI 어드바이저가 감 재배를 도와드립니다</p>
          </div>
        </div>
      </header>

      {/* 채팅 영역 */}
      <main className="flex-1 max-w-4xl mx-auto w-full px-6 py-8 overflow-y-auto">
        <div className="space-y-5">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-xs lg:max-w-md xl:max-w-lg px-4 py-3 rounded-2xl ${
                  msg.role === 'user'
                    ? 'bg-gradient-to-r from-orange-500 to-orange-600 text-white rounded-br-none shadow-md'
                    : 'bg-white text-gray-800 rounded-bl-none shadow-sm border border-orange-100'
                }`}
              >
                <p className="text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</p>
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-white text-gray-800 px-4 py-3 rounded-2xl rounded-bl-none flex gap-2 shadow-sm border border-orange-100">
                <Loader className="w-4 h-4 animate-spin text-orange-500" />
                <span className="text-sm">생각 중...</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </main>

      {/* 입력 영역 */}
      <footer className="bg-white border-t-2 border-orange-200">
        <form
          onSubmit={handleSendMessage}
          className="max-w-4xl mx-auto px-6 py-4 flex gap-3"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="질문을 입력해 주세요..."
            disabled={loading}
            className="flex-1 px-4 py-3 border-2 border-orange-200 rounded-full focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent disabled:bg-gray-50 transition"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 disabled:from-gray-300 disabled:to-gray-300 text-white font-semibold px-6 py-3 rounded-full transition flex items-center gap-2 shadow-md hover:shadow-lg"
          >
            <Send className="w-4 h-4" />
            <span className="hidden sm:inline">전송</span>
          </button>
        </form>
      </footer>
    </div>
  );
}
