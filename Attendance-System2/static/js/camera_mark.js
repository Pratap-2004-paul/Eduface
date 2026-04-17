// camera_mark.js
const startMarkBtn = document.getElementById("startMarkBtn");
const stopMarkBtn = document.getElementById("stopMarkBtn");
const markVideo = document.getElementById("markVideo");
const markCanvas = document.getElementById("markCanvas");
const markStatus = document.getElementById("markStatus");
const recognizedList = document.getElementById("recognizedList");

let markStream = null;
let markInterval = null;
let frameInterval = null;
let recognizedIds = new Set();

// Draw face frame on canvas
function drawFaceFrame() {
  const ctx = markCanvas.getContext("2d");
  const w = markCanvas.width;
  const h = markCanvas.height;
  
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
  ctx.strokeStyle = "#4CAF50";
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
  
  // Draw instruction text
  ctx.fillStyle = "#ffffff";
  ctx.font = "14px Arial";
  ctx.textAlign = "center";
  ctx.fillText("Position face in frame", w/2, 30);
}

startMarkBtn.addEventListener("click", async () => {
  startMarkBtn.disabled = true;
  stopMarkBtn.disabled = false;
  try {
    markStream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
    markVideo.srcObject = markStream;
    await markVideo.play();
    markStatus.innerText = "Scanning...";
    // Draw frame continuously
    frameInterval = setInterval(drawFaceFrame, 50);
    // Capture and recognize every 1.2 seconds
    markInterval = setInterval(captureAndRecognize, 1200);
  } catch (err) {
    alert("Camera error: " + err.message);
    startMarkBtn.disabled = false;
    stopMarkBtn.disabled = true;
  }
});

stopMarkBtn.addEventListener("click", () => {
  if (markInterval) clearInterval(markInterval);
  if (frameInterval) clearInterval(frameInterval);
  if (markStream) markStream.getTracks().forEach(t => t.stop());
  // Clear canvas
  const ctx = markCanvas.getContext("2d");
  ctx.clearRect(0, 0, markCanvas.width, markCanvas.height);
  startMarkBtn.disabled = false;
  stopMarkBtn.disabled = true;
  markStatus.innerText = "Stopped";
});

async function captureAndRecognize() {
  const canvas = document.createElement("canvas");
  canvas.width = markVideo.videoWidth || 640;
  canvas.height = markVideo.videoHeight || 480;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(markVideo, 0, 0, canvas.width, canvas.height);
  const blob = await new Promise(r => canvas.toBlob(r, "image/jpeg", 0.85));
  const fd = new FormData();
  fd.append("image", blob, "snap.jpg");
  try {
    const res = await fetch("/recognize_face", { method: "POST", body: fd });
    const j = await res.json();
    if (j.recognized) {
      markStatus.innerText = `✓ Recognized: ${j.name} (${Math.round(j.confidence*100)}%)`;
      if (!recognizedIds.has(j.student_id)) {
        recognizedIds.add(j.student_id);
        const li = document.createElement("li");
        li.className = "list-group-item list-group-item-success";
        li.innerText = `✓ ${j.name} — ${new Date().toLocaleTimeString()}`;
        recognizedList.prepend(li);
      }
    } else {
      let errorMsg = "Not recognized";
      if (j.error === "model_not_trained") {
        errorMsg = "⚠ Model not trained! Train first.";
      } else if (j.error === "face_not_detected") {
        errorMsg = "⚠ No face detected - check lighting";
      } else if (j.error === "low_confidence") {
        errorMsg = `⚠ Low confidence (${Math.round(j.confidence*100)}%)`;
      } else if (j.error) {
        errorMsg = `Error: ${j.error}`;
      }
      markStatus.innerText = errorMsg;
    }
  } catch (err) {
    console.error(err);
  }
}
