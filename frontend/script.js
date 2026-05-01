// =========================
// CONFIG (LOCAL + DEPLOYMENT)
// =========================
const BASE_URL =
    window.location.hostname === "127.0.0.1" ||
    window.location.hostname === "localhost"
        ? "http://127.0.0.1:8000"
        : "https://ai-security-system-2.onrender.com"; 
        // 👆 replace if your Render URL changes

// =========================
// BUFFER SYSTEM
// =========================
let faceBuffer = [];

// =========================
// REGISTER FACE
// =========================
async function register() {
    const name = document.getElementById("name").value;
    const file = document.getElementById("image").files[0];
    const email = document.getElementById("email").value;

    if (!name || !file || !email) {
        alert("Please fill all fields!");
        return;
    }

    const formData = new FormData();
    formData.append("name", name);
    formData.append("file", file);
    formData.append("email", email);

    try {
        const res = await fetch(`${BASE_URL}/register/`, {
            method: "POST",
            body: formData
        });

        const data = await res.json();
        alert("✅ " + (data.message || "Registered successfully"));

    } catch (err) {
        console.error(err);
        alert("❌ Server not reachable!");
    }
}

// =========================
// START CAMERA
// =========================
async function startCamera() {
    const video = document.getElementById("video");
    const status = document.getElementById("status");

    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: true
        });

        video.srcObject = stream;
        status.innerText = "📷 Camera started";

        // send frames continuously
        setInterval(sendFrame, 1200);

    } catch (err) {
        console.error(err);
        alert("❌ Camera access denied!");
    }
}

// =========================
// SEND FRAME TO BACKEND
// =========================
async function sendFrame() {
    const video = document.getElementById("video");
    const canvas = document.getElementById("canvas");
    const ctx = canvas.getContext("2d");
    const faceResult = document.getElementById("faceResult");

    if (!video.videoWidth) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0);

    canvas.toBlob(async (blob) => {

        const formData = new FormData();
        formData.append("file", blob, "frame.jpg");

        try {
            const res = await fetch(`${BASE_URL}/recognize/`, {
                method: "POST",
                body: formData
            });

            const data = await res.json();

            // =========================
            // SAFE BACKEND RESPONSE
            // =========================
            const face = data?.faces?.[0];

            // CASE 1: No face detected
            if (!face || face === "No face detected") {
                faceResult.innerText = "❌ No face detected";
                return;
            }

            // CASE 2: Unknown person (INTRUDER)
            if (face === "Unknown") {
                faceResult.innerText = "🚨 Intruder Detected";
                triggerAlert();
            }

            // CASE 3: Known person
            else {
                faceResult.innerText = `🧑 ${face}`;
            }

            // =========================
            // BUFFER LOGIC (STABLE)
            // =========================
            faceBuffer.push(face);

            if (faceBuffer.length > 5) {
                faceBuffer.shift();
            }

            const unknownCount = faceBuffer.filter(f => f === "Unknown").length;

            if (unknownCount >= 3) {
                triggerAlert();
                faceBuffer = [];
            }

        } catch (err) {
            console.error("API Error:", err);
            faceResult.innerText = "⚠️ Server error";
        }

    }, "image/jpeg");
}

// =========================
// ALERT SYSTEM
// =========================
function triggerAlert() {
    const audio = new Audio("alarm.mp3");
    audio.play();
}