import React, { useState, useRef, useEffect } from 'react';
import { MessageCircle, Send, AlertTriangle, CheckCircle2, Loader2, ChevronRight } from 'lucide-react';

/**
 * ChatIntake — Patient-facing chatbot for minimum-questions intake.
 * Design: soft blue #edf4fa, rounded cards, pill buttons (matches existing design system).
 *
 * Props:
 *   visit       — { visit_id, patient_id }
 *   patientToken — bearer token for API auth
 *   onComplete  — called with structured_intake when done
 *   onFallback  — called with no args to switch to the existing form
 */
export default function ChatIntake({ visit, patientToken, onComplete, onFallback }) {
  const [messages, setMessages] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [inputText, setInputText] = useState('');
  const [quickReplies, setQuickReplies] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isDone, setIsDone] = useState(false);
  const [isEmergency, setIsEmergency] = useState(false);
  const [error, setError] = useState(null);
  const [questionNumber, setQuestionNumber] = useState(0);
  const [maxQuestions, setMaxQuestions] = useState(6);
  const [started, setStarted] = useState(false);

  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  // Auto-scroll to bottom when messages update
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const headers = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${patientToken}`,
  };

  const startSession = async () => {
    setIsLoading(true);
    setError(null);
    setStarted(true);
    try {
      const res = await fetch('/api/chat/start', { method: 'POST', headers });
      if (!res.ok) throw new Error('Failed to start chat session');
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      setSessionId(data.session_id);
      setMaxQuestions(data.max_questions || 6);
      setQuestionNumber(data.question_number || 1);
      setQuickReplies(data.quick_replies || []);
      setMessages([{ role: 'assistant', content: data.question, id: Date.now() }]);
    } catch (err) {
      console.warn('[ChatIntake] Start failed:', err);
      // Silent fallback to existing form
      onFallback && onFallback();
    } finally {
      setIsLoading(false);
    }
  };

  const sendMessage = async (text) => {
    if (!text.trim() || isSending || isDone) return;
    const userMsg = { role: 'patient', content: text, id: Date.now() };
    setMessages(prev => [...prev, userMsg]);
    setInputText('');
    setQuickReplies([]);
    setIsSending(true);
    setError(null);

    try {
      const res = await fetch('/api/chat/message', {
        method: 'POST',
        headers,
        body: JSON.stringify({ session_id: sessionId, message: text }),
      });
      const data = await res.json();

      if (data.emergency) {
        setIsEmergency(true);
        setIsDone(true);
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: data.message || 'Please tell the nurse right now.',
          id: Date.now(),
          isEmergency: true,
        }]);
        return;
      }

      if (data.done) {
        setIsDone(true);
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: data.message || 'Thank you! Your information has been saved.',
          id: Date.now(),
          isDone: true,
        }]);
        onComplete && onComplete(data.structured_intake || {});
        return;
      }

      if (data.question) {
        setQuestionNumber(data.question_number || questionNumber + 1);
        setQuickReplies(data.quick_replies || []);
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: data.question,
          id: Date.now(),
        }]);
      }
    } catch (err) {
      console.error('[ChatIntake] Message send failed:', err);
      setError('Could not connect. Please check your connection and try again.');
    } finally {
      setIsSending(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    sendMessage(inputText);
  };

  const handleQuickReply = (reply) => {
    sendMessage(reply);
  };

  // ---- Render: not started yet ----
  if (!started) {
    return (
      <div style={styles.container}>
        <div style={styles.card}>
          <div style={styles.headerRow}>
            <MessageCircle size={22} color="#2563eb" />
            <span style={styles.headerTitle}>Quick Check-In Chat</span>
          </div>
          <p style={styles.intro}>
            Answer a few short questions to help the doctor prepare for your visit.
            This takes about 2 minutes.
          </p>
          <button style={styles.startBtn} onClick={startSession}>
            Start <ChevronRight size={16} style={{ marginLeft: 4 }} />
          </button>
          {onFallback && (
            <button style={styles.linkBtn} onClick={onFallback}>
              Fill out the form instead
            </button>
          )}
        </div>
      </div>
    );
  }

  // ---- Render: loading first question ----
  if (isLoading) {
    return (
      <div style={styles.container}>
        <div style={{ ...styles.card, alignItems: 'center', padding: '32px 16px' }}>
          <Loader2 size={28} color="#2563eb" style={{ animation: 'spin 1s linear infinite' }} />
          <p style={{ color: '#64748b', marginTop: 12 }}>Starting your check-in…</p>
        </div>
      </div>
    );
  }

  // ---- Render: chat ----
  return (
    <div style={styles.container}>
      {/* Progress indicator */}
      {!isDone && (
        <div style={styles.progress}>
          <span style={styles.progressText}>
            Question {questionNumber} of up to {maxQuestions}
          </span>
          <div style={styles.progressBar}>
            <div
              style={{
                ...styles.progressFill,
                width: `${Math.min(100, (questionNumber / maxQuestions) * 100)}%`,
              }}
            />
          </div>
        </div>
      )}

      {/* Messages */}
      <div style={styles.messageList}>
        {messages.map((msg) => (
          <div
            key={msg.id}
            style={msg.role === 'patient' ? styles.patientMsg : styles.assistantMsg}
          >
            {msg.isEmergency && (
              <div style={styles.emergencyBanner}>
                <AlertTriangle size={18} color="#dc2626" style={{ marginRight: 6 }} />
                {msg.content}
              </div>
            )}
            {msg.isDone && (
              <div style={styles.doneBanner}>
                <CheckCircle2 size={18} color="#16a34a" style={{ marginRight: 6 }} />
                {msg.content}
              </div>
            )}
            {!msg.isEmergency && !msg.isDone && (
              <div style={msg.role === 'patient' ? styles.patientBubble : styles.assistantBubble}>
                {msg.content}
              </div>
            )}
          </div>
        ))}

        {/* Typing indicator */}
        {isSending && (
          <div style={styles.assistantMsg}>
            <div style={styles.typingIndicator}>
              <span style={styles.dot} />
              <span style={{ ...styles.dot, animationDelay: '0.15s' }} />
              <span style={{ ...styles.dot, animationDelay: '0.3s' }} />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Quick reply pills */}
      {!isDone && quickReplies.length > 0 && (
        <div style={styles.quickReplies}>
          {quickReplies.map((reply, i) => (
            <button
              key={i}
              style={styles.quickReplyBtn}
              onClick={() => handleQuickReply(reply)}
              disabled={isSending}
            >
              {reply}
            </button>
          ))}
        </div>
      )}

      {/* Text input */}
      {!isDone && (
        <form style={styles.inputRow} onSubmit={handleSubmit}>
          <input
            ref={inputRef}
            style={styles.textInput}
            type="text"
            value={inputText}
            onChange={e => setInputText(e.target.value)}
            placeholder="Type your answer…"
            maxLength={1000}
            disabled={isSending}
            autoComplete="off"
          />
          <button
            type="submit"
            style={styles.sendBtn}
            disabled={isSending || !inputText.trim()}
          >
            <Send size={18} />
          </button>
        </form>
      )}

      {error && <p style={styles.errorText}>{error}</p>}

      {/* Fallback link */}
      {!isDone && onFallback && (
        <button style={styles.linkBtn} onClick={onFallback}>
          Switch to the intake form instead
        </button>
      )}
    </div>
  );
}

// ---- Inline styles (matches existing soft-blue design system) ----
const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
    maxWidth: 520,
    margin: '0 auto',
  },
  card: {
    background: '#fff',
    borderRadius: 20,
    padding: '24px 20px',
    boxShadow: '0 2px 12px rgba(0,0,0,0.07)',
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
  },
  headerRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: 700,
    color: '#1e293b',
  },
  intro: {
    fontSize: 14,
    color: '#475569',
    lineHeight: 1.5,
    margin: 0,
  },
  startBtn: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: '#2563eb',
    color: '#fff',
    border: 'none',
    borderRadius: 9999,
    padding: '12px 28px',
    fontSize: 15,
    fontWeight: 600,
    cursor: 'pointer',
    alignSelf: 'flex-start',
  },
  linkBtn: {
    background: 'none',
    border: 'none',
    color: '#64748b',
    fontSize: 13,
    cursor: 'pointer',
    textDecoration: 'underline',
    padding: 0,
    marginTop: 4,
  },
  progress: {
    background: '#fff',
    borderRadius: 12,
    padding: '10px 16px',
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
    boxShadow: '0 1px 6px rgba(0,0,0,0.05)',
  },
  progressText: {
    fontSize: 12,
    color: '#64748b',
  },
  progressBar: {
    height: 4,
    background: '#e2e8f0',
    borderRadius: 2,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    background: '#2563eb',
    borderRadius: 2,
    transition: 'width 0.4s ease',
  },
  messageList: {
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
    minHeight: 200,
    maxHeight: 400,
    overflowY: 'auto',
    padding: '8px 4px',
  },
  assistantMsg: {
    display: 'flex',
    justifyContent: 'flex-start',
  },
  patientMsg: {
    display: 'flex',
    justifyContent: 'flex-end',
  },
  assistantBubble: {
    background: '#fff',
    border: '1px solid #e2e8f0',
    borderRadius: '18px 18px 18px 4px',
    padding: '12px 16px',
    maxWidth: '82%',
    fontSize: 14,
    color: '#1e293b',
    lineHeight: 1.5,
    boxShadow: '0 1px 4px rgba(0,0,0,0.05)',
  },
  patientBubble: {
    background: '#2563eb',
    borderRadius: '18px 18px 4px 18px',
    padding: '12px 16px',
    maxWidth: '82%',
    fontSize: 14,
    color: '#fff',
    lineHeight: 1.5,
  },
  emergencyBanner: {
    display: 'flex',
    alignItems: 'center',
    background: '#fef2f2',
    border: '1.5px solid #fca5a5',
    borderRadius: 14,
    padding: '12px 16px',
    fontSize: 15,
    fontWeight: 700,
    color: '#dc2626',
    maxWidth: '90%',
  },
  doneBanner: {
    display: 'flex',
    alignItems: 'center',
    background: '#f0fdf4',
    border: '1.5px solid #86efac',
    borderRadius: 14,
    padding: '12px 16px',
    fontSize: 14,
    fontWeight: 600,
    color: '#16a34a',
    maxWidth: '90%',
  },
  typingIndicator: {
    display: 'flex',
    gap: 5,
    padding: '14px 18px',
    background: '#fff',
    borderRadius: '18px 18px 18px 4px',
    border: '1px solid #e2e8f0',
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: '50%',
    background: '#94a3b8',
    display: 'inline-block',
    animation: 'bounce 0.9s infinite',
  },
  quickReplies: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 8,
    paddingTop: 4,
  },
  quickReplyBtn: {
    background: '#edf4fa',
    border: '1px solid #bfdbfe',
    borderRadius: 9999,
    padding: '8px 16px',
    fontSize: 13,
    color: '#1e40af',
    cursor: 'pointer',
    fontWeight: 500,
    transition: 'background 0.15s',
  },
  inputRow: {
    display: 'flex',
    gap: 10,
    alignItems: 'center',
  },
  textInput: {
    flex: 1,
    border: '1.5px solid #cbd5e1',
    borderRadius: 9999,
    padding: '12px 18px',
    fontSize: 14,
    color: '#1e293b',
    outline: 'none',
    background: '#fff',
  },
  sendBtn: {
    background: '#2563eb',
    border: 'none',
    borderRadius: '50%',
    width: 44,
    height: 44,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#fff',
    cursor: 'pointer',
    flexShrink: 0,
  },
  errorText: {
    color: '#dc2626',
    fontSize: 13,
    textAlign: 'center',
    margin: 0,
  },
};
