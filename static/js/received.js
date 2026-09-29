/**
 * Secure Share - Received Files & Decrypted Download JavaScript
 * Handles inspecting incoming shared files, password prompting, and on-the-fly decryption streaming.
 */

let activeDownloadShareId = null;

document.addEventListener('DOMContentLoaded', () => {
  loadReceivedFiles();

  // Password Prompt Modal Submit Handler
  const passwordForm = document.getElementById('password-prompt-form');
  if (passwordForm) {
    passwordForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const pwd = document.getElementById('modal-share-password').value;
      if (!pwd) {
        showToast('Please enter the file password.', 'error');
        return;
      }
      closeModal('password-modal');
      document.getElementById('modal-share-password').value = '';
      if (activeDownloadShareId) {
        triggerDownload(activeDownloadShareId, pwd);
      }
    });
  }
});

async function loadReceivedFiles() {
  const tableBody = document.getElementById('received-table-body');
  const emptyState = document.getElementById('received-empty');

  try {
    const res = await fetch('/api/files/received');
    if (res.status === 401) {
      window.location.href = '/login';
      return;
    }
    const data = await res.json();

    if (data.success) {
      const shares = data.shares;
      if (!shares || shares.length === 0) {
        if (tableBody) tableBody.innerHTML = '';
        if (emptyState) emptyState.style.display = 'block';
        return;
      }

      if (emptyState) emptyState.style.display = 'none';

      if (tableBody) {
        tableBody.innerHTML = shares.map(share => {
          let statusBadge = '';
          let canDownload = true;

          if (!share.is_active) {
            statusBadge = '<span class="badge badge-revoked">Revoked</span>';
            canDownload = false;
          } else if (share.is_expired) {
            statusBadge = '<span class="badge badge-expired">Expired</span>';
            canDownload = false;
          } else if (share.max_downloads && share.download_count >= share.max_downloads) {
            statusBadge = '<span class="badge badge-warning">Limit Reached</span>';
            canDownload = false;
          } else {
            statusBadge = '<span class="badge badge-active">Available</span>';
          }

          const dlCount = share.max_downloads ? `${share.download_count} / ${share.max_downloads}` : `${share.download_count} (No Limit)`;
          const pwdLock = share.has_password ? '<span title="Password Protected" style="color: var(--accent-cyan); margin-left: 0.35rem;">🔒</span>' : '';

          return `
            <tr>
              <td>
                <div style="font-weight: 600; color: var(--text-main); display: flex; align-items: center;">
                  ${escapeHtml(share.file_name)} ${pwdLock}
                </div>
                <div style="font-size: 0.82rem; color: var(--text-muted);">${formatBytes(share.file_size)}</div>
              </td>
              <td>
                <div>${escapeHtml(share.sender_name || 'User')}</div>
                <div style="font-size: 0.82rem; color: var(--text-muted);">${escapeHtml(share.sender_email)}</div>
              </td>
              <td>${formatDate(share.expires_at)}</td>
              <td><span class="badge badge-info">${dlCount}</span></td>
              <td>${statusBadge}</td>
              <td>
                ${canDownload ? `
                  <button class="btn btn-primary btn-sm" onclick="initiateDownload(${share.id}, ${share.has_password})">
                    ⬇ Decrypt & Download
                  </button>
                ` : `
                  <button class="btn btn-secondary btn-sm" disabled style="opacity: 0.5; cursor: not-allowed;">
                    Unavailable
                  </button>
                `}
              </td>
            </tr>
          `;
        }).join('');
      }
    } else {
      showToast(data.error || 'Failed to load received files.', 'error');
    }
  } catch (err) {
    showToast('Failed to connect to server.', 'error');
  }
}

function initiateDownload(shareId, hasPassword) {
  if (hasPassword) {
    activeDownloadShareId = shareId;
    openModal('password-modal');
  } else {
    triggerDownload(shareId, null);
  }
}

async function triggerDownload(shareId, password) {
  showToast('Decrypting file on server...', 'info');

  try {
    const url = `/api/download/${shareId}`;
    const options = { method: 'POST', headers: {} };

    if (password) {
      options.headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify({ password: password });
    }

    const res = await fetch(url, options);

    if (!res.ok) {
      const data = await res.json().catch(() => ({ error: 'Download failed.' }));
      showToast(data.error || 'Download failed.', 'error');
      return;
    }

    // Extract filename from Content-Disposition header if available
    const disposition = res.headers.get('Content-Disposition');
    let filename = 'downloaded_file';
    if (disposition && disposition.indexOf('filename=') !== -1) {
      const matches = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/.exec(disposition);
      if (matches != null && matches[1]) {
        filename = matches[1].replace(/['"]/g, '');
      }
    }

    const blob = await res.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = downloadUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(downloadUrl);
    a.remove();

    showToast(`Decrypted and downloaded '${filename}' successfully!`, 'success');
    loadReceivedFiles(); // Refresh count
  } catch (err) {
    showToast('Network error during file download.', 'error');
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
