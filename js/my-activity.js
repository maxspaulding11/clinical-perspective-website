// "My Activity" panel on queue.html — shows the studies you've submitted
// and voted for, once signed in. Only present on the archive page.

(function () {
  const section = document.getElementById("my-activity");
  const submittedList = document.getElementById("my-activity-submitted");
  const votedList = document.getElementById("my-activity-voted");
  const origin = window.SPARE_CHANGE_ORIGIN;
  if (!section || !submittedList || !votedList || !origin || !window.spareChangeSession) return;

  function renderList(el, items, emptyText) {
    el.innerHTML = "";
    if (!items.length) {
      const li = document.createElement("li");
      li.className = "queue-empty";
      li.textContent = emptyText;
      el.appendChild(li);
      return;
    }
    items.forEach((item) => {
      const li = document.createElement("li");
      li.className = "queue-item";
      const link = document.createElement("a");
      link.href = item.url;
      link.target = "_blank";
      link.rel = "noopener nofollow";
      link.className = "queue-item-title";
      link.textContent = item.title;
      li.appendChild(link);
      el.appendChild(li);
    });
  }

  window.spareChangeSession.then((user) => {
    if (!user) return;
    section.hidden = false;
    fetch(origin + "/api/queue/mine", { credentials: "include" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!data) return;
        renderList(submittedList, data.submitted, "You haven't submitted any studies yet.");
        renderList(votedList, data.voted, "You haven't voted for any studies yet.");
      })
      .catch(() => {});
  });
})();
