// Google アナリティクス (GA4)。測定 ID はここ 1 か所だけ。空のうちは何も送らない。
(function () {
  var ID = 'G-F5CDXGCPRV';
  window.dataLayer = window.dataLayer || [];
  function gtag() { window.dataLayer.push(arguments); }
  window.track = function (name, params) { if (ID) gtag('event', name, params || {}); };
  if (!ID) return;
  var s = document.createElement('script'); s.async = true; s.src = 'https://www.googletagmanager.com/gtag/js?id=' + ID; document.head.appendChild(s);
  gtag('js', new Date()); gtag('config', ID);
})();
