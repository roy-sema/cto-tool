(function () {
  var conditionsList = document.getElementById('form-conditions-list');
  if (!conditionsList) {
    return;
  }

  var numInitialForms = parseInt(document.getElementById('id_conditions-INITIAL_FORMS').value);
  var totalForms = document.getElementById('id_conditions-TOTAL_FORMS');
  var conditionTemplate = conditionsList.querySelector('.template');
  var addBtn = document.getElementById('add-btn');

  addBtn.addEventListener('click', function (e) {
    e.preventDefault();

    var condition = conditionTemplate.cloneNode(true);
    condition.classList.remove('template', 'hidden');
    condition.classList.add('condition');
    index = getConditions().length;
    removeDeleteConditionHiddenInput(index);
    conditionsList.appendChild(condition);
    updateConditionsIndexes();
  });

  conditionsList.addEventListener('click', function (e) {
    e.preventDefault();
    var target = e.target;
    var button = target.tagName.toLowerCase() === 'button' ? target : target.closest('.delete-btn');
    if (button) {
      var condition = target.closest('.condition');
      condition.remove();
      updateConditionsIndexes();
    }
  });

  function getConditions() {
    return conditionsList.querySelectorAll('.condition:not(.template)')
  }

  function updateConditionsIndexes() {
    var conditions = getConditions();
    var numConditions = conditions.length;
    totalForms.value = numConditions;
    conditions.forEach(function (condition, index) {
      condition.querySelectorAll('input, select').forEach(function (input) {
        input.setAttribute('name', input.getAttribute('name').replace(/-\d+-/, '-' + index + '-'));
        input.setAttribute('id', input.getAttribute('id').replace(/-\d+-/, '-' + index + '-'));
      });
    });

    var missingForms = numInitialForms - numConditions;
    if (missingForms) {
      for (var i=0; i < missingForms; i++) {
        var index = numConditions + i;
        addDeleteConditionHiddenInput(index);
      }
    }
  }

  function addDeleteConditionHiddenInput(index) {
    var input = document.getElementById('id_conditions-' + index + '-DELETE');
    if (input) {
      return;
    }

    var input = document.createElement('input');
    input.setAttribute('type', 'hidden');
    input.setAttribute('id', 'id_conditions-' + index + '-DELETE');
    input.setAttribute('name', 'conditions-' + index + '-DELETE');
    input.setAttribute('value', 'on');
    conditionsList.appendChild(input);
  }

  function removeDeleteConditionHiddenInput(index) {
    var input = document.getElementById('id_conditions-' + index + '-DELETE');
    if (input) {
      input.remove();
    }
  }
})();
