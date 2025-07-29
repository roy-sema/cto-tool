document.addEventListener("DOMContentLoaded", function () {
  const form = document.querySelector("form");
  if (!form) return;

  form.addEventListener("submit", function () {
    const data = { initiatives: [] };

    // Collect all initiative rows
    const initiativeRows = document.querySelectorAll("tr[data-initiative-id]");
    const epicRows = document.querySelectorAll("tr[data-epic-id]");

    // Prepare a map from initiative id to its data
    const initiativeMap = {};

    initiativeRows.forEach((row) => {
      const id = String(row.getAttribute("data-initiative-id")); // Convert to string
      initiativeMap[id] = {
        id: id,
        pinned: row.querySelector(".inp-pinned")?.checked || false,
        disabled: false, // Default to false as the UI no longer has this field
        custom_name: row.querySelector(".inp-customname")?.value || "",
        epics: []
      };
    });

    // Assign each epic to the correct parent
    epicRows.forEach((row) => {
      const parentId = String(row.getAttribute("data-parent-id")); // Convert to string
      const epicId = String(row.getAttribute("data-epic-id"));
            
      if (!initiativeMap[parentId]) {
        return;
      }

      initiativeMap[parentId].epics.push({
        id: epicId,
        pinned: row.querySelector(".epic-inp-pinned")?.checked || false,
        disabled: false, // Default to false as the UI no longer has this field
        custom_name: row.querySelector(".epic-inp-customname")?.value || ""
      });
    });

    // Fill initiatives array
    data.initiatives = Object.values(initiativeMap);

    // Write to hidden input
    document.getElementById("jsonPayload").value = JSON.stringify(data);
  });
});
