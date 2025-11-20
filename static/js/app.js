const dropZone = document.getElementById('dropZone');
const videoInput = document.getElementById('videoInput');
const uploadCard = document.getElementById('uploadCard');
const statusCard = document.getElementById('statusCard');
const resultCard = document.getElementById('resultCard');
const statusTitle = document.getElementById('statusTitle');
const statusMessage = document.getElementById('statusMessage');
const resultVideo = document.getElementById('resultVideo');
const downloadBtn = document.getElementById('downloadBtn');
const resetBtn = document.getElementById('resetBtn');
const errorResetBtn = document.getElementById('errorResetBtn');
const spinner = document.getElementById('spinner');
const progressBar = document.getElementById('progressBar');

// Drag and drop handlers
dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
});

dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('dragover');
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    if (e.dataTransfer.files.length) {
        handleFile(e.dataTransfer.files[0]);
    }
});

dropZone.addEventListener('click', () => {
    videoInput.click();
});

videoInput.addEventListener('change', (e) => {
    if (e.target.files.length) {
        handleFile(e.target.files[0]);
    }
});

resetBtn.addEventListener('click', resetUI);
errorResetBtn.addEventListener('click', resetUI);

function resetUI() {
    resultCard.classList.add('hidden');
    statusCard.classList.add('hidden');
    uploadCard.classList.remove('hidden');
    videoInput.value = '';

    // Reset status card state
    spinner.classList.remove('hidden');
    progressBar.classList.remove('hidden');
    errorResetBtn.classList.add('hidden');
    statusTitle.textContent = 'Processing...';
    statusTitle.classList.remove('error-text');
}

async function handleFile(file) {
    if (!file.type.startsWith('video/')) {
        alert('Please upload a video file.');
        return;
    }

    // Show status, hide upload
    uploadCard.classList.add('hidden');
    statusCard.classList.remove('hidden');
    statusTitle.textContent = 'Uploading...';
    statusMessage.textContent = 'Sending video to server...';

    // Ensure clean state
    spinner.classList.remove('hidden');
    progressBar.classList.remove('hidden');
    errorResetBtn.classList.add('hidden');
    statusTitle.classList.remove('error-text');

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) throw new Error('Upload failed');

        const data = await response.json();
        pollStatus(data.job_id);

    } catch (error) {
        console.error(error);
        showError('Error uploading video: ' + error.message);
    }
}

async function pollStatus(jobId) {
    statusTitle.textContent = 'Processing...';

    const poll = setInterval(async () => {
        try {
            const response = await fetch(`/api/status/${jobId}`);
            const data = await response.json();

            statusMessage.textContent = data.message;

            if (data.status === 'completed') {
                clearInterval(poll);
                showResult(data);
            } else if (data.status === 'failed') {
                clearInterval(poll);
                showError(data.message);
            }
        } catch (error) {
            console.error(error);
            clearInterval(poll);
            showError('Error checking status');
        }
    }, 2000);
}

function showError(message) {
    spinner.classList.add('hidden');
    progressBar.classList.add('hidden');
    errorResetBtn.classList.remove('hidden');

    statusTitle.textContent = 'Failed';
    statusTitle.classList.add('error-text');
    statusMessage.textContent = message;
}

function showResult(data) {
    statusCard.classList.add('hidden');
    resultCard.classList.remove('hidden');

    resultVideo.src = data.download_url;
    downloadBtn.href = data.download_url;
}
