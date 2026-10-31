(() => {
  "use strict";
  const records = JSON.parse(document.getElementById("glossary-search-data").textContent);
  const input = document.getElementById("glossary-search");
  const results = document.getElementById("glossary-results");
  const count = document.getElementById("glossary-match-count");
  const empty = document.getElementById("glossary-no-matches");
  const normalize = (value) => value.normalize("NFKC").toLowerCase()
    .replace(/ß/gu, "ss").replace(/ς/gu, "σ")
    .replace(/[-‐‑–—]/gu, " ").replace(/\s+/gu, " ").trim();
  const index = records.map((record) => ({...record,
    names: [record.term, ...record.aliases].map(normalize)}));
  let matches = [];
  let active = -1;
  let highlighted = null;
  let highlightTimer = null;

  function activate(position) {
    active = position;
    Array.from(results.children).forEach((option, i) => {
      option.setAttribute("aria-selected", String(i === active));
    });
    if (active >= 0) {
      const option = results.children[active];
      input.setAttribute("aria-activedescendant", option.id);
      option.scrollIntoView({block: "nearest"});
    } else {
      input.removeAttribute("aria-activedescendant");
    }
  }

  function select(position) {
    const match = matches[position];
    if (!match) return;
    const entry = document.getElementById(match.record.id);
    if (!entry) return;
    if (highlighted) highlighted.classList.remove("is-highlighted");
    window.clearTimeout(highlightTimer);
    highlighted = entry;
    entry.classList.add("is-highlighted");
    entry.scrollIntoView({behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start"});
    entry.focus({preventScroll: true});
    highlightTimer = window.setTimeout(() => {
      entry.classList.remove("is-highlighted");
      if (highlighted === entry) highlighted = null;
    }, 2400);
  }

  function search() {
    const query = normalize(input.value);
    matches = [];
    if (query) {
      index.forEach((record, order) => {
        let rank = Infinity;
        let name = -1;
        record.names.forEach((value, i) => {
          const score = value === query ? 0 : value.startsWith(query) ? 1 : value.includes(query) ? 2 : Infinity;
          if (score < rank) {rank = score; name = i;}
        });
        if (Number.isFinite(rank)) matches.push({record, rank, name, order});
      });
      matches.sort((a, b) => a.rank - b.rank || a.order - b.order);
    }
    results.replaceChildren();
    matches.forEach((match, position) => {
      const option = document.createElement("li");
      option.id = "glossary-option-" + match.record.id;
      option.setAttribute("role", "option");
      const term = document.createElement("span");
      term.textContent = match.record.term;
      const detail = document.createElement("small");
      detail.textContent = match.record.id + (match.name > 0 ? " · Alias: " + match.record.aliases[match.name - 1] : "");
      option.append(term, detail);
      option.addEventListener("click", () => select(position));
      results.append(option);
    });
    results.hidden = matches.length === 0;
    empty.hidden = !query || matches.length > 0;
    input.setAttribute("aria-expanded", String(matches.length > 0));
    count.textContent = query
      ? matches.length + " matching " + (matches.length === 1 ? "entry" : "entries")
      : records.length + " glossary " + (records.length === 1 ? "entry" : "entries");
    activate(matches.length ? 0 : -1);
  }

  input.addEventListener("input", search);
  input.addEventListener("keydown", (event) => {
    if (!matches.length) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      activate((active + (event.key === "ArrowDown" ? 1 : -1) + matches.length) % matches.length);
    } else if (event.key === "Enter") {
      event.preventDefault();
      select(active < 0 ? 0 : active);
    }
  });
  search();
})();
