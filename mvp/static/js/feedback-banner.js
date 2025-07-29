(function () {
  function setCookie(name, value, days) {
    let expires = "";
    if (days) {
      const date = new Date();
      date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
      expires = "; expires=" + date.toUTCString();
    }
    document.cookie = name + "=" + (value || "")  + expires + "; path=/";
  }

  function getCookie(name) {
    const nameEQ = name + "=";
    const ca = document.cookie.split(';');
    for (let i = 0; i < ca.length; i++) {
      let c = ca[i];
      while (c.charAt(0) === ' ') c = c.substring(1, c.length);
      if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
    }
    return null;
  }

  document.getElementById('close-feedback-banner').addEventListener('click', function() {
    setCookie('feedback-banner-dismissed', 'true', 30);
    document.getElementById('feedback-banner').classList.add('hidden');
  });

  window.addEventListener("load", function() {
    if (getCookie('feedback-banner-dismissed') !== 'true') {
      document.getElementById('feedback-banner').classList.remove('hidden');
    }
  });
})();
