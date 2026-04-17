/**
 * Student Face Enrollment via Camera Capture
 * Used during student registration (Step 2)
 * Captures 20 face photos automatically for ML model training
 */

class StudentFaceEnrollment {
    constructor() {
        this.videoElement = null;
        this.canvasElement = null;
        this.capturedPhotos = [];
        this.isCapturing = false;
        this.photoCount = 0;
        this.maxPhotos = 20;
        this.captureInterval = null;
    }

    /**
     * Initialize the camera modal
     */
    initModal() {
        // Check if modal already exists
        if (document.getElementById('enrollment-camera-modal')) {
            return; // Don't create duplicate
        }

        const html = `
        <div class="modal-overlay active" id="enrollment-camera-modal">
            <div class="modal modal-lg" onclick="event.stopPropagation()">
                <div class="modal-header">
                    <div>
                        <h3>📷 Capture Face Photos for Enrollment</h3>
                        <p class="text-muted" style="font-size:.85rem;margin-top:4px">
                            Position your face in the center. We'll capture 20 photos automatically (2-3 seconds apart).
                        </p>
                    </div>
                    <button class="btn-close">✕</button>
                </div>
                <div class="modal-body">
                    <div id="enrollment-steps">
                        <!-- Step 1: Camera Preview -->
                        <div id="enrollment-step-preview" class="enrollment-step-content active">
                            <div style="text-align: center; margin-bottom: 20px;">
                                <video id="enrollment-video"
                                       style="width: 100%; max-width: 400px; border-radius: 8px; border: 2px solid var(--indigo-300);"
                                       playsinline autoplay></video>
                                <canvas id="enrollment-canvas" style="display: none;"></canvas>
                            </div>
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px;">
                                <button type="button" class="btn btn-outline" onclick="faceEnrollment.closeModal()">
                                    Cancel
                                </button>
                                <button type="button" class="btn btn-primary" onclick="faceEnrollment.startCapture()">
                                    Start Capture (20 Photos)
                                </button>
                            </div>
                            <div id="enrollment-status" style="text-align: center; color: var(--slate-600); font-size: .85rem;">
                                Ready to capture
                            </div>
                        </div>

                        <!-- Step 2: Capturing Progress -->
                        <div id="enrollment-step-capturing" style="display: none;" class="enrollment-step-content">
                            <div style="text-align: center;">
                                <div style="font-size: 3rem; margin: 20px 0;">📸</div>
                                <h4 style="margin: 0;">Capturing Photos...</h4>
                                <p style="color: var(--slate-600); margin: 8px 0;">
                                    <strong id="enrollment-photo-count">0</strong> / <strong>20</strong> photos captured
                                </p>
                                <div style="width: 100%; height: 8px; background: var(--slate-200); border-radius: 4px; margin: 20px 0; overflow: hidden;">
                                    <div id="enrollment-progress-bar"
                                         style="width: 0%; height: 100%; background: var(--indigo-500); transition: width 0.3s;"></div>
                                </div>
                                <p style="color: var(--slate-500); font-size: .85rem;">
                                    Don't move! Camera is auto-capturing...
                                </p>
                            </div>
                        </div>

                        <!-- Step 3: Photos Captured - Review -->
                        <div id="enrollment-step-review" style="display: none;" class="enrollment-step-content">
                            <h4 style="margin-bottom: 12px;">✅ Photos Captured Successfully!</h4>
                            <p style="color: var(--slate-600); margin-bottom: 16px;">
                                <strong id="enrollment-final-count">0</strong> face photos have been captured and are ready for ML training.
                            </p>
                            <div id="enrollment-photos-grid" style="
                                display: grid;
                                grid-template-columns: repeat(auto-fill, minmax(60px, 1fr));
                                gap: 8px;
                                margin-bottom: 20px;
                                max-height: 200px;
                                overflow-y: auto;
                            ">
                                <!-- Photo thumbnails will be inserted here -->
                            </div>
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                                <button type="button" class="btn btn-outline" onclick="faceEnrollment.resetAndRetry()">
                                    Retry Capture
                                </button>
                                <button type="button" class="btn btn-success" onclick="faceEnrollment.finishEnrollment()">
                                    Use These Photos ✓
                                </button>
                            </div>
                        </div>

                        <!-- Step 4: Error State -->
                        <div id="enrollment-step-error" style="display: none;" class="enrollment-step-content">
                            <div class="alert alert-error" style="margin-bottom: 20px;">
                                <strong>❌ Error:</strong>
                                <p id="enrollment-error-message" style="margin: 8px 0 0 0;"></p>
                            </div>
                            <button type="button" class="btn btn-primary btn-full" onclick="faceEnrollment.resetAndRetry()">
                                Try Again
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        `;
        
        const container = document.body;
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        container.appendChild(doc.body.firstChild);
        
        // Store references
        this.videoElement = document.getElementById('enrollment-video');
        this.canvasElement = document.getElementById('enrollment-canvas');
        
        // Add event listeners for closing modal
        const modal = document.getElementById('enrollment-camera-modal');
        const closeBtn = modal.querySelector('.btn-close');
        
        // Close button
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.closeModal());
        }
        
        // Click outside modal overlay to close
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.closeModal();
            }
        });
    }

    /**
     * Request camera access and display video feed
     */
    async requestCameraAccess() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    width: { ideal: 640 },
                    height: { ideal: 480 },
                    facingMode: 'user'
                },
                audio: false
            });
            
            this.videoElement.srcObject = stream;
            this.videoElement.play();
            return true;
        } catch (error) {
            console.error('Camera access error:', error);
            this.showError(`Camera access denied: ${error.message}`);
            return false;
        }
    }

    /**
     * Start capturing 20 photos automatically
     */
    async startCapture() {
        const hasCamera = await this.requestCameraAccess();
        if (!hasCamera) return;
        
        // Show capturing step
        document.getElementById('enrollment-step-preview').style.display = 'none';
        document.getElementById('enrollment-step-capturing').style.display = 'block';
        document.getElementById('enrollment-step-review').style.display = 'none';
        document.getElementById('enrollment-step-error').style.display = 'none';
        
        this.capturedPhotos = [];
        this.photoCount = 0;
        this.isCapturing = true;
        
        // Capture photos at intervals (2-3 seconds apart for 20 photos)
        const intervalMs = 2500; // 2.5 seconds
        this.captureInterval = setInterval(() => {
            if (this.photoCount < this.maxPhotos) {
                this.capturePhoto();
            } else {
                this.completeCapture();
            }
        }, intervalMs);
    }

    /**
     * Capture a single photo from video feed
     */
    capturePhoto() {
        if (!this.videoElement || !this.canvasElement) return;
        
        const ctx = this.canvasElement.getContext('2d');
        this.canvasElement.width = this.videoElement.videoWidth;
        this.canvasElement.height = this.videoElement.videoHeight;
        
        // Mirror the video for better UX
        ctx.scale(-1, 1);
        ctx.drawImage(this.videoElement, -this.canvasElement.width, 0);
        
        // Convert canvas to blob
        this.canvasElement.toBlob((blob) => {
            this.capturedPhotos.push({
                blob: blob,
                timestamp: new Date().toISOString(),
                index: this.photoCount
            });
            this.photoCount++;
            
            // Update UI
            const percentage = Math.round((this.photoCount / this.maxPhotos) * 100);
            document.getElementById('enrollment-progress-bar').style.width = percentage + '%';
            document.getElementById('enrollment-photo-count').textContent = this.photoCount;
        }, 'image/jpeg', 0.85);
    }

    /**
     * Complete capture and show review
     */
    completeCapture() {
        clearInterval(this.captureInterval);
        this.isCapturing = false;
        
        // Stop video stream
        if (this.videoElement.srcObject) {
            this.videoElement.srcObject.getTracks().forEach(track => track.stop());
        }
        
        // Show review step
        document.getElementById('enrollment-step-capturing').style.display = 'none';
        document.getElementById('enrollment-step-review').style.display = 'block';
        
        // Show thumbnails
        this.displayThumbnails();
        document.getElementById('enrollment-final-count').textContent = this.photoCount;
    }

    /**
     * Display captured photo thumbnails
     */
    displayThumbnails() {
        const grid = document.getElementById('enrollment-photos-grid');
        grid.innerHTML = '';
        
        this.capturedPhotos.forEach((photo, idx) => {
            const url = URL.createObjectURL(photo.blob);
            const img = document.createElement('img');
            img.src = url;
            img.style.cssText = `
                width: 60px;
                height: 60px;
                object-fit: cover;
                border-radius: 4px;
                border: 1px solid var(--slate-300);
            `;
            grid.appendChild(img);
        });
    }

    /**
     * Reset and retry capturing
     */
    resetAndRetry() {
        this.capturedPhotos = [];
        this.photoCount = 0;
        this.isCapturing = false;
        clearInterval(this.captureInterval);
        
        // Stop video if running
        if (this.videoElement && this.videoElement.srcObject) {
            this.videoElement.srcObject.getTracks().forEach(track => track.stop());
        }
        
        // Show preview step
        document.getElementById('enrollment-step-preview').style.display = 'block';
        document.getElementById('enrollment-step-capturing').style.display = 'none';
        document.getElementById('enrollment-step-review').style.display = 'none';
        document.getElementById('enrollment-step-error').style.display = 'none';
        document.getElementById('enrollment-status').textContent = 'Ready to capture';
    }

    /**
     * Finish enrollment and add photos to form
     */
    finishEnrollment() {
        // Add captured photos to the form
        const formData = new FormData();
        
        this.capturedPhotos.forEach((photo, idx) => {
            formData.append('face_photos[]', photo.blob, `face_${idx}.jpg`);
        });
        
        // Store in window so the form can access it
        window.capturedFacePhotos = {
            count: this.photoCount,
            formData: formData
        };
        
        // Update the capture status display in the form
        if (window.updateFaceCaptureStatus) {
            window.updateFaceCaptureStatus(this.photoCount);
        }
        
        console.log(`Enrollment successful: ${this.photoCount} photos captured`);
        this.closeModal();
    }

    /**
     * Show error message
     */
    showError(message) {
        document.getElementById('enrollment-step-preview').style.display = 'none';
        document.getElementById('enrollment-step-capturing').style.display = 'none';
        document.getElementById('enrollment-step-review').style.display = 'none';
        document.getElementById('enrollment-step-error').style.display = 'block';
        document.getElementById('enrollment-error-message').textContent = message;
        
        // Stop capturing if in progress
        if (this.isCapturing) {
            clearInterval(this.captureInterval);
            this.isCapturing = false;
        }
        
        // Stop video stream
        if (this.videoElement && this.videoElement.srcObject) {
            this.videoElement.srcObject.getTracks().forEach(track => track.stop());
        }
    }

    /**
     * Close the modal
     */
    closeModal() {
        // Stop video stream
        if (this.videoElement && this.videoElement.srcObject) {
            this.videoElement.srcObject.getTracks().forEach(track => track.stop());
        }
        
        clearInterval(this.captureInterval);
        this.isCapturing = false;
        
        const modal = document.getElementById('enrollment-camera-modal');
        if (modal) {
            modal.remove();
        }
    }

    /**
     * Open the enrollment modal
     */
    openModal() {
        this.initModal();
        this.resetAndRetry();
    }
}

// Initialize global instance
const faceEnrollment = new StudentFaceEnrollment();
