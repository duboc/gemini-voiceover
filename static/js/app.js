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
        formData.append('voice', voiceSelect.value);
        formData.append('processing_mode', processingModeSelect.value);
        formData.append('separation_model', separationModelSelect.value);
        formData.append('vocal_balance', vocalBalanceInput.value);

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

    // Update voice options based on selected language
    async updateVoiceOptions(languageCode = null) {
        const languageSelect = document.getElementById('language');
        const voiceSelect = document.getElementById('voice');
        
        if (!languageCode) {
            languageCode = languageSelect.value;
        }

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
        const formText = voiceSelect.parentElement.querySelector('.form-text');
        
        if (formText) {
            const originalText = formText.textContent;
            formText.innerHTML = `<span class="text-success"><i class="fas fa-check me-1"></i>Updated voices for ${languageName}</span>`;
            
            // Reset text after 3 seconds
            setTimeout(() => {
                formText.textContent = originalText;
            }, 3000);
        }
    }
}

// Global variable to store the VideoTranslator instance
let videoTranslatorInstance = null;

// Global function for updating voice options (called from HTML)
function updateVoiceOptions() {
    if (videoTranslatorInstance) {
        const languageSelect = document.getElementById('language');
        videoTranslatorInstance.updateVoiceOptions(languageSelect.value);
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

// Initialize audio settings toggle on page load
document.addEventListener('DOMContentLoaded', () => {
    // Call toggle function to set initial state
    if (typeof toggleAudioSettings === 'function') {
        toggleAudioSettings();
    }
});
