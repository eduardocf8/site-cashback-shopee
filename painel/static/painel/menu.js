/* Menu do celular: o botão "Menu" da barra do topo abre a lista completa por cima da tela
 * (a mesma do menu lateral do computador). "Fechar" e a tecla Esc fecham. */
(function () {
  var menu = document.getElementById('menu-principal');
  var abrir = document.querySelector('[data-abrir-menu]');
  if (!menu || !abrir) return;
  var fechar = menu.querySelector('[data-fechar-menu]');

  function mudar(aberto) {
    menu.classList.toggle('aberto', aberto);
    document.documentElement.classList.toggle('menu-aberto', aberto);
    abrir.setAttribute('aria-expanded', aberto ? 'true' : 'false');
    if (aberto && fechar) fechar.focus();
    else if (!aberto) abrir.focus();
  }

  abrir.addEventListener('click', function () { mudar(true); });
  if (fechar) fechar.addEventListener('click', function () { mudar(false); });
  document.addEventListener('keydown', function (evento) {
    if (evento.key === 'Escape' && menu.classList.contains('aberto')) mudar(false);
  });
  // Tela que cresce (celular deitado, janela maior): volta o menu lateral, sem a tela por cima.
  var largo = window.matchMedia('(min-width: 901px)');
  var aoMudar = function () { if (largo.matches && menu.classList.contains('aberto')) mudar(false); };
  if (largo.addEventListener) largo.addEventListener('change', aoMudar);
})();
