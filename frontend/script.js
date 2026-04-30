// =========================
// FRONTEND FACE BUFFER (FIX FALSE ALERTS)
// =========================
let faceBuffer = [];

// =========================
// REGISTER FUNCTION
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
        const res = await fetch("https://your-app-name.onrender.com/register/", {
            method: "POST",
            body: formData
        });

        const data = await res.json();

        status.innerText = data.message;
        alert(data.message);

    } catch (error) {
        console.error("Register Error:", error);
        alert("Registration failed!");
    }
}

// =========================
// START CAMERA
// =========================
async function startCamera() {
    const video = document.getElementById("video");
    const status = document.getElementById("status");

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        video.srcObject = stream;

        status.innerText = "Camera started...";

        setInterval(sendFrame, 1000);

    } catch (error) {
        console.error("Camera Error:", error);
        alert("Camera access denied!");
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
            const res = await fetch("https://your-app-name.onrender.com/recognize/", {
                method: "POST",
                body: formData
            });

            const data = await res.json();
            console.log(data);

            let faces = data.faces || [];

            // =========================
            // BUFFER LOGIC (FIX FALSE ALERTS)
            // =========================
            faceBuffer.push(faces);

            // keep last 5 frames
            if (faceBuffer.length > 5) {
                faceBuffer.shift();
            }

            // flatten buffer
            let allFaces = faceBuffer.flat();

            let unknownCount = allFaces.filter(f => f === "Unknown").length;

            // =========================
            // STABLE ALERT SYSTEM
            // =========================
            if (unknownCount >= 3) {
                triggerAlert();
                faceBuffer = []; // reset after alert
            }

            // =========================
            // LOGIC FOR NO FACE
            // =========================
            if (faces.includes("No face detected")) {
                console.log("No face detected");
            }

        } catch (error) {
            console.error("API Error:", error);
        }

    }, "image/jpeg");
}

// =========================
// SOUND ALERT
// =========================
function triggerAlert() {
    const audio = new Audio("alarm.mp3");
    audio.play();
}