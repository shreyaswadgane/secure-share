/**
 * Secure Share - Dashboard Analytics & Activity Feed JavaScript
 */

document.addEventListener('DOMContentLoaded', () => {
  loadDashboardData();
});

async function loadDashboardData() {
  const statSent = document.getElementById('stat-sent');
  const statReceived = document.getElementById('stat-received');
  const statActive = document.getElementById('stat-active');
  const statStorage = document.getElementById('stat-storage');
  const activityTableBody = document.getElementById('activity-table-body');
  const activityEmpty = document.getElementById('activity-empty');

  try {
    const res = await fetch('/api/dashboard');
    if (res.status === 401) {
      window.location.href = '/login';
      return;
    }
    const data = await res.json();

    if (data.success) {
      const stats = data.stats;
      if (statSent) statSent.textContent = stats.total_sent;
      if (statReceived) statReceived.textContent = stats.total_received;
      if (statActive) statActive.textContent = stats.active_shares;
      if (statStorage) statStorage.textContent = formatBytes(stats.total_storage_bytes);

      const logs = data.recent_activity;
      if (!logs || logs.length === 0) {
        if (activityTableBody) activityTableBody.innerHTML = '';
        if (activityEmpty) activityEmpty.style.display = 'block';
        return;
      }

      if (activityEmpty) activityEmpty.style.display = 'none';

      const actionBadge = (action) => {
        switch (action) {
          case 'UPLOAD':
            return '<span class="badge badge-info">Uploaded</span>';
          case 'DOWNLOAD':
            return '<span class="badge badge-active">Downloaded</span>';
          case 'REVOKE':
            return '<span class="badge badge-warning">Revoked</span>';
          case 'DELETE':
            return '<span class="badge badge-revoked">Deleted</span>';
          case 'REGISTER':
            return '<span class="badge badge-active">Joined</span>';
          case 'LOGIN':
            return '<span class="badge badge-info">Session</span>';
          default:
            return `<span class="badge">${action}</span>`;
        }
      };

      if (activityTableBody) {
        activityTableBody.innerHTML = logs.map(log => `
          <tr>
            <td>${actionBadge(log.action)}</td>
            <td><strong>${escapeHtml(log.file_name || '-')}</strong></td>
            <td style="color: var(--text-muted); font-size: 0.88rem;">${escapeHtml(log.details || '-')}</td>
            <td>${formatDate(log.timestamp)}</td>
          </tr>
        `).join('');
      }
    } else {
      showToast(data.error || 'Failed to load dashboard data.', 'error');
    }
  } catch (err) {
    showToast('Failed to connect to server.', 'error');
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
}
