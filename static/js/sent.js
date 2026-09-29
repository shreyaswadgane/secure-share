/**
 * Secure Share - Sent Files Management JavaScript
 * Allows senders to inspect active shares, check download limits, and revoke/delete access.
 */

document.addEventListener('DOMContentLoaded', () => {
  loadSentFiles();
});

async function loadSentFiles() {
  const tableBody = document.getElementById('sent-table-body');
  const emptyState = document.getElementById('sent-empty');

  try {
    const res = await fetch('/api/files/sent');
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
          if (!share.is_active) {
            statusBadge = '<span class="badge badge-revoked">Revoked</span>';
          } else if (share.is_expired) {
            statusBadge = '<span class="badge badge-expired">Expired</span>';
          } else if (share.max_downloads && share.download_count >= share.max_downloads) {
            statusBadge = '<span class="badge badge-warning">Limit Reached</span>';
          } else {
            statusBadge = '<span class="badge badge-active">Active</span>';
          }

          const dlLimit = share.max_downloads ? `${share.download_count} / ${share.max_downloads}` : `${share.download_count} (Unlimited)`;

          return `
            <tr>
              <td>
                <div style="font-weight: 600; color: var(--text-main);">${escapeHtml(share.file_name)}</div>
                <div style="font-size: 0.82rem; color: var(--text-muted);">${formatBytes(share.file_size)}</div>
              </td>
              <td>
                <div>${escapeHtml(share.receiver_name || 'User')}</div>
                <div style="font-size: 0.82rem; color: var(--text-muted);">${escapeHtml(share.receiver_email)}</div>
              </td>
              <td>${formatDate(share.expires_at)}</td>
              <td><span class="badge badge-info">${dlLimit}</span></td>
              <td>${statusBadge}</td>
              <td>
                <div style="display: flex; gap: 0.5rem;">
                  ${share.is_active && !share.is_expired ? `
                    <button class="btn btn-secondary btn-sm" onclick="revokeShare(${share.id})">Revoke</button>
                  ` : ''}
                  <button class="btn btn-danger btn-sm" onclick="deleteShare(${share.id})">Delete</button>
                </div>
              </td>
            </tr>
          `;
        }).join('');
      }
    } else {
      showToast(data.error || 'Failed to load sent files.', 'error');
    }
  } catch (err) {
    showToast('Failed to connect to server.', 'error');
  }
}

async function revokeShare(shareId) {
  if (!confirm('Are you sure you want to revoke access to this file? The recipient will no longer be able to download it.')) {
    return;
  }

  try {
    const res = await fetch(`/api/share/${shareId}?action=revoke`, { method: 'DELETE' });
    const data = await res.json();
    if (data.success) {
      showToast(data.message, 'success');
      loadSentFiles();
    } else {
      showToast(data.error || 'Failed to revoke share.', 'error');
    }
  } catch (err) {
    showToast('Network error while revoking share.', 'error');
  }
}

async function deleteShare(shareId) {
  if (!confirm('Are you sure you want to permanently delete this shared file? This action cannot be undone.')) {
    return;
  }

  try {
    const res = await fetch(`/api/share/${shareId}?action=delete`, { method: 'DELETE' });
    const data = await res.json();
    if (data.success) {
      showToast(data.message, 'success');
      loadSentFiles();
    } else {
      showToast(data.error || 'Failed to delete share.', 'error');
    }
  } catch (err) {
    showToast('Network error while deleting share.', 'error');
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
