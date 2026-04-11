// Calendrier — interactions générales
document.addEventListener('DOMContentLoaded', () => {

  // Tooltip sur les bandes de réservation (fallback title)
  document.querySelectorAll('.resa-band').forEach(band => {
    band.addEventListener('mouseenter', e => {
      const tip = band.getAttribute('title');
      if (tip) band.setAttribute('aria-label', tip);
    });
  });

  // Confirmation suppression depuis la liste
  document.querySelectorAll('form[data-confirm]').forEach(form => {
    form.addEventListener('submit', e => {
      if (!confirm(form.dataset.confirm)) e.preventDefault();
    });
  });

});
