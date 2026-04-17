// camera_face_enrollment.js - Face enrollment for students through their dashboard
const startCaptureBtn = document.getElementById("startCaptureBtn");
const stopCaptureBtn = document.getElementById("stopCaptureBtn");
const video = document.getElementById("enrollVideo");
const frameCanvas = document.getElementById("enrollCanvas");
const captureStatus = document.getElementById("captureStatus");
const progressBar = document.getElementById("progressBar");

let student_id = null;
let captured = 0;
const maxImages = 20;
let images = [];
let stream = null;
let frameInterval = null;

// Draw face frame on canvas
function drawCaptureFrame() {
  const ctx = frameCanvas.getContext("2d");
  const w = frameCanvas.width;
  const h = frameCanvas.height;
  
  // Clear canvas
  ctx.clearRect(0, 0, w, h);
  
  // Frame dimensions
  const frameWidth = Math.min(250, w * 0.6);
  const frameHeight = Math.min(320, h * 0.75);
  const frameX = (w - frameWidth) / 2;
  const frameY = (h - frameHeight) / 2;
  
  // Draw semi-transparent overlay outside frame
  ctx.fillStyle = "rgba(0, 0, 0, 0.3)";
  ctx.fillRect(0, 0, w, h);
  ctx.clearRect(frameX, frameY, frameWidth, frameHeight);
  
  // Draw frame border
  ctx.strokeStyle = "#FF9800";
  ctx.lineWidth = 3;
  ctx.strokeRect(frameX, frameY, frameWidth, frameHeight);
  
  // Draw corner markers
  const cornerSize = 15;
  const corners = [
    { x: frameX, y: frameY }, // top-left
    { x: frameX + frameWidth, y: frameY }, // top-right
    { x: frameX, y: frameY + frameHeight }, // bottom-left
    { x: frameX + frameWidth, y: frameY + frameHeight } // bottom-right
  ];
  
  ctx.strokeStyle = "#2196F3";
  ctx.lineWidth = 3;
  corners.forEach(corner => {
    ctx.strokeRect(corner.x - cornerSize/2, corner.y - cornerSize/2, cornerSize, cornerSize);
  });
  
  // Draw center guide
  ctx.strokeStyle = "rgba(255, 193, 7, 0.5)";
  ctx.lineWidth = 1;
  ctx.setLineDash([5, 5]);
  ctx.beginPath();
  ctx.moveTo(frameX + frameWidth/2, frameY);
  ctx.lineTo(frameX + frameWidth/2, frameY + frameHeight);
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(frameX, frameY + frameHeight/2);
  ctx.lineTo(frameX + frameWidth, frameY + frameHeight/2);
  ctx.stroke();
  ctx.setLineDash([]);
  
  // Draw capture progress
  ctx.fillStyle = "#ffffff";
  ctx.font = "bold 16px Arial";
  ctx.textAlign = "center";
  ctx.fillText("Position face in frame", w/2, 30);
  ctx.font = "14px Arial";
  ctx.fillStyle = "#FFD700";
  ctx.fillText(`Captured: ${captured} / ${maxImages}`, w/2, h - 15);
}

startCaptureBtn.addEventListener("click", async () => {
  startCaptureBtn.disabled = true;
  stopCaptureBtn.disabled = false;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
    video.srcObject = stream;
    await video.play();
    // Draw frame continuously
    frameInterval = setInterval(drawCaptureFrame, 50);
    captureImagesLoop();
  } catch (err) {
    alert("Camera access error: " + err.message);
    startCaptureBtn.disabled = false;
    stopCaptureBtn.disabled = true;
  }
});

stopCaptureBtn.addEventListener("click", () => {
  if (frameInterval) clearInterval(frameInterval);
  const ctx = frameCanvas.getContext("2d");
  ctx.clearRect(0, 0, frameCanvas.width, frameCanvas.height);
  if (stream) stream.getTracks().forEach(t => t.stop());
  startCaptureBtn.disabled = false;
  stopCaptureBtn.disabled = true;
  captureStatus.innerText = "Stopped";
});

async function captureImagesLoop() {
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth || 640;
  canvas.height = video.videoHeight || 480;
  const ctx = canvas.getContext("2d");

  while (captured < maxImages && stream) {
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise(res => canvas.toBlob(res, "image/jpeg", 0.9));
    images.push(blob);
    captured++;
    captureStatus.innerText = `Captured ${captured} / ${maxImages}`;
    progressBar.style.width = `${(captured / maxImages) * 100}%`;
    // Redraw frame with updated count
    drawCaptureFrame();
    // small visual flash
    await new Promise(r => setTimeout(r, 150));
  }

  // Stop frame animation
  if (frameInterval) clearInterval(frameInterval);
  const ctx2 = frameCanvas.getContext("2d");
  ctx2.clearRect(0, 0, frameCanvas.width, frameCanvas.height);

  // upload all images
  const form = new FormData();
  images.forEach((b, i) => form.append("images[]", b, `img_${i}.jpg`));
  const resp = await fetch(`/api/student/enroll_face`, { method: "POST", body: form });
  if (resp.ok) {
    const data = await resp.json();
    alert(data.msg || "Face images uploaded successfully!");
    captureStatus.innerText = "Upload complete!";
    captured = 0;
    images = [];
  } else {
    alert("Upload failed");
    captureStatus.innerText = "Upload failed";
  }

  // stop camera
  if (stream) stream.getTracks().forEach(t => t.stop());
  startCaptureBtn.disabled = false;
  stopCaptureBtn.disabled = true;
}
