import { useState } from 'react';
import { MessageCircle, X } from 'lucide-react';

const questions = {
  intake: 'How do patients complete intake?',
  reports: 'How do patients upload reports?',
  queue: 'How do staff use the queue?',
  records: 'Where are patient records?',
};

export default function WorkflowChat({ apiFetch }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [pending, setPending] = useState(false);

  async function ask(topic) {
    setMessages((previous) => [...previous, questions[topic]]);
    setPending(true);
    try {
      const response = await apiFetch('/api/workflow-chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic }),
      });
      if (!response.ok) throw new Error('Workflow help unavailable');
      const { answer, source } = await response.json();
      setMessages((previous) => [...previous, { answer, source }]);
    } catch {
      setMessages((previous) => [...previous, { answer: 'Help is unavailable. Try again in a moment.' }]);
    } finally {
      setPending(false);
    }
  }

  return (
    <aside className="workflow-chat" aria-label="Workflow help">
      {open && (
        <section className="card workflow-chat-panel">
          <h2>Workflow help</h2>
          <div className="workflow-chat-messages" role="log" aria-live="polite">
            {messages.map((message, index) => typeof message === 'string'
              ? <p key={index} className="workflow-chat-question">{message}</p>
              : <p key={index}>{message.source && <strong>{message.source === 'gemini' ? 'Gemini' : 'Chakshu guide'}</strong>}{message.answer}</p>)}
            {pending && <p>Getting an answer…</p>}
          </div>
          {Object.entries(questions).map(([topic, question]) => (
            <button key={topic} type="button" className="btn-secondary" disabled={pending} onClick={() => ask(topic)}>{question}</button>
          ))}
        </section>
      )}
      <button type="button" className="btn-primary" aria-expanded={open} onClick={() => setOpen(!open)}>
        {open ? <X size={18} /> : <MessageCircle size={18} />}
        {open ? 'Close help' : 'Workflow help'}
      </button>
    </aside>
  );
}
