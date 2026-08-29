import { mkdir, writeFile } from "node:fs/promises";

const user = process.env.PROFILE_USER || "thotashashank302";
const token = process.env.GITHUB_TOKEN || "";
const headers = {
  Accept: "application/vnd.github+json",
  "User-Agent": "profile-telemetry-renderer",
  ...(token ? { Authorization: `Bearer ${token}` } : {}),
};

const getJson = async (url) => {
  const response = await fetch(url, { headers });
  if (!response.ok) throw new Error(`${url} returned ${response.status}`);
  return response.json();
};

const escapeXml = (value) => String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;" })[char]);

async function getContributionDays() {
  const response = await fetch(`https://github.com/users/${user}/contributions`, { headers: { "User-Agent": headers["User-Agent"] } });
  if (!response.ok) throw new Error(`Contribution calendar returned ${response.status}`);
  const html = await response.text();
  const days = [];
  const pattern = /data-date="([^"]+)"[\s\S]*?<tool-tip[\s\S]*?>(No contributions|([0-9]+) contributions?)[^<]*<\/tool-tip>/g;
  for (const match of html.matchAll(pattern)) days.push({ date: match[1], count: Number(match[3] || 0) });
  if (!days.length) throw new Error("No contribution days found");
  return days;
}

const repos = (await getJson(`https://api.github.com/users/${user}/repos?per_page=100&type=owner&sort=updated`)).filter((repo) => !repo.fork);
const languageTotals = {};
for (const repo of repos) {
  const languages = await getJson(repo.languages_url);
  for (const [language, bytes] of Object.entries(languages)) languageTotals[language] = (languageTotals[language] || 0) + bytes;
}

const contributionDays = await getContributionDays();
const totalContributions = contributionDays.reduce((sum, day) => sum + day.count, 0);
const monthMap = new Map();
for (const day of contributionDays) {
  const key = day.date.slice(0, 7);
  monthMap.set(key, (monthMap.get(key) || 0) + day.count);
}
const months = [...monthMap.entries()].slice(-12);
const maxMonth = Math.max(1, ...months.map(([, count]) => count));
const stars = repos.reduce((sum, repo) => sum + repo.stargazers_count, 0);
const languageEntries = Object.entries(languageTotals).sort((a, b) => b[1] - a[1]).slice(0, 5);
const languageBytes = Math.max(1, languageEntries.reduce((sum, [, bytes]) => sum + bytes, 0));
const palette = ["#67E8F9", "#818CF8", "#C084FC", "#F0ABFC", "#94A3B8"];
const monthNames = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];

const bars = months.map(([month, count], index) => {
  const height = Math.max(count ? 5 : 2, Math.round((count / maxMonth) * 94));
  const x = 56 + index * 57;
  const label = monthNames[Number(month.slice(5, 7)) - 1];
  return `<g><rect x="${x}" y="${250 - height}" width="31" height="${height}" rx="6" fill="url(#bar)" opacity="${count ? 0.92 : 0.2}"/><text x="${x + 15.5}" y="271" text-anchor="middle" class="month">${label}</text></g>`;
}).join("");

const trackWidth = 368;
const segmentGap = 3;
const segmentSpace = trackWidth - segmentGap * Math.max(0, languageEntries.length - 1);
let allocatedLanguageWidth = 0;
let languageX = 760;
const languageSegments = languageEntries.map(([language, bytes], index) => {
  const width = index === languageEntries.length - 1
    ? segmentSpace - allocatedLanguageWidth
    : Math.max(1, Math.floor((bytes / languageBytes) * segmentSpace));
  const segment = `<rect x="${languageX}" y="182" width="${width}" height="12" rx="6" fill="${palette[index]}"/>`;
  allocatedLanguageWidth += width;
  languageX += width + segmentGap;
  return segment;
}).join("");
const languageLegend = languageEntries.map(([language, bytes], index) => {
  const y = 224 + index * 30;
  const percent = Math.round((bytes / languageBytes) * 100);
  return `<circle cx="770" cy="${y - 5}" r="5" fill="${palette[index]}"/><text x="786" y="${y}" class="legend">${escapeXml(language)}</text><text x="1128" y="${y}" text-anchor="end" class="percent">${percent}%</text>`;
}).join("");

const generated = new Date().toISOString().slice(0, 10);
const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="420" viewBox="0 0 1200 420" role="img" aria-labelledby="title desc">
<title id="title">GitHub mission telemetry for ${escapeXml(user)}</title><desc id="desc">${repos.length} owned public repositories, ${totalContributions} contributions in the last year, ${stars} stars, monthly contribution bars and primary language distribution.</desc>
<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#05070C"/><stop offset=".58" stop-color="#0A1020"/><stop offset="1" stop-color="#100A1E"/></linearGradient><linearGradient id="bar" x1="0" y1="1" x2="0" y2="0"><stop stop-color="#6366F1"/><stop offset="1" stop-color="#67E8F9"/></linearGradient><pattern id="grid" width="34" height="34" patternUnits="userSpaceOnUse"><path d="M34 0H0V34" fill="none" stroke="#93C5FD" stroke-opacity=".05"/></pattern><style>.label{fill:#8496B8;font:650 12px Inter,system-ui,sans-serif;letter-spacing:1.8px}.value{fill:#F8FAFC;font:760 34px Inter,system-ui,sans-serif}.heading{fill:#EAF6FF;font:720 20px Inter,system-ui,sans-serif}.month{fill:#7185A6;font:650 9px Inter,system-ui,sans-serif;letter-spacing:.8px}.legend{fill:#C9D5EA;font:560 13px Inter,system-ui,sans-serif}.percent{fill:#8CA3B8;font:650 12px Inter,system-ui,sans-serif}.foot{fill:#617391;font:550 10px Inter,system-ui,sans-serif;letter-spacing:1px}</style></defs>
<rect width="1200" height="420" rx="18" fill="url(#bg)"/><rect width="1200" height="420" rx="18" fill="url(#grid)"/>
<text x="56" y="48" class="label">LIVE MISSION TELEMETRY</text><circle cx="1118" cy="43" r="5" fill="#67E8F9"><animate attributeName="opacity" values=".3;1;.3" dur="2.4s" repeatCount="indefinite"/></circle><text x="1132" y="47" class="foot">SYNCED</text>
<g transform="translate(56 72)"><text y="33" class="value">${repos.length}</text><text y="56" class="label">OWNED REPOS</text></g><g transform="translate(250 72)"><text y="33" class="value">${totalContributions}</text><text y="56" class="label">YEAR SIGNALS</text></g><g transform="translate(482 72)"><text y="33" class="value">${stars}</text><text y="56" class="label">STARS EARNED</text></g>
<path d="M724 72V334" stroke="#818CF8" stroke-opacity=".18"/>
<text x="56" y="159" class="heading">Contribution trajectory</text><text x="56" y="184" class="label">LAST 12 MONTHS</text>${bars}
<text x="760" y="114" class="heading">Language signal</text><text x="760" y="141" class="label">BY PUBLIC CODE VOLUME</text><rect x="760" y="182" width="368" height="12" rx="6" fill="#172033"/>${languageSegments}${languageLegend}
<text x="56" y="390" class="foot">PUBLIC GITHUB DATA · UPDATED ${generated}</text><text x="1128" y="390" text-anchor="end" class="foot">OWNED ASSET · NO LIVE CARD SERVICE</text>
</svg>`;

await mkdir("assets", { recursive: true });
await writeFile("assets/mission-telemetry.svg", svg);
console.log(`Rendered ${repos.length} repositories, ${totalContributions} contributions and ${languageEntries.length} languages.`);
