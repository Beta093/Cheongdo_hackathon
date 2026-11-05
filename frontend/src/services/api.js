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

  // SSE 채팅 (스트리밍)
  streamChat: async (farmId, message, onChunk) => {
    const response = await fetch(`${API_BASE_URL}/farms/${farmId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message })
    });

    if (!response.body) throw new Error('No response body');
    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value);
      onChunk(chunk);
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
