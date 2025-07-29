const reRunAnalysis = async () => {
  const url = `${ BASE_URL }/api/repositories/${ REPOSITORY_PUBLIC_ID }/pulls/${ PULL_REQUEST_NUMBER }/re-run-analysis/`;
  const response = await fetch(url);
  if (!response.ok) {
    alert("Failed to re-run the analysis. Please try again later.");
  }
  window.location.reload();
}

const reRunAnalysisButton = () => {
  let userConfirmed = window.confirm("This operation will take some time. Are you sure?");
  if (userConfirmed) {
    const reRunAnalysisButton = document.getElementById("reRunAnalysisButton");
    reRunAnalysisButton.classList.add("hidden");
    reRunAnalysis()
  }
};
