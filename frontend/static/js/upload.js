// OCR Pipeline Frontend JavaScript

const API_BASE = '/api';

// DOM Elements - will be initialized after DOM loads
let uploadArea;
let fileInput;
let uploadButton;
let uploadProgress;
let progressFill;
let progressText;
let documentsList;
let statusFilter;
let refreshBtn;
let documentModal;
let closeModal;
let modalTitle;
let modalBody;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Initialize DOM elements
    uploadArea = document.getElementById('uploadArea');
    fileInput = document.getElementById('fileInput');
    uploadButton = document.getElementById('uploadButton');
    uploadProgress = document.getElementById('uploadProgress');
    progressFill = document.getElementById('progressFill');
    progressText = document.getElementById('progressText');
    documentsList = document.getElementById('documentsList');
    statusFilter = document.getElementById('statusFilter');
    refreshBtn = document.getElementById('refreshBtn');
    documentModal = document.getElementById('documentModal');
    closeModal = document.getElementById('closeModal');
    modalTitle = document.getElementById('modalTitle');
    modalBody = document.getElementById('modalBody');
    
    // Debug: Check if elements exist
    console.log('Initialized elements:', {
        uploadArea: !!uploadArea,
        fileInput: !!fileInput,
        uploadButton: !!uploadButton
    });
    
    loadDocuments();
    
    // Upload button click - primary method
    if (uploadButton) {
        uploadButton.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            console.log('Upload button clicked');
            if (fileInput) {
                console.log('File input found, triggering click');
                fileInput.click();
            } else {
                console.error('File input not found!');
            }
        });
    } else {
        console.error('Upload button not found!');
    }
    
    // Upload area click - fallback
    if (uploadArea) {
        uploadArea.addEventListener('click', (e) => {
            // Only trigger if not clicking on button
            if (uploadButton && !uploadButton.contains(e.target) && e.target !== uploadButton) {
                if (fileInput) {
                    fileInput.click();
                }
            }
        });
    }
    
    // File input change
    if (fileInput) {
        fileInput.addEventListener('change', handleFileSelect);
    }
    
    // Drag and drop
    if (uploadArea) {
        uploadArea.addEventListener('dragover', handleDragOver);
        uploadArea.addEventListener('dragleave', handleDragLeave);
        uploadArea.addEventListener('drop', handleDrop);
    }
    
    // Filter change
    statusFilter.addEventListener('change', loadDocuments);
    
    // Refresh button
    refreshBtn.addEventListener('click', loadDocuments);
    
    // Modal close
    closeModal.addEventListener('click', () => {
        documentModal.style.display = 'none';
    });
    
    window.addEventListener('click', (e) => {
        if (e.target === documentModal) {
            documentModal.style.display = 'none';
        }
    });
    
    // Auto-refresh for processing documents (only when needed)
    setInterval(() => {
        // Only refresh if we have processing/pending documents
        const hasProcessingDocs = Array.from(document.querySelectorAll('.document-card'))
            .some(card => card.classList.contains('processing') || card.classList.contains('pending'));

        if (hasProcessingDocs) {
            loadDocuments();
        }
    }, 5000); // Refresh every 5 seconds
});

// File handling
function handleDragOver(e) {
    e.preventDefault();
    uploadArea.classList.add('dragover');
}

function handleDragLeave(e) {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
}

function handleDrop(e) {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        uploadFiles(Array.from(files));
    }
}

function handleFileSelect(e) {
    const files = e.target.files;
    if (files.length > 0) {
        uploadFiles(Array.from(files));
    }
}

async function uploadFiles(files) {
    for (const file of files) {
        await uploadFile(file);
    }
}

async function uploadFile(file) {
    if (!uploadProgress || !progressFill || !progressText) {
        console.error('Upload elements not initialized');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    
    uploadProgress.style.display = 'block';
    progressFill.style.width = '0%';
    progressText.textContent = `Uploading ${file.name}...`;
    
    let jobId = null;
    let documentId = null;
    
    try {
        // Create AbortController for timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 60000); // 60 second timeout
        
        const response = await fetch(`${API_BASE}/upload`, {
            method: 'POST',
            body: formData,
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Upload failed: ${response.status} ${errorText}`);
        }
        
        const data = await response.json();
        jobId = data.job_id;
        documentId = data.document_id;
        
        progressFill.style.width = '100%';
        progressText.textContent = `Uploaded successfully! Processing... (Job ID: ${jobId})`;
        
        // Refresh document list immediately to show new document as pending
        loadDocuments();
        
        // Start polling for this specific job
        if (jobId) {
            pollJobStatus(jobId, documentId, file.name);
        } else {
            // Fallback: just reload documents after 2 seconds
            setTimeout(() => {
                uploadProgress.style.display = 'none';
                loadDocuments();
            }, 2000);
        }
        
    } catch (error) {
        if (error.name === 'AbortError') {
            progressText.textContent = `Upload timeout: Server took too long to respond`;
        } else {
            progressText.textContent = `Error: ${error.message}`;
        }
        progressFill.style.background = '#f44336';
        setTimeout(() => {
            uploadProgress.style.display = 'none';
            progressFill.style.background = 'linear-gradient(90deg, #667eea, #764ba2)';
            progressFill.style.width = '0%';
        }, 5000);
    }
}

// Poll job status for a specific upload
async function pollJobStatus(jobId, documentId, filename) {
    let pollCount = 0;
    let errorCount = 0;
    const maxPolls = 120; // 10 minutes max (120 * 5 seconds)
    const maxErrors = 5;  // Stop after 5 consecutive errors

    const pollInterval = setInterval(async () => {
        pollCount++;

        try {
            const response = await fetch(`${API_BASE}/status/${jobId}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const statusData = await response.json();
            const status = statusData.status;
            const currentStage = statusData.current_stage;

            // Reset error count on successful request
            errorCount = 0;

            // Update progress based on status
            if (status === 'processing') {
                const stageInfo = getStageInfo(currentStage);
                const progressPercent = getProgressPercent(currentStage);
                progressFill.style.width = `${progressPercent}%`;
                progressText.textContent = `${stageInfo.label} ${filename}...`;
            } else if (status === 'completed') {
                progressFill.style.width = '100%';
                progressFill.style.background = '#4caf50';
                progressText.textContent = `✓ Processing completed!`;
                clearInterval(pollInterval);

                // Reload and hide progress
                setTimeout(() => {
                    uploadProgress.style.display = 'none';
                    progressFill.style.background = 'linear-gradient(90deg, #667eea, #764ba2)';
                    progressFill.style.width = '0%';
                    loadDocuments();
                }, 2000);

            } else if (status === 'failed') {
                progressFill.style.width = '100%';
                progressFill.style.background = '#f44336';
                const errorMsg = statusData.error_message || 'Unknown error';
                progressText.textContent = `✗ Failed: ${errorMsg.substring(0, 100)}`;
                clearInterval(pollInterval);

                setTimeout(() => {
                    uploadProgress.style.display = 'none';
                    progressFill.style.background = 'linear-gradient(90deg, #667eea, #764ba2)';
                    progressFill.style.width = '0%';
                    loadDocuments();
                }, 5000);
            }

            // Stop polling if max polls reached
            if (pollCount >= maxPolls) {
                clearInterval(pollInterval);
                progressFill.style.width = '100%';
                progressFill.style.background = '#ff9800';
                progressText.textContent = `Processing taking longer than expected. Check document list.`;
                setTimeout(() => {
                    uploadProgress.style.display = 'none';
                    progressFill.style.background = 'linear-gradient(90deg, #667eea, #764ba2)';
                    progressFill.style.width = '0%';
                    loadDocuments();
                }, 5000);
            }

        } catch (error) {
            errorCount++;
            console.error(`Polling error (${errorCount}/${maxErrors}):`, error);

            // Stop after max consecutive errors
            if (errorCount >= maxErrors) {
                clearInterval(pollInterval);
                progressFill.style.background = '#ff9800';
                progressText.textContent = `Connection issues. Please refresh the page.`;
                setTimeout(() => {
                    uploadProgress.style.display = 'none';
                    progressFill.style.background = 'linear-gradient(90deg, #667eea, #764ba2)';
                }, 5000);
            }
        }
    }, 5000); // Poll every 5 seconds
}

// Load documents
async function loadDocuments() {
    try {
        const response = await fetch(`${API_BASE}/history`);
        const data = await response.json();
        
        displayDocuments(data.items);
    } catch (error) {
        documentsList.innerHTML = `<p class="loading">Error loading documents: ${error.message}</p>`;
    }
}

async function displayDocuments(documents) {
    // Sort documents by upload_date (most recent first) so latest appears on top
    const sorted = [...documents].sort((a, b) => {
        const dateA = new Date(a.upload_date);
        const dateB = new Date(b.upload_date);
        return dateB - dateA; // Descending order (newest first)
    });
    
    const filterValue = statusFilter.value;
    const filtered = filterValue === 'all' 
        ? sorted 
        : sorted.filter(doc => doc.status === filterValue);
    
    if (filtered.length === 0) {
        documentsList.innerHTML = `
            <div class="empty-state">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                    <line x1="16" y1="13" x2="8" y2="13"></line>
                    <line x1="16" y1="17" x2="8" y2="17"></line>
                    <polyline points="10 9 9 9 8 9"></polyline>
                </svg>
                <p>No documents found</p>
            </div>
        `;
        return;
    }
    
    // Create cards - current_stage is already included in history response
    documentsList.innerHTML = filtered.map(doc => createDocumentCard(doc)).join('');
    
    // Add click listeners
    filtered.forEach(doc => {
        const card = document.querySelector(`[data-doc-id="${doc.document_id}"]`);
        if (card) {
            card.addEventListener('click', () => showDocumentDetails(doc.document_id));
        }
    });
    
    // Add visual indicators for processing documents
    filtered.forEach(doc => {
        if (doc.status === 'processing' || doc.status === 'pending') {
            const card = document.querySelector(`[data-doc-id="${doc.document_id}"]`);
            if (card) {
                // Add pulsing animation
                card.classList.add('processing-pulse');
            }
        }
    });
}

function createDocumentCard(doc) {
    // Only show confidence badge if document is completed and has a valid confidence score
    const confidenceBadge = (doc.status === 'completed' && doc.confidence_score !== null && doc.confidence_score !== undefined && !isNaN(doc.confidence_score))
        ? `<span class="confidence-score ${getConfidenceClass(doc.confidence_score)}">
             Confidence: ${(doc.confidence_score * 100).toFixed(1)}%
           </span>`
        : '';
    
    const date = new Date(doc.upload_date).toLocaleString();
    const completedDate = doc.completed_at 
        ? new Date(doc.completed_at).toLocaleString()
        : '';
    
    // Show current stage for processing/pending documents
    let stageIndicator = '';
    if ((doc.status === 'processing' || doc.status === 'pending') && doc.current_stage) {
        const stageInfo = getStageInfo(doc.current_stage);
        const progressPercent = getProgressPercent(doc.current_stage);
        stageIndicator = `
            <div class="stage-indicator">
                <span class="stage-label">${stageInfo.icon} ${stageInfo.label}</span>
                <div class="progress-bar" style="width: 100%; height: 4px; background: #e0e0e0; border-radius: 2px; margin-top: 8px;">
                    <div class="progress-fill" style="width: ${progressPercent}%; height: 100%; background: linear-gradient(90deg, #667eea, #764ba2); border-radius: 2px; transition: width 0.3s;"></div>
                </div>
            </div>
        `;
    } else if (doc.status === 'pending') {
        // Show pending status with initial progress
        stageIndicator = `
            <div class="stage-indicator">
                <span class="stage-label">⏳ Waiting to start...</span>
                <div class="progress-bar" style="width: 100%; height: 4px; background: #e0e0e0; border-radius: 2px; margin-top: 8px;">
                    <div class="progress-fill" style="width: 5%; height: 100%; background: linear-gradient(90deg, #667eea, #764ba2); border-radius: 2px;"></div>
                </div>
            </div>
        `;
    }
    
    // Show summary preview if available
    let summaryPreview = '';
    if (doc.summary && doc.status === 'completed') {
        // Extract first meaningful content (skip classification heading)
        let previewText = doc.summary;
        // Remove markdown headings for preview
        previewText = previewText.replace(/^## .+$/gm, '').trim();
        // Remove extra whitespace
        previewText = previewText.replace(/\n+/g, ' ').trim();
        // Get first 150 chars
        const preview = previewText.length > 150 ? previewText.substring(0, 150) + '...' : previewText;
        summaryPreview = `
            <div class="summary-preview">
                <strong>Summary:</strong>
                <p>${preview}</p>
            </div>
        `;
    }
    
    return `
        <div class="document-card ${doc.status}" data-doc-id="${doc.document_id}">
            <div class="document-header">
                <span class="document-name">${doc.filename}</span>
                <span class="document-status status-${doc.status}">${doc.status}</span>
            </div>
            <div class="document-info">
                <span>Uploaded: ${date}</span>
                ${completedDate ? `<span>Completed: ${completedDate}</span>` : ''}
                ${confidenceBadge}
            </div>
            ${stageIndicator}
            ${summaryPreview}
        </div>
    `;
}

function getConfidenceClass(score) {
    if (score >= 0.7) return 'confidence-high';
    if (score >= 0.4) return 'confidence-medium';
    return 'confidence-low';
}

// Stage information mapping
function getStageInfo(stage) {
    // Check if stage includes page progress (e.g., "ocr_extraction:3/8")
    if (stage && stage.includes(':')) {
        const [baseStage, progress] = stage.split(':');
        if (baseStage === 'ocr_extraction' && progress) {
            return {
                label: `🔍 Extracting text (${progress} pages)`,
                icon: '🔍',
                progress: progress
            };
        }
    }

    const stages = {
        'preprocessing': { label: '📄 Preprocessing', icon: '📄' },
        'ocr_extraction': { label: '🔍 Extracting text', icon: '🔍' },
        'summarization': { label: '📝 Summarizing', icon: '📝' },
        'saving_results': { label: '💾 Saving results', icon: '💾' },
        'failed': { label: '❌ Failed', icon: '❌' }
    };
    return stages[stage] || { label: '⏳ Processing', icon: '⏳' };
}

// Get progress percentage based on stage
function getProgressPercent(stage) {
    // Check if stage includes page progress (e.g., "ocr_extraction:3/8")
    if (stage && stage.includes(':')) {
        const [baseStage, progress] = stage.split(':');
        if (baseStage === 'ocr_extraction' && progress) {
            // Parse "3/8" to calculate percentage within OCR stage (15% to 75%)
            const [current, total] = progress.split('/').map(Number);
            if (current && total) {
                // OCR stage is from 15% to 75% (60% range)
                const ocrProgress = (current / total) * 60 + 15;
                return Math.round(ocrProgress);
            }
        }
    }

    const stageProgress = {
        'preprocessing': 15,
        'ocr_extraction': 50,
        'summarization': 80,
        'saving_results': 95,
        'failed': 0
    };
    return stageProgress[stage] || 25;
}

// Convert markdown-style summary to formatted HTML
function formatSummary(markdown) {
    if (!markdown) return '';

    let html = markdown;

    // Convert ## Headings to <h4> with styling
    html = html.replace(/^## (.+)$/gm, '<h4 class="summary-heading">$1</h4>');

    // Convert - bullet points to <li> (handle multi-line lists)
    html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
    // Wrap consecutive <li> items in <ul>
    html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul class="summary-list">$&</ul>');

    // Convert **bold** to <strong>
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    // Convert *italic* to <em>
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

    // Convert line breaks to paragraphs (double newlines = new paragraph)
    html = html.split('\n\n').map(para => {
        para = para.trim();
        // Don't wrap if it's already a heading or list
        if (para.startsWith('<h4') || para.startsWith('<ul') || para.startsWith('<li')) {
            return para;
        }
        // Don't wrap empty paragraphs
        if (para.length === 0) {
            return '';
        }
        return `<p class="summary-paragraph">${para.replace(/\n/g, '<br>')}</p>`;
    }).join('\n');

    return html;
}

// Show document details
async function showDocumentDetails(documentId) {
    try {
        const response = await fetch(`${API_BASE}/document/${documentId}`);
        const doc = await response.json();
        
        modalTitle.textContent = doc.filename;
        
        let content = `
            <div class="modal-section">
                <h3>Document Information</h3>
                <p><strong>Type:</strong> ${doc.file_type}</p>
                <p><strong>Status:</strong> ${doc.status}</p>
                <p><strong>Uploaded:</strong> ${new Date(doc.upload_date).toLocaleString()}</p>
            </div>
        `;
        
        if (doc.extracted_content) {
            const conf = doc.extracted_content.confidence_score;
            const confClass = getConfidenceClass(conf);
            const confPercent = conf ? (conf * 100).toFixed(1) : 'N/A';
            
            // Show summary first and prominently - FULL SUMMARY with formatting
            if (doc.extracted_content.summary) {
                const formattedSummary = formatSummary(doc.extracted_content.summary);
                content += `
                    <div class="modal-section summary-section">
                        <h3>📄 Document Summary</h3>
                        <div class="summary-content">${formattedSummary}</div>
                    </div>
                `;
            } else {
                content += `
                    <div class="modal-section">
                        <p class="no-summary">Summary is being generated. Please check back later.</p>
                    </div>
                `;
            }
            
            content += `
                <div class="modal-section">
                    <h3>Confidence Score</h3>
                    <span class="confidence-badge ${confClass}">${confPercent}%</span>
                </div>
            `;
            
            if (doc.extracted_content.raw_text) {
                content += `
                    <div class="modal-section">
                        <h3>Extracted Text</h3>
                        <pre>${doc.extracted_content.raw_text}</pre>
                    </div>
                `;
            }
        } else {
            content += `
                <div class="modal-section">
                    <p>Document is still being processed. Please check back later.</p>
                </div>
            `;
        }
        
        modalBody.innerHTML = content;
        documentModal.style.display = 'block';
        
    } catch (error) {
        modalBody.innerHTML = `<p>Error loading document: ${error.message}</p>`;
        documentModal.style.display = 'block';
    }
}

