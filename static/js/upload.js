/**
 * Secure Share - File Upload & Encryption JavaScript
 * Features drag-and-drop, recipient search, security options, and progress bar.
 */

document.addEventListener('DOMContentLoaded', () => {
  const dropzone = document.getElementById('upload-dropzone');
  const fileInput = document.getElementById('file-input');
  const filePreview = document.getElementById('file-preview');
  const previewName = document.getElementById('preview-name');
  const previewSize = document.getElementById('preview-size');
  const removeFileBtn = document.getElementById('remove-file-btn');
  const uploadForm = document.getElementById('upload-form');
  const progressContainer = document.getElementById('upload-progress-container');
  const progressBarFill = document.getElementById('progress-bar-fill');
  const progressPercentage = document.getElementById('progress-percentage');
  const progressStatus = document.getElementById('progress-status');
  const recipientInput = document.getElementById('recipient-input');
  const recipientSuggestions = document.getElementById('recipient-suggestions');
  const submitBtn = document.getElementById('upload-submit-btn');

  let selectedFile = null;

  // 1. Drag & Drop Events
  if (dropzone) {
    dropzone.addEventListener('click', () => fileInput.click());

    ['dragenter', 'dragover'].forEach(eventName => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
      });
    });

    ['dragleave', 'drop'].forEach(eventName => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
      });
    });

    dropzone.addEventListener('drop', (e) => {
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        handleFileSelection(e.dataTransfer.files[0]);
      }
    });
  }

  // 2. File Input Change Event
  if (fileInput) {
    fileInput.addEventListener('change', () => {
      if (fileInput.files && fileInput.files.length > 0) {
        handleFileSelection(fileInput.files[0]);
      }
    });
  }

  function handleFileSelection(file) {
    // 25MB check on client side
    const maxBytes = 25 * 1024 * 1024;
    if (file.size > maxBytes) {
      showToast('File exceeds 25 MB limit.', 'error');
      return;
    }
    selectedFile = file;
    previewName.textContent = file.name;
    previewSize.textContent = formatBytes(file.size);
    filePreview.style.display = 'flex';
    dropzone.style.display = 'none';
  }

  if (removeFileBtn) {
    removeFileBtn.addEventListener('click', () => {
      selectedFile = null;
      fileInput.value = '';
      filePreview.style.display = 'none';
      dropzone.style.display = 'block';
    });
  }

  // 3. Recipient Autocomplete / Search
  let searchTimeout = null;
  if (recipientInput && recipientSuggestions) {
    recipientInput.addEventListener('input', () => {
      clearTimeout(searchTimeout);
      const query = recipientInput.value.trim();
      if (query.length < 2) {
        recipientSuggestions.style.display = 'none';
        return;
      }

      searchTimeout = setTimeout(async () => {
        try {
          const res = await fetch(`/api/users/search?q=${encodeURIComponent(query)}`);
          const data = await res.json();
          if (data.users && data.users.length > 0) {
            recipientSuggestions.innerHTML = data.users.map(u => `
              <div class="suggestion-item" data-email="${u.email}" style="padding: 0.6rem 1rem; cursor: pointer; border-bottom: 1px solid var(--border-color);">
                <strong>${escapeHtml(u.name)}</strong>
                <span style="color: var(--text-muted); font-size: 0.85rem; margin-left: 0.5rem;">(${escapeHtml(u.email)})</span>
              </div>
            `).join('');
            recipientSuggestions.style.display = 'block';

            recipientSuggestions.querySelectorAll('.suggestion-item').forEach(item => {
              item.addEventListener('click', () => {
                recipientInput.value = item.dataset.email;
                recipientSuggestions.style.display = 'none';
              });
            });
          } else {
            recipientSuggestions.style.display = 'none';
          }
        } catch (err) {
          recipientSuggestions.style.display = 'none';
        }
      }, 250);
    });

    document.addEventListener('click', (e) => {
      if (!recipientInput.contains(e.target) && !recipientSuggestions.contains(e.target)) {
        recipientSuggestions.style.display = 'none';
      }
    });
  }

  // 4. Form Submission with XMLHttpRequest Progress Bar
  if (uploadForm) {
    uploadForm.addEventListener('submit', (e) => {
      e.preventDefault();

      if (!selectedFile) {
        showToast('Please select a file to encrypt and upload.', 'error');
        return;
      }

      const recipient = recipientInput.value.trim();
      if (!recipient) {
        showToast('Please specify a recipient email or username.', 'error');
        return;
      }

      const expiry = document.getElementById('expiry-select').value;
      const maxDownloads = document.getElementById('max-downloads-select').value;
      const filePassword = document.getElementById('file-password-input').value.trim();

      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('recipient', recipient);
      formData.append('expiry', expiry);
      formData.append('max_downloads', maxDownloads);
      if (filePassword) {
        formData.append('password', filePassword);
      }

      // UI update for upload progress
      submitBtn.disabled = true;
      progressContainer.style.display = 'block';
      progressBarFill.style.width = '0%';
      progressPercentage.textContent = '0%';
      progressStatus.textContent = 'Encrypting & Uploading...';

      const xhr = new XMLHttpRequest();
      xhr.open('POST', '/api/upload', true);

      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          const percent = Math.round((event.loaded / event.total) * 100);
          progressBarFill.style.width = percent + '%';
          progressPercentage.textContent = percent + '%';
        }
      };

      xhr.onload = () => {
        submitBtn.disabled = false;
        try {
          const res = JSON.parse(xhr.responseText);
          if (xhr.status === 201 && res.success) {
            progressStatus.textContent = 'Completed!';
            progressBarFill.style.width = '100%';
            showToast('File encrypted and shared successfully!', 'success');
            setTimeout(() => {
              window.location.href = '/sent';
            }, 1000);
          } else {
            progressContainer.style.display = 'none';
            showToast(res.error || 'Upload failed.', 'error');
          }
        } catch (err) {
          progressContainer.style.display = 'none';
          showToast('Unexpected server response.', 'error');
        }
      };

      xhr.onerror = () => {
        submitBtn.disabled = false;
        progressContainer.style.display = 'none';
        showToast('Network error during file upload.', 'error');
      };

      xhr.send(formData);
    });
  }
});

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
