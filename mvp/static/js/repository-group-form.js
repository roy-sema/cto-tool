(function () {
  const potential_productivity_improvement_defaults = JSON.parse(document.currentScript.nextElementSibling.textContent);
  const select = document.getElementById('potential_productivity_improvement');
  const range = document.getElementById('potential_productivity_improvement_percentage');

  select.addEventListener('change', potential_productivity_improvement_changed);

  function potential_productivity_improvement_changed() {
    const value = select.value;
    if (value === 'unselected') {
      range.setAttribute('disabled', 'disabled');
      range.value = 0;
    } else {
      range.removeAttribute('disabled');
      range.value = potential_productivity_improvement_defaults[value];
    }
    range.oninput();
  }

  if (!range.value || range.value === '0') potential_productivity_improvement_changed();
})();
