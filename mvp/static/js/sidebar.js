(function () {
  window.addEventListener("load", function() {
    const main = document.getElementById('main-container');
    const sidebar = document.getElementById('sidebar-container');
    const openBtn = document.getElementById('sidebar-open');
    const closeBtn = document.getElementById('sidebar-close');

    if (openBtn) {
      openBtn.addEventListener('click', function() {
        sidebar?.classList.remove('hidden');
        main?.classList.add('hidden');
      });
    }

    if (closeBtn) {
      closeBtn.addEventListener('click', function() {
        main?.classList.remove('hidden');
        sidebar?.classList.add('hidden');
      });
    }
  });
})();
