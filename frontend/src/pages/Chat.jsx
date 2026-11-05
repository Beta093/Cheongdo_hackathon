import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { Send, ArrowLeft, Loader, AlertCircle, CheckCircle, Upload, X } from 'lucide-react';

export default function Chat() {
  const navigate = useNavigate();
  
  // Step 관리
  const [step, setStep] = useState('chat');  // input → masking → chat
  
  // Step 1: 입력
  const [userInput, setUserInput] = useState('');
  
  // Step 2: 마스킹
  const [maskedText, setMaskedText] = useState('');
  const [maskToken, setMaskToken] = useState('');
  
  // 대화
  const [messages, setMessages] = useState([
    {
      id: 1,
      role: 'assistant',
      content: '안녕하세요! 감잡아 AI 어드바이저입니다. 🍊\n\n감 재배에 관해 궁금한 점이나 문제가 있으시면 편하게 물어봐주세요!'
    }
  ]);
  
  // UI 상태
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedImage, setSelectedImage] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Step 1: 마스킹 요청
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

  // Step 2: 마스킹 확인 → 채팅
  const handleConfirmMask = () => {
    setStep('chat');
    setError(null);
  };

  // Step 3: 채팅 메시지 전송
  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!userInput.trim() && !selectedImage) return;

    const userMessage = {
      id: messages.length + 1,
      role: 'user',
      content: userInput,
      image: imagePreview
    };
    setMessages((prev) => [...prev, userMessage]);
    setUserInput('');
    setSelectedImage(null);
    setImagePreview(null);
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
      
      if (selectedImage) {
        // 이미지 업로드
        const formData = new FormData();
        formData.append('message', userInput || '이 사진을 분석해주세요');
        formData.append('image', selectedImage);
        
        const response = await fetch('http://localhost:8001/api/farms/demo/chat-image', {
          method: 'POST',
          body: formData
        });

        if (!response.ok) {
          throw new Error('이미지 전송 실패');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const json = JSON.parse(line.slice(6));
                if (json.type === 'message') {
                  fullResponse += json.content;
                  setMessages((prev) => [
                    ...prev.slice(0, -1),
                    { ...assistantMessage, content: fullResponse }
                  ]);
                }
              } catch (e) {
                // JSON 파싱 실패 무시
              }
            }
          }
        }
      } else {
        // 텍스트만 전송
        await api.streamChat('demo', userInput, (chunk) => {
          fullResponse += chunk;
          setMessages((prev) => [
            ...prev.slice(0, -1),
            { ...assistantMessage, content: fullResponse }
          ]);
        });
      }

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

  // 이미지 선택 처리
  const handleImageSelect = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // 파일 크기 확인 (5MB 이하)
    if (file.size > 5 * 1024 * 1024) {
      setError('이미지 크기는 5MB 이하여야 합니다');
      return;
    }

    setSelectedImage(file);
    
    // 미리보기
    const reader = new FileReader();
    reader.onload = (event) => {
      setImagePreview(event.target.result);
    };
    reader.readAsDataURL(file);
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
              <span className="text-sm text-orange-600 font-semibold">💡 팁: 개인정보가 포함되어 있으면 자동으로 마스킹됩니다.</span>
            </p>

            <form onSubmit={handleMask} className="space-y-4">
              <textarea
                value={userInput}
                onChange={(e) => setUserInput(e.target.value)}
                maxLength={4000}
                placeholder="예: '5월에 감 적과를 해야 하는데, 어떻게 하는지 알려줄래?'"
                className="w-full h-40 p-4 border-2 border-orange-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent resize-none"
              />
              <div className="flex justify-between items-center">
                <p className="text-sm text-gray-500">{userInput.length}/4000자</p>
                <button
                  type="submit"
                  disabled={loading || !userInput.trim()}
                  className="flex items-center gap-2 px-8 py-3 bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 disabled:from-gray-300 disabled:to-gray-300 text-white font-semibold rounded-lg transition"
                >
                  {loading ? <Loader className="w-5 h-5 animate-spin" /> : <CheckCircle className="w-5 h-5" />}
                  {loading ? '처리 중...' : '입력 분석'}
                </button>
              </div>
            </form>
          </div>
        </main>
      )}

      {/* Step 2: 마스킹 확인 화면 */}
      {step === 'masking' && (
        <main className="flex-1 max-w-4xl mx-auto w-full px-6 py-8 flex flex-col justify-center">
          <div className="bg-white rounded-2xl shadow-lg p-8 border-2 border-orange-100">
            <div className="mb-6 flex items-center gap-3">
              <CheckCircle className="w-6 h-6 text-green-600" />
              <h2 className="text-2xl font-bold text-gray-800">개인정보 마스킹 완료</h2>
            </div>

            <p className="text-gray-600 mb-6">
              다음과 같이 개인정보가 마스킹되었습니다. 확인 후 진행해주세요.
            </p>

            <div className="bg-gray-50 border-2 border-gray-200 rounded-lg p-6 mb-6 max-h-60 overflow-y-auto">
              <p className="text-gray-700 whitespace-pre-wrap leading-relaxed font-mono text-sm">
                {maskedText}
              </p>
            </div>

            <div className="space-y-3">
              <p className="text-sm text-orange-600 font-semibold">
                ✅ 마스킹된 항목:
              </p>
              <div className="bg-orange-50 rounded-lg p-4 text-sm text-gray-700 space-y-1">
                <p>• [이름], [주민번호], [전화번호], [이메일], [주소] 등 개인정보</p>
                <p>• 해당 정보는 AI에 전달되지 않습니다</p>
              </div>
            </div>

            <div className="flex gap-4 mt-8">
              <button
                onClick={() => {
                  setStep('input');
                  setError(null);
                }}
                className="flex-1 px-6 py-3 border-2 border-orange-300 text-orange-600 font-semibold rounded-lg hover:bg-orange-50 transition"
              >
                ← 다시 입력
              </button>
              <button
                onClick={handleConfirmMask}
                className="flex-1 px-6 py-3 bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 text-white font-semibold rounded-lg transition flex items-center justify-center gap-2"
              >
                <CheckCircle className="w-5 h-5" />
                확인하고 진행 →
              </button>
            </div>
          </div>
        </main>
      )}

      {/* Step 3: 채팅 화면 */}
      {step === 'chat' && (
        <>
          <main style={{ flex: 1, maxWidth: '56rem', margin: '0 auto', width: '100%', padding: '2rem 1rem', overflowY: 'auto' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  style={{
                    display: 'flex',
                    justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start'
                  }}
                >
                  <div
                    style={{
                      maxWidth: msg.role === 'user' ? '28rem' : '28rem',
                      padding: '1rem 1.25rem',
                      borderRadius: '1rem',
                      background: msg.role === 'user' 
                        ? 'linear-gradient(to right, #f97316, #ea580c)' 
                        : 'white',
                      color: msg.role === 'user' ? 'white' : '#374151',
                      boxShadow: msg.role === 'user' 
                        ? '0 10px 15px -3px rgba(0, 0, 0, 0.1)'
                        : '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                      border: msg.role === 'user' ? 'none' : '1px solid #fed7aa'
                    }}
                  >
                    {/* 이미지 표시 */}
                    {msg.image && (
                      <div style={{ marginBottom: '0.75rem' }}>
                        <img 
                          src={msg.image} 
                          alt="업로드된 이미지"
                          style={{
                            maxWidth: '100%',
                            maxHeight: '200px',
                            borderRadius: '0.5rem',
                            display: 'block'
                          }}
                        />
                      </div>
                    )}
                    <div style={{ fontSize: '0.875rem', lineHeight: 1.6, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                      {msg.role === 'user' ? (
                        msg.content
                      ) : (
                        <div>
                          {msg.content.split('\n\n').map((paragraph, idx) => (
                            <div key={idx} style={{ marginBottom: idx < msg.content.split('\n\n').length - 1 ? '0.5rem' : 0 }}>
                              {paragraph.split('\n').map((line, lineIdx) => (
                                <div key={lineIdx}>{line}</div>
                              ))}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
              {loading && (
                <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
                  <div style={{
                    background: 'white',
                    color: '#374151',
                    padding: '1rem 1.25rem',
                    borderRadius: '1rem',
                    display: 'flex',
                    gap: '0.5rem',
                    boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                    border: '1px solid #fed7aa'
                  }}>
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
            {/* 이미지 미리보기 */}
            {imagePreview && (
              <div style={{ padding: '1rem', borderBottom: '1px solid #fed7aa' }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1rem' }}>
                  <img 
                    src={imagePreview}
                    alt="미리보기"
                    style={{
                      width: '80px',
                      height: '80px',
                      borderRadius: '0.5rem',
                      objectFit: 'cover',
                      border: '2px solid #f97316'
                    }}
                  />
                  <div style={{ flex: 1 }}>
                    <p style={{ fontSize: '0.875rem', color: '#374151', marginBottom: '0.5rem' }}>
                      📁 {selectedImage?.name}
                    </p>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedImage(null);
                        setImagePreview(null);
                      }}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.5rem',
                        padding: '0.5rem 1rem',
                        background: '#fee2e2',
                        color: '#dc2626',
                        border: 'none',
                        borderRadius: '0.375rem',
                        cursor: 'pointer',
                        fontSize: '0.875rem',
                        fontWeight: '600'
                      }}
                    >
                      <X style={{ width: '16px', height: '16px' }} />
                      제거
                    </button>
                  </div>
                </div>
              </div>
            )}
            
            <form
              onSubmit={handleSendMessage}
              className="max-w-4xl mx-auto px-6 py-4 flex gap-3"
            >
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleImageSelect}
                accept="image/*"
                style={{ display: 'none' }}
              />
              
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={loading}
                style={{
                  padding: '0.75rem',
                  background: selectedImage ? '#fed7aa' : '#fef3c7',
                  border: '2px solid #f97316',
                  borderRadius: '9999px',
                  cursor: 'pointer',
                  color: '#b45309',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  transition: 'all 0.2s',
                  opacity: loading ? 0.5 : 1
                }}
                title="이미지 업로드"
              >
                <Upload style={{ width: '20px', height: '20px' }} />
              </button>

              <input
                type="text"
                value={userInput}
                onChange={(e) => setUserInput(e.target.value)}
                placeholder={selectedImage ? "이미지 분석 요청을 입력하세요..." : "질문을 입력해 주세요..."}
                disabled={loading}
                className="flex-1 px-4 py-3 border-2 border-orange-200 rounded-full focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent disabled:bg-gray-50 transition"
              />
              <button
                type="submit"
                disabled={loading || (!userInput.trim() && !selectedImage)}
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
