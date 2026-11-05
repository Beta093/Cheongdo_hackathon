import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { Send, ArrowLeft, Loader, AlertCircle, CheckCircle } from 'lucide-react';

export default function Chat() {
  const navigate = useNavigate();
  const [step, setStep] = useState('chat');
  const [userInput, setUserInput] = useState('');
  const [maskedText, setMaskedText] = useState('');
  const [maskToken, setMaskToken] = useState('');
  
  const [messages, setMessages] = useState([
    {
      id: 1,
      role: 'assistant',
      content: '안녕하세요! 감잡아 AI 어드바이저입니다. 🍊\n\n감 재배에 관해 궁금한 점이나 문제가 있으시면 편하게 물어봐주세요!'
    }
  ]);
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleMask = async (e) => {
    e.preventDefault();
    if (!userInput.trim()) {
      setError('입력을 해주세요');
      return;
    }

    if (userInput.length > 4000) {
      setError('4000자를 초과했습니다');
      return;
    }

    setError(null);
    setLoading(true);

    try {
      const response = await fetch('http://localhost:8001/api/farms/demo/mask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: userInput })
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || '마스킹 실패');
      }

      const data = await response.json();
      setMaskedText(data.masked_text);
      setMaskToken(data.mask_token);
      setStep('masking');
      setError(null);
    } catch (err) {
      setError(err.message);
      console.error('마스킹 오류:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmMask = () => {
    setStep('chat');
    setError(null);
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!userInput.trim()) return;

    const userMessage = {
      id: messages.length + 1,
      role: 'user',
      content: userInput
    };
    setMessages((prev) => [...prev, userMessage]);
    setUserInput('');
    setLoading(true);
    setError(null);

    const assistantMessage = {
      id: messages.length + 2,
      role: 'assistant',
      content: ''
    };
    setMessages((prev) => [...prev, assistantMessage]);

    try {
      let fullResponse = '';
      
      await api.streamChat('demo', userInput, (chunk) => {
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
    } catch (err) {
      console.error('메시지 전송 실패:', err);
      setError(err.message);
      setMessages((prev) => [
        ...prev.slice(0, -1),
        {
          ...assistantMessage,
          content: `⚠️ 오류가 발생했습니다: ${err.message}`
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
            <p className="text-sm text-gray-500">
              {step === 'input' && 'Step 1: 상담 내용 입력'}
              {step === 'masking' && 'Step 2: 개인정보 확인'}
              {step === 'chat' && 'Step 3: AI 상담 진행 중'}
            </p>
          </div>
        </div>
      </header>

      {/* 에러 메시지 */}
      {error && (
        <div className="max-w-4xl mx-auto w-full px-6 mt-4">
          <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded">
            <div className="flex gap-3">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <p className="text-red-700">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Step 1: 입력 화면 */}
      {step === 'input' && (
        <main className="flex-1 max-w-4xl mx-auto w-full px-6 py-8 flex flex-col justify-center">
          <div className="bg-white rounded-2xl shadow-lg p-8 border-2 border-orange-100">
            <h2 className="text-2xl font-bold text-gray-800 mb-2">상담 내용 입력</h2>
            <p className="text-gray-600 mb-6">
              감 재배에 관한 질문이나 문제를 입력해주세요.
              <br />
              입력하신 정보는 마스킹 처리되어 안전하게 보호됩니다.
            </p>
            <form onSubmit={handleMask} className="space-y-4">
              <textarea
                value={userInput}
                onChange={(e) => setUserInput(e.target.value)}
                placeholder="예: 감에 갈색 반점이 생겼는데 어떻게 해야 하나요?"
                className="w-full px-4 py-3 border-2 border-orange-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent disabled:bg-gray-50 transition resize-none h-32"
                disabled={loading}
              />
              <button
                type="submit"
                disabled={loading || !userInput.trim()}
                className="w-full bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 disabled:from-gray-300 disabled:to-gray-300 text-white font-semibold py-3 rounded-lg transition flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <Loader className="w-4 h-4 animate-spin" />
                    처리 중...
                  </>
                ) : (
                  <>
                    <CheckCircle className="w-4 h-4" />
                    개인정보 마스킹 진행
                  </>
                )}
              </button>
            </form>
          </div>
        </main>
      )}

      {/* Step 2: 마스킹 확인 */}
      {step === 'masking' && (
        <main className="flex-1 max-w-4xl mx-auto w-full px-6 py-8 flex flex-col justify-center">
          <div className="bg-white rounded-2xl shadow-lg p-8 border-2 border-orange-100">
            <h2 className="text-2xl font-bold text-gray-800 mb-6">개인정보 확인</h2>
            <div className="mb-6 p-4 bg-orange-50 rounded-lg border-l-4 border-orange-400">
              <p className="text-sm text-gray-600 mb-4">다음과 같이 개인정보가 마스킹됩니다:</p>
              <div className="bg-white p-4 rounded border-2 border-orange-200 font-mono text-sm">
                {maskedText}
              </div>
            </div>
            <button
              onClick={handleConfirmMask}
              className="w-full bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 text-white font-semibold py-3 rounded-lg transition"
            >
              진행하기
            </button>
          </div>
        </main>
      )}

      {/* Step 3: 채팅 */}
      {step === 'chat' && (
        <>
          <main className="flex-1 max-w-4xl mx-auto w-full px-6 py-6 overflow-y-auto">
            <div className="space-y-4">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  style={{
                    display: 'flex',
                    justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                    marginBottom: '1rem'
                  }}
                >
                  <div
                    style={{
                      maxWidth: '70%',
                      padding: '1rem',
                      borderRadius: '0.75rem',
                      background: msg.role === 'user' ? '#fed7aa' : '#f5f5f5',
                      color: msg.role === 'user' ? '#92400e' : '#374151',
                      wordWrap: 'break-word',
                      whiteSpace: 'pre-wrap',
                      lineHeight: '1.6'
                    }}
                  >
                    {msg.content}
                  </div>
                </div>
              ))}
              {loading && (
                <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
                  <div
                    style={{
                      padding: '1rem',
                      borderRadius: '0.75rem',
                      background: '#f5f5f5',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                      boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                      border: '1px solid #fed7aa'
                    }}
                  >
                    <Loader style={{ width: '1.25rem', height: '1.25rem', animation: 'spin 1s linear infinite', color: '#f97316', flexShrink: 0 }} />
                    <span style={{ fontSize: '0.875rem' }}>생각 중...</span>
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
                value={userInput}
                onChange={(e) => setUserInput(e.target.value)}
                placeholder="질문을 입력해 주세요..."
                disabled={loading}
                className="flex-1 px-4 py-3 border-2 border-orange-200 rounded-full focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent disabled:bg-gray-50 transition"
              />
              <button
                type="submit"
                disabled={loading || !userInput.trim()}
                className="bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 disabled:from-gray-300 disabled:to-gray-300 text-white font-semibold px-6 py-3 rounded-full transition flex items-center gap-2 shadow-md hover:shadow-lg"
              >
                <Send className="w-4 h-4" />
                <span className="hidden sm:inline">전송</span>
              </button>
            </form>
          </footer>
        </>
      )}
    </div>
  );
}
