// page.js — the war table page's script (kept out of the page, so its Content-Security-Policy can allow scripts from this site only)
(function () {
  // the Play bar on a phone shows while neither of the page's own Play buttons is in sight
  var dock = document.getElementById("dock"), seen = {};
  if (dock && "IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) { seen[e.target.id] = e.isIntersecting; });
      dock.classList.toggle("on", !seen.play && !seen.play2);
    }, { threshold: 0 });
    ["play", "play2"].forEach(function (id) { var el = document.getElementById(id); if (el) io.observe(el); });
  }

  // Share: the phone's own share sheet where there is one, else the link copied
  var share = document.getElementById("share"), url = "https://tensorrent.github.io/CLI-Tortoises-Demo/wartles/";
  if (share) share.addEventListener("click", function () {
    var said = function (t) { share.textContent = t; setTimeout(function () { share.textContent = "Share the link"; }, 2200); };
    if (navigator.share) { navigator.share({ title: "Wartles & Wartoises", text: "Turtles against tortoises: a free war in your browser.", url: url }).catch(function () {}); return; }
    if (navigator.clipboard) navigator.clipboard.writeText(url).then(function () { said("Link copied"); }, function () { said("Copy it from below"); });
    else said("Copy it from below");
  });
})();
