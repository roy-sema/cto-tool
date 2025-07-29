(function () {
  window.addEventListener("load", function() {
    if (window.te) {
      window.te.Popover.Default.allowList['svg'] = ['viewBox', 'width', 'height', 'style'];
      window.te.Popover.Default.allowList['path'] = ['d'];
    }
  });
})();
