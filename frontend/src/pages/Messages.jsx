import { useEffect, useMemo, useState } from 'react';
import { ChevronDown, ChevronUp, Download, ExternalLink, MessageSquareText, Search, TriangleAlert } from 'lucide-react';
import { Link } from 'react-router-dom';
import { getMessageAttachment, getMessages } from '../api/client';

const categoryLabel = (value) => (value || 'PENDING').replaceAll('_', ' ');

function formatDate(value) {
  if (!value) return 'Unknown date';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export default function Messages() {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(null);
  const [filters, setFilters] = useState({ search: '', placement_only: false, has_error: false });

  useEffect(() => {
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const data = await getMessages({ ...filters, search: filters.search || undefined, limit: 100 });
        setMessages(data.messages || []);
      } catch (error) {
        console.error('Could not load messages', error);
      } finally {
        setLoading(false);
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [filters]);

  const stats = useMemo(() => ({
    total: messages.length,
    placement: messages.filter(m => m.is_placement_related).length,
    errors: messages.filter(m => m.processing_error).length,
  }), [messages]);

  const downloadAttachment = async (message) => {
    try {
      const file = await getMessageAttachment(message._id);
      const url = URL.createObjectURL(file);
      const link = document.createElement('a');
      link.href = url;
      link.download = message.attachment_filename || 'attachment';
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Could not download attachment', error);
    }
  };

  return (
    <div className="page-container fade-in">
      <div className="page-header">
        <h1 className="page-title">Message Inbox</h1>
        <p className="page-subtitle">Audit every imported or forwarded message and see what the extractor found.</p>
      </div>

      <div className="message-stats">
        <div><span>Shown</span><strong>{stats.total}</strong></div>
        <div><span>Placement related</span><strong>{stats.placement}</strong></div>
        <div><span>Needs attention</span><strong>{stats.errors}</strong></div>
      </div>

      <div className="search-bar">
        <div className="search-input-wrap">
          <Search className="icon" />
          <input className="search-input" placeholder="Search message text…" value={filters.search}
            onChange={e => setFilters(current => ({ ...current, search: e.target.value }))} />
        </div>
        <label className="message-filter">
          <input type="checkbox" checked={filters.placement_only}
            onChange={e => setFilters(current => ({ ...current, placement_only: e.target.checked }))} />
          Placement related only
        </label>
        <label className="message-filter">
          <input type="checkbox" checked={filters.has_error}
            onChange={e => setFilters(current => ({ ...current, has_error: e.target.checked }))} />
          Extraction errors only
        </label>
      </div>

      {loading ? <div className="loading"><div className="spinner" /><span>Loading messages…</span></div> : (
        <div className="message-list">
          {messages.map(message => {
            const isExpanded = expanded === message._id;
            return (
              <article className="message-card" key={message._id}>
                <div className="message-card-top">
                  <div>
                    <div className="message-meta">
                      <span className={`message-category ${message.is_placement_related ? 'relevant' : ''}`}>
                        {categoryLabel(message.category)}
                      </span>
                      <span>{message.source || 'UNKNOWN'}</span>
                      <span>{formatDate(message.message_date)}</span>
                    </div>
                    <p className="message-preview">{message.message_text || 'No message text saved.'}</p>
                  </div>
                  <button className="btn-ghost icon-button" onClick={() => setExpanded(isExpanded ? null : message._id)}
                    aria-label={isExpanded ? 'Hide details' : 'Show details'}>
                    {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                  </button>
                </div>

                <div className="message-important">
                  <span><b>Extracted:</b> {message.is_placement_related ? 'Placement related' : 'Not placement related'}</span>
                  {message.opportunity_id && <Link to={`/opportunities/${message.opportunity_id}`}>Open opportunity <ExternalLink size={14} /></Link>}
                  {message.attachment_available && <button className="message-download" onClick={() => downloadAttachment(message)}><Download size={14} /> Source file</button>}
                  {message.processing_error && <span className="message-error"><TriangleAlert size={15} /> {message.processing_error}</span>}
                </div>

                {message.extraction && (
                  <div className="extraction-facts">
                    {message.extraction.company && <span><b>Company</b>{message.extraction.company}</span>}
                    {message.extraction.role && <span><b>Role</b>{message.extraction.role}</span>}
                    {message.extraction.ctc && <span><b>CTC</b>{message.extraction.ctc}</span>}
                    {message.extraction.deadline && <span><b>Deadline</b>{formatDate(message.extraction.deadline)}</span>}
                    {message.extraction.status && <span><b>Status</b>{message.extraction.status}</span>}
                  </div>
                )}

                {isExpanded && (
                  <div className="message-detail">
                    <h3><MessageSquareText size={18} /> Original message</h3>
                    <pre>{message.message_text}</pre>
                    <div className="message-detail-grid">
                      <span><b>Sender</b>{message.sender_name || 'Not available'}</span>
                      <span><b>Processed</b>{formatDate(message.processed_at)}</span>
                      <span><b>Attachment</b>{message.attachment_filename || 'None'}{message.attachment_text_extracted === false ? ' (scanned / no text extracted)' : ''}</span>
                      <span><b>Message ID</b>{message.telegram_message_id || 'Not available'}</span>
                    </div>
                  </div>
                )}
              </article>
            );
          })}
          {!messages.length && <div className="empty-state"><MessageSquareText size={42} /><h3>No messages found</h3><p>Import a Telegram export or forward a message to start building your inbox.</p></div>}
        </div>
      )}
    </div>
  );
}
