// camera_add_student.js
const saveInfoBtn = document.getElementById("saveInfoBtn");
const startCaptureBtn = document.getElementById("startCaptureBtn");
const addStudentBtn = document.getElementById("addStudentBtn");
const video = document.getElementById("video");
const frameCanvas = document.getElementById("frameCanvas");
const captureStatus = document.getElementById("captureStatus");
const progressBar = document.getElementById("progressBar");

let student_id = null;
let captured = 0;
const maxImages = 50;
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

document.getElementById("studentForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const res = await fetch("/add_student", { method: "POST", body: fd });
  if (!res.ok) {
    alert("Failed to save student info");
    return;
  }
  const j = await res.json();
  student_id = j.student_id;
  alert("Student info saved. Click Start Capture to open the camera.");
  startCaptureBtn.disabled = false;
});

startCaptureBtn.addEventListener("click", async () => {
  startCaptureBtn.disabled = true;
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
  }
});

async function captureImagesLoop() {
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth || 640;
  canvas.height = video.videoHeight || 480;
  const ctx = canvas.getContext("2d");

  while (captured < maxImages) {
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise(res => canvas.toBlob(res, "image/jpeg", 0.9));
    images.push(blob);
    captured++;
    captureStatus.innerText = `Captured ${captured} / ${maxImages}`;
    progressBar.style.width = `${(captured / maxImages) * 100}%`;
    // Redraw frame with updated count
    drawCaptureFrame();
    // small visual flash
    await new Promise(r => setTimeout(r, 200));
  }

  // Stop frame animation
  if (frameInterval) clearInterval(frameInterval);
  const ctx2 = frameCanvas.getContext("2d");
  ctx2.clearRect(0, 0, frameCanvas.width, frameCanvas.height);

  // upload all images in one request
  const form = new FormData();
  form.append("student_id", student_id);
  images.forEach((b, i) => form.append("images[]", b, `img_${i}.jpg`));
  const resp = await fetch("/upload_face", { method: "POST", body: form });
  if (resp.ok) {
    alert("Captured images uploaded");
    addStudentBtn.disabled = false;
  } else {
    alert("Upload failed");
  }

  // stop camera
  if (stream) stream.getTracks().forEach(t => t.stop());
}

addStudentBtn.addEventListener("click", () => {
  alert("Student record complete. Returning to dashboard.");
  window.location.href = "/";
});
