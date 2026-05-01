const BASE_URL =
    window.location.hostname === "127.0.0.1" ||
    window.location.hostname === "localhost"
        ? "http://127.0.0.1:8000"
        : "https://ai-security-system-2.onrender.com"; 
        // replace with your Render URL if needed

// =========================
// STATE CONTROL
// =========================
let faceBuffer = [];
let isProcessing = false;

// =========================
// REGISTER FACE
// =========================
async function register() {
    const name = document.getElementById("name").value;
    const email = document.getElementById("email").value;
    const file = document.getElementById("image").files[0];
    const status = document.getElementById("registerStatus");

    if (!name || !email || !file) {
        alert("Please fill all fields!");
        return;
    }

    const formData = new FormData();
    formData.append("name", name);
    formData.append("email", email);
    formData.append("file", file);

    try {
        const res = await fetch(`${BASE_URL}/register/`, {
            method: "POST",
            body: formData
        });

        const data = await res.json();

        if (data.status === "success") {
            status.innerText = "✅ " + data.message;
            alert(data.message);
        } else {
            status.innerText = "❌ Registration failed";
        }

    } catch (err) {
        console.error(err);
        alert("❌ Server error during registration");
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
        status.innerText = "📷 Camera running";

        // IMPORTANT: prevent multiple intervals
        setInterval(sendFrame, 1200);

    } catch (err) {
        console.error(err);
        alert("Camera access denied!");
    }
}

// =========================
// SEND FRAME TO BACKEND
// =========================
async function sendFrame() {

    if (isProcessing) return;
    isProcessing = true;

    const video = document.getElementById("video");
    const canvas = document.getElementById("canvas");
    const ctx = canvas.getContext("2d");
    const faceResult = document.getElementById("faceResult");

    if (!video.videoWidth) {
        isProcessing = false;
        return;
    }

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
            // HANDLE ERRORS
            // =========================
            if (!data || !data.status) {
                faceResult.innerText = "⚠️ Server error";
                isProcessing = false;
                return;
            }

            // =========================
            // NO FACE DETECTED
            // =========================
            if (data.status === "no_face") {
                faceResult.innerText = "❌ No face detected";
                isProcessing = false;
                return;
            }

            // =========================
            // GET NAME
            // =========================
            const name = data.faces?.[0];

            if (!name) {
                faceResult.innerText = "⚠️ Processing...";
                isProcessing = false;
                return;
            }

            // =========================
            // DISPLAY RESULT
            // =========================
            if (name === "Unknown") {
                faceResult.innerText = "🚨 Intruder Detected";
            } else {
                faceResult.innerText = "🧑 " + name;
            }

            // =========================
            // BUFFER SYSTEM (for alert)
            // =========================
            faceBuffer.push(name);

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
            faceResult.innerText = "⚠️ Connection error";
        }

        isProcessing = false;

    }, "image/jpeg");
}

// =========================
// ALERT SOUND
// =========================
function triggerAlert() {
    const audio = new Audio("alarm.mp3");
    audio.play();
}