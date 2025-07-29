(function () {
  function setCookie(name, value, days) {
    let expires = "";
    if (days) {
      const date = new Date();
      date.setTime(date.getTime() + days * 24 * 60 * 60 * 1000);
      expires = "; expires=" + date.toUTCString();
    }
    document.cookie = name + "=" + (value || "") + expires + "; path=/";
  }

  function getCookie(name) {
    const nameEQ = name + "=";
    const ca = document.cookie.split(";");
    for (let i = 0; i < ca.length; i++) {
      let c = ca[i];
      while (c.charAt(0) === " ") c = c.substring(1, c.length);
      if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
    }
    return null;
  }

  let dismissedMessages = (getCookie("dissmissed-system-messages") || "").split(
    "|"
  );

  const messages = Array.from(
    document.getElementsByClassName("system-message")
  );

  window.addEventListener("load", function () {
    messages.forEach(function (message) {
      const messageId = message.getAttribute("data-id");
      const isDismissable = message.getAttribute("data-dismissable");

      // In case dismissable attribute changed after user dismissed it
      if (!isDismissable) {
        message.classList.remove("hidden");
        return;
      }

      if (!dismissedMessages.includes(messageId)) {
        message.classList.remove("hidden");
        const dismissButton = message.getElementsByClassName(
          "dismiss-system-message"
        );
        if (!dismissButton.length) {
          return;
        }
        dismissButton[0].addEventListener("click", function () {
          dismissedMessages.push(messageId);
          setCookie(
            "dissmissed-system-messages",
            dismissedMessages.join("|"),
            30
          );
          message.classList.add("hidden");
        });
      }
    });
  });
})();
