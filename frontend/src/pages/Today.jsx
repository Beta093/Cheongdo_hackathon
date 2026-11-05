import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { ArrowLeft, AlertCircle } from 'lucide-react';

export default function Today() {
  const [tasks, setTasks] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    const loadTasks = async () => {
      try {
        const data = await api.getTodayTasks('demo-farm');
        setTasks(data);
      } catch (error) {
        console.error('작업 로드 실패:', error);
        setError('작업을 불러올 수 없습니다.');
      } finally {
        setLoading(false);
      }
    };
    loadTasks();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="spinner"></div>
      </div>
    );
  }

  return (
    <main className="container py-8">
      <div className="hero">
        <h2 className="text-4xl font-bold mb-2">📋 오늘 할 일</h2>
        <p className="text-lg opacity-90">{new Date().toLocaleDateString('ko-KR', { weekday: 'long', month: 'long', day: 'numeric' })}</p>
      </div>

      {error ? (
        <div className="alert alert-warning rounded-xl mt-6">
          <div className="alert-icon">⚠️</div>
          <p>{error}</p>
        </div>
      ) : tasks && tasks.tasks ? (
        <div className="flex flex-col gap-4 mt-8">
          {tasks.tasks.map((task, idx) => (
            <div key={idx} className="card card-accent hover-shadow">
              <div className="flex justify-between items-start mb-3">
                <div className="flex-1">
                  <div className="flex gap-2 items-center mb-1">
                    <h3 className="text-lg font-bold text-dark">{task.task}</h3>
                    <span className={`task-priority ${
                      task.priority === 'high' ? 'high' :
                      task.priority === 'medium' ? 'medium' : 'low'
                    }`}>
                      {task.priority === 'high' ? '높음' : task.priority === 'medium' ? '중간' : '낮음'}
                    </span>
                  </div>
                  <p className="text-sm text-muted">⏰ {task.recommended_time || '오전 10시'}</p>
                </div>
              </div>

              {task.reason && (
                <p className="text-dark mb-3 leading-relaxed">{task.reason}</p>
              )}

              {task.description && (
                <div className="bg-light rounded-lg p-3 text-sm text-dark mb-3 border border-border-color">
                  <p className="font-semibold mb-2">📝 상세 정보</p>
                  <p>{task.description}</p>
                </div>
              )}

              {task.sources && task.sources.length > 0 && (
                <div className="text-xs text-muted border-t border-border-color pt-2">
                  📚 출처: {task.sources.join(', ')}
                </div>
              )}
            </div>
          ))}

          {/* 팁 */}
          <div className="alert alert-info rounded-xl">
            <div className="alert-icon">💡</div>
            <div>
              <p className="font-semibold mb-1">AI 상담하기</p>
              <p className="text-sm">각 작업에 대해 더 자세히 알고 싶다면 AI 상담 메뉴를 이용해보세요!</p>
            </div>
          </div>

          {/* 액션 버튼 */}
          <button
            onClick={() => navigate('/chat')}
            className="btn btn-primary btn-lg btn-block mt-2"
          >
            💬 AI에게 질문하기
          </button>
        </div>
      ) : (
        <div className="card text-center py-12 mt-6">
          <p className="text-2xl mb-2">✨</p>
          <p className="text-muted">데이터를 불러올 수 없습니다.</p>
        </div>
      )}
    </main>
  );
}
