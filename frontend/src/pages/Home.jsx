import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { Sprout, Settings } from 'lucide-react';

export default function Home() {
  const [farm, setFarm] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const loadFarm = async () => {
      try {
        const demoFarm = await api.getDemoFarm();
        setFarm(demoFarm);
      } catch (error) {
        console.error('농장 정보 로드 실패:', error);
      } finally {
        setLoading(false);
      }
    };
    loadFarm();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="spinner mb-4 mx-auto"></div>
          <p className="text-light">농장 정보 로딩 중...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-bg">
      {/* 헤더 */}
      <header className="bg-white shadow-md sticky top-16 z-40">
        <div className="container flex justify-between items-center py-3">
          <div className="flex items-center gap-2">
            <span className="text-3xl">🍊</span>
            <div>
              <h1 className="text-2xl font-bold text-primary">감잡아</h1>
              <p className="text-xs text-muted">AI 영농 어드바이저</p>
            </div>
          </div>
          <button className="p-2 hover:bg-light rounded-lg transition">
            <Settings className="w-5 h-5 text-primary" />
          </button>
        </div>
      </header>

      {/* 메인 콘텐츠 */}
      <main className="container py-8">
        {farm && (
          <div className="flex flex-col gap-8">
            {/* 히로 섹션 */}
            <div className="hero text-center">
              <h2 className="text-4xl font-bold mb-2">🌿 {farm.name || '데모 농장'}</h2>
              <p className="text-lg opacity-90">감 재배의 모든 것을 AI와 함께 해결하세요</p>
            </div>

            {/* 농장 정보 카드 */}
            <div className="card card-accent">
              <div className="card-header">
                <h3 className="card-title">농장 정보</h3>
              </div>
              <div className="grid grid-2 gap-4">
                <div className="p-3 bg-light rounded-lg">
                  <p className="text-sm text-muted mb-1">📍 위치</p>
                  <p className="font-semibold text-dark">{farm.location || '청도'}</p>
                </div>
                <div className="p-3 bg-light rounded-lg">
                  <p className="text-sm text-muted mb-1">🌾 품종</p>
                  <p className="font-semibold text-dark">{farm.variety || '청도반시'}</p>
                </div>
                <div className="p-3 bg-light rounded-lg">
                  <p className="text-sm text-muted mb-1">📅 재배 연수</p>
                  <p className="font-semibold text-dark">{farm.tree_age_years || 5}년</p>
                </div>
                <div className="p-3 bg-light rounded-lg">
                  <p className="text-sm text-muted mb-1">📐 면적</p>
                  <p className="font-semibold text-dark">{farm.area_m2 || 3000}㎡</p>
                </div>
              </div>
            </div>

            {/* 액션 버튼들 */}
            <div className="grid grid-2">
              <button
                onClick={() => navigate('/today')}
                className="card hover-shadow cursor-pointer transition group"
              >
                <div className="text-4xl mb-3 group-hover:scale-110 transition">📋</div>
                <h3 className="font-bold text-dark mb-1">오늘 할 일</h3>
                <p className="text-sm text-muted">우선순위별 작업 목록</p>
              </button>

              <button
                onClick={() => navigate('/chat')}
                className="card hover-shadow cursor-pointer transition group"
              >
                <div className="text-4xl mb-3 group-hover:scale-110 transition">💬</div>
                <h3 className="font-bold text-dark mb-1">AI 상담</h3>
                <p className="text-sm text-muted">AI와 실시간 채팅</p>
              </button>

              <button
                onClick={() => navigate('/proposals')}
                className="card hover-shadow cursor-pointer transition group"
              >
                <div className="text-4xl mb-3 group-hover:scale-110 transition">✨</div>
                <h3 className="font-bold text-dark mb-1">AI 제안</h3>
                <p className="text-sm text-muted">맞춤 영농 제안</p>
              </button>

              <button
                onClick={() => navigate('/calendar')}
                className="card hover-shadow cursor-pointer transition group"
              >
                <div className="text-4xl mb-3 group-hover:scale-110 transition">📅</div>
                <h3 className="font-bold text-dark mb-1">일정 계획</h3>
                <p className="text-sm text-muted">월별 작업 캘린더</p>
              </button>
            </div>

            {/* 팁 */}
            <div className="alert alert-info rounded-xl">
              <div className="alert-icon">ℹ️</div>
              <div>
                <p className="font-semibold mb-1">AI 감잡아를 활용하세요!</p>
                <p className="text-sm">영농 관련 질문, 병충해 진단, 일정 관리 등 모든 것을 AI와 함께 처리할 수 있습니다.</p>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
