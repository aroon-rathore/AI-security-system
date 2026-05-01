 // =========================
// CONFIG (DEPLOYMENT READY)
// =========================

// Auto-switch between local and production
const BASE_URL =
    window.location.hostname === "127.0.0.1" ||
    window.location.hostname === "localhost"
        ? "http://127.0.0.1:8000"
        : "https://YOUR-DEPLOYED-BACKEND-URL"; 
        // 👆 replace after deployment (Hugging Face / Render link)

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
    const status = document.getElementById("registerStatus");

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

        if (!res.ok) {
            throw new Error(data.message || "Registration failed");
        }

        status.innerText = data.message;
        alert("✅ " + data.message);

    } catch (err) {
        console.error(err);
        alert("❌ Server not reachable!");
    }
}

// =========================
// START CAMERA (USER DEVICE)
// =========================
async function startCamera() {
    const video = document.getElementById("video");
    const status = document.getElementById("status");

    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: true
        });

        video.srcObject = stream;

        status.innerText = "📷 Camera active";

        // send frames every 1 second
        setInterval(sendFrame, 1000);

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

            const faceResult = document.getElementById("faceResult");

            if (data.status === "no_face") {
                faceResult.innerText = "❌ No face detected";
                return;
            }

            const names = data.name || [];

            if (Array.isArray(names)) {
                faceResult.innerText = `🧑 ${names[0]}`;

                // BUFFER LOGIC
                faceBuffer.push(names[0]);

            } else {
                faceResult.innerText = `🧑 ${names}`;
                faceBuffer.push(names);
            }

            if (faceBuffer.length > 5) {
                faceBuffer.shift();
            }

            const unknownCount = faceBuffer.filter(n => n === "Unknown").length;

            if (unknownCount >= 3) {
                triggerAlert();
                faceBuffer = [];
            }

        } catch (err) {
            console.error("API Error:", err);
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