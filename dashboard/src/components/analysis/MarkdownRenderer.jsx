/** Render a markdown string to HTML for AI prose output. */

function mdInline(text) {
  return text
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/`(.+?)`/g, "<code>$1</code>");
}

export function renderMarkdown(md) {
  const lines = md.split("\n");
  let html = "", inUl = false, inOl = false, inTable = false, thDone = false;
  const closeAll = () => {
    if (inUl) { html += "</ul>"; inUl = false; }
    if (inOl) { html += "</ol>"; inOl = false; }
    if (inTable) { html += "</tbody></table>"; inTable = false; thDone = false; }
  };
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.startsWith("#### ")) { closeAll(); html += "<h4>" + mdInline(line.slice(5)) + "</h4>"; continue; }
    if (line.startsWith("### ")) { closeAll(); html += "<h3>" + mdInline(line.slice(4)) + "</h3>"; continue; }
    if (line.startsWith("## ")) { closeAll(); html += "<h2>" + mdInline(line.slice(3)) + "</h2>"; continue; }
    if (line.startsWith("# ")) { closeAll(); html += "<h2>" + mdInline(line.slice(2)) + "</h2>"; continue; }
    if (/^[-*]{3,}\s*$/.test(line)) { closeAll(); html += "<hr>"; continue; }
    if (/^\|[\s\-:|]+\|$/.test(line)) { thDone = true; continue; }
    if (line.startsWith("|") && line.endsWith("|")) {
      if (inUl) { html += "</ul>"; inUl = false; }
      if (inOl) { html += "</ol>"; inOl = false; }
      const cells = line.slice(1, -1).split("|").map((c) => c.trim());
      if (!inTable) { html += "<table><thead>"; inTable = true; thDone = false; }
      const tag = thDone ? "td" : "th";
      html += "<tr>" + cells.map((c) => "<" + tag + ">" + mdInline(c) + "</" + tag + ">").join("") + "</tr>";
      if (!thDone && i + 1 < lines.length && /^\|[\s\-:|]+\|$/.test(lines[i + 1])) {
        html += "</thead><tbody>";
      }
      continue;
    }
    if (inTable) { html += "</tbody></table>"; inTable = false; thDone = false; }
    if (/^[-*]\s/.test(line)) {
      if (inOl) { html += "</ol>"; inOl = false; }
      if (!inUl) { html += "<ul>"; inUl = true; }
      html += "<li>" + mdInline(line.replace(/^[-*]\s/, "")) + "</li>";
      continue;
    }
    if (inUl) { html += "</ul>"; inUl = false; }
    if (/^\d+\.\s/.test(line)) {
      if (inUl) { html += "</ul>"; inUl = false; }
      if (!inOl) { html += "<ol>"; inOl = true; }
      html += "<li>" + mdInline(line.replace(/^\d+\.\s/, "")) + "</li>";
      continue;
    }
    if (inOl) { html += "</ol>"; inOl = false; }
    if (!line.trim()) continue;
    html += "<p>" + mdInline(line) + "</p>";
  }
  closeAll();
  return html;
}

/** Preact component that renders markdown as dangerouslySetInnerHTML. */
export function Prose({ markdown }) {
  if (!markdown) return null;
  return <div class="ai-prose" dangerouslySetInnerHTML={{ __html: renderMarkdown(markdown) }} />;
}
