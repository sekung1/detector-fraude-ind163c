// Validación básica en el navegador y bloqueo de doble envío.
// El servidor vuelve a validar todo; esto solo da aviso inmediato al usuario.
document.querySelectorAll('form').forEach(function (form) {
  form.addEventListener('submit', function (evento) {
    const vacios = Array.from(form.querySelectorAll('[required]')).filter(function (campo) {
      return !String(campo.value || '').trim();
    });
    if (vacios.length) {
      evento.preventDefault();
      vacios[0].focus();
      vacios.forEach(function (campo) { campo.setAttribute('aria-invalid', 'true'); });
      return;
    }
    const boton = form.querySelector('button[type="submit"]');
    if (boton) {
      boton.dataset.texto = boton.textContent;
      boton.disabled = true;
      boton.textContent = 'Evaluando…';
    }
  });
});

// Si el usuario vuelve con el botón "atrás", reactivamos el botón.
window.addEventListener('pageshow', function () {
  document.querySelectorAll('button[type="submit"][disabled]').forEach(function (boton) {
    boton.disabled = false;
    boton.textContent = boton.dataset.texto || 'Evaluar';
  });
});
