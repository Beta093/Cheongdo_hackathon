// API 서비스 (로컬 or 배포된 백엔드 URL)
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

export const api = {
  // 데모 농장 조회
  getDemoFarm: async () => {
    const res = await fetch(`${API_BASE_URL}/farms/demo`);
    return res.json();
  },

  // 오늘의 작업 조회
  getTodayTasks: async (farmId) => {
    const res = await fetch(`${API_BASE_URL}/farms/${farmId}/today`);
    return res.json();
  },

  // SSE 채팅 (스트리밍) - 향상된 파싱
  streamChat: async (farmId, message, onChunk) => {
    try {
      const response = await fetch(`${API_BASE_URL}/farms/${farmId}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      if (!response.body) throw new Error('No response body');
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        
        // SSE 형식 파싱: "data: {...}\n\n"
        const lines = buffer.split('\n');
        
        for (let i = 0; i < lines.length - 1; i++) {
          const line = lines[i].trim();
          
          if (line.startsWith('data: ')) {
            try {
              const jsonStr = line.substring(6); // "data: " 제거
              const data = JSON.parse(jsonStr);
              
              // 메시지 콘텐츠 추출
              if (data.type === 'message' && data.content) {
                onChunk(data.content);
              }
            } catch (e) {
              console.error('JSON 파싱 오류:', e);
            }
          }
        }
        
        // 마지막 불완전한 라인은 버퍼에 유지
        buffer = lines[lines.length - 1];
      }
    } catch (error) {
      console.error('Chat API 오류:', error);
      throw error;
    }
  },

  // 제안 목록
  getProposals: async (farmId) => {
    const res = await fetch(`${API_BASE_URL}/proposals`);
    return res.json();
  },

  // 제안 승인
  approveProposal: async (proposalId) => {
    const res = await fetch(`${API_BASE_URL}/proposals/${proposalId}/approve`, {
      method: 'POST'
    });
    return res.json();
  },

  // 캘린더
  getCalendar: async (farmId) => {
    const res = await fetch(`${API_BASE_URL}/farms/${farmId}/calendar`);
    return res.json();
  }
};
