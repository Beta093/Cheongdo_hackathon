import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { ArrowLeft, CheckCircle2, Circle } from 'lucide-react';

export default function Calendar() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const loadEvents = async () => {
      try {
        const data = await api.getCalendar('demo-farm');
        setEvents(data.calendar_events || []);
      } catch (error) {
        console.error('캘린더 로드 실패:', error);
      } finally {
        setLoading(false);
      }
    };
    loadEvents();
  }, []);

  const handleToggleEvent = (eventId) => {
    setEvents((prev) =>
      prev.map((e) => (e.id === eventId ? { ...e, completed: !e.completed } : e))
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-gray-600">로딩 중...</p>
      </div>
    );
  }

  // 월별로 그룹핑
  const eventsByMonth = events.reduce((acc, event) => {
    const month = new Date(event.scheduled_date).toLocaleDateString('ko-KR', {
      year: 'numeric',
      month: 'long'
    });
    if (!acc[month]) acc[month] = [];
    acc[month].push(event);
    return acc;
  }, {});

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
            재배 일정
          </h1>
        </div>
      </header>

      {/* 콘텐츠 */}
      <main className="max-w-4xl mx-auto px-6 py-8">
        {events.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            <p>일정이 없습니다.</p>
          </div>
        ) : (
          <div className="space-y-8">
            {Object.entries(eventsByMonth).map(([month, monthEvents]) => (
              <div key={month}>
                <h2 className="text-xl font-bold text-gray-800 mb-4 pb-2 border-b-2 border-green-500">
                  {month}
                </h2>
                <div className="space-y-3">
                  {monthEvents.map((event) => (
                    <div
                      key={event.id}
                      className={`bg-white rounded-lg shadow p-4 flex gap-4 items-start border-l-4 ${
                        event.completed
                          ? 'border-green-500 opacity-60'
                          : 'border-orange-500'
                      }`}
                    >
                      <button
                        onClick={() => handleToggleEvent(event.id)}
                        className="mt-1 flex-shrink-0"
                      >
                        {event.completed ? (
                          <CheckCircle2 className="w-6 h-6 text-green-600" />
                        ) : (
                          <Circle className="w-6 h-6 text-gray-300 hover:text-gray-400" />
                        )}
                      </button>
                      <div className="flex-1">
                        <div className="flex justify-between items-start">
                          <div>
                            <h3
                              className={`font-semibold ${
                                event.completed
                                  ? 'text-gray-500 line-through'
                                  : 'text-gray-800'
                              }`}
                            >
                              {event.task}
                            </h3>
                            <p className="text-sm text-gray-500 mt-1">
                              {new Date(event.scheduled_date).toLocaleDateString(
                                'ko-KR'
                              )}
                            </p>
                          </div>
                          <span className="px-2 py-1 bg-orange-100 text-orange-700 text-xs font-semibold rounded">
                            {event.category || '관리'}
                          </span>
                        </div>
                        {event.description && (
                          <p className="text-sm text-gray-600 mt-2">
                            {event.description}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
