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
      <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-orange-50 to-amber-50">
        <p className="text-orange-600 font-semibold">로딩 중...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-orange-50 to-amber-50">
      {/* 헤더 */}
      <header className="bg-white shadow-sm border-b-2 border-orange-200">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center gap-4">
          <button
            onClick={() => navigate('/')}
            className="p-2 hover:bg-orange-100 rounded-lg transition text-orange-600"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <h1 className="text-2xl font-bold bg-gradient-to-r from-orange-600 to-orange-500 bg-clip-text text-transparent">
            💡 AI 제안 확인
          </h1>
        </div>
      </header>

      {/* 콘텐츠 */}
      <main className="max-w-4xl mx-auto px-6 py-8">
        {proposals.length === 0 ? (
          <div className="text-center py-12 bg-white rounded-lg shadow-sm border-2 border-orange-100">
            <p className="text-orange-600 font-semibold mb-2">📭 현재 제안이 없습니다.</p>
            <p className="text-sm text-gray-600">오늘의 일정에서 작업을 완료하면 제안이 나타납니다.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {proposals.map((proposal) => (
              <div
                key={proposal.id}
                className={`bg-white rounded-lg shadow-sm p-6 border-l-4 transition hover:shadow-md ${
                  proposal.status === 'approved'
                    ? 'border-green-500 opacity-75'
                    : 'border-orange-500'
                }`}
              >
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <h3 className="text-lg font-bold text-gray-800">
                      {proposal.task}
                    </h3>
                    <p className="text-sm text-orange-600 font-medium mt-1">
                      📍 권장 날짜: {proposal.recommended_date}
                    </p>
                  </div>
                  <span
                    className={`px-3 py-1 text-sm font-semibold rounded-full transition ${
                      proposal.status === 'approved'
                        ? 'bg-green-100 text-green-700'
                        : 'bg-orange-100 text-orange-700 border border-orange-300'
                    }`}
                  >
                    {proposal.status === 'approved' ? '✓ 승인됨' : '⏳ 대기 중'}
                  </span>
                </div>

                {proposal.reason && (
                  <p className="text-gray-700 mb-3 leading-relaxed">{proposal.reason}</p>
                )}

                {proposal.ai_generated && (
                  <div className="bg-gradient-to-r from-orange-50 to-amber-50 rounded-lg p-3 text-sm text-orange-700 mb-3 border border-orange-200">
                    🤖 <span className="font-semibold">AI가 생성한 제안</span>입니다. 검증된 영농 기술을 바탕으로 합니다.
                  </div>
                )}

                {proposal.sources && proposal.sources.length > 0 && (
                  <div className="text-xs text-gray-600 mb-4 bg-gray-50 rounded p-2 border border-gray-200">
                    📚 <span className="font-semibold">출처:</span> {proposal.sources.map((s) => s.name || s).join(', ')}
                  </div>
                )}

                {proposal.status !== 'approved' && (
                  <button
                    onClick={() => handleApprove(proposal.id)}
                    className="w-full bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 text-white font-semibold py-3 px-4 rounded-lg transition flex items-center justify-center gap-2 shadow-md hover:shadow-lg"
                  >
                    <Check className="w-5 h-5" />
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
