import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { ArrowLeft, Check, X } from 'lucide-react';

export default function Proposals() {
  const [proposals, setProposals] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const loadProposals = async () => {
      try {
        const data = await api.getProposals('demo-farm');
        setProposals(data.proposals || []);
      } catch (error) {
        console.error('제안 로드 실패:', error);
      } finally {
        setLoading(false);
      }
    };
    loadProposals();
  }, []);

  const handleApprove = async (proposalId) => {
    try {
      await api.approveProposal(proposalId);
      setProposals((prev) =>
        prev.map((p) => (p.id === proposalId ? { ...p, status: 'approved' } : p))
      );
    } catch (error) {
      console.error('제안 승인 실패:', error);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-gray-600">로딩 중...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-green-50 to-blue-50">
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
            AI 제안 확인
          </h1>
        </div>
      </header>

      {/* 콘텐츠 */}
      <main className="max-w-4xl mx-auto px-6 py-8">
        {proposals.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            <p>현재 제안이 없습니다.</p>
            <p className="text-sm">오늘의 일정에서 작업을 완료하면 제안이 나타납니다.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {proposals.map((proposal) => (
              <div
                key={proposal.id}
                className={`bg-white rounded-lg shadow p-6 border-l-4 ${
                  proposal.status === 'approved'
                    ? 'border-green-500 opacity-75'
                    : 'border-purple-500'
                }`}
              >
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <h3 className="text-lg font-bold text-gray-800">
                      {proposal.task}
                    </h3>
                    <p className="text-sm text-gray-500 mt-1">
                      권장 날짜: {proposal.recommended_date}
                    </p>
                  </div>
                  <span
                    className={`px-3 py-1 text-sm font-semibold rounded-full ${
                      proposal.status === 'approved'
                        ? 'bg-green-100 text-green-700'
                        : 'bg-yellow-100 text-yellow-700'
                    }`}
                  >
                    {proposal.status === 'approved' ? '✓ 승인됨' : '대기 중'}
                  </span>
                </div>

                {proposal.reason && (
                  <p className="text-gray-700 mb-3">{proposal.reason}</p>
                )}

                {proposal.ai_generated && (
                  <div className="bg-purple-50 rounded p-3 text-sm text-purple-700 mb-3">
                    🤖 AI가 생성한 제안입니다.
                  </div>
                )}

                {proposal.sources && proposal.sources.length > 0 && (
                  <div className="text-xs text-gray-500 mb-4">
                    📚 출처: {proposal.sources.map((s) => s.name || s).join(', ')}
                  </div>
                )}

                {proposal.status !== 'approved' && (
                  <button
                    onClick={() => handleApprove(proposal.id)}
                    className="w-full bg-purple-600 hover:bg-purple-700 text-white font-semibold py-2 px-4 rounded-lg transition flex items-center justify-center gap-2"
                  >
                    <Check className="w-4 h-4" />
                    이 제안 수용하기
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
