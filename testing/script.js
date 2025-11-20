const btnStartGame = document.getElementById('btnStartGame');
const btnConnect = document.getElementById('btnConnect');
const btnPushToTalk = document.getElementById('btnPushToTalk');
const btnEndGame = document.getElementById('btnEndGame');
const btnGenerate = document.getElementById('btnGenerate');
const btnRefreshScenarios = document.getElementById('btnRefreshScenarios');
const statusDiv = document.getElementById('status');
const resultsDiv = document.getElementById('results');
const audioPlayer = document.getElementById('audioPlayer');
const chatLog = document.getElementById('chatLog');
const timerDiv = document.getElementById('timer');
const scenarioSelect = document.getElementById('scenarioSelect');
const descriptionInput = document.getElementById('descriptionInput');
const charCount = document.getElementById('charCount');
const exampleChips = document.querySelectorAll('.example-chip');

const canvasLeft = document.getElementById('visualizerLeft');
const canvasRight = document.getElementById('visualizerRight');
const ctxLeft = canvasLeft.getContext('2d');
const ctxRight = canvasRight.getContext('2d');

let audioContext;
let aiAnalyser, aiDataArray, aiBufferLength;
let micAnalyser, micDataArray, micBufferLength, micStream, animationId;

function initAudioContext() {
    if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
}

function initAIVisualizer() {
    if (!audioContext) {
        initAudioContext();
    }

    aiAnalyser = audioContext.createAnalyser();
    aiAnalyser.fftSize = 512;
    aiBufferLength = aiAnalyser.frequencyBinCount;
    aiDataArray = new Uint8Array(aiBufferLength);

    const aiSource = audioContext.createMediaElementSource(audioPlayer);
    aiSource.connect(aiAnalyser);
    aiSource.connect(audioContext.destination);
}

async function initMicVisualizer(stream) {
    if (!audioContext) {
        initAudioContext();
    }

    micAnalyser = audioContext.createAnalyser();
    micAnalyser.fftSize = 512;
    micBufferLength = micAnalyser.frequencyBinCount;
    micDataArray = new Uint8Array(micBufferLength);

    const micSource = audioContext.createMediaStreamSource(stream);
    micSource.connect(micAnalyser);

    if (!animationId) {
        drawVisualizers();
    }
}

function stopMicVisualizer() {
    micAnalyser = null;
    micDataArray = null;
}

function drawVisualizers() {
    animationId = requestAnimationFrame(drawVisualizers);

    // Draw AI visualizer (left)
    if (aiAnalyser && aiDataArray && !audioPlayer.paused) {
        aiAnalyser.getByteFrequencyData(aiDataArray);
        drawRadialVisualizer(ctxLeft, canvasLeft, aiDataArray);
    } else {
        drawRadialVisualizer(ctxLeft, canvasLeft, new Uint8Array(128));
    }

    // Draw Mic visualizer (right)
    if (micAnalyser && micDataArray) {
        micAnalyser.getByteFrequencyData(micDataArray);
        drawRadialVisualizer(ctxRight, canvasRight, micDataArray);
    } else {
        drawRadialVisualizer(ctxRight, canvasRight, new Uint8Array(128));
    }
}

function drawRadialVisualizer(ctx, canvas, data) {
    const width = canvas.width;
    const height = canvas.height;
    const centerX = width / 2;
    const centerY = height / 2;
    const radius = Math.min(width, height) / 3;

    ctx.clearRect(0, 0, width, height);

    const bars = 128;
    const barWidth = 2.5;

    for (let i = 0; i < bars; i++) {
        const value = data[Math.floor(i * data.length / bars)] || 0;
        const barHeight = (value / 255) * radius * 0.7;
        const angle = (i / bars) * Math.PI * 2;

        const x1 = centerX + Math.cos(angle) * radius;
        const y1 = centerY + Math.sin(angle) * radius;
        const x2 = centerX + Math.cos(angle) * (radius + barHeight);
        const y2 = centerY + Math.sin(angle) * (radius + barHeight);

        const gradient = ctx.createLinearGradient(x1, y1, x2, y2);
        gradient.addColorStop(0, '#00BFFF');
        gradient.addColorStop(0.5, '#FF69B4');
        gradient.addColorStop(1, '#FFEB3B');

        ctx.strokeStyle = gradient;
        ctx.lineWidth = barWidth;
        ctx.lineCap = 'round';

        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
    }

    ctx.beginPath();
    ctx.arc(centerX, centerY, radius - 5, 0, Math.PI * 2);
    ctx.strokeStyle = '#FF69B4';
    ctx.lineWidth = 2;
    ctx.stroke();
}

audioPlayer.addEventListener('play', () => {
    if (!aiAnalyser) {
        initAIVisualizer();
    }

    if (audioContext.state === 'suspended') {
        audioContext.resume();
    }

    if (!animationId) {
        drawVisualizers();
    }
});

audioPlayer.addEventListener('pause', () => {
    // Visualizer will show empty state automatically
});

audioPlayer.addEventListener('ended', () => {
    // Visualizer will show empty state automatically
});

let sessionId = null, socket = null, mediaRecorder = null, audioQueue = [];
let timerInterval = null, timeLeft = 120, typingIndicator = null;
let pendingAIMessage = '', isTimerPaused = false, isSpamMode = false, spamQueue = [];

const API_URL = window.__ENV__.API_URL;
const WS_URL = window.__ENV__.WS_URL;

const TEST_USER_ID = "html_test_user";

// Initialize visualizers on page load
function initializeVisualizers() {
    // Draw empty state circles immediately
    drawRadialVisualizer(ctxLeft, canvasLeft, new Uint8Array(128));
    drawRadialVisualizer(ctxRight, canvasRight, new Uint8Array(128));

    // Start animation loop
    if (!animationId) {
        drawVisualizers();
    }
}

// Initialize on page load
initializeVisualizers();
loadScenarios();

descriptionInput.addEventListener('input', () => {
    const length = descriptionInput.value.length;
    charCount.textContent = `${length} / 500`;

    if (length < 10) {
        charCount.classList.remove('warning');
        btnGenerate.disabled = true;
    } else if (length > 450) {
        charCount.classList.add('warning');
        btnGenerate.disabled = false;
    } else {
        charCount.classList.remove('warning');
        btnGenerate.disabled = false;
    }
});

exampleChips.forEach(chip => {
    chip.addEventListener('click', () => {
        descriptionInput.value = chip.dataset.example;
        descriptionInput.dispatchEvent(new Event('input'));
    });
});

btnGenerate.onclick = async () => {
    const description = descriptionInput.value.trim();
    if (description.length < 10 || description.length > 500) {
        updateStatus("Description must be 10-500 characters");
        return;
    }

    btnGenerate.disabled = true;
    btnGenerate.innerHTML = '<span class="loading"></span> Generating...';
    updateStatus("🤖 AI is creating your scenario...");

    try {
        const response = await fetch(`${API_URL}/api/v1/scenarios/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ description })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to generate scenario');
        }

        const data = await response.json();
        updateStatus(`✅ Created: ${data.scenario.title}`);

        descriptionInput.value = '';
        charCount.textContent = '0 / 500';

        await loadScenarios();
        scenarioSelect.value = data.scenario.id;

    } catch (err) {
        updateStatus(`❌ Error: ${err.message}`);
        console.error("Generation Error:", err);
    } finally {
        btnGenerate.disabled = false;
        btnGenerate.textContent = '🤖 Generate';
    }
};

btnRefreshScenarios.onclick = async () => await loadScenarios();

async function loadScenarios() {
    btnRefreshScenarios.disabled = true;
    try {
        const response = await fetch(`${API_URL}/api/v1/scenarios/`);
        if (!response.ok) throw new Error('Failed to load scenarios');

        const scenarios = await response.json();
        scenarioSelect.innerHTML = '';
        scenarios.forEach(scenario => {
            const option = document.createElement('option');
            option.value = scenario.id;
            option.textContent = scenario.title;
            scenarioSelect.appendChild(option);
        });

        if (scenarios.length === 0) {
            scenarioSelect.innerHTML = '<option>No scenarios available</option>';
        }
    } catch (err) {
        console.error("Error loading scenarios:", err);
        scenarioSelect.innerHTML = '<option>Error loading scenarios</option>';
    } finally {
        btnRefreshScenarios.disabled = false;
    }
}

btnStartGame.onclick = async () => {
    const scenarioId = scenarioSelect.value;
    if (!scenarioId) {
        updateStatus("Please select a scenario first");
        return;
    }

    updateStatus("Starting game...");
    chatLog.innerHTML = "";
    resultsDiv.style.display = 'none';
    resultsDiv.innerHTML = "";
    updateTimerDisplay();

    try {
        const response = await fetch(`${API_URL}/api/v1/game/start/${scenarioId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: TEST_USER_ID })
        });

        if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);

        const data = await response.json();
        sessionId = data.session_id;
        updateStatus(`Game created!`);
        btnStartGame.disabled = true;
        btnConnect.disabled = false;
        scenarioSelect.disabled = true;
        btnRefreshScenarios.disabled = true;
        descriptionInput.disabled = true;
        btnGenerate.disabled = true;
        pendingAIMessage = data.conversation_history[0].message;

        // Fetch and display scenario details
        await displayScenarioInfo(scenarioId);
    } catch (err) {
        updateStatus(`Error: ${err.message}`);
        console.error("Fetch Error:", err);
    }
};

async function displayScenarioInfo(scenarioId) {
    try {
        const response = await fetch(`${API_URL}/api/v1/scenarios/`);
        if (!response.ok) throw new Error('Failed to load scenario info');

        const scenarios = await response.json();
        const scenario = scenarios.find(s => s.id === scenarioId);

        if (scenario && scenario.what_to_do) {
            const infoDiv = document.getElementById('scenarioInfo');
            infoDiv.innerHTML = `
                <h3>💡 What To Do</h3>
                <p>${scenario.what_to_do}</p>
            `;
            infoDiv.style.display = 'block';
        }
    } catch (err) {
        console.error("Error loading scenario info:", err);
    }
}

btnConnect.onclick = () => {
    if (!sessionId) {
        updateStatus("No session ID. Start a game first.");
        return;
    }

    updateStatus("Connecting...");
    socket = new WebSocket(`${WS_URL}/api/v1/game/ws/${sessionId}`);
    socket.binaryType = 'blob';

    socket.onopen = () => {
        updateStatus("Connected! AI will speak first.");
        btnConnect.disabled = true;
        btnEndGame.disabled = false;
        startTimer();
    };

    socket.onmessage = (event) => {
        if (typeof event.data === 'string') {
            handleJsonMessage(JSON.parse(event.data));
        } else {
            handleAudioChunk(event.data);
        }
    };

    socket.onerror = (err) => {
        updateStatus(`WebSocket Error`);
        console.error("WebSocket Error:", err);
        stopTimer();
    };

    socket.onclose = (event) => {
        updateStatus(`Closed. Code: ${event.code}`);
        enableAll(false);
        stopTimer();
    };
};

function handleJsonMessage(data) {
    console.log("JSON:", data);
    switch (data.status) {
        case "angry_spam_streak":
            updateStatus("⚠️ ANGRY SPAM INCOMING!");
            isSpamMode = true;
            spamQueue = [];
            btnPushToTalk.disabled = true;
            btnEndGame.disabled = true;
            showTypingIndicator();
            break;
        case "spam_message":
            spamQueue.push({ text: data.text, index: data.index, audio: null });
            break;
        case "spam_streak_complete":
            updateStatus("Processing spam...");
            playSpamStreak();
            break;
        case "ai_speaking":
            updateStatus("AI is speaking...");
            btnPushToTalk.disabled = true;
            btnEndGame.disabled = true;
            audioQueue = [];
            showTypingIndicator();
            break;
        case "ai_finished_speaking":
            updateStatus("Your turn. Hold to speak.");
            btnPushToTalk.disabled = false;
            btnEndGame.disabled = false;
            if (!isSpamMode) playFullAudio();
            break;
        case "ai_thinking":
            updateStatus("AI is thinking...");
            btnPushToTalk.disabled = true;
            btnEndGame.disabled = true;
            break;
        case "evaluating":
            updateStatus("Evaluating...");
            btnPushToTalk.disabled = true;
            btnEndGame.disabled = true;
            stopTimer();
            break;
        case "game_over":
            updateStatus("Game Over!");
            resultsDiv.innerHTML = `
                <h3>Score: ${data.score}/10</h3>
                <p><strong>Justification:</strong> ${data.justification}</p>
            `;
            resultsDiv.style.display = 'block';
            stopTimer();
            socket.close();
            break;
        case "user_response_text":
            addMessageToChat('user', data.text);
            break;
        case "ai_response_text":
            if (!data.text || !data.text.includes("BREAK")) {
                if (!isSpamMode) pendingAIMessage = data.text;
            }
            break;
        case "error":
            updateStatus(`Error: ${data.message}`);
            break;
    }
}

function handleAudioChunk(audioChunk) {
    if (isSpamMode && spamQueue.length > 0) {
        for (let i = 0; i < spamQueue.length; i++) {
            if (!spamQueue[i].audio) {
                spamQueue[i].audio = audioChunk;
                break;
            }
        }
    } else {
        audioQueue.push(audioChunk);
    }
}

function playFullAudio() {
    if (audioQueue.length === 0) return;
    const fullAudioBlob = new Blob(audioQueue, { type: 'audio/wav' });
    audioPlayer.src = URL.createObjectURL(fullAudioBlob);

    audioPlayer.onplay = () => {
        hideTypingIndicator();
        pauseTimer();
        if (pendingAIMessage) {
            addMessageToChat('ai', pendingAIMessage);
            pendingAIMessage = '';
        }
    };

    audioPlayer.onended = () => resumeTimer();
    audioPlayer.play().catch(e => console.error("Audio error:", e));
    audioQueue = [];
}

async function playSpamStreak() {
    hideTypingIndicator();
    pauseTimer();

    for (let spam of spamQueue) {
        addMessageToChat('ai', spam.text, true);

        if (spam.audio) {
            audioPlayer.src = URL.createObjectURL(new Blob([spam.audio], { type: 'audio/wav' }));
            await new Promise((resolve) => {
                audioPlayer.onended = resolve;
                audioPlayer.play().catch(e => { console.error("Spam audio error:", e); resolve(); });
            });
            await new Promise(r => setTimeout(r, 200));
        }
    }

    isSpamMode = false;
    spamQueue = [];
    resumeTimer();
    updateStatus("Your turn. Hold to speak.");
    btnPushToTalk.disabled = false;
    btnEndGame.disabled = false;
}

btnPushToTalk.onmousedown = async () => {
    if (!socket) return;

    if (!audioPlayer.paused) {
        console.log("🚫 Interrupting AI");
        audioPlayer.pause();
        audioPlayer.currentTime = 0;
        resumeTimer();
    }

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        micStream = stream;
        await initMicVisualizer(stream);

        mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });

        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0 && socket.readyState === WebSocket.OPEN) {
                socket.send(event.data);
            }
        };

        mediaRecorder.onstop = () => {
            if (socket.readyState === WebSocket.OPEN) {
                sendJson({ action: "stop_speaking" });
            }
            stream.getTracks().forEach(track => track.stop());
            stopMicVisualizer();
        };

        mediaRecorder.start(500);
        sendJson({ action: "start_speaking" });
        updateStatus("Listening... Release to stop.");

    } catch (err) {
        updateStatus(`Mic error: ${err.message}`);
        console.error("Microphone Error:", err);
    }
};

btnPushToTalk.onmouseup = () => {
    if (mediaRecorder) {
        mediaRecorder.stop();
        updateStatus("AI is thinking...");
    }
};

btnEndGame.onclick = () => endGame();

function startTimer() {
    timeLeft = 120;
    isTimerPaused = false;
    updateTimerDisplay();
    stopTimer();

    timerInterval = setInterval(() => {
        if (!isTimerPaused) {
            timeLeft--;
            updateTimerDisplay();

            if (timeLeft <= 30) {
                timerDiv.classList.add('low');
            }

            if (timeLeft <= 0) {
                console.log("Timer finished");
                stopTimer();
                endGame(true);
            }
        }
    }, 1000);
}

function stopTimer() {
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
    timeLeft = 120;
    isTimerPaused = false;
    timerDiv.classList.remove('low');
}

function pauseTimer() {
    console.log("⏸️ Timer paused");
    isTimerPaused = true;
}

function resumeTimer() {
    console.log("▶️ Timer resumed");
    isTimerPaused = false;
}

function updateTimerDisplay() {
    const minutes = Math.floor(timeLeft / 60);
    const seconds = timeLeft % 60;
    const pauseIndicator = isTimerPaused ? ' ⏸️' : '';
    timerDiv.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}${pauseIndicator}`;
}

function endGame(isAutoEnd = false) {
    if (isAutoEnd) {
        updateStatus("Time's up! Evaluating...");
    } else {
        console.log("User clicked End Game");
    }
    sendJson({ action: "end_game" });
    btnPushToTalk.disabled = true;
    btnEndGame.disabled = true;
}

function addMessageToChat(role, text, isSpam = false) {
    const msgDiv = document.createElement('div');
    msgDiv.classList.add('message', role);
    if (isSpam) msgDiv.classList.add('spam');
    msgDiv.textContent = text;
    chatLog.appendChild(msgDiv);
    chatLog.scrollTop = chatLog.scrollHeight;
}

function showTypingIndicator() {
    hideTypingIndicator();
    typingIndicator = document.createElement('div');
    typingIndicator.classList.add('typing-indicator');
    typingIndicator.innerHTML = '<span></span><span></span><span></span>';
    chatLog.appendChild(typingIndicator);
    chatLog.scrollTop = chatLog.scrollHeight;
}

function hideTypingIndicator() {
    if (typingIndicator && typingIndicator.parentNode) {
        typingIndicator.parentNode.removeChild(typingIndicator);
        typingIndicator = null;
    }
}

function sendJson(data) {
    if (socket && socket.readyState === WebSocket.OPEN) {
        console.log("Sending JSON:", data);
        socket.send(JSON.stringify(data));
    }
}

function updateStatus(message) {
    console.log("Status:", message);
    statusDiv.textContent = message;
}

function enableAll(all = true) {
    if (all) {
        btnStartGame.disabled = false;
        scenarioSelect.disabled = false;
        btnRefreshScenarios.disabled = false;
        descriptionInput.disabled = false;
        btnGenerate.disabled = descriptionInput.value.length < 10;
    }
    btnConnect.disabled = true;
    btnPushToTalk.disabled = true;
    btnEndGame.disabled = true;

    if (all) {
        // Clear both canvases
        ctxLeft.clearRect(0, 0, canvasLeft.width, canvasLeft.height);
        ctxRight.clearRect(0, 0, canvasRight.width, canvasRight.height);

        // Reset AI analyser
        aiAnalyser = null;
        aiDataArray = null;
    }
}