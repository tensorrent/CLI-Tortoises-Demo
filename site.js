// site.js — the landing page's script (kept out of the page, so its Content-Security-Policy can allow scripts from this site only)
(function () {
  // someone with a saved game in this browser goes straight back to it
  var saved = false;
  try { saved = !!localStorage.getItem("cli-tortoises.v3"); } catch (e) { saved = false; }
  if (saved) {
    document.querySelectorAll("[data-play]").forEach(function (a) {
      a.setAttribute("href", "game.html");
      var s = a.querySelector("span"); if (s && a.id === "play") s.textContent = "Continue your island";
    });
  }

  // the Play bar on a phone shows while neither of the page's own Play buttons is in sight
  var dock = document.getElementById("dock"), seen = {};
  if (dock && "IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) { seen[e.target.id] = e.isIntersecting; });
      dock.classList.toggle("on", !seen.play && !seen.play2);
    }, { threshold: 0 });
    ["play", "play2"].forEach(function (id) { var el = document.getElementById(id); if (el) io.observe(el); });
  }

  // the cast's voices: one at a time, from the game's own recordings
  var playing = null, btnOn = null;
  document.querySelectorAll("[data-voice]").forEach(function (b) {
    b.addEventListener("click", function () {
      if (btnOn === b && playing && !playing.paused) { playing.pause(); b.classList.remove("on"); btnOn = null; return; }
      if (playing) playing.pause();
      if (btnOn) btnOn.classList.remove("on");
      playing = new Audio(b.getAttribute("data-voice")); btnOn = b; b.classList.add("on");
      playing.addEventListener("ended", function () { b.classList.remove("on"); if (btnOn === b) btnOn = null; });
      playing.play().catch(function () { b.classList.remove("on"); btnOn = null; });
    });
  });

  // the parade loops seamlessly: a second copy of the herd follows the first
  var row = document.querySelector(".parade .row");
  if (row) row.innerHTML += row.innerHTML;
})();
