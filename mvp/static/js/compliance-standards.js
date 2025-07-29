(function () {
  const geographiesLength = JSON.parse(document.currentScript.nextElementSibling.textContent);
  const industriesLength = JSON.parse(document.currentScript.nextElementSibling.nextElementSibling.textContent);
  const search_input = document.getElementById("search");
  const relevance_option = document.getElementById("relevance_option");

  document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('filter-form');
    const filterLocation = document.getElementById('filter-location');
    const filterIndustry = document.getElementById('filter-industry');

    form.addEventListener('submit', (_event) => {
      resetIfAllSelected(filterLocation, geographiesLength);
      resetIfAllSelected(filterIndustry, industriesLength);
      search_input.value = search_input.value.replace(/\s+/g, ' ').trim();
    });

    function resetIfAllSelected(filterElement, totalOptions) {
      const selectedOptions = Array.from(filterElement.selectedOptions);
      if (selectedOptions.length >= totalOptions || selectedOptions.length === 0) {
        filterElement.selectedIndex = -1; // remove selected
        filterElement.appendChild(new Option('all', 'all')).selected = true; // Create & select "all" option
      }
    }
  });

  // adds a 'relevance' option and select it when user starts typing
  search_input.addEventListener("keyup", (e) => {
    if (e.target.value.trim().length > 0) {
      relevance_option.disabled = false
      relevance_option.hidden = false;
      relevance_option.selected = true;
    } else {
      relevance_option.disabled = true
      relevance_option.hidden = true;
      relevance_option.selected = false;
    }
  })

})();
