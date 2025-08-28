function search(type, data, searchString) {
  const lowerSearch = searchString.toLowerCase();

  data.forEach(dataObj => {
    const [name, id] = Object.entries(dataObj)[0];
    if (name.includes(lowerSearch)) {
      const element = document.getElementById(`${type}-${id}`);
      if (element) element.style.display = 'flex';
    } else {
      const element = document.getElementById(`${type}-${id}`);
      if (element) element.style.display = 'none';
    }
  });
}

function debounce(func, delay) {
  // Returns a debounced version of the function that delays its execution.
  // This is needed to prevent too many calls to search function for large lists.
  let timeout;
  return function (...args) {
    clearTimeout(timeout);
    timeout = setTimeout(() => func.apply(this, args), delay);
  };
}

document.addEventListener("DOMContentLoaded", function () {
  const dataContainer = document.getElementById('data-container');
  const orgRepositories = JSON.parse(dataContainer.dataset.repositories);
  const orgProjects = JSON.parse(dataContainer.dataset.projects);

  const searchRepositoriesInput = document.getElementById("repository-search");
  const searchProjectsInput = document.getElementById("project-search");

  // Prevent default form submission on Enter key press in search inputs
  [searchRepositoriesInput, searchProjectsInput].forEach(input => {
    input.addEventListener("keydown", function (event) {
      if (event.key === "Enter") event.preventDefault();
    });
  });

  searchRepositoriesInput.addEventListener("input", debounce(function () {
    search("repository", orgRepositories, this.value);
  }, 300));

  searchProjectsInput.addEventListener("input", debounce(function () {
    search("project", orgProjects, this.value);
  }, 300));
});
