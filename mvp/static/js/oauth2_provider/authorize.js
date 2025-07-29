(function () {
  document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("authorization-form");

    form.addEventListener("submit", (_event) => {
      var buttonClicked = _event.submitter;
      document.getElementById("submit-buttons-container").classList.add("hidden");

      var messageId = buttonClicked.name === "allow" ? "allow-message" : "cancel-message";
      document.getElementById(messageId).classList.remove("hidden");
    });
  });
})();
