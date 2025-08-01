(function () {
  var checkboxLists = document.querySelectorAll('.checkbox-list');
  checkboxLists.forEach(function (checkboxList) {
    initCheckboxList(checkboxList);
  });

  function initCheckboxList(checkboxList) {
    var checkboxes = checkboxList.querySelectorAll('input[type="checkbox"]');
    var selectAll = checkboxList.querySelector('.checkbox-list-select-all');
    var selectNone = checkboxList.querySelector('.checkbox-list-select-none');
    var numSelected = checkboxList.querySelector('.checkbox-list-num-selected');

    function updateNumSelected() {
      var numChecked = checkboxList.querySelectorAll('input[type="checkbox"]:checked').length;
      numSelected.textContent = numChecked;
    }

    selectAll.addEventListener('click', function (e) {
      e.preventDefault();
      checkboxes.forEach(function (checkbox) {
        checkbox.checked = true;
      });
      updateNumSelected();
    });

    selectNone.addEventListener('click', function (e) {
      e.preventDefault();
      checkboxes.forEach(function (checkbox) {
        checkbox.checked = false;
      });
      updateNumSelected();
    });

    checkboxList.addEventListener('change', function (e) {
      if (e.target.type !== 'checkbox') return;
      updateNumSelected();
    });
  }
})();
