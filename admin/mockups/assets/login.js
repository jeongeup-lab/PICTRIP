// Login page: reveal the error banner when redirected back with ?error=1.
(function () {
  const params = new URLSearchParams(location.search);
  if (params.get("error")) {
    const el = document.getElementById("login-error");
    if (el) el.style.display = "";
  }
})();
