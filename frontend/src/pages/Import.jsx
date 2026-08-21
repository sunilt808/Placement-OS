import { useState } from 'react';
import { UploadCloud, CheckCircle } from 'lucide-react';
import { uploadExport } from '../api/client';
import toast from 'react-hot-toast';

export default function Import() {
  const [file, setFile] = useState(null);
  const [importing, setImporting] = useState(false);
  const [progress, setProgress] = useState(null);
  const [dragOver, setDragOver] = useState(false);

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files?.length) {
      setFile(e.dataTransfer.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setImporting(true);
    setProgress({ total: 'Scanning...', ai_processed: 0 });
    
    try {
      await uploadExport(file, (stats) => {
        setProgress(stats);
      });
      toast.success('Import complete!');
    } catch (e) {
      toast.error('Import failed: ' + e.message);
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="page-container fade-in">
      <div className="page-header">
        <h1 className="page-title">Historical Import</h1>
        <p className="page-subtitle">Upload your Telegram chat export (JSON preferred) to analyze past opportunities.</p>
      </div>

      <div className="card" style={{ maxWidth: 800, margin: '0 auto' }}>
        {!importing && !progress?.done ? (
          <>
            <div 
              className={`drop-zone ${dragOver ? 'drag-over' : ''}`}
              onDragOver={e => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              onClick={() => document.getElementById('file-upload').click()}
            >
              <UploadCloud size={48} style={{ color: 'var(--blue)' }} />
              <h3>{file ? file.name : 'Click or drag Telegram export here'}</h3>
              <p>Supports .json, .txt, .html</p>
              <input 
                id="file-upload" 
                type="file" 
                accept=".json,.txt,.html,.htm" 
                style={{ display: 'none' }}
                onChange={e => e.target.files?.length && setFile(e.target.files[0])}
              />
            </div>
            
            <div style={{ marginTop: 24, textAlign: 'center' }}>
              <button 
                className="btn btn-primary" 
                disabled={!file}
                onClick={handleUpload}
                style={{ width: '100%', justifyContent: 'center', padding: '12px' }}
              >
                Start Import
              </button>
            </div>
          </>
        ) : (
          <div style={{ padding: 20 }}>
            <h3 style={{ marginBottom: 24, display: 'flex', alignItems: 'center', gap: 8 }}>
              {progress?.done ? <><CheckCircle color="var(--green)" /> Import Complete</> : <><div className="spinner" style={{width:16,height:16,borderWidth:2}}/> Importing...</>}
            </h3>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <div className="card">
                <div className="text-muted" style={{ fontSize: '0.8rem', textTransform: 'uppercase', marginBottom: 4 }}>Total Messages</div>
                <div style={{ fontSize: '1.5rem', fontWeight: 700 }}>{progress?.total || 0}</div>
              </div>
              <div className="card">
                <div className="text-muted" style={{ fontSize: '0.8rem', textTransform: 'uppercase', marginBottom: 4 }}>Pre-filtered</div>
                <div style={{ fontSize: '1.5rem', fontWeight: 700 }}>{progress?.prefiltered || 0}</div>
              </div>
              <div className="card" style={{ gridColumn: '1 / -1', background: 'var(--blue-soft)', borderColor: 'rgba(79,142,247,0.3)' }}>
                <div className="text-muted" style={{ fontSize: '0.8rem', textTransform: 'uppercase', marginBottom: 4, color: 'var(--blue)' }}>AI Processed</div>
                <div style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--blue)' }}>{progress?.ai_processed || 0}</div>
                {progress?.prefiltered > 0 && !progress?.done && (
                  <div className="progress-bar" style={{ marginTop: 12 }}>
                    <div className="progress-fill" style={{ width: `${(progress.ai_processed / progress.prefiltered) * 100}%` }} />
                  </div>
                )}
              </div>
              <div className="card">
                <div className="text-muted" style={{ fontSize: '0.8rem', textTransform: 'uppercase', marginBottom: 4 }}>New Opportunities</div>
                <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--green)' }}>+{progress?.created || 0}</div>
              </div>
              <div className="card">
                <div className="text-muted" style={{ fontSize: '0.8rem', textTransform: 'uppercase', marginBottom: 4 }}>Duplicates Merged</div>
                <div style={{ fontSize: '1.5rem', fontWeight: 700 }}>{progress?.duplicates || 0}</div>
              </div>
            </div>
            
            {progress?.done && (
              <div style={{ marginTop: 24, textAlign: 'center' }}>
                <button className="btn btn-ghost" onClick={() => { setFile(null); setProgress(null); }}>
                  Upload Another File
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
