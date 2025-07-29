(function() {
  const btn = document.getElementById('download-gbom');
  if (!btn) {
    return;
  }

  const pollTime = 1000;
  const maxWait = 2000;

  const url = btn.href;

  const idle = btn.querySelector('.download-indicator-idle');
  const loading = btn.querySelector('.download-indicator-loading');
  const success = btn.querySelector('.download-indicator-success');
  const error = btn.querySelector('.download-indicator-error');
  const emailMessage = btn.querySelector('.download-email-message');

  var status = idle;

  const indicators = [idle, loading, success, error]

  function showIndicator(indicator) {
    indicators.forEach(i => {
      if (i === indicator) {
        i.classList.remove('hidden');
      } else {
        i.classList.add('hidden');
      }
    });
    status = indicator;
  }

  var waitTime = 0;
  function checkGBOMStatus() {
    fetch(url)
      .then(response => response.json())
      .then(data => {
        if (data.status === 'ready') {
          window.location.href = btn.href + '?download=true';
          showIndicator(success);
        } else if (data.status === 'processing') {
          if (waitTime > maxWait) {
            emailMessage.classList.remove('hidden');
          }
          setTimeout(checkGBOMStatus, pollTime);
          waitTime += pollTime;
        }
      })
      .catch(error => {
        console.error('Error:', error);
        showIndicator(error);
      });
  }

  btn.addEventListener('click', function(e) {
    e.preventDefault();
    if (status !== idle) {
      return;
    }

    showIndicator(loading);
    checkGBOMStatus();
  });
})();
