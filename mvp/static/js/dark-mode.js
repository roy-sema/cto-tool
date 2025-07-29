(function () {
  var localStorageKey = 'color-theme'

  var systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

  function isDark() {
    var userPreference = localStorage.getItem(localStorageKey);
    return userPreference == 'dark' || (
      systemPrefersDark && (!userPreference || userPreference == 'system')
    );
  }

  function setTheme() {
    if (isDark()) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }

  setTheme();

  window.addEventListener("load", function () {
    var buttons = {
      dark: document.getElementById('dark-mode-btn-dark'),
      light: document.getElementById('dark-mode-btn-light'),
      system: document.getElementById('dark-mode-btn-system')
    };

    var darkFlag = document.getElementById('dark-mode-flag-dark');
    var lightFlag = document.getElementById('dark-mode-flag-light');

    function setFlags() {
      if (isDark()) {
        darkFlag?.classList.remove('hidden');
        lightFlag?.classList.add('hidden');
      } else {
        darkFlag?.classList.add('hidden');
        lightFlag?.classList.remove('hidden');
      }
    }

    function setButtons() {
      var userPreference = localStorage.getItem(localStorageKey);
      var currentTheme = userPreference || 'system';

      Object.entries(buttons).forEach(function ([theme, btn]) {
        if (theme == currentTheme) {
          btn?.classList.add("bg-blue", "text-white");
          btn?.classList.remove("bg-white", "dark:bg-slate-900");
        } else {
          btn?.classList.remove("bg-blue", "text-white");
          btn?.classList.add("bg-white", "dark:bg-slate-900");
        }
      });
    };

    Object.entries(buttons).forEach(function ([theme, btn]) {
      btn?.addEventListener('click', function () {
        localStorage.setItem(localStorageKey, theme);
        setTheme();
        setFlags();
        setButtons();
      });
    });

    setFlags();
    setButtons();
  });
})();
