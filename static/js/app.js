// Gemini Video Voiceover Translator - Frontend JavaScript

class VideoTranslator {
    constructor() {
        this.processId = null;
        this.statusCheckInterval = null;
        this.voicesData = {}; // Cache for voice data
        this.initializeEventListeners();
        this.initializeVoiceSelection();
    }

    initializeEventListeners() {
        // Form submission
        document.getElementById('upload-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleFileUpload();
        });

        // Download button
        document.getElementById('download-btn').addEventListener('click', () => {
            this.downloadFile();
        });

        // New translation button
        document.getElementById('new-translation-btn').addEventListener('click', () => {
            this.resetForm();
        });

        // Retry button
        document.getElementById('retry-btn').addEventListener('click', () => {
            this.resetForm();
        });

        // File input validation
        document.getElementById('video-file').addEventListener('change', (e) => {
            this.validateFile(e.target.files[0]);
        });
    }

    validateFile(file) {
        if (!file) return;

        const maxSize = 500 * 1024 * 1024; // 500MB
        const allowedTypes = ['video/mp4', 'video/quicktime'];

        if (file.size > maxSize) {
            this.showError('File size must be less than 500MB');
            document.getElementById('video-file').value = '';
            return false;
        }

        if (!allowedTypes.includes(file.type)) {
            this.showError('Only MP4 and MOV files are supported');
            document.getElementById('video-file').value = '';
            return false;
        }

        return true;
    }

    async handleFileUpload() {
        const formData = new FormData();
        const fileInput = document.getElementById('video-file');
        const languageSelect = document.getElementById('language');
        const ttsBackendSelect = document.getElementById('tts-backend');
        const voiceSelect = document.getElementById('voice');
        const processingModeSelect = document.getElementById('processing-mode');
        const separationModelSelect = document.getElementById('separation-model');
        const vocalBalanceInput = document.getElementById('vocal-balance');

        // Validate file
        if (!fileInput.files[0] || !this.validateFile(fileInput.files[0])) {
            return;
        }

        // Prepare form data
        formData.append('video', fileInput.files[0]);
        formData.append('language', languageSelect.value);
        formData.append('tts_backend', ttsBackendSelect.value);
        formData.append('voice', voiceSelect.value);
        formData.append('processing_mode', processingModeSelect.value);
        formData.append('separation_model', separationModelSelect.value);
        formData.append('vocal_balance', vocalBalanceInput.value);

        const enableSubtitles = document.getElementById('enable-subtitles');
        if (enableSubtitles && enableSubtitles.checked) {
            formData.append('enable_subtitles', 'true');
            const subtitleLang = document.getElementById('subtitle-language');
            if (subtitleLang) {
                formData.append('subtitle_language', subtitleLang.value);
            }
        }

        try {
            // Show processing section
            this.showSection('processing-section');
            this.updateProgress(0, 'Uploading file...');

            // Upload file
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (response.ok && result.success) {
                this.processId = result.process_id;
                this.startStatusChecking();
            } else {
                throw new Error(result.error || 'Upload failed');
            }

        } catch (error) {
            this.showError(error.message);
        }
    }

    startStatusChecking() {
        this.statusCheckInterval = setInterval(async () => {
            try {
                const response = await fetch(`/status/${this.processId}`);
                const status = await response.json();

                if (response.ok) {
                    this.handleStatusUpdate(status);
                } else {
                    throw new Error(status.error || 'Status check failed');
                }

            } catch (error) {
                this.stopStatusChecking();
                this.showError(error.message);
            }
        }, 2000); // Check every 2 seconds
    }

    stopStatusChecking() {
        if (this.statusCheckInterval) {
            clearInterval(this.statusCheckInterval);
            this.statusCheckInterval = null;
        }
    }

    handleStatusUpdate(status) {
        switch (status.status) {
            case 'processing':
                this.updateProgress(status.progress, status.message);
                break;

            case 'awaiting_review':
                this.stopStatusChecking();
                this.showReviewSection();
                break;

            case 'completed':
                this.stopStatusChecking();
                this.showSection('results-section');
                this.addSuccessAnimation();
                break;

            case 'error':
                this.stopStatusChecking();
                this.showError(status.message || status.error);
                break;

            default:
                this.updateProgress(status.progress || 0, status.message || 'Processing...');
        }
    }

    async showReviewSection() {
        try {
            // Fetch review data
            const response = await fetch(`/api/review/${this.processId}`);
            if (!response.ok) {
                throw new Error('Failed to fetch review data');
            }

            const data = await response.json();
            this.renderReviewData(data);
            this.showSection('review-section');

        } catch (error) {
            this.showError('Failed to load review data: ' + error.message);
        }
    }

    renderReviewData(data) {
        const container = document.getElementById('review-content');
        const transcription = data.transcription.transcription || [];
        const translation = data.translation.transcription || [];
        const targetLanguage = data.target_language;

        let html = '<div class="row">';
        
        // Transcription column
        html += '<div class="col-md-6">';
        html += '<h4 class="mb-3"><i class="fas fa-microphone me-2"></i>Original Transcription</h4>';
        html += '<div class="transcription-segments">';
        
        transcription.forEach((segment, index) => {
            html += `
                <div class="segment-card mb-3">
                    <div class="segment-header">
                        <span class="badge bg-secondary">#${index + 1}</span>
                        <span class="text-muted ms-2">
                            <i class="fas fa-clock me-1"></i>
                            ${this.formatTime(segment.start_time)} - ${this.formatTime(segment.end_time)}
                        </span>
                    </div>
                    <div class="segment-text mt-2">
                        ${this.escapeHtml(segment.text)}
                    </div>
                </div>
            `;
        });
        
        html += '</div></div>';
        
        // Translation column
        html += '<div class="col-md-6">';
        html += `<h4 class="mb-3"><i class="fas fa-language me-2"></i>Translation (${targetLanguage})</h4>`;
        html += '<div class="translation-segments">';
        
        translation.forEach((segment, index) => {
            html += `
                <div class="segment-card mb-3">
                    <div class="segment-header">
                        <span class="badge bg-primary">#${index + 1}</span>
                        <span class="text-muted ms-2">
                            <i class="fas fa-clock me-1"></i>
                            ${this.formatTime(segment.start_time)} - ${this.formatTime(segment.end_time)}
                        </span>
                    </div>
                    <div class="segment-text mt-2">
                        <textarea class="form-control segment-edit" 
                                  data-index="${index}" 
                                  rows="2">${this.escapeHtml(segment.text)}</textarea>
                    </div>
                </div>
            `;
        });
        
        html += '</div></div>';
        html += '</div>';
        
        container.innerHTML = html;
        
        // Store translation data for later use
        this.currentTranslationData = data.translation;
    }

    async approveTranslation() {
        try {
            // Collect edited translations
            const editedSegments = document.querySelectorAll('.segment-edit');
            const translationData = { ...this.currentTranslationData };
            
            editedSegments.forEach((textarea, index) => {
                if (translationData.transcription[index]) {
                    translationData.transcription[index].text = textarea.value;
                }
            });

            // Send approval with updated translation
            const response = await fetch(`/api/approve/${this.processId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    translation: translationData
                })
            });

            if (!response.ok) {
                throw new Error('Failed to approve translation');
            }

            // Show processing section and resume status checking
            this.showSection('processing-section');
            this.updateProgress(65, 'Translation approved! Generating speech...');
            this.startStatusChecking();

        } catch (error) {
            this.showError('Failed to approve translation: ' + error.message);
        }
    }

    formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    updateProgress(progress, message) {
        const progressBar = document.getElementById('progress-bar');
        const progressText = document.getElementById('progress-text');
        const statusMessage = document.getElementById('status-message');

        progressBar.style.width = `${progress}%`;
        progressText.textContent = `${progress}%`;
        statusMessage.textContent = message;

        // Add animation for progress updates
        progressBar.classList.add('progress-bar-animated');
    }

    async downloadFile() {
        if (!this.processId) {
            this.showError('No file available for download');
            return;
        }

        try {
            // Create download link
            const downloadUrl = `/download/${this.processId}`;
            const link = document.createElement('a');
            link.href = downloadUrl;
            link.download = '';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

        } catch (error) {
            this.showError('Download failed: ' + error.message);
        }
    }

    showSection(sectionId) {
        // Hide all sections
        const sections = [
            'upload-section',
            'processing-section',
            'review-section',
            'results-section',
            'error-section'
        ];

        sections.forEach(id => {
            document.getElementById(id).style.display = 'none';
        });

        // Show target section
        document.getElementById(sectionId).style.display = 'block';
    }

    showError(message) {
        this.stopStatusChecking();
        document.getElementById('error-message').textContent = message;
        this.showSection('error-section');
    }

    resetForm() {
        // Reset form
        document.getElementById('upload-form').reset();
        
        // Reset state
        this.processId = null;
        this.stopStatusChecking();
        
        // Show upload section
        this.showSection('upload-section');
        
        // Reset progress
        this.updateProgress(0, 'Ready to start...');
    }

    addSuccessAnimation() {
        const resultsSection = document.getElementById('results-section');
        resultsSection.classList.add('success-checkmark');
        
        // Remove animation class after animation completes
        setTimeout(() => {
            resultsSection.classList.remove('success-checkmark');
        }, 600);
    }

    // Utility method to format file size
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // Utility method to format duration
    formatDuration(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        
        if (hours > 0) {
            return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        } else {
            return `${minutes}:${secs.toString().padStart(2, '0')}`;
        }
    }

    // Initialize voice selection functionality
    initializeVoiceSelection() {
        // Load initial voices for default language
        const languageSelect = document.getElementById('language');
        if (languageSelect) {
            this.updateVoiceOptions(languageSelect.value);
        }
    }

    // Fetch and render the recommended TTS backend hint for the chosen language.
    // For languages where Chirp 3 HD has incomplete voice coverage (e.g. zh-CN),
    // the backend returns a recommendation that we surface in the help text.
    async refreshTTSRecommendation(languageCode) {
        const helpEl = document.getElementById('tts-backend-help');
        const backendSelect = document.getElementById('tts-backend');
        if (!helpEl || !backendSelect) return;

        try {
            const resp = await fetch(`/api/tts-recommendation/${languageCode}`);
            if (!resp.ok) return;
            const data = await resp.json();

            if (data.is_override) {
                const recommendedLabel = backendSelect.querySelector(`option[value="${data.recommended}"]`)?.textContent || data.recommended;
                helpEl.innerHTML = `<span class="text-warning"><i class="fas fa-info-circle me-1"></i>Recommended for this language: <strong>${this.escapeHtml(recommendedLabel)}</strong></span>`;
            } else {
                helpEl.textContent = 'Gemini: Universal | Chirp3: Premium';
            }
        } catch (err) {
            // Non-fatal; keep default help text
            console.warn('TTS recommendation fetch failed:', err);
        }
    }

    // Update voice options based on selected language
    async updateVoiceOptions(languageCode = null) {
        const languageSelect = document.getElementById('language');
        const voiceSelect = document.getElementById('voice');

        if (!languageCode) {
            languageCode = languageSelect.value;
        }

        this.refreshTTSRecommendation(languageCode);

        try {
            // Check if we have cached data for this language
            if (!this.voicesData[languageCode]) {
                // Fetch voices for the selected language
                const response = await fetch(`/api/voices/${languageCode}`);
                if (!response.ok) {
                    throw new Error('Failed to fetch voices');
                }
                this.voicesData[languageCode] = await response.json();
            }

            const data = this.voicesData[languageCode];
            
            // Clear current voice options
            voiceSelect.innerHTML = '';
            
            // Add voice options for the selected language
            Object.entries(data.voices).forEach(([voiceId, voiceName]) => {
                const option = document.createElement('option');
                option.value = voiceId;
                option.textContent = voiceName;
                
                // Select default voice
                if (voiceId === data.default_voice) {
                    option.selected = true;
                }
                
                voiceSelect.appendChild(option);
            });

            // Add visual feedback
            this.showVoiceUpdateFeedback(data.language_name);

        } catch (error) {
            console.error('Error updating voice options:', error);
            // Fallback: show error in voice select
            voiceSelect.innerHTML = '<option value="">Error loading voices</option>';
        }
    }

    // Show visual feedback when voices are updated
    showVoiceUpdateFeedback(languageName) {
        const voiceSelect = document.getElementById('voice');
        const formText = voiceSelect.parentElement.querySelector('#voice-help');
        
        if (formText) {
            const originalText = formText.textContent;
            formText.innerHTML = `<span class="text-success"><i class="fas fa-check me-1"></i>Updated for ${languageName}</span>`;
            
            // Reset text after 3 seconds
            setTimeout(() => {
                formText.textContent = originalText;
            }, 3000);
        }
    }
    
    // Update voices based on TTS backend and language
    async updateVoicesForBackend(ttsBackend, languageCode) {
        const voiceSelect = document.getElementById('voice');
        const cacheKey = `${ttsBackend}_${languageCode}`;

        this.refreshTTSRecommendation(languageCode);
        
        try {
            // Check if we have cached data for this combo
            if (!this.voicesData[cacheKey]) {
                // Fetch voices for the selected backend and language
                const response = await fetch(`/api/voices/${ttsBackend}/${languageCode}`);
                if (!response.ok) {
                    throw new Error('Failed to fetch voices');
                }
                this.voicesData[cacheKey] = await response.json();
            }

            const data = this.voicesData[cacheKey];
            
            // Clear current voice options
            voiceSelect.innerHTML = '';
            
            // Add voice options
            Object.entries(data.voices).forEach(([voiceId, voiceName]) => {
                const option = document.createElement('option');
                option.value = voiceId;
                option.textContent = voiceName;
                
                // Select default voice
                if (voiceId === data.default_voice) {
                    option.selected = true;
                }
                
                voiceSelect.appendChild(option);
            });

            // Add visual feedback
            this.showVoiceUpdateFeedback(data.language_name);

        } catch (error) {
            console.error('Error updating voices for backend:', error);
            // Fallback: show error in voice select
            voiceSelect.innerHTML = '<option value="">Error loading voices</option>';
        }
    }
}

// Global variable to store the VideoTranslator instance
let videoTranslatorInstance = null;

// Global function for updating voice options (called from HTML)
function updateVoiceOptions() {
    if (videoTranslatorInstance) {
        const languageSelect = document.getElementById('language');
        const ttsBackendSelect = document.getElementById('tts-backend');
        videoTranslatorInstance.updateVoicesForBackend(ttsBackendSelect.value, languageSelect.value);
    }
}

// Global function for updating TTS backend (called from HTML)
function updateTTSBackend() {
    if (videoTranslatorInstance) {
        const languageSelect = document.getElementById('language');
        const ttsBackendSelect = document.getElementById('tts-backend');
        videoTranslatorInstance.updateVoicesForBackend(ttsBackendSelect.value, languageSelect.value);
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    videoTranslatorInstance = new VideoTranslator();
    window.videoTranslator = videoTranslatorInstance; // Make it globally accessible
    
    // Add some visual feedback for file selection
    const fileInput = document.getElementById('video-file');
    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            const fileInfo = document.querySelector('.form-text');
            const originalText = fileInfo.textContent;
            fileInfo.innerHTML = `
                <strong>Selected:</strong> ${file.name} 
                <span class="text-muted">(${(file.size / (1024 * 1024)).toFixed(1)} MB)</span>
            `;
            
            // Reset text after 5 seconds
            setTimeout(() => {
                fileInfo.textContent = originalText;
            }, 5000);
        }
    });
    
    // Add hover effects to feature cards
    const featureCards = document.querySelectorAll('.card');
    featureCards.forEach(card => {
        if (card.querySelector('.fa-3x')) { // Only feature cards
            card.classList.add('feature-card');
        }
    });
});

// Handle page visibility changes to pause/resume status checking
document.addEventListener('visibilitychange', () => {
    const translator = window.videoTranslator;
    if (translator && translator.statusCheckInterval) {
        if (document.hidden) {
            // Page is hidden, reduce check frequency
            translator.stopStatusChecking();
            translator.statusCheckInterval = setInterval(async () => {
                // Check less frequently when page is hidden
                const response = await fetch(`/status/${translator.processId}`);
                const status = await response.json();
                translator.handleStatusUpdate(status);
            }, 10000); // Check every 10 seconds when hidden
        } else {
            // Page is visible, resume normal checking
            translator.stopStatusChecking();
            translator.startStatusChecking();
        }
    }
});

// Toggle audio separation settings based on processing mode
function toggleAudioSettings() {
    const processingMode = document.getElementById('processing-mode').value;
    const audioSettings = document.getElementById('audio-separation-settings');
    
    if (processingMode === 'preserve_music') {
        audioSettings.style.display = 'block';
    } else {
        audioSettings.style.display = 'none';
    }
}

// Toggle subtitle settings visibility
function toggleSubtitleSettings() {
    const checkbox = document.getElementById('enable-subtitles');
    const settings = document.getElementById('subtitle-settings');
    if (settings) {
        settings.style.display = checkbox && checkbox.checked ? 'block' : 'none';
    }
    // Sync subtitle language with voiceover target language when first shown
    if (checkbox && checkbox.checked) {
        const lang = document.getElementById('language');
        const subLang = document.getElementById('subtitle-language');
        if (lang && subLang && !subLang.dataset.userChanged) {
            subLang.value = lang.value;
        }
    }
}

// Initialize audio settings toggle on page load
document.addEventListener('DOMContentLoaded', () => {
    if (typeof toggleAudioSettings === 'function') {
        toggleAudioSettings();
    }
    if (typeof toggleSubtitleSettings === 'function') {
        toggleSubtitleSettings();
    }
    // Mark subtitle language as user-changed once the user interacts
    const subLang = document.getElementById('subtitle-language');
    if (subLang) {
        subLang.addEventListener('change', () => { subLang.dataset.userChanged = 'true'; });
    }
});
