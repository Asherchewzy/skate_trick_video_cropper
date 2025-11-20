const dropZone = document.getElementById('dropZone');
const videoInput = document.getElementById('videoInput');
const uploadCard = document.getElementById('uploadCard');
const statusCard = document.getElementById('statusCard');
const resultCard = document.getElementById('resultCard');
const statusTitle = document.getElementById('statusTitle');
const statusMessage = document.getElementById('statusMessage');
const fileStatusList = document.getElementById('fileStatusList');
const resultVideo = document.getElementById('resultVideo');
const downloadList = document.getElementById('downloadList');
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
        handleFiles(Array.from(e.dataTransfer.files));
    }
});

dropZone.addEventListener('click', () => {
    videoInput.click();
});

videoInput.addEventListener('change', (e) => {
    if (e.target.files.length) {
        handleFiles(Array.from(e.target.files));
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
    statusMessage.textContent = 'Initializing...';
    fileStatusList.innerHTML = '';
    downloadList.innerHTML = '';
    resultVideo.src = '';
    resultVideo.classList.remove('hidden');
}

async function handleFiles(files) {
    if (!files || !files.length) {
        return;
    }

    const nonVideo = files.find((file) => !file.type.startsWith('video/'));
    if (nonVideo) {
        alert('Please upload only video files.');
        return;
    }

    // Show status, hide upload
    uploadCard.classList.add('hidden');
    statusCard.classList.remove('hidden');
    statusTitle.textContent = 'Uploading...';
    statusMessage.textContent = 'Sending videos to server...';

    // Ensure clean state
    spinner.classList.remove('hidden');
    progressBar.classList.remove('hidden');
    errorResetBtn.classList.add('hidden');
    statusTitle.classList.remove('error-text');

    const formData = new FormData();
    files.forEach((file) => formData.append('files', file));

    try {
        const response = await fetch('/api/upload/batch', {
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

            statusMessage.textContent = data.message || 'Processing...';
            renderFileStatus(data.items || []);

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

function renderFileStatus(items) {
    fileStatusList.innerHTML = '';
    items.forEach((item) => {
        const li = document.createElement('li');
        const message = item.message ? ` — ${item.message}` : '';
        li.textContent = `${item.filename}: ${item.status}${message}`;
        fileStatusList.appendChild(li);
    });
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

    const completedItems = (data.items || []).filter(
        (item) => item.status === 'completed' && item.download_url
    );

    downloadList.innerHTML = '';

    if (completedItems.length) {
        resultVideo.classList.remove('hidden');
        resultVideo.src = completedItems[0].download_url;
    } else {
        resultVideo.classList.add('hidden');
    }

    (data.items || []).forEach((item) => {
        const container = document.createElement('div');
        if (item.status === 'completed' && item.download_url) {
            const link = document.createElement('a');
            link.className = 'btn primary-btn';
            link.href = item.download_url;
            link.download = item.filename || 'highlight.mp4';
            link.textContent = `Download: ${item.filename}`;
            container.appendChild(link);
        } else if (item.status === 'failed') {
            container.textContent = `${item.filename} failed: ${item.message || ''}`;
        } else {
            container.textContent = `${item.filename}: ${item.status}`;
        }
        downloadList.appendChild(container);
    });
}
