// =========================
// CONFIG
// =========================
const BASE_URL = "http://127.0.0.1:8000";
let faceBuffer = [];
let recognitionInterval = null;

// =========================
// REGISTER FACE
// =========================
async function register() {
    const name = document.getElementById("name").value;
    const file = document.getElementById("image").files[0];
    const email = document.getElementById("email").value;
    const status = document.getElementById("registerStatus");

    if (!name || !file || !email) {
        alert("❌ Please fill all fields!");
        return;
    }

    // Validate email format
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
        alert("❌ Please enter a valid email address!");
        return;
    }

    const formData = new FormData();
    formData.append("name", name);
    formData.append("file", file);
    formData.append("email", email);

    status.innerText = "⏳ Registering...";
    status.style.color = "#fbbf24";

    try {
        const res = await fetch(`${BASE_URL}/register/`, {
            method: "POST",
            body: formData
        });

        const data = await res.json();

        if (!res.ok) {
            throw new Error(data.message || "Registration failed");
        }

        status.innerText = data.message;
        status.style.color = "#4ade80";
        alert(data.message);
        
        // Clear form
        document.getElementById("name").value = "";
        document.getElementById("email").value = "";
        document.getElementById("image").value = "";
        
        // Update status after 3 seconds
        setTimeout(() => {
            status.innerText = "";
        }, 3000);

    } catch (err) {
        console.error("Registration error:", err);
        status.innerText = "❌ Connection error! Make sure server is running";
        status.style.color = "#ef4444";
        alert("❌ Cannot connect to server! Make sure the backend is running on port 8000");
    }
}

// =========================
// START CAMERA
// =========================
async function startCamera() {
    const video = document.getElementById("video");
    const status = document.getElementById("status");
    const faceResult = document.getElementById("faceResult");

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ 
            video: { 
                width: { ideal: 640 },
                height: { ideal: 480 } 
            } 
        });
        video.srcObject = stream;

        status.innerText = "✅ Camera started...";
        status.style.color = "#4ade80";
        
        // Wait for video to be ready
        await new Promise((resolve) => {
            video.onloadedmetadata = () => {
                video.play();
                resolve();
            };
        });

        // Start recognition every 1.5 seconds
        if (recognitionInterval) {
            clearInterval(recognitionInterval);
        }
        recognitionInterval = setInterval(sendFrame, 1500);
        
        faceResult.innerText = "🎥 Monitoring for faces...";
        faceResult.style.color = "#fbbf24";

    } catch (err) {
        console.error("Camera error:", err);
        status.innerText = "❌ Camera access denied!";
        status.style.color = "#ef4444";
        alert("Camera access denied! Please allow camera permissions.");
    }
}

// =========================
// SEND FRAME TO API
// =========================
async function sendFrame() {
    const video = document.getElementById("video");
    const canvas = document.getElementById("canvas");
    const ctx = canvas.getContext("2d");

    if (!video.videoWidth || !video.videoHeight) {
        return;
    }

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob(async (blob) => {
        if (!blob) return;

        const formData = new FormData();
        formData.append("file", blob, "frame.jpg");

        try {
            const res = await fetch(`${BASE_URL}/recognize/`, {
                method: "POST",
                body: formData
            });

            const data = await res.json();
            const faces = data.faces || [];
            const faceResult = document.getElementById("faceResult");

            // Update UI based on detection
            if (faces.length === 0) {
                if (data.message) {
                    faceResult.innerText = `ℹ️ ${data.message}`;
                } else {
                    faceResult.innerText = "❌ No face detected";
                }
                faceResult.style.color = "#fbbf24";
            } 
            else {
                // Display detected faces
                let displayText = "";
                if (faces.length === 1) {
                    displayText = faces[0] === "Unknown" ? "❌ UNKNOWN PERSON!" : `✅ ${faces[0]}`;
                } else {
                    displayText = `👥 ${faces.length} faces: ${faces.join(", ")}`;
                }
                faceResult.innerText = displayText;
                faceResult.style.color = faces.includes("Unknown") ? "#ef4444" : "#4ade80";
            }

            // Buffer logic for unknown faces
            if (faces.length > 0 && faces.includes("Unknown")) {
                faceBuffer.push("Unknown");
                
                if (faceBuffer.length > 5) {
                    faceBuffer.shift();
                }
                
                const unknownCount = faceBuffer.filter(f => f === "Unknown").length;
                
                // Trigger alert if unknown face detected 3 times in last 5 frames
                if (unknownCount >= 3) {
                    triggerAlert();
                    faceBuffer = []; // Reset buffer after alert
                }
            } else if (faces.length > 0 && !faces.includes("Unknown")) {
                // Reset buffer if known face detected
                faceBuffer = [];
            }

        } catch (err) {
            console.error("API Error:", err);
            document.getElementById("faceResult").innerText = "⚠️ API connection error";
            document.getElementById("faceResult").style.color = "#ef4444";
        }
    }, "image/jpeg");
}

// =========================
// TRIGGER ALERT
// =========================
function triggerAlert() {
    try {
        const audio = new Audio("/alarm.mp3");
        audio.play().catch(e => {
            console.error("Audio play error:", e);
            // Show visual alert if audio fails
            const faceResult = document.getElementById("faceResult");
            faceResult.innerHTML = "🚨 INTRUDER ALERT! 🚨";
            faceResult.style.color = "#ef4444";
            faceResult.style.fontWeight = "bold";
            faceResult.style.fontSize = "24px";
            
            // Add blink animation
            if (!document.querySelector("#blink-style")) {
                const style = document.createElement("style");
                style.id = "blink-style";
                style.textContent = `
                    @keyframes blink {
                        0%, 100% { opacity: 1; }
                        50% { opacity: 0.5; }
                    }
                    .blink {
                        animation: blink 0.5s infinite;
                    }
                `;
                document.head.appendChild(style);
            }
            faceResult.classList.add("blink");
        });
        
        console.log("🚨 INTRUDER ALERT TRIGGERED!");
        
        // Remove visual alert after 5 seconds
        setTimeout(() => {
            const result = document.getElementById("faceResult");
            result.classList.remove("blink");
            result.style.fontWeight = "normal";
            result.style.fontSize = "18px";
        }, 5000);
        
    } catch (err) {
        console.error("Alert error:", err);
    }
}

// =========================
// CHECK BACKEND STATUS ON LOAD
// =========================
async function checkBackendStatus() {
    const debugEl = document.getElementById("debug");
    try {
        const res = await fetch(`${BASE_URL}/health`);
        if (res.ok) {
            const data = await res.json();
            debugEl.innerHTML = `✅ Backend Connected<br>📊 Status: ${data.status}<br>🕐 ${new Date(data.timestamp).toLocaleTimeString()}`;
            debugEl.style.color = "#4ade80";
        } else {
            throw new Error("Backend not responding");
        }
    } catch (err) {
        debugEl.innerHTML = "❌ Backend NOT Connected<br>Run: python src/api.py";
        debugEl.style.color = "#ef4444";
    }
}

// Check backend on page load
checkBackendStatus();
// Check every 10 seconds
setInterval(checkBackendStatus, 10000);